"""Evidence-scoped publisher leads from ordinary public article paragraphs.

These are candidates, not verified monitors or inferred ownership. A link in a
footer, a share control, or an unrelated paragraph does not establish a role.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .domain import canonical_url, facebook_post


ROLE = re.compile(
    r'(?P<organizer>\b(?:co[- ]organi[sz]ed|organi[sz]ed|organi[sz]ers?)\s*(?:by|:)\s*)'
    r'|(?P<host>\b(?:co[- ]hosted|hosted|hosts?)\s*(?:by|:)\s*)'
    r'|(?P<sponsor>\b(?:sponsored\s+by|(?:our\s+|the\s+)?sponsors?\s*:?)\s+)'
    r'|(?P<challenge_partner>\bchallenge\s+partners?\s*:?\s*)'
    r'|(?P<community_partner>\bcommunity\s+partners?\s*:?\s*|\b(?:community\s+|learning\s+)?partnership\s+with\s+(?:the\s+)?)'
    r'|(?P<contributor>\bmade\s+possible\s+by\s+|\bheld\s+with\s+(?:the\s+)?)',
    re.I,
)
TOKEN = re.compile(r'\[\[publisher:(\d+)\]\]')
ROLE_WORDS = re.compile(r'^(?:our |the )?(?:community |challenge )?(?:partners?|sponsors?|hosts?|organizers?)\s*:?$', re.I)
NEGATED = re.compile(r'\b(?:not|never|seeking|seeks?|looking\s+for|become|becoming|potential|prospective|interested)\b', re.I)


def _paragraphs(content):
    # Clone supplied soups: a caller may still need its links or full text.
    soup = BeautifulSoup(str(content), 'html.parser')
    for node in soup.select('script, style, nav, footer, header, aside, form, .sharedaddy, .share-buttons, .social-share, .author, .comment-respond, #comments'):
        node.decompose()
    paragraphs = soup.find_all(['p', 'li', 'dd'])
    return [p for p in paragraphs if not p.find_parent(['p', 'li', 'dd'])]


def _public_url(value, base):
    url = canonical_url(urljoin(base, value))
    if not url:
        return None
    parts = urlsplit(url)
    if (facebook_post(url) or
            re.search(r'(?:^|/)(?:sharer(?:\.php)?|share(?:Article|\.php)?|intent|submit|login|signin)(?:/|$)', parts.path, re.I) or
            re.search(r'\.(?:pdf|mp4|png|jpe?g|webp|gif)(?:$)', parts.path, re.I)):
        return None
    return url


def _name(value):
    name = re.sub(r'\s+', ' ', value).strip(' \t\n,:;—–-')
    name = re.sub(r'^Visit\s+', '', name, flags=re.I)
    name = re.sub(r'\s+(?:Official\s+)?(?:on\s+)?(?:Facebook|LinkedIn|Website)$', '', name, flags=re.I)
    if not (2 <= len(name) <= 160) or ROLE_WORDS.fullmatch(name):
        return None
    if re.match(r'^(?:https?://|click\b|read\b|join\b|learn\b|register\b|explore\b)', name, re.I):
        return None
    return name


def publisher_leads_from_html(content, announcement_url):
    """Return named, local relationship evidence; never fetch linked accounts.

    Stable URL leads may be deduplicated by URL by the caller. Unlinked names
    intentionally have no guessed account ID; their identity remains scoped to
    this evidence until a public account can be established.
    """
    leads = {}
    for paragraph in _paragraphs(content):
        quote = re.sub(r'\s+', ' ', paragraph.get_text(' ', strip=True))
        nodes = []
        # Anchors and explicitly emphasized names retain where they occurred in
        # their clause. Emphasis alone does not establish a publisher role.
        for node in list(paragraph.select('a[href], strong, b')):
            if node.parent is None or node.find_parent(['a', 'strong', 'b']):
                continue
            name = _name(node.get_text(' ', strip=True))
            if not name:
                continue
            url = _public_url(node.get('href', ''), announcement_url) if node.name == 'a' else None
            same_announcement = url == canonical_url(announcement_url) if url else False
            if node.name == 'a' and not url:
                continue
            if same_announcement:
                url = None
            nodes.append({'name': name, 'url': url})
            node.replace_with(f'[[publisher:{len(nodes) - 1}]]')
        text = re.sub(r'\s+', ' ', paragraph.get_text(' ', strip=True))
        markers = list(ROLE.finditer(text))
        for token in TOKEN.finditer(text):
            prior = [m for m in markers if m.end() <= token.start()]
            if not prior:
                continue
            marker = prior[-1]
            # A role belongs to its clause, not arbitrary links later in a
            # paragraph. Real partner lists may contain multiple linked names.
            between = text[marker.end():token.start()]
            before = text[max(0, marker.start() - 70):marker.start()]
            if re.search(r'[.!?;]', TOKEN.sub('', between)) or NEGATED.search(before):
                continue
            item = nodes[int(token[1])]
            # Unlinked emphasis is useful for "partnership with Name"; a
            # generic bold phrase elsewhere in a role list is too uncertain.
            if not item['url'] and re.sub(r'\b(?:the|our)\b|[\s,:]', '', between, flags=re.I):
                continue
            role = marker.lastgroup
            if role == 'organizer' and re.match(r'co[- ]', marker[0], re.I):
                role = 'co-organizer'
            lead = {'name': item['name'], 'role': role, 'evidence': {'url': announcement_url, 'quote': quote[:600]}}
            if item['url']:
                lead['url'] = item['url']
            leads[(item['url'] or item['name'], role)] = lead
        # A named sponsor can appear as ordinary text, without a public link.
        # Require a clear label/context and stop at punctuation or a new clause.
        for match in re.finditer(r'(?:\bcourtesy\s+of\s+(?:our\s+|the\s+)?sponsor\s+|\bSponsor\s*:\s*)([A-Z][A-Za-z0-9&+ -]{1,90})(?=[.,;!]|$)', quote):
            name = _name(match[1])
            if name and not re.search(r'\b(?:for|which|who|provides?|offering)\b', name, re.I):
                if not any(v['name'] == name and v['role'] == 'sponsor' for v in leads.values()):
                    leads[(name, 'sponsor')] = {'name': name, 'role': 'sponsor', 'evidence': {'url': announcement_url, 'quote': match[0][:600]}}
    return list(leads.values())[:40]


def relationship_scope(content, announcement_url=None):
    """Evidence that a Philippine organization hosts or organizes this event.

    A Philippine sponsor or audience does not make a foreign event local. A
    named, linked host/organizer or an explicit held-with relationship qualifies.
    """
    for lead in publisher_leads_from_html(content, announcement_url or 'https://scope.invalid/'):
        if not lead.get('url') or not re.search(r'\bPhilippines\b', lead['name'], re.I):
            continue
        if lead['role'] in ('host', 'organizer', 'co-organizer'):
            return lead['evidence']
        if lead['role'] == 'contributor' and re.search(
                r'\bheld\s+with\s+(?:the\s+)?' + re.escape(lead['name']) + r'(?:\b|$)',
                lead['evidence']['quote'], re.I):
            return lead['evidence']
    return None
