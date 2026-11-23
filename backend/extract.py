"""Small deterministic extractors. Ambiguity stays visible instead of guessed."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from .domain import canonical_url, instant, manila_day, norm, parse_date_range, parse_moment, publisher_url, region_from

CTF = re.compile(r'\bCTF\b|capture[\s-]+the[\s-]+flag|hack\s*(?:for|4)\s*gov|haxxor', re.I)
CONTEST = re.compile(r'(?:capture[\s-]+the[\s-]+flag|\bCTF\b)[^.!?\n]{0,45}\b(?:competition|tournament|contest|challenge)\b|\b(?:competition|tournament|contest)\b[^.!?\n]{0,45}(?:capture[\s-]+the[\s-]+flag|\bCTF\b)', re.I)
PH_VENUE = re.compile(r'(?:Venue|Location)[ \t]*:[ \t]*(?:\n[ \t]*)?[^\n]+|\b(?:Happening on[^.!?\n]{0,55}?\bat|held (?:at|in)|take place (?:at|in))\s+[^.!?\n]{0,140}', re.I)
PH_PLACES = re.compile(r'\b(?:Philippines|Makati|Manila|Quezon City|Cebu|Davao|Baguio|Iligan|Tuguegarao|Pampanga|Clark|Batangas|Cagayan de Oro)\b', re.I)


def publisher_context(source, text):
    """A publisher sharing an invitation is not automatically its organizer."""
    source = dict(source)
    if source.get('publisher_role') not in ('resharer', 'both'):
        return source
    if source.get('scope_pattern') and source.get('organizer') and source.get('organizer_key') not in (None, 'unconfirmed'):
        if re.search(source['scope_pattern'], text, re.I):
            source['_organizer_quote'] = re.search(source['scope_pattern'], text, re.I)[0]
            return source
    match = re.search(r'\b(?:organized|organised|hosted)\s+by\s+(?:the\s+)?([^\n.!?]{3,100})', text, re.I)
    if not match:
        match = re.search(r'Respectfully yours,?\s*\n\s*(?:The\s+)?([^\n]{3,100}?)\s+Team\b', text, re.I)
    source['organizer'] = re.split(r'\s+(?:in celebration|for the|on the|taking place)\b', match[1], flags=re.I)[0].strip(' ,:') if match else 'Organizer not confirmed'
    source['organizer_key'] = norm(source['organizer']) if match else 'unconfirmed'
    source['_organizer_quote'] = match[0] if match else None
    venue = next((m for m in PH_VENUE.finditer(text) if PH_PLACES.search(m[0])), None)
    source['_scope_quote'] = venue[0] if venue else source.get('_relationship_scope_quote')
    # A generic invitation shared by a Philippine school is insufficient. A
    # local venue or separately verified organizer relationship is required.
    if not source['_scope_quote'] and not source.get('scope_pattern'):
        return None
    return source


def body_event_context(text):
    return re.search(r'(?:Event Details\s*:?\s*Date|Tournament dates?|Competition dates?|CTF dates?|Event date)[ \t]*:[ \t]*(?:\n[ \t]*)?[^\n]+|\bHappening on\s+[A-Za-z]+\s+\d{1,2},?\s+20\d{2}', text, re.I)


def body_event_year(title, text):
    year = re.search(r'\b20\d{2}\b', title)
    if year:
        return year
    # The edition may be supported by an explicitly labeled event date. Do not
    # borrow the posting date, workshop date, or a footer's copyright year.
    detail = body_event_context(text)
    return re.search(r'\b20\d{2}\b', detail[0]) if detail else None


def tournament_days(title, text):
    """Retain a calendar day without manufacturing start/end clock times.

    A standalone tournament invitation may put Date under Event Details, with
    HTML splitting the label from its value. Parent conference and teaching
    agendas do not establish the date of a CTF track merely by mentioning one.
    """
    days = []
    for explicit in re.finditer(r'(?im)^\s*(?:Tournament|Competition|CTF) date\s*:[ \t]*(?:\n[ \t]*)?([^\n]+)', text):
        value = parse_moment(explicit[1])
        if value['precision'] == 'date':
            days.append((value, explicit[0].strip()))
    # A parent event date alone is insufficient. This sentence explicitly ties
    # the dated event to its CTF competition; retain the day, never agenda clocks.
    for sentence in re.finditer(r'\bHappening on\s+([A-Za-z]+\s+\d{1,2},?\s+20\d{2})[^.!?\n]*', text, re.I):
        feature = re.search(r'\b(?:the event|we)\s+will\s+(?:feature|host|hold|include)\b(.+)', sentence[0], re.I)
        value = parse_moment(sentence[1])
        direct_contest = feature and re.search(
            r'(?:^|[,;]|\b(?:alongside|and))\s*(?:(?:a|an|the)\s+)?(?:hands-on\s+)?(?:cybersecurity\s+)?(?:' + CONTEST.pattern + ')',
            feature[1], re.I)
        if direct_contest and value['precision'] == 'date':
            days.append((value, sentence[0].strip()))
    if not CONTEST.search(text):
        return days
    if re.search(r'\b(?:conference|summit|festival|meetup)\b', title + '\n' + text, re.I):
        return days
    if re.search(r'\b(?:hackathon|workshop|training|seminar|webinar|bootcamp|course)\b', title, re.I):
        return days
    for block in re.finditer(r'(?im)^[ \t]*Event Details[ \t]*:[ \t]*\n[ \t]*Date[ \t]*:[ \t]*(?:\n[ \t]*)?([^\n]+)', text):
        value = parse_moment(block[1])
        if value['precision'] == 'date':
            days.append((value, block[0].strip()))
    return days


def conflicting_dates(candidates):
    """Compare claims of the same role, allowing day/time corroboration.

    Start and end are separate roles: a legitimate multiday range is not a
    conflict. A single competition day also claims the start's calendar day.
    """
    conflicts = []
    for fields in (('competition_date', 'start'), ('end',)):
        claims = [c for c in candidates if c['field'] in fields and manila_day(c['date'])]
        for i, left in enumerate(claims):
            for right in claims[i + 1:]:
                a, b = left['date'], right['date']
                disagree = instant(a) != instant(b) if instant(a) and instant(b) else manila_day(a) != manila_day(b)
                if disagree:
                    for claim in (left, right):
                        if claim not in conflicts:
                            conflicts.append(claim)
    # Distinct roles may span days, but cannot put the end before the start.
    starts = [c for c in candidates if c['field'] == 'start' and manila_day(c['date'])]
    ends = [c for c in candidates if c['field'] == 'end' and manila_day(c['date'])]
    for start in starts:
        for end in ends:
            a, b = start['date'], end['date']
            reversed_bounds = instant(b) < instant(a) if instant(a) and instant(b) else manila_day(b) < manila_day(a)
            if reversed_bounds:
                for claim in (start, end):
                    if claim not in conflicts:
                        conflicts.append(claim)
    return conflicts


def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup(['script', 'style', 'nav', 'footer', 'header']):
        node.decompose()
    return soup.get_text('\n', strip=True), soup


def identify(title, text, source, url):
    context = title + '\n' + text
    if not CTF.search(context):
        return None
    # Topic mentions, writeups and generic evergreen pages are not competitions.
    if re.search(r'\b(?:writeup|write-up|walkthrough)\b', title, re.I):
        return None
    root = re.search(r'\b(?:ROOTCON|RC)\s*(\d{1,2})\b', context, re.I)
    tcon = re.search(r'\bTCON\s*(\d{1,2})(?:bit)?\b', context, re.I)
    hfg = re.search(r'hack\s*(?:for|4)\s*gov\s*(\d+)?', context, re.I)
    body_named = source.get('body_identity') and not CTF.search(title) and CONTEST.search(text)
    year = body_event_year(title, text) if body_named else re.search(r'\b20\d{2}\b', title) or re.search(r'\b20\d{2}\b', text)
    stage = 'qualifier' if re.search(r'\b(?:qualifiers?|qualifying|pre-quals?)\b', title, re.I) else 'main'
    if re.search(r'\bnational\s+finals?\b', title, re.I):
        stage = 'national-final'
    elif re.search(r'\bregional\s+finals?\b', title, re.I):
        stage = 'regional-final'
    elif re.search(r'\bfinals?\b', title, re.I):
        stage = 'final'
    # For short social announcements the first line identifies the stage, not a
    # sentence about what winners may advance to in a different competition.
    if stage == 'main' and source.get('kind') == 'bluesky':
        first = text.split('\n\n')[0]
        if re.search(r'\b(?:qualifiers?|qualifying|pre-quals?)\b', first, re.I):
            stage = 'qualifier'
    region = region_from(title, source.get('region', 'Unspecified'))
    if root:
        series, edition, org = 'ROOTCON CTF', root[1], 'rootcon'
        name = f'ROOTCON {edition} CTF'
        # Do not import unrelated village CTFs as the main ROOTCON CTF.
        if re.search(r'(?:village|codebreakers).*?(?:CTF|capture)', title, re.I):
            return None
    elif tcon:
        series, edition, org = 'TCON CTF', tcon[1], 'hackthenorth'
        name = f'TCON {edition} CTF'
    elif hfg and (year or hfg[1]):
        series, edition, org = 'HackForGov', year[0] if year else f'edition-{hfg[1]}', 'dict'
        name = f'HackForGov {edition}'
        if region == 'Unspecified':
            region = region_from(text)
        if stage == 'main':
            # Region and stage must be explicit. Never merge unknown national and regional rounds.
            stage = 'regional' if region != 'Unspecified' else 'unspecified'
        name += f' · {region}' if region != 'Unspecified' else ''
    else:
        if not year or not (CTF.search(title) or body_named):
            return None
        series = re.sub(r'\b20\d{2}\b|\b(?:registration|register|announcement|teaser|update|postponed|cancelled|canceled|now|open|coming|soon)\b', '', title, flags=re.I)
        series = re.sub(r'\s+', ' ', series).strip(' :-–—!')
        series = re.sub(r'^(?:Invitation to|Invitation:|Join us for)\s+', '', series, flags=re.I)
        if body_named:
            series += ' · CTF'
        if len(series) < 4:
            return None
        edition, org, name = year[0], source['organizer_key'], series + ' ' + year[0]
    if stage not in ('main', 'regional', 'unspecified'):
        name += ' · ' + stage.replace('-', ' ').title()
    return {'organizer_key': org, 'series': series, 'edition': edition, 'region': region, 'stage': stage}, name


def extract(title, text, url, source, *, posted_at=None, links=None, access='full', external_id=None):
    title = re.sub(r'\s+', ' ', title).strip()
    source = publisher_context(source, text) if access != 'search_only' else source
    if source is None:
        return None
    # A university publishing an article about a foreign CTF does not turn that
    # competition into a Philippine event. Publisher feeds opt into this guard.
    if source.get('scope_pattern') and not re.search(source['scope_pattern'], title + '\n' + text, re.I):
        return None
    identity = identify(title, text, source, url)
    if not identity:
        return None
    key, name = identity
    facts = {'name': name, 'organizer': source['organizer'], 'region': key['region'],
             'format': 'unknown', 'eligibility': None, 'registration_url': None,
             'start': None, 'end': None, 'competition_date': None, 'deadline': None, 'registration_opens': None,
             'summary': None, 'lifecycle': None, 'registration_state': None}
    announcement = {'url': publisher_url(url, source.get('url_normalization')), 'title': title[:240], 'posted_at': posted_at,
                    'access': access, 'kind': 'announcement', 'external_id': external_id,
                    'evidence': None, 'identity': key, 'facts': facts, 'field_evidence': {}}
    if source.get('publisher_role'):
        announcement['publisher'] = {'id': source.get('publisher_id', source.get('id')),
                                     'name': source.get('publisher_name', source.get('name')),
                                     'role': source['publisher_role'], 'url': source.get('url')}
        if source['publisher_role'] in ('resharer', 'both'):
            announcement['official'] = False
            announcement['relationship'] = 'reshare'
    proof = announcement['field_evidence']
    def cite(field, quote, evidence_url=None):
        proof[field] = {'url': evidence_url or announcement['url'], 'quote': quote[:600]}
    cite('name', title)
    if access == 'search_only':
        # A discovery result is not full-post permission or confirmed event detail.
        # Store only the result title and URL with licensed storage; no snippets.
        return announcement
    combined = title + '\n' + text
    if not CTF.search(title):
        cite('name', title + ' | ' + next((line.strip() for line in text.splitlines() if CTF.search(line)), title))
        if source.get('body_identity'):
            detail = body_event_context(text)
            if detail:
                cite('edition', detail[0])
                facts['summary'] = 'Publisher event context: ' + re.sub(r'\s+', ' ', detail[0]).strip() + '. CTF clock times and registration window are not confirmed.'
                cite('summary', detail[0])
    def asserted_status(pattern):
        return any(re.search(pattern, sentence, re.I) and not re.search(
            r'\b(?:if|unless|not|never|may|might|could|whether)\b', sentence, re.I)
            for sentence in re.split(r'[.!?\n]', combined))

    completion_pattern = r'\b(?:successfully concluded|has concluded|competition concluded|competition has ended|CTF has ended|(?:event|competition|CTF) closed with (?:the )?(?:awarding|award|closing))\b'
    if asserted_status(r'\b(?:cancelled|canceled)\b'):
        facts['lifecycle'], announcement['kind'] = 'cancelled', 'cancellation'
    elif asserted_status(r'\bpostponed\b'):
        facts['lifecycle'], announcement['kind'] = 'postponed', 'postponement'
    elif asserted_status(completion_pattern) or (re.search(r'\bCTF (?:champions?|crown)\b', combined, re.I) and re.search(r'\b(?:congratulations|winning team|taking the CTF crown)\b', combined, re.I)):
        facts['lifecycle'], announcement['kind'] = 'finished', 'completion'
    elif re.search(r'\brescheduled\b', combined, re.I):
        facts['lifecycle'], announcement['kind'] = 'scheduled', 'reschedule'
    recap = re.search(r'\b(?:wins?|won|winners?|champions?|recap|concludes?|concluded|triumphs?)\b', title, re.I)
    if recap and re.search(r'\b(?:competition|tournament|CTF|capture[\s-]+the[\s-]+flag)\b', combined, re.I):
        announcement['kind'] = 'recap'
        facts['registration_state'] = 'closed'
        # Completion is explicit only when the article states it, not from a
        # past-looking title that might concern another stage.
    elif re.search(r'\bregistration\s+(?:is\s+)?(?:now\s+)?(?:closed|full)\b', combined, re.I):
        facts['registration_state'] = 'closed'
    elif re.search(r'\bregistration\s+(?:is\s+)?(?:now\s+)?open\b|\bregistration\s*[-–:]\s*open\b|\bregister (?:now|today)\b', combined, re.I):
        facts['registration_state'], announcement['kind'] = 'open', 'registration'
    elif re.search(r'\bregistration\s+(?:opens?|opening)\s+(?:soon|on)\b', combined, re.I):
        facts['registration_state'] = 'not_yet_open'
    if facts['lifecycle'] == 'finished':
        # A retrospective completion notice cannot advertise stale registration.
        facts['registration_state'] = 'closed'
        # Quote the assertion itself. Earlier workshop prose containing "ended"
        # must not consume the excerpt budget and hide the completion evidence.
        for sentence in re.split(r'[.!?\n]', combined):
            match = re.search(completion_pattern, sentence, re.I)
            if match and not re.search(r'\b(?:if|unless|not|never|may|might|could|whether)\b', sentence, re.I):
                quote = sentence[max(0, match.start() - 100):match.end() + 400].strip()
                cite('lifecycle', quote)
                cite('registration_state', quote)
                break
        if source.get('publisher_role') in ('resharer', 'both'):
            announcement['kind'] = 'recap'
    if re.search(r'\binvite[- ]only\b|\binvitation only\b', combined, re.I):
        facts['eligibility'] = 'Invitation only. See the organizer’s announcement for selection rules.'
    elif re.search(r'\bcampus[- ]only\b', combined, re.I):
        facts['eligibility'] = 'Campus only. See the organizer’s announcement for the eligible campus.'
    # Explicit labels only. In particular do not treat a post/publication date or
    # conference registration window as the competition's dates.
    labels = {
        'start': r'(?:Competition (?:start|date)|CTF (?:start|date)|Start(?:s| time)?|Opening)',
        'end': r'(?:Competition end|CTF end|End(?:s| time)?|Closing)',
        'deadline': r'(?:Registration deadline|Deadline (?:of|for) registration|Register by)',
        'registration_opens': r'(?:Registration opens|Registration start)',
    }
    candidates = []
    for field, label in labels.items():
        for m in re.finditer(r'(?:^|\n)\s*' + label + r'\s*:\s*([^\n]+)', text, re.I):
            value, quote = parse_moment(m[1]), m[0].strip()
            if field in ('start', 'end'):
                candidates.append({'field': field, 'date': value, 'quote': quote})
            if facts[field] is None or (field in ('start', 'end') and instant(value)):
                facts[field] = value
                cite(field, quote)
    for dates in re.finditer(r'(?:^|\n)\s*(?:Competition dates?|CTF dates?)\s*:\s*([^\n]+)', text, re.I):
        date_range = parse_date_range(dates[1])
        if date_range:
            facts['start'], facts['end'] = date_range
            cite('start', dates[0].strip())
            candidates.append({'field': 'start', 'date': date_range[0], 'quote': dates[0].strip()})
            if facts['end']:
                cite('end', dates[0].strip())
                candidates.append({'field': 'end', 'date': date_range[1], 'quote': dates[0].strip()})
    days = tournament_days(title, text)
    candidates.extend({'field': 'competition_date', 'date': value, 'quote': quote} for value, quote in days)
    if days and not facts['start'] and not facts['end']:
        facts['competition_date'], quote = days[0]
        cite('competition_date', quote)
    conflicts = conflicting_dates(candidates)
    if conflicts:
        facts['date_conflicts'] = conflicts
        for field in ('start', 'end', 'competition_date'):
            facts[field] = None
            proof.pop(field, None)
        cite('date_conflicts', '\n'.join(c['quote'] for c in conflicts))
        facts['summary'] = 'Conflicting competition dates in the source. Schedule unconfirmed.'
        cite('summary', proof['date_conflicts']['quote'])
    eligible = re.search(r'(?:^|\n)\s*(?:Eligibility|Eligible participants|Open to)\s*:\s*([^\n]+)', text, re.I)
    if eligible:
        facts['eligibility'] = eligible[1][:600]
        cite('eligibility', eligible[0].strip())
    elif source.get('body_identity'):
        restriction = re.search(r'Only currently enrolled students of[^.!?\n]{0,160}(?:are allowed to attend|may participate)', text, re.I)
        if restriction:
            facts['eligibility'] = restriction[0].replace('*', '').strip()
            cite('eligibility', restriction[0])
    if re.search(r'(?:^|\n)\s*(?:Format|Venue)\s*:\s*online\b|\bheld online\b|\bonline CTF\b', text, re.I):
        facts['format'] = 'online'
    elif re.search(r'(?:^|\n)\s*Format\s*:\s*(?:in.person|onsite)\b', text, re.I):
        facts['format'] = 'in_person'
    elif re.search(r'(?:^|\n)\s*Format\s*:\s*hybrid\b', text, re.I):
        facts['format'] = 'hybrid'
    for label, href in links or []:
        if re.search(r'\b(?:CTF registration|register (?:here|now)|registration form)\b', label, re.I):
            facts['registration_url'] = canonical_url(href)
            cite('registration_url', label + ': ' + href)
            break
    direct_link = re.search(r'(?:^|\n)\s*(?:Registration(?: link| form)?|Register(?: here| now)?)\s*:\s*(https?://[^\s<>]+)', text, re.I)
    if direct_link:
        facts['registration_url'] = canonical_url(direct_link[1].rstrip('.,)'))
        cite('registration_url', direct_link[0].strip())
    # A short, attributed evidence excerpt; never retain entire pages or media.
    relevant = [line.strip() for line in text.splitlines() if CTF.search(line)]
    announcement['evidence'] = ' '.join(relevant)[:280] or None
    if not facts['start'] and re.search(r'\b(?:coming soon|stay tuned|save the date)\b', text, re.I):
        announcement['kind'] = 'teaser'
    # Each promoted field carries the line or configured organizer source behind
    # it. Unknown values receive no supporting claim.
    patterns = {'format': r'\bonline\b|\b(?:in.person|onsite|hybrid)\b',
                'eligibility': r'invite|invitation|campus.only',
                'registration_state': r'registr|register|closed with.*award|has ended|concluded',
                'lifecycle': r'cancel|postpon|conclud|ended|champion|crown|rescheduled|closed with.*award'}
    for field, pattern in patterns.items():
        if facts.get(field) not in (None, 'unknown') and field not in proof:
            line = ' '.join(line.strip() for line in combined.splitlines() if re.search(pattern, line, re.I))
            if line:
                cite(field, line)
    if source.get('_organizer_quote'):
        cite('organizer', source['_organizer_quote'])
    elif source.get('publisher_role') in ('resharer', 'both'):
        pass
    elif source.get('scope_pattern'):
        cite('organizer', re.search(source['scope_pattern'], combined, re.I)[0])
    elif source.get('url'):
        cite('organizer', source.get('organizer_evidence', source.get('philippine_connection', source['organizer'])), source['url'])
    if key['region'] != 'Unspecified':
        region_line = next((line.strip() for line in combined.splitlines() if region_from(line) == key['region']), None)
        cite('region', region_line or source.get('philippine_connection', key['region']),
             announcement['url'] if region_line else source.get('url'))
    if posted_at:
        cite('posted_at', f'Publisher publication metadata: {posted_at}')
    if source.get('_scope_quote'):
        announcement['scope_evidence'] = {'url': announcement['url'], 'quote': source['_scope_quote'][:600]}
        proof['philippine_connection'] = announcement['scope_evidence']
    return announcement
