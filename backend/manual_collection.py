"""Opt-in local preview control for the existing collector CLI."""
from __future__ import annotations

import ipaddress
import json
import os
from contextlib import closing
from pathlib import Path
import secrets
import signal
import sqlite3
import subprocess
import sys
import threading
from urllib.parse import urlsplit

from .domain import utcnow
from .source_index import load_sources

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 20 * 60


def local_request(request):
    """Do not trust forwarded headers or expose the token to arbitrary Hosts."""
    try:
        peer = ipaddress.ip_address(request.remote_addr or '')
        host = urlsplit('http://' + request.host).hostname
        return peer.is_loopback and (host == 'localhost' or ipaddress.ip_address(host or '').is_loopback)
    except ValueError:
        return False


def safe_preview_database(database):
    if not database or str(database) == ':memory:' or str(database).startswith('file:'):
        return False
    target = Path(database).resolve()
    production = ROOT / 'data/ctfinder.sqlite3'
    if target == production.resolve():
        return False
    try:
        if target.exists() and production.exists() and target.samefile(production):
            return False
    except OSError:
        return False
    return True


class ManualCollection:
    def __init__(self, database, config, *, enabled=False):
        self.enabled = bool(enabled and safe_preview_database(database))
        self.database = Path(database).resolve() if self.enabled else None
        self.config = Path(config).resolve()
        self.token = secrets.token_urlsafe(32) if self.enabled else None
        self.lock = threading.RLock()
        self.thread = None
        self.process = None
        self.closing = False
        self.source_ids = []
        self.status = {'enabled': self.enabled, 'state': 'idle', 'started_at': None,
                       'finished_at': None, 'completed_sources': 0, 'total_sources': 0,
                       'message': 'Ready to fetch using the configured sources.'}

    def capabilities(self):
        return {'enabled': self.enabled, **({'token': self.token} if self.enabled else {})}

    def _counts(self):
        with closing(sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=1)) as db:
            events = db.execute('SELECT count(DISTINCT event_id) FROM announcements WHERE withdrawn=0').fetchone()[0]
            announcements = db.execute('SELECT count(*) FROM announcements WHERE withdrawn=0').fetchone()[0]
            completed = {row[0] for row in db.execute(
                'SELECT id FROM sources WHERE last_attempt >= ?', (self.status['started_at'],))}
        return events, announcements, len(completed.intersection(self.source_ids))

    def snapshot(self):
        with self.lock:
            if self.status['state'] == 'running':
                try:
                    events, announcements, completed = self._counts()
                    self.status.update(events=events, announcements=announcements, completed_sources=completed)
                except sqlite3.Error:
                    pass  # A source commit can briefly hold the database lock.
            return dict(self.status)

    def start(self):
        with self.lock:
            if self.status['state'] == 'running':
                return False
            if self.closing:
                raise ValueError('The preview server is stopping.')
            # Recheck aliases before every launch, and never accept paths from HTTP.
            if not self.enabled or not safe_preview_database(self.database):
                raise ValueError('Manual collection requires a separate preview database.')
            sources = load_sources(self.config)
            self.source_ids = [source['id'] for source in sources]
            if not any(source.get('enabled') is not False and source['kind'] != 'restricted' for source in sources):
                raise ValueError('No enabled collector sources are configured.')
            directory = self.database.parent / 'manual-fetch'
            directory.mkdir(parents=True, exist_ok=True)
            started = utcnow()
            self.status = {'enabled': True, 'state': 'running', 'started_at': started,
                           'finished_at': None, 'completed_sources': 0,
                           'total_sources': len(sources), 'message': 'Fetching public sources…'}
            stem = started.replace(':', '-').replace('+', '_') + '-' + secrets.token_hex(4)
            self.report_path = directory / (stem + '.json')
            self.log_path = directory / (stem + '.log')
            self.thread = threading.Thread(target=self._run, name='local-manual-collection', daemon=True)
            try:
                self.thread.start()
            except RuntimeError as exc:
                self.status.update(state='failed', finished_at=utcnow(), message='Collection worker could not start.')
                raise ValueError('Collection worker could not start') from exc
            return True

    def close(self):
        """Stop only this server's child process group on normal shutdown."""
        with self.lock:
            self.closing = True
            process, thread = self.process, self.thread
        if process is not None and process.poll() is None:
            self._terminate(process)
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=5)

    @staticmethod
    def _terminate(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def _run(self):
        command = [sys.executable, '-m', 'backend.collect', '--database', str(self.database),
                   '--config', str(self.config), '--report', str(self.report_path)]
        result, message, report = 'failed', 'Collector could not finish. Previous saved listings remain available.', {}
        try:
            with self.log_path.open('w') as log:
                with self.lock:
                    if self.closing:
                        return
                    process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                               stdin=subprocess.DEVNULL, start_new_session=True)
                    self.process = process
                try:
                    code = process.wait(timeout=TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    self._terminate(process)
                    message = 'Collection exceeded the 20-minute limit and was stopped. Completed source updates remain saved.'
                else:
                    if self.report_path.exists():
                        loaded = json.loads(self.report_path.read_text())
                        if (not isinstance(loaded, dict) or not isinstance(loaded.get('sources'), list)
                                or not all(isinstance(source, dict) for source in loaded['sources'])):
                            raise ValueError('Invalid collector report')
                        report = loaded
                    checked = report.get('sources', [])
                    if code == 0 and any(source.get('status') in ('ok', 'partial') for source in checked):
                        result = 'completed'
                        message = 'Collection completed. Saved listings have been refreshed.'
                    elif checked:
                        message = 'No source check succeeded. Previous saved listings remain available; see source coverage for failures.'
                    else:
                        message = f'Collector exited without a completed report (exit {code}). See the saved local log.'
        except (OSError, ValueError, TypeError) as exc:
            message = f'{type(exc).__name__}: collector could not complete. Previous saved listings remain available.'
        finally:
            with self.lock:
                if self.closing:
                    result = 'failed'
                    message = 'Collection stopped with the local preview server. Completed source updates remain saved.'
                try:
                    events, announcements, completed = self._counts()
                    self.status.update(events=events, announcements=announcements, completed_sources=completed)
                except sqlite3.Error:
                    pass
                checked = report.get('sources', []) if isinstance(report, dict) else []
                warnings = sum(source.get('status') not in ('ok', 'disabled') for source in checked)
                self.status.update(state=result, finished_at=utcnow(), warning_count=warnings, message=message)
                if result == 'completed' and warnings:
                    self.status['message'] = 'Collection completed with source warnings. Saved listings have been refreshed; see source coverage.'
                # Keep reports/logs and the final status beside the preview DB,
                # not in ephemeral /tmp, without persisting the browser token.
                status_path = self.report_path.with_suffix('.status.json')
                try:
                    status_path.write_text(json.dumps(self.status, indent=2) + '\n')
                except OSError:
                    pass
