"""The development fetch control delegates to the CLI; tests never fetch pages."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import threading

import pytest

from backend import manual_collection as module
from backend.app import create_app


@pytest.fixture
def preview(tmp_path, monkeypatch):
    config = tmp_path / 'sources.json'
    config.write_text(json.dumps({'sources': [
        {'id': 'sample', 'name': 'Sample', 'kind': 'html', 'url': 'https://organizer.example/events'}]}))
    monkeypatch.setenv('CTF_SOURCES', str(config))
    monkeypatch.setenv('CTF_ENABLE_MANUAL_FETCH', '1')
    app = create_app(tmp_path / 'preview.sqlite3')
    return app, app.test_client(), config


def authorization(client):
    return {'X-Collection-Token': client.get('/api/events').json['manual_collection']['token']}


def fake_process(monkeypatch, *, statuses=('ok',), code=0, hold=None, timeout=False, started=None):
    commands = []
    class Process:
        pid = 987654321
        def __init__(self, command, **kwargs):
            commands.append((command, kwargs))
            self.returncode = None
            self.report = Path(command[command.index('--report') + 1])
            if started:
                started.set()
        def poll(self):
            return self.returncode
        def wait(self, timeout=None):
            if hold:
                assert hold.wait(5)
            if timeout and timed_out:
                raise subprocess.TimeoutExpired(commands[-1][0], timeout)
            self.report.write_text(json.dumps({'sources': [{'id': str(i), 'status': status}
                for i, status in enumerate(statuses)], 'events': 0, 'announcements': 0}))
            self.returncode = code
            return code
    timed_out = timeout
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    return commands


def finish(app):
    app.extensions['manual_collection'].thread.join(5)
    assert not app.extensions['manual_collection'].thread.is_alive()


def test_default_disabled_even_with_an_explicit_preview(tmp_path, monkeypatch):
    monkeypatch.delenv('CTF_ENABLE_MANUAL_FETCH', raising=False)
    config = tmp_path / 'sources.json'; config.write_text('{"sources": []}')
    monkeypatch.setenv('CTF_SOURCES', str(config))
    client = create_app(tmp_path / 'preview.sqlite3').test_client()
    assert client.get('/api/events').json['manual_collection'] == {'enabled': False}
    assert client.get('/api/collection').status_code == 404
    assert client.post('/api/collection', json={}).status_code == 404


def test_production_aliases_and_missing_explicit_database_are_refused(tmp_path, monkeypatch):
    root = tmp_path / 'repo'; (root / 'data').mkdir(parents=True)
    production = root / 'data/ctfinder.sqlite3'; production.touch()
    monkeypatch.setattr(module, 'ROOT', root)
    alias = tmp_path / 'alias.sqlite3'; alias.symlink_to(production)
    hardlink = tmp_path / 'hard.sqlite3'; os.link(production, hardlink)
    for target in (None, ':memory:', production, alias, hardlink):
        manager = module.ManualCollection(target, tmp_path / 'sources.json', enabled=True)
        assert not manager.enabled
        assert manager.token is None


def test_token_and_loopback_gate_and_request_cannot_choose_database(preview, monkeypatch):
    app, client, _ = preview
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch'))
    headers = authorization(client)
    assert client.post('/api/collection', json={}).status_code == 403
    assert client.post('/api/collection', json={}, headers={'X-Collection-Token': 'wrong'}).status_code == 403
    assert client.post('/api/collection', json={}, headers=headers,
                       environ_overrides={'REMOTE_ADDR': '192.0.2.20'}).status_code == 403
    assert client.get('/api/events', environ_overrides={'REMOTE_ADDR': '192.0.2.20'}).json['manual_collection'] == {'enabled': False}
    assert client.get('/api/events', headers={'Host': 'attacker.example'}).json['manual_collection'] == {'enabled': False}
    assert client.get('/api/collection', headers={'Host': 'attacker.example'}).status_code == 403
    assert client.post('/api/collection', data='{}', headers=headers).status_code == 400
    assert client.post('/api/collection', json={'database': '/somewhere/else'}, headers=headers).status_code == 400


def test_cli_arguments_overlap_and_completed_report_are_preserved(preview, monkeypatch):
    app, client, config = preview
    hold = threading.Event()
    commands = fake_process(monkeypatch, statuses=('ok', 'blocked'), hold=hold)
    headers = authorization(client)
    first = client.post('/api/collection', json={}, headers=headers)
    assert first.status_code == 202
    assert first.json['state'] == 'running'
    assert client.post('/api/collection', json={}, headers=headers).status_code == 409
    manager = app.extensions['manual_collection']
    with sqlite3.connect(manager.database) as db:
        db.execute('UPDATE sources SET last_attempt=? WHERE id=?', (manager.status['started_at'], 'sample'))
    assert client.get('/api/collection').json['completed_sources'] == 1
    hold.set(); finish(app)
    status = client.get('/api/collection').json
    assert status['state'] == 'completed'
    assert status['warning_count'] == 1
    assert status['finished_at']
    assert status['events'] == status['announcements'] == 0
    command, kwargs = commands[0]
    assert command[:3] == [module.sys.executable, '-m', 'backend.collect']
    assert command[command.index('--database') + 1] == str(manager.database)
    assert command[command.index('--config') + 1] == str(config)
    assert kwargs['stdin'] == subprocess.DEVNULL
    assert kwargs['start_new_session'] is True
    assert manager.report_path.parent == manager.database.parent / 'manual-fetch'
    assert manager.report_path.exists() and manager.log_path.exists()
    assert manager.report_path.with_suffix('.status.json').exists()
    assert manager.token not in manager.report_path.with_suffix('.status.json').read_text()


@pytest.mark.parametrize(('statuses', 'code'), [(('blocked', 'error'), 1), (('error',), 0)])
def test_all_source_failures_never_report_success(preview, monkeypatch, statuses, code):
    app, client, _ = preview
    fake_process(monkeypatch, statuses=statuses, code=code)
    assert client.post('/api/collection', json={}, headers=authorization(client)).status_code == 202
    finish(app)
    status = client.get('/api/collection').json
    assert status['state'] == 'failed'
    assert status['warning_count'] == len(statuses)
    assert 'No source check succeeded' in status['message']


def test_timeout_stops_job_and_reports_saved_partial_updates(preview, monkeypatch):
    app, client, _ = preview
    fake_process(monkeypatch, timeout=True)
    killed = []
    monkeypatch.setattr(module.ManualCollection, '_terminate', staticmethod(lambda process: killed.append(process.pid)))
    assert client.post('/api/collection', json={}, headers=authorization(client)).status_code == 202
    finish(app)
    status = client.get('/api/collection').json
    assert killed == [987654321]
    assert status['state'] == 'failed'
    assert '20-minute limit' in status['message']


def test_empty_configuration_does_not_start(preview, monkeypatch):
    app, client, config = preview
    config.write_text('{"sources": []}')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch'))
    assert client.post('/api/collection', json={}, headers=authorization(client)).status_code == 400
    assert client.get('/api/collection').json['state'] == 'idle'


def test_unwritable_artifact_path_does_not_leave_job_running(preview, monkeypatch):
    app, client, _ = preview
    artifact_path = app.extensions['manual_collection'].database.parent / 'manual-fetch'
    artifact_path.write_text('A regular file prevents directory creation.')
    headers = authorization(client)
    assert client.post('/api/collection', json={}, headers=headers).status_code == 400
    assert client.get('/api/collection').json['state'] == 'idle'
    artifact_path.unlink()
    fake_process(monkeypatch)
    assert client.post('/api/collection', json={}, headers=headers).status_code == 202
    finish(app)
    assert client.get('/api/collection').json['state'] == 'completed'


def test_process_launch_error_finishes_and_can_retry(preview, monkeypatch):
    app, client, _ = preview
    def denied(*args, **kwargs):
        raise OSError('A private implementation detail must not leak.')
    monkeypatch.setattr(module.subprocess, 'Popen', denied)
    headers = authorization(client)
    assert client.post('/api/collection', json={}, headers=headers).status_code == 202
    finish(app)
    status = client.get('/api/collection').json
    assert status['state'] == 'failed'
    assert 'private implementation detail' not in status['message']
    fake_process(monkeypatch)
    assert client.post('/api/collection', json={}, headers=headers).status_code == 202
    finish(app)
    assert client.get('/api/collection').json['state'] == 'completed'


def test_progress_reader_closes_sqlite_connection(preview, monkeypatch):
    app, _, _ = preview
    manager = app.extensions['manual_collection']
    reader = sqlite3.connect(manager.database)
    monkeypatch.setattr(module.sqlite3, 'connect', lambda *args, **kwargs: reader)
    manager._counts()
    with pytest.raises(sqlite3.ProgrammingError, match='closed database'):
        reader.execute('SELECT 1')


def test_shutdown_cancels_only_owned_child_and_finishes_status(preview, monkeypatch):
    app, client, _ = preview
    hold = threading.Event()
    started = threading.Event()
    fake_process(monkeypatch, hold=hold, started=started)
    killed = []
    def terminate(process):
        killed.append(process.pid)
        process.returncode = -9
        hold.set()
    monkeypatch.setattr(module.ManualCollection, '_terminate', staticmethod(terminate))
    assert client.post('/api/collection', json={}, headers=authorization(client)).status_code == 202
    manager = app.extensions['manual_collection']
    assert started.wait(5)
    # The worker acquires the same lock while publishing its child handle.
    with manager.lock:
        assert manager.process is not None
    manager.close()
    finish(app)
    assert killed == [987654321]
    assert manager.snapshot()['state'] == 'failed'
    assert 'stopped with the local preview server' in manager.snapshot()['message']


@pytest.mark.parametrize('payload', [{'sources': None}, {'sources': [None]}, []])
def test_malformed_report_is_failed_not_stuck_running(preview, monkeypatch, payload):
    app, client, _ = preview
    class Process:
        def __init__(self, command, **kwargs):
            self.report = Path(command[command.index('--report') + 1])
        def wait(self, timeout=None):
            self.report.write_text(json.dumps(payload)); return 0
        def poll(self):
            return 0
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    assert client.post('/api/collection', json={}, headers=authorization(client)).status_code == 202
    finish(app)
    assert client.get('/api/collection').json['state'] == 'failed'
