"""Run the same collection job interactively or from the daily systemd/cron task."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db as storage
from .adapters import ADAPTERS, CredentialsRequired
from .network import Client, FetchError, RateLimited
from .source_index import load_sources
from .metrics import registration_observations
from .publishers import ensure_schema, harvest, publisher_summaries, sync_configured_publishers

ROOT = Path(__file__).resolve().parent.parent


def collect(db, sources, *, client=None, adapters=None, now=None):
    client = client or Client()
    adapters = adapters or ADAPTERS
    # An injected time makes offline tests deterministic. Live observations must
    # be timestamped after the source returns, not at the beginning of a job that
    # may spend minutes waiting on earlier sources or provider rate limits.
    def clock():
        return now if now is not None else datetime.now(timezone.utc)
    stamp = clock().isoformat()
    ensure_schema(db)
    storage.register_sources(db, sources)
    run_id = db.execute('INSERT INTO runs(started_at) VALUES(?)', (stamp,)).lastrowid
    db.commit()
    report = {'started_at': stamp, 'sources': []}
    for source in sources:
        attempted = clock()
        attempt_stamp = attempted.isoformat()
        observed_stamp = None
        sid = source['id']
        count, accepted, added = 0, 0, 0
        status, message = 'error', ''
        discoveries = []
        search_audit = {}
        publisher_counts = {'new_candidates': 0, 'new_relationships': 0, 'accepted': 0, 'rejected': 0}
        retry_after = None
        next_retry_at = None
        try:
            if source.get('enabled') is False:
                status, message = 'disabled', source.get('index_reason') or source.get('reason') or 'Disabled in source configuration; no request made.'
            elif source['kind'] == 'restricted':
                status, message = 'policy_restricted', source['reason']
            else:
                previous_retry = db.execute('SELECT next_retry_at FROM sources WHERE id=?', (sid,)).fetchone()[0]
                if previous_retry and datetime.fromisoformat(previous_retry) > attempted:
                    remaining = (datetime.fromisoformat(previous_retry) - attempted).total_seconds()
                    raise RateLimited(max(1, int(remaining + 0.999)))
                known = db.execute('SELECT * FROM announcements WHERE source_id=? AND withdrawn=0', (sid,)).fetchall()
                result = adapters[source['kind']](source, client, known, attempted)
                observed_stamp = clock().isoformat()
                count = result.discovered
                if hasattr(result, 'searches'):
                    search_audit['searches'] = result.searches
                if hasattr(result, 'decisions'):
                    search_audit['decisions'] = result.decisions
                if hasattr(result, 'route_checks'):
                    search_audit['route_checks'] = result.route_checks
                retry_after = getattr(result, 'retry_after', None)
                if retry_after is None:
                    delays = [a['retry_after'] for q in getattr(result, 'searches', [])
                              if q.get('status') == 'error' for a in q.get('attempts', [])
                              if a.get('status') == 'rate_limited' and a.get('retry_after') is not None]
                    retry_after = max(delays) if delays else None
                # Atomic per-source ingestion. A parsing/DB failure cannot leave a
                # half-updated source or erase listings from the previous run.
                with db:
                    for announcement in result.announcements:
                        if not announcement.get('url'):
                            continue
                        announcement = dict(announcement)
                        announcement.setdefault('publisher', source.get('publisher_name', source['name']))
                        announcement.setdefault('publisher_role', source.get('publisher_role'))
                        announcement.setdefault('index_id', source.get('index_id'))
                        event_id, created = storage.ingest(db, sid, announcement, observed_stamp)
                        leads = [{**lead, 'evidence': {**lead.get('evidence', {}),
                                  'discovery_path': announcement.get('discovery_path', [source['url'], announcement['url']])}}
                                 for lead in announcement.get('publisher_leads', [])]
                        harvested = harvest(db, sid, leads,
                                            event_id=event_id, announcement_url=announcement['url'], now=observed_stamp)
                        for field in publisher_counts:
                            publisher_counts[field] += harvested.get(field, 0)
                        accepted += 1
                        added += int(created)
                        discoveries.append({'event_id': event_id, 'url': announcement['url'],
                                            'path': announcement.get('discovery_path', [source['url'], announcement['url']]),
                                            'related_links': announcement.get('related_links', [])})
                    for external_id in result.deleted:
                        storage.withdraw(db, sid, external_id, observed_stamp)
                    leads = [{**lead, 'evidence': {**lead.get('evidence', {}),
                              'discovery_path': [source['url'], lead.get('evidence', {}).get('url')]}}
                             for lead in getattr(result, 'publisher_leads', [])]
                    harvested = harvest(db, sid, leads, now=observed_stamp)
                    for field in publisher_counts:
                        publisher_counts[field] += harvested.get(field, 0)
                status = 'error' if getattr(result, 'failed', False) else 'partial' if result.warnings else 'ok'
                if getattr(result, 'failed', False) and getattr(result, 'failure_status', None):
                    status = result.failure_status
                message = result.message + (' ' + '; '.join(result.warnings) if result.warnings else '')
        except CredentialsRequired as exc:
            status, message = 'needs_credentials', str(exc)
        except RateLimited as exc:
            status, message, retry_after = 'rate_limited', str(exc), exc.retry_after
        except FetchError as exc:
            status = 'blocked' if 'HTTP 403' in str(exc) or 'disallows automated access' in str(exc) else 'error'
            message = str(exc)[:400]
        except Exception as exc:
            db.rollback()
            # Report a useful but bounded/sanitized error. Request exceptions never
            # carry credentials from the HTTP wrapper.
            status = 'error'
            message = str(exc)[:400] if exc.__class__.__name__ == 'FetchError' else f'{type(exc).__name__}: source could not be processed; previous listings preserved.'
            accepted = added = 0
            discoveries = []
            publisher_counts = {field: 0 for field in publisher_counts}
        finished_stamp = clock().isoformat()
        if retry_after is not None:
            next_retry_at = (datetime.fromisoformat(finished_stamp) + timedelta(seconds=retry_after)).isoformat()
        db.execute('''UPDATE sources SET status=?,last_attempt=?,
          last_success=CASE WHEN ?='ok' THEN ? ELSE last_success END,
          message=?,discovered=?,accepted=?,next_retry_at=? WHERE id=?''',
                   (status, attempt_stamp, status, observed_stamp or finished_stamp, message, count, accepted, next_retry_at, sid))
        db.commit()
        report['sources'].append({'id': sid, 'name': source['name'], 'status': status,
                                  'publisher': source.get('publisher_name', source['name']),
                                  'publisher_role': source.get('publisher_role'),
                                  'coverage': source.get('coverage', []),
                                  'index_id': source.get('index_id'),
                                  'enabled': source.get('enabled', True),
                                  'attempted_at': attempt_stamp, 'observed_at': observed_stamp,
                                  'finished_at': finished_stamp,
                                  'discovered': count, 'accepted': accepted, 'new_announcements': added,
                                  'discoveries': discoveries, 'message': message, **search_audit})
        report['sources'][-1].update(publisher_candidates=publisher_counts, retry_after=retry_after,
                                    next_retry_at=next_retry_at)
    report['finished_at'] = clock().isoformat()
    report['events'] = db.execute('SELECT count(DISTINCT event_id) FROM announcements WHERE withdrawn=0').fetchone()[0]
    report['announcements'] = db.execute('SELECT count(*) FROM announcements WHERE withdrawn=0').fetchone()[0]
    sync_configured_publishers(db, sources, now=report['finished_at'])
    report['publisher_candidates'] = publisher_summaries(db)
    report['registration_observations'] = registration_observations(db)
    report['verified_timely_count'] = sum(item['status'] == 'verified_timely'
                                         for item in report['registration_observations'])
    report['live_open_observation_count'] = sum(item['live_open_observation'] is not None
                                               for item in report['registration_observations'])
    report['first_seen_live_open_count'] = sum(item['first_seen_while_live_open']
                                              for item in report['registration_observations'])
    db.execute('UPDATE runs SET finished_at=?,report=? WHERE id=?', (report['finished_at'], json.dumps(report), run_id))
    db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=os.environ.get('CTF_DATABASE', str(ROOT / 'data/ctfinder.sqlite3')))
    parser.add_argument('--config', default=os.environ.get('CTF_SOURCES', str(ROOT / 'sources.json')))
    parser.add_argument('--source', action='append', help='Source ID to run; repeat for multiple sources')
    parser.add_argument('--report', help='Also write the JSON run report here')
    args = parser.parse_args()
    try:
        sources = load_sources(args.config)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(f'Invalid source configuration: {exc}')
    if args.source:
        missing = set(args.source) - {s['id'] for s in sources}
        if missing:
            parser.error('Unknown source IDs: ' + ', '.join(sorted(missing)))
        sources = [s for s in sources if s['id'] in args.source]
    Path(args.database).parent.mkdir(parents=True, exist_ok=True)
    # Scheduling and manual invocation share a lock; overlapping jobs do not run.
    with open(args.database + '.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'Another collector is already running.\n')
        db = storage.connect(args.database)
        try:
            report = collect(db, sources)
        finally:
            db.close()
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.tmp')
        temp.write_text(rendered + '\n')
        temp.replace(target)
    return 0 if any(s['status'] in ('ok', 'partial') for s in report['sources']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
