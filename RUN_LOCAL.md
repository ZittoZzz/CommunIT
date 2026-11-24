# CommunIT: run and stop locally

Run these commands from the **repository root** (the directory containing `backend/`, `frontend/` and this file), regardless of its folder name. Start each terminal there. The preview uses a separate saved database; it does not run discovery or change installed services.

| Process | Default address | Stop |
| --- | --- | --- |
| Flask preview API | http://127.0.0.1:5001/api/events | Ctrl+C in its terminal |
| Vite frontend | http://127.0.0.1:5173 | Ctrl+C in its terminal |

## 1. Install dependencies

Use Python 3.12+ and Node 22.12+ with npm available on your PATH.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
```

Existing environments can reuse installed dependencies when they match the requirements and lockfile. `.venv/`, `.tools/`, `node_modules/`, SQLite files and `data/` are ignored; their presence in another developer's workspace is not part of a fresh clone.

## 2. Prepare an isolated preview

A fresh clone has **no saved event database**. Obtain a populated SQLite snapshot from a previous CommunIT collection or a maintainer. It must contain this application's `events`, `announcements` and `sources` tables; an empty or unrelated SQLite file will not work. If you do not have a snapshot, stop here: dependency installation alone cannot populate the board. Collection is separate from this quickstart.

Replace the example source path with your saved snapshot. Keep source and destination different:

```bash
.venv/bin/python -m backend.prepare_preview \
  --source /absolute/path/to/saved-events.sqlite3 \
  --destination "$PWD/data/local-preview.sqlite3"
```

The helper reads the source in read-only mode, copies committed records with SQLite's backup API and prints the resulting counts. It repairs a missing/empty preview, reuses an already populated preview, and rejects a missing/empty/invalid source when a copy is needed. For an intentional replacement, stop the preview backend first and repeat the command with `--replace`; the existing destination is backed up under `data/preview-backups/` before replacement.

Always supply `--source` here. Its omitted default is `data/ctfinder.sqlite3`, the main database, which this setup does not use. Never use that main path or an original benchmark snapshot as the preview destination.

Create the local configuration below. Its relative `extends` resolves from the file in `data/`, so it also works if the checkout is moved or renamed. It retains the community profile and a 45-day listing window; loading source metadata does not collect events.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path('data/local-preview-sources.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({
    'extends': '../sources.community.json',
    'sources': [],
    'listing_window_days': 45,
}, indent=2) + '\n')
PY
```

## 3. Start the backend — terminal 1

```bash
CTF_DATABASE="$PWD/data/local-preview.sqlite3" \
CTF_SOURCES="$PWD/data/local-preview-sources.json" \
CTF_ENABLE_MANUAL_FETCH=0 PORT=5001 \
.venv/bin/python -m backend.app
```

Check **http://127.0.0.1:5001/api/health**. Set `CTF_DATABASE` explicitly before every backend launch: startup initializes schema and reconciles source metadata in the selected database. Keep the snapshot original untouched and serve only the preview copy. Restart this process after backend or configuration changes.

## 4. Start the frontend — terminal 2

```bash
VITE_API_TARGET=http://127.0.0.1:5001 \
npm --prefix frontend run dev -- --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to the preview backend and updates frontend edits without a build. The public **Refresh saved listings** button reloads saved records; there is no public collection button or source-health panel.

**Shutdown:** press Ctrl+C in each preview terminal. Stop only processes you started. Do not rely on historical PID files or stop an installed service to free a development port. If ports are occupied, choose unused ports and keep `PORT`, `VITE_API_TARGET`, the Vite `--port` and the browser-test URL consistent.

## Checks

Backend tests do not require running preview servers or a saved snapshot: they use temporary fixtures and fake source transports, not live discovery. An explicit fallback database keeps accidental default connections away from the main database:

```bash
mkdir -p data/local-checks
CTF_DATABASE="$PWD/data/local-checks/test-default.sqlite3" \
CTF_ENABLE_MANUAL_FETCH=0 \
.venv/bin/python -m pytest -q
```

Build into ignored verification output, leaving any installed `frontend/dist` alone:

```bash
npm --prefix frontend run build -- --outDir ../data/local-checks/build
```

With the preview servers above running and a compatible Playwright Chromium browser installed:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 \
npm --prefix frontend run test:e2e
```

Set `PLAYWRIGHT_BASE_URL` to the **frontend actually running**. For example, use `http://127.0.0.1:5174` if Vite was started on 5174. The repository's Playwright default is 5000; omitting the override can hit an unrelated service. Some browser checks use the normal API and need populated saved listings; route fixtures alone do not cover the entire suite. If Chromium is missing, install the version expected by the locked Playwright dependency with `npm --prefix frontend exec -- playwright install chromium`.

## Separate maintenance and historical evidence

Collection is not required to start or verify the frontend. When explicitly collecting community events, follow [source-admission rules](docs/source-index.md) and use the community profile with a separate database:

```bash
CTF_DATABASE="$PWD/data/community-check.sqlite3" \
.venv/bin/python -m backend.collect \
  --config sources.community.json \
  --report data/community-check-report.json
```

This command makes public network requests. Use a new path for a fresh evaluation; reuse retains discoveries, first-seen timestamps and cooldowns. Inspect the saved report for blocked sources, rate limits and partial results. It does not modify deployment defaults or schedules.

Frozen benchmark reports and inputs remain at their original paths; see the [November 23 report](docs/benchmark-2026-11-23.md). Its ignored database and saved input files are not included in a fresh clone. This guide does not provide a benchmark replay recipe: a saved report/`inputs.json` is not automatically a valid `CTF_SOURCES` configuration. Inspect its actual structure and resolve referenced config paths before any separate reproduction task. For display inspection, copy a populated saved snapshot with the helper above and use the preview configuration; this is not a benchmark rerun. Never launch the backend or collector against original benchmark artifacts.

## Troubleshooting

- **No snapshot:** obtain a populated saved database before startup; do not silently create an empty preview or use the main database as a shortcut.
- **Empty board:** check the helper's counts, selected section and filters. Old saved dates may be past or outside the preview window; an empty Upcoming section does not prove the database is empty.
- **API error:** confirm the backend health URL and the Vite proxy target; restart Vite after changing `VITE_API_TARGET`.
- **Old interface:** use the Vite address. Flask's `/` serves an existing `frontend/dist` build, which may be stale or absent.
- **Port occupied:** select another port or stop your own earlier preview in its terminal; leave unrelated services and schedules alone.
