"""Conservative, historical evidence of discovery while registration was open.

Publication dates and an event's first appearance do not prove timely discovery.
Only a stored observation with a supported open registration window can do so.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .domain import instant


def _has_evidence(evidence, field):
    proof = evidence.get(field)
    return (isinstance(proof, dict) and isinstance(proof.get('url'), str)
            and bool(proof['url'].strip()) and isinstance(proof.get('quote'), str)
            and bool(proof['quote'].strip()))


def evaluate_registration_observation(facts, evidence, observed_at):
    """Return reasons an individual historical observation is not verified.

    An empty list means the observation qualifies. Date-only deadlines remain
    unverified even when a publisher's general timezone is known: a clock cutoff
    must not be invented for a measurement of registration availability.
    """
    reasons = []
    try:
        observed = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
        if observed.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        observed = None
        reasons.append('observation_time_unconfirmed')
    state = facts.get('lifecycle')
    if state in ('finished', 'cancelled', 'postponed'):
        reasons.append(f'event_{state}_at_observation')
    end = instant(facts.get('end'))
    if observed is not None and end is not None and observed >= end:
        reasons.append('competition_ended_at_observation')
    if facts.get('registration_state') != 'open':
        reasons.append('registration_not_confirmed_open')
    if not _has_evidence(evidence, 'registration_state'):
        reasons.append('registration_state_evidence_missing')
    deadline = facts.get('deadline')
    if deadline is None:
        reasons.append('registration_deadline_missing')
    elif instant(deadline) is None or not deadline.get('timezone'):
        reasons.append('registration_deadline_time_or_timezone_unconfirmed')
    elif observed is not None and observed >= instant(deadline):
        reasons.append('registration_deadline_passed_at_observation')
    if not _has_evidence(evidence, 'deadline'):
        reasons.append('registration_deadline_evidence_missing')
    opens = facts.get('registration_opens')
    if opens is not None:
        if instant(opens) is None or not opens.get('timezone'):
            reasons.append('registration_opening_time_or_timezone_unconfirmed')
        elif observed is not None and observed < instant(opens):
            reasons.append('registration_not_started_at_observation')
        if not _has_evidence(evidence, 'registration_opens'):
            reasons.append('registration_opening_evidence_missing')
    return reasons


def _known_event_blockers(rows, observed_at):
    """Do not count a stale invitation after another observed update closes it."""
    at = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    latest = {}
    for row in rows:
        if row['revision_id'] is None:
            continue
        try:
            observed = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00'))
            if observed.tzinfo is None or observed > at:
                continue
        except (AttributeError, TypeError, ValueError):
            continue
        facts = json.loads(row['facts_json'])
        for field in ('lifecycle', 'registration_state'):
            value = facts.get(field)
            if not value or value == 'unknown':
                continue
            if field not in latest or observed > latest[field][0]:
                latest[field] = (observed, {value})
            elif observed == latest[field][0]:
                # One collection run shares its observation timestamp. Conflicting
                # open and closed evidence in that run cannot verify availability.
                latest[field][1].add(value)
    reasons = []
    for value in latest.get('lifecycle', (None, set()))[1]:
        if value in ('cancelled', 'postponed', 'finished'):
            reasons.append(f'event_{value}_already_observed')
    for value in latest.get('registration_state', (None, set()))[1]:
        if value in ('closed', 'not_yet_open'):
            reasons.append(f'registration_{value}_already_observed')
    return sorted(reasons)


def registration_observations(db):
    """Summarize each retained event using revision-time facts and evidence.

    A later correction does not retroactively prove that a missing deadline was
    observed earlier. A later closure also does not erase an earlier genuinely
    open observation. Withdrawn announcements and deleted evidence are excluded.
    """
    rows = db.execute('''SELECT e.id AS event_id,e.first_seen,a.id AS announcement_id,
        a.url,r.source_id,r.id AS revision_id,r.observed_at,r.facts_json,r.evidence_json
      FROM events e JOIN announcements a ON a.event_id=e.id
      LEFT JOIN revisions r ON r.announcement_id=a.id
      WHERE a.withdrawn=0 ORDER BY e.first_seen,e.id,r.id''').fetchall()
    summaries = {}
    event_rows = {}
    for row in rows:
        event_rows.setdefault(row['event_id'], []).append(row)
    for row in rows:
        summary = summaries.setdefault(row['event_id'], {
            'event_id': row['event_id'], 'first_seen': row['first_seen'],
            'status': 'not_verified', 'earliest_verified_at': None,
            'announcement_id': None, 'revision_id': None, 'source_id': None,
            'url': None, 'registration_evidence': {}, 'registration_window': {},
            'observations_checked': 0, 'reasons': [],
        })
        if row['revision_id'] is None:
            if 'no_retained_revision' not in summary['reasons']:
                summary['reasons'].append('no_retained_revision')
            continue
        summary['observations_checked'] += 1
        facts = json.loads(row['facts_json'])
        evidence = json.loads(row['evidence_json'])
        reasons = evaluate_registration_observation(facts, evidence, row['observed_at'])
        if not reasons:
            reasons = _known_event_blockers(event_rows[row['event_id']], row['observed_at'])
        if reasons:
            summary['reasons'] = list(dict.fromkeys(summary['reasons'] + reasons))
            continue
        timestamp = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
        previous = summary['earliest_verified_at']
        if previous is not None and datetime.fromisoformat(previous) <= timestamp:
            continue
        summary.update({
            'status': 'verified_timely', 'earliest_verified_at': timestamp.isoformat(),
            'announcement_id': row['announcement_id'], 'revision_id': row['revision_id'],
            'source_id': row['source_id'], 'url': row['url'],
            'registration_evidence': {field: evidence[field] for field in
                ('registration_state', 'deadline', 'registration_opens') if field in evidence},
            'registration_window': {field: facts.get(field) for field in
                ('registration_state', 'deadline', 'registration_opens')},
        })
    for summary in summaries.values():
        if summary['status'] == 'verified_timely':
            # Failed observations are not reasons to doubt the qualifying one.
            summary['reasons'] = []
    return list(summaries.values())
