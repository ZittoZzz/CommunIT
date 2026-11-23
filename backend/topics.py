"""Conservative, evidence-backed topic labels for the student directory.

This is a read projection, not a collector classification or a stored migration.
The old ``topic`` field is intentionally left intact: its ``general_it`` value
also covered narrow software/cloud events and is not a safe catch-all tag.
"""
from __future__ import annotations

import html
import re

from .event_text import project_content, title_quote, verified_organizer, legacy_ctf_heading_only


TOPICS = (
    'cybersecurity', 'ai_data', 'cloud_devops', 'software_development',
    'networking_systems', 'community', 'general_it',
)

PATTERNS = {
    'cybersecurity': re.compile(
        r'\b(?:cyber[ -]?security|information security|infosec|ethical hacking|'
        r'penetration testing|digital forensics|reverse engineering|web exploitation|'
        r'cryptography|capture[ -]the[ -]flag|\w*CTF)\b', re.I),
    'ai_data': re.compile(
        r'\b(?:AI|artificial intelligence|machine learning|deep learning|'
        r'large language models?|LLMs?|data science|data analytics|data engineering|'
        r'data analysis|data visualization)\b', re.I),
    'cloud_devops': re.compile(
        r'\b(?:cloud (?:computing|infrastructure|native|development|engineering|'
        r'platforms?|deployment|services?|architecture)|AWS (?:cloud|training|skills|workshops?|labs?)|'
        r'(?:learn(?:ing)?|train(?:ing)? on|train(?:ing)? in)\s+(?:about\s+)?AWS|DevOps|Kubernetes|Docker|'
        r'infrastructure as code|CI/CD|continuous integration|continuous deployment)\b', re.I),
    'software_development': re.compile(
        r'\b(?:(?:software|web|app|application|mobile) (?:development|engineering)|'
        r'computer programming|(?:app|application|software|website)[ -]building|'
        r'(?:coding|programming) (?:workshop|tutorial|course)|'
        r'open[ -]source (?:software|development|contributions?)|'
        r'(?:websites?|mobile apps?|software applications?)\b[^.!?\n]{0,140}\b'
        r'(?:are welcome|are accepted|are allowed)|'
        r'(?:build(?:ing)?|develop(?:ing)?|creat(?:e|ing))\b[^.!?\n]{0,85}?\b'
        r'(?:apps?|applications?|software|websites?|APIs?|AI agents?|games?))\b', re.I),
    'networking_systems': re.compile(
        r'\b(?:computer networks?|networking systems?|network protocols?|TCP/IP|'
        r'network security|systems? administration|network(?:ing)? configuration|'
        r'networking setup|system configuration|Linux administration|operating systems?|'
        r'IP routing)\b', re.I),
    'general_it': re.compile(
        r'\b(?:information technology (?:events?|conferences?|workshops?|meetups?|summits?|sessions?|skills?|topics?)|'
        r'general (?:IT|technology)|broad tech(?:nology)?|multi[- ]topic (?:IT|tech(?:nology)?)|'
        r'(?:broad|wide) (?:range|variety) of (?:tech|technology|technical) topics)\b', re.I),
}
COMMUNITY = re.compile(
    r'\b(?:community[- ]building(?: program| activities| sessions?)?|community showcase|'
    r'(?:developer|tech|technology|user[- ]group)\s+(?:community\s+)?social|'
    r'bring(?:s|ing)?\b[^.!?\n]{0,80}\b(?:developers?|peers|tech enthusiasts?|builders?)\b[^.!?\n]{0,40}\btogether|'
    r'(?:meet|connect with)\s+(?:other |fellow |local )?(?:developers?|peers|builders?)\b[^.!?\n]{0,100}\b(?:share|connect|projects|community)|'
    r'(?:share|showcase)\s+(?:their |your |our )?projects\b[^.!?\n]{0,100}\b(?:peers|community|developers?))\b', re.I)
RECRUITING = re.compile(r'\b(?:recruit(?:ing|ment)?|job fair|hiring|employers?|job seekers?|job opportunities)\b', re.I)
COMMUNITY_PROGRAM = re.compile(r'\b(?:community[- ]building|community showcase|(?:developer|tech|technology|user[- ]group)\s+(?:community\s+)?social)\b', re.I)
ROUTINE_BREAK = re.compile(r'\b(?:(?:networking|coffee|lunch|tea|refreshment)\s+break|networking lunch)\b', re.I)
CTF = re.compile(r'\b(?:capture[ -]the[ -]flag|\w*CTF)\b', re.I)
CTF_ACTIVITY = re.compile(
    r'(?:capture[ -]the[ -]flag|CTF)\b[^.!?\n]{0,100}\b(?:competition|tournament|challenge|contest)|'
    r'\b(?:competition|tournament|challenge|contest)\b[^.!?\n]{0,100}(?:capture[ -]the[ -]flag|CTF)\b', re.I)
METADATA = re.compile(
    r'(?im)^\s*(?:co[- ]organi[sz]ers?|organi[sz]ers?|hosts?|sponsors?|partners?)\s*:', re.I)
NEGATED = re.compile(
    r'\b(?:no|not|without|excluding|unrelated to|rather than)\s+(?:\w+\s+){0,3}$', re.I)
HACKFORGOV = re.compile(r'\bhack\s*(?:for|4)\s*gov\b', re.I)


def _series_topic(payload):
    # Topic taxonomy is separate from verification of this edition's schedule
    # or signup. Require both the parsed identity and its retained title quote;
    # a query, organizer name or unsupported generated name cannot establish it.
    if payload.get('access') not in ('full', 'search_only'):
        return None
    if not HACKFORGOV.fullmatch(payload.get('identity', {}).get('series') or ''):
        return None
    item = payload.get('field_evidence', {}).get('name') or {}
    if (HACKFORGOV.search(item.get('quote') or '')
            and HACKFORGOV.search(payload.get('facts', {}).get('name') or '')
            and str(item.get('url', '')).startswith(('https://', 'http://'))):
        return {**item, 'basis': 'event_series', 'access': payload['access']}
    return None


def _snippets(payload):
    """Subject evidence only; never organizer names, search text or fee metadata."""
    _, proof = project_content(payload)
    for field in ('topic', 'name', 'description', 'summary'):
        item = proof.get(field)
        if isinstance(item, dict) and isinstance(item.get('quote'), str) and item.get('url'):
            for source in item.get('sources') or [item]:
                yield source['quote'], source['url'], field
    if (isinstance(payload.get('evidence'), str) and payload.get('url')
            and not legacy_ctf_heading_only(payload)):
        yield payload['evidence'], payload['url'], 'evidence'


def _sentences(text, payload):
    text = METADATA.split(text, maxsplit=1)[0]
    names = [payload.get('facts', {}).get('organizer')]
    publisher = payload.get('publisher')
    names.append(publisher.get('name') if isinstance(publisher, dict) else publisher)
    for original in re.split(r'(?<=[.!?])\s+|\n|\s+\|\s+', text):
        original = original.strip()
        # Classify a cleaned, masked sentence, but cite the original retained
        # sentence: organizer-name removal must not silently edit quotations.
        sentence = re.sub(r'<[^>]*>', ' ', html.unescape(original))
        sentence = re.split(
            r'\b(?:hosted|organi[sz]ed|sponsored|presented|supported|powered) by\b|'
            r'\b(?:organi[sz]ers?|hosts?|sponsors?|partners?)\s*:', sentence, maxsplit=1, flags=re.I)[0]
        for name in names:
            if isinstance(name, str) and name.strip():
                # An organizer called Global AI or AWS does not make every
                # event an AI or cloud session. Keep its actual subject text.
                sentence = re.sub(r'(?<!\w)' + re.escape(name.strip()) + r'(?!\w)', '', sentence, flags=re.I)
        sentence = sentence.strip()
        if sentence:
            yield original, sentence


def _positive(pattern, sentence):
    for match in pattern.finditer(sentence):
        before = sentence[max(0, match.start() - 50):match.start()]
        after = sentence[match.end():]
        if NEGATED.search(re.sub(r'\bnot only\b', '', before, flags=re.I)):
            continue
        if re.match(r"\s+(?:(?:is|are|was|were|will|does|do)\s+(?:not|never)|isn't|aren't|won't)\b", after, re.I):
            continue
        yield match


def project_topics(payloads):
    """Return stable labels and their citations from active saved announcements.

    A fetched, verified organizer page can establish several subjects. Existing
    fetched CTF announcements may also establish cybersecurity with an explicit
    competition quote even when a university or partner republished the notice.
    Known event-series taxonomy can label a search-only lead without upgrading
    its verification. Other search text and legacy topic strings establish nothing.
    """
    evidence = {}
    for payload in payloads:
        if series_proof := _series_topic(payload):
            evidence.setdefault('cybersecurity', series_proof)
        if payload.get('access') != 'full':
            continue
        verified = verified_organizer(payload)
        named_ctf = CTF.search(payload.get('facts', {}).get('name') or '')
        snippets = list(_snippets(payload))
        recruiting_context = any(RECRUITING.search(quote) for quote, _, field in snippets if field != 'name')
        for quote, url, field in snippets:
            if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
                continue
            for original, sentence in _sentences(quote, payload):
                if not verified:
                    # This exception is intentionally narrow. A fetched article
                    # naming an actual CTF contest can corroborate its subject;
                    # an unverified "AI hackathon" title cannot establish tags.
                    if named_ctf and next(_positive(CTF_ACTIVITY, sentence), None):
                        evidence.setdefault('cybersecurity', {'url': url, 'quote': original})
                    continue
                for topic, pattern in PATTERNS.items():
                    if next(_positive(pattern, sentence), None):
                        evidence.setdefault(topic, {'url': url, 'quote': original})
                # Community is an organizer-described purpose/program, not a
                # title, organizer identity, recruiting pitch or routine break.
                community_program = COMMUNITY_PROGRAM.search(sentence)
                if (field not in ('name', 'summary') and not title_quote(payload, quote) and not RECRUITING.search(sentence)
                        and (not recruiting_context or community_program)
                        and (not ROUTINE_BREAK.search(sentence) or community_program)):
                    if next(_positive(COMMUNITY, sentence), None):
                        evidence.setdefault('community', {'url': url, 'quote': original})
    return [topic for topic in TOPICS if topic in evidence], {
        topic: evidence[topic] for topic in TOPICS if topic in evidence}
