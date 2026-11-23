"""The normal CLI and local button share a lock across database path aliases."""
import fcntl
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


collector = importlib.import_module('backend.collect')
ROOT = Path(__file__).resolve().parent.parent


def test_cli_symlink_alias_cannot_bypass_existing_canonical_database_lock(tmp_path):
    target = tmp_path / 'preview.sqlite3'; target.touch()
    alias = tmp_path / 'alias.sqlite3'; alias.symlink_to(target)
    config = tmp_path / 'sources.json'; config.write_text(json.dumps({'sources': []}))
    lock_path = target.with_name(target.name + '.lock')
    with lock_path.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [sys.executable, '-m', 'backend.collect', '--database', str(alias), '--config', str(config)],
            cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert 'Another collector is already running.' in result.stderr
    assert target.stat().st_size == 0  # The SQLite connection was never opened.
    assert not alias.with_name(alias.name + '.lock').exists()


@pytest.mark.parametrize('memory', [False, True])
def test_cli_opens_the_canonical_locked_path_and_preserves_memory_semantics(tmp_path, monkeypatch, capsys, memory):
    target = tmp_path / 'preview.sqlite3'; target.touch()
    alias = tmp_path / 'alias.sqlite3'; alias.symlink_to(target)
    config = tmp_path / 'sources.json'; config.write_text(json.dumps({'sources': []}))
    opened = []
    class Connection:
        closed = False
        def close(self):
            self.closed = True
    connection = Connection()
    def connect(path):
        opened.append(path)
        return connection
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(collector.storage, 'connect', connect)
    monkeypatch.setattr(collector, 'collect', lambda db, sources: {'sources': [{'status': 'ok'}]})
    monkeypatch.setattr(sys, 'argv', ['collect', '--database', ':memory:' if memory else str(alias), '--config', str(config)])
    assert collector.main() == 0
    assert opened == [':memory:' if memory else str(target.resolve())]
    assert connection.closed
    assert json.loads(capsys.readouterr().out)['sources'][0]['status'] == 'ok'
