"""Public review notes and ageing; no moderation or inferred event completion."""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit

from .domain import parse_moment

REVIEW_DAYS = 45


def meetup_id(url):
    """Meetup's numeric event ID survives title, group slug and locale changes."""
    p = urlsplit(url or '')
    if p.scheme not in ('http', 'https') or p.hostname not in ('meetup.com', 'www.meetup.com'):
        return None
    match = re.fullmatch(r'/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?[^/]+/events/(\d+)/?', p.path)
    return 'meetup:' + match[1] if match else None


def parent_schedule(payload):
    """Recover only retained calendar context, never promote it to CTF bounds."""
    facts = {}
    proof = {}
    context = payload.get('event_context') or {}
    evidence = context.get('evidence') or {}
    if context.get('kind') == 'calendar' and evidence.get('url') and context.get('calendar_date'):
        facts['parent_event_start'] = parse_moment(context['calendar_date'])
        proof['parent_event_start'] = evidence
    return facts, proof


def event_page_verified(payload):
    if payload.get('access') != 'full':
        return False
    if payload.get('verification_method') == 'event_page':
        return True
    # Legacy structured Meetup payloads predate verification_method. Their
    # retained primary-page identity evidence establishes the fetch, unlike RSS.
    proof = payload.get('field_evidence') or {}
    platform_id = meetup_id(payload.get('url'))
    return bool(platform_id and payload.get('external_id') == platform_id
                and payload.get('official') is True
                and proof.get('name', {}).get('quote', '').startswith('Schema.org Event name=')
                and meetup_id(proof.get('organizer_event_url', {}).get('url')) == platform_id)


def review_listing(current, items, now=None):
    at = now or datetime.now(timezone.utc)
    fetched = [(row, p) for row, p in items if p.get('access') == 'full']
    page_reads = [(row, p) for row, p in fetched if event_page_verified(p)]
    reasons = []
    if not fetched:
        reasons.append('Source content could not be verified. Confirm the schedule and signup with the organizer.')
    if any(meetup_id(p.get('url')) for _, p in items) and not page_reads:
        reasons.append('Saved Meetup feed information needs an event-page check; the page may have changed.')
    if current.get('date_conflicts'):
        reasons.append('The source gives conflicting event dates. Neither date is treated as confirmed.')
    if items and all(row['source_status'] in ('error', 'blocked', 'rate_limited') for row, _ in items):
        reasons.append('The latest source checks could not complete. Previously saved information is still shown.')
    unresolved = current['status'] in ('schedule_tba', 'undated_lead', 'date_conflict', 'end_unconfirmed', 'postponed')
    if unresolved and not reasons:
        reasons.append('The event schedule or completion needs confirmation.')
    expiry = None
    # First discovery is immutable across successful searches and feed rereads.
    # Confirmed schedules/closure remove unresolved status, not elapsed time.
    if unresolved and not any(current.get(f) for f in ('start', 'end', 'competition_date', 'deadline', 'submission_deadline')):
        try:
            first = min(datetime.fromisoformat(row['first_seen'].replace('Z', '+00:00')) for row, _ in items)
            if first.tzinfo:
                expiry = first + timedelta(days=REVIEW_DAYS)
        except (ValueError, TypeError):
            pass
    expired = bool(expiry and at >= expiry)
    if expired:
        current['section'] = 'archived'
        reasons.append(f'Unresolved for {REVIEW_DAYS} days since first discovery. Archived as an unverified lead; this does not confirm the event ended.')
    current['review'] = {'required': bool(reasons), 'reasons': reasons, 'expired': expired,
                         'expires_at': expiry.isoformat() if expiry else None}
    current['verification'] = {
        'last_observed_at': max((row['last_observed_at'] if 'last_observed_at' in row.keys() else None) or row['last_seen'] for row, _ in items),
        'last_content_fetched_at': max((row['last_seen'] for row, _ in fetched), default=None),
        'last_event_page_checked_at': max((row['last_seen'] for row, _ in page_reads), default=None),
        'basis': 'event_page' if page_reads else 'fetched_content' if fetched else 'search_only',
    }
