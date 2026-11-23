"""The local preview helper copies data safely without touching collectors."""
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from backend import prepare_preview as preview


def database(path, names=()):
    conn = sqlite3.connect(path)
    conn.executescript('''
        CREATE TABLE events(id TEXT PRIMARY KEY, identity_json TEXT, first_seen TEXT);
        CREATE TABLE announcements(id INTEGER PRIMARY KEY, event_id TEXT, payload TEXT, first_seen TEXT);
        CREATE TABLE sources(id TEXT PRIMARY KEY, name TEXT);
    ''')
    conn.execute('INSERT INTO sources VALUES (?,?)', ('source', 'Organizer'))
    for index, name in enumerate(names):
        conn.execute('INSERT INTO events VALUES (?,?,?)', (name, '{"edition":"2035"}', '2035-11-22T01:02:03Z'))
        conn.execute('INSERT INTO announcements VALUES (?,?,?,?)', (index, name, json.dumps({'name': name}), '2035-11-22T01:02:03Z'))
    conn.commit(); conn.close()
    return path


def rows(path, table='events'):
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return conn.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
    finally:
        conn.close()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_preview_is_seeded_with_ids_payloads_and_first_seen_unchanged(tmp_path):
    source = database(tmp_path / 'source.sqlite3', ['event-one', 'event-two'])
    destination = tmp_path / 'preview.sqlite3'
    before = digest(source)
    result = preview.prepare_preview(source, destination)
    assert result['action'] == 'seeded'
    assert result['counts'] == {'events': 2, 'announcements': 2, 'sources': 1}
    assert result['backup'] is None
    for table in ('events', 'announcements', 'sources'):
        assert rows(source, table) == rows(destination, table)
    assert digest(source) == before


def test_empty_existing_preview_is_backed_up_and_repaired(tmp_path):
    source = database(tmp_path / 'source.sqlite3', ['event'])
    destination = database(tmp_path / 'preview.sqlite3')
    result = preview.prepare_preview(source, destination)
    backup = Path(result['backup'])
    assert backup.parent == tmp_path / 'preview-backups'
    assert backup.is_file() and rows(backup) == []
    assert rows(destination) == rows(source)
    assert result['counts']['events'] == 1


def test_empty_sqlite_file_is_repaired_after_backup(tmp_path):
    source = database(tmp_path / 'source.sqlite3', ['event'])
    destination = tmp_path / 'preview.sqlite3'; destination.touch()
    result = preview.prepare_preview(source, destination)
    assert Path(result['backup']).exists()
    assert rows(destination) == rows(source)


def test_nonempty_preview_is_reused_without_overwrite_or_source_requirement(tmp_path):
    destination = database(tmp_path / 'preview.sqlite3', ['keep-me'])
    before = digest(destination)
    result = preview.prepare_preview(tmp_path / 'missing-source.sqlite3', destination)
    assert result['action'] == 'reused' and result['counts']['events'] == 1
    assert result['backup'] is None
    assert digest(destination) == before
    assert not (tmp_path / 'preview-backups').exists()


def test_replace_requires_explicit_flag_and_retains_unique_backups(tmp_path):
    source = database(tmp_path / 'source.sqlite3', ['new'])
    destination = database(tmp_path / 'preview.sqlite3', ['old'])
    assert preview.prepare_preview(source, destination)['action'] == 'reused'
    assert rows(destination)[0][0] == 'old'
    result = preview.prepare_preview(source, destination, replace=True)
    assert result['action'] == 'replaced'
    assert rows(Path(result['backup']))[0][0] == 'old'
    assert rows(destination)[0][0] == 'new'
    again = preview.prepare_preview(source, destination, replace=True)
    assert again['backup'] != result['backup']
    assert Path(result['backup']).exists()


@pytest.mark.parametrize('kind', ['missing', 'empty', 'invalid', 'wrong-schema'])
def test_bad_source_fails_clearly_without_creating_or_overwriting_preview(tmp_path, kind):
    source = tmp_path / 'source.sqlite3'
    if kind == 'empty':
        database(source)
    elif kind == 'invalid':
        source.write_text('Not a SQLite database')
    elif kind == 'wrong-schema':
        source.touch()
    destination = database(tmp_path / 'preview.sqlite3')
    before = digest(destination)
    with pytest.raises(preview.PreviewError):
        preview.prepare_preview(source, destination)
    assert digest(destination) == before
    assert not (tmp_path / 'preview-backups').exists()
    missing_destination = tmp_path / 'not-created.sqlite3'
    with pytest.raises(preview.PreviewError):
        preview.prepare_preview(source, missing_destination)
    assert not missing_destination.exists()


@pytest.mark.parametrize('alias', ['same-path', 'symlink', 'hardlink'])
def test_source_cannot_be_destination_even_through_aliases(tmp_path, alias):
    source = database(tmp_path / 'source.sqlite3', ['event'])
    destination = source if alias == 'same-path' else tmp_path / 'alias.sqlite3'
    if alias == 'symlink':
        destination.symlink_to(source)
    elif alias == 'hardlink':
        destination.hardlink_to(source)
    before = digest(source)
    with pytest.raises(preview.PreviewError, match='different files'):
        preview.prepare_preview(source, destination, replace=True)
    assert digest(source) == before


def test_production_destination_is_refused_even_with_other_source(tmp_path, monkeypatch):
    production = database(tmp_path / 'production.sqlite3', ['production'])
    source = database(tmp_path / 'other.sqlite3', ['test'])
    monkeypatch.setattr(preview, 'DEFAULT_SOURCE', production)
    alias = tmp_path / 'alias.sqlite3'; alias.symlink_to(production)
    with pytest.raises(preview.PreviewError, match='production database'):
        preview.prepare_preview(source, alias, replace=True)
    assert rows(production)[0][0] == 'production'


def test_cli_reports_counts_paths_backup_and_readable_failure(tmp_path, capsys):
    source = database(tmp_path / 'source.sqlite3', ['event'])
    destination = tmp_path / 'preview.sqlite3'
    preview.main(['--source', str(source), '--destination', str(destination)])
    result = json.loads(capsys.readouterr().out)
    assert result['counts']['events'] == 1
    assert result['source'] == str(source) and result['destination'] == str(destination)
    with pytest.raises(SystemExit) as error:
        preview.main(['--source', str(tmp_path / 'missing'), '--destination', str(tmp_path / 'new')])
    assert error.value.code == 2
    assert 'Preview preparation failed' in capsys.readouterr().err


def test_committed_wal_records_are_included_without_changing_source_mode(tmp_path):
    source = database(tmp_path / 'source.sqlite3', ['first'])
    writer = sqlite3.connect(source)
    try:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('INSERT INTO events VALUES (?,?,?)', ('uncheckpointed', '{}', '2035-11-22T01:02:03Z'))
        writer.commit()
        destination = tmp_path / 'preview.sqlite3'
        result = preview.prepare_preview(source, destination)
        assert result['counts']['events'] == 2
        assert rows(destination) == rows(source)
        assert writer.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    finally:
        writer.close()


def test_backup_failure_cannot_overwrite_existing_destination(tmp_path, monkeypatch):
    source = database(tmp_path / 'source.sqlite3', ['new'])
    destination = database(tmp_path / 'preview.sqlite3', ['old'])
    before = digest(destination)
    def failed_backup(*args):
        raise OSError('Backup directory unavailable')
    monkeypatch.setattr(preview, '_backup', failed_backup)
    with pytest.raises(preview.PreviewError, match='Backup directory unavailable'):
        preview.prepare_preview(source, destination, replace=True)
    assert digest(destination) == before
