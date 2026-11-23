from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urljoin, urlsplit

import feedparser
from bs4 import BeautifulSoup

from .domain import canonical_url, facebook_post, norm, parse_moment, region_from
from .extract import CTF, clean_html, extract
from .network import FetchError, RateLimited
from .event_context import attach_article_context
from .verification import meetup_id


class Result:
    def __init__(self):
        self.announcements = []
        self.discovered = 0
        self.warnings = []
        self.deleted = []
        self.message = ''
        self.decisions = []
        self.publisher_leads = []


def bluesky(source, client, known, now):
    result = Result()
    actor = source['actor']
    endpoint = 'https://public.api.bsky.app/xrpc/app.bsky.feed.'
    cutoff = now - timedelta(days=source.get('lookback_days', 540))
    posts = {}
    cursor = None
    for page in range(source.get('max_pages', 4)):
        params = {'actor': actor, 'limit': 100, 'filter': 'posts_no_replies'}
        if cursor:
            params['cursor'] = cursor
        response = json.loads(client.read(endpoint + 'getAuthorFeed', params=params))
        if not isinstance(response.get('feed'), list):
            raise FetchError('Unexpected Bluesky response')
        feed = response['feed']
        oldest = now
        for item in feed:
            p = item['post']
            # An organizer's repost of someone else's content is not their announcement.
            if p['author'].get('handle', '').lower() != actor.lower() and p['author'].get('did') != actor:
                continue
            created = datetime.fromisoformat(p['record']['createdAt'].replace('Z', '+00:00'))
            oldest = min(oldest, created)
            if created >= cutoff:
                posts[p['uri']] = p
        cursor = response.get('cursor')
        if not cursor or oldest < cutoff:
            break
    else:
        if cursor and oldest >= cutoff:
            result.warnings.append('Author-feed page limit reached; older posts may be missing')
    # Recheck every retained public post, including posts outside the feed window,
    # for corrections, deletion, or moderation. Empty successful responses confirm
    # unavailability; network failures never delete anything.
    uris = sorted({row['external_id'] for row in known if row['external_id']})
    for i in range(0, len(uris), 25):
        chunk = uris[i:i + 25]
        try:
            response = json.loads(client.read(endpoint + 'getPosts', params=[('uris', x) for x in chunk]))
            if not isinstance(response.get('posts'), list):
                raise FetchError('Unexpected post recheck response')
            returned = {p['uri']: p for p in response['posts']}
            posts.update(returned)
            for uri in set(chunk) - set(returned):
                posts.pop(uri, None)
                result.deleted.append(uri)
        except (FetchError, ValueError, KeyError) as exc:
            result.warnings.append(f'Post recheck failed: {type(exc).__name__}')
    result.discovered = len(posts)
    for uri, post in posts.items():
        if any(label.get('val') in ('!no-unauthenticated', '!hide') for label in post.get('labels', [])):
            if uri in uris:
                result.deleted.append(uri)
            continue
        record = post['record']
        text = record.get('text', '')
        if not CTF.search(text):
            # If an edited existing post no longer supports a CTF, remove its facts.
            if uri in uris:
                result.deleted.append(uri)
            continue
        title = text.split('\n')[0]
        links = []
        encoded = text.encode('utf-8')
        for facet in record.get('facets', []):
            for feature in facet.get('features', []):
                if feature.get('$type') == 'app.bsky.richtext.facet#link':
                    bounds = facet['index']
                    label = encoded[bounds['byteStart']:bounds['byteEnd']].decode('utf-8', errors='replace')
                    links.append((label, feature['uri']))
        url = f"https://bsky.app/profile/{post['author']['did']}/post/{uri.rsplit('/', 1)[-1]}"
        ann = extract(title, text, url, source, posted_at=record['createdAt'], links=links, external_id=uri)
        if ann:
            result.announcements.append(attach_discovery(ann, links, [source['url'], url]))
    result.message = 'Public author feed and full post text read through the documented Bluesky API; only extracted facts and brief excerpts retained, no media.'
    return result


def posted_from_html(soup):
    # Calendar <time> nodes often describe the event, not publication.
    for selector, attr in [('meta[property="article:published_time"]', 'content'), ('time[itemprop="datePublished"][datetime]', 'datetime'), ('time[pubdate][datetime]', 'datetime')]:
        node = soup.select_one(selector)
        if node:
            return node.get(attr)
    return None


def article_parts(raw, url, source):
    """Read a configured publisher's content area, never its navigation/sidebar."""
    soup = BeautifulSoup(raw, 'html.parser')
    article = (soup.select_one(source['article_selector']) if source.get('article_selector') else
               soup.find('article') or soup.find('main') or soup)
    if article is None:
        raise FetchError('Configured article selector was not found')
    if source.get('exclude_selector'):
        for node in article.select(source['exclude_selector']):
            node.decompose()
    # A semantic article header contains the announcement's own title on many
    # university CMSs. Keep that title while still excluding page-wide headers,
    # navigation, footers, and their outbound links from event evidence.
    article_nodes = [article] if article.name == 'article' else article.select('article')
    own_header = article_nodes[0].find('header', recursive=False) if len(article_nodes) == 1 else None
    header_title = own_header.select_one(source.get('title_selector', 'h1')) if own_header else None
    text, cleaned = clean_html(str(article))
    for field, label in [('organizer_selector', 'Organized by'), ('status_selector', '')]:
        if source.get(field):
            nodes = soup.select(source[field])
            extra = '\n'.join(node.get_text(' ', strip=True) for node in nodes)
            if extra:
                text += '\n' + (label + ' ' if label else '') + extra
    title_node = (cleaned.select_one(source['title_selector']) or header_title if source.get('title_selector') else
                  cleaned.find('h1') or header_title or soup.find('title'))
    title = title_node.get_text(' ', strip=True) if title_node else ''
    if source.get('title_from_metadata'):
        meta = soup.select_one('meta[property="og:title"]')
        if meta and meta.get('content'):
            title = meta['content']
    if not CTF.search(title):
        # Some university pages have a generic page heading and a specific event
        # heading inside the article. Do not promote arbitrary prose to a title.
        candidates = [node.get_text(' ', strip=True) for node in cleaned.select('h1, h2, h3')
                      if CTF.search(node.get_text(' ', strip=True))
                      and re.search(r'\b20\d{2}\b', node.get_text(' ', strip=True))]
        if len(candidates) == 1:
            title = candidates[0]
    links = content_links(cleaned, url)
    return soup, title, text, links


def content_links(cleaned, url):
    links = [(a.get_text(' ', strip=True), urljoin(url, a['href'])) for a in cleaned.select('a[href]')]
    # A Facebook embed is an outbound post link, not permission to fetch it.
    # Restrict inspection to the article container, excluding shared footers.
    for frame in cleaned.select('iframe[src]'):
        src = urlsplit(urljoin(url, frame['src']))
        if src.hostname in ('www.facebook.com', 'facebook.com') and src.path == '/plugins/post.php':
            for href in parse_qs(src.query).get('href', []):
                if facebook_post(href):
                    links.append(('Embedded Facebook announcement', href))
    return links


def attach_discovery(ann, links, path):
    """An article's outbound link proves discovery, not access to the linked post."""
    ann['discovery_path'] = list(dict.fromkeys(path))
    related = {}
    for label, href in links:
        post = facebook_post(href)
        if post:
            related[post['url']] = {'url': post['url'], 'label': label or 'Facebook post',
                                    'access': 'linked_only', 'discovered_on': ann['url']}
    ann['related_links'] = list(related.values())
    for label, href in links:
        if not facebook_post(href) and re.search(r'\.pdf(?:\?|$)', href, re.I):
            ann['related_links'].append({'url': href, 'label': label or 'Publisher attachment',
                                         'access': 'linked_only', 'discovered_on': ann['url']})
    ann['related_links'] = list({link['url']: link for link in ann['related_links']}.values())
    return ann


def publisher_context_from_content(source, content, url):
    """Opt-in relationship evidence from the article itself, not site chrome."""
    if not source.get('discover_publishers'):
        return source, []
    from .relationships import publisher_leads_from_html, relationship_scope
    leads = publisher_leads_from_html(content, url)
    context = dict(source)
    if source.get('relationship_scope'):
        proof = relationship_scope(content)
        if proof:
            context['_relationship_scope_quote'] = proof['quote']
    return context, leads


def html(source, client, known, now):
    # Preserve the publisher's title. Conference components use the shared
    # explicit-contest body check; an agenda heading alone cannot name a CTF.
    if source.get('ctf_component_heading'):
        source = {**source, 'body_identity': True}
    result = Result()
    allowed = source.get('allowed_hosts', [urlsplit(source['url']).hostname])
    limit = source.get('max_pages', 12)
    root = canonical_url(source['url'])
    indexes = {root, *(canonical_url(u) for u in source.get('index_urls', []))}
    queue = list(dict.fromkeys([root, *sorted(indexes - {root})]))
    paths = {root: [root]}
    for index in indexes - {root}:
        paths[index] = [root, index]
    # Existing announcements are rechecked, even if they leave the news index.
    queue += [row['url'] for row in known if urlsplit(row['url']).hostname in allowed]
    for row in known:
        paths.setdefault(row['url'], json.loads(row['payload']).get('discovery_path', [root, row['url']]))
    seen = set()
    pattern = re.compile(source.get('link_pattern', r'ctf|capture|hackforgov|news|announcement'), re.I)
    while queue and len(seen) < limit:
        url = queue.pop(0)
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            raw = client.public_page(url, allowed)
            is_index = bool(source.get('index_only') and url in indexes)
            if is_index:
                soup = BeautifulSoup(raw, 'html.parser')
                title_node = soup.find('title')
                title, text, article_links = title_node.get_text(' ', strip=True) if title_node else '', '', []
            else:
                soup, title, text, article_links = article_parts(raw, url, source)
            posted = posted_from_html(soup)
            links = [(a.get_text(' ', strip=True), urljoin(url, a['href'])) for a in soup.select(source.get('link_selector', 'a[href]')) if a.get('href')]
            if source.get('index_only') and not is_index and not source.get('follow_article_links'):
                # Related-event widgets on detail pages are not the recurring
                # archive. Known details are still rechecked on every run.
                links = []
            for label, href in links:
                candidate = canonical_url(href)
                if candidate and urlsplit(candidate).hostname in allowed and pattern.search(candidate + ' ' + label) and candidate not in seen and candidate not in queue:
                    queue.append(candidate)
                    paths[candidate] = paths[url] + [candidate]
            # Announcement index pages and generic conference information do not
            # identify a particular CTF simply because some footer mentions one.
            eligible_title = not is_index and (CTF.search(title) or re.search(r'\b(?:ROOTCON|RC|TCON)\s*\d+\b', title, re.I) or source.get('body_identity'))
            if source.get('reject_text_pattern') and re.search(source['reject_text_pattern'], text, re.I):
                result.decisions.append({'url': url, 'title': title[:240], 'accepted': False, 'reason': 'Unpublished/draft calendar entry'})
                continue
            if eligible_title:
                ann = extract(title, text, url, source, posted_at=posted, links=article_links)
                if ann:
                    result.announcements.append(attach_discovery(ann, article_links, paths[url]))
                result.decisions.append({'url': url, 'title': title[:240], 'accepted': bool(ann),
                                         'reason': 'Identified CTF announcement' if ann else 'Body/title does not establish an in-scope competition and edition'})
            else:
                result.decisions.append({'url': url, 'title': title[:240], 'accepted': False,
                                         'reason': 'Archive index' if is_index else 'No identifiable CTF in title'})
            # Schema.org Event is an explicit machine-readable announcement path.
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    data = json.loads(script.string or script.get_text())
                except ValueError:
                    continue
                nodes = data if isinstance(data, list) else data.get('@graph', [data])
                for node in nodes:
                    if not isinstance(node, dict) or node.get('@type') not in ('Event', 'SportsEvent') or not CTF.search(node.get('name', '')):
                        continue
                    ann = extract(node['name'], node.get('description', ''), node.get('url', url), source, posted_at=node.get('datePublished'))
                    if ann:
                        for k, field in [('startDate', 'start'), ('endDate', 'end')]:
                            if node.get(k):
                                ann['facts'][field] = parse_moment(node[k])
                                ann['field_evidence'][field] = {'url': url, 'quote': f'Schema.org Event {k}: {node[k]}'}
                        result.announcements.append(attach_discovery(ann, article_links, paths[url]))
        except (FetchError, ValueError) as exc:
            if url == canonical_url(source['url']):
                raise
            result.warnings.append(f'{urlsplit(url).path}: {exc}')
    result.discovered = len(seen)
    if queue:
        result.warnings.append('Page budget reached; additional links deferred')
    result.message = 'Organizer index scanned for new announcements; known announcement pages rechecked. Generic conferences and evergreen CTF descriptions are excluded.'
    return result


def rss(source, client, known, now):
    result = Result()
    raw = client.public_page(source['url'])
    # Keep iframe hrefs for linked-post provenance. We never render feed HTML;
    # clean_html removes executable content before text extraction.
    feed = feedparser.parse(raw, sanitize_html=False)
    if not feed.version:
        raise FetchError('Response is not a supported RSS or Atom feed')
    entries = feed.entries[:source.get('max_items', 40)]
    result.discovered = len(entries)
    allowed = source.get('allowed_hosts', [urlsplit(source['url']).hostname])
    recheck = {}
    paths = {}
    retained_urls = {row['url'] for row in known}
    for entry in entries:
        content = entry.get('content', [{}])[0].get('value', entry.get('summary', ''))
        if source.get('feed_text_format') == 'markdown':
            content = content.replace('\\n', '\n')
        text, soup = clean_html(content)
        posted = None
        if entry.get('published_parsed'):
            posted = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        elif entry.get('published'):
            posted = entry.published
        url = canonical_url(entry.get('link', ''))
        if not url:
            continue
        links = content_links(soup, url)
        paths[url] = [source['url'], url]
        context, leads = publisher_context_from_content(source, soup, url)
        ann = extract(entry.get('title', ''), text, url, context, posted_at=posted, links=links)
        if ann:
            ann['verification_method'] = 'feed'
            ann['publisher_leads'] = leads
            attach_article_context(ann, soup)
        elif source.get('publisher_news'):
            result.publisher_leads.extend(leads)
        if ann and (url not in retained_urls or not source.get('follow_articles')):
            result.announcements.append(attach_discovery(ann, links, paths[url]))
        result.decisions.append({'url': url, 'title': entry.get('title', ''), 'accepted': bool(ann),
                                 'stage': 'feed_body', 'reason': 'Identified CTF announcement' if ann else 'Body/title does not establish an in-scope competition and edition'})
        # A feed often contains only a teaser or "read more". Follow new entries,
        # not just previously accepted articles. No individual URL configuration.
        if (source.get('follow_articles') or meetup_id(url)) and urlsplit(url).hostname in allowed:
            recheck[url] = (entry.get('title', ''), posted)
    # Re-fetch retained article pages even after an item leaves the feed.
    for row in known:
        if urlsplit(row['url']).hostname in allowed:
            if source.get('content_complete') and row['url'] in paths and not meetup_id(row['url']):
                continue
            payload = json.loads(row['payload'])
            recheck.setdefault(row['url'], (payload['title'], payload.get('posted_at')))
            paths.setdefault(row['url'], payload.get('discovery_path', [source['url'], row['url']]))
    for url, (fallback_title, fallback_posted) in recheck.items():
        try:
            if meetup_id(url):
                from .opportunity_pages import primary_event_url, verify_page
                # A failed read must not replace an already checked page with
                # an older feed excerpt or advance its successful-read clock.
                if url in retained_urls:
                    result.announcements = [a for a in result.announcements if a['url'] != url]
                ann, reason = verify_page(client.public_page(url, allowed), primary_event_url(url), source, client, now)
                result.decisions.append({'url': url, 'title': ann['title'] if ann else fallback_title,
                                         'accepted': bool(ann), 'stage': 'event_page', 'reason': reason})
                if ann:
                    ann['posted_at'] = fallback_posted
                    result.announcements = [a for a in result.announcements if a['url'] != url]
                    result.announcements.append(attach_discovery(ann, [], paths[url]))
                continue
            soup, title, text, links = article_parts(client.public_page(url, allowed), url, source)
            article = soup.select_one(source['article_selector']) if source.get('article_selector') else soup.find('article') or soup.find('main') or soup
            context, leads = publisher_context_from_content(source, article, url)
            ann = extract(title or fallback_title, text, url, context,
                          posted_at=posted_from_html(soup) or fallback_posted, links=links)
            if ann:
                ann['publisher_leads'] = leads
                attach_article_context(ann, article)
                # Prefer the rechecked current article over its feed excerpt.
                result.announcements = [a for a in result.announcements if a['url'] != ann['url']]
                result.announcements.append(attach_discovery(ann, links, paths[url]))
            elif source.get('publisher_news'):
                result.publisher_leads.extend(leads)
            result.decisions.append({'url': url, 'title': title or fallback_title, 'accepted': bool(ann),
                                     'stage': 'article_body', 'publisher_leads': len(leads),
                                     'reason': 'Identified CTF announcement' if ann else 'No confirmed competition; publisher relationships retained only' if leads and source.get('publisher_news') else 'Body/title does not establish an in-scope competition and edition'})
        except RateLimited as exc:
            result.retry_after = exc.retry_after
            result.warnings.append(f'Article recheck rate limited: {exc}')
            break
        except FetchError as exc:
            result.warnings.append(f'Article recheck: {exc}')
    result.message = f'Public RSS/Atom feed scanned; {len(recheck)} new or retained article URLs rechecked.'
    return result


def ctftime(source, client, known, now):
    result = Result()
    international = source.get('include_international_online', False)
    international_pool = {}
    if international:
        from .ctftime_primary import append_international, read_directory, failure_status
        result.route_checks = []
    start = now - timedelta(days=source.get('lookback_days', 180))
    finish = now + timedelta(days=source.get('future_days', 365))
    pool = {}
    # Small windows avoid silently losing events to the API's result cap.
    while start < finish:
        end = min(start + timedelta(days=31), finish)
        params = {'limit': 100, 'start': int(start.timestamp()), 'finish': int(end.timestamp())}
        if international:
            try:
                data = read_directory(client, source['url'], result, params)
            except FetchError as exc:
                result.failed, result.failure_status = True, failure_status(exc)
                result.message = 'CTFtime directory fetch failed; candidate count is unverified.'
                if isinstance(exc, RateLimited):
                    result.retry_after = exc.retry_after
                return result
        else:
            data = json.loads(client.read(source['url'], params=params))
        if not isinstance(data, list):
            raise FetchError('Unexpected CTFtime response')
        if len(data) >= 100:
            result.warnings.append('CTFtime monthly response hit 100-event cap')
        pool.update({str(x['id']): x for x in data})
        start = end
    for row in known:
        external_id = row['external_id']
        if external_id and external_id not in pool:
            try:
                event_url = source['url'] + external_id + '/'
                pool[external_id] = read_directory(client, event_url, result) if international else json.loads(client.read(event_url))
            except (FetchError, ValueError):
                result.warnings.append(f'CTFtime event {external_id} recheck failed')
    result.discovered = len(pool)
    names = {norm(x) for x in source.get('organizer_names', [])}
    ids = set(source.get('organizer_ids', []))
    for eid, e in pool.items():
        organizers = e.get('organizers', [])
        ph_org = any(norm(o.get('name', '')) in names or o.get('id') in ids for o in organizers)
        ph_location = e.get('onsite') and re.search(r'\b(?:Philippines|Manila|Cebu|Davao|Baguio|Pampanga|Tuguegarao)\b', e.get('location', ''), re.I)
        if not (ph_org or ph_location):
            if international:
                international_pool[eid] = e
            continue
        organizer = ', '.join(o['name'] for o in organizers) or 'Organizer not specified by CTFtime'
        config = {'organizer': organizer, 'organizer_key': norm(organizer), 'kind': 'ctftime'}
        title = e['title']
        ann = extract(title, e.get('description', ''), e['ctftime_url'], config, external_id=eid)
        if not ann:
            # A CTFtime event ID is an explicit stable competition identifier.
            ann = {'url': e['ctftime_url'], 'title': title, 'posted_at': None, 'kind': 'announcement',
                   'access': 'full', 'external_id': eid, 'evidence': None,
                   'identity': {'organizer_key': config['organizer_key'], 'series': title, 'edition': 'ctftime-' + eid, 'region': region_from(e.get('location', '')), 'stage': 'main'},
                   'facts': {'name': title, 'organizer': organizer, 'region': region_from(e.get('location', ''))}}
        # The API supplies confirmed instants. Registration times are NOT supplied.
        ann['facts'].update({'start': parse_moment(e['start']), 'end': parse_moment(e['finish']),
                             'format': 'in_person' if e.get('onsite') else 'online',
                             'eligibility': e.get('restrictions') or None})
        # Link to organizer website as a secondary link, never call it a verified
        # registration endpoint or silently claim CTFtime is the original organizer.
        ann['facts']['summary'] = 'Listed by CTFtime; follow the linked listing to the organizer. Registration deadline was not supplied.'
        result.announcements.append(ann)
    result.message = 'Supplementary event metadata only. Included Philippine venues or explicitly configured Philippine organizers; global events open to everyone are excluded.'
    if international:
        append_international(source, client, known, now, result, international_pool)
        result.message = ('CTFtime directory scanned; Philippine metadata retained and international online discoveries checked against organizer pages. '
                          'Directory schedules alone do not verify international editions; unverified primary pages are reported separately.')
    return result


def brave(source, client, known, now):
    result = Result()
    token = os.environ.get('BRAVE_SEARCH_API_KEY')
    if not token or os.environ.get('BRAVE_STORAGE_RIGHTS') != '1':
        raise CredentialsRequired('Requires server-side BRAVE_SEARCH_API_KEY and a plan with storage rights (BRAVE_STORAGE_RIGHTS=1). Facebook full posts are not fetched.')
    for target in source['targets']:
        for page in range(2):
            data = json.loads(client.read(source['url'], params={'q': target['query'], 'count': 20, 'offset': page}, headers={'X-Subscription-Token': token, 'Accept': 'application/json'}))
            for hit in data.get('web', {}).get('results', []):
                result.discovered += 1
                url = canonical_url(hit.get('url', ''))
                if not url:
                    continue
                p = urlsplit(url)
                if p.hostname not in ('facebook.com', 'www.facebook.com', 'm.facebook.com'):
                    continue
                post = facebook_post(url)
                accounts = {str(a).lower() for a in [target['account'], *target.get('account_aliases', [])]}
                if not post or (post['account'] or '').lower() not in accounts:
                    continue
                # No snippets, dates, registration states or body facts are promoted.
                config = {**target, 'kind': 'brave'}
                ann = extract(hit.get('title', ''), '', url, config, access='search_only')
                if ann:
                    ann['discovery_path'] = [source['url'], url]
                    ann['discovery_query'] = target['query']
                    result.announcements.append(ann)
            if not data.get('query', {}).get('more_results_available'):
                break
    result.message = 'Indexed Facebook URLs only. Full-post access is not verified; results may be stale or incomplete.'
    return result


class CredentialsRequired(Exception):
    pass


from .tavily import tavily
from .luma import luma
from .mlh import mlh
from .opportunity_search import opportunity_search

ADAPTERS = {'bluesky': bluesky, 'html': html, 'rss': rss, 'ctftime': ctftime, 'brave': brave, 'tavily': tavily, 'luma': luma, 'mlh': mlh, 'opportunity_search': opportunity_search, 'opportunity_calendar': opportunity_search}
