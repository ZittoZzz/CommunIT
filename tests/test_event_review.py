"""Review, expiry and stable platform identity through saved data and API."""
from copy import deepcopy
from datetime import timedelta
from html import escape
import json

import pytest

from backend import db
from backend.adapters import rss
from backend.domain import event_key, parse_moment
from backend.luma import parse_event
from backend.network import FetchError
from backend.topics import project_topics
from test_opportunity_pages import NOW, MEETUP, schema, page, verify
from test_topics import announcement
from test_luma import detail, page as luma_page, SOURCE as LUMA_SOURCE, EVENT as LUMA_EVENT

SOURCE = {'id': 'feed', 'name': 'Example feed', 'kind': 'rss', 'content_complete': True,
          'url': 'https://www.meetup.com/example-builders/events/rss/'}


def seed(payload, at=NOW):
    conn = db.connect(':memory:')
    db.register_sources(conn, [SOURCE])
    db.ingest(conn, SOURCE['id'], payload, at.isoformat())
    return conn


@pytest.mark.parametrize('access', ['search_only', 'full'])
def test_unresolved_expiry_is_visible_and_rediscovery_does_not_reset_it(access):
    ann = announcement('', access=access)
    conn = seed(ann)
    first = db.events(conn, NOW, window_days=45)[0]
    assert first['review']['required'] and not first['review']['expired']
    db.ingest(conn, 'feed', ann, (NOW + timedelta(days=44)).isoformat())
    event = db.events(conn, NOW + timedelta(days=45), window_days=45)[0]
    assert event['section'] == 'archived'
    assert event['review']['expired']
    assert event['status'] not in ('finished', 'past_date')
    assert event['registration_status'] == 'unknown'
    assert len(db.events(conn, NOW + timedelta(days=90))) == 1
    if access == 'search_only':
        assert event['verification']['last_content_fetched_at'] is None
        assert db.events(conn, NOW)[0]['section'] == 'watchlist'
    # Newly verified schedule can resolve a stale lead without losing its age.
    ann['access'] = 'full'
    ann['facts']['start'] = parse_moment((NOW + timedelta(days=50)).isoformat())
    db.ingest(conn, 'feed', ann, (NOW + timedelta(days=46)).isoformat())
    event = db.events(conn, NOW + timedelta(days=46), window_days=45)[0]
    assert event['section'] == 'upcoming' and not event['review']['required']
    assert event['first_seen'] == NOW.isoformat()


def test_search_observation_cannot_advance_successful_content_check():
    ann = announcement('Cloud computing workshop')
    conn = seed(ann)
    search = deepcopy(ann); search['access'] = 'search_only'
    db.ingest(conn, 'feed', search, (NOW + timedelta(days=1)).isoformat())
    event = db.events(conn, NOW)[0]
    assert event['verification']['last_content_fetched_at'] == NOW.isoformat()
    assert event['verification']['last_event_page_checked_at'] is None
    assert event['verification']['last_observed_at'] == (NOW + timedelta(days=1)).isoformat()


def test_legacy_structured_meetup_is_not_mislabeled_as_a_feed():
    ann, _ = verify(page())
    ann.pop('verification_method')
    event, = db.events(seed(ann), NOW)
    assert not event['review']['required']
    assert event['verification']['last_event_page_checked_at'] == NOW.isoformat()


def test_matched_full_meetup_description_preserves_restricted_student_eligibility():
    node = schema(); node['description'] = 'Only currently enrolled students of the'
    description = 'Only currently enrolled students of the Example University are allowed to attend.\nLearn cloud computing.'
    metadata = {'props': {'pageProps': {'event': {'id': '1234567', 'description': description}}}}
    ann, _ = verify(page(node, metadata=metadata))
    assert 'Example University are allowed to attend' in ann['facts']['eligibility']
    assert ann['facts']['description'] == description
    # An unrelated recommendation cannot supply the event's requirements.
    metadata['props']['pageProps']['event']['id'] = '9999999'
    ann, _ = verify(page(schema(), metadata=metadata))
    assert ann['facts']['eligibility'] is None


def test_meetup_same_id_updates_title_and_retains_revision_history():
    node = schema(); node['name'] = 'Cloud computing meetup #1'
    ann, _ = verify(page(node)); conn = seed(ann)
    original_id = db.events(conn, NOW)[0]['id']
    node['name'] = 'Cloud computing meetup #2'
    node['startDate'] = '2035-12-01T04:00:00Z'; node['endDate'] = '2035-12-01T08:00:00Z'
    newer, _ = verify(page(node))
    newer['identity']['series'] = 'Changed title identity'
    db.ingest(conn, 'feed', newer, (NOW + timedelta(hours=1)).isoformat())
    event, = db.events(conn, NOW)
    assert event['id'] == original_id and event['name'] == node['name']
    assert event['start']['value'].startswith('2035-12-01')
    assert conn.execute('SELECT count(*) FROM revisions').fetchone()[0] == 2
    assert event['announcements'][0]['revision_count'] == 2
    assert not event['review']['required']
    # A distinct numeric event, even with the same name, remains distinct.
    other = deepcopy(newer); other['url'] = MEETUP.replace('1234567', '7654321')
    other['identity']['edition'] = '7654321'
    db.ingest(conn, 'feed', other, NOW.isoformat())
    assert len(db.events(conn, NOW)) == 2


def test_legacy_duplicate_cards_fold_without_deleting_rows_or_history():
    node = schema(); ann, _ = verify(page(node)); conn = seed(ann)
    # Reproduce rows written by the old title-based identity algorithm.
    old = deepcopy(ann); old['identity']['series'] = 'Old title'
    old['facts']['name'] = 'Old title'; old['facts']['summary'] = 'Old summary'
    old['facts']['competition_date'] = parse_moment('2035-11-04')
    old.pop('verification_method')
    key = event_key(old['identity']); before = (NOW - timedelta(days=1)).isoformat()
    conn.execute('INSERT INTO events VALUES(?,?,?)', (key, json.dumps(old['identity']), before))
    conn.execute('INSERT INTO announcements(event_id,source_id,url,payload,first_seen,last_seen,changed_at) VALUES(?,?,?,?,?,?,?)',
                 (key, 'feed', old['url'], json.dumps(old), before, before, before))
    event, = db.events(conn, NOW)
    assert event['name'] == ann['facts']['name'] and event['summary'] is None
    assert event['competition_date'] is None and event['section'] == 'upcoming'
    assert len(event['announcements']) == 2
    assert conn.execute('SELECT count(*) FROM events').fetchone()[0] == 2
    assert event['first_seen'] == before


def test_meetup_description_conflict_survives_until_a_consistent_page_revision():
    node = schema(); node['name'] = 'Cybersecurity meetup'
    node['description'] = 'Happening on November 4, 2035, the event will feature a CTF competition.'
    ann, _ = verify(page(node)); conn = seed(ann)
    event, = db.events(conn, NOW)
    assert event['status'] == 'date_conflict' and event['section'] == 'unconfirmed'
    assert event['start'] is event['end'] is event['competition_date'] is None
    assert event['review']['required']
    assert {c['date']['value'][:10] for c in event['date_conflicts']} == {'2035-11-04', '2035-11-29'}
    node['description'] = node['description'].replace('November 4', 'November 29')
    ann, _ = verify(page(node)); db.ingest(conn, 'feed', ann, (NOW + timedelta(hours=1)).isoformat())
    event, = db.events(conn, NOW)
    assert event['section'] == 'upcoming' and not event['review']['required']


def test_ctf_track_date_does_not_conflict_with_multiday_meetup_start():
    node = schema(); node['endDate'] = '2035-12-01T08:00:00Z'
    node['description'] = 'Cybersecurity conference.\nCTF date: November 30, 2035'
    ann, _ = verify(page(node))
    assert not ann['facts']['date_conflicts']
    assert ann['facts']['competition_date'] is None


def test_calendar_discovery_keeps_conflicting_event_visible_for_review():
    from backend.opportunity_search import opportunity_search
    from test_opportunity_search import Client
    node = schema(); node['description'] = 'Happening on November 4, 2035, the cloud workshop will take place.'
    calendar = 'https://www.meetup.com/find/ph--manila/technology/'
    source = {'id': 'calendar', 'name': 'Calendar', 'kind': 'opportunity_calendar', 'url': calendar}
    client = Client(pages={calendar: '<a href="' + MEETUP + '">Workshop</a>', MEETUP: page(node)})
    result = opportunity_search(source, client, [], NOW)
    ann, = result.announcements
    assert ann['facts']['date_conflicts']
    assert db.events(seed(ann), NOW, window_days=45)[0]['section'] == 'unconfirmed'


def test_rss_rechecks_even_complete_feeds_and_failures_preserve_known_page():
    node = schema(); node['name'] = 'Security Meetup'
    node['description'] = 'Cybersecurity CTF competition.'
    feed = '<rss version="2.0"><channel><item><title>Old title</title><link>' + MEETUP + '</link><description>' + escape(node['description']) + '</description></item></channel></rss>'
    class Pages:
        failed = False
        def public_page(self, url, allowed_hosts=None):
            if url == SOURCE['url']: return feed
            assert url == MEETUP
            if self.failed: raise FetchError('Page temporarily blocked')
            return page(node)
    client = Pages(); result = rss(SOURCE, client, [], NOW)
    ann, = result.announcements
    assert ann['verification_method'] == 'event_page' and ann['facts']['name'] == 'Security Meetup'
    conn = seed(ann); known = list(conn.execute('SELECT * FROM announcements'))
    client.failed = True
    result = rss(SOURCE, client, known, NOW + timedelta(hours=1))
    assert not result.announcements and result.warnings
    assert db.events(conn, NOW)[0]['verification']['last_event_page_checked_at'] == NOW.isoformat()


def test_parent_luma_schedule_never_becomes_complete_ctf_schedule():
    data = detail()
    data['description_mirror'] = 'A cybersecurity CTF competition, with workshops and an opening ceremony.'
    ann, _ = parse_event(luma_page(data), LUMA_EVENT, LUMA_SOURCE, NOW)
    assert ann['facts']['start'] is ann['facts']['end'] is None
    assert ann['facts']['parent_event_start']['value'].startswith('2032-03-08')
    assert ann['facts']['registration_state'] == 'unknown'
    conn = seed(ann); event, = db.events(conn, NOW)
    assert event['status'] != 'finished' and event['review']['required']
    assert event['parent_event_end']['value']


@pytest.mark.parametrize('text,expected', [
    ('GitHub Actions and CI/CD pipelines.', ['devops']),
    ('Learn Azure cloud services.', ['cloud']),
    ('Deploy to AWS using GitHub Actions.', ['cloud', 'devops']),
    ('Git basics and pull requests.', ['software_development']),
    ('GitHub gathering.', []),
    ('Docker and Kubernetes social.', []),
    ('DevOps workshop.', ['devops']),
])
def test_cloud_and_devops_are_independent_evidence_backed_topics(text, expected):
    assert project_topics([announcement(text)])[0] == expected
