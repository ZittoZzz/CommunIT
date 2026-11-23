"""Keep organizer program text separate from audience and entry requirements."""
from __future__ import annotations

import re


PROGRAM = re.compile(
    r'\b(?:learn(?:ing)?|teach(?:ing)?|workshops?|keynotes?|hands[- ]on|agenda|'
    r'learning objectives?|showcase|social|community[- ]building|share projects|'
    r'(?:build(?:ing)?|creat(?:e|ing)|develop(?:ing)?)\b[^.!?]{0,80}\b(?:apps?|applications?|projects?|software)|'
    r'(?:equip|empower)\s+(?:\w+\s+){0,4}(?:students?|builders?|developers?)|'
    r'bring(?:s|ing)?\b[^.!?]{0,100}\btogether|meet (?:fellow |other )?(?:peers|developers))\b', re.I)
REQUIREMENT = re.compile(
    r'\b(?:must|requires?|required|restricted to|limited to|students? only|members? only|'
    r'only (?:students?|members?)|at least \d+|aged? \d+|minimum age)\b', re.I)
AUDIENCE = re.compile(
    r'\b(?:open to|designed for|aimed at|welcomes?|equip|empower)\s+'
    r'(?P<audience>(?:(?:all|aspiring|young|the|next generation of)\s+)?'
    r'(?:students?(?: builders?)?|developers?|beginners?|everyone|anyone|all|members?)'
    r'(?:\s+and\s+(?:students?|developers?|beginners?))?)\b', re.I)


def sentences(text):
    return [part.strip() for part in re.split(r'(?<=[.!?])\s+|\n', text or '') if part.strip()]


def program_sentence(text):
    # An admission requirement to complete a course is not the event's agenda.
    return bool(PROGRAM.search(text) and not REQUIREMENT.search(text))


def audience_statements(text):
    """Return audience wording with the exact sentence supporting each claim."""
    values = []
    for sentence in sentences(text):
        if REQUIREMENT.search(sentence) and re.search(
                r'\b(?:attendees?|participants?|students?|members?|applicants?|registration|admission|entry|age)\b', sentence, re.I):
            values.append((sentence, sentence))
        elif match := AUDIENCE.search(sentence):
            if program_sentence(sentence):
                values.append(('Intended audience: ' + match['audience'] + '.', sentence))
            else:
                values.append((sentence, sentence))
        elif re.search(r'\bwhether you(?:\x27re| are)\b', sentence, re.I) and not program_sentence(sentence):
            values.append((sentence, sentence))
    return list(dict.fromkeys(values))


def verified_organizer(payload):
    return payload.get('access') == 'full' and (payload.get('official') is True or (
        payload.get('official') is not False and payload.get('publisher_role') in ('organizer', 'both')))


def title_quote(payload, text):
    value = re.sub(r'^(?:Schema\.org Event name=|Visible heading and Event name:\s*)', '', text.strip(), flags=re.I)
    def normalized(item):
        return re.sub(r'[\W_]+', ' ', item or '').strip().casefold()
    return bool(normalized(value)) and normalized(value) in {
        normalized(payload.get('title')), normalized(payload.get('facts', {}).get('name'))}


def legacy_ctf_heading_only(payload):
    """Recognize the old adapter's synthetic title plus bare agenda excerpt.

    This does not match named CTFs or descriptions of an actual competition.
    Keep the stored announcement intact; repair only its display projection.
    """
    return bool(re.search(r' · CTF$', payload.get('title') or '', re.I)
                and re.fullmatch(r'\s*(?:Capture[ -]the[ -]Flag|CTF)\s*',
                                 payload.get('evidence') or '', re.I))


def retain_description(facts, proof, text, url):
    """Retain the actual event section, not a synthetic topic/title summary."""
    if text and text.strip():
        facts['description'] = text.strip()
        proof['description'] = {'url': url, 'quote': text.strip()}


def project_content(payload):
    """Recover old misplaced program text on read without rewriting history."""
    facts = dict(payload.get('facts') or {})
    proof = dict(payload.get('field_evidence') or {})
    if legacy_ctf_heading_only(payload):
        original_title = re.sub(r' · CTF$', '', payload['title'], flags=re.I)
        facts['name'] = original_title
        if proof.get('name'):
            proof['name'] = {**proof['name'], 'quote': original_title}
    if not verified_organizer(payload):
        return facts, proof
    descriptions = []
    for field in ('description', 'agenda', 'learning_objectives'):
        evidence = proof.get(field)
        if isinstance(evidence, dict) and evidence.get('quote') and evidence.get('url'):
            descriptions.append((evidence['quote'], evidence['url']))
    # Older adapters kept just a topic sentence from the actual event section.
    # It can still describe the program; the event title cannot fill this role.
    for field in ('topic', 'summary'):
        evidence = proof.get(field)
        if (isinstance(evidence, dict) and evidence.get('quote') and evidence.get('url')
                and not title_quote(payload, evidence['quote'])):
            descriptions.extend((sentence, evidence['url']) for sentence in sentences(evidence['quote'])
                                if program_sentence(sentence))
    eligibility = facts.get('eligibility')
    evidence = proof.get('eligibility')
    if isinstance(eligibility, str) and isinstance(evidence, dict) and evidence.get('url'):
        # Recover only sentences actually retained in the source citation; a
        # legacy generated audience summary cannot become organizer program text.
        source = evidence.get('quote') or ''
        program = [sentence for sentence in sentences(eligibility)
                   if sentence in source and program_sentence(sentence)]
        if program:
            descriptions.extend((sentence, evidence['url']) for sentence in program)
            remaining = [sentence for sentence in sentences(eligibility) if sentence not in program]
            audience = audience_statements('\n'.join(program))
            remaining.extend(value for value, _ in audience)
            facts['eligibility'] = '\n'.join(dict.fromkeys(remaining)) or None
            if facts['eligibility']:
                proof['eligibility'] = dict(evidence)
            else:
                proof.pop('eligibility', None)
    if descriptions:
        descriptions = list(dict.fromkeys(descriptions))
        descriptions = [(quote, url) for quote, url in descriptions
                        if not any(url == other_url and quote != other and quote in other
                                   for other, other_url in descriptions)]
        facts['description'] = '\n\n'.join(quote for quote, _ in descriptions)
        proof['description'] = {'url': descriptions[0][1], 'quote': descriptions[0][0]}
        if len(descriptions) > 1:
            proof['description']['sources'] = [{'url': url, 'quote': quote} for quote, url in descriptions]
    return facts, proof
