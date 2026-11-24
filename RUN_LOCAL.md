# IT_Community_PH: run and stop locally

Use two terminals: one for the backend and one for the frontend. Open **http://127.0.0.1:5173** to see the current frontend code, including edits made during development.

| Process | Address | Stop |
| --- | --- | --- |
| Backend — Flask API | http://127.0.0.1:5001/api/events | Press **Ctrl+C** in the backend terminal |
| Frontend — Vite | http://127.0.0.1:5173 | Press **Ctrl+C** in the frontend terminal |

## 1. Prepare the local database

This command copies saved events into `data/local-preview.sqlite3` if the preview is missing or empty. A preview that already contains events is reused. The main database is opened read-only; an existing preview is backed up before replacement.

```bash
cd /home/miguel/Documents/GitHub/IT_Community_PH

.venv/bin/python -m backend.prepare_preview

.venv/bin/python - <<'PY'
import json
from pathlib import Path
root = Path.cwd().resolve()
config = {'extends': str(root / 'sources.community.json'), 'sources': [], 'listing_window_days': 45}
(root / 'data/local-preview-sources.json').write_text(json.dumps(config, indent=2) + '\n')
PY
```

The command prints the event count and any backup path. If the source is missing, invalid, or empty, preparation stops with an explanation instead of silently creating an empty preview. To use a different saved database, pass `--source /absolute/path/to/saved.sqlite3`. To deliberately refresh an already populated preview from that source, add `--replace`; the previous preview is saved under `data/preview-backups/` first. Stop the preview backend and any preview collection before replacing a populated database.

This copies the main database's saved listings, not a lost temporary prototype snapshot. Data under `data/` survives restarts; `/tmp` snapshots may be removed. Database preparation does not fetch sources. The preview configuration extends `sources.community.json`: qualified CTF publishers and recurring public technology calendars, with paused routes retained as disabled candidates, with the existing 45-day listing view. It excludes the legacy individual AWS event seed. Undated leads remain on Watchlist. The deployment's `sources.json` and `source-index.json` are unchanged. Regenerate this configuration to enable the broader sources in an older preview; restarting the backend is required.

## 2. Run the backend — terminal 1

```bash
cd /home/miguel/Documents/GitHub/IT_Community_PH

CTF_DATABASE="$PWD/data/local-preview.sqlite3" \
CTF_SOURCES="$PWD/data/local-preview-sources.json" \
CTF_ENABLE_MANUAL_FETCH=0 \
PORT=5001 \
.venv/bin/python -m backend.app
```

Leave this terminal running. You can check the backend at **http://127.0.0.1:5001/api/health**.

**Stop the backend:** press **Ctrl+C** in this terminal. To restart it, run the same command again. Restart after editing backend Python files; this command does not enable automatic reload.

After the public-review update, restart this backend and reload the Vite page to see the review notes, Archived leads, and separate Cloud/DevOps filters. Startup applies additive observation and source-membership/provenance tables/columns to the explicitly selected preview database. Topic labels, review/expiry and legacy Meetup duplicate display are read projections; they do not require collection. The two reported Meetup/Luma records were already updated in the saved preview from checked public pages, with the prior database backed up under `data/review-verification/preview-before-repair.sqlite3`.

If the preview was started in the background during the empty-database repair, its PID is in `data/local-preview-backend.pid` and its log is in `data/local-preview-verification/backend.log`. Stop that instance before using the foreground command above. This checks that the PID still belongs to the preview backend:

```bash
.venv/bin/python - <<'PY'
import os, signal
from pathlib import Path
root = Path.cwd().resolve()
pid = int((root / 'data/local-preview-backend.pid').read_text())
process = Path('/proc') / str(pid)
if process.exists():
    env = (process / 'environ').read_bytes().split(b'\0')
    assert b'CTF_DATABASE=' + str(root / 'data/local-preview.sqlite3').encode() in env
    assert b'backend.app' in (process / 'cmdline').read_bytes().split(b'\0')
    os.kill(pid, signal.SIGTERM)
    print('Stopped the background preview backend.')
else:
    print('That preview process is already stopped.')
PY
```

The public frontend exposes only **Refresh saved listings**. Collection diagnostics and source inventories are local CLI/report functions; no token or diagnostic switch is returned by `/api/events`. Leave `CTF_ENABLE_MANUAL_FETCH` unset (or `0`) for ordinary preview/deployment. The older localhost/token-guarded endpoint remains for local tooling only.

## 3. Run the frontend — terminal 2

```bash
cd /home/miguel/Documents/GitHub/IT_Community_PH
export PATH="$PWD/.tools/bin:$PATH"

VITE_API_TARGET=http://127.0.0.1:5001 \
npm --prefix frontend run dev -- --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**. Vite forwards `/api` requests to the backend on port 5001 and updates the page as you edit frontend files. A frontend build is not required for this development mode.

**Stop the frontend:** press **Ctrl+C** in this terminal. Stop both terminals when finished; stopping one does not stop the other.

## Campus Bulletin branch preview (no collection)

The frontend work is on `feat/campus-bulletin`. Its verification copy of saved events is `data/campus-bulletin/preview.sqlite3`; the original production and local-preview databases were preserved. The copy and its empty-source, 45-day configuration are local ignored artifacts. These commands reuse that prepared copy; they do not run discovery. If it is missing in another checkout, prepare an isolated copy of a populated saved database before starting the backend.

From the repository root, run in separate terminals:

```bash
CTF_DATABASE="$PWD/data/campus-bulletin/preview.sqlite3" \
CTF_SOURCES="$PWD/data/campus-bulletin/sources.json" \
CTF_ENABLE_MANUAL_FETCH=0 PORT=5002 \
.venv/bin/python -m backend.app
```

```bash
PATH="$PWD/.tools/bin:$PATH" VITE_API_TARGET=http://127.0.0.1:5002 \
npm --prefix frontend run dev -- --port 5174 --strictPort
```

Open **http://127.0.0.1:5174**. Stop each process with **Ctrl+C** in its terminal; do not kill another service occupying these ports. No installed service or deployment build is changed. The existing commands on ports 5001/5173 also show the new frontend when run from this branch.

## Collect events manually (local CLI)

The public page's **Refresh saved listings** reloads stored data without fetching publishers. To collect, use the isolated CLI command below. No website collection button or route-health panel is exposed. Reports contain per-route outcomes, retries, deferrals, discovery paths and parsed evidence; do not publish them as the public API. A successful process can include partial source failures, so inspect the report.

The community profile has 16 request-eligible routes and 17 disabled candidates after source qualification. It retains recurring primary/calendar coverage and qualified Cebby/GDG Cebu routes; legacy event seeds, blocked government pages and unqualified/redundant discovery are excluded or disabled. The default CTF profile remains separate. See `docs/source-quality-2026-11-23.md` for every decision. Restart the preview backend after code/config changes; do not run discovery just to update the UI.

## Isolated community collection

For a fresh collection without changing the saved preview or production database:

```bash
CTF_DATABASE="$PWD/data/community-check.sqlite3" \
.venv/bin/python -m backend.collect \
  --config sources.community.json \
  --report data/community-check-report.json
```

Use a new database path for a new evaluation. Reusing it preserves prior discoveries and is not an empty-database benchmark. This profile uses recurring calendars and date-generated generic queries; it never reads the benchmark reports. Keyless Tavily can return HTTP 429; the report records the wait and skipped queries, while calendar routes continue. No paid fallback is enabled.

The November 23 evaluated snapshot is `data/benchmark-2026-11-23/final-live/events.sqlite3` with its exact configuration in `final-live/inputs.json`. To inspect it, substitute those two absolute paths for `CTF_DATABASE` and `CTF_SOURCES` in the backend command, without replacing `data/local-preview.sqlite3`. Never start the backend against a frozen evaluation database: copy it to a separate ignored preview path first, then inspect the copy. Keep collection disabled. See [the evaluation report](docs/benchmark-2026-11-23.md) for trace paths and limitations.

## Common startup issues

- **Port already in use:** stop the earlier process in its terminal. If you choose another backend port, also change `VITE_API_TARGET` to match. `--strictPort` prevents Vite from silently using a different frontend port.
- **API connection error:** confirm the backend is running on port 5001, then restart the frontend if you changed `VITE_API_TARGET`.
- **Empty directory:** run step 1 and read the printed event count. An existing empty preview is now repaired from the saved source. Also check the selected tab and filters. Use the isolated collector CLI for fresh collection.
- **Old interface:** use port **5173**. Flask's `/` route serves the last built frontend, which may be older than the source code.
- **Existing website on port 5000:** it is separate from this preview. If you intentionally want to stop the installed website service, use `systemctl --user stop ctfinder-ph-web.service`. This does not stop the collector timer.

## Dependencies, if missing

This workspace already has `.venv`, `.tools/bin`, and frontend dependencies. On a fresh setup, install dependencies before running the commands above:

```bash
cd /home/miguel/Documents/GitHub/IT_Community_PH
export PATH="$PWD/.tools/bin:$PATH"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend ci
```

Use Python 3.12+ and Node 22.12+. If `.tools/bin` is absent, install Node separately and use its `npm` command.
