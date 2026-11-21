"""Conservative cross-publisher matching with fictional URLs and competitions."""
from copy import deepcopy

import pytest

from backend.db import connect, events, ingest, register_sources


SOURCES = [{'id': value, 'name': value, 'kind': 'rss', 'url': f'https://{value}.example/feed/'}
           for value in ('publisher', 'organizer')]


def announcement(url='https://publisher.example/news/nebula-2031/', organizer='unconfirmed'):
    registration = 'https://forms.example/register/nebula-2031/'
    return {'url': url, 'title': 'Nebula CTF 2031', 'access': 'full', 'kind': 'registration',
            'identity': {'organizer_key': organizer, 'series': 'Nebula CTF',
                         'edition': '2031', 'region': 'Unspecified', 'stage': 'main'},
            'facts': {'name': 'Nebula CTF 2031', 'organizer': organizer,
                      'registration_url': registration},
            'field_evidence': {'registration_url': {'url': url, 'quote': 'Register here: ' + registration}}}


@pytest.fixture
def db():
    connection = connect(':memory:')
    register_sources(connection, SOURCES)
    yield connection
    connection.close()


def test_same_article_organizer_correction_preserves_id_and_first_seen(db):
    first = announcement()
    event_id, _ = ingest(db, 'publisher', first, '2031-01-01T00:00:00+00:00')
    corrected = announcement(organizer='nebula-club')
    corrected['facts']['registration_url'] = None
    del corrected['field_evidence']['registration_url']
    second_id, created = ingest(db, 'organizer', corrected, '2031-01-02T00:00:00+00:00')
    assert second_id == event_id and created is False
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
    assert db.execute('SELECT count(*) FROM announcements').fetchone()[0] == 1
    assert events(db)[0]['first_seen'] == '2031-01-01T00:00:00+00:00'
    assert events(db)[0]['organizer'] == 'nebula-club'


def test_shared_specific_registration_link_merges_publishers_and_keeps_both_links(db):
    first = announcement()
    event_id, _ = ingest(db, 'publisher', first, '2031-01-01T00:00:00+00:00')
    second = announcement('https://organizer.example/events/nebula-2031/', 'nebula-club')
    incoming_id, created = ingest(db, 'organizer', second, '2031-01-02T00:00:00+00:00')
    assert incoming_id == event_id and created is True
    assert len(events(db)) == 1
    assert {a['url'] for a in events(db)[0]['announcements']} == {first['url'], second['url']}
    repeat_id, repeat_created = ingest(db, 'organizer', second, '2031-01-03T00:00:00+00:00')
    assert repeat_id == event_id and repeat_created is False
    assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 2


@pytest.mark.parametrize('identity_change', [
    {'edition': '2032'}, {'region': 'NCR'}, {'stage': 'qualifier'},
    {'stage': 'final'}, {'stage': 'regional-final'}, {'stage': 'national-final'},
    {'series': 'Orion CTF'},
])
@pytest.mark.parametrize('same_article', [True, False])
def test_shared_urls_do_not_erase_identity_boundaries(db, identity_change, same_article):
    first = announcement()
    ingest(db, 'publisher', first)
    second = announcement(first['url'] if same_article else 'https://organizer.example/events/nebula/', 'nebula-club')
    second['identity'].update(identity_change)
    ingest(db, 'organizer', second)
    assert len(events(db)) == 2


@pytest.mark.parametrize('registration', [
    'https://forms.example/', 'https://forms.example/?id=nebula2031',
    'https://forms.example/register', 'https://forms.example/registration/',
    'https://forms.example/forms/', 'https://forms.example/registration.php',
    'https://forms.example/forms/register.php', 'https://forms.example/event-registration',
])
def test_generic_registration_endpoints_do_not_merge_events(db, registration):
    first = announcement()
    second = announcement('https://organizer.example/events/nebula/', 'nebula-club')
    for ann in (first, second):
        ann['facts']['registration_url'] = registration
    ingest(db, 'publisher', first)
    ingest(db, 'organizer', second)
    assert len(events(db)) == 2


def test_specific_form_query_is_usable_with_matching_identity(db):
    first = announcement()
    second = announcement('https://organizer.example/events/nebula/', 'nebula-club')
    for ann in (first, second):
        ann['facts']['registration_url'] = 'https://forms.example/form?id=nebula2031'
    ingest(db, 'publisher', first)
    ingest(db, 'organizer', second)
    assert len(events(db)) == 1


def test_shared_registration_link_requires_evidence_on_both_announcements(db):
    first = announcement()
    first['field_evidence'] = {}
    second = announcement('https://organizer.example/events/nebula/', 'nebula-club')
    ingest(db, 'publisher', first)
    ingest(db, 'organizer', second)
    assert len(events(db)) == 2


def test_conflicting_known_organizers_do_not_merge_just_from_a_registration_link(db):
    ingest(db, 'publisher', announcement(organizer='one-club'))
    ingest(db, 'organizer', announcement('https://organizer.example/events/nebula/', 'different-club'))
    assert len(events(db)) == 2


def test_no_facebook_opaque_identity_inference_from_permalink(db):
    url = 'https://www.facebook.com/fictional/posts/opaque-fictional-token/'
    first = announcement(url)
    second = announcement(url, 'nebula-club')
    first['facts']['registration_url'] = second['facts']['registration_url'] = None
    ingest(db, 'publisher', first)
    ingest(db, 'organizer', second)
    assert len(events(db)) == 2
