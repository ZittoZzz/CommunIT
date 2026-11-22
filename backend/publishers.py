"""Evidence-backed publisher candidates discovered by recurring monitors.

Candidates do not become network inputs automatically. An operator can qualify
one recurring source once, add it to the existing source index, and associate
its stable profile URL/account with ``publisher_identity_urls`` or
``publisher_account_ids``. A successful configured monitor then links that
candidate to the index. No individual event submissions are needed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .domain import canonical_url, utcnow


ROLES = {'host', 'co-organizer', 'organizer', 'sponsor', 'partner', 'publisher', 'resharer',
         'contributor', 'challenge-partner', 'community-partner'}


def ensure_schema(db):
    """Additive, transaction-safe schema creation; never touches event history."""
    statements = [
        '''CREATE TABLE IF NOT EXISTS publisher_candidates (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, public_url TEXT, account_id TEXT,
          identity_status TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'candidate', index_id TEXT, monitor_source_id TEXT,
          recurring_url TEXT, verified_at TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS publisher_identity_keys (
          identity_key TEXT PRIMARY KEY,
          publisher_id TEXT NOT NULL REFERENCES publisher_candidates(id)
        )''',
        '''CREATE TABLE IF NOT EXISTS publisher_relationships (
          id TEXT PRIMARY KEY, publisher_id TEXT NOT NULL REFERENCES publisher_candidates(id),
          source_id TEXT NOT NULL, event_id TEXT REFERENCES events(id),
          announcement_url TEXT NOT NULL, role TEXT NOT NULL,
          relationship_status TEXT NOT NULL, name TEXT NOT NULL,
          evidence_json TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
        )''',
    ]
    for statement in statements:
        db.execute(statement)


def _stamp(now):
    return now.isoformat() if isinstance(now, datetime) else now or utcnow()


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _source_url(value):
    if not isinstance(value, str):
        return None
    try:
        return canonical_url(value)
    except ValueError:
        return None


def identity_url(value):
    """Normalize tracking and documented account URL shapes, not arbitrary paths.

    A source adapter is responsible for supplying a publisher/profile URL. We
    deliberately do not turn an event permalink into an organizer homepage.
    Arbitrary website paths keep their case and trailing slash semantics.
    """
    value = _source_url(value)
    if not value:
        return None
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    path = parsed.path
    # Account paths are publicly equivalent on these known platform domains.
    if host in ('luma.com', 'www.luma.com', 'lu.ma', 'www.lu.ma'):
        if re.fullmatch(r'/user/[^/]+/?', path):
            return urlunsplit(('https', 'luma.com', path.rstrip('/'), '', ''))
    if host in ('facebook.com', 'www.facebook.com', 'm.facebook.com'):
        query = dict(parse_qsl(parsed.query))
        if path == '/profile.php':
            if query.get('id', '').isdigit():
                return 'https://www.facebook.com/profile.php?' + urlencode({'id': query['id']})
            return None
        if re.fullmatch(r'/groups/\d+/?', path):
            return 'https://www.facebook.com' + path.rstrip('/')
        username = path.strip('/').lower()
        reserved = {'share', 'sharer', 'watch', 'reel', 'reels', 'events', 'groups',
                    'login', 'logout', 'photo', 'photos', 'video', 'videos', 'posts',
                    'story', 'stories', 'permalink', 'plugins', 'marketplace', 'help'}
        if (re.fullmatch(r'/[A-Za-z0-9.]+/?', path) and username not in reserved and
                not username.endswith(('.php', '.html', '.htm')) and
                not any(key in query for key in ('story_fbid', 'fbid', 'post_id'))):
            # Dots are valid in account usernames. Full post/share paths never
            # establish a publisher profile and are not reduced to their owner.
            return 'https://www.facebook.com/' + username
        return None
    return value


def _account(value):
    if isinstance(value, dict):
        namespace, identifier = value.get('namespace'), value.get('id')
        if isinstance(namespace, str) and isinstance(identifier, str):
            value = namespace + ':' + identifier
    if not isinstance(value, str) or ':' not in value:
        return None
    namespace, identifier = value.strip().split(':', 1)
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]*', namespace) or not identifier.strip():
        return None
    return namespace.lower() + ':' + identifier.strip()


def _identity_keys(lead):
    url = identity_url(lead.get('url'))
    account = _account(lead.get('account_id'))
    keys = []
    if url:
        keys.append('url:' + url)
    if account:
        keys.append('account:' + account)
    return url, account, keys


def harvest(db, source_id, leads, *, event_id=None, announcement_url=None, now=None):
    """Retain relationship leads; only callers can establish an accepted event.

    With ``event_id=None`` these are source-only publisher leads, never event
    announcements. Missing stable identities are scoped to their evidence URL
    and name, avoiding an unsafe name-only merge across unrelated publishers.
    The caller owns the surrounding ingestion transaction.
    """
    ensure_schema(db)
    stamp = _stamp(now)
    result = {'accepted': 0, 'new_candidates': 0, 'new_relationships': 0, 'rejected': 0, 'rejections': []}
    for lead in leads or []:
        if not isinstance(lead, dict):
            result['rejections'].append({'reason': 'Publisher lead is not an object'})
            continue
        name = lead.get('name')
        role = str(lead.get('role') or '').strip().lower().replace('_', '-')
        evidence = lead.get('evidence')
        if not isinstance(evidence, dict):
            evidence = {}
        # Evidence may be an individual social post. Keep that exact source
        # canonicalization separate from the stricter publisher-profile rules.
        evidence_url = _source_url(evidence.get('url'))
        quote = evidence.get('quote')
        if (not isinstance(name, str) or not name.strip() or role not in ROLES or
                not evidence_url or not isinstance(quote, str) or not quote.strip()):
            result['rejections'].append({'name': name if isinstance(name, str) else None,
                                       'reason': 'Publisher name, recognized role and linked relationship evidence are required'})
            continue
        name = name.strip()
        url, account, keys = _identity_keys(lead)
        identity_status = 'stable' if keys else 'evidence_only'
        if not keys:
            # Role is not identity: the same named publisher in one announcement
            # can be both its host and sponsor without creating two candidates.
            keys = ['evidence:' + _digest(evidence_url + '\n' + name.casefold())]
        placeholders = ','.join('?' for _ in keys)
        matches = {row['publisher_id'] for row in db.execute(
            f'SELECT publisher_id FROM publisher_identity_keys WHERE identity_key IN ({placeholders})', keys)}
        if len(matches) > 1:
            result['rejections'].append({'name': name, 'reason': 'Conflicting existing stable identities; review required'})
            continue
        publisher_id = next(iter(matches)) if matches else _digest(sorted(keys)[0])
        existed = db.execute('SELECT id FROM publisher_candidates WHERE id=?', (publisher_id,)).fetchone()
        db.execute('''INSERT INTO publisher_candidates
          (id,name,public_url,account_id,identity_status,first_seen,last_seen)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
          last_seen=excluded.last_seen,
          public_url=COALESCE(publisher_candidates.public_url,excluded.public_url),
          account_id=COALESCE(publisher_candidates.account_id,excluded.account_id)''',
                   (publisher_id, name, url, account, identity_status, stamp, stamp))
        for key in keys:
            db.execute('INSERT OR IGNORE INTO publisher_identity_keys VALUES(?,?)', (key, publisher_id))
        status = lead.get('relationship_status') or ('competition_confirmed' if event_id else 'publisher_lead')
        # Retain revised evidence instead of replacing an earlier quote. Repeats
        # with exactly the same evidence update last_seen without duplicating it.
        retained_evidence = {**evidence, 'url': evidence_url, 'quote': quote.strip()}
        encoded = json.dumps(retained_evidence, sort_keys=True, ensure_ascii=False)
        related_url = _source_url(announcement_url) or evidence_url
        relationship_id = _digest(json.dumps([publisher_id, source_id, event_id, related_url,
                                               role, status, encoded], ensure_ascii=False))
        previous = db.execute('SELECT id FROM publisher_relationships WHERE id=?', (relationship_id,)).fetchone()
        db.execute('''INSERT INTO publisher_relationships
          (id,publisher_id,source_id,event_id,announcement_url,role,relationship_status,name,
           evidence_json,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen''',
                   (relationship_id, publisher_id, source_id, event_id, related_url, role, status,
                    name, encoded, stamp, stamp))
        result['accepted'] += 1
        result['new_candidates'] += int(not existed)
        result['new_relationships'] += int(not previous)
    result['rejected'] = len(result['rejections'])
    return result


def _configured_keys(source):
    values = [source.get('publisher_url'), source.get('url'), *(source.get('publisher_identity_urls') or [])]
    accounts = [source.get('publisher_account_id'), *(source.get('publisher_account_ids') or [])]
    keys = {'url:' + normalized for value in values if (normalized := identity_url(value))}
    keys.update('account:' + normalized for value in accounts if (normalized := _account(value)))
    return sorted(keys)


def sync_configured_publishers(db, sources, *, now=None):
    """Link existing candidates to explicitly configured, verified index monitors.

    Exact identity aliases, an active index entry and an observed successful
    check are all required for activation. Display-name similarity is ignored.
    This never adds candidates or edits the source configuration.
    """
    ensure_schema(db)
    linked = []
    for source in sources:
        if not source.get('index_id'):
            continue
        keys = _configured_keys(source)
        if not keys:
            continue
        placeholders = ','.join('?' for _ in keys)
        matches = {row['publisher_id'] for row in db.execute(
            f'SELECT publisher_id FROM publisher_identity_keys WHERE identity_key IN ({placeholders})', keys)}
        if len(matches) != 1:
            continue
        publisher_id = next(iter(matches))
        state = db.execute('SELECT last_success FROM sources WHERE id=?', (source['id'],)).fetchone()
        active = bool(source.get('enabled', True) and source.get('index_status') == 'active' and
                      state and state['last_success'])
        db.execute('''UPDATE publisher_candidates SET status=?,index_id=?,monitor_source_id=?,
          recurring_url=?,verified_at=CASE WHEN ? THEN COALESCE(verified_at,?) ELSE verified_at END
          WHERE id=?''',
                   ('active' if active else 'candidate', source['index_id'], source['id'], source['url'],
                    active, state['last_success'] if state else None, publisher_id))
        linked.append({'publisher_id': publisher_id, 'source_id': source['id'], 'active': active})
    return linked


def publisher_summaries(db):
    """Read-only candidates and evidence suitable for collection reports/review."""
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='publisher_candidates'").fetchone()
    if not exists:
        return []
    output = []
    for row in db.execute('SELECT * FROM publisher_candidates ORDER BY first_seen,id'):
        record = dict(row)
        relationships = []
        for related in db.execute('SELECT * FROM publisher_relationships WHERE publisher_id=? ORDER BY first_seen,id', (row['id'],)):
            item = dict(related)
            item['evidence'] = json.loads(item.pop('evidence_json'))
            relationships.append(item)
        record['roles'] = sorted({item['role'] for item in relationships})
        record['names'] = sorted({item['name'] for item in relationships})
        record['event_ids'] = sorted({item['event_id'] for item in relationships if item['event_id']})
        record['relationships'] = relationships
        record['identity_keys'] = [item['identity_key'] for item in db.execute(
            'SELECT identity_key FROM publisher_identity_keys WHERE publisher_id=? ORDER BY identity_key', (row['id'],))]
        output.append(record)
    return output
