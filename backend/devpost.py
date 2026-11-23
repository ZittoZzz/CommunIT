"""Verify a supplied public Devpost overview without network or account access."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup

from .domain import MANILA, canonical_url, instant, manila_day, moment, norm, parse_moment
from .luma import community_topic, manila_moment
from .network import FetchError
from .event_text import retain_description


MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
DAY = rf'(?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}}|\d{{1,2}}\s+{MONTH}\s+20\d{{2}})'
ISO = r'20\d{2}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?'
CLOCK = re.compile(r'^\s*,?\s*(?:at|@)?\s*(\d{1,2}:\d{2})\s*([ap]\.?m\.?)?', re.I)
ZONE = re.compile(r'^\s*(UTC|GMT|EST|EDT|PST|PDT|PHT|KST|Eastern Time|Pacific Time|[A-Za-z_]+/[A-Za-z_]+)(?![\w+−-])', re.I)
OFFSETS = {'UTC': 0, 'GMT': 0, 'EST': -5, 'EDT': -4, 'PST': -8, 'PDT': -7, 'PHT': 8, 'KST': 9}
LABELS = {'submission_deadline': r'(?:project )?submission deadline(?:\s+is)?|submit\b[^.!?\n]{0,70}?\bby',
          'deadline': r'registration (?:deadline|closes?|ends?)(?:\s+is)?|register by',
          'registration_opens': r'registration opens?',
          'start': r'(?:event|hackathon|competition) (?:starts?|begins?)'}


def _events(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if any(t in ('Event', 'Hackathon') for t in ([types] if isinstance(types, str) else types)):
                yield value
            yield from walk(value.get('@graph', []))
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (TypeError, ValueError):
            continue


def _root(url):
    value = canonical_url(url or '')
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.hostname.endswith('.devpost.com') or parsed.path not in ('/', '/overview', '/rules', '/details'):
        return None
    return f'{parsed.scheme}://{parsed.netloc}/'


def _named_date(raw, anchor=None):
    """Parse a labelled date; US abbreviations require numeric-offset metadata.

    A date-only body statement can corroborate a separately explicit platform
    instant, but never supplies a made-up midnight or timezone by itself.
    """
    iso = re.match(ISO, raw)
    if iso:
        return manila_moment(iso[0]), iso[0]
    day = re.match(DAY, raw, re.I)
    if not day:
        return None, raw[:120]
    value = parse_moment(day[0])
    tail = raw[day.end():]
    clock = CLOCK.match(tail)
    if not clock:
        return value, day[0]
    zone = ZONE.match(tail[clock.end():])
    if not zone:
        return None, raw[:120]
    label = zone[1]
    # A numeric UTC offset attached to a known abbreviation is unsupported;
    # it must not be silently dropped while matching a prefix such as UTC.
    remainder = tail[clock.end() + zone.end():]
    if re.match(r'\s*[+−-]\s*\d', remainder):
        return None, raw[:120]
    region = re.match(r'\s*\(([A-Za-z_]+/[A-Za-z_]+)\)', remainder)
    try:
        if region:
            tz = ZoneInfo(region[1])
        elif '/' in label:
            tz = ZoneInfo(label)
        elif label.lower() in ('eastern time', 'pacific time'):
            if not instant(anchor):
                return None, raw[:120]
            tz = ZoneInfo('America/New_York' if label.lower() == 'eastern time' else 'America/Los_Angeles')
        elif label.upper() in OFFSETS:
            if label.upper() in ('EST', 'EDT', 'PST', 'PDT') and not instant(anchor):
                return None, raw[:120]
            tz = timezone(timedelta(hours=OFFSETS[label.upper()]))
        else:
            return None, raw[:120]
        stamp = clock[1] + re.sub(r'\.', '', clock[2] or '').upper()
        time = datetime.strptime(stamp, '%I:%M%p' if clock[2] else '%H:%M').time()
        dt = datetime.combine(datetime.fromisoformat(value['value']).date(), time, tz)
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
        return None, raw[:120]
    length = day.end() + clock.end() + zone.end() + (region.end() if region else 0)
    quote = raw[:length]
    return moment(quote, dt.astimezone(MANILA).isoformat(), 'datetime', 'Asia/Manila'), quote


def _typed_dates(body, anchors):
    found = {}
    for field, label in LABELS.items():
        pattern = re.compile(r'\b(?:' + label + r')\s*[:,]?\s*(?=' + DAY + '|' + ISO + ')', re.I)
        for match in pattern.finditer(body):
            value, date_quote = _named_date(body[match.end():], anchors.get(field))
            quote = match[0] + date_quote
            if not value or not value.get('value'):
                raise FetchError('Devpost labelled date has unsupported or missing timezone: ' + quote)
            found.setdefault(field, []).append((value, quote))
    return found


def _same_date(value, anchor):
    if instant(value) and instant(anchor):
        return instant(value) == instant(anchor)
    if value.get('precision') == 'date' and anchor:
        # Compare the organizer's stated calendar day, before Manila conversion.
        raw = anchor.get('raw', '')
        try:
            return value['value'] == datetime.fromisoformat(raw.replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            return value['value'] == anchor.get('value')
    return value.get('value') == (anchor or {}).get('value')


def _eligibility(soup, body):
    node = soup.select_one('#eligibility-list')
    if not node:
        raise FetchError('Devpost primary eligibility list is unavailable')
    items = []
    worldwide, philippines = False, False
    for item in node.select('li'):
        text = item.get_text(' ', strip=True)
        tips = [n.get('title', '').strip() for n in item.select('[data-tooltip][title]')]
        countries = ', '.join(tips)
        if re.search(r'All countries/territories', text, re.I):
            if re.search(r'excluding|except', text, re.I):
                if not countries:
                    raise FetchError('Devpost country exceptions are not readable; Philippine eligibility is unverified')
                if re.search(r'\bPhilippines\b', countries, re.I):
                    return None, 'Primary eligibility excludes the Philippines: ' + text + ' (' + countries + ')'
            worldwide = True
        elif re.search(r'Only specific.*countries/territories included', text, re.I):
            philippines = bool(re.search(r'\bPhilippines\b', countries, re.I))
        items.append(text + (' (' + countries + ')' if countries else ''))
    # Organizer prose can narrow a platform's broad default country list.
    local = re.search(r'\b(?:for|open to)\s+[^.!?\n]{0,70}\bstudents?\b[^.!?\n]{0,35}\b(?:studying|residing|living|based)\s+in\s+[^.!?\n]+', body, re.I)
    excluded = re.search(r'[^.!?\n]*(?:Philippines|Filipinos?)[^.!?\n]*(?:excluded|ineligible|not eligible|not permitted)|'
                         r'[^.!?\n]*(?:not open to|excludes?)\b[^.!?\n]*(?:Philippines|Filipinos?)', body, re.I)
    only = re.search(r'\b(?:only (?:open|available) to|limited to (?:residents?|citizens?) of|[A-Za-z]+ (?:residents?|citizens?) only)\b[^.!?\n]*', body, re.I)
    residence = re.search(r'\b(?:participants?|applicants?|entrants?)\s+(?:must|have to|are required to)\s+'
                          r'(?:reside|live|be (?:based|residents?|citizens?))\s+(?:in|of)\s+[^.!?\n]+', body, re.I)
    institution = re.search(r'\b(?:must|have to|are required to)\s+be\s+(?:currently\s+)?enrolled at\s+(?!a\b|an\b|any\b)[^.!?\n]+', body, re.I)
    conflicts = [match for match in (local, only, residence, institution) if match and not re.search(r'Philippin|Filipino', match[0], re.I)]
    if excluded or conflicts:
        reason = (excluded or conflicts[0])[0]
        return None, 'Primary body restricts participation despite the platform country list: ' + reason
    if not worldwide and not philippines:
        return None, 'Primary country eligibility does not establish participation from the Philippines'
    terms = [line.strip() for line in body.splitlines() if re.search(
        r'\b(?:event|hackathon|competition|participation) (?:is )?(?:open to|for|designed for)|'
        r'^\s*(?:open to|only .+ (?:may|can) participate|(?:all )?(?:participants?|applicants?|entrants?) must (?:be|reside|live|attend|have reached))', line, re.I)]
    # Keep platform and body audience conditions together. A contradictory
    # minimum age cannot be silently resolved in favour of either source.
    platform = '; '.join(items)
    minimum = re.search(r'\bAges?\s+(\d+)', platform, re.I)
    for term in terms:
        ages = [int(n) for n in re.findall(r'\b(?:aged?|ages?)\s+(\d+)', term, re.I)]
        if ages and ((re.search(r'legal age of majority', platform, re.I) and min(ages) < 18)
                     or (minimum and min(ages) < int(minimum[1]))):
            return None, 'Conflicting primary age eligibility: ' + platform + ' | ' + term
    return '; '.join(dict.fromkeys([*items, *terms])), None


def parse_event(raw, url, source, now):
    """Return the normal announcement contract; window filtering stays upstream."""
    url = _root(url)
    if not url:
        return None, 'Not a supported Devpost primary overview URL'
    soup = BeautifulSoup(raw, 'html.parser')
    nodes = [n for n in _events(soup) if _root(n.get('url')) == url]
    if len(nodes) != 1:
        raise FetchError('A unique Devpost primary Event record matching this URL is unavailable')
    data = nodes[0]
    title = BeautifulSoup(data.get('name') or '', 'html.parser').get_text(' ', strip=True)
    if not title or not any(norm(h.get_text(' ', strip=True)) == norm(title) for h in soup.select('h1')):
        raise FetchError('Devpost event identity is not corroborated by a matching visible heading')
    organizer = data.get('organizer') or {}
    if not isinstance(organizer, dict) or not organizer.get('name'):
        raise FetchError('Devpost primary organizer identity is unavailable')
    name = BeautifulSoup(organizer['name'], 'html.parser').get_text(' ', strip=True)
    if not name:
        raise FetchError('Devpost primary organizer name is unreadable')
    mode = str(data.get('eventAttendanceMode', '')).rsplit('/', 1)[-1]
    if not mode:
        raise FetchError('Devpost attendance format is not explicitly stated')
    if mode != 'OnlineEventAttendanceMode':
        return None, 'Devpost event is not explicitly online; Philippine onsite scope is unverified'
    articles = soup.select('article#challenge-description, article#challenge-requirements')
    if not articles:
        raise FetchError('Devpost organizer description and requirements are unreadable')
    for article in articles:
        for node in article.select('script,style,nav,footer,aside,[hidden],[aria-hidden="true"]'):
            node.decompose()
    body = '\n'.join(n.get_text(' ', strip=True) for article in articles for n in article.select('p,li,h2,h3,h4'))
    if not body:
        body = '\n'.join(n.get_text(' ', strip=True) for n in articles)
    eligibility, reason = _eligibility(soup, body)
    if not eligibility:
        return None, reason
    topic, topic_quote = community_topic(title, body)
    if not topic:
        return None, 'Primary Devpost text does not establish an AI, cybersecurity or general IT topic'
    start = manila_moment(data.get('startDate'))
    end = manila_moment(data.get('endDate'))
    if not start.get('value') or not end.get('value'):
        raise FetchError('Devpost primary schedule is missing an explicit date or timezone')
    if ((instant(start) and instant(end) and instant(end) < instant(start))
            or (manila_day(start) and manila_day(end) and manila_day(end) < manila_day(start))):
        return None, 'Devpost primary end precedes its start'
    sidebar = soup.select_one('#challenge-information [data-dates-text][data-iso-date]')
    sidebar_date = manila_moment(sidebar.get('data-iso-date')) if sidebar and re.match(r'Deadline:', sidebar.get_text(' ', strip=True), re.I) else None
    if sidebar_date and not instant(sidebar_date):
        raise FetchError('Devpost sidebar deadline lacks an explicit timezone')
    if sidebar_date:
        display = re.sub(r'^Deadline:\s*', '', sidebar.get_text(' ', strip=True), flags=re.I)
        displayed, quote = _named_date(display, sidebar_date)
        if not displayed or not _same_date(displayed, sidebar_date):
            return None, 'Conflicting primary sidebar display and numeric date: ' + display + ' | data-iso-date=' + sidebar['data-iso-date']
    if sidebar_date and not _same_date(sidebar_date, end):
        return None, 'Conflicting primary Devpost sidebar and Event end: ' + sidebar.get_text(' ', strip=True) + ' | endDate=' + str(data.get('endDate'))
    typed = _typed_dates(body, {'start': start, 'submission_deadline': sidebar_date})
    dates, date_proof = {}, {}
    for field, entries in typed.items():
        anchor = start if field == 'start' else sidebar_date if field == 'submission_deadline' else None
        values = [value for value, _ in entries]
        chosen = anchor or next((value for value in values if instant(value)), values[0])
        if any(not _same_date(value, chosen) for value in values):
            quote = ' | '.join(q for _, q in entries)
            if anchor:
                quote += ' | ' + ('startDate=' + str(data.get('startDate')) if field == 'start' else sidebar.get_text(' ', strip=True) + '; data-iso-date=' + sidebar['data-iso-date'])
            return None, 'Conflicting primary ' + field + ': ' + quote
        dates[field] = chosen
        date_proof[field] = ' | '.join(dict.fromkeys(q for _, q in entries))
        if anchor:
            date_proof[field] += ' | ' + ('startDate=' + str(data.get('startDate')) if field == 'start' else sidebar.get_text(' ', strip=True) + '; data-iso-date=' + sidebar['data-iso-date'])
    identifiers, actions = set(), []
    for a in soup.select('a[href]'):
        target = canonical_url(urljoin(url, a['href']))
        if not target or urlsplit(target).hostname != urlsplit(url).hostname or urlsplit(target).path.rstrip('/') != '/register':
            continue
        query = parse_qs(urlsplit(target).query)
        ids = query.get('flow[data][challenge_id]', [])
        if len(ids) == 1 and ids[0].isdigit() and query.get('flow[name]') == ['register_for_challenge']:
            identifiers.add(ids[0])
            label = a.get_text(' ', strip=True)
            if re.fullmatch(r'Join hackathon|Register(?: now)?', label, re.I):
                enabled = not a.has_attr('disabled') and a.get('aria-disabled') != 'true' and 'disabled' not in a.get('class', [])
                hidden = (a.has_attr('hidden') or a.get('aria-hidden') == 'true' or 'hidden' in a.get('class', [])
                          or a.find_parent(attrs={'hidden': True}) or a.find_parent(attrs={'aria-hidden': 'true'})
                          or a.find_parent(['nav', 'footer', 'aside']))
                actions.append((target, label, bool(enabled and not hidden)))
    if len(identifiers) != 1:
        raise FetchError('Devpost edition identifier is absent or ambiguous on event registration links')
    identifier = next(iter(identifiers))
    active = next((item for item in actions if item[2]), None)
    state, state_quote = ('open', 'Enabled event Join hackathon control') if active else ('unknown', None)
    closed = re.search(r'\b(?:hackathon registration|registration) (?:is )?(?:now )?closed\b', body, re.I)
    if closed:
        state, state_quote = 'closed', closed[0]
    if instant(dates.get('deadline')) and instant(dates['deadline']) <= now:
        state, state_quote = 'closed', date_proof['deadline']
    if instant(dates.get('registration_opens')) and instant(dates['registration_opens']) > now:
        state, state_quote = 'not_yet_open', date_proof['registration_opens']
    approval = re.search(r'\b(?:Applications? requires? organizer approval|organizer approval (?:is )?required|registration requires approval)\b', body, re.I)
    waitlist = re.search(r'\b(?:Applicants? (?:are|will be) placed on (?:a|the) waitlist|join (?:the )?waitlist)\b', body, re.I)
    if state == 'open' and (waitlist or approval):
        state, state_quote = ('waitlisted', waitlist[0]) if waitlist else ('approval_required', approval[0])
    price, price_quote = {'kind': 'unknown'}, None
    for statement in re.finditer(r'([^.!?\n]+)([.!?]?)', body):
        sentence = statement[1]
        # Keep the terminator until after classification: a FAQ question such
        # as "Is it free to participate?" is not an affirmative price claim.
        if statement[2] == '?':
            continue
        if re.search(r'\b(?:not|only|if|unless|except|members?|alumni)\b|\bfor (?!everyone\b|anyone\b|all participants\b)', sentence, re.I):
            continue
        free = re.search(r'\b(?:participation is free|registration is free|free to (?:join|participate|enter)|(?:Cost|Entry fee|Registration fee):?\s*Free)\b', sentence, re.I)
        if free:
            price, price_quote = {'kind': 'free', 'amount': 0}, sentence.strip()
            break
    fee_pattern = re.compile(r'\b(?:Registration|Entry|Participation) fee\s*:\s*(USD|PHP|EUR|GBP|\$|₱)\s*'
                             r'((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\d,]|\.\d)', re.I)
    fees = [(match, line) for line in body.splitlines() for match in fee_pattern.finditer(line)
            if not re.search(r'\b(?:no|not|waived)\b', line[:match.start()], re.I)
            and float(match[2].replace(',', '')) > 0]
    if fees:
        price = {'kind': 'paid'}
        prices = {(match[1].upper(), float(match[2].replace(',', ''))) for match, _ in fees}
        conditional = any(re.search(r'\b(?:for|only|if|unless|members?|students?|alumni|early|late)\b', line, re.I) for _, line in fees)
        if len(prices) == 1 and not conditional:
            currency, amount = next(iter(prices))
            price['amount'] = amount
            if currency in ('USD', 'PHP', 'EUR', 'GBP'):
                price['currency'] = currency
        price_quote = ' | '.join(dict.fromkeys(line for _, line in fees))
    account = re.search(r'[^\n.!?]*(?:must (?:have|create) (?:a )?Devpost account|Devpost account (?:is )?required|log in to (?:join|register))[^\n.!?]*', body, re.I)
    if account and re.search(r'\b(?:not|no|unless|if)\b', account[0], re.I):
        account = None
    facts = {'name': title, 'organizer': name, 'geography': 'international_online', 'region': 'International online',
             'topic': topic, 'format': 'online', 'attendance_options': ['Online'],
             'start': start, 'end': end, 'competition_date': None, 'deadline': None,
             'submission_deadline': None, 'registration_opens': None, **dates,
             'eligibility': eligibility, 'price': price, 'registration_state': state,
             'registration_url': active[0] if active else None, 'account_required': True if account else None,
             'organizer_event_url': url, 'summary': None,
             'lifecycle': None}
    proof = {}
    def cite(field, quote, **extra):
        proof[field] = {'url': url, 'quote': quote[:1200], **extra}
    cite('name', 'Visible heading and Event name: ' + title)
    cite('edition', 'Event register_for_challenge challenge_id=' + identifier)
    cite('organizer', 'Primary Event organizer.name=' + name)
    cite('organizer_event_url', 'Primary Event url=' + url)
    cite('geography', eligibility)
    cite('eligibility', eligibility)
    cite('region', eligibility)
    cite('format', 'Primary Event eventAttendanceMode=' + mode)
    cite('attendance_options', 'Primary Event eventAttendanceMode=' + mode)
    cite('topic', topic_quote)
    retain_description(facts, proof, body, url)
    cite('start', 'Primary Event startDate=' + str(data.get('startDate')))
    cite('end', 'Primary Event endDate=' + str(data.get('endDate')))
    for field, quote in date_proof.items():
        cite(field, quote)
    if active:
        cite('registration_url', active[1] + ': ' + active[0])
    if state_quote:
        cite('registration_state', state_quote, **({'basis': 'live_registration_widget'} if state in ('open', 'approval_required', 'waitlisted') else {}))
    if price_quote:
        cite('price', price_quote)
    if account:
        cite('account_required', account[0])
    lifecycle = str(data.get('eventStatus', '')).rsplit('/', 1)[-1]
    if lifecycle in ('EventCancelled', 'EventPostponed'):
        facts['lifecycle'] = 'cancelled' if lifecycle == 'EventCancelled' else 'postponed'
        cite('lifecycle', 'Primary Event eventStatus=' + lifecycle)
    return {'url': url, 'external_id': 'devpost:' + identifier, 'title': title, 'posted_at': None,
            'access': 'full', 'official': True, 'kind': 'registration' if state in ('open', 'approval_required', 'waitlisted') else 'announcement',
            'identity': {'organizer_key': 'devpost:' + norm(name), 'series': 'Devpost hackathon',
                         'edition': identifier, 'region': 'International online', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof, 'publisher_leads': [],
            'discovery_path': list(dict.fromkeys([source.get('url', url), url]))}, 'Verified primary Devpost edition and eligibility; typed cutoffs kept separate'
