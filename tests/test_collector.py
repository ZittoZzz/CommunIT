import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.adapters import Result, bluesky, brave, ctftime, CredentialsRequired
from backend.app import create_app
from backend.collect import collect
from backend.db import connect, events, ingest, register_sources, source_states
from backend.domain import canonical_url, lifecycle, parse_moment
from backend.extract import extract
from backend.network import FetchError

SOURCE = {'id': 'fixture', 'name': 'Fixture organizer (not live)', 'url': 'https://organizer.example/',
          'kind': 'rss', 'organizer': 'DICT Region VII', 'organizer_key': 'dict'}
NOW = datetime(2027, 1, 20, tzinfo=timezone.utc)
FIXTURES = json.loads((Path(__file__).parent / 'fixtures/announcements.json').read_text())


@pytest.fixture
def db():
    connection = connect(':memory:')
    register_sources(connection, [SOURCE])
    yield connection
    connection.close()


def announcement(i):
    data = FIXTURES[i]
    return extract(data['title'], data['text'], data['url'], SOURCE, posted_at=data['posted_at'])


def test_teaser_becomes_one_dated_event_with_registration_and_history(db):
    ingest(db, 'fixture', announcement(0), '2027-01-02T00:00:00+00:00')
    assert events(db, NOW)[0]['status'] == 'schedule_tba'
    ingest(db, 'fixture', announcement(1), '2027-01-06T00:00:00+00:00')
    records = events(db, NOW)
    assert len(records) == 1
    event = records[0]
    assert len(event['announcements']) == 2
    assert event['announcement_url'].endswith('/teaser')
    assert event['start']['value'] == '2027-02-20T09:00:00+08:00'
    assert event['deadline']['value'] == '2027-02-10'
    assert event['deadline']['precision'] == 'date'
    assert event['registration_status'] == 'open'
    assert event['registration_url'] == 'https://organizer.example/register'
    assert event['posted_at'] == FIXTURES[0]['posted_at']
    assert event['first_seen'] == '2027-01-02T00:00:00+00:00'


def test_repeat_collection_is_idempotent_and_preserves_first_seen(db):
    def adapter(*args):
        result = Result()
        result.announcements = [announcement(0), announcement(1)]
        result.discovered = 2
        return result
    one = collect(db, [SOURCE], adapters={'rss': adapter}, now=NOW)
    first_seen = events(db, NOW)[0]['first_seen']
    two = collect(db, [SOURCE], adapters={'rss': adapter}, now=datetime(2027, 1, 21, tzinfo=timezone.utc))
    assert (one['events'], two['events'], two['announcements']) == (1, 1, 2)
    assert two['sources'][0]['new_announcements'] == 0
    assert events(db, NOW)[0]['first_seen'] == first_seen
    assert db.execute('select count(*) from revisions').fetchone()[0] == 2


def test_regions_editions_and_stages_do_not_merge_even_same_url(db):
    for i in range(4):
        ingest(db, 'fixture', announcement(i))
    assert len(events(db, NOW)) == 3  # teaser + registration merged; two finals separate
    newer = announcement(1)
    newer['identity'] = {**newer['identity'], 'edition': '2028'}
    ingest(db, 'fixture', newer)
    other = announcement(1)
    other['identity'] = {**other['identity'], 'region': 'Region VIII — Eastern Visayas'}
    ingest(db, 'fixture', other)
    assert len(events(db, NOW)) == 5


def test_postponement_clears_current_schedule_and_old_late_fetch_cannot_restore_it(db):
    ingest(db, 'fixture', announcement(1), '2027-01-06T00:00:00+00:00')
    ingest(db, 'fixture', announcement(4), '2027-01-11T00:00:00+00:00')
    ingest(db, 'fixture', announcement(0), '2027-01-19T00:00:00+00:00')
    event = events(db, NOW)[0]
    assert event['status'] == 'postponed'
    assert event['start'] is None and event['end'] is None
    assert event['registration_status'] == 'unknown'
    assert db.execute('select count(*) from revisions').fetchone()[0] == 3


def test_edited_announcement_replaces_facts_and_has_revision(db):
    data = announcement(1)
    ingest(db, 'fixture', data, '2027-01-06T00:00:00+00:00')
    data['facts']['start'] = parse_moment('February 25, 2027 at 09:00 PHT')
    ingest(db, 'fixture', data, '2027-01-07T00:00:00+00:00')
    event = events(db, NOW)[0]
    assert event['start']['value'].startswith('2027-02-25')
    assert event['announcements'][0]['revision_count'] == 2
    assert db.execute('select count(*) from revisions').fetchone()[0] == 2


def test_failed_fetch_preserves_data_last_success_and_other_source_runs(db):
    def good(*args):
        result = Result()
        result.announcements = [announcement(1)]
        return result
    collect(db, [SOURCE], adapters={'rss': good}, now=NOW)
    before = source_states(db)[0]['last_success']
    def fail(*args):
        raise FetchError('HTTP 403')
    second = {**SOURCE, 'id': 'second', 'kind': 'html'}
    report = collect(db, [SOURCE, second], adapters={'rss': fail, 'html': good}, now=datetime(2027, 1, 21, tzinfo=timezone.utc))
    assert [x['status'] for x in report['sources']] == ['error', 'ok']
    assert len(events(db, NOW)) == 1
    assert source_states(db)[0]['last_success'] == before


@pytest.mark.parametrize('raw,precision', [
    ('November 21, 2026', 'date'), ('2026-11-21', 'date'),
    ('November 21', 'text'), ('11/12/26', 'text'),
    ('November 21, 2026 at 09:00', 'text'), ('November 21, 2026 at 09:00 PST', 'text')])
def test_ambiguous_dates_never_become_midnight_instants(raw, precision):
    value = parse_moment(raw)
    assert value['precision'] == precision
    assert value['raw'] == raw
    assert value['timezone'] is None
    assert 'T00:00' not in (value['value'] or '')


def test_datetime_has_explicit_timezone():
    value = parse_moment('2026-11-21T01:00:00Z')
    assert value['value'] == '2026-11-21T01:00:00+00:00'
    assert value['precision'] == 'datetime'


def test_registration_and_completion_are_independent():
    now = datetime(2027, 2, 21, tzinfo=timezone.utc)
    base = {'start': parse_moment('2027-02-20T01:00:00Z'), 'registration_state': 'closed'}
    assert lifecycle(base, now) == ('end_unconfirmed', 'closed', 'upcoming')
    assert lifecycle({**base, 'end': parse_moment('2027-02-20')}, now)[0] != 'finished'
    assert lifecycle({**base, 'end': parse_moment('2027-02-20T09:00:00Z')}, now)[0] == 'finished'
    assert lifecycle({'lifecycle': 'finished'}, now)[2] == 'finished'
    assert lifecycle({'lifecycle': 'cancelled', 'registration_state': 'open'}, now) == ('cancelled', 'closed', 'upcoming')
    assert lifecycle({'deadline': parse_moment('2027-02-10')}, now)[1] == 'unknown'
    assert lifecycle({'registration_opens': parse_moment('2027-03-01T00:00:00Z')}, now)[1] == 'not_yet_open'


def test_search_only_does_not_claim_details_from_snippet():
    data = FIXTURES[1]
    ann = extract(data['title'], data['text'], 'https://facebook.com/cyberdictr3/posts/123', SOURCE, access='search_only')
    assert ann['facts']['start'] is None
    assert ann['facts']['registration_state'] is None
    assert ann['facts']['eligibility'] is None
    assert ann['posted_at'] is None
    assert ann['evidence'] is None


def test_url_dedup_preserves_facebook_identifiers():
    assert canonical_url('https://example.com/post?utm_campaign=x#top') == 'https://example.com/post'
    assert canonical_url('https://facebook.com/story.php?story_fbid=1&id=2') != canonical_url('https://facebook.com/story.php?story_fbid=3&id=2')
    assert canonical_url('javascript:alert(1)') is None


def test_generic_conference_talk_is_not_a_ctf():
    assert extract('Conference 2027', 'Talks on cybersecurity and AI.', 'https://x.example', SOURCE) is None
    assert extract('It can solve CTFs', 'It can solve CTFs. It can write code.', 'https://x.example', SOURCE) is None


def test_optional_search_needs_key_and_storage_rights(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    with pytest.raises(CredentialsRequired):
        brave({}, None, [], NOW)
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY', 'test-only-token')
    monkeypatch.delenv('BRAVE_STORAGE_RIGHTS', raising=False)
    with pytest.raises(CredentialsRequired):
        brave({}, None, [], NOW)


def test_social_deletion_is_distinct_from_fetch_failure(db):
    data = announcement(1)
    data['external_id'] = 'at://did:plc:example/app.bsky.feed.post/abc'
    ingest(db, 'fixture', data)
    class Client:
        def read(self, url, **kwargs):
            return json.dumps({'feed': []} if url.endswith('getAuthorFeed') else {'posts': []})
    config = {**SOURCE, 'kind': 'bluesky', 'actor': 'fixture.example', 'max_pages': 1}
    collect(db, [config], client=Client(), now=NOW)
    assert events(db, NOW) == []
    assert db.execute('select count(*) from revisions').fetchone()[0] == 0


def test_ctftime_requires_real_philippine_connection():
    foreign = {'id': 1, 'title': 'World CTF 2027', 'description': 'Open to everyone including Filipino participants.',
               'location': '', 'onsite': False, 'organizers': [{'id': 2, 'name': 'Foreign Club'}]}
    local = {**foreign, 'id': 2, 'title': 'Campus CTF 2027', 'organizers': [{'id': 3, 'name': 'Philippine Club'}],
             'ctftime_url': 'https://ctftime.org/event/2/', 'start': '2027-01-21T01:00:00Z', 'finish': '2027-01-21T09:00:00Z', 'restrictions': 'Academic'}
    class Client:
        def read(self, *args, **kwargs): return json.dumps([foreign, local])
    result = ctftime({'url': 'https://ctftime.org/api/v1/events/', 'lookback_days': 1, 'future_days': 1,
                      'organizer_names': ['Philippine Club']}, Client(), [], NOW)
    assert len(result.announcements) == 1
    assert result.announcements[0]['facts']['name'] == 'Campus CTF 2027'


def test_api_serves_real_database_not_samples(tmp_path):
    file = str(tmp_path / 'test.sqlite')
    app = create_app(file)
    client = app.test_client()
    response = client.get('/api/events')
    assert response.status_code == 200
    assert response.json['events'] == []
    assert response.json['timezone'] == 'Asia/Manila'
    assert client.post('/api/events', json={'name': 'fake'}).status_code == 405
    assert client.get('/api/health').json['status'] == 'ok'


def test_announcement_order_compares_instants_across_timezones(db):
    newer = announcement(1)
    newer['posted_at'] = '2027-01-09T23:00:00-05:00'  # Jan 10, 04:00 UTC
    older = announcement(4)
    older['posted_at'] = '2027-01-10T02:00:00Z'
    newer['facts']['lifecycle'] = 'scheduled'  # explicit reschedule
    ingest(db, 'fixture', newer, '2027-01-11T01:00:00Z')
    ingest(db, 'fixture', older, '2027-01-11T01:00:00Z')
    event = events(db, NOW)[0]
    assert event['status'] == 'scheduled'
    assert event['start'] is not None


def test_campus_and_invite_only_are_not_excluded():
    for restriction in ('Campus-only', 'Invite-only'):
        ann = extract('Campus CTF 2027', f'Capture the Flag competition. {restriction}.', 'https://organizer.example/ctf', SOURCE)
        assert ann is not None and ann['facts']['eligibility']


def test_hypothetical_cancellation_and_future_champions_do_not_change_lifecycle():
    ann = extract('Campus CTF 2027', 'Capture the Flag competition. If the event is cancelled, refunds apply. The CTF champions will receive prizes.', 'https://organizer.example/ctf', SOURCE)
    assert ann['facts']['lifecycle'] is None
    ann = extract('Campus CTF 2027 cancelled', 'The competition is cancelled.', 'https://organizer.example/ctf', SOURCE)
    assert ann['facts']['lifecycle'] == 'cancelled'


def test_completion_requires_organizer_evidence():
    ann = extract('ROOTCON 20 CTF Champions', 'Congratulations to the winning team on taking the CTF crown!', 'https://organizer.example/ctf', SOURCE)
    assert ann['facts']['lifecycle'] == 'finished'
