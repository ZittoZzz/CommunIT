# IT_Community_PH project handoff

Last updated: **2026-11-23, Asia/Manila**.

This is the current project handoff for a new agent/chat working in the same repository. Read [AGENTS.md](AGENTS.md) for working rules and [RUN_LOCAL.md](RUN_LOCAL.md) for commands. Check the actual workspace before acting; the observations below are dated, not a promise about current process or source availability.

## Project and architecture

Current checkout: `/home/miguel/Documents/GitHub/IT_Community_PH`. Repository/package configuration has not been renamed; the public-facing brand is **CommunITy PH**.

The site lists tech meetups, competitions, workshops, and conferences in the Philippines, plus international online opportunities available to Filipinos. It began as a CTF directory, and several default discovery routes still focus on CTFs.

| Area | Technology / entry points |
| --- | --- |
| Backend | Python, Flask; `backend/app.py` |
| Database | SQLite files; `backend/db.py` |
| Collector | Existing CLI `backend/collect.py`; adapters under `backend/` |
| Source configuration | `sources.json`, `source-index.json`, and broad preview profile `sources.community.json`; loaded by `backend/source_index.py` |
| Listing | `backend.db.events()` → `GET /api/events` → `frontend/src/App.tsx` |
| Frontend | React, TypeScript, Vite; `frontend/src/styles.css` |
| Tests | pytest under `tests/`; Playwright under `frontend/e2e/` |

The database preserves event identities, announcement payloads/revisions, first-seen timestamps, source health, and collection runs. Display topics and some legacy content repairs are projected from saved evidence when the API reads records; they do not require rewriting stored payloads.

## Local preview and database selection

| Path / address | Purpose |
| --- | --- |
| `data/ctfinder.sqlite3` | Main/production SQLite DB. Protect it during development. |
| `data/local-preview.sqlite3` | Persistent local preview DB, separate from production. |
| `data/local-preview-sources.json` | Local source configuration extending the absolute `sources.community.json` path, with `sources: []` and `listing_window_days: 45`. Regenerated during the benchmark task; restart an older preview backend to load it. |
| `data/preview-backups/` | Backups made before the preview preparation helper replaces an existing DB. |
| `data/manual-fetch/` | Manual collector reports, logs, and final status files. |
| `http://127.0.0.1:5001` | Preview backend; health at `/api/health`, records at `/api/events`. |
| `http://127.0.0.1:5173` | Vite frontend, proxying `/api` to the preview backend. |

Use the commands in **RUN_LOCAL.md**. `backend.prepare_preview` repairs a missing/empty preview from a read-only saved source, reuses populated previews, and requires `--replace` for an explicit populated-preview refresh. It backs up an existing destination before replacement. A missing/empty/invalid source is an error, not permission to silently create an empty preview.

Default backend/collector commands can select the main DB. Explicitly set `CTF_DATABASE` or pass `--database`. The 45-day listing view comes from `CTF_SOURCES`; it is not automatically enabled in every configuration. Flask on port 5000 may be an independently installed service and may serve an older `frontend/dist` build. Do not stop or rebuild that deployment as part of routine preview work.

The last topic-fix session restarted the preview backend in the background. `data/local-preview-backend.pid` is only a hint: verify the current process command, port, and DB before stopping it. That session's log is `data/topic-section-verification/backend.log`; the earlier repair log is `data/local-preview-verification/backend.log`. Do not assume a recorded PID is still valid.

`data/`, SQLite files, local dependencies, build outputs, and logs are Git-ignored. They persist in this workspace but will not appear automatically in another checkout. Earlier useful `/tmp` snapshots disappeared; keep durable local evidence under `data/` and report missing artifacts honestly.

## Implemented student-facing behavior

- Navbar brand: **CommunITy PH**. H1: **The Tech Board**. Subtitle: **Your next tech meetup, hackathon, or conference might be right here.** Browser title: **The Tech Board | CommunITy PH**. No student-only label above the headline. Generic wording uses “Events”; actual event/competition titles remain specific.
- Campus Bulletin uses a cork board with compact date-first selectable cards and a pinned paper containing the existing event details, retained evidence, announcement history, and registration information. Desktop selection preserves the list; mobile Back restores filters, scroll position, and focus. See the latest frontend checkpoint below.
- Section tabs: **Upcoming & live**, **All events**, **Past & finished**, **Date unconfirmed**, **Watchlist**, **Archived leads**. Upcoming remains the default. All events includes every section once and preserves active filters and the existing sorting/grouping.
- Filters compose: Topic, Format, Registration, and text search. Counts and empty states reflect the filtered rows. The current UI has no separate Region selector; geography is shown through PH/international groups and event locations.
- Topic choices: Cybersecurity, AI & Data, Cloud, DevOps, Software Development, Networking & Systems, Community, General IT, plus All topics. Cloud and DevOps are separate evidence-backed topics. An event can have multiple supported topics and appears once in each filtered result set.
- Topic projection in `backend/topics.py` applies to old and new records. Unsupported legacy topic strings and organizer names are not fallbacks. Program descriptions are kept separate from eligibility by `backend/event_text.py`.
- Manila date-only events remain eligible throughout their calendar day and expire the following day without an invented start time. Historical/conflicting dates must not become Upcoming merely because a year or another date looks current. Date and listing regressions are in `tests/test_meetup_dates.py` and `tests/test_pilot_listing.py`.
- PH hybrid events stay in the PH section with both attendance options on one card. Public approval-required applications display **Applications open · approval required**; restricted fellow/member tickets stay separate. Account requirements and unknown fees/deadlines are retained.

## Manual fetch and empty-preview repair

The earlier empty-page problem came from reusing an existing preview DB with zero events. The source DB still contained 12 records, but the earlier 19-event temporary snapshot was not recoverable on November 23. The helper repaired the preview, then one authorized manual fetch added two records for a 14-record preview. This was fresh collection, not restoration of the old benchmark snapshot.

**Fetch events** is an opt-in development control implemented in `backend/manual_collection.py`, `backend/app.py`, and the frontend:

- Requires `CTF_ENABLE_MANUAL_FETCH=1` and an explicit nonproduction DB. Refuses the default production DB and its aliases; validates localhost requests and a token.
- Starts the existing collector CLI asynchronously through `POST /api/collection`; `GET /api/collection` reports progress. Requests cannot choose database or source paths.
- Prevents overlapping jobs; CLI symlink paths resolve to the same database lock. Times out after 20 minutes and cleans up its own child on normal backend shutdown.
- Saves source warnings, logs, and reports. The UI reloads saved results after completion or partial failure while preserving filters. Uncertain network failures require checking job status before retrying.
- **Refresh saved listings** only reloads stored listings. It does not collect. Fetch/Refresh and collection status live in **Directory updates** below source coverage. The fetch feature is disabled by default; omit its environment flag for deployment.

Do not assume the UI still shows the prior job's progress after a backend restart; persistent reports remain under `data/manual-fetch/`.

## Latest topic corrections and All events tab

Completed on **2026-11-23**:

1. **AWS Student Community Day:** the old HTML adapter appended ` · CTF` to a conference title from a bare Capture The Flag agenda heading. It then supplied its own synthetic title as topic evidence. `backend/adapters.py` now preserves the source title and uses the existing explicit-contest body check. `backend/event_text.py` recognizes the legacy bare-heading signature and repairs the display name; `backend/topics.py` does not use that bare excerpt as a whole-event Cybersecurity claim. The saved AWS record now has no topic tag. Cloud was deliberately not inferred from the AWS name; the retained excerpt does not establish it.
2. **HackForGov / Hack4Gov:** these saved leads were excluded because topic projection rejected all search-only evidence. A narrow event-series rule now requires the parsed series, event name, and retained matching title citation. All five saved HackForGov leads receive Cybersecurity. This does not upgrade source access or verify schedule, registration, price, eligibility, region, or round. They remain Watchlist leads with unknown signup.
3. **All events:** added next to Upcoming & live in `frontend/src/App.tsx`; tests cover all sections, deduplication in display, combined filters, counts, empty states, keyboard navigation, desktop, and mobile.

These repairs were verified through the normal API on a copy of the existing preview DB and then through the local site. No collector ran for the topic/tab ticket. Stored records, first-seen times, run history, source configuration, production DB, and the benchmark report were unchanged. Existing records do **not** need reprocessing for these topic/display corrections.

Relevant regression files: `tests/test_topics.py`, `tests/test_publisher_discovery.py`, and `frontend/e2e/directory.spec.ts`.

## Earlier topic/tab verification

These results predate the new benchmark work below. The existing preview DB was preserved; fresh collections can change counts.

| Check | Result |
| --- | --- |
| Backend suite | **746 passed** (`.venv/bin/python -m pytest -q`) |
| Browser suite | **29 passed**, including desktop/mobile and normal listing checks |
| Frontend | TypeScript + Vite build passed; isolated output under `data/topic-section-verification/build/` |
| Preview listing | **14 records**: 2 Upcoming/live, 8 Watchlist, 4 Past/finished |
| Cybersecurity filter | **11 records** across All events; 7 Watchlist, including all 5 HackForGov leads; AWS excluded |
| Final live UI check | No browser errors and **zero collection POSTs** |

Evidence, if still available locally:

- `data/topic-section-verification/verification.json` — test counts and protected-file checks.
- `data/topic-section-verification/ui-proof.json` — actual filtered counts and no-collection check.
- `data/topic-section-verification/before-live-api.json` and `after-live-api.json` — normal API comparison.
- `data/topic-section-verification/copied-preview.sqlite3` — test copy; never treat it as production or a blind snapshot.
- `data/topic-section-verification/all-events-desktop.png`, `cybersecurity-desktop.png`, and `cybersecurity-watchlist-mobile.png` — current screenshots at that checkpoint.
- `data/local-preview-verification/` — earlier preview repair/manual-fetch evidence; its topic screenshots predate the latest corrections.

For future frontend checks, point Playwright at the preview (`PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173`); the repository default is port 5000. The local verification config under `data/topic-section-verification/playwright.config.mjs` records the installed Chromium path used here. Verify availability rather than installing browsers or starting production services automatically.

## Discovery, benchmark history, and remaining gaps

MLH Global Hack Week uses `backend/mlh.py` and the organizer calendar at `https://ghw.mlh.com/`. Safe AI Philippines uses shared `backend/luma.py` parsing and its organizer calendar at `https://luma.com/safeaiph?k=c`. Both flow through the existing collector, SQLite, API, and UI. Do not substitute reference edition URLs as discovery inputs.

The normal deployment's `sources.json` remains heavily CTF-oriented and still contains a pre-existing individual AWS seed. The new reusable `sources.community.json` profile inherits the existing routes, excludes that seed, and adds recurring public calendars plus generic searches. Use it for broad community collection as documented in RUN_LOCAL.md; an unchanged default run is not a clean independent-discovery evaluation. The preview configuration now extends the new profile, but its existing saved database was not replaced.

The historical [November 22 prototype report](docs/prototype-iteration-2026-11-22.md) records:

- Original frozen blind score: **0/8 discovery, 0/4 actionable**. Keep it unchanged.
- Later known-reference regression: **8/8 discovery, 4/4 actionable**, after saved-response improvements. This was not a new blind run and did **not** establish an overall acceptance pass.
- Remaining historical acceptance gaps included cybersecurity being available only in Watchlist, conflicting prize wording in a visible organizer title, and four original replays remaining unverified because required raw HTML was absent. Do not turn expected answers into fabricated replay results.
- The historical final prototype had **19 events / 22 announcements**. Its `/tmp` DB/capture links may now be missing. The November 23 preview's 14 records are a separate dataset and do not revise those historical results.

Other known limits: source failures and blocked robots checks remain possible; coverage is not complete across all topics/regions. The old preview AWS record still lacks retained program evidence for Cloud, while newly verified standalone website data can support it. A current HackForGov NCR edition/round/signup remains unestablished by saved search leads. Safe AI revision churn remains separate from duplicate-event prevention. Deployment and schedules were not changed.

## Latest benchmark work — November 23, 2026

The user's new ten-event reference set covers Nov 23–Jan 7, Manila time. See [the report](docs/benchmark-2026-11-23.md) and [per-event runtime traces](docs/benchmark-2026-11-23-results.json). This is a known-reference improvement, not a blind evaluation; frozen earlier reports/scores are unchanged.

- Baseline normal collector, isolated empty DB with the individual AWS seed removed: **1/10 event matches** (MLH). Fresh final profile run: **10/10 event matches, 9/10 reference URLs**, all ten visible in the normal API's Upcoming & live section. The final DB has 35 total records. AWS is matched through its co-organizer's recurring Meetup calendar under the title “AWS Student Community Day Davao”; same date, venue, Mindanao edition and organizer corroborate identity. This is not a complete-field pass.
- Final runtime inputs contain recurring calendars and generic month-generated queries, no reference titles, individual event URLs or replay fixtures. Search-assisted calendar selection was done during development and is disclosed. Final Tavily search returned 429; all ten accepted matches came from calendar routes.
- Separate complete generic public-search output verified the AWS website after parser repairs. That assisted DB retains Nov 28 date-only, minimum advertised PHP 199, individual tiers, unknown inventory/deadline, and supported Cloud program evidence. It is not autonomous exact-website discovery credit; the two AWS source records were not merged across databases.
- `backend/opportunity_search.py` / `opportunity_pages.py`: bounded public calendars and external directory traversal, matched Meetup event/group PH scope, technical topic support, public YouTube premiere verification and conservative price parsing. `network.py` guards external discovered URLs against nonpublic DNS addresses. `source_index.py` supports relative profile inheritance with cycle/exclusion validation. `collect.py` includes parsed fields/citations in runtime discoveries.
- `backend/standalone_event.py`: conservative self-canonical organizer/about/venue/ticket/FAQ fallback, preserving date-only precision, separating sales dates from event dates and ticket prices from inventory. `devpost.py` follows linked rules and distinguishes registration/submission cutoffs, eligibility, free entry and account requirements. Explicit attendee requirements are retained by `event_text.py`.
- `frontend/src/App.tsx` displays advertised minimum prices as “From PHP 199.” Topic projection in `topics.py` computes whole-quote title checks once instead of once per sentence; all 35 event objects stayed identical, while a local projection check improved from 2.463s profiled to 0.351s unprofiled.

Benchmark verification at that checkpoint: **781 pytest tests passed**, **29 Playwright tests passed**, TypeScript/Vite build passed into ignored `data/benchmark-2026-11-23/build/`. Initial browser loading timeouts exposed the topic-projection slowdown; the final suite passed after the fix. Additional actual-API desktop/mobile proof and protected-file checks are in `data/benchmark-2026-11-23/verification.json`. Evidence and useful DBs stay under that directory. Production assets/services/schedules, main DB and the existing preview DB were preserved during that task.

The final useful snapshot is `data/benchmark-2026-11-23/final-live/events.sqlite3`; use its `inputs.json` with the normal backend to inspect it. The temporary browser-check backend used port 5002 because 5001 was occupied; the owned backend and Vite processes were stopped after verification, leaving the existing port 5001 service untouched. Use RUN_LOCAL.md for current startup commands rather than assuming any verification process remains running.

Remaining gaps: autonomous discovery of the exact AWS website (the event itself is recovered through Meetup); no verified RSVP control in fetched Meetup HTML; Conf42 “no registration required” not explicitly established; AI Unwrapped's attendee-only link restriction not separately projected; bounded calendar traversal and Tavily quota; cross-platform AWS identity merging untested. Do not claim a blind pass, complete factual parity, seat availability, or exhaustive coverage. The requested event-recovery iteration is complete with those disclosed limits; do not fabricate missing facts to improve the score.

## Public review notes, source updates and separate topics — November 23, 2026

Implemented at the user's request; **no admin access or moderation controls** were added.

- Flagged events remain publicly visible with a compact **Flagged for review** badge and an explanation in Details. Search-only/unreadable content, unresolved schedules, source-check failures and conflicting dates can trigger the note. Undated search leads stay on Watchlist even without the optional listing-window setting.
- Unresolved leads with no confirmed schedule/cutoff expire **45 days after first discovery** into **Archived leads**, still visible in All events. Expiry is a verification state, never an assertion that the event ended. Search/feed rediscovery does not reset the clock; subsequently confirmed dates can resolve the lead. There are no manual approval/hide/archive actions yet.
- `backend/verification.py`, `db.py`: separate last observation, successful content fetch and event-page check. An additive `announcements.last_observed_at` column allows search rediscovery without advancing the previous content-fetch time. Legacy structured Meetup evidence can establish its previous page read; missing page-check timestamps remain unknown.
- `adapters.py`, `opportunity_pages.py`, `opportunity_search.py`: Meetup RSS items now recheck their event pages even in a complete feed. A failed page read preserves previously checked facts and timestamps. Philippine cybersecurity Meetup events can use the structured whole-event verifier; its agenda is not promoted to a separate CTF schedule. Conflicting page/body dates remain unresolved and can be retained for public review. Matched full event descriptions retain eligibility such as QCU-only restrictions instead of using truncated JSON-LD/fragmented text.
- `db.py`: the numeric Meetup event ID governs title changes; existing duplicate rows fold into one display card without deleting historical rows or revisions. The latest verified page supplies current facts, preventing old duplicate fields from reappearing.
- `luma.py`, `verification.py`, `frontend/src/App.tsx`: parent-event dates display explicitly as context alongside unconfirmed CTF times. Confirmed completion remains Finished/closed; a remaining RSVP control does not override it. Legacy retained calendar dates also project without a collection run.
- `topics.py` and UI: **Cloud** and **DevOps** are separate. Tags still require event evidence; GitHub alone, container tool names alone and organizer names do not establish either. The reported DevOps event now projects only `devops`.

Two **already stored** public pages were freshly read at about **20:10 PHT**, not discovered through benchmark inputs. Meetup still says Nov 29 in its schedule and Nov 4 in its description, so the repaired preview has one **Hack The Box Meetup #12** card under Date unconfirmed, flagged for review, with the QCU restriction retained. The Luma Packet Capture card stays Finished and shows its Oct 4 parent-event start/end separately. Both verified payloads were applied to `data/local-preview.sqlite3` after backup to `data/review-verification/preview-before-repair.sqlite3`. Unrelated announcements, original first-seen timestamps and historical duplicate rows were preserved. The preview now projects 41 event cards; five HackForGov search leads remain visible and flagged. Later collections can change these counts.

Verification: **800 pytest tests passed**; **31 browser checks passed: the 29 existing checks plus the corrected two new review checks**; TypeScript/Vite build passed under `data/review-verification/build/`. The initial two new browser cases used the wrong topic-filter locator; their corrected desktop/mobile checks passed. Additional real-API browser proof covers one conflicted Meetup card, retained QCU eligibility, finished Luma context, DevOps-only tags and five visible flagged search leads, with no page errors or collection POSTs.

Evidence: `data/review-verification/{backend-tests-final.log,frontend-build-final.log,browser-tests.log,review-browser-tests.log,browser-proof.json,final-api.json,known-recheck.json,preview-repair.json}` and desktop/mobile screenshots. `known-recheck.json` distinguishes original fetch timestamps from later offline reparsing. No full collector/discovery run or benchmark re-evaluation was performed. Frozen benchmark artifacts/scores, the production DB, deployment assets/services and schedules were preserved. Restart an existing preview backend to load the changed Python code; UI development mode updates through Vite. The temporary verification servers use ports 5002/5174 and are stopped after checks.

Remaining limits: the organizer must resolve the Meetup date contradiction; Facebook search-only leads still cannot establish current schedules/signup; historical page-check timestamps without retained proof remain unknown; public notes provide no manual moderation workflow. No automatic inference of attendance availability was added.

## Campus Bulletin frontend — November 23, 2026, 20:42 PHT

Implemented on **`feat/campus-bulletin`** from the approved `/home/miguel/Downloads/Campus-Bulletin.html` visual/interaction reference. The prototype was not copied into production; its demo events and finish switch are absent. No merge or deployment was performed.

- `frontend/src/App.tsx` reuses `EventCard`, `EventDate`, ticket/evidence/source components and the normal `/api/events` data. Existing details now render in `EventPaper`. The cork-only CSS is in `frontend/src/styles.css`; the brand remains IT_Community_PH and the headline is The Campus Board.
- Compact date-first cards stay on the left. Desktop selection updates a bounded, sticky paper without remounting, moving or resetting the list. Native buttons support Enter/Space. On mobile (through 760px), the full-width paper replaces the visible list; the list stays mounted. Back/Escape restores the captured scroll position and selected-card focus, with filters intact. Editing a filter while reading returns to results without stealing filter focus. Resizing back to desktop preserves selection.
- Retained search, all topic choices including Community and separate Cloud/DevOps, format/registration filters, all section tabs, PH/international-online groups, location/format, lifecycle/review notes, unknown facts, distinct registration/submission deadlines, restricted ticket distinctions, and real organizer links. Important facts and source links precede long descriptions. Existing filter/sort/ranking logic is unchanged.
- Updated `frontend/e2e/directory.spec.ts` and `review.spec.ts` to inspect the selected paper instead of row expansion; added six navigation/filter regression checks in `campus-board.spec.ts`. **37 Playwright Chromium tests passed**, including keyboard selection, identical desktop list DOM/geometry/scroll, mobile Back at 390/760px, focus, resize, and filters. **TypeScript + Vite build passed**, output isolated under `data/campus-bulletin/build/`; `git diff --check` passed. Earlier runs exposed test locators that assumed details remained inside cards; those scopes were corrected without dropping field checks.
- Real normal-API browser proof used an isolated SQLite backup of saved preview data: **41 events**, zero browser errors, zero collection POSTs, no mobile horizontal overflow. No discovery or collector ran. Hash checks confirm **38 protected backend/configuration/existing-database/benchmark files unchanged**. The production and original preview databases, deployment assets/services/schedules, frozen benchmark reports and ranking were untouched.

Local evidence: `data/campus-bulletin/{browser-suite-final.log,build-final.log,live-api.json,live-proof.json,protected-check.json,verification.json}`. Screenshots: `desktop.png`, `mobile-board.png`, `mobile-paper.png` (plus full mobile board). The isolated preview copy and empty-source 45-day configuration remain in this directory. Temporary ports **5002/5174** are stopped after verification; start/stop commands are in RUN_LOCAL.md. AGENTS.md records the durable navigation/design requirements.

Limits: browser checks used desktop Chromium with mobile viewport emulation, not physical-device Safari/Firefox testing. Saved source uncertainties remain unchanged; this frontend task does not reverify organizers or seat availability. No outstanding implementation blocker.

## Attached board sections and prominent notes — November 23, 2026, 20:56 PHT

Follow-up on `feat/campus-bulletin`, frontend only:

- Section tabs now attach directly to the top edge of the cork board, below search/topic/format/registration controls. After the 21:12 PHT correction, only the selected tab uses its section accent: **green Upcoming**, **blue All**, **red Past/finished**, **orange Date unconfirmed**, **gray Watchlist**, **muted purple Archived**. Unselected tabs are white with subdued text and borders. The board keeps its original wood-colored frame; the heading stamp, selected card/date and paper eyebrow retain fixed colors. Cork texture, filters, ranking, keyboard tab navigation and mobile Back behavior remain intact. Mobile tabs scroll horizontally without widening the page.
- Review reasons and source notices now appear in an expanded **Important notes** callout near the paper title, before schedule/eligibility/signup facts. Strong orange border, heading, icons and larger text make them visible without relying on color alone. Cards with source notices but no review flag show **Notes to check**; review badges have stronger contrast. Facts and note wording still come from the existing API.
- Changed `frontend/src/App.tsx`, `styles.css`, and `e2e/campus-board.spec.ts`; AGENTS.md records the durable placement/color rules. Startup commands in RUN_LOCAL.md are unchanged.
- Verification: **41 individual Chromium checks passed**: 39 passed in the full run, and the two new desktop/mobile accent checks passed on rerun after fixing CSS specificity. The new checks cover attached placement, six distinct matching accents, keyboard selection, and notes visible ahead of facts on desktop/mobile. **TypeScript/Vite build and `git diff --check` passed**. Real saved-event screenshots have no browser errors, POST requests or mobile horizontal overflow. Protected backend/configuration/existing-database/benchmark hashes are unchanged; no collector ran.
- Evidence: `data/board-sections/{browser-tests.log,tabs-recheck.log,build-final.log,browser-proof.json,verification.json}`; screenshots `upcoming-desktop.png`, `finished-desktop.png`, `unconfirmed-desktop.png`, `watchlist-desktop.png`, `archived-desktop.png`, `notes-mobile.png`, `board-mobile.png`. Verification used an isolated copy of the saved preview with collection disabled; temporary ports 5002/5174 are stopped afterward. No merge/deployment or source-data change. Physical mobile-device testing remains outside this Chromium viewport check.

### Selected-tab-only color correction — November 23, 2026, 21:12 PHT

Updated `frontend/src/styles.css` to restrict section colors to the active tab, restoring the original wood frame and fixed card/paper colors. White inactive tabs use subtle neutral text/borders and a neutral hover. Important notes remain prominent. Updated the two existing section-style checks in `frontend/e2e/campus-board.spec.ts` and the durable rule in AGENTS.md.

New verification: **2 targeted desktop/mobile Chromium checks passed**, exercising all six selections, white inactive tabs, keyboard navigation and unchanged frame colors; **TypeScript/Vite build and `git diff --check` passed**. Logs: `data/quiet-tabs/{browser-tests.log,build.log}`. No full-suite rerun for this CSS-only correction; the preceding 41-check result belongs to the earlier checkpoint. Browser fixtures required only temporary Vite, stopped after verification. No backend, collector or database was started or changed; no merge/deployment.

### Bottom directory controls — November 23, 2026, 21:24 PHT

Removed the redundant section heading stamp and count row inside the board; section tabs retain visible labels/counts, and filtered counts remain announced to screen readers. This supersedes the heading-stamp reference above. Moved Fetch, the now-labelled **Refresh saved listings** button, collection progress/completion/warnings, and loaded timestamp into **Directory updates** below source coverage. Refresh failures appear beside these controls while preserving saved results; initial load errors remain above the board. Clear filters stays with the search/filter controls. Existing fetch authorization, polling and retry behavior are unchanged.

Affected paths: `frontend/src/{App.tsx,styles.css}`, `frontend/e2e/directory.spec.ts`; durable guidance and UI instructions updated in AGENTS.md and RUN_LOCAL.md. **18 targeted Chromium browser checks passed**, covering desktop/mobile placement, completion messages, refresh failures, fetch polling/retries, filtering, keyboard selection, tab colors and mobile Back. **TypeScript/Vite build and `git diff --check` passed**. Evidence: `data/directory-controls/{build.log,browser-tests.log}` and desktop/mobile `directory-updates.png` screenshots under `browser-results/` (mock API fixtures, not live listings).

Verification used temporary Vite only; no backend, collector, database, ranking or benchmark changes. The full browser suite and physical-device testing were not rerun for this layout change. No merge or deployment. Startup commands are unchanged.

### Header timezone placement — November 23, 2026, Asia/Manila

Moved **Asia/Manila · PHT** to the right of **The student tech noticeboard** in a shared header row (`frontend/src/App.tsx`, `styles.css`). Removed the empty filter-footer space when no filters are active; Clear filters remains with the controls. TypeScript/Vite build, four existing desktop/mobile browser checks and `git diff --check` passed. Additional mocked-API layout checks at 1366, 390 and 320px confirmed aligned row centers and no horizontal overflow. Evidence and header screenshots: `data/hero-timezone/`. Browser verification used Chromium viewport emulation, not physical devices. No backend/database changes or collector run; temporary Vite stopped afterward. No merge/deployment; startup instructions unchanged.

### Shorter inactive tabs and simpler header — November 23, 2026, Asia/Manila

Removed the “Find a tech event. Pin it open to see the details.” subtitle and its unused styles. Selected section tabs keep their original 52px desktop / 48px mobile height; inactive tabs are 20px shorter with aligned bottoms, so their tops sit lower. Existing active-only colors, white inactive tabs and board frame are unchanged. Affected: `frontend/src/{App.tsx,styles.css}`; AGENTS.md records the final height rule.

TypeScript/Vite build, four existing desktop/mobile Chromium checks and `git diff --check` passed. Additional mocked-API geometry checks verified original selected heights and the 20px difference for all six sections at 1366/390px. Logs, geometry results and screenshots: `data/raised-tabs/` (final screenshots show shortened inactive tabs, not enlarged selected tabs). No full-suite or physical-device run. No backend/database/collector changes, merge or deployment; temporary Vite stopped after verification.

### Chronological event listings — November 23, 2026, Asia/Manila

At the user's request, frontend listing order now follows the Manila calendar date displayed on each card, earliest first within the separate PH / international-online groups, across section tabs. Signup status and free pricing no longer take precedence. Shared `eventDay()` in `frontend/src/App.tsx` keeps sorting consistent with card dates (start, competition date, or labelled parent-event date). Unknown/conflicting dates go last; deadline-only listings remain undated. Same-day ties retain input order without inventing times for date-only facts. This supersedes earlier checkpoints describing the original sorting as unchanged; backend ranking/data are untouched.

Updated the two old signup/price priority tests in `frontend/e2e/directory.spec.ts` to assert chronological order with self-contained fixtures; added desktop/mobile date regressions in `campus-board.spec.ts` covering shuffled input, Manila rollover, parent/competition dates, undated/conflicting entries, geography groups and filtering. **10 individual Chromium checks passed**: eight initially, plus the two new sorting checks after narrowing their date locator to exclude deadline labels. TypeScript/Vite build and `git diff --check` passed. Evidence: `data/date-order/{build.log,browser-tests.log,sorting-recheck.log}`. Checks used mocked API data, not a full live-API or physical-device run. AGENTS.md updated. Temporary Vite stopped; no backend, collector, database, benchmark, merge or deployment changes. Startup instructions unchanged.

### Visible listings update time — November 23, 2026, Asia/Manila

Added **Listings last updated** immediately below The Campus Board title, visible on arrival on desktop/mobile, as requested for event-data freshness. `frontend/src/App.tsx` selects the latest valid, timezone-qualified `sources[].last_success` and displays its date/time in PHT with a semantic `<time>`. Page reloads/Refresh, newer failed attempts and API `generated_at` do not advance it. Missing/invalid timestamps show **Not recorded yet**; initial loading/failure use Checking/Unavailable. The timestamp means latest successful source fetch, not website code revision or a guarantee all sources are fresh; its tooltip explains this and source coverage retains individual checks. Existing Directory loaded remains separate. Styling is in `frontend/src/styles.css`; no login system was added.

TypeScript/Vite build and `git diff --check` passed. **Six individual Chromium browser checks passed**: four existing desktop/mobile rendering/control checks initially, plus two freshness checks after fixing their initial-request count for React development mounting. Coverage includes visibility on arrival, offset comparison, PHT conversion, stable time on refresh/failed attempts, advancement for newer success, and missing/invalid timestamps. Evidence and mocked-data screenshots: `data/listings-updated/{build.log,browser-tests.log,freshness-recheck.log,browser-results/}`. No full-suite/live-source/physical-device check. AGENTS.md updated; backend, collector, database and benchmark untouched. Temporary Vite stopped; no merge/deployment or startup-command changes.

### Public homepage copy — November 23, 2026, Asia/Manila

Updated navbar/H1/subtitle to the exact copy recorded above in `frontend/src/App.tsx`; removed the student-only eyebrow without replacement. Timezone placement was subsequently tightened as recorded below; freshness stays visible below the new subtitle. `frontend/index.html` has the exact browser title. `frontend/src/styles.css` adds modest subtitle spacing/responsive type and removes the fixed 320px body minimum that clipped the header beside a reserved scrollbar at 320px. Existing narrow-screen navigation wrapping handles that width. Board, paper, colors, filters, navigation destinations and event-data behavior are unchanged. No repository/package/URL rename.

Updated existing header expectations in `frontend/e2e/directory.spec.ts`; **four desktop/mobile Chromium checks passed**, including exact brand/title/subtitle, absent eyebrow and retained timezone/freshness. **TypeScript/Vite build and `git diff --check` passed**. Additional screenshot/geometry review at **1366, 760, 390 and 320px** found no overlap or horizontal overflow; subtitle wraps to two lines on narrow mobile, and navigation wraps cleanly at 320px. Evidence: `data/public-header/{build.log,browser-tests.log,layout.json,header-1366.png,header-760.png,header-390.png,header-320.png}`. Mocked API/Chromium viewport verification only; no physical-device/full-suite run. AGENTS.md and this handoff updated; RUN_LOCAL.md commands unchanged. Temporary Vite stopped; no backend/collector/database changes, commit, push or deployment.

### Title-aligned timezone — November 23, 2026, Asia/Manila

`frontend/src/App.tsx` and `styles.css` remove the separate timezone row above the H1. The hero uses a shared grid row with timezone top-aligned to the right of The Tech Board, eliminating the extra top space. At 600px and below, timezone follows the freshness line on the right to keep the full title/subtitle readable. Exact copy, navigation, freshness semantics and board behavior are retained.

TypeScript/Vite build, four existing desktop/mobile header/freshness checks and `git diff --check` passed. Geometry checks and screenshots at 1366/760/390/320px confirm wide-screen top alignment and no overlap/overflow. Evidence: `data/title-timezone/{build.log,browser-tests.log,layout.json,header-1366.png,header-760.png,header-390.png,header-320.png}`. Chromium/mocked API only; no physical-device/full-suite run. Handoff updated; temporary Vite stopped. No backend/data/collector changes, commit, push or deployment.

## Keeping this handoff current

**Every agent that changes the system must update this file before finishing.** Update the affected current-state sections, date, tests actually run, and remaining work. Update `AGENTS.md` for durable rule changes and `RUN_LOCAL.md` for changed run/stop instructions. Do not preserve stale counts as current facts or silently rewrite historical benchmark results.

This file and `AGENTS.md` were created on November 23 as a documentation-only handoff. Their creation did not rerun application tests, collect events, alter databases, or change the previously reported verification results. Markdown links and diff formatting were checked.
