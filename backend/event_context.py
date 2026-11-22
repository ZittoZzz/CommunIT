"""Narrow, evidence-backed joining of a program recap and calendar notice.

This never uses display-name similarity. The article must explicitly name the
program whose kickoff it reports, while the calendar must show that same full
subject and kickoff date. Edition, stage and geographic conflicts veto a join.
"""
from __future__ import annotations

import re
from datetime import date
from bs4 import BeautifulSoup
from .domain import norm, parse_moment, region_from

DATE = re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d{2}\b', re.I)
PHASE = re.compile(r'\b(?:kick[- ]?off|opening(?:\s+day|\s+event)?)\s+(?:of|for)\s*$', re.I)
UNKNOWN = {'', 'unknown', 'unspecified'}


def normalized_venue(value):
    text = norm(value).replace('-', ' ')
    ordinal = {'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
               'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10'}
    words = [ordinal.get(word, re.sub(r'^(\d+)(?:st|nd|rd|th)$', r'\1', word))
             for word in text.split() if word not in ('at', 'the')]
    return ' '.join(words)


def venue_parts(values):
    if isinstance(values, dict):
        values = [values[key] for key in ('address', 'full_address', 'short_address') if isinstance(values.get(key), str)]
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return set()
    parts = set()
    for value in values:
        if not isinstance(value, str):
            continue
        for item in [value, *value.split(',')]:
            item = normalized_venue(item)
            if len(item.split()) >= 3 and len(item) >= 12:
                parts.add(item)
    return parts


def article_event_context(content, url):
    soup = BeautifulSoup(str(content), 'html.parser')
    for node in soup.select('script,style,nav,footer,aside,header'):
        node.decompose()
    paragraphs = [p for p in soup.find_all('p') if p.get_text(' ', strip=True)][:4]
    candidates = []
    for paragraph in paragraphs:
        names = [node for node in paragraph.select('b,strong') if 8 <= len(node.get_text(' ', strip=True)) <= 160]
        # Multiple highlighted subjects in the same lead paragraph are unsafe.
        if len(names) != 1:
            continue
        node = names[0]
        subject = node.get_text(' ', strip=True)
        paragraph_text = re.sub(r'\s+', ' ', paragraph.get_text(' ', strip=True))
        before, found, after = paragraph_text.partition(subject)
        if not found or not PHASE.search(before):
            continue
        dates = {parse_moment(m[0])['value'] for m in DATE.finditer(before[-220:])
                 if parse_moment(m[0])['precision'] == 'date'}
        if len(dates) != 1:
            continue
        if len(norm(subject).split('-')) < 2 or re.search(r'\b(?:winners?|speakers?|organizers?)\b', subject, re.I):
            continue
        candidates.append({'kind': 'program_recap', 'subject': subject, 'phase': 'kickoff',
                           'calendar_date': dates.pop(), 'region': 'Unspecified',
                           'evidence': {'url': url, 'quote': paragraph_text[:600]}})
    if len(candidates) != 1:
        return None
    context = candidates[0]
    venues = []
    for paragraph in paragraphs:
        text = re.sub(r'\s+', ' ', paragraph.get_text(' ', strip=True))
        if context['subject'] not in text and not re.search(r'\bheld\b|\b(?:Venue|Location)\s*:|\btook place\b', text, re.I):
            continue
        for found in re.finditer(r'\b(?:at|Venue\s*:|Location\s*:)\s+(?:the\s+)?([^.!?\n]{5,180})', text, re.I):
            value = found[1].strip(' ,;')
            if re.search(r'\b(?:kickoff|kick-off|opening|event|challenge|competition)\b', value, re.I):
                continue
            if venue_parts(value):
                venues.append(value)
    context['venue_names'] = list(dict.fromkeys(venues))
    context['venue_evidence'] = [{'url': url, 'quote': value} for value in context['venue_names']]
    for value in venues:
        region = region_from(value)
        if region != 'Unspecified':
            context['region'] = region
            break
    return context


def attach_article_context(announcement, content):
    if announcement.get('access') == 'search_only':
        return announcement
    if announcement.get('facts', {}).get('lifecycle') != 'finished' and announcement.get('kind') not in ('recap', 'completion'):
        return announcement
    context = article_event_context(content, announcement['url'])
    if context:
        announcement['event_context'] = context
    return announcement


def context_match(previous, incoming):
    """Return traceable match evidence or None; the DB rejects ambiguous events."""
    contexts = [previous.get('event_context'), incoming.get('event_context')]
    if not all(isinstance(c, dict) for c in contexts):
        return None
    if {c.get('kind') for c in contexts} != {'program_recap', 'calendar'}:
        return None
    for ann, context in zip((previous, incoming), contexts):
        evidence = context.get('evidence') or {}
        if ann.get('access') == 'search_only' or evidence.get('url') != ann.get('url') or not evidence.get('quote'):
            return None
    recap, calendar = sorted(contexts, key=lambda c: c['kind'] == 'calendar')
    if recap.get('phase') != 'kickoff':
        return None
    subject = recap.get('subject', '')
    title = calendar.get('title', '')
    # Match the whole subject; a collaborator prefix must have an explicit
    # title delimiter. Substring and token-similarity matches are not accepted.
    titles = [title, *re.split(r'\s+(?:x|presents?)\s+|\s*[|·]\s*', title, flags=re.I)]
    if not subject or norm(subject) not in {norm(value) for value in titles}:
        return None
    day = recap.get('calendar_date')
    try:
        date.fromisoformat(day)
    except (ValueError, TypeError):
        return None
    if day != calendar.get('calendar_date'):
        return None
    old, new = previous.get('identity', {}), incoming.get('identity', {})
    for field in ('edition', 'stage'):
        if not old.get(field) or norm(old[field]) != norm(new.get(field, '')):
            return None
    if re.fullmatch(r'20\d{2}', str(old['edition'])) and day[:4] != str(old['edition']):
        return None
    identity_regions = [norm(ann.get('identity', {}).get('region') or '') for ann in (previous, incoming)]
    if all(r not in UNKNOWN for r in identity_regions) and identity_regions[0] != identity_regions[1]:
        return None
    regions = [norm(c.get('region') or ann.get('identity', {}).get('region') or '')
               for ann, c in zip((previous, incoming), contexts)]
    if all(r not in UNKNOWN for r in regions) and regions[0] != regions[1]:
        return None
    venues = [venue_parts(c.get('venue_names') or c.get('venue') or []) for c in contexts]
    if all(venues):
        shared = venues[0] & venues[1]
        if not shared:
            return None
        geography = 'Exact normalized venue: ' + sorted(shared)[0]
    elif all(r not in UNKNOWN for r in regions):
        geography = 'Same confirmed region: ' + regions[0]
    else:
        meaningful = [word for word in norm(re.sub(r'capture[ -]the[ -]flag', '', subject, flags=re.I)).split('-')
                      if word not in {'the', 'a', 'an', 'of', 'for', 'and', 'ctf', 'event', 'competition', 'challenge'}]
        if len(meaningful) < 4:
            return None
        geography = 'Region unconfirmed on one source; exact distinctive full subject and kickoff date'
    return {'rule': 'exact_program_subject_and_kickoff', 'subject': subject,
            'calendar_date': day, 'geography': geography,
            'evidence': [contexts[0]['evidence'], contexts[1]['evidence']]}
