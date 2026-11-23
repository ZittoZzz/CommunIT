from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from .domain import canonical_url, event_key, lifecycle, manila_day, norm, utcnow
from .event_context import context_match
from .topics import project_topics
from .event_text import project_content
from .verification import event_page_verified, meetup_id, parent_schedule, review_listing

ROOT = Path(__file__).resolve().parent.parent


def connect(path=None):
    path = path or os.environ.get('CTF_DATABASE', str(ROOT / 'data/ctfinder.sqlite3'))
    if str(path) != ':memory:':
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY, identity_json TEXT NOT NULL, first_seen TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS announcements (
      id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
      source_id TEXT NOT NULL, url TEXT NOT NULL, external_id TEXT,
      payload TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      changed_at TEXT NOT NULL, revision_count INTEGER NOT NULL DEFAULT 1,
      withdrawn INTEGER NOT NULL DEFAULT 0, UNIQUE(event_id, url)
    );
    CREATE TABLE IF NOT EXISTS revisions (
      id INTEGER PRIMARY KEY, announcement_id INTEGER NOT NULL REFERENCES announcements(id),
      observed_at TEXT NOT NULL, facts_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sources (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, kind TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'not_run', last_success TEXT, last_attempt TEXT,
      message TEXT NOT NULL DEFAULT '', discovered INTEGER NOT NULL DEFAULT 0,
      accepted INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, report TEXT
    );
    ''')
    # Additive migrations preserve existing first-seen timestamps and history.
    # Old revisions have no retained evidence; do not manufacture it from the
    # current announcement, which may have been edited since that observation.
    migrations = {
        'announcements': {'last_observed_at': 'TEXT'},
        'sources': {
            'publisher_name': 'TEXT', 'publisher_role': 'TEXT',
            'coverage': "TEXT NOT NULL DEFAULT '[]'", 'index_id': 'TEXT',
            'enabled': 'INTEGER NOT NULL DEFAULT 1', 'index_status': 'TEXT',
            'next_retry_at': 'TEXT',
        },
        'revisions': {'evidence_json': "TEXT NOT NULL DEFAULT '{}'", 'source_id': 'TEXT'},
    }
    for table, columns in migrations.items():
        existing = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
        for column, declaration in columns.items():
            if column not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
    db.commit()
    return db


def register_sources(db, sources):
    for source in sources:
        disabled = source.get('enabled') is False
        db.execute('''INSERT INTO sources(id,name,url,kind,publisher_name,publisher_role,coverage,index_id,enabled,index_status,status,message)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url,kind=excluded.kind,
          publisher_name=excluded.publisher_name,publisher_role=excluded.publisher_role,
          coverage=excluded.coverage,index_id=excluded.index_id,enabled=excluded.enabled,
          index_status=excluded.index_status,
          last_success=CASE WHEN sources.url<>excluded.url OR sources.kind<>excluded.kind
            THEN NULL ELSE sources.last_success END,
          next_retry_at=CASE WHEN sources.url<>excluded.url OR sources.kind<>excluded.kind
            THEN NULL ELSE sources.next_retry_at END,
          status=CASE WHEN excluded.enabled=0 THEN 'disabled'
            WHEN sources.url<>excluded.url OR sources.kind<>excluded.kind THEN 'not_run'
            WHEN sources.status='disabled' THEN 'not_run' ELSE sources.status END,
          message=CASE WHEN excluded.enabled=0 THEN excluded.message
            WHEN sources.status='disabled' THEN '' ELSE sources.message END''',
                   (source['id'], source['name'], source['url'], source['kind'],
                    source.get('publisher_name', source['name']), source.get('publisher_role'),
                    json.dumps(source.get('coverage', []), ensure_ascii=False), source.get('index_id'),
                    int(not disabled), source.get('index_status'), 'disabled' if disabled else 'not_run',
                    source.get('index_reason') or source.get('reason') or 'Disabled in source configuration; no request made.' if disabled else ''))
    db.commit()


def discovery_queries(payload):
    """Preserve the queries that found a URL without duplicating query labels."""
    values = [payload.get('discovery_query'), *(payload.get('discovery_queries') or [])]
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def compatible_post_identity(previous, incoming):
    """A shared post may be repurposed; explicit event boundaries still apply."""
    previous_edition, incoming_edition = str(previous.get('edition', '')), str(incoming.get('edition', ''))
    if (len(previous_edition) == len(incoming_edition) == 4 and
            previous_edition.isdigit() and incoming_edition.isdigit() and
            previous_edition != incoming_edition):
        return False
    unknown_regions = ('', 'unspecified', 'unknown')
    previous_region = str(previous.get('region') or '').strip().casefold()
    incoming_region = str(incoming.get('region') or '').strip().casefold()
    if (previous_region not in unknown_regions and incoming_region not in unknown_regions and
            previous_region != incoming_region):
        return False
    stages = {previous.get('stage'), incoming.get('stage')}
    finals = {'final', 'regional-final', 'national-final'}
    if 'qualifier' in stages and stages.intersection(finals):
        return False
    if 'national-final' in stages and stages.intersection({'regional', 'regional-final'}):
        return False
    # Generic main/unspecified or final labels may become more specific when a
    # search title changes. They do not establish a conflicting event boundary.
    return True


def _strict_link_identity(previous, incoming, *, shared_announcement=False):
    """A reusable URL must not join different rounds, editions, or regions."""
    for field in ('edition', 'region', 'stage'):
        if not previous.get(field) or norm(previous[field]) != norm(incoming.get(field, '')):
            return False
    def series(value):
        return norm(re.sub(r'capture[\s-]+the[\s-]+flag', 'CTF', value, flags=re.I))
    previous_series = series(previous.get('series', ''))
    if len(previous_series) < 4 or previous_series != series(incoming.get('series', '')):
        return False
    # A correction of the exact same article can establish its actual organizer.
    # Shared forms require consistent known organizers or a formerly unknown one.
    unknown = {'', 'unknown', 'unconfirmed', 'organizer-unconfirmed'}
    old_org, new_org = norm(previous.get('organizer_key', '')), norm(incoming.get('organizer_key', ''))
    return shared_announcement or old_org == new_org or old_org in unknown or new_org in unknown


def _facebook_url(url):
    host = (urlsplit(url).hostname or '').lower()
    return host == 'facebook.com' or host.endswith('.facebook.com')


def _specific_registration_url(url):
    """Reject homepages and generic form endpoints, even when shared verbatim."""
    url = canonical_url(url) if isinstance(url, str) else None
    if not url or _facebook_url(url):
        return None
    parsed = urlsplit(url)
    if parsed.path in ('', '/'):
        return None
    generic = {'register', 'registration', 'form', 'forms', 'event', 'events',
               'signup', 'sign-up', 'submit', 'apply', 'index', 'index.html',
               'index.php', 'viewform', 'view', 'd', 'e', 'event-registration',
               'registration-form', 'registrationform', 'sign_up'}
    parts = [re.sub(r'\.(?:html?|php|aspx?)$', '', part.casefold())
             for part in parsed.path.strip('/').split('/') if part]
    specific_path = any(len(part) >= 8 and part not in generic for part in parts)
    specific_query = any(key.casefold() in ('id', 'event', 'event_id', 'form', 'form_id')
                         and len(value) >= 6 for key, value in parse_qsl(parsed.query))
    return url if specific_path or specific_query else None


def _linked_event(db, announcement):
    """Find one unambiguous event supported by an exact shared article/form URL."""
    url = announcement['url']
    if not _facebook_url(url):
        matches = db.execute('''SELECT a.*,e.identity_json FROM announcements a
          JOIN events e ON e.id=a.event_id WHERE a.url=? AND a.withdrawn=0 ORDER BY a.id''', (url,)).fetchall()
        matches = [row for row in matches if _strict_link_identity(
            json.loads(row['identity_json']), announcement['identity'], shared_announcement=True)]
        if len({row['event_id'] for row in matches}) == 1:
            return matches[0]
    registration = _specific_registration_url(announcement.get('facts', {}).get('registration_url'))
    proof = announcement.get('field_evidence', {}).get('registration_url')
    if not registration or not proof or announcement.get('access') == 'search_only':
        return None
    matches = []
    for row in db.execute('''SELECT a.*,e.identity_json FROM announcements a
        JOIN events e ON e.id=a.event_id WHERE a.withdrawn=0 ORDER BY a.id'''):
        previous = json.loads(row['payload'])
        if previous.get('access') == 'search_only' or not previous.get('field_evidence', {}).get('registration_url'):
            continue
        if _specific_registration_url(previous.get('facts', {}).get('registration_url')) != registration:
            continue
        if _strict_link_identity(json.loads(row['identity_json']), announcement['identity']):
            matches.append(row)
    return matches[0] if len({row['event_id'] for row in matches}) == 1 else None


def _context_linked_event(db, announcement):
    if not announcement.get('event_context'):
        return None
    matches = []
    for row in db.execute("SELECT a.* FROM announcements a WHERE a.withdrawn=0 ORDER BY a.id"):
        proof = context_match(json.loads(row['payload']), announcement)
        if proof:
            matches.append((row, proof))
    if len({row['event_id'] for row, proof in matches}) != 1:
        return None
    row, proof = matches[0]
    identity = db.execute('SELECT identity_json FROM events WHERE id=?', (row['event_id'],)).fetchone()[0]
    return row['event_id'], json.loads(identity), proof


def ingest(db, source_id, announcement, now=None):
    now = now or utcnow()
    key = event_key(announcement['identity'])
    announcement = dict(announcement)
    existing = db.execute('SELECT * FROM announcements WHERE event_id=? AND url=?',
                          (key, announcement['url'])).fetchone()
    platform_id = meetup_id(announcement['url'])
    if platform_id:
        announcement['external_id'] = platform_id
        candidates = db.execute('''SELECT a.*,e.identity_json FROM announcements a
          JOIN events e ON e.id=a.event_id ORDER BY a.first_seen,a.id''').fetchall()
        # Platform identity wins over an editable title/organizer/date. Existing
        # duplicate rows remain available as history; the read view folds them.
        existing = next((row for row in candidates if meetup_id(row['url']) == platform_id), None)
        if existing:
            key = existing['event_id']
            announcement['identity'] = json.loads(existing['identity_json'])
    external_id = announcement.get('external_id') or ''
    numeric_facebook_id = external_id.startswith('facebook:post:') and external_id.removeprefix('facebook:post:').isdigit()
    if not existing and numeric_facebook_id:
        # Numeric IDs identify the same post across story.php/posts/photo URL
        # shapes. Opaque permalink tokens provide no such equivalence evidence.
        candidates = db.execute('''SELECT a.*,e.identity_json FROM announcements a
          JOIN events e ON a.event_id=e.id WHERE a.external_id=? ORDER BY a.id''', (external_id,)).fetchall()
        existing = next((row for row in candidates if compatible_post_identity(
            json.loads(row['identity_json']), announcement['identity'])), None)
        if existing:
            key = existing['event_id']
            announcement['identity'] = json.loads(existing['identity_json'])
            announcement['url'] = existing['url']
    if not existing:
        linked = _linked_event(db, announcement)
        if linked is not None:
            key = linked['event_id']
            announcement['identity'] = json.loads(linked['identity_json'])
            existing = db.execute('SELECT * FROM announcements WHERE event_id=? AND url=?',
                                  (key, announcement['url'])).fetchone()
    if not existing:
        contextual = _context_linked_event(db, announcement)
        if contextual is not None:
            key, identity, match_evidence = contextual
            announcement['identity'] = identity
            announcement['event_match'] = match_evidence
            existing = db.execute('SELECT * FROM announcements WHERE event_id=? AND url=?',
                                  (key, announcement['url'])).fetchone()
    db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',
               (key, json.dumps(announcement['identity']), now))
    if existing and not existing['withdrawn']:
        previous = json.loads(existing['payload'])
        queries = list(dict.fromkeys(discovery_queries(previous) + discovery_queries(announcement)))
        if previous.get('access') != 'search_only' and announcement.get('access') == 'search_only':
            # Seeing an indexed URL again is not a refresh of its full source.
            # Keep its facts, source attribution, observation time, and revisions.
            preserved = dict(previous)
            if queries:
                preserved['discovery_query'], preserved['discovery_queries'] = queries[0], queries
            if not preserved.get('discovery_path') and announcement.get('discovery_path'):
                preserved['discovery_path'] = announcement['discovery_path']
            db.execute('UPDATE announcements SET payload=?,external_id=COALESCE(external_id,?),last_observed_at=? WHERE id=?',
                       (json.dumps(preserved, sort_keys=True, ensure_ascii=False),
                        external_id if numeric_facebook_id else None, now, existing['id']))
            return key, False
        if queries:
            announcement['discovery_query'], announcement['discovery_queries'] = queries[0], queries
        if not announcement.get('discovery_path') and previous.get('discovery_path'):
            announcement['discovery_path'] = previous['discovery_path']
    payload = json.dumps(announcement, sort_keys=True, ensure_ascii=False)
    if existing:
        changed = existing['payload'] != payload or existing['withdrawn']
        db.execute('''UPDATE announcements SET source_id=?,external_id=?,payload=?,last_seen=?,
          changed_at=CASE WHEN ? THEN ? ELSE changed_at END,
          revision_count=revision_count+?,withdrawn=0 WHERE id=?''',
                   (source_id, announcement.get('external_id') or existing['external_id'], payload, now, changed, now, int(changed), existing['id']))
        aid = existing['id']
    else:
        changed = True
        cursor = db.execute('''INSERT INTO announcements(event_id,source_id,url,external_id,
          payload,first_seen,last_seen,changed_at) VALUES(?,?,?,?,?,?,?,?)''',
                            (key, source_id, announcement['url'], announcement.get('external_id'), payload, now, now, now))
        aid = cursor.lastrowid
    if changed:
        # Retain extracted fact history, not full social posts or HTML.
        db.execute('INSERT INTO revisions(announcement_id,observed_at,facts_json,evidence_json,source_id) VALUES(?,?,?,?,?)',
                   (aid, now, json.dumps(announcement['facts'], ensure_ascii=False),
                    json.dumps(announcement.get('field_evidence', {}), ensure_ascii=False), source_id))
    db.execute('UPDATE announcements SET last_observed_at=? WHERE id=?', (now, aid))
    return key, existing is None


def withdraw(db, source_id, external_id, now):
    # An API-confirmed deletion is different from a failed fetch. Remove cached
    # social facts/evidence, including revision copies, and hide orphan events.
    rows = db.execute('SELECT id FROM announcements WHERE source_id=? AND external_id=?', (source_id, external_id)).fetchall()
    for row in rows:
        db.execute('DELETE FROM revisions WHERE announcement_id=?', (row['id'],))
        db.execute("UPDATE announcements SET payload='{}',withdrawn=1,last_seen=? WHERE id=?", (now, row['id']))


def observation_order(item):
    row, payload = item
    raw = row['changed_at'] if row['revision_count'] > 1 else payload.get('posted_at') or row['first_seen']
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).isoformat()
        # Date-only publication metadata is ordered at day precision, never
        # converted into an event start or displayed as a midnight timestamp.
        if len(raw) == 10:
            return raw
    except ValueError:
        pass
    return row['first_seen']


def events(db, now=None, window_days=None):
    output = []
    records = list(db.execute('SELECT * FROM events ORDER BY first_seen,id'))
    groups, platform_groups = {}, {}
    for event in records:
        rows = db.execute('''SELECT a.*,s.name AS source_name,s.status AS source_status FROM announcements a
          JOIN sources s ON a.source_id=s.id WHERE a.event_id=? AND a.withdrawn=0''', (event['id'],)).fetchall()
        platform_ids = {meetup_id(row['url']) for row in rows} - {None}
        group = next((platform_groups[p] for p in platform_ids if p in platform_groups), event['id'])
        groups.setdefault(group, (event, []))[1].extend(rows)
        for platform_id in platform_ids:
            platform_groups[platform_id] = group
    for event, rows in reversed(list(groups.values())):
        if not rows:
            continue
        items = [(row, json.loads(row['payload'])) for row in rows]
        # Posted timestamps order different announcements. Actual revisions use
        # observation time so an edited old announcement can correct newer facts.
        items.sort(key=observation_order)
        # Prefer the latest verified event-page version over an RSS excerpt;
        # older duplicate titles remain history, never competing event cards.
        if any(meetup_id(row['url']) for row in rows):
            items.sort(key=lambda item: (event_page_verified(item[1]), item[0]['last_seen'], item[0]['id']))
        identity = json.loads(event['identity_json'])
        current = {'id': event['id'], **identity, 'first_seen': event['first_seen'],
                   'start': None, 'end': None, 'competition_date': None, 'deadline': None, 'registration_opens': None,
                   'eligibility': None, 'description': None, 'registration_url': None, 'summary': None,
                   'format': 'unknown', 'registration_state': 'unknown', 'date_conflicts': [], 'field_evidence': {}}
        full = [item for item in items if item[1].get('access') != 'search_only']
        fact_items = full or items
        if any(meetup_id(row['url']) for row in rows):
            latest = {}
            for item in fact_items:
                latest[meetup_id(item[0]['url']) or item[0]['url']] = item
            fact_items = list(latest.values())
        # Search titles are discovery evidence, never corrections to a fetched
        # announcement, even when the search result has an earlier timestamp.
        for row, payload in fact_items:
            if payload.get('access') == 'search_only' and current.get('name'):
                continue
            # Old collectors sometimes stored program descriptions in the
            # audience field. Correct the read projection, preserving payloads.
            facts, field_evidence = project_content(payload)
            context_facts, context_proof = parent_schedule(payload)
            facts = {**context_facts, **facts}
            field_evidence = {**context_proof, **field_evidence}
            # A date-only reminder can corroborate existing bounds. Keep their
            # precision; only a different day replaces them as a reschedule.
            new_day = payload['facts'].get('competition_date')
            old_bound = current.get('start') or current.get('end')
            same_day = bool(new_day and manila_day(new_day) and manila_day(old_bound) == manila_day(new_day))
            reset = ('start', 'end') if new_day and not same_day else ('competition_date',) if payload['facts'].get('start') or payload['facts'].get('end') else ()
            if payload['facts'].get('date_conflicts'):
                reset = ('start', 'end', 'competition_date')
            elif any(manila_day(payload['facts'].get(field)) for field in ('start', 'end', 'competition_date')):
                current['date_conflicts'] = []
                current['field_evidence'].pop('date_conflicts', None)
            for field in reset:
                if not payload['facts'].get(field):
                    current[field] = None
                    current['field_evidence'].pop(field, None)
            for k, v in facts.items():
                if k == 'competition_date' and same_day:
                    continue  # The supporting date remains in announcement evidence.
                if v is not None and (v != 'unknown' or k not in current):
                    current[k] = v
                    evidence = field_evidence.get(k)
                    if evidence:
                        current['field_evidence'][k] = evidence
                    else:
                        # Evidence must follow the selected value. An older quote
                        # cannot substantiate a newer announcement's correction.
                        current['field_evidence'].pop(k, None)
            if payload['facts'].get('lifecycle') == 'postponed':
                current['start'] = current['end'] = current['competition_date'] = current['deadline'] = None
                current['date_conflicts'] = []
                current['registration_state'] = 'unknown'
                for field in ('start', 'end', 'competition_date', 'deadline', 'registration_state', 'date_conflicts'):
                    current['field_evidence'].pop(field, None)
        chronological = sorted(items, key=lambda x: observation_order(({**dict(x[0]), 'revision_count': 1}, x[1])))
        full_chronological = [item for item in chronological if item[1].get('access') != 'search_only']
        def primary(item):
            return (item[1].get('official') is not False and
                    (item[0]['source_id'] != 'ctftime' or
                     item[1].get('official') is True and item[1].get('directory_provenance')))
        official = [item for item in full_chronological if primary(item)]
        unverified = [item for item in full_chronological if item[0]['source_id'] != 'ctftime']
        original = (official or unverified or full_chronological or chronological)[0]
        current['announcement_url'] = original[1]['url']
        if original[1].get('access') == 'search_only':
            current['announcement_label'] = 'Search result · verify source'
        elif original[0]['source_id'] == 'ctftime' and not primary(original):
            current['announcement_label'] = 'CTFtime listing'
        elif original[1].get('official') is False:
            current['announcement_label'] = 'Announcement · verify source'
        else:
            current['announcement_label'] = 'Official announcement'
        current['posted_at'] = original[1].get('posted_at')
        if original[1].get('field_evidence', {}).get('posted_at'):
            current['field_evidence']['posted_at'] = original[1]['field_evidence']['posted_at']
        current['last_checked'] = max(row['last_seen'] for row in rows)
        current['status'], current['registration_status'], current['section'] = lifecycle(current, now)
        current['notices'] = []
        dated = [p.get('posted_at') for _, p in items if p.get('posted_at')]
        try:
            latest_post = max(datetime.fromisoformat(d.replace('Z', '+00:00')) for d in dated) if dated else None
            if latest_post and latest_post.tzinfo and (now or datetime.now(timezone.utc)) - latest_post > timedelta(days=45) and current['section'] == 'upcoming':
                current['notices'].append('The latest dated announcement is over 45 days old. Current participation and completion are unconfirmed.')
        except (ValueError, TypeError):
            pass
        if all(p.get('access') == 'search_only' for _, p in items):
            current['notices'].append('Search result only. Full post was not accessed; confirm all details with the organizer.')
            if current['status'] == 'schedule_tba':
                current['status'] = 'undated_lead'
                current['section'] = 'watchlist'
                current['notices'].append('Undated search lead. An edition year is not a confirmed upcoming schedule or open registration.')
        if current['status'] == 'past_date':
            current['notices'].append('The announced event date has passed. Completion is unconfirmed; this is historical coverage, not a current registration opportunity.')
        if current['status'] == 'date_conflict':
            dates = ', '.join(dict.fromkeys(c['date']['raw'] for c in current['date_conflicts']))
            current['notices'].append(f'Conflicting event dates: {dates}. The schedule is unconfirmed; verify with the organizer.')
        if current['status'] == 'end_unconfirmed':
            current['notices'].append('The start has passed, but no confirmed end or completion notice was found.')
        if current['status'] == 'schedule_tba':
            current['notices'].append('Schedule TBA. This listing does not confirm that registration is open.')
        if current.get('deadline') and not current['deadline'].get('timezone'):
            current['notices'].append('The registration deadline has no confirmed time zone or cutoff time. Check the announcement.')
        current['announcements'] = []
        for row, payload in reversed(chronological):
            current['announcements'].append({k: payload.get(k) for k in ('url', 'title', 'kind', 'posted_at', 'access', 'evidence', 'publisher', 'publisher_role', 'index_id')} | {
                'first_seen': row['first_seen'], 'last_seen': row['last_seen'],
                'source_name': row['source_name'], 'revision_count': row['revision_count'],
                'related_links': payload.get('related_links', []),
                'discovery_path': payload.get('discovery_path', []),
                'discovery_query': payload.get('discovery_query'),
                'discovery_queries': discovery_queries(payload),
                'field_evidence': payload.get('field_evidence', {})})
        if window_days and current['section'] == 'upcoming':
            from .domain import in_window, MANILA
            at = now or datetime.now(timezone.utc)
            qualifying = any(in_window(current.get(field), at, window_days)
                             for field in ('start', 'competition_date', 'deadline', 'submission_deadline'))
            # Existing date-only records remain eligible throughout today;
            # displaying them does not invent a midnight start timestamp.
            today = any(current.get(field) and current[field].get('precision') == 'date'
                        and manila_day(current[field]) == at.astimezone(MANILA).date()
                        for field in ('start', 'competition_date', 'deadline', 'submission_deadline'))
            if not (qualifying or today) or (current.get('recurring') and current['registration_status'] not in ('open', 'approval_required')):
                current['section'] = 'watchlist'
                current['notices'].append('Watchlist: no confirmed start or cutoff in the next '
                                          + str(window_days) + ' days, or recurring signup is unverified.')
        # Project from the saved source evidence at read time, so legacy rows
        # gain supported tags without a collector run or a data migration.
        current['topics'], current['topic_evidence'] = project_topics(
            payload for _, payload in reversed(items))
        review_listing(current, items, now)
        output.append(current)
    return output


def source_states(db):
    states = []
    for row in db.execute('SELECT * FROM sources ORDER BY name'):
        state = dict(row)
        state['coverage'] = json.loads(state['coverage'])
        state['enabled'] = bool(state['enabled'])
        states.append(state)
    return states
