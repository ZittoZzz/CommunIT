"""Conservative semantic HTML fallback for an organizer's standalone conference.

No event names, dates, hosts, or reference editions are configured here. An
about section, explicit organizer statement, PH venue, and consistent ticket
dates must all belong to the same self-canonical page.
"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .domain import canonical_url, norm, parse_moment, region_from
from .event_text import retain_description
from .luma import community_topic


def parse_event(raw, url, source, now):
    soup = BeautifulSoup(raw, 'html.parser')
    def meta(key):
        node = soup.select_one(f'meta[property="{key}"]')
        return node.get('content', '').strip() if node else ''
    title = meta('og:title')
    about, tickets, location = [soup.select_one('section#' + key) for key in ('about', 'tickets', 'location')]
    if not (title and canonical_url(meta('og:url')) == url and about and tickets and location):
        return None, 'Standalone semantic event sections unavailable'
    heading = about.find(['h1', 'h2'])
    if not heading or norm(re.sub(r'^What is\s+', '', heading.get_text(' ', strip=True), flags=re.I)) != norm(title):
        return None, 'Standalone title and event heading disagree'
    organizer, eligibility = None, None
    for detail in soup.select('section#faq details'):
        question = detail.find('summary')
        answer = detail.find('p')
        if not question or not answer:
            continue
        text = answer.get_text(' ', strip=True)
        if re.search(r'who (?:is |are )?organi[sz]', question.get_text(' ', strip=True), re.I):
            match = re.search(r'\b(?:co-)?organi[sz]ed by (.+?)(?:\.$|$)', text, re.I)
            if match:
                organizer = match[1]
        elif re.search(r'who can (?:attend|participate)', question.get_text(' ', strip=True), re.I):
            eligibility = text
    venue = location.get_text(' ', strip=True)
    if not organizer or not re.search(r'\bPhilippines\b', venue, re.I):
        return None, 'Standalone organizer or Philippine venue not established'
    ticket_times = tickets.select('time[datetime]')
    for stamp in ticket_times:
        # A ticket card can date its sales window rather than the event.
        # Preserve that uncertainty instead of promoting a booking cutoff
        # (or release date) into the event's schedule.
        context = stamp.parent.get_text(' ', strip=True)
        if re.search(r'\b(?:sales?|selling|registration|sign[\s-]?ups?|applications?|submissions?|deadline|cut[\s-]?off|expires?|expiry|expiration)\b|'
                     r'\b(?:book|buy|purchase|register|enroll|apply)\s+(?:by|before|until)\b|'
                     r'\b(?:early bird|tickets?|booking)\s+(?:ends?|starts?|opens?|closes?|releases?|valid|available until)\b', context, re.I):
            return None, 'Standalone ticket date describes sales or signup; event schedule is unverified'
    dates = [parse_moment(t.get('datetime', '')) for t in ticket_times]
    if not dates or any(d['precision'] != 'date' for d in dates) or len({d['value'] for d in dates}) != 1:
        return None, 'Standalone ticket dates are absent or conflicting'
    description = '\n'.join(p.get_text(' ', strip=True) for p in about.select('p'))
    topic, topic_quote = community_topic(title, description)
    if not topic:
        return None, 'Standalone program does not establish a technical event'
    tiers = []
    for card in tickets.select('article'):
        name = card.find(['h2', 'h3', 'h4'])
        amounts = re.findall(r'(?:₱|PHP)\s*([\d,]+(?:\.\d{1,2})?)', card.get_text(' ', strip=True))
        if name and len(set(amounts)) == 1:
            tiers.append({'name': name.get_text(' ', strip=True), 'price': {'kind': 'paid',
                          'amount': float(amounts[0].replace(',', '')), 'currency': 'PHP'},
                          'access': 'unknown', 'eligibility': None, 'attendance': 'onsite',
                          'registration_state': 'unknown', 'deadline': None})
    signup = next((canonical_url(urljoin(url, a['href'])) for a in tickets.select('a[href]')
                   if re.fullmatch(r'(?:secure|get|buy) (?:your )?tickets?', a.get_text(' ', strip=True), re.I)
                   and not a['href'].startswith('#')), None)
    price = {'kind': 'paid', 'minimum_amount': min(t['price']['amount'] for t in tiers), 'currency': 'PHP'} if tiers else {'kind': 'unknown'}
    facts = {'name': title, 'organizer': organizer, 'geography': 'PH', 'region': region_from(venue, 'Philippines'),
             'topic': topic, 'format': 'in_person', 'attendance_options': ['Onsite'],
             'start': dates[0], 'end': None, 'competition_date': None, 'deadline': None,
             'submission_deadline': None, 'registration_opens': None, 'registration_state': 'unknown',
             'registration_url': signup, 'organizer_event_url': url, 'price': price,
             'ticket_options': tiers, 'eligibility': eligibility, 'account_required': None,
             'summary': None, 'lifecycle': None}
    proof = {field: {'url': url, 'quote': quote} for field, quote in {
        'name': title, 'organizer': organizer, 'geography': venue, 'region': venue, 'format': venue,
        'organizer_event_url': meta('og:url'), 'start': 'Ticket date: ' + dates[0]['raw'], 'topic': topic_quote,
    }.items()}
    if tiers:
        proof['price'] = {'url': url, 'quote': '; '.join(t['name'] + ': PHP ' + str(t['price']['amount']) for t in tiers)}
        proof['ticket_options'] = proof['price']
    if eligibility:
        proof['eligibility'] = {'url': url, 'quote': eligibility}
    if signup:
        proof['registration_url'] = {'url': url, 'quote': 'Advertised ticket link: ' + signup + '; availability unverified'}
    retain_description(facts, proof, description, url)
    return {'url': url, 'title': title, 'external_id': 'web:' + norm(title), 'posted_at': None,
            'official': True, 'access': 'full', 'kind': 'announcement',
            'identity': {'organizer_key': url, 'series': 'standalone event', 'edition': title,
                         'region': 'Philippines', 'stage': 'main'},
            'facts': facts, 'field_evidence': proof, 'publisher_leads': [], 'discovery_path': [url]}, \
           'Verified standalone organizer sections; ticket date remains date-only and inventory unknown'
