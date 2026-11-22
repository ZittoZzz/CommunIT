"""Publisher identity/provenance regressions; fictional organizations only."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.db import connect, ingest, register_sources
from backend.adapters import Result
from backend.collect import collect
from backend.extract import extract
from backend.publishers import (ensure_schema, harvest, publisher_summaries,
                                sync_configured_publishers, identity_url)


SOURCE = {'id': 'city', 'name': 'Example public city calendar', 'kind': 'rss',
          'url': 'https://calendar.example/feed/', 'organizer': 'Fictional Guild',
          'organizer_key': 'fictional-guild'}
URL = 'https://calendar.example/competition'
FIRST = '2031-01-01T00:00:00+00:00'
SECOND = '2031-01-02T00:00:00+00:00'
LEAD = {'name': 'Fictional Guild', 'role': 'host',
        'url': 'https://luma.com/user/usr-fictional', 'account_id': 'luma:usr-fictional',
        'evidence': {'url': URL, 'quote': 'Hosted by Fictional Guild'}}


@pytest.fixture
def db():
    connection = connect(':memory:')
    register_sources(connection, [SOURCE])
    ensure_schema(connection)
    yield connection
    connection.close()


def event(db):
    announcement = extract('Nebula CTF 2031', 'A cybersecurity competition in Manila, Philippines.', URL, SOURCE)
    return ingest(db, SOURCE['id'], announcement, FIRST)[0]


def test_repeat_runs_keep_one_candidate_relationship_and_first_seen(db):
    event_id = event(db)
    first = harvest(db, 'city', [LEAD], event_id=event_id, now=FIRST)
    second = harvest(db, 'city', [LEAD], event_id=event_id, now=SECOND)
    assert first['new_candidates'] == first['new_relationships'] == 1
    assert second['new_candidates'] == second['new_relationships'] == 0
    [candidate] = publisher_summaries(db)
    assert candidate['first_seen'] == FIRST
    assert candidate['last_seen'] == SECOND
    assert candidate['status'] == 'candidate'
    assert candidate['verified_at'] is None
    assert candidate['event_ids'] == [event_id]
    assert candidate['relationships'][0]['first_seen'] == FIRST
    assert candidate['relationships'][0]['last_seen'] == SECOND
    assert candidate['relationships'][0]['evidence'] == LEAD['evidence']
    assert candidate['relationships'][0]['relationship_status'] == 'competition_confirmed'


def test_shared_account_and_profile_aliases_join_different_events_without_name_matching(db):
    harvest(db, 'city', [LEAD], now=FIRST)
    renamed = deepcopy(LEAD)
    renamed.update(name='Guild public display name', role='sponsor', url='https://lu.ma/user/usr-fictional/?utm_source=other')
    renamed.pop('account_id')
    renamed['evidence'] = {'url': 'https://another.example/announcement', 'quote': 'Sponsored by Guild public display name'}
    result = harvest(db, 'other', [renamed], now=SECOND)
    assert result['new_candidates'] == 0
    [candidate] = publisher_summaries(db)
    assert candidate['roles'] == ['host', 'sponsor']
    assert len(candidate['relationships']) == 2
    assert candidate['names'] == ['Fictional Guild', 'Guild public display name']


def test_same_display_name_different_stable_profiles_remains_separate(db):
    other = {**LEAD, 'url': 'https://different.example/', 'account_id': 'luma:usr-unrelated'}
    harvest(db, 'city', [LEAD, other], now=FIRST)
    candidates = publisher_summaries(db)
    assert len(candidates) == 2
    assert {item['name'] for item in candidates} == {'Fictional Guild'}


@pytest.mark.parametrize('urls', [
    ('https://facebook.com/Example.Club/', 'https://m.facebook.com/example.club?utm_source=calendar',
     'https://www.facebook.com/example.club'),
    ('https://facebook.com/groups/123456789/', 'https://m.facebook.com/groups/123456789?ref=share',
     'https://www.facebook.com/groups/123456789'),
    ('https://facebook.com/profile.php?id=987654321', 'https://m.facebook.com/profile.php?id=987654321&locale=en_US',
     'https://www.facebook.com/profile.php?id=987654321'),
])
def test_facebook_known_profile_and_group_variants_deduplicate(db, urls):
    first, second, expected = urls
    lead = {key: value for key, value in LEAD.items() if key != 'account_id'}
    harvest(db, 'city', [{**lead, 'url': first}], now=FIRST)
    result = harvest(db, 'city', [{**lead, 'url': second}], now=SECOND)
    assert result['new_candidates'] == 0
    [candidate] = publisher_summaries(db)
    assert candidate['public_url'] == expected


@pytest.mark.parametrize('url', [
    'https://facebook.com/profile.php?name=Example.Club',
    'https://facebook.com/profile.php?id=not-numeric',
    'https://facebook.com/Example.Club/posts/123456789',
    'https://facebook.com/groups/123456789/posts/555555555',
    'https://facebook.com/story.php?id=987654321&story_fbid=123456789',
    'https://facebook.com/photo.php?fbid=123456789',
    'https://facebook.com/share/p/opaque',
])
def test_facebook_post_or_unsupported_profile_url_never_infers_publisher(url):
    assert identity_url(url) is None


def test_facebook_relationship_post_is_still_retained_as_source_evidence(db):
    url = 'https://facebook.com/Example.Club/posts/123456789'
    lead = {**LEAD, 'evidence': {'url': url, 'quote': 'Hosted by Fictional Guild'}}
    harvest(db, 'city', [lead], announcement_url=url, now=FIRST)
    [candidate] = publisher_summaries(db)
    assert candidate['relationships'][0]['announcement_url'] == url
    assert candidate['relationships'][0]['evidence']['url'] == url


def test_missing_identity_scoped_to_evidence_not_name_across_events(db):
    lead = {'name': 'Fictional Guild', 'role': 'host', 'evidence': LEAD['evidence']}
    second = {**lead, 'evidence': {'url': 'https://elsewhere.example/invitation', 'quote': 'Hosted by Fictional Guild'}}
    harvest(db, 'city', [lead, second], now=FIRST)
    repeated = harvest(db, 'city', [lead, second], now=SECOND)
    assert repeated['new_candidates'] == repeated['new_relationships'] == 0
    assert len(publisher_summaries(db)) == 2
    assert {row['identity_status'] for row in publisher_summaries(db)} == {'evidence_only'}


def test_namespaced_account_only_identity_is_stable_but_bare_id_is_not(db):
    account = {**LEAD, 'account_id': {'namespace': 'Luma', 'id': 'usr-fictional'}}
    account.pop('url')
    harvest(db, 'city', [account], now=FIRST)
    result = harvest(db, 'city', [LEAD], now=SECOND)
    assert result['new_candidates'] == 0
    [candidate] = publisher_summaries(db)
    assert candidate['account_id'] == 'luma:usr-fictional'
    assert candidate['public_url'] == LEAD['url']
    bare = {**account, 'account_id': 'usr-fictional', 'evidence': {'url': 'https://example.org/post', 'quote': 'Hosted by Fictional Guild'}}
    harvest(db, 'city', [bare], now=SECOND)
    assert len(publisher_summaries(db)) == 2


def test_source_only_partnership_lead_never_creates_event(db):
    lead = {**LEAD, 'role': 'partner', 'relationship_status': 'partnership_only'}
    harvest(db, 'city', [lead], now=FIRST)
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
    [candidate] = publisher_summaries(db)
    assert candidate['event_ids'] == []
    assert candidate['relationships'][0]['relationship_status'] == 'partnership_only'
    assert candidate['status'] == 'candidate'


def test_relationship_role_and_changed_quote_are_preserved_as_evidence(db):
    harvest(db, 'city', [LEAD], now=FIRST)
    sponsor = {**LEAD, 'role': 'sponsor', 'evidence': {'url': URL, 'quote': 'Sponsored by Fictional Guild'}}
    correction = {**LEAD, 'evidence': {'url': URL, 'quote': 'Co-hosted by Fictional Guild and the Example Club'}}
    harvest(db, 'city', [sponsor, correction], now=SECOND)
    [candidate] = publisher_summaries(db)
    assert len(candidate['relationships']) == 3
    assert LEAD['evidence']['quote'] in {item['evidence']['quote'] for item in candidate['relationships']}


def test_invalid_or_unsupported_lead_never_creates_candidate(db):
    leads = [None, {}, {**LEAD, 'role': 'speaker'}, {**LEAD, 'evidence': {}},
             {**LEAD, 'evidence': {'url': 'javascript:invalid', 'quote': 'No source'}}]
    result = harvest(db, 'city', leads, now=FIRST)
    assert result['accepted'] == 0
    assert result['rejected'] == len(leads)
    assert publisher_summaries(db) == []


def test_conflicting_existing_accounts_require_review_and_do_not_merge(db):
    other = {**LEAD, 'url': 'https://luma.com/user/usr-second', 'account_id': 'luma:usr-second'}
    harvest(db, 'city', [LEAD, other], now=FIRST)
    conflicting = {**LEAD, 'account_id': other['account_id']}
    result = harvest(db, 'city', [conflicting], now=SECOND)
    assert result['accepted'] == 0
    assert result['rejections'][0]['reason'].startswith('Conflicting')
    assert len(publisher_summaries(db)) == 2


def test_successful_verified_index_monitor_links_existing_identity_without_creating_candidates(db):
    harvest(db, 'city', [LEAD], now=FIRST)
    monitored = {**SOURCE, 'id': 'guild-feed', 'url': 'https://guild.example/news/feed/',
                 'index_id': 'guild', 'index_status': 'active', 'enabled': True,
                 'publisher_identity_urls': [LEAD['url']]}
    unrelated = {**monitored, 'id': 'other-feed', 'index_id': 'other',
                 'publisher_identity_urls': ['https://other.example/']}
    register_sources(db, [monitored, unrelated])
    sync_configured_publishers(db, [monitored, unrelated])
    [candidate] = publisher_summaries(db)
    assert candidate['status'] == 'candidate'  # No successful source check yet.
    db.execute("UPDATE sources SET last_success=?,status='ok' WHERE id='guild-feed'", (SECOND,))
    links = sync_configured_publishers(db, [monitored, unrelated])
    assert len(links) == 1 and links[0]['active'] is True
    [candidate] = publisher_summaries(db)
    assert candidate['status'] == 'active'
    assert candidate['recurring_url'] == monitored['url']
    assert candidate['monitor_source_id'] == 'guild-feed'
    assert candidate['verified_at'] == SECOND
    assert candidate['first_seen'] == FIRST
    # A later temporary fetch failure does not erase the verified monitor link.
    db.execute("UPDATE sources SET status='error' WHERE id='guild-feed'")
    sync_configured_publishers(db, [monitored])
    assert publisher_summaries(db)[0]['status'] == 'active'
    sync_configured_publishers(db, [{**monitored, 'enabled': False}])
    assert publisher_summaries(db)[0]['status'] == 'candidate'
    assert publisher_summaries(db)[0]['verified_at'] == SECOND


def test_index_display_name_alone_never_links_candidate(db):
    harvest(db, 'city', [LEAD], now=FIRST)
    source = {**SOURCE, 'index_id': 'guild', 'index_status': 'active',
              'publisher_name': LEAD['name']}
    db.execute("UPDATE sources SET last_success=?,status='ok' WHERE id='city'", (SECOND,))
    assert sync_configured_publishers(db, [source]) == []
    assert publisher_summaries(db)[0]['status'] == 'candidate'


def test_candidate_writes_roll_back_with_event_transaction(db):
    db.commit()
    with pytest.raises(RuntimeError):
        with db:
            event_id = event(db)
            harvest(db, 'city', [LEAD], event_id=event_id, now=FIRST)
            raise RuntimeError('Source parsing failed')
    assert publisher_summaries(db) == []
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 0


def test_summaries_on_existing_database_are_read_only():
    db = connect(':memory:')
    before = list(db.execute('SELECT name FROM sqlite_master ORDER BY name'))
    assert publisher_summaries(db) == []
    assert list(db.execute('SELECT name FROM sqlite_master ORDER BY name')) == before
    db.close()


def test_normal_collection_harvests_event_and_partnership_leads_without_duplicates(db):
    announcement = extract('Nebula CTF 2031', 'A cybersecurity competition in Manila, Philippines.', URL, SOURCE)
    announcement['publisher_leads'] = [LEAD]
    partner = {**LEAD, 'name': 'Other Partner', 'role': 'community_partner',
               'url': 'https://other.example/', 'account_id': 'example:other',
               'relationship_status': 'partnership_only',
               'evidence': {'url': 'https://calendar.example/partners', 'quote': 'Community partner: Other Partner'}}

    def adapter(*args):
        result = Result()
        result.announcements = [announcement]
        result.publisher_leads = [partner]
        return result

    first = collect(db, [SOURCE], adapters={'rss': adapter}, now=datetime(2031, 1, 1, tzinfo=timezone.utc))
    second = collect(db, [SOURCE], adapters={'rss': adapter}, now=datetime(2031, 1, 2, tzinfo=timezone.utc))
    assert first['events'] == second['events'] == 1
    assert first['announcements'] == second['announcements'] == 1
    assert len(first['publisher_candidates']) == len(second['publisher_candidates']) == 2
    assert first['sources'][0]['publisher_candidates']['new_candidates'] == 2
    assert second['sources'][0]['publisher_candidates']['new_candidates'] == 0
    assert second['sources'][0]['publisher_candidates']['new_relationships'] == 0
    assert {row['first_seen'] for row in second['publisher_candidates']} == {FIRST}
    only_partner = next(row for row in second['publisher_candidates'] if row['name'] == 'Other Partner')
    assert only_partner['event_ids'] == []
    assert only_partner['roles'] == ['community-partner']
