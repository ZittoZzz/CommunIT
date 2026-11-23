"""Synthetic search transport tests; no benchmark identifiers or live requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.collect import collect
from backend.db import connect, events
from backend.domain import parse_moment
from backend.network import FetchError, RateLimited
from backend import opportunity_search as search
from backend.tavily import ENDPOINT


NOW = datetime(2035, 11, 22, 3, tzinfo=timezone.utc)
URL = 'https://luma.com/example-tech-session'
QUERY = 'Philippines AI technology events November December 2035'
SECOND_QUERY = 'online programming workshops worldwide December 2035'
SOURCE = {'id': 'public-opportunities', 'name': 'Public opportunity search',
          'kind': 'opportunity_search', 'url': ENDPOINT, 'window_days': 45,
          'queries': [{'query': QUERY}, {'query': SECOND_QUERY}]}


def announcement(url=URL, start=None):
    start = start or NOW + timedelta(days=7)
    return {'url': url, 'external_id': 'evt-example', 'title': 'Community Technology Session',
            'posted_at': None, 'access': 'full', 'official': True, 'kind': 'announcement',
            'identity': {'organizer_key': 'luma:cal-example', 'series': 'Luma event',
                         'edition': 'evt-example', 'region': 'Philippines', 'stage': 'main'},
            'facts': {'name': 'Community Technology Session', 'organizer': 'Example Community',
                      'region': 'Philippines', 'geography': 'PH', 'topic': 'general_it',
                      'format': 'online', 'start': parse_moment(start.isoformat()),
                      'end': None, 'deadline': None, 'submission_deadline': None,
                      'registration_state': 'unknown', 'registration_url': url},
            'field_evidence': {'name': {'url': url, 'quote': 'Community Technology Session'},
                               'start': {'url': url, 'quote': start.isoformat()}},
            'discovery_path': [url]}


class Client:
    def __init__(self, responses=None, pages=None):
        self.responses = list(responses or [])
        self.pages = pages or {URL: b'public page'}
        self.calls, self.requests = [], []

    def post_json(self, url, payload, headers=None):
        self.calls.append((url, deepcopy(payload), deepcopy(headers)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def public_page(self, url, allowed_hosts=None):
        self.requests.append((url, allowed_hosts))
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return page


def manifest(tmp_path, queries=None):
    path = tmp_path / 'complete-search-results.json'
    data = {'provider': 'Public web search tool', 'queries': queries or [
        {'query': QUERY, 'status': 'ok', 'results': [{'url': URL, 'title': 'Search title'}]},
        {'query': SECOND_QUERY, 'status': 'ok', 'results': [{'url': URL, 'title': 'Another title'}]},
    ]}
    path.write_text(json.dumps(data))
    return {**SOURCE, 'search_results_path': str(path)}


def verify(monkeypatch, value=None):
    calls = []
    def parser(raw, url, source, client, now):
        calls.append((raw, url, deepcopy(source)))
        return deepcopy(value if value is not None else announcement(url)), 'Verified synthetic public page'
    monkeypatch.setattr(search, 'verify_page', parser)
    monkeypatch.setattr(search, 'page_event_links', lambda raw, url, **kwargs: [])
    return calls


def test_external_complete_manifest_deduplicates_fetches_and_keeps_truthful_provider(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    parsed = verify(monkeypatch)
    client = Client()
    result = search.opportunity_search(source, client, [], NOW)
    assert result.discovered == 2 and len(result.announcements) == 1
    assert len(client.requests) == len(parsed) == 1 and client.calls == []
    assert parsed[0][2]['url'] == URL
    ann, = result.announcements
    assert ann['facts']['name'] == 'Community Technology Session'
    assert ann['discovery_queries'] == sorted([QUERY, SECOND_QUERY])
    assert ann['discovery_path'] == [URL]
    assert ann['discovery_provider'] == 'Public web search tool'
    assert all(s['provider'] == 'Public web search tool' for s in result.searches)
    assert 'Tavily was not called' in result.message


def test_platform_alias_hits_keep_raw_audit_but_fetch_one_primary_url(tmp_path, monkeypatch):
    alias = 'https://lu.ma/example-tech-session?ref=search'
    source = manifest(tmp_path, [
        {'query': QUERY, 'status': 'ok', 'results': [{'url': URL, 'title': 'Primary'}]},
        {'query': SECOND_QUERY, 'status': 'ok', 'results': [{'url': alias, 'title': 'Alias'}]},
    ])
    verify(monkeypatch)
    client = Client()
    result = search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [URL]
    assert result.searches[1]['results'][0]['url'] == alias
    assert result.announcements[0]['discovery_queries'] == sorted([QUERY, SECOND_QUERY])


def test_native_mode_reuses_keyless_search_and_never_promotes_snippets(monkeypatch):
    parsed = verify(monkeypatch)
    hit = {'url': URL, 'title': 'Unverified title', 'content': 'Registration is free, worldwide, and open until tomorrow'}
    client = Client([{'results': [hit]}, {'results': []}])
    result = search.opportunity_search(SOURCE, client, [], NOW)
    ann, = result.announcements
    assert len(client.calls) == 2 and len(parsed) == 1
    assert all(headers == {'X-Tavily-Access-Mode': 'keyless'} for _, _, headers in client.calls)
    assert 'Registration is free' not in json.dumps(result.searches + result.announcements)
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['discovery_path'] == [ENDPOINT, URL]


@pytest.mark.parametrize('url', [
    'https://facebook.com/example/posts/123', 'https://luma.com.evil.example/event',
    'https://evildevpost.com/event', 'https://evil.example/?next=https://luma.com/event',
    'https://user:password@luma.com/event', 'https://luma.com:1234/event', 'javascript:alert(1)',
    'https://www.meetup.com/find/?keywords=AI', 'https://globalai.community/file.pdf',
])
def test_unsupported_or_unsafe_search_hosts_are_audited_without_fetching(tmp_path, monkeypatch, url):
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': url, 'title': 'A result'}]}])
    parsed = verify(monkeypatch)
    client = Client()
    result = search.opportunity_search(source, client, [], NOW)
    assert result.discovered == 1 and result.searches[0]['results'][0]['url'] == url
    assert result.decisions[0]['decision'] == 'unsupported'
    assert not result.failed and not result.announcements and not client.requests and not parsed


@pytest.mark.parametrize('url', ['https://gdg.community.dev/events/details/example/',
                                  'https://www.meetup.com/example/events/123/',
                                  'https://example-challenge.devpost.com/'])
def test_supported_platform_hosts_are_available_to_page_verifier(tmp_path, monkeypatch, url):
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': url, 'title': 'A result'}]}])
    verify(monkeypatch)
    client = Client(pages={url: b'public page'})
    assert len(search.opportunity_search(source, client, [], NOW).announcements) == 1
    assert client.requests[0][0] == url


@pytest.mark.parametrize('failure,decision', [(FetchError('HTTP 403'), 'blocked'),
                                            (FetchError('robots.txt disallows automated access'), 'blocked'),
                                            (FetchError('ReadTimeout'), 'error')])
def test_failed_page_is_partial_not_a_successful_empty_match(tmp_path, monkeypatch, failure, decision):
    source = manifest(tmp_path)
    verify(monkeypatch)
    with connect(':memory:') as db:
        report = collect(db, [source], client=Client(pages={URL: failure}), now=NOW)
        record, = report['sources']
        assert record['status'] == 'partial' and record['accepted'] == 0
        assert record['decisions'][0]['decision'] == decision


def test_successful_empty_search_is_distinct_from_failed_search(tmp_path, monkeypatch):
    verify(monkeypatch)
    for status, expected in [('ok', 'ok'), ('error', 'error'), ('blocked', 'blocked'), ('rate_limited', 'rate_limited')]:
        source = manifest(tmp_path, [{'query': QUERY, 'status': status, 'results': []}])
        with connect(':memory:') as db:
            report = collect(db, [source], client=Client(), now=NOW)
            assert report['sources'][0]['status'] == expected
            assert report['sources'][0]['discovered'] == report['sources'][0]['accepted'] == 0


@pytest.mark.parametrize('offset,accepted', [(0, 1), (44, 1), (45, 0), (-1, 0)])
def test_search_window_uses_start_or_cutoff_and_not_search_title(tmp_path, monkeypatch, offset, accepted):
    source = manifest(tmp_path)
    verify(monkeypatch, announcement(start=NOW + timedelta(days=offset)))
    result = search.opportunity_search(source, Client(), [], NOW)
    assert len(result.announcements) == accepted


def test_future_explicit_submission_cutoff_can_qualify_earlier_start(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    ann = announcement(start=NOW - timedelta(days=3))
    ann['facts']['submission_deadline'] = parse_moment((NOW + timedelta(days=2)).isoformat())
    verify(monkeypatch, ann)
    assert len(search.opportunity_search(source, Client(), [], NOW).announcements) == 1


def test_normal_collect_replay_preserves_one_record_and_first_seen(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    verify(monkeypatch)
    db = connect(':memory:')
    first = collect(db, [source], client=Client(), now=NOW)
    before, = events(db, NOW)
    second = collect(db, [source], client=Client(), now=NOW + timedelta(hours=1))
    after, = events(db, NOW)
    assert first['events'] == second['events'] == first['announcements'] == second['announcements'] == 1
    assert second['sources'][0]['new_announcements'] == 0
    assert before['id'] == after['id'] and before['first_seen'] == after['first_seen']
    assert after['announcements'][0]['discovery_queries'] == sorted([QUERY, SECOND_QUERY])
    db.close()


def test_retained_event_refreshes_after_search_disappearance_and_window_expiry(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    verify(monkeypatch)
    db = connect(':memory:')
    collect(db, [source], client=Client(), now=NOW)
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': []}])
    client = Client()
    report = collect(db, [source], client=client, now=NOW + timedelta(days=100))
    assert report['sources'][0]['discovered'] == 0 and report['sources'][0]['accepted'] == 1
    assert client.requests[0][0] == URL
    event, = events(db, NOW)
    assert event['announcements'][0]['discovery_queries'] == sorted([QUERY, SECOND_QUERY])
    db.close()


def test_page_budget_audits_every_hit_but_never_fetches_more_than_80(tmp_path, monkeypatch):
    urls = [f'https://luma.com/example-{i}' for i in range(85)]
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': u, 'title': 'Result'} for u in urls]}])
    source['max_pages'] = 100
    verify(monkeypatch)
    client = Client(pages={u: b'page' for u in urls})
    result = search.opportunity_search(source, client, [], NOW)
    assert len(client.requests) == 80 and result.discovered == 85
    assert len(result.searches[0]['results']) == 85
    assert sum(d['decision'] == 'deferred' for d in result.decisions) == 5
    assert result.warnings


def test_page_budget_round_robins_queries_before_a_later_query_starves(tmp_path, monkeypatch):
    first_urls = [f'https://luma.com/example-{i}' for i in range(10)]
    later = 'https://luma.com/other-query-result'
    source = manifest(tmp_path, [
        {'query': QUERY, 'status': 'ok', 'results': [{'url': u, 'title': 'Result'} for u in first_urls]},
        {'query': SECOND_QUERY, 'status': 'ok', 'results': [{'url': later, 'title': 'Result'}]},
    ])
    source['max_pages'] = 2
    verify(monkeypatch)
    client = Client(pages={u: b'page' for u in [*first_urls, later]})
    search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [first_urls[0], later]


def test_bounded_cold_and_warm_replay_keep_identical_query_and_calendar_traversal(tmp_path, monkeypatch):
    calendar = 'https://globalai.community/chapters/example/'
    later = 'https://luma.com/later-query-event'
    deferred = 'https://luma.com/deferred-event'
    source = manifest(tmp_path, [
        {'query': QUERY, 'status': 'ok', 'results': [{'url': u, 'title': 'Result'} for u in [calendar, deferred]]},
        {'query': SECOND_QUERY, 'status': 'ok', 'results': [{'url': later, 'title': 'Result'}]},
    ])
    source['max_pages'] = 3
    verify(monkeypatch)
    monkeypatch.setattr(search, 'page_event_links', lambda raw, url, **kwargs: [URL] if url == calendar else [])
    saved_pages = {url: b'same saved page' for url in [calendar, URL, later, deferred]}
    cold_client = Client(pages=deepcopy(saved_pages))
    cold = search.opportunity_search(source, cold_client, [], NOW)
    known = [{'url': ann['url'], 'payload': json.dumps(ann)} for ann in cold.announcements]
    warm_client = Client(pages=deepcopy(saved_pages))
    warm = search.opportunity_search(source, warm_client, known, NOW)
    assert [url for url, _ in cold_client.requests] == [calendar, URL, later]
    assert warm_client.requests == cold_client.requests
    assert [ann['url'] for ann in warm.announcements] == [ann['url'] for ann in cold.announcements]
    assert warm.route_checks == cold.route_checks
    assert warm.decisions == cold.decisions


@pytest.mark.parametrize('maximum,refreshed', [(2, False), (3, True)])
def test_retained_only_refresh_follows_discovered_calendar_children_when_budget_allows(tmp_path, monkeypatch, maximum, refreshed):
    calendar = 'https://globalai.community/chapters/example/'
    retained_url = 'https://luma.com/no-longer-in-search'
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': calendar, 'title': 'Calendar'}]}])
    source['max_pages'] = maximum
    verify(monkeypatch)
    monkeypatch.setattr(search, 'page_event_links', lambda raw, url, **kwargs: [URL] if url == calendar else [])
    old = announcement(retained_url)
    known = [{'url': retained_url, 'payload': json.dumps(old)}]
    client = Client(pages={url: b'saved page' for url in [calendar, URL, retained_url]})
    result = search.opportunity_search(source, client, known, NOW)
    expected = [calendar, URL] + ([retained_url] if refreshed else [])
    assert [url for url, _ in client.requests] == expected
    decision = next(item for item in result.decisions if item['url'] == retained_url)
    assert decision['decision'] == ('accepted' if refreshed else 'deferred')
    if not refreshed:
        assert 'budget' in decision['reason']


def test_calendar_link_is_followed_once_with_depth_and_actual_discovery_path(tmp_path, monkeypatch):
    root = 'https://globalai.community/communities/'
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': root, 'title': 'Communities'}]}])
    verify(monkeypatch)
    monkeypatch.setattr(search, 'page_event_links', lambda raw, url, **kwargs: [URL] if url == root else [])
    client = Client(pages={root: b'calendar with event link', URL: b'public event'})
    result = search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [root, URL]
    assert result.announcements[0]['discovery_path'] == [root, URL]
    assert result.announcements[0]['discovery_queries'] == [QUERY]
    assert result.decisions[1]['depth'] == 1 and result.decisions[1]['path'] == [root, URL]


def test_depth_one_event_cannot_expand_into_more_related_events(tmp_path, monkeypatch):
    root = 'https://globalai.community/communities/'
    extra = 'https://luma.com/unrelated-recommendation'
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': root, 'title': 'Communities'}]}])
    verify(monkeypatch)
    monkeypatch.setattr(search, 'page_event_links', lambda raw, url, **kwargs: [URL] if url == root else [extra])
    client = Client(pages={root: b'calendar', URL: b'event'})
    result = search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [root, URL]
    assert len(result.announcements) == 1


def test_ownership_verification_shares_hard_public_page_budget(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    source['max_pages'] = 1
    verify(monkeypatch)
    owner = 'https://luma.com/example-calendar'
    def verifier(raw, url, source, client, now):
        client.public_page(owner, allowed_hosts=['luma.com'])
        return announcement(url), 'Verified ownership'
    monkeypatch.setattr(search, 'verify_page', verifier)
    client = Client(pages={URL: b'event', owner: b'calendar'})
    result = search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [URL]
    assert not result.announcements
    assert result.decisions[0]['decision'] == 'deferred'
    assert result.warnings


def test_owner_page_reused_without_consuming_budget_twice(tmp_path, monkeypatch):
    other = 'https://luma.com/second-example'
    owner = 'https://luma.com/example-calendar'
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': u, 'title': 'Result'} for u in [URL, other]]}])
    source['max_pages'] = 3
    verify(monkeypatch)
    def verifier(raw, url, source, client, now):
        client.public_page(owner, allowed_hosts=['luma.com'])
        return announcement(url), 'Verified ownership'
    monkeypatch.setattr(search, 'verify_page', verifier)
    client = Client(pages={URL: b'event', other: b'event', owner: b'calendar'})
    result = search.opportunity_search(source, client, [], NOW)
    assert [url for url, _ in client.requests] == [URL, owner, other]
    assert len(result.announcements) == 2


def test_rate_limited_page_stops_requests_and_defers_remaining(tmp_path, monkeypatch):
    other = 'https://luma.com/second-example'
    source = manifest(tmp_path, [{'query': QUERY, 'status': 'ok', 'results': [{'url': u, 'title': 'Result'} for u in [URL, other]]}])
    verify(monkeypatch)
    client = Client(pages={URL: RateLimited(120), other: b'page'})
    result = search.opportunity_search(source, client, [], NOW)
    assert len(client.requests) == 1 and result.retry_after == 120
    assert [d['decision'] for d in result.decisions] == ['rate_limited', 'deferred']


def test_bad_manifest_fails_before_any_network_request(tmp_path):
    source = manifest(tmp_path)
    path = source['search_results_path']
    with open(path, 'w') as handle:
        json.dump({'provider': 'Public search', 'queries': [{'query': QUERY, 'status': 'ok', 'results': 'invalid'}]}, handle)
    client = Client()
    with pytest.raises(FetchError, match='invalid query record'):
        search.opportunity_search(source, client, [], NOW)
    assert client.calls == client.requests == []
