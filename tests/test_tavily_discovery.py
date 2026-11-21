"""Offline keyless discovery regressions. Names, dates, and post IDs are fictional."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.collect import collect
from backend.db import connect, events
from backend.network import FetchError, RateLimited
from backend.tavily import ENDPOINT, post_identity, search_announcement, search_queries, tavily


NOW = datetime(2031, 2, 10, tzinfo=timezone.utc)
SOURCE = {
    'id': 'free-search', 'name': 'Free public search', 'kind': 'tavily', 'url': ENDPOINT,
    'queries': [
        {'query': 'Philippines cybersecurity CTF registration', 'include_domains': ['facebook.com']},
        {'query': 'Philippines capture the flag competition announcements'},
    ],
    'max_results': 20,
    'organizers': [{
        'organizer': 'Kestrel University', 'organizer_key': 'kestrel-university',
        'facebook_accounts': ['kestrel-university', '808080'],
        'event_pattern': r'\bAurora\s+CTF\b',
        'evidence_url': 'https://kestrel.edu.ph/about/',
        'philippine_connection': 'Fictional Philippine university for offline tests.',
    }],
}
SNIPPET = ('Philippines. Registration open. Competition dates: April 12–15, 2031\n'
           'Eligibility: Everyone\nFormat: online\n'
           'Registration link: https://signup.example/aurora\n'
           'Related reels: Philippine Aurora CTF 2031 has concluded.')


def hit(title='Aurora CTF 2031', url='https://facebook.com/kestrel-university/posts/707070', **kwargs):
    return {'title': title, 'url': url, 'content': SNIPPET, **kwargs}


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, url, payload, *, headers=None):
        self.calls.append((url, deepcopy(payload), deepcopy(headers)))
        assert self.responses, 'Unexpected extra API call'
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def db():
    connection = connect(':memory:')
    yield connection
    connection.close()


@pytest.mark.parametrize('title,url', [
    ('Aurora CTF 2031', 'https://facebook.com/unknown-organizer/posts/707070'),
    ('International CTF 2031 open to participants from the Philippines', 'https://world.example/event/'),
    ('Japan University hosts Aurora CTF 2031, open to participants from the Philippines',
     'https://foreign.example/ctf/'),
    ('Philippines team wins Aurora CTF 2031 in Japan', 'https://news.example/article/'),
    ('Kestrel University students win Aurora CTF 2031 in Japan',
     'https://facebook.com/kestrel-university/posts/707070'),
    ('Tokyo CTF 2031 hosted by Japan University',
     'https://facebook.com/kestrel-university/posts/707070'),
    ('Japan University hosts Tokyo CTF 2031', 'https://kestrel.edu.ph/news/tokyo/'),
    ('University students win Aurora CTF 2031 abroad', 'https://kestrel.edu.ph/news/winners/'),
    ('Community programming tutorial', 'https://facebook.com/kestrel-university/posts/707070'),
    ('Philippine CTF writeup 2031', 'https://facebook.com/unknown-organizer/posts/707070'),
])
def test_query_and_related_snippet_cannot_establish_local_competition(title, url):
    client = FakeClient({'results': [hit(title, url)]}, {'results': []})
    result = tavily(SOURCE, client, [], NOW)
    assert result.discovered == 1 and not result.failed
    assert result.announcements == []
    # Rejected URLs remain reviewable before organizer filtering.
    assert result.searches[0]['results'] == [{'url': url, 'title': title}]
    assert result.decisions[0]['accepted'] is False


@pytest.mark.parametrize('title,url', [
    ('Philippine CTF 2031', 'https://facebook.com/new-organizer/posts/707070'),
    ('Aurora CTF 2031', 'https://facebook.com/kestrel-university/posts/707070'),
    ('Aurora CTF 2031', 'https://facebook.com/story.php?id=808080&story_fbid=707070'),
    ('Kestrel University hosts Nebula CTF 2031', 'https://facebook.com/kestrel-university/posts/707070'),
    ('Nebula CTF 2031 organized by Kestrel University', 'https://facebook.com/kestrel-university/posts/707070'),
    ('HackForGov 2031 regional final', 'https://facebook.com/unknown-office/posts/707070'),
    ('Philippine university hosts Aurora CTF 2031', 'https://kestrel.edu.ph/news/aurora/'),
])
def test_supported_title_or_known_publisher_yields_only_search_evidence(title, url):
    announcement, reason = search_announcement(hit(title, url), SOURCE)
    assert announcement is not None, reason
    assert announcement['access'] == 'search_only'
    assert announcement['official'] is False
    assert announcement['posted_at'] is None
    assert announcement['evidence'] is None
    assert announcement['kind'] == 'announcement'
    for field in ('start', 'end', 'deadline', 'registration_opens', 'registration_url',
                  'eligibility', 'registration_state', 'lifecycle', 'summary'):
        assert announcement['facts'][field] is None
        assert field not in announcement['field_evidence']
    assert announcement['facts']['format'] == 'unknown'
    assert SNIPPET not in json.dumps(announcement)
    assert announcement['field_evidence']['name']['quote'] == title
    assert 'philippine_connection' in announcement['field_evidence']


def test_known_publisher_does_not_become_organizer_of_independent_philippine_program():
    announcement, reason = search_announcement(hit('HackForGov 2031 regional final'), SOURCE)
    assert announcement is not None, reason
    assert announcement['facts']['organizer'] == 'Organizer unconfirmed'
    assert 'organizer' not in announcement['field_evidence']
    assert announcement['field_evidence']['philippine_connection']['quote'] == 'HackForGov 2031 regional final'


@pytest.mark.parametrize('title', ['Philippine CTF', 'HackForGov', 'Aurora CTF registration open'])
def test_snippet_year_does_not_supply_a_missing_edition(title):
    announcement, reason = search_announcement(hit(title), SOURCE)
    assert announcement is None
    assert 'edition' in reason


@pytest.mark.parametrize('url', ['https://facebook.com/kestrel-university/',
                                 'https://facebook.com/reel/707070',
                                 'https://facebook.com/search/top?q=CTF'])
def test_facebook_pages_and_unidentifiable_reels_are_not_announcements(url):
    announcement, _ = search_announcement(hit('Philippine CTF 2031', url), SOURCE)
    assert announcement is None


def test_keyless_queries_do_not_use_credentials_and_audit_all_urls_before_filtering(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'unused-private-key')
    monkeypatch.setenv('BRAVE_STORAGE_RIGHTS', 'unchanged-value')
    local = hit()
    unrelated = hit('Foreign university CTF 2031', 'https://foreign.example/ctf/')
    client = FakeClient({'results': [unrelated, local], 'query': 'provider echo'}, {'results': []})
    result = tavily(SOURCE, client, [], NOW)
    assert result.discovered == 2 and len(result.announcements) == 1
    assert [record['url'] for record in result.searches[0]['results']] == [unrelated['url'], local['url']]
    assert result.searches[1]['status'] == 'ok' and result.searches[1]['results'] == []
    assert 'content' not in json.dumps(result.searches)
    assert 'unused-private-key' not in json.dumps(client.calls)
    assert len(client.calls) == 2
    for url, payload, headers in client.calls:
        assert url == ENDPOINT
        assert headers == {'X-Tavily-Access-Mode': 'keyless'}
        assert payload['search_depth'] == 'basic'
        assert payload['include_answer'] is False
        assert payload['include_raw_content'] is False
        assert payload['include_images'] is False
        assert 'api_key' not in payload
    assert client.calls[0][1]['include_domains'] == ['facebook.com']
    assert client.calls[0][1]['include_domains_mode'] == 'restrict'
    assert 'include_domains' not in client.calls[1][1]
    import os
    assert os.environ['BRAVE_STORAGE_RIGHTS'] == 'unchanged-value'


def test_one_bounded_retry_honors_short_server_delay(monkeypatch):
    sleeps = []
    monkeypatch.setattr('backend.tavily.time.sleep', sleeps.append)
    client = FakeClient(RateLimited(3), {'results': [hit()]}, {'results': []})
    result = tavily(SOURCE, client, [], NOW)
    assert sleeps == [3] and len(client.calls) == 3
    assert client.calls[0] == client.calls[1]
    assert result.searches[0]['status'] == 'ok'
    assert [attempt['status'] for attempt in result.searches[0]['attempts']] == ['rate_limited', 'ok']
    assert not result.failed and not result.warnings


@pytest.mark.parametrize('delay', [None, 31, -1])
def test_unknown_long_or_negative_delay_is_not_retried_or_bypassed_by_second_query(monkeypatch, delay):
    sleeps = []
    monkeypatch.setattr('backend.tavily.time.sleep', sleeps.append)
    client = FakeClient(RateLimited(delay), {'results': []})
    result = tavily(SOURCE, client, [], NOW)
    assert sleeps == [] and len(client.calls) == 1
    assert result.searches[0]['status'] == 'error'
    assert result.searches[1]['status'] == 'skipped'
    assert result.searches[1]['attempts'] == []
    assert result.warnings and result.failed


def test_repeated_rate_limit_stops_after_one_retry_and_skips_later_query(monkeypatch):
    sleeps = []
    monkeypatch.setattr('backend.tavily.time.sleep', sleeps.append)
    client = FakeClient(RateLimited(0), RateLimited(0), {'results': [hit()]})
    result = tavily(SOURCE, client, [], NOW)
    assert sleeps == [0] and len(client.calls) == 2
    assert result.searches[0]['status'] == 'error'
    assert len(result.searches[0]['attempts']) == 2
    assert result.searches[1]['status'] == 'skipped'
    assert result.searches[1]['attempts'] == []
    assert result.announcements == [] and result.failed


def test_bad_response_is_an_error_but_successful_zero_results_are_not():
    client = FakeClient({'results': 'not a list'}, {'results': []})
    result = tavily(SOURCE, client, [], NOW)
    assert result.searches[0]['status'] == 'error'
    assert result.searches[1]['status'] == 'ok'
    assert result.discovered == 0 and not result.failed and result.warnings


def test_queries_only_use_official_endpoint():
    client = FakeClient()
    with pytest.raises(FetchError, match='official Tavily'):
        search_queries({**SOURCE, 'url': 'https://proxy.example/search'}, client)
    assert client.calls == []


def test_normal_collect_twice_keeps_equivalent_numeric_post_and_query_trace_once(db):
    first = hit()
    equivalent = hit(url='https://facebook.com/story.php?id=808080&story_fbid=707070')
    results = []
    for index in range(2):
        client = FakeClient({'results': [first]}, {'results': [equivalent]})
        results.append(collect(db, [SOURCE], client=client, now=NOW + timedelta(days=index)))
    assert results[0]['events'] == results[1]['events'] == 1
    assert results[0]['announcements'] == results[1]['announcements'] == 1
    assert results[1]['sources'][0]['new_announcements'] == 0
    event = events(db, NOW)[0]
    assert event['status'] == 'schedule_tba'
    assert event['registration_status'] == 'unknown'
    assert event['announcement_label'] == 'Search result · verify source'
    assert event['first_seen'] == NOW.isoformat()
    assert event['announcements'][0]['discovery_queries'] == sorted(q['query'] for q in SOURCE['queries'])
    assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 1
    assert db.execute('SELECT revision_count FROM announcements').fetchone()[0] == 1
    assert db.execute('SELECT external_id FROM announcements').fetchone()[0] == 'facebook:post:707070'


def test_partial_and_failed_queries_preserve_previous_records_and_last_success(db):
    first = collect(db, [SOURCE], client=FakeClient({'results': [hit()]}, {'results': []}), now=NOW)
    assert first['sources'][0]['status'] == 'ok'
    snapshot = dict(db.execute('SELECT * FROM announcements').fetchone())
    for offset, responses, status in [
        (1, [FetchError('HTTP 503'), {'results': []}], 'partial'),
        (2, [FetchError('HTTP 502'), FetchError('HTTP 503')], 'error'),
    ]:
        report = collect(db, [SOURCE], client=FakeClient(*responses), now=NOW + timedelta(days=offset))
        assert report['sources'][0]['status'] == status
        assert report['events'] == report['announcements'] == 1
        assert report['sources'][0]['new_announcements'] == 0
        assert dict(db.execute('SELECT * FROM announcements').fetchone()) == snapshot
        source = db.execute('SELECT * FROM sources').fetchone()
        assert source['last_success'] == NOW.isoformat()
        assert source['last_attempt'] == (NOW + timedelta(days=offset)).isoformat()
    # Empty successful searches are observations, not deletions or failures.
    later = NOW + timedelta(days=3)
    report = collect(db, [SOURCE], client=FakeClient({'results': []}, {'results': []}), now=later)
    assert report['sources'][0]['status'] == 'ok'
    assert report['events'] == report['announcements'] == 1
    assert db.execute('SELECT last_success FROM sources').fetchone()[0] == later.isoformat()


def test_non_rate_limit_failure_does_not_discard_other_query_discoveries(db):
    client = FakeClient(FetchError('HTTP 503'), {'results': [hit()]})
    report = collect(db, [SOURCE], client=client, now=NOW)
    source = report['sources'][0]
    assert source['status'] == 'partial'
    assert report['events'] == report['announcements'] == 1
    assert source['accepted'] == source['new_announcements'] == 1
    assert [query['status'] for query in source['searches']] == ['error', 'ok']
    assert db.execute('SELECT last_success FROM sources').fetchone()[0] is None
    assert events(db, NOW)[0]['announcements'][0]['access'] == 'search_only'


def test_opaque_permalink_does_not_claim_numeric_post_equivalence(db):
    opaque = hit(url='https://facebook.com/kestrel-university/posts/pfbidFictionalOpaque')
    numeric = hit()
    assert post_identity(opaque['url']) != post_identity(numeric['url'])
    assert post_identity(opaque['url']).startswith('facebook:opaque:')
    report = collect(db, [SOURCE], client=FakeClient({'results': [opaque]}, {'results': [numeric]}), now=NOW)
    assert report['events'] == 1
    # Shared event title does not prove these are the same announcement.
    assert report['announcements'] == 2
    assert len(events(db, NOW)[0]['announcements']) == 2
