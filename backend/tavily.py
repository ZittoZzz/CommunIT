"""Free keyless search discovery. Search output is never treated as full-post access."""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .domain import canonical_url, facebook_post, norm, region_from
from .extract import CTF, extract
from .network import FetchError, RateLimited

ENDPOINT = 'https://api.tavily.com/search'


@dataclass
class SearchResult:
    announcements: list = field(default_factory=list)
    discovered: int = 0
    warnings: list = field(default_factory=list)
    deleted: list = field(default_factory=list)
    message: str = ''
    searches: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    failed: bool = False


def search_queries(source, client):
    """Return every result before organizer/scope filtering, plus bounded audit data."""
    if source.get('url') != ENDPOINT:
        raise FetchError('Keyless search endpoint must be the official Tavily Search API')
    hits, audits, warnings = [], [], []
    rate_limit = None
    for query in source['queries']:
        payload = {'query': query['query'], 'search_depth': 'basic', 'topic': 'general',
                   'max_results': min(20, max(1, source.get('max_results', 20))),
                   'auto_parameters': False, 'include_answer': False,
                   'include_raw_content': False, 'include_images': False}
        if query.get('include_domains'):
            payload.update(include_domains=query['include_domains'], include_domains_mode='restrict')
        audit = {'query': query['query'], 'include_domains': query.get('include_domains', []),
                 'status': 'error', 'attempts': [], 'results': []}
        audits.append(audit)
        if rate_limit is not None:
            audit.update(status='skipped', message=f'Keyless quota unavailable: {rate_limit}')
            continue
        for attempt in range(2):
            try:
                data = client.post_json(ENDPOINT, payload, headers={'X-Tavily-Access-Mode': 'keyless'})
                results = data.get('results')
                if not isinstance(results, list) or any(not isinstance(hit, dict) for hit in results):
                    raise FetchError('Unexpected Tavily search response')
                audit['attempts'].append({'status': 'ok'})
                audit.update(status='ok', provider_query=data.get('query'), request_id=data.get('request_id'))
                # URLs and titles are recorded before any organizer or scope test.
                # No complete snippets, raw pages, answers, or media are retained.
                audit['results'] = [{'url': hit.get('url', ''), 'title': hit.get('title', '')[:500]}
                                    for hit in results]
                hits.extend((hit, query['query']) for hit in results)
                break
            except RateLimited as exc:
                audit['attempts'].append({'status': 'rate_limited', 'retry_after': exc.retry_after})
                if attempt == 0 and exc.retry_after is not None and 0 <= exc.retry_after <= 30:
                    time.sleep(exc.retry_after)
                    continue
                audit['message'] = str(exc)
                warnings.append(f"{query['query']}: {exc}")
                # The quota belongs to this API, not to an individual query.
                # Do not issue another query during the advertised cooldown.
                rate_limit = exc
                break
            except FetchError as exc:
                audit['attempts'].append({'status': 'error'})
                audit['message'] = str(exc)
                warnings.append(f"{query['query']}: {exc}")
                break
    return hits, audits, warnings


def post_identity(url):
    post = facebook_post(url)
    if not post:
        return None
    if post['post'].isdigit():
        return 'facebook:post:' + post['post']
    # An opaque token does not establish equivalence to any numeric post ID.
    return f"facebook:opaque:{post['account']}:{post['post']}"


def search_announcement(hit, source):
    url = canonical_url(hit.get('url', ''))
    title = unicodedata.normalize('NFKC', hit.get('title', '')).strip()
    if not url or not CTF.search(title):
        return None, 'No identifiable CTF in result title'
    host = urlsplit(url).hostname
    post = facebook_post(url)
    if host in ('facebook.com', 'www.facebook.com', 'm.facebook.com') and not post:
        return None, 'Facebook result is not an identifiable post URL'
    # Snippets can contain unrelated posts, sidebars, or "related reels". They
    # are not used to infer identity, locality, dates, eligibility, or status.
    publisher = next((p for p in source.get('organizers', [])
                      if (post and (post['account'] or '').lower() in
                          [a.lower() for a in p.get('facebook_accounts', [])])
                      or (not post and host not in ('facebook.com', 'www.facebook.com', 'm.facebook.com')
                          and host in [h.lower() for h in p.get('publisher_hosts', [])])), None)
    if publisher:
        names = [publisher['organizer'], *publisher.get('name_aliases', [])]
        named_host = any(re.search(
            r'\b' + re.escape(name) + r'\s+(?:hosts?|organizes?)\b|'
            r'\b(?:hosted|organized)\s+by\s+' + re.escape(name) + r'\b', title, re.I)
            for name in names)
        own_series = publisher.get('event_pattern') and re.search(publisher['event_pattern'], title, re.I)
        if not named_host and not own_series:
            # A configured account or partner website may promote somebody
            # else's competition. Publisher identity alone is not ownership.
            publisher = None
    hfg = re.search(r'\bhack\s*(?:for|4)\s*gov\b|\bhack\s*(?:for|4)\s*gov\s*\d+', title, re.I)
    participation = re.search(r'\b(?:students?|teams?|members?|delegates?)\b.{0,70}\b(?:wins?|won|participat\w*|competed?|placed|ranked)\b', title, re.I)
    hosting = re.search(r'\b(?:hosts?|organizes?|hosted by|organized by)\b', title, re.I)
    if participation and not hosting and not hfg:
        return None, 'Student participation does not establish Philippine event organization'
    explicit_local = re.search(
        r'\bPhilippine\s+(?:CTF|capture[ -]the[ -]flag)\b|'
        r'\b(?:CTF|capture[ -]the[ -]flag)(?:\s+competition)?\s+(?:in|at)\s+(?:the\s+)?Philippines\b|'
        r'\bPhilippine\s+(?:university|school|college|community|company|organization|government agency)\s+'
        r'(?:hosts?|organizes?)\b[^.!?\n]{0,100}\b(?:CTF|capture[ -]the[ -]flag)\b', title, re.I)
    # "Hosts a CTF ... open to participants from the Philippines" does not
    # identify a Philippine host or venue. Named configured hosts were checked
    # above; an unrelated mention of the country cannot prove event scope.
    explicit_country = re.search(r'\bPhilippine(?:s)?\b', title, re.I)
    if not publisher and not hfg and not (explicit_local and explicit_country):
        return None, 'Philippine organizer or venue not established by title/source'
    organizer = publisher['organizer'] if publisher else 'Organizer unconfirmed'
    organizer_key = publisher['organizer_key'] if publisher else 'unconfirmed-' + norm(post['account'] if post else host)
    config = {'kind': 'tavily', 'organizer': organizer, 'organizer_key': organizer_key}
    if publisher and publisher.get('url_normalization'):
        config['url_normalization'] = publisher['url_normalization']
    if publisher and publisher.get('region'):
        config['region'] = publisher['region']
    ann = extract(title, '', url, config, access='search_only', external_id=post_identity(url))
    if not ann:
        return None, 'Title lacks an unambiguous competition edition'
    ann['official'] = False
    ann['field_evidence']['philippine_connection'] = {
        'url': publisher.get('evidence_url', url) if publisher else url,
        'quote': publisher.get('philippine_connection', organizer) if publisher else title[:500]}
    if publisher:
        ann['field_evidence']['organizer'] = {'url': publisher.get('evidence_url', url), 'quote': organizer}
    if region_from(title) != 'Unspecified':
        ann['field_evidence']['region'] = {'url': url, 'quote': title[:500]}
    ann['discovery_path'] = [ENDPOINT, url]
    ann['related_links'] = []
    return ann, 'Accepted as search-only; schedule and registration remain unconfirmed'


def tavily(source, client, known, now):
    result = SearchResult()
    hits, result.searches, result.warnings = search_queries(source, client)
    result.discovered = len(hits)
    result.failed = not any(q['status'] == 'ok' for q in result.searches)
    accepted = {}
    for hit, query in hits:
        ann, reason = search_announcement(hit, source)
        result.decisions.append({'url': hit.get('url', ''), 'accepted': ann is not None, 'reason': reason})
        if not ann:
            continue
        key = ann.get('external_id') or ann['url']
        if key not in accepted:
            accepted[key] = ann
            ann['discovery_queries'] = []
        if query not in accepted[key]['discovery_queries']:
            accepted[key]['discovery_queries'].append(query)
    for ann in accepted.values():
        ann['discovery_queries'].sort()
        ann['discovery_query'] = ann['discovery_queries'][0]
        result.announcements.append(ann)
    result.message = ('Free Tavily keyless search; no API key or paid fallback. '
                      'All returned URLs are recorded before scope filtering. '
                      'Search titles identify leads only; full posts, schedules and registration are unverified.')
    return result
