"""Luma's public subscription and public page monitor; no authenticated APIs.

The documented city subscription is discovery-only. Detail pages supply body,
public hosts and ticket state; calendar DTSTAMP/STATUS are not event publication
or registration evidence. Feed disappearance never withdraws an announcement.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .domain import MANILA, canonical_url, in_window, instant, moment, parse_moment, region_from
from .extract import CTF, extract
from .event_text import retain_description
from .network import FetchError, RateLimited

LUMA_HOSTS = ('luma.com', 'lu.ma')
SECURITY = re.compile(r'cyber\s*security|cybersecurity|ethical hacking|hacking|penetration testing|digital forensics|reverse engineering|web exploitation|\bpwn\b|\bOSINT\b|cryptography|security (?:skills|challenges|competition)', re.I)
COMPONENT = re.compile(r'\b(?:conference|summit|festival|meetup|hackathon)\b', re.I)
TEACHING = re.compile(r'\b(?:workshops?|training|tutorials?|lessons?|learn(?:ing)?|teach(?:ing|es)?|practi[cs]e|prepar(?:e|ation|ing)|walkthroughs?|class(?:es)?|courses?|lectures?|seminars?|discuss(?:ion|ions|es)?|demonstrat(?:e|es|ion|ions)|study|introduction|talks?|guided|labs?|exercises?)\b', re.I)
CTF_DECLARATION = re.compile(r'\b(?:a|an|is|presents?|includes?|features?|featuring|hosts?)\s+(?:[\w&+/-]+\s+){0,7}(?:capture[\s-]+the[\s-]+flag|CTF)\b', re.I)
PARTICIPATION = re.compile(r'\b(?:participants?|players?|teams?|competitors?|attendees?)\b[^.!?\n]{0,180}\b(?:challenges?|flags?|puzzles?)\b', re.I)
AI_TOPIC = re.compile(r'\bAI\b|artificial intelligence|machine learning|large language models?|\bLLMs?\b', re.I)
IT_TOPIC = re.compile(r'\b(?:software (?:development|engineering)|web development|cloud computing|computer programming|information technology|developer conference|technology conference|DevFest|Google I/O|AWS|Google Cloud|Kubernetes|DevOps|Python|JavaScript|Ruby|Rails|PHP|Magento|agile|scrum|open source|embedded systems|operating systems|chaos engineering|site reliability engineering|data engineering)\b', re.I)
WORLDWIDE = re.compile(r'\b(?:(?:open|available|accessible)\s+(?:to\s+(?:\w+\s+){0,5})?(?:worldwide|all countries|any country)|(?:participants?|students?|developers?|builders?|attendees?|teams?|people|anyone|everyone)\s+(?:from\s+)?(?:worldwide|all countries|any country|around the world|anywhere(?: in the world)?)|(?:join|participate|attend|register|compete)\s+(?:online\s+)?from\s+(?:anywhere(?: in the world)?|any country))\b', re.I)


def worldwide_participation(description):
    """Explicit audience access, not global speakers or negated availability."""
    if re.search(r'\b(?:only|restricted to|limited to)\b[^.!?\n]{0,100}\b(?:residents?|citizens?)\b|\b(?:residents?|citizens?)\b[^.!?\n]{0,100}\bonly\b|\b(?:must|need to) (?:live|reside)\b', description, re.I):
        return None
    for sentence in re.split(r'(?<=[.!?])\s+|\n', description):
        found = WORLDWIDE.search(sentence)
        if found and not re.search(r"\b(?:not|except|excluding|restricted|cannot)\b|can't|isn't|aren't", sentence, re.I):
            return found
    return None


def community_topic(title, description):
    """Classify the announced subject, excluding trailing partner/host lists."""
    narrative = re.split(r'(?im)^\s*(?:co[- ]organi[sz]ers?|organi[sz]ers?|hosts?|sponsors?|partners?)\s*:', description)[0]
    for text in (title, narrative):
        for topic, pattern in (('ai', AI_TOPIC), ('cybersecurity', SECURITY), ('general_it', IT_TOPIC)):
            found = pattern.search(text)
            if found:
                line = next((line.strip() for line in text.splitlines() if pattern.search(line)), found[0])
                return topic, line[:600]
    return None, None


def competition_evidence(title, description):
    """Distinguish announced play from teaching about CTF techniques.

    Some publishers explicitly call the activity a Capture the Flag event and
    describe attendee challenges, without repeating the word competition. That
    supports the CTF's existence, but does not establish that the calendar slot
    or its registration widget is the complete competition window.
    """
    # Relationship lists are metadata, not instructional framing: a sponsor's
    # display name can itself contain words such as "Tutorials" or "Training".
    narrative = re.split(r'(?im)^\s*(?:co[- ]organi[sz]ers?|organi[sz]ers?|hosts?|sponsors?|partners?)\s*:', description)[0]
    combined = title + '\n' + narrative
    if not SECURITY.search(combined):
        return None, None
    explicit = re.compile(
        r'(?:CTF|capture[ -]the[ -]flag)[^.!?\n]{0,100}\b(?:competition|tournament|contest|compete|leaderboard|scoreboard|prizes)\b|\b(?:competition|tournament|contest)\b[^.!?\n]{0,100}(?:CTF|capture[ -]the[ -]flag)', re.I)
    for sentence in re.split(r'[.!?\n]', combined):
        found = explicit.search(sentence)
        if not found:
            continue
        # A lesson about competition techniques is still only a lesson. An
        # explicitly separate competition alongside training may qualify.
        teaching_before = TEACHING.search(sentence[:found.start()])
        teaching_subject = re.match(r'\s*(?:techniques|skills|strategies|workshop|training|tutorial|lesson)\b', sentence[found.end():], re.I)
        if teaching_subject or (teaching_before and not re.search(
                r'\b(?:features?|featuring|includes?|alongside|followed by|follows?)\b', sentence, re.I)):
            continue
        if re.search(r'\b(?:no|not|without)\b[^.!?]{0,35}(?:CTF|capture[ -]the[ -]flag|competition)', sentence, re.I):
            continue
        return found[0], 'explicit_competition'
    if TEACHING.search(combined):
        return None, None
    participation = PARTICIPATION.search(narrative)
    if not participation:
        return None, None
    for sentence in re.split(r'[.!?\n]', narrative):
        declaration = CTF_DECLARATION.search(sentence)
        if declaration and re.search(r'\b(?:events?|activities|activity|games?|tracks?|sessions?)\b', sentence, re.I):
            if re.search(r'\b(?:no|not|without|cancelled|canceled)\b', sentence, re.I):
                continue
            return sentence.strip() + ' | ' + participation[0], 'declared_ctf_activity'
    return None, None


def page_data(raw, kind):
    soup = BeautifulSoup(raw, 'html.parser')
    node = soup.select_one('script#__NEXT_DATA__')
    try:
        data = json.loads(node.string or node.get_text())['props']['pageProps']['initialData']
        if data['kind'] != kind or not isinstance(data['data'], dict):
            raise ValueError('Unexpected Luma page kind')
        return data['data']
    except (TypeError, KeyError, ValueError, AttributeError):
        raise FetchError('Public Luma page schema unavailable') from None


def event_url(value):
    if not isinstance(value, str) or not value:
        return None
    url = canonical_url(urljoin('https://luma.com/', value))
    if not url:
        return None
    p = urlsplit(url)
    if p.hostname not in LUMA_HOSTS or not re.fullmatch(r'/[A-Za-z0-9_-]+/?', p.path):
        return None
    return 'https://luma.com/' + p.path.strip('/')


def subscription_links(raw):
    """Unfold only the URL-bearing ICS fields; never interpret ICS as full facts."""
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw
    if 'BEGIN:VCALENDAR' not in text or 'END:VCALENDAR' not in text:
        raise FetchError('Luma subscription did not return a valid calendar')
    text = re.sub(r'\r?\n[ \t]', '', text)
    urls = []
    entries = re.findall(r'BEGIN:VEVENT\r?\n(.*?)END:VEVENT', text, re.S)
    for entry in entries:
        for line in entry.splitlines():
            if line.startswith(('DESCRIPTION:', 'URL:')):
                line = line.replace(r'\n', '\n').replace(r'\,', ',')
                # Luma's DESCRIPTION begins with the public event link. Later
                # links can identify sponsors/calendars, not another event.
                for found in re.findall(r'https?://(?:luma\.com|lu\.ma)/[A-Za-z0-9_-]+(?:\?[^\s\\]*)?', line):
                    url = event_url(found)
                    if url and url not in urls:
                        urls.append(url)
                    if url:
                        break
    return urls, len(entries)


def rich_description(node):
    """Keep description text and its own links; exclude guest lists/page footers."""
    if isinstance(node, str):
        return node, []
    if not isinstance(node, dict):
        return '', []
    if node.get('type') in ('hard_break', 'hardBreak'):
        return '\n', []
    if node.get('type') == 'text':
        text = node.get('text', '')
        links = [(text, mark.get('attrs', {}).get('href')) for mark in node.get('marks', [])
                 if mark.get('type') == 'link' and mark.get('attrs', {}).get('href')]
        return text, links
    texts, links = [], []
    for child in node.get('content', []):
        text, found = rich_description(child)
        texts.append(text)
        links.extend(found)
    sep = '\n' if node.get('type') in ('doc', 'bullet_list', 'ordered_list', 'list_item') else ''
    return sep.join(texts), links


def public_host(host, announcement_url):
    account = host.get('api_id')
    name = host.get('name')
    if not name or not account or not re.fullmatch(r'usr-[A-Za-z0-9_-]+', account):
        return None
    # The stable account URL works when a display username is changed.
    return {'name': name, 'role': 'host', 'url': f'https://luma.com/user/{account}',
            'account_id': 'luma:' + account,
            'evidence': {'url': announcement_url, 'quote': f'Luma public hosts: {name} ({account})'}}


def registration_state(data, now):
    event = data.get('event', {})
    end = parse_moment(event.get('end_at') or '')
    if end.get('value') and end.get('precision') == 'datetime':
        if datetime.fromisoformat(end['value']) <= now:
            return 'closed', 'Confirmed competition end has passed: ' + event['end_at']
    available = data.get('registration_availability')
    if available in ('closed', 'ended', 'sold_out', 'sold-out', 'not_accepting'):
        if data.get('waitlist_active') is True:
            return 'waitlisted', 'Luma waitlist_active=true'
        return 'closed', 'Luma registration_availability=' + available
    if data.get('waitlist_active') is True or available in ('waitlist', 'waitlisted'):
        return 'waitlisted', 'Luma waitlist_active=true or registration_availability=' + str(available)
    if available == 'open':
        if (data.get('ticket_info') or {}).get('require_approval') is True:
            return 'approval_required', 'Luma registration_availability=open; ticket_info.require_approval=true'
        approval = (data.get('ticket_info') or {}).get('require_approval')
        if approval is False:
            return 'open', 'Luma registration_availability=open; ticket_info.require_approval=false'
        return 'unknown', 'Luma registration_availability=open; approval requirement not confirmed'
    return 'unknown', None


def manila_moment(raw):
    value = parse_moment(raw or '')
    dt = instant(value)
    return moment(raw, dt.astimezone(MANILA).isoformat(), 'datetime', 'Asia/Manila') if dt else value


def community_tickets(data, raw, now):
    """Public application routes are separate from fellow/member entitlements.

    Platform `type=free` / `is_free` defaults with null monetary values are not
    an organizer price statement. Nor is a ticket validity bound a sales cutoff.
    """
    soup = BeautifulSoup(raw, 'html.parser')
    control = any(
        re.fullmatch(r'Request to Join|Request to Register|Register', node.get_text(' ', strip=True) or node.get('value', ''), re.I)
        and not node.has_attr('disabled') and node.get('aria-disabled') != 'true'
        for node in soup.select('button, input[type="submit"]'))
    tickets = []
    for ticket in data.get('ticket_types', []):
        if ticket.get('is_hidden') or not ticket.get('name'):
            continue
        name, description = ticket['name'], ticket.get('description') or ''
        restricted = bool(ticket.get('membership_restriction') or ticket.get('ethereum_token_requirements')
                          or re.search(r'\b(?:fellows?|members?|alumni|staff|invite[- ]only)\b', name, re.I)
                          or re.search(r'\b(?:fellows?|members?|alumni|staff|completed|completion of|restricted to|reserved for)\b|\bmust (?:be|have)\b|\b(?:students?|graduates?|invitees?) only\b|\bonly (?:students?|graduates?|invitees?)\b', description, re.I))
        access = 'restricted' if restricted else 'public' if re.match(r'(?:Standard|General Admission|Public)\b', name, re.I) else 'unknown'
        attendance = 'online' if re.search(r'\bonline\b', name, re.I) else 'onsite' if re.search(r'\bon[- ]?site\b', name, re.I) else None
        cents = ticket.get('cents')
        price = {'kind': 'unknown'}
        if isinstance(cents, (int, float)) and not isinstance(cents, bool) and cents >= 0:
            price = {'kind': 'free' if cents == 0 else 'paid', 'amount': cents / 100}
            if ticket.get('currency'):
                price['currency'] = ticket['currency'].upper()
        state, _ = registration_state({**data, 'ticket_info': {'require_approval': ticket.get('require_approval')}}, now)
        deadline = manila_moment(ticket['end_at']) if ticket.get('end_at') else None
        starts = instant(manila_moment(ticket.get('start_at')))
        ends = instant(deadline)
        if ticket.get('is_disabled') or ticket.get('spots_remaining') == 0 or (ends and ends <= now):
            state = 'closed'
        elif starts and starts > now:
            state = 'not_yet_open'
        elif state in ('open', 'approval_required') and not control:
            state = 'unknown'
        tickets.append({'name': name, 'access': access, 'attendance': attendance,
                        'eligibility': description or ('Membership or restricted-ticket requirements apply.' if restricted else None),
                        'registration_state': state, 'price': price, 'deadline': deadline})
    public = [ticket for ticket in tickets if ticket['access'] == 'public']
    active = [ticket for ticket in public if ticket['registration_state'] in ('open', 'approval_required')]
    # An unrestricted route must be evidenced; restricted-only offers cannot
    # make the card actionable for a general student audience.
    states = {ticket['registration_state'] for ticket in active or public}
    state = next(iter(states)) if len(states) == 1 else 'unknown'
    prices = [ticket['price'] for ticket in public]
    price = prices[0] if prices and all(p == prices[0] for p in prices) else {'kind': 'unknown'}
    deadlines = [ticket['deadline'] for ticket in public]
    deadline = deadlines[0] if deadlines and all(d == deadlines[0] for d in deadlines) else None
    return tickets, state, price, deadline


def parse_community_event(raw, data, url, source, now):
    """Opt-in community events on public Luma organizer calendars, not a CTF bypass."""
    event, calendar = data.get('event') or {}, data.get('calendar') or {}
    title = event.get('name') or ''
    description, _ = rich_description(data.get('description_mirror'))
    topic, topic_quote = community_topic(title, description)
    generic = source.get('topic') == 'community'
    if not generic and (source.get('topic') != 'ai' or not re.search(r'\bAI\b|artificial intelligence', title + '\n' + description, re.I)):
        return None, 'No configured AI topic evidence in title or description'
    if generic and not topic:
        return None, 'No supported event topic in the primary title or description'
    if not generic:
        topic = 'ai'
        topic_quote = next((line.strip() for line in (title + '\n' + description).splitlines()
                            if re.search(r'\bAI\b|artificial intelligence', line, re.I)), title)
    calendar_id = source.get('_calendar_id')
    if (not calendar_id or calendar.get('api_id') != calendar_id or event.get('calendar_api_id') != calendar_id
            or not calendar.get('name') or not re.fullmatch(r'evt-[A-Za-z0-9_-]+', event.get('api_id') or '')):
        return None, 'Event ownership by the discovered organizer calendar is unconfirmed'
    address = event.get('geo_address_info') or {}
    ph_venue = address.get('country_code') == 'PH' or address.get('country') == 'Philippines'
    worldwide = worldwide_participation(description)
    international_online = (generic and not ph_venue and event.get('location_type') in ('online', 'virtual', 'meet') and worldwide)
    if not ph_venue and not international_online:
        return None, 'No confirmed Philippine venue; calendar membership alone is insufficient'
    if generic and ph_venue and topic == 'cybersecurity':
        return None, 'Philippine cybersecurity events require the separate competition verifier'
    tickets, state, price, deadline = community_tickets(data, raw, now)
    public = [t for t in tickets if t['access'] == 'public']
    attendance = {t['attendance'] for t in public if t['attendance']}
    physical = event.get('location_type') == 'offline'
    if physical and attendance == {'online', 'onsite'}:
        mode = 'hybrid'
    elif attendance == {'online'}:
        mode = 'online'
    elif physical and attendance == {'onsite'}:
        mode = 'in_person'
    else:
        mode = 'in_person' if physical else 'online' if event.get('location_type') in ('online', 'virtual', 'meet') else 'unknown'
    city = address.get('city') or address.get('region') or 'Philippines'
    options = ([f'Onsite — {city}'] if 'onsite' in attendance else []) + (['Online'] if 'online' in attendance else [])
    eligibility = ('Standard public tickets are available; organizer approval required.' if state == 'approval_required'
                   else 'Public ticket options are listed; check their current availability.') if public else 'Public student eligibility is unconfirmed.'
    if any(t['access'] == 'restricted' for t in tickets):
        eligibility += ' Restricted ticket requirements apply only to their named tickets.'
    start, end = manila_moment(event.get('start_at')), manila_moment(event.get('end_at'))
    if instant(start) and instant(end) and instant(end) < instant(start):
        raise FetchError('Conflicting Luma event schedule; end precedes start')
    facts = {'name': title, 'organizer': calendar['name'], 'geography': 'PH' if ph_venue else 'international_online', 'topic': topic,
             'region': region_from(' '.join(str(x) for x in address.values()), 'Philippines') if ph_venue else 'International online',
             'format': mode, 'attendance_options': options, 'ticket_options': tickets,
             'start': start if start.get('value') else None, 'end': end if end.get('value') else None,
             'competition_date': None, 'deadline': deadline, 'submission_deadline': None,
             'registration_opens': None, 'registration_state': state, 'registration_url': url,
             'organizer_event_url': url, 'eligibility': eligibility, 'price': price,
             'account_required': None, 'summary': None, 'lifecycle': None}
    proof = {}
    def cite(field, quote, evidence_url=url):
        proof[field] = {'url': evidence_url, 'quote': quote[:600]}
    cite('name', title)
    cite('organizer', f"Luma presenting calendar: {calendar['name']} ({calendar_id})")
    cite('organizer_event_url', 'Public event page linked from organizer calendar: ' + url, source['url'])
    cite('geography', json.dumps(address, ensure_ascii=False) if ph_venue else 'Luma online location; ' + worldwide[0])
    cite('region', json.dumps(address, ensure_ascii=False) if ph_venue else worldwide[0])
    cite('topic', topic_quote or title + ' | ' + description)
    retain_description(facts, proof, description, url)
    for field, key in [('start', 'start_at'), ('end', 'end_at')]:
        if facts[field]:
            cite(field, f'Luma event.{key}={event[key]}; timezone={event.get("timezone")}')
    ticket_proof = '; '.join(f"{t['name']} [{t['access']}]: {t['eligibility'] or 'No ticket-specific restriction stated'}" for t in tickets)
    for field in ('ticket_options', 'attendance_options', 'eligibility'):
        cite(field, ticket_proof)
    cite('format', f"Luma location_type={event.get('location_type')}; public ticket options: " + ', '.join(t['name'] for t in public))
    cite('price', 'Public ticket cents: ' + json.dumps([{'name': t.get('name'), 'cents': t.get('cents'), 'currency': t.get('currency')} for t in data.get('ticket_types', []) if t.get('name') in {p['name'] for p in public}]))
    cite('registration_url', 'Organizer public event registration page: ' + url)
    cite('registration_state', 'Luma registration_availability=' + str(data.get('registration_availability')) + '; public tickets: ' + '; '.join(f"{t['name']}: {t['registration_state']}" for t in public))
    if state in ('open', 'approval_required'):
        proof['registration_state']['basis'] = 'live_registration_widget'
    if deadline:
        cite('deadline', 'All public ticket sales end_at=' + deadline['raw'])
    hosts = [lead for host in data.get('hosts', []) if (lead := public_host(host, url))]
    return {'url': url, 'external_id': event['api_id'], 'title': title, 'posted_at': None,
            'access': 'full', 'official': True, 'verification_method': 'event_page', 'kind': 'registration' if state in ('open', 'approval_required') else 'announcement',
            'identity': {'organizer_key': 'luma:' + calendar_id, 'series': 'Luma event',
                         'edition': event['api_id'], 'region': 'Philippines' if ph_venue else 'International online', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof, 'publisher_leads': hosts,
            'discovery_path': [source['url'], url]}, 'Verified community event from its public organizer calendar'


def parse_event(raw, url, source, now):
    data = page_data(raw, 'event')
    if source.get('event_scope') == 'community':
        return parse_community_event(raw, data, url, source, now)
    event = data.get('event') or {}
    title = event.get('name') or ''
    description, links = rich_description(data.get('description_mirror'))
    combined = title + '\n' + description
    if not CTF.search(combined) or not SECURITY.search(combined):
        return None, 'No actual cybersecurity CTF evidence in title and description'
    competitive, recognition = competition_evidence(title, description)
    if not competitive:
        return None, 'CTF topic or workshop without competition evidence'
    address = event.get('geo_address_info') or {}
    ph_venue = address.get('country_code') == 'PH' or address.get('country') == 'Philippines'
    ph_host = re.search(r'\b(?:organized|organised|hosted) by[^\n.!?]{0,150}(?:Philippines|Philippine|Filipino)', description, re.I)
    if not ph_venue and not ph_host:
        return None, 'No confirmed Philippine venue or Philippine organizer; city membership alone is insufficient'
    hosts = [lead for host in data.get('hosts', []) if (lead := public_host(host, url))]
    organizer = ', '.join(lead['name'] for lead in hosts) or 'Organizer not confirmed'
    organizer_key = '|'.join(sorted(lead['account_id'] for lead in hosts)) or 'unconfirmed'
    start = parse_moment(event.get('start_at') or '')
    calendar_date = start.get('value') if start.get('precision') == 'date' else None
    if start.get('precision') == 'datetime':
        calendar_start = datetime.fromisoformat(start['value'])
        # Edition identity follows the organizer's calendar date, not the UTC
        # transport date. Keep the original instant in the published facts.
        if event.get('timezone'):
            try:
                calendar_start = calendar_start.astimezone(ZoneInfo(event['timezone']))
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                pass
        calendar_date = calendar_start.date().isoformat()
    year = calendar_date[:4] if calendar_date else None
    if not re.search(r'\b20\d{2}\b', title) and not year:
        return None, 'Competition edition unconfirmed'
    text = description
    if year:
        text += '\nEvent date: ' + calendar_date
    # Body identity still requires an explicit competition. Add no invented text.
    derived = {'id': source['id'], 'name': source['name'], 'url': url, 'kind': 'luma',
               'organizer': organizer, 'organizer_key': organizer_key, 'body_identity': True,
               'region': region_from(' '.join(str(x) for x in address.values()), 'Unspecified')}
    # The generic text extractor may otherwise borrow an earlier historical
    # year mentioned in a CTF-titled article. Supply the confirmed calendar year
    # only as identity context, retaining the publisher's actual title below.
    identity_title = title
    if recognition == 'declared_ctf_activity' and not CTF.search(title):
        # This is a derived listing label, not a fabricated publisher headline.
        identity_title += ' · CTF'
    if year and not re.search(r'\b20\d{2}\b', title):
        identity_title += ' ' + year
    ann = extract(identity_title, text, url, derived, links=links, external_id=event.get('api_id'))
    if not ann:
        return None, 'Competition identity could not be established conservatively'
    facts, proof = ann['facts'], ann['field_evidence']
    retain_description(facts, proof, description, url)
    ann['title'] = title[:240]
    name_quote = title
    if not CTF.search(title):
        name_quote += ' | ' + next((line.strip() for line in description.splitlines() if CTF.search(line)), title)
    proof['name'] = {'url': url, 'quote': name_quote[:600]}
    ann['official'] = True
    ann['recognition'] = recognition
    proof['competition'] = {'url': url, 'quote': competitive[:600]}
    ann['scope_evidence'] = {'url': url, 'quote': json.dumps(address, ensure_ascii=False)[:600] if ph_venue else ph_host[0]}
    proof['philippine_connection'] = dict(ann['scope_evidence'])
    # Calendar context can corroborate a recap's explicitly named event and
    # kickoff date. It is identity evidence, not the complete CTF schedule.
    ann['event_context'] = {
        'kind': 'calendar', 'title': title, 'calendar_date': calendar_date,
        'region': facts.get('region'), 'venue': address,
        'venue_names': [address[key] for key in ('address', 'full_address')
                        if isinstance(address.get(key), str) and address[key]],
        'evidence': {'url': url, 'quote':
            f'Luma title={title}; start_at={event.get("start_at")}; '
            f'timezone={event.get("timezone")}; address={json.dumps(address, ensure_ascii=False)}'},
    }
    if year and ann['identity']['edition'] == year and not re.search(r'\b20\d{2}\b', title):
        proof['edition'] = {'url': url, 'quote': f'Luma start_at={event["start_at"]}; timezone={event.get("timezone") or "unspecified"}; calendar date={calendar_date}'}
    facts['organizer'] = organizer
    if hosts:
        proof['organizer'] = {'url': url, 'quote': '; '.join(lead['evidence']['quote'] for lead in hosts)[:600]}
    else:
        proof.pop('organizer', None)
    facts['format'] = 'in_person' if event.get('location_type') == 'offline' else ('online' if event.get('location_type') in ('online', 'virtual', 'meet') else 'unknown')
    if facts['format'] != 'unknown':
        proof['format'] = {'url': url, 'quote': 'Luma location_type=' + str(event.get('location_type'))}
    # A conference/meetup ticket and schedule do not promise entry into its CTF.
    component = bool(recognition == 'declared_ctf_activity' or COMPONENT.search(combined) or re.search(
        r'\b(?:kick[- ]?off|opening ceremony|awards? ceremony|workshops?|panel sessions?)\b', description, re.I))
    if not component:
        for key, src in [('start', 'start_at'), ('end', 'end_at')]:
            moment = parse_moment(event.get(src) or '')
            if moment.get('precision') in ('datetime', 'date'):
                facts[key] = moment
                proof[key] = {'url': url, 'quote': f'Luma {src}={event[src]}; timezone={event.get("timezone", "unknown")}'}
        if facts.get('start') and facts.get('end'):
            # extract() conservatively creates a Schedule TBA context summary;
            # structured standalone competition times supersede that message.
            facts['summary'] = None
            proof.pop('summary', None)
        state, quote = registration_state(data, now)
        facts['registration_state'] = state
        if quote:
            proof['registration_state'] = {'url': url, 'quote': quote}
            if state in ('open', 'approval_required', 'waitlisted'):
                proof['registration_state']['basis'] = 'live_registration_widget'
        facts['registration_url'] = url
        proof['registration_url'] = {'url': url, 'quote': 'Public competition registration page: ' + url}
        if state in ('open', 'approval_required', 'waitlisted'):
            ann['kind'] = 'registration'
        # Only use an explicit single ticket sales deadline, never competition end.
        tickets = [t for t in data.get('ticket_types', []) if not t.get('is_hidden') and not t.get('is_disabled')]
        if len(tickets) == 1 and tickets[0].get('end_at'):
            facts['deadline'] = parse_moment(tickets[0]['end_at'])
            proof['deadline'] = {'url': url, 'quote': 'Luma ticket sales end_at=' + tickets[0]['end_at']}
    else:
        # Generic Start/End labels in a parent agenda can refer to its doors,
        # keynote or workshop. Keep only explicitly competition-labeled dates.
        for field, key in (('parent_event_start', 'start_at'), ('parent_event_end', 'end_at')):
            value = parse_moment(event.get(key) or '')
            if value.get('precision') in ('datetime', 'date'):
                facts[field] = value
                proof[field] = {'url': url, 'quote': f'Luma {key}={event[key]}; parent event schedule, not complete CTF schedule'}
        for key in ('start', 'end'):
            if not re.search(r'\b(?:CTF|Competition)\s+(?:start|end|date)', proof.get(key, {}).get('quote', ''), re.I):
                facts[key] = None
                proof.pop(key, None)
        # Generic registration prose in a conference body is not CTF-specific.
        for key in ('registration_state', 'registration_url', 'deadline', 'registration_opens'):
            facts[key] = 'unknown' if key == 'registration_state' else None
            proof.pop(key, None)
        facts['summary'] = ('The announcement identifies a CTF activity. Its complete competition schedule and registration window are not confirmed.'
                            if recognition == 'declared_ctf_activity' else
                            'CTF is part of this event. The parent event ticket and schedule do not confirm CTF entry or competition times.')
        proof['summary'] = {'url': url, 'quote': (title + ' | ' + competitive)[:600]}
    ann['publisher_leads'] = hosts
    ann['verification_method'] = 'event_page'
    # Public rich-text role lists can name organizations without linking them.
    # Such leads retain evidence-scoped identity; never invent a website.
    role = None
    for line in description.splitlines():
        line = line.strip()
        heading = re.fullmatch(r'(Hosts?|Co[- ]organi[sz]ers?|Organi[sz]ers?|Sponsors?)\s*:', line, re.I)
        if heading:
            key = heading[1].lower()
            role = 'sponsor' if key.startswith('sponsor') else ('host' if key.startswith('host') else 'co-organizer' if key.startswith('co') else 'organizer')
            continue
        if not role:
            continue
        if not line or len(line) > 120 or re.search(r'[.!?;:]|\b(?:register|tickets?|join|learn)\b', line, re.I):
            role = None
            continue
        lead = {'name': line, 'role': role, 'evidence': {'url': url, 'quote': f'{role}: {line}'}}
        matching_host = next((host for host in hosts if host['name'] == line), None)
        if matching_host:
            lead.update({key: matching_host[key] for key in ('url', 'account_id')})
        ann['publisher_leads'].append(lead)
    # Retain explicitly linked sponsor/partner relations, never all footer links.
    for label, href in links:
        if not label.strip() or not canonical_url(href):
            continue
        match = re.search(r'\b(sponsored by|sponsor|co-organized by|co-organised by|partner(?:ed)? with)\s*[:–—-]?\s*' + re.escape(label.strip()), description, re.I)
        if match:
            role = 'sponsor' if match[1].lower().startswith('sponsor') else ('co-organizer' if match[1].lower().startswith('co-') else 'partner')
            ann['publisher_leads'].append({'name': label.strip(), 'role': role, 'url': canonical_url(href),
                                            'evidence': {'url': url, 'quote': match[0][:600]}})
    unique = {}
    for lead in ann['publisher_leads']:
        unique[(lead.get('account_id') or lead.get('url') or lead['name'], lead['role'])] = lead
    ann['publisher_leads'] = list(unique.values())
    from .adapters import attach_discovery
    return attach_discovery(ann, links, [source['url'], url]), 'Accepted cybersecurity competition with Philippine scope evidence'


def luma(source, client, known, now):
    from .adapters import Result
    result = Result()
    result.route_checks, result.publisher_leads = [], []
    urls, origin = [], source['url']
    routes = [('ical', source['ical_url'])] if source.get('ical_url') else []
    if source.get('page_fallback', True):
        routes.append(('page', source['url']))
    succeeded = False
    for kind, url in routes:
        try:
            raw = client.public_page(url, allowed_hosts=[urlsplit(url).hostname])
            if kind == 'ical':
                urls, count = subscription_links(raw)
                check = {'route': kind, 'url': url, 'status': 'ok', 'entries': count, 'event_links': len(urls)}
            else:
                kind_name = source.get('page_kind', 'discover-place')
                data = page_data(raw, kind_name)
                if kind_name == 'calendar':
                    calendar = data.get('calendar') or {}
                    if not re.fullmatch(r'cal-[A-Za-z0-9_-]+', calendar.get('api_id') or '') or not calendar.get('name'):
                        raise FetchError('Public Luma organizer calendar identity unavailable')
                    source = {**source, '_calendar_id': calendar['api_id']}
                    entries = (data.get('upcoming') or {}).get('entries')
                    total = data.get('upcoming_event_count')
                    if (data.get('upcoming') or {}).get('has_more'):
                        result.warnings.append('Luma organizer calendar is a partial rendered slice; more events are not inspected')
                else:
                    entries = data.get('events')
                    total = (data.get('place') or {}).get('event_count')
                if not isinstance(entries, list) or any(not isinstance(item, dict) or not isinstance(item.get('event'), dict) for item in entries):
                    raise FetchError('Public Luma calendar events schema unavailable')
                urls = list(dict.fromkeys(u for item in entries if (u := event_url(item['event'].get('url')))))
                if len(urls) < len({item['event'].get('url') for item in entries}):
                    raise FetchError('Public Luma calendar contains unreadable event links')
                check = {'route': kind, 'url': url, 'status': 'ok', 'event_links': len(urls), 'reported_event_count': total, 'pagination': 'Public rendered slice only; no undocumented API pagination'}
                if isinstance(total, int) and total > len(urls):
                    result.warnings.append(f'Luma public page returned {len(urls)} of {total} advertised events')
            result.route_checks.append(check)
            succeeded, origin = True, url
            break
        except (FetchError, ValueError, KeyError) as exc:
            status = 'rate_limited' if isinstance(exc, RateLimited) else ('blocked' if '403' in str(exc) or 'robots' in str(exc) else 'error')
            result.route_checks.append({'route': kind, 'url': url, 'status': status, 'error': str(exc)})
            result.warnings.append(f'Luma {kind}: {exc}')
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
                # Do not make a second route request during the provider cooldown.
                break
    if not succeeded:
        result.failed = True
        result.failure_status = result.route_checks[-1]['status'] if result.route_checks else 'error'
        result.message = 'No Luma discovery route succeeded; prior listings preserved.'
        return result
    discovered = list(urls)
    # Retained announcements are rechecked after aging out of the upcoming feed.
    retained = set()
    for row in known:
        if event_url(row['url']):
            retained.add(event_url(row['url']))
        if (url := event_url(row['url'])) and url not in urls:
            urls.append(url)
    result.discovered = len(discovered)
    maximum = source.get('max_items', 60)
    if len(urls) > maximum:
        result.warnings.append(f'Luma detail limit {maximum}; {len(urls) - maximum} links not inspected')
    for url in urls[:maximum]:
        try:
            raw = client.public_page(url, allowed_hosts=list(LUMA_HOSTS))
            ann, reason = parse_event(raw, url, source, now)
            if ann and source.get('window_days') and url not in retained and not any(
                    in_window(ann['facts'].get(field), now, source['window_days'])
                    for field in ('start', 'deadline', 'submission_deadline')):
                ann, reason = None, 'No confirmed start or cutoff inside the 45-day Manila window (date-only boundaries unresolved)'
            result.route_checks.append({'route': 'event', 'url': url, 'status': 'ok'})
            result.decisions.append({'url': url, 'title': page_data(raw, 'event').get('event', {}).get('name'),
                                     'decision': 'accepted' if ann else 'rejected', 'reason': reason})
            if ann:
                ann['discovery_path'] = list(dict.fromkeys([source['url'], origin, url]))
                result.announcements.append(ann)
        except (FetchError, ValueError, KeyError) as exc:
            status = 'rate_limited' if isinstance(exc, RateLimited) else ('blocked' if '403' in str(exc) or 'robots' in str(exc) else 'error')
            result.route_checks.append({'route': 'event', 'url': url, 'status': status, 'error': str(exc)})
            result.decisions.append({'url': url, 'decision': status, 'reason': str(exc)})
            result.warnings.append('Luma event check failed: ' + str(exc))
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
                break
    result.message = f'Public Luma calendar returned {len(discovered)} event links; {len(result.announcements)} qualifying or retained events. Read descriptions before configured topic filtering. No login, cookies, or paid API.'
    return result
