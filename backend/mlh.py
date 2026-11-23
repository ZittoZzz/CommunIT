"""One organizer calendar: public Global Hack Week editions and their signup pages.

No event editions are configured here. This adapter uses the normal collector's
announcement contract without relaxing the CTF rules of other sources.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .domain import MANILA, canonical_url, in_window, instant, manila_day, moment, parse_moment
from .network import FetchError, RateLimited
from .event_text import retain_description

HOSTS = ('ghw.mlh.com', 'events.mlh.com')


def page_text(soup):
    return ' '.join(soup.stripped_strings)


def event_links(soup, base, host, *, registration=False):
    links = []
    for node in soup.select('a[href]'):
        url = canonical_url(urljoin(base, node['href']))
        if not url or urlsplit(url).hostname != host:
            continue
        if not re.fullmatch(r'/events/[^/]+/?', urlsplit(url).path):
            continue
        if registration and not re.search(r'\b(?:register|sign up)\b', node.get_text(' ', strip=True), re.I):
            continue
        if url not in links:
            links.append(url)
    return links


def published_moment(raw):
    """Use MLH's explicit UTC metadata, never infer a zone from a bare clock."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC', raw):
        try:
            dt = datetime.strptime(raw, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
        except ValueError:
            return moment(raw)
    else:
        value = parse_moment(raw)
        dt = instant(value)
        if not dt:
            return value
    return moment(raw, dt.astimezone(MANILA).isoformat(), 'datetime', 'Asia/Manila')


def schedule(soup, field):
    values = [published_moment(n.get('content') or n.get_text(' ', strip=True))
              for n in soup.select(f'[itemprop="{field}"]')]
    values = [v for v in values if v['precision'] in ('date', 'datetime')]
    if len({(v['value'], v['precision']) for v in values}) > 1:
        raise FetchError(f'Conflicting MLH {field} values; schedule unverified')
    return values[0] if values else None


def parse_registration(raw, url, edition_raw, edition_url, source):
    soup = BeautifulSoup(raw, 'html.parser')
    edition = BeautifulSoup(edition_raw, 'html.parser')
    for node in soup.select('script, style, nav, footer'):
        node.decompose()
    for node in edition.select('script, style'):
        node.decompose()
    name = soup.select_one('h1[itemprop="name"]')
    organizer = soup.select_one('[itemprop="organizer"] [itemprop="name"]')
    organizer_name = organizer.get('content') or organizer.get_text(' ', strip=True) if organizer else ''
    if not organizer_name:
        heading = soup.find(lambda n: n.name == 'h4' and n.get_text(strip=True) == 'Hosted by')
        host = heading.find_next_sibling('div') if heading else None
        organizer_name = host.get_text(' ', strip=True) if host else ''
    if not name or organizer_name != 'Major League Hacking':
        raise FetchError('MLH registration page lacks an event name or organizer identity')
    title = name.get_text(' ', strip=True)
    if not re.search(r'\bGlobal Hack Week\b', title, re.I):
        raise FetchError('Linked signup is not a Global Hack Week edition')
    identifier = re.fullmatch(r'/events/(\d+)-[^/]+/?', urlsplit(url).path)
    if not identifier:
        raise FetchError('MLH edition identifier is unverified')
    start, end = schedule(soup, 'startDate'), schedule(soup, 'endDate')
    if start and end and (instant(start) > instant(end) if instant(start) and instant(end)
                          else manila_day(start) > manila_day(end)):
        raise FetchError('MLH event end precedes its start; schedule unverified')
    text, edition_text = page_text(soup), page_text(edition)
    online = soup.select_one('[itemprop="location"][itemtype="https://schema.org/VirtualLocation"]')
    worldwide = re.search(r'\b(?:for )?anyone, anywhere\b', edition_text, re.I)
    if not online or not worldwide:
        return None, 'International online access is unverified'
    eligibility_heading = soup.find(lambda n: n.name in ('h3', 'h4') and n.get_text(strip=True) == 'Who can attend?')
    audiences = [n.get_text(' ', strip=True) for n in eligibility_heading.parent.select('button.option')] if eligibility_heading else []
    permission = re.search(r"I am either over 18 years of age or have a parent's permission to participate in this event\.?", text)
    eligibility = 'Worldwide, including the Philippines. ' + ('; '.join(audiences) + '.' if audiences else 'Audience restrictions not confirmed.')
    if permission:
        eligibility += ' Under 18s need a parent’s permission.'
    free = re.search(r'Global Hack Week is a 100% free event for anyone, anywhere!?', edition_text, re.I)
    price = {'kind': 'free', 'amount': 0} if free else {'kind': 'unknown'}
    # A specific signup price takes precedence over general series copy.
    prices = [n.get('content') or n.get_text(' ', strip=True) for n in soup.select('[itemprop="price"]')]
    amounts = {float(p) for p in prices if re.fullmatch(r'\d+(?:\.\d+)?', p)}
    if amounts and min(amounts) > 0:
        price = {'kind': 'paid'}
        if len(amounts) == 1:
            price['amount'] = next(iter(amounts))
        currency = soup.select_one('[itemprop="priceCurrency"]')
        if currency and re.fullmatch(r'[A-Z]{3}', currency.get('content', '')):
            price['currency'] = currency['content']
    elif len(amounts) > 1:
        price = {'kind': 'unknown'}  # Mixed free/paid offers need ticket-specific evidence.
    state, account, signup_quote = 'unknown', None, None
    if re.search(r'\bThis event ended\b|\bRegistration (?:is )?closed\b', text, re.I):
        state = 'closed'
        signup_quote = re.search(r'\bThis event ended\b|\bRegistration (?:is )?closed\b', text, re.I)[0]
    else:
        for node in soup.select('a[href]'):
            target = canonical_url(urljoin(url, node['href']))
            label = node.get_text(' ', strip=True)
            if (target == url.rstrip('/') + '/register' and not node.has_attr('disabled')
                    and node.get('aria-disabled') != 'true' and 'disabled' not in node.get('class', [])
                    and re.fullmatch(r'(?:Log In & )?Register', label, re.I)):
                state, account, signup_quote = 'open', True if re.search(r'Log In', label, re.I) else None, label
                break
    facts = {'name': title, 'organizer': organizer_name, 'region': 'Worldwide',
             'geography': 'international_online', 'topic': 'general_it', 'format': 'online',
             'start': start, 'end': end, 'competition_date': None,
             'deadline': None, 'submission_deadline': None, 'registration_opens': None,
             'eligibility': eligibility, 'price': price, 'account_required': account,
             'registration_url': url, 'registration_state': state,
             'organizer_event_url': edition_url, 'summary': None, 'lifecycle': None}
    proof = {}
    def cite(field, quote, source_url=url):
        proof[field] = {'url': source_url, 'quote': quote[:600]}
    cite('name', title)
    cite('organizer', organizer_name)
    cite('organizer_event_url', 'Organizer edition page: ' + edition_url, edition_url)
    cite('registration_url', 'Register link designates ' + url, edition_url)
    cite('format', online.get_text(' ', strip=True))
    cite('geography', worldwide[0], edition_url)
    cite('eligibility', '; '.join(audiences) + (' | ' + permission[0] if permission else ''))
    description = soup.select_one('[itemprop="description"]')
    if description:
        cite('topic', description.get_text(' ', strip=True))
        retain_description(facts, proof, description.get_text(' ', strip=True), url)
    for field, value in [('start', start), ('end', end)]:
        if value:
            cite(field, field + 'Date: ' + value['raw'])
    if amounts and max(amounts) > 0:
        cite('price', 'Signup price metadata: ' + ', '.join(prices))
    elif free:
        cite('price', free[0], edition_url)
    if signup_quote:
        cite('registration_state', signup_quote)
        if state == 'open':
            proof['registration_state']['basis'] = 'live_registration_widget'
            cite('account_required', signup_quote)
    return {'url': url, 'title': title, 'posted_at': None, 'access': 'full', 'official': True,
            'external_id': identifier[1], 'kind': 'registration' if state == 'open' else 'announcement',
            'identity': {'organizer_key': 'mlh', 'series': 'Global Hack Week',
                         'edition': identifier[1], 'region': 'Worldwide', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof,
            'discovery_path': [source['url'], edition_url, url]}, 'Verified organizer edition'


def mlh(source, client, known, now):
    from .adapters import Result
    result = Result()
    result.route_checks = []
    def fetch(url, route):
        try:
            raw = client.public_page(url, allowed_hosts=HOSTS)
        except FetchError as exc:
            status = 'rate_limited' if isinstance(exc, RateLimited) else 'blocked' if 'HTTP 403' in str(exc) or 'disallows automated access' in str(exc) else 'error'
            result.route_checks.append({'route': route, 'url': url, 'status': status, 'error': str(exc)})
            raise
        result.route_checks.append({'route': route, 'url': url, 'status': 'ok'})
        return raw
    try:
        raw = fetch(source['url'], 'calendar')
    except FetchError as exc:
        result.failed = True
        result.failure_status = result.route_checks[-1]['status']
        if isinstance(exc, RateLimited):
            result.retry_after = exc.retry_after
        result.message = 'MLH calendar fetch failed; qualifying edition count is unverified.'
        return result
    soup = BeautifulSoup(raw, 'html.parser')
    if not re.search(r'Attend an upcoming Global Hack Week', page_text(soup), re.I):
        raise FetchError('MLH calendar structure is unreadable; zero matches cannot be established')
    urls = event_links(soup, source['url'], 'ghw.mlh.com')
    result.discovered = len(urls)
    retained = set()
    for row in known:
        payload = json.loads(row['payload'])
        path = payload.get('discovery_path', [])
        retained.add(payload['url'])
        if len(path) == 3 and urlsplit(path[1]).hostname == 'ghw.mlh.com' and path[1] not in urls:
            urls.append(path[1])
    limit = source.get('max_items', 40)
    if len(urls) > limit:
        result.warnings.append('MLH edition limit reached; additional editions were not checked')
    seen = set()
    for edition_url in urls[:limit]:
        try:
            edition_raw = fetch(edition_url, 'edition')
            edition = BeautifulSoup(edition_raw, 'html.parser')
            links = event_links(edition, edition_url, 'events.mlh.com', registration=True)
            if len(links) != 1:
                raise FetchError('Edition signup destination is missing or ambiguous')
            url = links[0]
            if url in seen:
                continue
            seen.add(url)
            raw = fetch(url, 'registration')
            ann, reason = parse_registration(raw, url, edition_raw, edition_url, source)
            if ann and url not in retained and not any(in_window(ann['facts'].get(field), now, source.get('window_days', 45))
                                                      for field in ('start', 'deadline', 'submission_deadline')):
                ann, reason = None, 'No confirmed start or cutoff inside the 45-day window (date-only boundaries remain unresolved)'
            result.decisions.append({'url': url, 'edition_url': edition_url, 'accepted': bool(ann), 'reason': reason})
            if ann:
                result.announcements.append(ann)
        except FetchError as exc:
            result.warnings.append(f'MLH edition check failed: {exc}')
            result.decisions.append({'url': edition_url, 'accepted': False, 'reason': str(exc), 'unverified': True})
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
                break
    result.message = f'MLH calendar read successfully: {result.discovered} edition links, {len(result.announcements)} qualifying or retained editions. Unstated cutoffs remain unknown.'
    return result
