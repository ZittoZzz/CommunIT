"""Primary public-page verification for the bounded opportunity discovery pilot.

Search titles/snippets never establish facts. Only the supplied primary page
and, for Luma, its actually linked presenting calendar can establish them.
No private, undocumented, or authenticated API is used here.
"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from .domain import canonical_url, instant, manila_day, norm, parse_moment, region_from
from .event_text import audience_statements, retain_description
from .luma import (LUMA_HOSTS, community_topic, event_url, manila_moment,
                   page_data, parse_community_event, public_host, worldwide_participation)
from .network import FetchError


def primary_event_url(url):
    """Known public event URL shapes, stripped only of platform tracking state."""
    if not isinstance(url, str):
        return None
    try:
        url = canonical_url(url)
        if url and urlsplit(url).port not in (None, 80, 443):
            return None
    except ValueError:
        return None
    if not url:
        return None
    p = urlsplit(url)
    if p.hostname in LUMA_HOSTS:
        return event_url(url)
    if p.hostname in ('meetup.com', 'www.meetup.com'):
        found = re.fullmatch(r'/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?([^/]+)/events/(\d+)/?', p.path)
        if found:
            return f'https://www.meetup.com/{found[1]}/events/{found[2]}/'
    if p.hostname == 'gdg.community.dev':
        found = re.fullmatch(r'/events/details/([^/]+)(?:/cohost-[^/]+)?/?', p.path)
        if found:
            return 'https://gdg.community.dev/events/details/' + found[1] + '/'
    if p.hostname and p.hostname.endswith('.devpost.com') and p.hostname not in (
            'www.devpost.com', 'info.devpost.com', 'help.devpost.com', 'blog.devpost.com', 'secure.devpost.com'):
        if p.path in ('/', '/overview', '/rules', '/details'):
            return 'https://' + p.hostname + '/'
    return None


def page_event_links(raw, url, *, external_pages=False):
    """Only actual hub links; event detail recommendations are not discovery."""
    soup = BeautifulSoup(raw, 'html.parser')
    host = urlsplit(url).hostname
    embedded = []
    if host in LUMA_HOSTS:
        try:
            page_data(raw, 'event')
            return []
        except FetchError:
            pass
        # Current category/city pages have a separate public Next.js shape.
        script = soup.select_one('script#__NEXT_DATA__')
        try:
            props = json.loads(script.string or script.get_text())['props']['pageProps']
            if props.get('place') and props.get('categoryPage') and isinstance(props.get('initialEvents'), dict):
                entries = props['initialEvents'].get('entries', [])
                return list(dict.fromkeys(event_url(e.get('event', {}).get('url')) for e in entries
                                          if event_url(e.get('event', {}).get('url'))))
        except (TypeError, ValueError, KeyError, AttributeError):
            pass
        for kind in ('calendar', 'discover-place'):
            try:
                data = page_data(raw, kind)
            except FetchError:
                continue
            upcoming = data.get('upcoming') or {}
            if kind == 'calendar' and not isinstance(upcoming, dict):
                raise FetchError('Public Luma calendar upcoming links have an unreadable schema')
            entries = upcoming.get('entries', []) if kind == 'calendar' else data.get('events', [])
            if not isinstance(entries, list) or any(not isinstance(item, dict) or not isinstance(item.get('event'), dict) for item in entries):
                raise FetchError('Public Luma calendar event links have an unreadable schema')
            embedded = [event_url(item['event'].get('url')) for item in entries]
            break
        return list(dict.fromkeys(item for item in embedded if item))
    elif primary_event_url(url):
        return []
    # A primary standalone event may link to tickets or speakers. Those are
    # not a calendar and must not suppress verification of the event itself.
    elif external_pages:
        nodes = list(_events(soup))
        own = [n for n in nodes if canonical_url(n.get('url', '')) == canonical_url(url)]
        if own and any(urlsplit((n.get('organizer') or {}).get('url', '')).hostname == host
                       for n in own if isinstance(n.get('organizer'), dict)):
            return []
    linked = []
    for node in soup.select('a[href]'):
        if node.find_parent(['nav', 'header', 'footer', 'aside']):
            continue
        try:
            target = canonical_url(urljoin(url, node['href']))
            primary = primary_event_url(target)
            if (not primary and external_pages and target
                    and (node.select_one('time[datetime]') or re.search(r'\b(?:conference|hackathon|meetup|workshop|summit|community day)\b', node.get_text(' ', strip=True), re.I))
                    and not urlsplit(target).path.lower().endswith(('.pdf', '.jpg', '.png'))):
                primary = target
            linked.append(primary)
        except ValueError:
            continue
    return list(dict.fromkeys(item for item in linked + embedded if item and item != primary_event_url(url)))


def _plain(value):
    return BeautifulSoup(value, 'html.parser').get_text(' ', strip=True) if isinstance(value, str) else ''


def _description(soup, node):
    """Read the publisher's event section, excluding recommendations/footers."""
    url = primary_event_url(node.get('url'))
    if url and urlsplit(url).hostname == 'www.meetup.com':
        # JSON-LD descriptions are often truncated, while rendered inline tags
        # split a single eligibility sentence over many text nodes. The matched
        # public Event record retains the full description without either loss.
        script = soup.select_one('script#__NEXT_DATA__')
        try:
            props = json.loads(script.string or script.get_text())['props']['pageProps']
            event_id = urlsplit(url).path.strip('/').split('/')[-1]
            event = props.get('event') or {}
            if str(event.get('id')) == event_id and isinstance(event.get('description'), str) and event['description'].strip():
                return _plain(event['description'])
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    parts = [_plain(node.get('description'))]
    for control in soup.select('button[aria-controls]'):
        if control.get_text(' ', strip=True).lower() in ('about the conference', 'about this event'):
            panel = soup.find(id=control['aria-controls'])
            if panel:
                # Introductory event paragraphs, excluding speaker biographies,
                # talk recommendations and global subscription/footer forms.
                parts.extend(p.get_text(' ', strip=True) for p in panel.select('p')[:1])
    heading = next((h for h in soup.select('h2,h3') if h.get_text(' ', strip=True).lower() in ('details', 'about this event')), None)
    if heading:
        strings = []
        for item in heading.next_elements:
            if isinstance(item, Tag) and item is not heading and item.name in ('h1', 'h2', 'h3'):
                break
            if isinstance(item, NavigableString) and not heading in item.parents and not any(
                    parent.name in ('script', 'style', 'nav', 'footer') for parent in item.parents):
                text = str(item).strip()
                if text:
                    strings.append(text)
        parts.append('\n'.join(strings))
    return '\n'.join(part for part in parts if part)


def _events(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if any(kind in ('Event', 'BusinessEvent', 'EducationEvent', 'SocialEvent') for kind in types):
                yield value
            if '@graph' in value:
                yield from walk(value['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue


def _locations(node):
    locations = node.get('location', [])
    return [item for item in (locations if isinstance(locations, list) else [locations]) if isinstance(item, dict)]


def _scope(node, description):
    locations = _locations(node)
    countries = []
    address_text = []
    for location in locations:
        address = location.get('address') or {}
        if isinstance(address, dict):
            country = address.get('addressCountry') or ''
            if isinstance(country, dict):
                country = country.get('name') or country.get('identifier') or ''
            countries.append(str(country).lower())
            address_text.append(json.dumps(address, ensure_ascii=False))
        elif isinstance(address, str):
            countries.append('philippines' if re.search(r'\bPhilippines\b', address, re.I) else '')
            address_text.append(address)
    declared = str(node.get('eventAttendanceMode', '')).rsplit('/', 1)[-1]
    modes = {'OnlineEventAttendanceMode': 'online', 'OfflineEventAttendanceMode': 'in_person', 'MixedEventAttendanceMode': 'hybrid'}
    mode = modes.get(declared)
    virtual = any(item.get('@type') == 'VirtualLocation' for item in locations)
    physical = any(item.get('@type') == 'Place' for item in locations)
    if not mode:
        mode = 'hybrid' if virtual and physical else 'online' if virtual else 'in_person' if physical else 'unknown'
    if any(country in ('ph', 'philippines') for country in countries) and mode in ('in_person', 'hybrid'):
        return 'PH', mode, '; '.join(address_text)
    worldwide = worldwide_participation(description)
    if mode == 'online' and worldwide:
        return 'international_online', mode, declared + '; ' + worldwide[0]
    return None, mode, None


def _controls(soup, url):
    controls = []
    pattern = re.compile(r'^(?:Attend(?: event)?|RSVP(?: now)?|Register(?: now| for (?:this )?event)?|Request to (?:join|register)|Join (?:the )?waitlist|Buy tickets?|Get tickets?)$', re.I)
    for item in soup.select('button,input[type="submit"],a[href],[role="button"]'):
        ancestry = [item, *item.parents]
        if any(parent.name in ('footer', 'aside', 'nav', 'header') or parent.has_attr('hidden')
               or parent.get('aria-hidden') == 'true' or parent.has_attr('inert')
               or re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden)', parent.get('style', ''), re.I)
               for parent in ancestry if isinstance(parent, Tag)):
            continue
        if item.name == 'a' and primary_event_url(urljoin(url, item['href'])) != url:
            continue
        label = item.get_text(' ', strip=True) or item.get('value', '')
        if not pattern.fullmatch(label):
            continue
        enabled = not item.has_attr('disabled') and all(str(item.get(key, '')).lower() != 'true' for key in ('aria-disabled', 'data-disabled'))
        controls.append((item, label, enabled))
    return controls


def _typed_deadlines(description):
    """Only explicitly labelled dates; never use schedule end as a cutoff."""
    fields = {}
    labels = {'deadline': r'(?:registration|RSVP|ticket sales) (?:deadline|closes?|ends?)',
              'submission_deadline': r'(?:submission|project submission) deadline',
              'registration_opens': r'(?:registration|RSVP|ticket sales) opens?'}
    for field, label in labels.items():
        match = re.search(r'(?im)^\s*(' + label + r')\s*:\s*([^\n]+?)\s*$', description)
        if match:
            value = manila_moment(match[2].strip().rstrip('.'))
            if value.get('value'):
                fields[field] = (value, match[0].strip())
    return fields


def _meetup_group_scope(soup, url, node):
    """An event's own PH group can host online; unrelated cache entries cannot."""
    script = soup.select_one('script#__NEXT_DATA__')
    try:
        props = json.loads(script.string or script.get_text())['props']['pageProps']
        identifier = urlsplit(url).path.strip('/').split('/')[-1]
        direct = props.get('event') or {}
        cache = props.get('__APOLLO_STATE__') or {}
        event = cache.get('Event:' + identifier) or {}
        if str(direct.get('id')) != identifier or str(event.get('id')) != identifier:
            return None
        reference = (event.get('group') or {}).get('__ref')
        group = cache.get(reference) or {}
        organizer = node.get('organizer') or {}
        expected = canonical_url(organizer.get('url', '')).rstrip('/')
        actual = canonical_url(group.get('link', '')).rstrip('/')
        if (not reference or reference != 'Group:' + str(group.get('id')) or actual != expected
                or str(group.get('country', '')).lower() not in ('ph', 'phl', 'philippines')):
            return None
        return f'Meetup Event:{identifier} group={reference}; link={actual}; country={group["country"]}; city={group.get("city", "")}'
    except (TypeError, ValueError, KeyError, AttributeError):
        return None


def _meetup_state(soup, url, now, controls):
    """Capacity must refer to YES RSVPs, not the unrelated WAITLIST count."""
    script = soup.select_one('script#__NEXT_DATA__')
    try:
        props = json.loads(script.string or script.get_text())['props']['pageProps']
    except (TypeError, ValueError, KeyError, AttributeError):
        return 'unknown', None, {}
    event_id = urlsplit(url).path.strip('/').split('/')[-1]
    direct = props.get('event') or {}
    event = (props.get('__APOLLO_STATE__') or {}).get('Event:' + event_id) or {}
    if str(event.get('id')) != event_id or str(direct.get('id')) != event_id:
        return 'unknown', None, {}
    dates = {}
    for key, field in (('rsvpOpenTime', 'registration_opens'), ('rsvpCloseTime', 'deadline')):
        raw = (event.get('rsvpSettings') or {}).get(key)
        value = manila_moment(raw) if isinstance(raw, str) else None
        if value and value.get('value'):
            dates[field] = (value, f'Meetup event {event_id} rsvpSettings.{key}={raw}')
    if instant(dates.get('deadline', (None,))[0]) and instant(dates['deadline'][0]) <= now:
        return 'closed', dates['deadline'][1], dates
    if instant(dates.get('registration_opens', (None,))[0]) and instant(dates['registration_opens'][0]) > now:
        return 'not_yet_open', dates['registration_opens'][1], dates
    maximum = event.get('maxTickets')
    yes = None
    for key, value in event.items():
        if key.startswith('rsvps(') and isinstance(value, dict):
            try:
                args = json.loads(key[len('rsvps('):-1])
            except ValueError:
                continue
            if args.get('filter', {}).get('rsvpStatus') == ['YES']:
                yes = value.get('totalCount')
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0 or not isinstance(yes, int) or yes < 0:
        return 'unknown', None, dates
    quote = f'Meetup event {event_id}: status={event.get("status")}; maxTickets={maximum}; YES RSVP totalCount={yes}; waitlistMode={event.get("waitlistMode")}'
    active = [(item, label) for item, label, enabled in controls if enabled]
    if maximum <= yes:
        if any('waitlist' in label.lower() for _, label in active):
            return 'waitlisted', quote + '; enabled waitlist action', dates
        return 'unknown', quote + '; capacity does not establish a current registration route', dates
    if event.get('status') == 'ACTIVE' and active:
        if any(re.match(r'Request to', label, re.I) for _, label in active):
            return 'approval_required', quote + '; enabled application action', dates
        if any(re.fullmatch(r'Attend(?: event)?|RSVP(?: now)?|Register(?: now)?', label, re.I) for _, label in active):
            return 'open', quote + '; enabled event registration action', dates
    return 'unknown', None, dates


def _price(description):
    # Platform offer price=0 is often a default, even for paid/waitlist events.
    paid = re.search(r'\b(?:paid (?:ticketed )?event|paid tickets?|(?:registration fee|ticket price)\s*:?\s*(?:PHP|USD|EUR|GBP|₱|\$)\s*[1-9][\d,.]*|tickets? (?:cost|priced at))[^\n!?]*', description, re.I)
    free_pattern = re.compile(r'\b(?:free (?:admission|registration|tickets?|entry|event|(?:online )?(?:conference|meetup|workshop))|(?:admission|registration|tickets?|entry) (?:is|are) free|(?:this |the )?(?:event|meetup|workshop|conference) (?:is|will be) (?:totally |completely |100% )?free|no (?:registration|admission|entry) fee|free of charge)\b', re.I)
    if paid and not re.search(r'\b(?:no|not a|not|without)\s*$', description[max(0, paid.start() - 15):paid.start()], re.I):
        return {'kind': 'paid'}, paid[0]
    for statement in re.finditer(r'([^.!?\n]+)([.!?]?)', description):
        sentence = statement[1]
        free = free_pattern.search(sentence)
        if not free or statement[2] == '?':
            continue
        # Qualifiers before the matched phrase matter too: "Only members:
        # this event is free" and "not a free conference" are not free entry.
        if re.search(r"\b(?:not|never|isn['’]t|aren['’]t|wasn['’]t|won['’]t|if|unless|except|only|members?|students?|fellows?|sponsors?|eligible|limited to|subject to|with (?:a|an|the) (?:membership|code))\b", sentence, re.I):
            continue
        return {'kind': 'free', 'amount': 0}, sentence.strip()
    return {'kind': 'unknown'}, None


def _audience(description):
    """Keep the audience/requirements apart from the workshop program."""
    return '\n'.join(value for value, _ in audience_statements(description))[:600] or None


def _structured_event(raw, url, source, now):
    soup = BeautifulSoup(raw, 'html.parser')
    nodes = list(_events(soup))
    if not nodes:
        raise FetchError('Primary Event structured metadata unavailable; page may require JavaScript')
    external = source.get('allow_external_pages') and not primary_event_url(url)
    identity_url = canonical_url if external else primary_event_url
    matching = [node for node in nodes if identity_url(node.get('url', url)) == url]
    if len(matching) > 1:
        raise FetchError('Ambiguous primary Event records match this URL')
    if not matching:
        return None, 'A unique primary Event record matching this URL is unavailable'
    node = matching[0]
    title = _plain(node.get('name'))
    if not title:
        raise FetchError('Primary Event name is unavailable')
    if external and norm(title) not in {norm(h.get_text(' ', strip=True)) for h in soup.select('h1')}:
        return None, 'Standalone Event metadata is not corroborated by the primary visible heading'
    if not node.get('url'):
        headings = {_plain(h.get_text(' ', strip=True)).casefold() for h in soup.select('h1')}
        if title.casefold() not in headings:
            raise FetchError('URL-less Event name does not match the primary visible heading')
    description = _description(soup, node)
    topic, topic_quote = community_topic(title, description)
    if not topic:
        return None, 'No supported AI, cybersecurity or general IT topic in the primary event text'
    geography, mode, scope_quote = _scope(node, description)
    public_broadcast = None
    if external and mode == 'online' and re.search(r'\bfree online conference\b', description, re.I):
        broadcast = re.search(r'All talks premiere on YouTube[^.]*', description, re.I)
        watch = next((a for a in soup.select('a[href]') if urlsplit(a['href']).hostname in ('www.youtube.com', 'youtube.com')
                      and re.fullmatch(r'Watch (?:all )?talks', a.get_text(' ', strip=True), re.I)), None)
        if broadcast and watch and not re.search(r'\b(?:restricted|members only|residents only)\b', description, re.I):
            public_broadcast = (watch['href'], broadcast[0])
            geography, scope_quote = 'international_online', broadcast[0] + '; public viewing link: ' + watch['href']
    if mode == 'online' and urlsplit(url).hostname == 'www.meetup.com':
        group_scope = _meetup_group_scope(soup, url, node)
        if group_scope:
            geography, scope_quote = 'PH', group_scope
    if not geography:
        return None, 'No Philippine physical venue or explicitly worldwide online participation'
    if geography == 'PH' and topic == 'cybersecurity' and urlsplit(url).hostname != 'www.meetup.com':
        return None, 'Philippine cybersecurity events require the separate competition verifier'
    organizer = node.get('organizer') or {}
    if isinstance(organizer, list):
        organizer = organizer[0] if len(organizer) == 1 else {}
    name = _plain(organizer.get('name')) if isinstance(organizer, dict) else ''
    organizer_url = canonical_url(organizer.get('url') or '') if isinstance(organizer, dict) else None
    if not name or not organizer_url:
        return None, 'Primary event organizer identity is unavailable'
    if external and urlsplit(organizer_url).hostname.removeprefix('www.') != urlsplit(url).hostname.removeprefix('www.'):
        return None, 'Standalone event publisher is not corroborated as its organizer; follow the primary organizer link'
    start = manila_moment(node.get('startDate') if isinstance(node.get('startDate'), str) else None)
    end = manila_moment(node.get('endDate') if isinstance(node.get('endDate'), str) else None)
    if not start.get('value'):
        raise FetchError('Primary event start date is unavailable or lacks unambiguous precision')
    if ((instant(start) and instant(end) and instant(end) < instant(start))
            or (manila_day(start) and manila_day(end) and manila_day(end) < manila_day(start))):
        raise FetchError('Conflicting primary event schedule; end precedes start')
    controls = _controls(soup, url)
    state, state_quote, dates = 'unknown', None, _typed_deadlines(description)
    host = urlsplit(url).hostname
    if host == 'www.meetup.com':
        state, state_quote, typed = _meetup_state(soup, url, now, controls)
        dates.update(typed)
    else:
        offers = node.get('offers', [])
        offers = offers if isinstance(offers, list) else [offers]
        available = [offer for offer in offers if isinstance(offer, dict) and str(offer.get('availability')).rsplit('/', 1)[-1] in ('InStock', 'LimitedAvailability')]
        active = [(control, label) for control, label, enabled in controls if enabled]
        if active and available:
            if any('waitlist' in label.lower() for _, label in active) or re.search(r'\b(?:join|sign(?:ing)? up for) (?:the )?waitlist\b', description, re.I):
                state = 'waitlisted'
            elif any(label.lower().startswith('request to') for _, label in active) or re.search(r'\b(?:organizer approval required|registration requires approval)\b', description, re.I):
                state = 'approval_required'
            else:
                state = 'open'
            state_quote = 'Enabled event action: ' + ', '.join(label for _, label in active) + '; primary offers availability=' + ', '.join(str(offer['availability']) for offer in available)
        waitlist_notice = re.search(r'[^\n]*(?:sign(?:ing)? up for|join) (?:the )?waitlist[^\n]*', description, re.I)
        if waitlist_notice and state in ('unknown', 'open'):
            # An explicit organizer notice establishes the offered route even
            # if the public widget is disabled; it does not establish entry.
            state, state_quote = 'waitlisted', waitlist_notice[0].strip()
    if instant(end) and instant(end) <= now:
        state, state_quote = 'closed', 'Confirmed event end has passed: ' + str(node.get('endDate'))
    for field, expected in (('deadline', 'closed'), ('registration_opens', 'not_yet_open')):
        value = instant(dates.get(field, (None,))[0])
        if value and (value <= now if field == 'deadline' else value > now):
            state, state_quote = expected, dates[field][1]
    price, price_quote = _price(description)
    region = region_from(scope_quote, 'Philippines') if geography == 'PH' else 'International online'
    attendance = ['Online'] if mode == 'online' else ['Onsite', 'Online'] if mode == 'hybrid' else ['Onsite']
    facts = {'name': title, 'organizer': name, 'geography': geography, 'topic': topic,
             'region': region, 'format': mode, 'attendance_options': attendance, 'ticket_options': [],
             'start': start, 'end': end if end.get('value') else None, 'competition_date': None,
             'deadline': None, 'submission_deadline': None, 'registration_opens': None,
             'registration_state': state, 'registration_url': url if controls else None,
             'organizer_event_url': url, 'eligibility': None, 'price': price,
             'account_required': None, 'summary': None, 'lifecycle': None}
    if public_broadcast:
        facts['summary'] = 'Free online premiere. Public YouTube viewing link: ' + public_broadcast[0]
        facts['registration_url'] = public_broadcast[0]
    proof = {}
    def cite(field, quote):
        proof[field] = {'url': url, 'quote': quote[:600]}
    cite('name', 'Schema.org Event name=' + title)
    cite('organizer', 'Schema.org Event organizer=' + json.dumps(organizer, ensure_ascii=False))
    cite('organizer_event_url', 'Primary Event page: ' + url)
    cite('topic', topic_quote)
    retain_description(facts, proof, description, url)
    cite('geography', scope_quote)
    cite('region', scope_quote)
    cite('format', 'Schema.org eventAttendanceMode=' + str(node.get('eventAttendanceMode')) + '; location=' + json.dumps(node.get('location'), ensure_ascii=False))
    cite('attendance_options', proof['format']['quote'])
    for field, key in (('start', 'startDate'), ('end', 'endDate')):
        if facts[field]:
            cite(field, 'Schema.org Event ' + key + '=' + node[key])
    for field, (value, quote) in dates.items():
        facts[field] = value
        cite(field, quote)
    if state_quote:
        cite('registration_state', state_quote)
        if state in ('open', 'approval_required') or (state == 'waitlisted' and 'enabled' in state_quote.lower()):
            proof['registration_state']['basis'] = 'live_registration_widget'
    if controls:
        cite('registration_url', 'Public event action: ' + '; '.join(label + (' [enabled]' if enabled else ' [disabled]') for _, label, enabled in controls))
    if public_broadcast:
        cite('registration_url', public_broadcast[1] + '; Watch all talks: ' + public_broadcast[0])
        cite('summary', public_broadcast[1])
    if price_quote:
        cite('price', price_quote)
    eligibility = _audience(description)
    if eligibility:
        facts['eligibility'] = eligibility
        cite('eligibility', '\n'.join(quote for _, quote in audience_statements(description)))
    status = str(node.get('eventStatus', '')).rsplit('/', 1)[-1]
    if status in ('EventCancelled', 'EventPostponed'):
        facts['lifecycle'] = 'cancelled' if status == 'EventCancelled' else 'postponed'
        cite('lifecycle', 'Schema.org eventStatus=' + status)
    if host == 'www.meetup.com':
        # This is the whole Meetup event. Do not label its agenda bounds as a
        # separate CTF's schedule or use a CTF track date as a reschedule.
        from .extract import conflicting_dates
        claims = [{'field': 'start', 'date': start, 'quote': proof['start']['quote']}]
        for match in re.finditer(
                r'(?im)^[ \t*]*(?:Happening on\s+|Event date[ \t*]*:[ \t*]*)([A-Za-z]+\s+\d{1,2},?\s+20\d{2}|20\d{2}-\d{2}-\d{2})[^\n]*', description):
            claims.append({'field': 'start', 'date': parse_moment(match[1]), 'quote': match[0].strip()})
        conflicts = conflicting_dates(claims)
        facts['date_conflicts'] = conflicts
        if conflicts:
            facts['start'] = facts['end'] = facts['competition_date'] = None
            facts['registration_state'] = 'unknown'
            state = 'unknown'
            for field in ('start', 'end', 'competition_date', 'registration_state'):
                proof.pop(field, None)
            cite('date_conflicts', '\n'.join(c['quote'] for c in conflicts))
    platform = 'meetup' if host == 'www.meetup.com' else 'web' if external else 'gdg'
    event_id = url if external else urlsplit(url).path.strip('/').split('/')[-1]
    return {'url': url, 'external_id': platform + ':' + event_id, 'title': title,
            'posted_at': None, 'access': 'full', 'official': True, 'verification_method': 'event_page',
            'kind': 'registration' if state in ('open', 'approval_required') else 'announcement',
            'identity': {'organizer_key': platform + ':' + organizer_url, 'series': platform + ' event',
                         'edition': event_id, 'region': 'Philippines' if geography == 'PH' else 'International online', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof, 'publisher_leads': [],
            'discovery_path': list(dict.fromkeys([source.get('url', url), url]))}, 'Verified primary structured event and event body'


def _luma_event(raw, url, source, client, now):
    data = page_data(raw, 'event')
    event, calendar = data.get('event') or {}, data.get('calendar') or {}
    calendar_id = calendar.get('api_id')
    if not calendar_id or calendar_id != event.get('calendar_api_id') or not re.fullmatch(r'cal-[A-Za-z0-9_-]+', calendar_id):
        return None, 'Luma event presenting calendar identity is unavailable'
    soup = BeautifulSoup(raw, 'html.parser')
    candidates = []
    for link in soup.select('a[href]'):
        try:
            target = canonical_url(urljoin(url, link['href']))
        except ValueError:
            continue
        if not target or urlsplit(target).hostname not in LUMA_HOSTS:
            continue
        try:
            if urlsplit(target).port not in (None, 80, 443):
                continue
        except ValueError:
            continue
        parsed = urlsplit(target)
        matches_slug = calendar.get('slug') and parsed.path.strip('/') == calendar['slug']
        if parse_qs(parsed.query).get('k') == ['c'] or matches_slug:
            candidates.append(target)
    if not candidates:
        # A personal-calendar event has no public presenting calendar. In this
        # case only its named, visibly linked primary host supplies identity;
        # do not present a hidden "Personal" calendar as an organization.
        owner_id = calendar.get('personal_user_api_id')
        if calendar.get('is_personal') is True and owner_id:
            host = next((host for host in data.get('hosts', []) if host.get('api_id') == owner_id), None)
            owner = public_host(host, url) if host else None
            linked_hosts = {urlsplit(urljoin(url, link['href'])).path.rstrip('/') for link in soup.select('a[href]')
                            if urlsplit(urljoin(url, link['href'])).hostname in LUMA_HOSTS}
            host_paths = {'/user/' + owner_id, '/user/' + str((host or {}).get('username') or '')}
            if owner and linked_hosts & host_paths:
                ann, reason = parse_community_event(raw, data, url, {**source, 'url': url, '_calendar_id': calendar_id,
                    'event_scope': 'community', 'topic': 'community'}, now)
                if ann:
                    ann['facts']['organizer'] = owner['name']
                    ann['identity']['organizer_key'] = owner['account_id']
                    ann['field_evidence']['organizer'] = owner['evidence']
                    ann['field_evidence']['organizer_event_url'] = {'url': url, 'quote': 'Primary event page names and links public host ' + owner_id}
                    ann['discovery_path'] = list(dict.fromkeys([source.get('url', url), url]))
                    return ann, 'Verified personal Luma event from its named and visibly linked public host'
                return ann, reason
        return None, 'No public presenting calendar URL is linked from the Luma event'
    for calendar_url in list(dict.fromkeys(candidates))[:2]:
        calendar_raw = client.public_page(calendar_url, allowed_hosts=list(LUMA_HOSTS))
        try:
            public = page_data(calendar_raw, 'calendar').get('calendar') or {}
        except FetchError:
            continue
        if public.get('api_id') != calendar_id or not public.get('name'):
            continue
        verified_source = {**source, 'url': calendar_url, '_calendar_id': calendar_id,
                           'event_scope': 'community', 'topic': 'community'}
        ann, reason = parse_community_event(raw, data, url, verified_source, now)
        if ann:
            ann['field_evidence']['organizer']['calendar_url'] = calendar_url
            ann['field_evidence']['organizer']['quote'] += '; public linked calendar api_id=' + public['api_id']
            ann['field_evidence']['organizer_event_url'] = {'url': url, 'quote': 'Public event with matching presenting calendar ID: ' + calendar_id}
            ann['discovery_path'] = list(dict.fromkeys([source.get('url', url), url, calendar_url]))
        return ann, reason
    return None, 'Linked public calendar does not confirm the event presenting calendar ID'


def verify_page(raw, url, source, client, now):
    """Return the normal announcement contract or a factual rejection reason."""
    try:
        return _verify_page(raw, url, source, client, now)
    except (AttributeError, TypeError, KeyError) as exc:
        raise FetchError('Primary event structured metadata has unreadable field types') from exc


def _verify_page(raw, url, source, client, now):
    normalized = primary_event_url(url)
    if not normalized and source.get('allow_external_pages'):
        from .standalone_event import parse_event as standalone
        announcement, reason = standalone(raw, canonical_url(url), source, now)
        if announcement:
            return announcement, reason
        return _structured_event(raw, canonical_url(url), source, now)
    if not normalized:
        return None, 'Not a supported primary event URL'
    host = urlsplit(normalized).hostname
    if host in LUMA_HOSTS:
        try:
            page_data(raw, 'event')
        except FetchError:
            for kind in ('calendar', 'discover-place'):
                try:
                    page_data(raw, kind)
                    return None, 'Public Luma calendar is a discovery page, not an event'
                except FetchError:
                    continue
            raise FetchError('Public Luma event metadata unavailable; page may require JavaScript') from None
        return _luma_event(raw, normalized, source, client, now)
    if host in ('www.meetup.com', 'gdg.community.dev'):
        return _structured_event(raw, normalized, source, now)
    if host and host.endswith('.devpost.com'):
        from .devpost import parse_event
        soup = BeautifulSoup(raw, 'html.parser')
        rules_url = normalized.rstrip('/') + '/rules'
        linked = any(canonical_url(urljoin(normalized, a['href'])) == rules_url for a in soup.select('a[href]'))
        rules_raw = client.public_page(rules_url, allowed_hosts=[host]) if linked and client else None
        return parse_event(raw, normalized, source, now, rules_raw=rules_raw)
    return None, 'Devpost primary format is unsupported; eligibility, dates and signup are unverified'
