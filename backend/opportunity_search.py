"""Bounded public search discovery; event facts come only from verified pages.

The optional search manifest is an experiment input containing complete output
from generic public-web searches. It is not a permanent event seed source.
"""
from __future__ import annotations

import json
from datetime import timedelta
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .domain import MANILA, canonical_url, in_window
from .network import FetchError, RateLimited
from .tavily import ENDPOINT, SearchResult, search_queries


HOSTS = frozenset(('luma.com', 'lu.ma', 'meetup.com', 'www.meetup.com',
                  'gdg.community.dev', 'devpost.com', 'www.devpost.com',
                  'globalai.community', 'www.globalai.community'))


class PageBudgetExceeded(FetchError):
    pass


class PublicPages:
    """Share one page budget/cache with verifiers' ownership-link checks."""
    def __init__(self, client, maximum, route_checks, *, external_pages=False):
        self.client, self.maximum, self.route_checks = client, maximum, route_checks
        self.external_pages = external_pages
        self.cache, self.count, self.current_url = {}, 0, None

    def __getattr__(self, name):
        return getattr(self.client, name)

    def public_page(self, url, allowed_hosts=None):
        if url in self.cache:
            return self.cache[url]
        if self.count >= self.maximum:
            raise PageBudgetExceeded('Shared public-page budget reached; ownership or event verification incomplete')
        self.count += 1
        try:
            fetch = self.client.discovered_page if self.external_pages else self.client.public_page
            raw = fetch(url, allowed_hosts=allowed_hosts)
        except FetchError as exc:
            if url != self.current_url:
                status = ('rate_limited' if isinstance(exc, RateLimited) else
                          'blocked' if '403' in str(exc) or 'robots' in str(exc) else 'error')
                self.route_checks.append({'route': 'verification_link', 'url': url,
                                          'discovered_on': self.current_url, 'status': status,
                                          'error': str(exc)[:400]})
            raise
        self.cache[url] = raw
        if url != self.current_url:
            self.route_checks.append({'route': 'verification_link', 'url': url,
                                      'discovered_on': self.current_url, 'status': 'ok'})
        return raw


def supported_url(value, *, external_pages=False):
    """Restrict search-controlled fetches to supported public event platforms."""
    if not isinstance(value, str):
        return None
    try:
        url = canonical_url(value)
        host = urlsplit(url).hostname if url else None
        port = urlsplit(url).port if url else None
    except ValueError:
        return None
    if not host or port not in (None, 80, 443):
        return None
    if urlsplit(url).path.lower().endswith('.pdf'):
        return None
    if host in ('meetup.com', 'www.meetup.com') and '/find' in urlsplit(url).path.lower():
        # Public city/topic pages contain actual edition links. Their search
        # cards remain discovery evidence only, never event facts.
        if not urlsplit(url).path.startswith('/find/ph--'):
            return None
    if host not in HOSTS and not host.endswith('.devpost.com') and not external_pages:
        return None
    if host in ('facebook.com', 'www.facebook.com', 'm.facebook.com', 'rootcon.org', 'www.rootcon.org'):
        return None
    # Keep explicit Luma calendar navigation; normalize primary event aliases
    # using the same platform rules as the verifier, never a guessed slug.
    if host in ('luma.com', 'lu.ma') and parse_qs(urlsplit(url).query).get('k') == ['c']:
        return url
    from .opportunity_pages import primary_event_url
    return primary_event_url(url) or url


def verify_page(raw, url, source, client, now):
    # Delayed import keeps search transport independent of page parser support.
    from .opportunity_pages import verify_page as verify
    return verify(raw, url, source, client, now)


def page_event_links(raw, url, *, external_pages=False):
    from .opportunity_pages import page_event_links as links
    return links(raw, url, external_pages=external_pages)


def round_robin_urls(queries_by_url, searches):
    """Give each query a turn without changing the provider's per-query rank."""
    buckets = [deque(url for url, queries in queries_by_url.items() if audit['query'] in queries)
               for audit in searches]
    ordered, seen = [], set()
    while any(buckets):
        for bucket in buckets:
            while bucket and bucket[0] in seen:
                bucket.popleft()
            if bucket:
                url = bucket.popleft()
                seen.add(url)
                ordered.append(url)
    return ordered


def manifest_searches(path):
    """Read every result, retaining URL/title audit data and no search snippets."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError) as exc:
        raise FetchError('External public-search manifest is unreadable') from exc
    if (not isinstance(data, dict) or not isinstance(data.get('provider'), str)
            or not data['provider'].strip() or not isinstance(data.get('queries'), list)
            or not data['queries']):
        raise FetchError('External public-search manifest requires provider and queries')
    provider, hits, searches, warnings = data['provider'].strip(), [], [], []
    for query in data['queries']:
        if (not isinstance(query, dict) or not isinstance(query.get('query'), str)
                or not query['query'].strip()
                or query.get('status') not in ('ok', 'error', 'blocked', 'rate_limited', 'skipped')
                or not isinstance(query.get('results'), list)
                or any(not isinstance(hit, dict) or not isinstance(hit.get('url'), str)
                       or not isinstance(hit.get('title'), str) for hit in query['results'])):
            raise FetchError('External public-search manifest has an invalid query record')
        audit = {'query': query['query'], 'provider': provider,
                 'mode': 'external_public_search_manifest', 'status': query['status'],
                 'results': [{'url': hit['url'], 'title': hit['title'][:500]}
                             for hit in query['results']]}
        if query['status'] != 'ok':
            audit['message'] = 'External search did not complete successfully'
            warnings.append(f"{query['query']}: {audit['message']} ({query['status']})")
        else:
            hits.extend((hit, query['query']) for hit in audit['results'])
        searches.append(audit)
    return hits, searches, warnings, provider


def opportunity_search(source, client, known, now):
    """Search first, fetch bounded supported pages, then apply the event window."""
    result = SearchResult()
    result.route_checks, result.publisher_leads = [], []
    external = bool(source.get('search_results_path'))
    external_pages = bool(source.get('allow_external_pages'))
    calendar = source.get('kind') == 'opportunity_calendar'
    if calendar:
        provider = 'Public calendars'
        roots = source.get('calendar_urls') or [source['url']]
        result.searches = [{'query': url, 'provider': provider, 'mode': 'public_calendar',
                            'status': 'ok', 'results': [{'url': url, 'title': ''}]} for url in roots]
        hits = [({'url': url, 'title': ''}, url) for url in roots]
    elif external:
        hits, result.searches, result.warnings, provider = manifest_searches(source['search_results_path'])
    else:
        queries = source.get('queries')
        if source.get('query_templates'):
            start = now.astimezone(MANILA).date()
            end = start + timedelta(days=source.get('window_days', 45))
            months = list(dict.fromkeys((start + timedelta(days=i)).strftime('%B %Y')
                                       for i in range((end - start).days + 1)))
            queries = [{'query': template.format(months=' '.join(months))}
                       for template in source['query_templates']]
        hits, result.searches, result.warnings = search_queries({**source, 'queries': queries,
                                                                'url': source.get('url', ENDPOINT)}, client)
        provider = 'Tavily keyless'
        for audit in result.searches:
            audit.update(provider=provider, mode='keyless_api')
    result.discovered = len(hits)
    result.failed = not any(query['status'] == 'ok' for query in result.searches)
    if result.failed and any(query['status'] == 'blocked' for query in result.searches):
        result.failure_status = 'blocked'
    if result.failed and any(query['status'] == 'rate_limited' or any(
            attempt.get('status') == 'rate_limited' for attempt in query.get('attempts', []))
            for query in result.searches):
        result.failure_status = 'rate_limited'

    queries_by_url, titles = {}, {}
    for hit, query in hits:
        raw_url = hit.get('url', '')
        url = supported_url(raw_url, external_pages=external_pages)
        if url is None:
            result.decisions.append({'url': raw_url, 'title': hit.get('title', '')[:500],
                                     'accepted': False, 'decision': 'unsupported',
                                     'query': query, 'reason': 'No supported public-page verifier for this URL'})
            continue
        queries_by_url.setdefault(url, set()).add(query)
        titles.setdefault(url, hit.get('title', '')[:500])

    # Refresh stored public evidence even if search no longer returns the page.
    retained = {}
    for row in known:
        url = supported_url(row['url'], external_pages=external_pages)
        if not url:
            continue
        try:
            payload = json.loads(row['payload'])
        except (KeyError, TypeError, ValueError):
            payload = {}
        retained[url] = payload
    # Persisted results must not change which current search/calendar pages
    # fit in the same budget. Refresh retained-only URLs after normal discovery.
    urls = round_robin_urls(queries_by_url, result.searches)
    roots, linked = deque(urls), deque()
    refresh = deque(url for url in retained if url not in queries_by_url)
    paths = {url: [url] for url in [*urls, *refresh]}
    for url in refresh:
        payload = retained[url]
        if isinstance(payload.get('discovery_path'), list) and payload['discovery_path']:
            paths[url] = payload['discovery_path']
    depths = {url: 0 for url in paths}
    all_paths = {url: [path] for url, path in paths.items()}
    accepted_urls = {}
    maximum = min(80, max(1, int(source.get('max_pages', 40))))
    pages = PublicPages(client, maximum, result.route_checks, external_pages=external_pages)
    accepted, seen = {}, set()
    prefer_link = False
    stopped_by_limit = False
    last_link_root = None
    while (roots or linked or refresh) and len(seen) < maximum:
        queue = (linked if linked and (prefer_link or not roots) else roots) if roots or linked else refresh
        if queue is linked and last_link_root:
            # A large first calendar must not consume every later calendar's
            # event budget. Rotate to another actual discovery root if possible.
            for _ in range(len(linked)):
                if paths[linked[0]][0] != last_link_root:
                    break
                linked.rotate(-1)
        url = queue.popleft()
        if queue is linked:
            last_link_root = paths[url][0]
        prefer_link = queue is roots
        if url in seen:
            continue
        seen.add(url)
        depth, path = depths[url], paths[url]
        try:
            # Redirects remain confined to this exact supported host. Verifiers
            # decide separately whether an organizer-designated link is valid.
            pages.current_url = url
            raw = pages.public_page(url, allowed_hosts=[urlsplit(url).hostname])
            result.route_checks.append({'route': 'public_page', 'url': url, 'status': 'ok',
                                        'depth': depth, 'path': path})
            from .opportunity_pages import primary_event_url
            follow_directory = depth == 0 or (external_pages and depth < 2 and not primary_event_url(url))
            children = page_event_links(raw, url, external_pages=external_pages) if follow_directory else []
            for child in children:
                child = supported_url(child, external_pages=external_pages)
                if not child or child == url:
                    continue
                child_path = path + [child]
                if child_path not in all_paths.setdefault(child, []):
                    all_paths[child].append(child_path)
                queries_by_url.setdefault(child, set()).update(queries_by_url.get(url, set()))
                if child not in paths:
                    paths[child], depths[child] = path + [child], depth + 1
                    linked.append(child)
                elif child not in seen and depths[child] == 0:
                    # A directly returned event also has this proven calendar
                    # route; use it without fetching the event a second time.
                    paths[child], depths[child] = path + [child], 1
                    linked.append(child)
            # A transport endpoint is not an organizer or event evidence URL.
            page_source = {**source, 'url': url}
            ann, reason = ((None, 'Public organizer calendar links discovered for verification') if children else
                           verify_page(raw, url, page_source, pages, now))
            parsed_fields = ann.get('facts') if ann else None
            conflict_in_window = bool(ann and any(
                in_window(claim.get('date'), now, source.get('window_days', 45))
                for claim in ann.get('facts', {}).get('date_conflicts', [])))
            if ann and url not in retained and not conflict_in_window and not any(
                    in_window(ann.get('facts', {}).get(field), now, source.get('window_days', 45))
                    for field in ('start', 'deadline', 'submission_deadline')):
                ann, reason = None, 'No confirmed start or cutoff inside the 45-day Manila window (date-only boundaries unresolved)'
            result.decisions.append({'url': url, 'title': titles.get(url, ''),
                                     'accepted': bool(ann), 'decision': 'accepted' if ann else 'rejected',
                                     'queries': sorted(queries_by_url.get(url, [])), 'reason': reason,
                                     'depth': depth, 'path': path, 'parsed_fields': parsed_fields})
            if not ann:
                continue
            old = retained.get(url, {})
            queries = set(old.get('discovery_queries', [])) | queries_by_url.get(url, set())
            if old.get('discovery_query'):
                queries.add(old['discovery_query'])
            queries.update(ann.get('discovery_queries', []))
            if queries:
                ann['discovery_queries'] = sorted(queries)
                ann['discovery_query'] = ann['discovery_queries'][0]
            ann['discovery_provider'] = provider
            prefix = [] if external or calendar else [ENDPOINT]
            verified_path = ann.get('discovery_path') or [url]
            ann['discovery_path'] = list(dict.fromkeys(prefix + path + verified_path))
            key = ann.get('url') or url
            accepted_urls[key] = url
            if key in accepted:
                previous = accepted[key]
                previous['discovery_queries'] = sorted(set(previous.get('discovery_queries', [])) | queries)
                if previous['discovery_queries']:
                    previous['discovery_query'] = previous['discovery_queries'][0]
            else:
                accepted[key] = ann
        except PageBudgetExceeded as exc:
            result.warnings.append(str(exc))
            result.decisions.append({'url': url, 'accepted': False, 'decision': 'deferred',
                                     'reason': str(exc), 'depth': depth, 'path': path})
            break
        except (FetchError, ValueError, KeyError) as exc:
            status = ('rate_limited' if isinstance(exc, RateLimited) else
                      'blocked' if '403' in str(exc) or 'robots' in str(exc) else 'error')
            result.route_checks.append({'route': 'verification', 'url': url, 'status': status,
                                        'error': str(exc)[:400], 'depth': depth, 'path': path})
            result.decisions.append({'url': url, 'accepted': False, 'decision': status,
                                     'reason': str(exc)[:400], 'depth': depth, 'path': path})
            result.warnings.append('Public opportunity verification failed: ' + str(exc)[:400])
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
                stopped_by_limit = True
                break
    pending = [url for url in dict.fromkeys([*roots, *linked, *refresh]) if url not in seen]
    if pending:
        reason = ('Public page provider rate limit; verification not attempted' if stopped_by_limit
                  else 'Public detail page budget reached')
        if not stopped_by_limit:
            result.warnings.append(f'Public detail limit {maximum}; {len(pending)} pages were not checked')
        result.decisions.extend({'url': url, 'accepted': False, 'decision': 'deferred',
                                 'reason': reason, 'depth': depths[url], 'path': paths[url]} for url in pending)
    result.announcements = list(accepted.values())
    for ann in result.announcements:
        url = accepted_urls[ann['url']]
        ann['discovery_paths'] = all_paths.get(url, [ann['discovery_path']])
    # A configured calendar descriptor is not a successful page check.
    # Preserve partial results when any page was read; all-access failures must
    # not masquerade as a healthy empty calendar or a successful search.
    if calendar and not any(c['status'] == 'ok' for c in result.route_checks):
        failures = [c['status'] for c in result.route_checks]
        if failures:
            result.failed = True
            result.failure_status = ('rate_limited' if 'rate_limited' in failures else
                                     'blocked' if all(s == 'blocked' for s in failures) else 'error')
    result.message = (f'{provider}: {len(hits)} search hits; {pages.count} public page checks; '
                      f'{len(result.announcements)} verified or retained opportunities. '
                      'Search output supplies discovery only; public pages supply event facts. '
                      + ('Public calendar links fetched directly; no search provider was called.' if calendar else
                         'External public-search manifest used for this experiment; Tavily was not called.'
                         if external else 'Free keyless access; no API key or paid fallback.'))
    return result
