"""Prepare a local SQLite preview without running collectors or registering sources."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / 'data/ctfinder.sqlite3'
DEFAULT_DESTINATION = ROOT / 'data/local-preview.sqlite3'


class PreviewError(RuntimeError):
    pass


def _same_file(left, right):
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and os.path.samefile(left, right))


def _readonly(path):
    if not path.is_file():
        raise PreviewError(f'Database does not exist: {path}')
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)


def _counts(conn, path, *, allow_empty=False):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = ('events', 'announcements', 'sources')
    if not tables and allow_empty:
        return {name: 0 for name in required}
    if missing := set(required) - tables:
        raise PreviewError(f'Invalid preview database {path}: missing tables {", ".join(sorted(missing))}')
    return {name: conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in required}


def _backup(conn, destination):
    directory = destination.parent / 'preview-backups'
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    fd, name = tempfile.mkstemp(prefix=f'{destination.stem}-{stamp}-', suffix='.sqlite3', dir=directory)
    os.close(fd)
    path = Path(name)
    try:
        with closing(sqlite3.connect(path)) as backup:
            conn.backup(backup)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def prepare_preview(source=DEFAULT_SOURCE, destination=DEFAULT_DESTINATION, *, replace=False):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if _same_file(source, destination):
        raise PreviewError('Source and preview destination must be different files, including aliases.')
    if _same_file(DEFAULT_SOURCE, destination):
        raise PreviewError(f'Refusing to write the production database: {DEFAULT_SOURCE}')
    try:
        with ExitStack() as stack:
            previous = None
            if destination.exists():
                previous = stack.enter_context(closing(_readonly(destination)))
                previous.execute('BEGIN')
                counts = _counts(previous, destination, allow_empty=True)
                if counts['events'] and not replace:
                    return {'action': 'reused', 'source': str(source), 'destination': str(destination),
                            'counts': counts, 'backup': None}

            original = stack.enter_context(closing(_readonly(source)))
            original.execute('BEGIN')
            source_counts = _counts(original, source)
            if not source_counts['events']:
                raise PreviewError(f'Source database has no events; preview was not changed: {source}')
            backup = _backup(previous, destination) if previous else None
            if previous:
                previous.close()  # Release the read snapshot before the atomic backup write.
            destination.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(destination, timeout=30)) as target:
                # SQLite backup takes a consistent source snapshot and replaces
                # the target in one transaction, including IDs and timestamps.
                original.backup(target)
                counts = _counts(target, destination)
            return {'action': 'replaced' if backup and replace else 'seeded',
                    'source': str(source), 'destination': str(destination),
                    'counts': counts, 'backup': str(backup) if backup else None}
    except (sqlite3.Error, OSError) as exc:
        raise PreviewError(f'Could not prepare local preview: {exc}') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--destination', type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument('--replace', action='store_true', help='Refresh a nonempty preview after backing it up.')
    args = parser.parse_args(argv)
    try:
        result = prepare_preview(args.source, args.destination, replace=args.replace)
    except PreviewError as exc:
        parser.exit(2, f'Preview preparation failed: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
