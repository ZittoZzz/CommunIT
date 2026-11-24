"""Visitor projection. Collection diagnostics stay in SQLite and CLI reports."""
from datetime import datetime
from urllib.parse import urlsplit

EVENT_FIELDS = set('''id name organizer region format eligibility announcement_url
announcement_label registration_url registration_status registration_state status section
competition_date start end deadline registration_opens posted_at first_seen summary description
stage edition notices geography topic topics price account_required submission_deadline
attendance_options ticket_options parent_event_start parent_event_end date_conflicts review
verification organizer_event_url lifecycle series'''.split())
ANNOUNCEMENT_FIELDS = set('''url title kind posted_at first_seen last_seen access evidence
revision_count publisher_role'''.split())
# Explicit evidence fields, never discovery queries, traversal paths or source IDs.
EVIDENCE_FIELDS = EVENT_FIELDS | {'philippine_connection', 'name', 'topic', 'organizer', 'posted_at'}


def public_url(value):
    if not isinstance(value, str):
        return None
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        return None
    # Subscription/search endpoints are collector inputs, not visitor citations.
    if (p.hostname in ('api.tavily.com', 'api.search.brave.com', 'public.api.bsky.app')
            or p.path.rstrip('/').endswith(('/feed', '/feed.xml', '/rss', '.ics'))
            or p.path.startswith(('/ics/', '/api/'))):
        return None
    return value


def evidence_map(evidence, *, topics=False):
    return {key: {'url': url, 'quote': proof.get('quote', '')}
            for key, proof in (evidence or {}).items()
            if (topics or key in EVIDENCE_FIELDS) and isinstance(proof, dict)
            and (url := public_url(proof.get('url')))}


def public_event(event):
    result = {k: v for k, v in event.items() if k in EVENT_FIELDS}
    result['field_evidence'] = evidence_map(event.get('field_evidence'))
    result['topic_evidence'] = evidence_map(event.get('topic_evidence'), topics=True)
    result['announcements'] = []
    for ann in event.get('announcements', []):
        item = {k: v for k, v in ann.items() if k in ANNOUNCEMENT_FIELDS}
        # A route display name (e.g. a search provider) is not publisher identity.
        publisher = ann.get('publisher')
        if isinstance(publisher, dict):
            publisher = publisher.get('name')
        item['publisher'] = publisher if publisher and publisher != ann.get('source_name') else urlsplit(ann['url']).hostname
        item['field_evidence'] = evidence_map(ann.get('field_evidence'))
        item['related_links'] = [{'url': url, 'label': link.get('label', ''), 'access': 'linked_only'}
                                 for link in ann.get('related_links', [])
                                 if (url := public_url(link.get('url')))]
        result['announcements'].append(item)
    return result


def listings_updated_at(events):
    """Latest retained, evidenced event-page check, including partial runs.

    Search observation, route success, page load and unverified legacy timestamps
    cannot advance this value. This is not a claim that every listing was checked.
    """
    dates = []
    for event in events:
        value = (event.get('verification') or {}).get('last_event_page_checked_at')
        if not value:
            continue
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if stamp.tzinfo:
                dates.append((stamp, value))
        except (TypeError, ValueError):
            continue
    return max(dates)[1] if dates else None
