# CTF Finder PH

A React + TypeScript directory backed by Flask and SQLite. The public site answers **“Which Philippine CTFs can I join?”** A backend publisher index tells the daily collector which recurring feeds and archives to monitor. Competitions are discovered automatically; there is no submission form or event-URL seed. The default configuration uses **₱0 in API fees**.

## Start locally

Requires Python 3.12+ and Node 22.12+.

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
# This workspace has a verified local Node installation because Node was absent:
export PATH="$PWD/.tools/bin:$PATH"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m backend.collect --report data/last-collection.json
.venv/bin/python -m backend.app
```

Open **http://127.0.0.1:5000**. The API and built frontend share this origin. On another machine with Node installed, omit the PATH line. For frontend development, run `npm --prefix frontend run dev` in another terminal; Vite proxies `/api` to Flask.

If the local website is already running as `ctfinder-ph-web.service`, stop it with `systemctl --user stop ctfinder-ph-web.service` before starting a foreground server on port 5000. Flask's server is for local use, not an Internet production deployment.

## Daily collection

The same job runs on demand:

```bash
.venv/bin/python -m backend.collect
# Optional source selection or a separate database:
.venv/bin/python -m backend.collect --source rootcon-bluesky --database data/check.sqlite3
```

Install/start the local website and the **06:00 Asia/Manila** daily timer:

```bash
./scripts/install-services.sh
systemctl --user list-timers ctfinder-ph-collect.timer
systemctl --user start ctfinder-ph-collect.service  # collect immediately
journalctl --user -u ctfinder-ph-collect.service -n 40 --no-pager
```

Both services and the timer were installed and verified locally. A persistent user timer catches up when the user manager next starts; it cannot fetch while the computer is off or offline. No system-wide service or login lingering was enabled. Stop automatic work with `systemctl --user disable --now ctfinder-ph-collect.timer ctfinder-ph-web.service`.

The timer reads the current source configuration on its next invocation. Publisher-index changes do not require a new scheduler or a web-service restart.

## Publisher index and free access

**[source-index.json](source-index.json)** contains the pilot's ten publisher records. Each records its role (`organizer`, `resharer`, or `both`), coverage, enabled status, and a recurring monitor or reference to an existing source. **[sources.json](sources.json)** loads this index and retains the existing source adapters and supplemental searches. Historical example announcements and qualification evidence belong in **[the source-index report](docs/source-index.md)**, outside runtime configuration.

Five pilot publishers are enabled: **ROOTCON, UP Manila, Hack The Box Meetup Manila, AWS student communities in Mindanao, and CREST's Philippine partner announcements**. Five remain disabled candidates: FEU Tech Eventually, University of Mindanao Student Developers Community, OWASP Cebu, the Philippine Information Agency, and VEKTR Security. Readable pages alone do not qualify as working CTF discovery. The report explains the missing extraction, advance-publication, recurring-feed, or access evidence for each candidate. The pilot does not yet provide a verified active Visayas publisher.

Supported adapters remain `bluesky`, `html` (bounded permitted-host crawling and JSON-LD events), `rss`, `ctftime`, free keyless `tavily`, and disabled optional `brave`. RSS sources can enable `follow_articles` to inspect new feed entries and retained articles. Configured content selectors remove navigation and unrelated sidebars. Opt-in body recognition handles invitations whose titles omit “CTF,” while still requiring an actual competition, an evidenced edition, and Philippine scope. A sharing university remains the publisher; it becomes the organizer only when the announcement supports that attribution.

Direct recurring sources run before Tavily, which remains a secondary route to announcements and previously unconfigured publishers. The index does not automatically enable an unverified publisher returned by search. Source health records publisher role, coverage, attempt time, last complete success, and accepted-announcement counts. **A successful source check with zero accepted announcements is not a competition discovery.** Disabled candidates are reported as `disabled`, not as failed API requests. Source failures preserve earlier listings and do not stop other monitors.

Tavily now runs three broad Philippine CTF queries: Facebook announcements, unrestricted registration searches, and community calendars. It always uses **free keyless access**, never reads an API key, and has no paid fallback. A short HTTP 429 cooldown permits one bounded retry; a longer limit skips remaining Tavily queries while other sources continue. Result titles and URLs are logged before filtering under `sources[].searches` in the collection report. `sources[].decisions` explains exclusions. Search-only listings have unconfirmed schedules, registration, and eligibility, and are labeled **Search result · verify source**. Snippets can include unrelated posts and are not used as event facts. Verified organizer relationships may include exact partner website hosts as well as Facebook accounts; host membership alone does not establish event ownership.

Run the same searches without applying organizer filters or opening a database:

```bash
.venv/bin/python -m backend.tavily_check
# Optional: save the URL/title audit (not full search responses).
.venv/bin/python -m backend.tavily_check --report /tmp/ctf-search-audit.json
```

Optional diagnostic `--title` and `--post-id` arguments compare returned results locally; they never enter the queries. Tavily documents [free keyless access](https://docs.tavily.com/documentation/keyless) and [result retention](https://help.tavily.com/articles/1612400809-storing-caching-retaining-output).

No keys are needed for the working defaults. **Brave is disabled in the default zero-fee configuration**, even if credentials already exist locally. This pilot does not change `.env` or `BRAVE_STORAGE_RIGHTS`. There is no paid fallback. Facebook login, cookies, and HTML/full-post scraping are not used. A discovered Facebook link or embed proves the link was found; it does not prove access to the post or its poster.

## What was verified

The latest **[source-index report](docs/source-index.md)** records the active and candidate publishers, their live access results, the recurring-source paths that reached listings, changes from the prior baseline, and separate competition/original-Facebook-post outcomes for the supplied acceptance case. It also records which feeds were checked successfully without finding a competition.

For example, UP Manila's recurring WordPress announcements feed is searched with the generic phrase `capture the flag`; the collector follows the matching article and reads its body. CREST's recurring Asia calendar and past-events index produce a sponsor announcement through a permitted article link. These are reusable publisher routes, not manually inserted competition URLs. Historical invitations discovered today demonstrate historical coverage, not timely alerts.

Collection reports include `registration_observations` and `verified_timely_count`. A verified observation requires explicit open registration, retained source evidence, and a confirmed timed deadline that had not passed when the collector observed it. Date-only or ambiguous windows remain unverified. First-seen times and each revision's registration evidence are preserved; an earlier publication date never substitutes for the collector's observation time. These measurements cover retained listings and do not change the independently selected benchmark.

Prior checkpoints remain available in the [initial source report](docs/coverage.md), [article-discovery report](docs/discovery-iteration.md), [Tavily verification](docs/tavily-discovery.md), and [community-discovery investigation](docs/community-discovery.md). The ten-event benchmark and supplied personal-profile acceptance identifiers remain evaluation-only and are never loaded by the daily collector.

Repeat the normal job twice on one fresh temporary database, without changing the production database, services, or timer:

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
pilot_dir="$(mktemp -d /tmp/ctfinder-source-index-XXXXXX)"
.venv/bin/python -m backend.collect \
  --database "$pilot_dir/events.sqlite3" \
  --report "$pilot_dir/run-1.json"
# If a report returns Retry-After, wait that many seconds before the next run.
.venv/bin/python -m backend.collect \
  --database "$pilot_dir/events.sqlite3" \
  --report "$pilot_dir/run-2.json"
```

Both commands use the default source index and the same collection entry point as the daily timer. Search rankings may change between runs; check `new_announcements`, event/announcement totals, source statuses, and the saved discovery paths before interpreting any difference as a duplicate.

## Verification

With the local web service running:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

Backend fixtures verify publisher-index loading and disabled sources, body-based competition identity, reshare attribution, separate qualifiers/finals/regions/years, duplicate collection, shared-link matching, revised registration evidence, timeliness measurements, postponements, cancellation, date precision, social deletion, failure isolation, and Philippine scope. Browser tests cover real listings, mobile layout, filters, history, source health, timezone rendering, and error recovery. Fixtures are isolated from the live SQLite database. [Architecture and parsing rules](docs/architecture.md).
