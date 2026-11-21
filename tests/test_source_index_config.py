"""Publisher-index and evidence-history regressions; fictional sources only."""
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.adapters import Result
from backend.collect import collect
from backend.db import connect, ingest, register_sources, source_states
from backend.extract import extract
from backend.source_index import SourceConfigurationError, load_sources


SOURCE = {'id': 'kestrel', 'name': 'Kestrel announcements', 'kind': 'rss',
          'url': 'https://kestrel.example/feed/', 'organizer': 'Kestrel Club',
          'organizer_key': 'kestrel'}
PUBLISHER = {'id': 'kestrel-index', 'name': 'Kestrel Club', 'role': 'both',
             'coverage': ['Luzon', 'Online'], 'enabled': True,
             'status': 'active', 'source_id': 'kestrel'}
NOW = datetime(2031, 2, 1, tzinfo=timezone.utc)


def write_config(tmp_path, publishers=None, sources=None):
    config = {'sources': deepcopy([SOURCE] if sources is None else sources)}
    if publishers is not None:
        config['publisher_index'] = 'publishers.json'
        (tmp_path / 'publishers.json').write_text(json.dumps({'publishers': publishers}))
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps(config))
    return path


def test_legacy_configuration_remains_usable_without_index(tmp_path):
    assert load_sources(write_config(tmp_path)) == [SOURCE]


def test_index_reference_and_new_monitor_merge_with_legacy_sources(tmp_path):
    supplemental = {**SOURCE, 'id': 'supplemental'}
    new_monitor = {**SOURCE, 'id': 'new-monitor', 'url': 'https://new.example/feed/'}
    publisher = {**PUBLISHER, 'id': 'new-publisher', 'name': 'Another Publisher',
                 'role': 'resharer', 'enabled': False, 'status': 'candidate',
                 'reason': 'Advance announcement has not been verified',
                 'monitor': new_monitor}
    del publisher['source_id']
    sources = load_sources(write_config(tmp_path, [PUBLISHER, publisher], [SOURCE, supplemental]))
    assert [source['id'] for source in sources] == ['kestrel', 'supplemental', 'new-monitor']
    assert sources[0]['publisher_role'] == 'both'
    assert sources[0]['publisher_name'] == 'Kestrel Club'
    assert sources[0]['coverage'] == ['Luzon', 'Online']
    assert sources[0]['index_id'] == 'kestrel-index'
    assert sources[1] == supplemental
    assert sources[2]['enabled'] is False
    assert sources[2]['index_reason'] == publisher['reason']


@pytest.mark.parametrize('publishers', [
    [{**PUBLISHER, 'source_id': 'missing'}],
    [{**PUBLISHER, 'monitor': SOURCE}],
    [{key: value for key, value in PUBLISHER.items() if key != 'source_id'}],
    [{**PUBLISHER, 'role': 'unknown'}],
    [{**PUBLISHER, 'enabled': 'yes'}],
    [PUBLISHER, PUBLISHER],
    [PUBLISHER, {**PUBLISHER, 'id': 'other-publisher'}],
])
def test_invalid_publisher_configuration_fails_before_collection(tmp_path, publishers):
    with pytest.raises(SourceConfigurationError):
        load_sources(write_config(tmp_path, publishers))


def test_unknown_adapter_rejected_even_when_disabled(tmp_path):
    source = {**SOURCE, 'kind': 'not-a-real-adapter', 'enabled': False}
    with pytest.raises(SourceConfigurationError, match='Unknown source adapter'):
        load_sources(write_config(tmp_path, sources=[source]))


def test_unknown_monitor_adapter_rejected(tmp_path):
    publisher = {key: value for key, value in PUBLISHER.items() if key != 'source_id'}
    publisher['monitor'] = {**SOURCE, 'id': 'other', 'kind': 'not-a-real-adapter'}
    with pytest.raises(SourceConfigurationError, match='Unknown source adapter'):
        load_sources(write_config(tmp_path, [publisher]))


def test_disabled_source_never_fetches_and_retains_last_success(tmp_path):
    sources = load_sources(write_config(tmp_path, [PUBLISHER]))
    db = connect(':memory:')
    calls = []

    def adapter(*args):
        calls.append(args)
        result = Result()
        result.decisions = [{'url': 'https://kestrel.example/news/', 'accepted': False,
                             'reason': 'No competition'}]
        return result

    first = collect(db, sources, adapters={'rss': adapter}, now=NOW)
    prior_success = source_states(db)[0]['last_success']
    assert first['sources'][0]['decisions'][0]['reason'] == 'No competition'
    disabled = [{**sources[0], 'enabled': False, 'index_reason': 'Access under review'}]
    second = collect(db, disabled, adapters={'rss': adapter}, now=NOW)
    assert len(calls) == 1
    assert second['sources'][0]['status'] == 'disabled'
    assert second['sources'][0]['publisher_role'] == 'both'
    assert second['sources'][0]['publisher'] == 'Kestrel Club'
    state = source_states(db)[0]
    assert state['last_success'] == prior_success
    assert state['status'] == 'disabled'
    assert state['enabled'] is False
    assert state['coverage'] == ['Luzon', 'Online']
    assert state['message'] == 'Access under review'
    register_sources(db, sources)
    assert source_states(db)[0]['status'] == 'not_run'
    assert source_states(db)[0]['last_success'] == prior_success
    db.close()


def test_revision_keeps_registration_evidence_at_each_observation():
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    ann = extract('Nebula CTF 2031',
                  'Registration open.\nRegistration deadline: March 5, 2031',
                  'https://kestrel.example/nebula/', SOURCE)
    ingest(db, SOURCE['id'], ann, '2031-02-01T00:00:00+00:00')
    changed = extract('Nebula CTF 2031',
                      'Registration closed.\nRegistration deadline: March 3, 2031',
                      ann['url'], SOURCE)
    ingest(db, SOURCE['id'], changed, '2031-02-02T00:00:00+00:00')
    rows = db.execute('SELECT * FROM revisions ORDER BY id').fetchall()
    assert len(rows) == 2
    assert json.loads(rows[0]['facts_json'])['registration_state'] == 'open'
    assert 'March 5, 2031' in json.loads(rows[0]['evidence_json'])['deadline']['quote']
    assert json.loads(rows[1]['facts_json'])['registration_state'] == 'closed'
    assert 'March 3, 2031' in json.loads(rows[1]['evidence_json'])['deadline']['quote']
    assert db.execute('SELECT first_seen FROM events').fetchone()[0] == '2031-02-01T00:00:00+00:00'
    db.close()


def test_additive_migration_does_not_rewrite_prior_evidence_or_success(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    legacy = sqlite3.connect(path)
    legacy.executescript('''
        CREATE TABLE sources (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, kind TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'not_run', last_success TEXT, last_attempt TEXT,
          message TEXT NOT NULL DEFAULT '', discovered INTEGER NOT NULL DEFAULT 0,
          accepted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE revisions (
          id INTEGER PRIMARY KEY, announcement_id INTEGER NOT NULL,
          observed_at TEXT NOT NULL, facts_json TEXT NOT NULL
        );
        INSERT INTO sources(id,name,url,kind,status,last_success)
          VALUES('kestrel','Kestrel','https://kestrel.example/feed/','rss','ok','2030-01-01');
        INSERT INTO revisions VALUES(1,1,'2030-01-01','{"registration_state":"open"}');
    ''')
    legacy.commit()
    legacy.close()
    migrated = connect(path)
    row = migrated.execute('SELECT * FROM revisions').fetchone()
    assert row['facts_json'] == '{"registration_state":"open"}'
    assert row['observed_at'] == '2030-01-01'
    assert row['evidence_json'] == '{}'
    assert source_states(migrated)[0]['last_success'] == '2030-01-01'
    assert source_states(migrated)[0]['coverage'] == []
    migrated.close()
    # Migration is idempotent and does not require rebuilding the database.
    connect(path).close()
