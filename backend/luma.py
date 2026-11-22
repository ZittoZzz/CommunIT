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

from .domain import canonical_url, parse_moment, region_from
from .extract import CTF, extract
from .network import FetchError, RateLimited

LUMA_HOSTS = ('luma.com', 'lu.ma')
SECURITY = re.compile(r'cyber\s*security|cybersecurity|ethical hacking|hacking|penetration testing|digital forensics|reverse engineering|web exploitation|\bpwn\b|\bOSINT\b|cryptography|security (?:skills|challenges|competition)', re.I)
COMPONENT = re.compile(r'\b(?:conference|summit|festival|meetup|hackathon)\b', re.I)
TEACHING = re.compile(r'\b(?:workshops?|training|tutorials?|lessons?|learn(?:ing)?|teach(?:ing|es)?|practi[cs]e|prepar(?:e|ation|ing)|walkthroughs?|class(?:es)?|courses?|lectures?|seminars?|discuss(?:ion|ions|es)?|demonstrat(?:e|es|ion|ions)|study|introduction|talks?|guided|labs?|exercises?)\b', re.I)
CTF_DECLARATION = re.compile(r'\b(?:a|an|is|presents?|includes?|features?|featuring|hosts?)\s+(?:[\w&+/-]+\s+){0,7}(?:capture[\s-]+the[\s-]+flag|CTF)\b', re.I)
PARTICIPATION = re.compile(r'\b(?:participants?|players?|teams?|competitors?|attendees?)\b[^.!?\n]{0,180}\b(?:challenges?|flags?|puzzles?)\b', re.I)


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


def parse_event(raw, url, source, now):
    data = page_data(raw, 'event')
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
                data = page_data(raw, 'discover-place')
                entries = data.get('events')
                if not isinstance(entries, list) or any(not isinstance(item, dict) or not isinstance(item.get('event'), dict) for item in entries):
                    raise FetchError('Public Luma city page events schema unavailable')
                urls = list(dict.fromkeys(u for item in entries if (u := event_url(item['event'].get('url')))))
                total = (data.get('place') or {}).get('event_count')
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
    for row in known:
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
            result.decisions.append({'url': url, 'title': page_data(raw, 'event').get('event', {}).get('name'),
                                     'decision': 'accepted' if ann else 'rejected', 'reason': reason})
            if ann:
                ann['discovery_path'] = list(dict.fromkeys([source['url'], origin, url]))
                result.announcements.append(ann)
        except (FetchError, ValueError, KeyError) as exc:
            status = 'rate_limited' if isinstance(exc, RateLimited) else ('blocked' if '403' in str(exc) else 'error')
            result.decisions.append({'url': url, 'decision': status, 'reason': str(exc)})
            result.warnings.append('Luma event check failed: ' + str(exc))
            if isinstance(exc, RateLimited):
                result.retry_after = exc.retry_after
                break
    result.message = f'Public Luma {result.route_checks[-1]["route"]} returned {len(discovered)} event links; read descriptions before competition filtering. No login, cookies, or paid API.'
    return result
