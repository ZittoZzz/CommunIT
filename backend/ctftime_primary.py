"""Opt-in organizer verification for international CTFtime discoveries.

The directory supplies discovery, organizer attribution, and an online/open scope
signal. It cannot supply a primary edition's schedule, price, or signup state.
No event URLs, names, dates, or credentials are configured in this adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .domain import MANILA, canonical_url, in_window, instant, moment, norm, parse_moment
from .network import FetchError, RateLimited


class Unverified(FetchError):
    def __init__(self, reason, status='unverified'):
        self.status = status
        super().__init__(reason)


def failure_status(exc):
    if isinstance(exc, RateLimited):
        return 'rate_limited'
    if isinstance(exc, Unverified):
        return exc.status
    return 'blocked' if 'HTTP 403' in str(exc) or 'disallows automated access' in str(exc) else 'error'


def read_directory(client, url, result, params=None):
    """Record API failures as failures, including malformed successful responses."""
    try:
        data = json.loads(client.read(url, params=params))
        if not isinstance(data, list if params is not None else dict):
            raise ValueError('Unexpected API shape')
    except (FetchError, ValueError, UnicodeDecodeError) as exc:
        result.route_checks.append({'route': 'directory_api', 'url': url,
                                    'status': failure_status(exc), 'error': str(exc)})
        if isinstance(exc, FetchError):
            raise
        raise FetchError('CTFtime API response is unreadable; candidate count is unverified') from None
    result.route_checks.append({'route': 'directory_api', 'url': url, 'status': 'ok',
                                'entries': len(data) if isinstance(data, list) else 1})
    return data


MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
DATE_TIME = rf'{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+20\d{{2}})?(?:,?\s+(?:at\s+)?)\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*(?:AM|PM)?\s*(?:UTC|GMT)(?![\w+−-]|\s*[+−-]\s*\d)'
UTC_RANGE = re.compile(rf'({DATE_TIME})\s*(?:until|to|[-–—])\s*({DATE_TIME})', re.I)


def utc_moment(raw, edition_year):
    """Borrow only the year of the matching primary heading, never the API year."""
    cleaned = re.sub(r'(?<=\d)(?:st|nd|rd|th)\b', '', raw, flags=re.I)
    cleaned = re.sub(r'\b(?:at|UTC|GMT)\b|[,\.]', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    explicit = re.search(r'\b20\d{2}\b', cleaned)
    if explicit and explicit[0] != edition_year:
        raise Unverified('Primary schedule year conflicts with the matching edition heading')
    if not explicit:
        cleaned = re.sub(r'^(\S+ \d+) ', rf'\1 {edition_year} ', cleaned)
    cleaned = re.sub(r'\bSept\b', 'Sep', cleaned, flags=re.I)
    for month_format in ('%B', '%b'):
        for clock_format in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M%p'):
            try:
                dt = datetime.strptime(cleaned, month_format + ' %d %Y ' + clock_format).replace(tzinfo=timezone.utc)
                return moment(raw, dt.astimezone(MANILA).isoformat(), 'datetime', 'Asia/Manila')
            except ValueError:
                continue
    raise Unverified('Primary UTC schedule could not be parsed')


def parse_primary(raw, url, event, source):
    soup = BeautifulSoup(raw, 'html.parser')
    for node in soup.select('script, style, nav, footer, aside, template, [hidden], [aria-hidden="true"]'):
        node.decompose()
    text = ' '.join(soup.stripped_strings)
    page_title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if re.search(r'^(?:Access denied|Just a moment|Verify you are human|Attention Required)', page_title, re.I):
        raise Unverified('Primary page is an access challenge', 'blocked')
    if re.search(r'\b(?:enable|requires?|needs?) JavaScript\b', text, re.I) and len(text) < 400:
        raise Unverified('Primary page requires JavaScript; edition facts are unreadable', 'javascript_only')
    if len(text) < 70:
        raise Unverified('Primary page has insufficient readable event content', 'unreadable')
    headings = [n.get_text(' ', strip=True) for n in soup.select('h1,h2,h3')]
    title = next((h for h in headings if norm(h) == norm(event.get('title', ''))), None)
    years = re.findall(r'\b20\d{2}\b', title or '')
    if not title or len(set(years)) != 1:
        raise Unverified('Primary heading does not establish the exact directory edition')
    ranges = [(utc_moment(m[1], years[0]), utc_moment(m[2], years[0]), m[0])
              for m in UTC_RANGE.finditer(text)]
    if not ranges:
        raise Unverified('Primary schedule is absent or unsupported; directory times are not confirmation')
    schedules = {(a['value'], b['value']) for a, b, _ in ranges}
    if len(schedules) != 1:
        raise Unverified('Conflicting primary schedules; dates remain unverified')
    start, end, schedule_quote = ranges[0]
    if instant(end) <= instant(start):
        raise Unverified('Primary event end does not follow its start')
    if any(instant(value) != instant(parse_moment(event.get(key, '')))
           for value, key in ((start, 'start'), (end, 'finish'))):
        raise Unverified('Primary dates conflict with the directory schedule; dates remain unverified')
    participation = re.search(
        r'\b(?:You are allowed to play\b[^.!?]*|(?:Play|Participate) (?:individually|solo|as a team)\b[^.!?]*|'
        r'Teams? (?:can|may|must|of|solve)\b[^.!?]*)', text, re.I)
    internet = re.search(r'[^.!?]*\b(?:online|internet|public infrastructure|platform|account)\b[^.!?]*', text, re.I)
    competition = re.search(r'CTF|capture[ -]the[ -]flag', text, re.I)
    restriction = re.search(
        r'\b(?:invitation[- ]only|invite[- ]only|only (?:open|available) to|must (?:be|reside in)|'
        r'(?:residents?|citizens?|students?|nationals?) only|limited to|not open to|not eligible|'
        r'only (?:students?|residents?|citizens?|nationals?)|Philippin\w*|Filipino\w*)\b[^.!?]*', text, re.I)
    if not participation or not internet or not competition or restriction:
        raise Unverified('Primary online participation rules are absent or restricted; international access is unverified')
    organizer = ', '.join(o.get('name', '') for o in event.get('organizers', []) if o.get('name'))
    if not organizer:
        raise Unverified('Directory organizer attribution is missing')
    directory_url = canonical_url(event.get('ctftime_url', ''))
    if not directory_url:
        raise Unverified('Directory event provenance is missing')
    facts = {'name': title, 'organizer': organizer, 'region': 'Worldwide',
             'geography': 'international_online', 'topic': 'cybersecurity', 'format': 'online',
             'start': start, 'end': end, 'competition_date': None,
             'deadline': None, 'submission_deadline': None, 'registration_opens': None,
             'eligibility': participation[0].strip() + '. Philippine-specific eligibility terms are not stated. CTFtime labels entry Open.',
             'price': {'kind': 'unknown'}, 'account_required': None,
             'registration_url': None, 'registration_state': 'unknown',
             'organizer_event_url': url, 'lifecycle': None,
             'recurring': bool(event.get('ctf_id')),
             'summary': 'Discovered through CTFtime; matching edition and UTC schedule verified on the organizer page. Unstated registration and submission cutoffs remain unknown.'}
    proof = {}
    def cite(field, quote, evidence_url=url, **extra):
        proof[field] = {'url': evidence_url, 'quote': quote[:600], **extra}
    cite('name', title)
    cite('edition', title)
    cite('organizer', 'CTFtime organizer attribution: ' + organizer, directory_url)
    cite('organizer_event_url', 'CTFtime organizer URL: ' + url, directory_url)
    cite('start', title + ' | ' + schedule_quote)
    cite('end', title + ' | ' + schedule_quote)
    cite('eligibility', participation[0], directory_url=directory_url,
         directory_quote='restrictions=Open; onsite=false', limitations='Philippine-specific eligibility terms are not stated')
    for field in ('format', 'geography'):
        cite(field, participation[0] + ' | ' + internet[0], directory_url=directory_url,
             directory_quote='onsite=false; restrictions=Open', basis='directory_scope_and_primary_participation_rules')
    cite('topic', competition[0])
    free = next((match for node in soup.select('p,li')
                 for sentence in re.split(r'[.!?]', node.get_text(' ', strip=True))
                 if (match := re.fullmatch(
                     r'(?:(?:Participation|Registration|Entry) is free(?: for (?:everyone|anyone|all participants))?|'
                     r'(?:It is )?free to (?:participate|play|enter)|(?:There is )?no (?:registration|entry|participation) fee)',
                     sentence.strip(), re.I))), None)
    if free:
        facts['price'] = {'kind': 'free', 'amount': 0}
        cite('price', free[0])
    closed = re.search(r'\bRegistration (?:is )?(?:now )?closed\b', text, re.I)
    if closed:
        facts['registration_state'] = 'closed'
        cite('registration_state', closed[0])
    # A navigation link, invitation to register, or account rule does not prove
    # that a signup destination is currently enabled. Only an actual live form
    # on this matching edition page can establish it in this bounded route.
    for form in soup.select('form'):
        if closed or form.has_attr('disabled') or form.find_parent('fieldset', disabled=True):
            continue
        target = canonical_url(urljoin(url, form.get('action') or url))
        if (not target or urlsplit(target).hostname != urlsplit(url).hostname
                or not re.search(r'/(?:register|signup|sign-up)(?:/|$)', urlsplit(target).path)):
            continue
        fields = [n for n in form.select('input[type="password"]')
                  if not n.has_attr('disabled') and not n.find_parent('fieldset', disabled=True)]
        controls = form.select('button:not([type]), button[type="submit"], input[type="submit"]')
        enabled = [n for n in controls if not n.has_attr('disabled') and n.get('aria-disabled') != 'true'
                   and not n.find_parent('fieldset', disabled=True) and 'disabled' not in n.get('class', []) and re.fullmatch(
                       r'(?:Register|Sign up|Create account)', n.get('value') or n.get_text(' ', strip=True), re.I)]
        if fields and enabled:
            facts.update(registration_url=url, registration_state='open', account_required=True)
            cite('registration_url', 'Enabled registration form on matching edition page')
            cite('registration_state', enabled[0].get('value') or enabled[0].get_text(' ', strip=True), basis='live_registration_widget')
            cite('account_required', 'Registration form requires an email or password')
            break
    series = re.sub(r'\b20\d{2}\b', '', title).strip()
    return {'url': url, 'title': title, 'posted_at': None, 'access': 'full', 'official': True,
            'publisher': organizer, 'publisher_role': 'organizer',
            'external_id': str(event['id']), 'kind': 'registration' if facts['registration_state'] == 'open' else 'announcement',
            'identity': {'organizer_key': norm(organizer), 'series': series,
                         'edition': 'ctftime-' + str(event['id']), 'region': 'Worldwide', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof,
            'directory_provenance': {'url': directory_url, 'api_url': source['url'], 'organizer_url': url},
            'discovery_path': [source['url'], directory_url, url]}


def public_organizer_url(raw):
    """Directory links must not name obvious local network destinations."""
    url = canonical_url(raw)
    if not url:
        return None
    parsed = urlsplit(url)
    host = parsed.hostname
    try:
        if parsed.port not in (None, 443 if parsed.scheme == 'https' else 80):
            return None
        ip_address(host)
    except ValueError:
        # Invalid port specifications and local/unqualified names are not
        # public organizer addresses. IP literals are intentionally unsupported.
        try:
            parsed.port
        except ValueError:
            return None
        return url if '.' in host and not host.endswith(('.local', '.internal', '.localhost')) else None
    return None


def append_international(source, client, known, now, result, pool):
    retained = {str(row['external_id']) for row in known if row['external_id']}
    checked = 0
    for eid, event in pool.items():
        decision = {'url': event.get('ctftime_url'), 'title': event.get('title', ''),
                    'external_id': eid, 'accepted': False, 'stage': 'international_primary'}
        result.decisions.append(decision)
        if event.get('onsite') is not False or event.get('restrictions', '').lower() != 'open':
            decision['reason'] = 'Directory does not identify an online event with Open entry'
            continue
        if eid not in retained and not in_window(parse_moment(event.get('start', '')), now, source.get('future_days', 45)):
            decision['reason'] = 'Directory start is outside the discovery window'
            continue
        url = public_organizer_url(event.get('url', ''))
        decision['primary_url'] = url
        if not url or urlsplit(url).hostname in ('ctftime.org', 'www.ctftime.org'):
            decision.update(reason='Directory has no usable organizer URL', unverified=True)
            result.warnings.append('CTFtime primary URL missing: ' + eid)
            continue
        if checked >= source.get('max_primary_pages', 30):
            decision.update(reason='Primary page limit reached; candidate unverified', unverified=True)
            result.warnings.append('CTFtime primary page limit reached')
            continue
        checked += 1
        try:
            raw = client.public_page(url, allowed_hosts=[urlsplit(url).hostname])
            result.route_checks.append({'route': 'primary_page', 'url': url, 'status': 'ok'})
        except FetchError as exc:
            result.route_checks.append({'route': 'primary_page', 'url': url, 'status': failure_status(exc), 'error': str(exc)})
            decision.update(reason=str(exc), unverified=True)
            result.warnings.append('CTFtime primary fetch failed: ' + str(exc))
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
            continue
        try:
            announcement = parse_primary(raw, url, event, source)
        except Unverified as exc:
            result.route_checks.append({'route': 'primary_verification', 'url': url, 'status': exc.status, 'error': str(exc)})
            decision.update(reason=str(exc), unverified=True)
            result.warnings.append('CTFtime primary unverified: ' + eid + ': ' + str(exc))
            continue
        result.route_checks.append({'route': 'primary_verification', 'url': url, 'status': 'ok'})
        decision.update(accepted=True, reason='Primary edition, UTC schedule, and online participation corroborated')
        result.announcements.append(announcement)
