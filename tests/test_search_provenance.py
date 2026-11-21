"""Offline search provenance regressions; all event names and IDs are fictional."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.app import create_app
from backend.db import connect, events, ingest, register_sources
from backend.extract import extract


NOW = datetime(2031, 2, 10, tzinfo=timezone.utc)
SOURCE = {'id': 'official', 'name': 'Fictional university feed', 'kind': 'rss',
          'url': 'https://kestrel.example/feed/', 'organizer': 'Kestrel University',
          'organizer_key': 'kestrel-university'}
SOURCES = [SOURCE, {**SOURCE, 'id': 'search', 'name': 'Generic search'},
           {**SOURCE, 'id': 'unverified', 'name': 'Unverified publisher'},
           {**SOURCE, 'id': 'ctftime', 'name': 'CTFtime'}]
QUERY = 'Philippines cybersecurity CTF competition'


@pytest.fixture
def db():
    connection = connect(':memory:')
    register_sources(connection, SOURCES)
    yield connection
    connection.close()


def announcement(url='https://kestrel.example/news/nebula', *, access='full', posted='2031-02-02T03:00:00Z'):
    return extract('Nebula CTF 2031',
                   'Competition dates: April 12–15, 2031\nEligibility: Kestrel University students',
                   url, SOURCE, posted_at=posted, access=access)


@pytest.mark.parametrize('source_id,access,official,label', [
    ('search', 'search_only', True, 'Search result · verify source'),
    ('unverified', 'full', False, 'Announcement · verify source'),
    ('official', 'full', None, 'Official announcement'),
    ('ctftime', 'full', None, 'CTFtime listing'),
])
def test_primary_link_labels_match_source_authority(db, source_id, access, official, label):
    ann = announcement(access=access)
    if official is not None:
        ann['official'] = official
    ingest(db, source_id, ann, '2031-02-03T00:00:00Z')
    assert events(db, NOW)[0]['announcement_label'] == label


def test_full_official_source_is_primary_even_after_earlier_search_and_unverified_article(db):
    search = announcement('https://facebook.com/kestrel/posts/707070', access='search_only', posted='2031-02-01T00:00:00Z')
    unverified = announcement('https://news.example/nebula', posted='2031-02-02T00:00:00Z')
    unverified['official'] = False
    official = announcement(posted='2031-02-03T00:00:00Z')
    for source_id, ann in [('search', search), ('unverified', unverified), ('official', official)]:
        ingest(db, source_id, ann, '2031-02-04T00:00:00Z')
    event = events(db, NOW)[0]
    assert len(event['announcements']) == 3
    assert event['announcement_url'] == official['url']
    assert event['announcement_label'] == 'Official announcement'
    assert event['posted_at'] == official['posted_at']


@pytest.mark.parametrize('search_posted', ['2031-02-01T00:00:00Z', '2031-02-03T00:00:00Z'])
def test_search_cannot_supply_or_overwrite_full_facts_regardless_of_order(db, search_posted):
    full = announcement()
    search = announcement('https://facebook.com/kestrel/posts/707070', access='search_only', posted=search_posted)
    # Intentionally malformed search input tests the reconciliation boundary,
    # independently of the adapter's own title-only extraction restriction.
    search['facts'].update(name='Unsupported search name', organizer='Organizer unconfirmed',
                           eligibility='Anyone', deadline={'raw': 'Tomorrow'},
                           lifecycle='cancelled', registration_state='open')
    search['field_evidence']['eligibility'] = {'url': search['url'], 'quote': 'Anyone'}
    ingest(db, 'search', search, '2031-02-04T00:00:00Z')
    ingest(db, 'official', full, '2031-02-04T00:00:00Z')
    event = events(db, NOW)[0]
    assert event['name'] == 'Nebula CTF 2031'
    assert event['organizer'] == 'Kestrel University'
    assert event['eligibility'] == 'Kestrel University students'
    assert event['field_evidence']['eligibility']['url'] == full['url']
    assert event['deadline'] is None
    assert event['registration_status'] == 'unknown'
    assert event['status'] == 'scheduled'


def test_same_url_search_preserves_full_record_and_does_not_reorder_older_facts(db):
    full = announcement()
    ingest(db, 'official', full, '2031-02-02T04:00:00Z')
    before = dict(db.execute('SELECT * FROM announcements').fetchone())
    correction = announcement(full['url'] + '/correction', posted='2031-02-03T03:00:00Z')
    correction['facts']['start'] = {'raw': 'April 19, 2031', 'value': '2031-04-19', 'precision': 'date', 'timezone': None}
    ingest(db, 'official', correction, '2031-02-03T04:00:00Z')
    search = announcement(full['url'], access='search_only')
    search['discovery_query'] = QUERY
    for _ in range(2):
        key, created = ingest(db, 'search', search, '2031-02-05T04:00:00Z')
        assert not created
    after = dict(db.execute('SELECT * FROM announcements WHERE id=?', (before['id'],)).fetchone())
    for field in ('source_id', 'first_seen', 'last_seen', 'changed_at', 'revision_count'):
        assert after[field] == before[field]
    event = events(db, NOW)[0]
    assert event['start']['value'] == '2031-04-19'
    saved = next(ann for ann in event['announcements'] if ann['url'] == full['url'])
    assert saved['access'] == 'full'
    assert saved['source_name'] == SOURCE['name']
    assert saved['discovery_queries'] == [QUERY]
    assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 2


def test_full_fetch_upgrades_search_attribution_and_keeps_query_trace(db):
    search = announcement(access='search_only')
    search['discovery_query'] = QUERY
    search['official'] = False
    ingest(db, 'search', search, '2031-02-02T04:00:00Z')
    ingest(db, 'official', announcement(), '2031-02-03T04:00:00Z')
    event = events(db, NOW)[0]
    assert event['announcement_label'] == 'Official announcement'
    assert event['announcements'][0]['source_name'] == SOURCE['name']
    assert event['announcements'][0]['access'] == 'full'
    assert event['announcements'][0]['discovery_queries'] == [QUERY]


def test_api_exposes_single_and_multiple_search_queries_without_duplicates(tmp_path):
    path = str(tmp_path / 'search.sqlite3')
    db = connect(path)
    register_sources(db, SOURCES)
    ann = announcement(access='search_only')
    ann['discovery_query'] = QUERY
    ann['discovery_queries'] = [QUERY, 'site:facebook.com Philippines CTF registration']
    ann['discovery_path'] = ['https://search.example/', ann['url']]
    ingest(db, 'search', ann, '2031-02-03T04:00:00Z')
    db.commit()
    db.close()
    result = create_app(path).test_client().get('/api/events').json['events'][0]['announcements'][0]
    assert result['discovery_query'] == QUERY
    assert result['discovery_queries'] == ann['discovery_queries']
    assert result['discovery_path'] == ann['discovery_path']


def test_equivalent_numeric_facebook_links_keep_one_event_and_announcement(db):
    first = announcement('https://facebook.com/story.php?id=808080&story_fbid=707070', access='search_only')
    first['external_id'] = 'facebook:post:707070'
    first['discovery_query'] = QUERY
    key, created = ingest(db, 'search', first, '2031-02-03T04:00:00Z')
    assert created
    alternate = deepcopy(first)
    alternate['url'] = 'https://facebook.com/kestrel/posts/707070'
    alternate['identity']['series'] = 'Nebula Capture the Flag'
    alternate['discovery_query'] = 'site:facebook.com Philippines CTF registration'
    for _ in range(2):
        next_key, created = ingest(db, 'search', alternate, '2031-02-04T04:00:00Z')
        assert next_key == key and not created
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
    assert db.execute('SELECT count(*) FROM announcements').fetchone()[0] == 1
    event = events(db, NOW)[0]
    assert event['announcement_url'] == first['url']
    assert event['series'] == first['identity']['series']
    assert event['announcements'][0]['discovery_queries'] == [QUERY, alternate['discovery_query']]


def test_numeric_search_link_cannot_replace_matching_full_record_with_another_title(db):
    full = announcement('https://facebook.com/kestrel/posts/707070')
    full['external_id'] = 'facebook:post:707070'
    ingest(db, 'official', full, '2031-02-03T04:00:00Z')
    search = announcement('https://facebook.com/story.php?id=808080&story_fbid=707070', access='search_only')
    search['external_id'] = full['external_id']
    search['identity']['series'] = 'Nebula Capture the Flag'
    search['facts']['name'] = 'Nebula Capture the Flag 2031'
    ingest(db, 'search', search, '2031-02-04T04:00:00Z')
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
    event = events(db, NOW)[0]
    assert event['name'] == full['facts']['name']
    assert event['announcement_url'] == full['url']
    assert event['announcements'][0]['access'] == 'full'


def test_opaque_facebook_tokens_do_not_imply_numeric_post_equivalence(db):
    first = announcement('https://facebook.com/kestrel/posts/pfbidOpaqueA', access='search_only')
    first['external_id'] = 'facebook:opaque:kestrel:pfbidOpaqueA'
    second = deepcopy(first)
    second['url'] = 'https://facebook.com/kestrel/posts/pfbidOpaqueB'
    second['external_id'] = 'facebook:opaque:kestrel:pfbidOpaqueB'
    ingest(db, 'search', first, '2031-02-03T04:00:00Z')
    ingest(db, 'search', second, '2031-02-03T04:00:00Z')
    assert len(events(db, NOW)[0]['announcements']) == 2


def test_reused_numeric_facebook_post_keeps_explicit_years_separate_and_deduplicates_each(db):
    first = announcement('https://facebook.com/kestrel/posts/707070', access='search_only')
    first['external_id'] = 'facebook:post:707070'
    following_year = deepcopy(first)
    following_year['identity']['edition'] = '2032'
    following_year['title'] = following_year['facts']['name'] = 'Nebula CTF 2032'
    keys = []
    for index, ann in enumerate((first, following_year)):
        key, created = ingest(db, 'search', ann, f'2031-02-0{index + 3}T04:00:00Z')
        assert created
        keys.append(key)
    assert keys[0] != keys[1]
    # A different permalink/title shape for each year must select the matching
    # edition, not simply the oldest row with this reused Facebook post ID.
    for expected_key, ann in zip(keys, (first, following_year)):
        alternate = deepcopy(ann)
        alternate['url'] = 'https://facebook.com/story.php?id=808080&story_fbid=707070'
        alternate['identity']['series'] = 'Nebula Capture the Flag'
        key, created = ingest(db, 'search', alternate, '2032-02-04T04:00:00Z')
        assert key == expected_key and not created
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 2
    assert db.execute('SELECT count(*) FROM announcements').fetchone()[0] == 2
    assert {event['edition'] for event in events(db, NOW)} == {'2031', '2032'}


@pytest.mark.parametrize('first_scope,second_scope', [
    ({'stage': 'qualifier'}, {'stage': 'regional-final'}),
    ({'stage': 'qualifier'}, {'stage': 'national-final'}),
    ({'stage': 'regional-final'}, {'stage': 'national-final'}),
    ({'region': 'Region VI — Western Visayas'}, {'region': 'Region VII — Central Visayas'}),
])
def test_reused_numeric_post_does_not_merge_explicit_round_or_region_boundaries(db, first_scope, second_scope):
    first = announcement('https://facebook.com/kestrel/posts/707070', access='search_only')
    first['external_id'] = 'facebook:post:707070'
    second = deepcopy(first)
    first['identity'].update(first_scope)
    second['identity'].update(second_scope)
    first_key, _ = ingest(db, 'search', first, '2031-02-03T04:00:00Z')
    second_key, created = ingest(db, 'search', second, '2031-02-04T04:00:00Z')
    assert first_key != second_key and created
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 2
    assert db.execute('SELECT count(*) FROM announcements').fetchone()[0] == 2
