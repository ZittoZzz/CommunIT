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

**[source-index.json](source-index.json)** contains 15 publisher and calendar records. Each records its role (`organizer`, `resharer`, or `both`), coverage, enabled status, and a recurring monitor or reference to an existing source. **[sources.json](sources.json)** loads this index and retains the existing source adapters and supplemental searches. Historical example announcements and qualification evidence belong in the research reports, outside runtime configuration.

Ten monitors are enabled: **ROOTCON, UP Manila, Hack The Box Meetup Manila, AWS student communities in Mindanao, CREST's Philippine partner announcements, Luma Manila, KakaComputer's CTF RSS feed, Cyber404's partnership RSS feed, CyberPH's public Luma calendar, and Cisco NetConnect's public Luma calendar**. Five remain disabled candidates: FEU Tech Eventually, University of Mindanao Student Developers Community, OWASP Cebu, the Philippine Information Agency, and VEKTR Security. Readable pages alone do not establish working CTF discovery. The [source-index report](docs/source-index.md) lists the additions and preserves the earlier five-active-publisher checkpoint and candidate blockers. The index does not yet provide a verified active Visayas publisher.

Supported adapters are `bluesky`, `html` (bounded permitted-host crawling and JSON-LD events), `rss`, `luma`, `ctftime`, free keyless `tavily`, and disabled optional `brave`. RSS sources can enable `follow_articles` to inspect new feed entries and retained articles. Configured content selectors remove navigation and unrelated sidebars. Opt-in body recognition handles invitations whose titles omit “CTF,” while still requiring an actual competition, an evidenced edition, and Philippine scope. A sharing university remains the publisher; it becomes the organizer only when the announcement supports that attribution.

Direct recurring sources run before Tavily, which remains a secondary route to announcements and previously unconfigured publishers. The index does not automatically enable an unverified publisher returned by search. Source health records publisher role, coverage, attempt time, last complete success, and accepted-announcement counts. **A successful source check with zero accepted announcements is not a competition discovery.** Disabled candidates are reported as `disabled`, not as failed API requests. Blocked requests and HTTP 429 rate limits are reported separately. `Retry-After` cooldowns are persisted as `next_retry_at`, so another collection skips that source until its retry time. Source failures preserve earlier listings and do not stop other monitors.

Luma Manila uses its documented public city iCal subscription, with the public city page as a fallback. The collector follows discovered event links and inspects their descriptions, public hosts, venue, schedule, and registration state. The initial live check returned six event links; the city page advertised seven events while exposing six links. No current CTF qualified. The city calendar excludes online and private events, and its visible slice is not a complete Philippine competition directory. A working calendar check therefore does not establish timely CTF discovery. A conference ticket does not establish entry into its CTF; supported standalone competition states retain `open`, `approval_required`, `waitlisted`, `closed`, or `unknown`.

CyberPH and Cisco NetConnect use documented public publisher iCal subscriptions, with `page_fallback: false`. One-time publisher-name research found public non-CTF events, which exposed their owning public calendars; the documented subscription route then returned event links, including online events. Each discovered competition still needs its own Philippine-scope evidence. CyberPH's feed provided historical CTF evidence; Cisco's readable calendar has not yet demonstrated CTF discovery. WorkFlow PH is not enabled because a qualifying recurring route with CTF invitation evidence was not established. Facebook and Luma identities are not merged merely because their display names match.

Accepted competitions can produce publisher candidates from explicit host, organizer, sponsor, and partner relationships. Relevant partnership articles can also produce candidates without creating an event. KakaComputer's recap can corroborate a historical competition and identify publishers; it cannot produce an open-registration alert. Cyber404 partnership news requires a separate actual competition announcement before becoming an event.

Candidate records retain roles, public profile/account identities where available, relationship quotes, the originating announcement and discovery path, and first/last-seen times. Stable identities deduplicate repeated mentions; display names alone never merge organizations across articles. A name without a verified public URL remains an evidence-scoped candidate. Candidates do not automatically become monitors, including Facebook profiles. Qualify a recurring public source once, add its monitor to the source index with an explicit `publisher_identity_urls` or `publisher_account_ids` association, and verify a successful check; the collector then links the existing candidate to that active monitor. Future competitions still come from the recurring source, without per-event submissions.

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

The latest **[classification and advance-notice report](docs/advance-notice-report.md)** traces a dated 2025 invitation that incorrectly appeared under Upcoming, verifies its correction through SQLite, the API, and desktop/mobile UI, and audits eight existing publishers or candidates. A past announced date now appears under **Past & finished**, labeled **Past date · completion unconfirmed**; it does not invent a competition end or registration closure. Date-only tournament days remain dates. Genuine teasers retain **Schedule TBA**, while unconfirmed search results say **Undated search lead**. Verification used a separate database and isolated development servers; the production database, services, and frontend build were not changed.

The earlier **[publisher and registration-opportunity report](docs/publisher-opportunity-report.md)** covers the two publisher calendars and registration observations. The **[Luma discovery report](docs/luma-discovery.md)** and **[live verification JSON](docs/luma-verification.json)** record the city/RSS investigation, candidate publishers, duplicate checks, and separate competition/original-Facebook-post outcomes. These reports distinguish a readable calendar from a discovered CTF and historical coverage from timely discovery.

For example, UP Manila's recurring WordPress announcements feed is searched with the generic phrase `capture the flag`; the collector follows the matching article and reads its body. CREST's recurring Asia calendar and past-events index produce a sponsor announcement through a permitted article link. These are reusable publisher routes, not manually inserted competition URLs. Historical invitations discovered today demonstrate historical coverage, not timely alerts.

Collection reports include `registration_observations` and `verified_timely_count`. A verified observation requires explicit open registration, retained source evidence, and a confirmed timed deadline that had not passed when the collector observed it. Date-only or ambiguous windows remain unverified. First-seen times and each revision's registration evidence are preserved; an earlier publication date never substitutes for the collector's observation time. These measurements cover retained listings and do not change the independently selected benchmark.

Separately, `live_open_observation_count` records a current registration control observed open with evidence of a future or ongoing competition, even when no deadline is published. `first_seen_live_open_count` counts those observations made when the collector first found the event. Static invitation prose, old pages with stale open controls, approval requirements, and waitlists do not qualify. These observations do not increase the existing deadline-backed timely count or rewrite the frozen benchmark.

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

Both commands use the default source index and the same collection entry point as the daily timer. Search rankings may change between runs; check `new_announcements`, event/announcement totals, `publisher_candidates`, source statuses, and the saved discovery paths before interpreting any difference as a duplicate. Candidate first-seen timestamps and relationships should also remain stable on an unchanged second run.

## Verification

With the local web service running:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

Backend fixtures verify publisher-index loading and disabled sources, body-based competition identity, reshare attribution, separate qualifiers/finals/regions/years, duplicate collection, shared-link matching, revised registration evidence, timeliness measurements, postponements, cancellation, date precision, social deletion, failure isolation, and Philippine scope. Luma and publisher regressions cover calendar fallback, blocked versus empty responses, cooldown persistence, conference-ticket separation, registration states, timezone boundaries, relationship roles, candidate identity aliases, and transaction rollback. Calendar regressions cover wrapped HTML date labels, workshop/parent-program separation, past-date classification, rescheduling, and unchanged first-seen timestamps. Browser tests cover real listings, mobile layout, filters, history, source health, timezone rendering, error recovery, past dates, future teasers, and undated search leads. Fixtures are isolated from the live SQLite database. [Architecture and parsing rules](docs/architecture.md).
