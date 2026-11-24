# CommunIT project handoff

Last updated: **November 24, 2026, Asia/Manila**.

Read [AGENTS.md](AGENTS.md) for durable rules and [RUN_LOCAL.md](RUN_LOCAL.md) for setup and checks. This is current implementation context, not a claim about running processes or live source availability. Superseded checkpoints are in the [archived November 23–24 handoff](docs/archive/project-context-2026-11-24.md); the [archive index](docs/archive/README.md) records artifact locations and preservation decisions.

## Pinned-notice redesign · November 24, 2026, Asia/Manila

Implemented the approved “Proposed” notice from `CommunIT-notice-study.html` on `feat/pinned-notice-redesign`, based on latest fetched main **`b59a003`**. Existing browser-title spelling corrections were retained. `frontend/src/App.tsx` reuses `EventDate` beside the supported schedule/venue after review notes; only remaining facts appear in the grid. Parent-event dates, conflicts, deadlines, Manila precision and organizer-link selection retain their existing semantics. `frontend/src/styles.css` adds the green paper edge/month strip, responsive title, one 210 ms stamp press, underlined organizer action and quieter green search panel. The approved paper tabs, cork and date-first cards remain.

**Verified:** production TypeScript/Vite build; **35 Chromium browser tests passed** covering long titles/addresses at 1366/390/320 px, uncertainty/parent dates, separate deadlines, empty grids, URL deduplication, desktop selection/list stability, mobile Back focus/scroll at 390/760 px, reopening the selected notice, reduced motion and keyboard focus. A read-only saved-preview check rendered 41 saved records with no page errors and confirmed the organizer hover/pressed transforms. [Review notes and desktop/mobile screenshots](docs/reviews/pinned-notice-2026-11-24/README.md) describe coverage and reproduction; detailed local logs are under ignored `data/pinned-notice/`.

No live collection, main database access, backend/schema/API/configuration changes or deployment. Backend tests and Firefox/WebKit were not run for this presentation-only change; external organizer pages were not reverified. Startup commands are unchanged; this session used the existing isolated preview through Vite **5174** because 5173 belongs to another checkout. The existing preview remains running.

## Architecture

CommunIT lists Philippine tech meetups, workshops, conferences and competitions, plus international online opportunities available to Filipinos. The repository is `ZittoZzz/CommunIT`; legacy package names and deployment defaults remain unchanged.

| Area | Current entry points |
| --- | --- |
| Flask API | [backend/app.py](backend/app.py); `GET /api/events`, `GET /api/health` |
| SQLite storage | [backend/db.py](backend/db.py); events, announcement revisions, first-seen times, source membership and collection history |
| Public projection | [backend/public_directory.py](backend/public_directory.py), [backend/topics.py](backend/topics.py), [backend/verification.py](backend/verification.py) |
| Collection | [backend/collect.py](backend/collect.py), existing adapters and bounded public-page discovery |
| Source loading | [backend/source_index.py](backend/source_index.py); [sources.json](sources.json), [source-index.json](source-index.json), [sources.community.json](sources.community.json) |
| Frontend | React/TypeScript/Vite; [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/styles.css](frontend/src/styles.css) |
| Verification | [tests/](tests/) (pytest), [frontend/e2e/](frontend/e2e/) (Playwright) |

Normal listings flow through `backend.db.events()` → public API projection → React. Topic and legacy display repairs use retained evidence without rewriting historical payloads. Stable numeric Meetup event IDs support revision/duplicate display reconciliation; original rows and conflicting dates remain available for review.

## Preview and data boundaries

- `data/ctfinder.sqlite3` is the protected main database. Backend startup can initialize schema and register/reconcile sources: always set `CTF_DATABASE` to an isolated copy before starting it.
- Fresh clones contain no ignored SQLite data. Supply a populated saved snapshot explicitly with `backend.prepare_preview --source`; the helper reads the source in read-only mode, refuses the main path as a destination, reuses populated previews and backs up intentional replacements. See [the setup procedure](RUN_LOCAL.md#2-prepare-an-isolated-preview).
- Ordinary preview paths are `data/local-preview.sqlite3` and `data/local-preview-sources.json`. The latter extends `../sources.community.json` and sets a 45-day listing window. Keep `CTF_ENABLE_MANUAL_FETCH=0`.
- Default preview ports are Flask 5001 and Vite 5173. Set `VITE_API_TARGET` and `PLAYWRIGHT_BASE_URL` to the servers actually running; Playwright otherwise defaults to 5000. Do not infer current service state from old PID files or reports.
- Keep useful local snapshots/logs under ignored `data/`; neither these files nor historical `/tmp` captures are guaranteed to exist in another checkout. Build checks use an isolated output directory rather than installed `frontend/dist`.

## Current public behavior

- Navbar home link: **CommunIT**, with the cork/two-note inline logo. Browser title: **Tech Board | CommunIT**; favicon: [frontend/public/communit.svg](frontend/public/communit.svg). There is no visible hero heading; **Tech events** remains an accessible hidden H1. **Philippines · PHT** sits beside Events; dates use Asia/Manila.
- The Campus Bulletin cork board has compact date-first cards and one pinned detail paper. Desktop selection preserves list position; mobile Back restores filters, scroll and selected-card focus. Listings sort by displayed Manila calendar day within separate PH/international-online groups; unknown/conflicting dates go last, with stable same-day ties.
- Public tabs are **Upcoming**, **Past**, **Needs confirmation**, **Archive**. Needs confirmation combines backend unconfirmed/watchlist records without changing their meaning. Undated unresolved leads expire after 45 days from first discovery into Archived leads; rediscovery does not reset verification or imply completion.
- Controls are **Search events**, **Browse by interest**, **How to attend**. Registration never filters public listings. **Interests in these listings** with **Select to filter** shows at most four categories from current section/search/attendance matches before interest filtering; chips and dropdown share selection. Unsupported topics stay visible under All interests.
- Important review/source notes precede a shared card/notice date stamp beside the supported schedule and venue. Parent-event dates and deadlines remain distinct. The **What we can get** grid contains remaining attendance, interests, eligibility, price, account and signup/deadline facts and disappears when empty. Preserve original date precision; missing facts stay absent. Current fully fetched event-page location evidence can supply venues; organizer addresses, stale or search-only evidence cannot.
- Primary **View organizer’s page** and a distinct **Register** action remain below collected facts. Internal evidence/history, route inventories and collector diagnostics are not shown in the public notice. The underlying records are retained.
- **Listings last updated** uses `listings_updated_at`, the latest retained verified event-page check among saved listings; missing/invalid values omit the entire line. **Refresh saved listings** below the board reloads stored data and does not collect. There is no public Fetch events button or source-health panel.

## Discovery decisions and evidence

Use the broad community profile for explicitly authorized community collection. It excludes the legacy individual AWS seed and applies profile-local qualification decisions; CTF-oriented deployment defaults remain separate. Reconcile complete profile membership before partial runs and retain historical sources/events. Read [source-admission rules](docs/source-index.md) and the [November 23 qualification report](docs/source-quality-2026-11-23.md). Source routes/configurations were not changed by this cleanup.

Topics require event evidence: Cloud and DevOps remain separate, organizer/tool names are insufficient, and a bare CTF agenda heading does not classify an entire conference. A retained matching HackForGov/Hack4Gov series title can establish Cybersecurity, including for a search lead, but verifies no schedule, signup, fee or eligibility. Preserve unknown facts, conflicting dates and the difference between blocked access and a successful empty check.

Benchmark inputs remain evaluation-only. Frozen [November 22 results](docs/prototype-iteration-2026-11-22.md) retain the original **0/8 discovery, 0/4 actionable** blind score and later **8/8, 4/4** known-reference regression. The [November 23 report](docs/benchmark-2026-11-23.md) retains **10/10 event matches, 9/10 reference URLs**, a known-reference result rather than a blind or complete-field pass. These reports, raw evidence and original scores were not revised. Inspect copies of saved benchmark databases only; archived commands are historical records, not current setup instructions.

## Browser-title spelling — November 24, 2026, Asia/Manila

Corrected **Tech Board | CommunT** to **Tech Board | CommunIT** in `frontend/index.html`, the existing browser-test expectation and current AGENTS/handoff guidance. Favicon and navbar are unchanged. TypeScript/Vite build and a targeted Chromium title/favicon check on port 5174 passed with mocked API data; `git diff --check` passed. Evidence: `data/title-spelling/{build.log,browser-check.json}`. No full browser suite, backend/database change, collection or deployment; the existing preview remains running.

## Earlier docs cleanup verification

Rechecked against **`dd3356cf102bbc5828b0ae93a18cffe296f46d23`** (the audit baseline), with existing interest-label edits in App/CSS/e2e and AGENTS/handoff preserved. This cleanup changes documentation and removes only the unused `frontend/public/flag.svg`; no app logic, API, schema, collector, source configuration or test was changed for it. The favicon, browser title, inline SVG/icons and organizer actions are preserved.

- README is a short CommunIT overview; RUN_LOCAL uses repo-root commands, explicit saved-snapshot preparation, isolated databases and the actual Playwright preview URL.
- Superseded handoff checkpoints moved to `docs/archive/project-context-2026-11-24.md`. The initial `desktop.png`, `mobile.png` and `verification.json` moved together to `docs/archive/initial-verification-2026-11-21/`; their bytes and relative screenshot references are preserved. The coverage report link and archive index locate them.
- **814 backend tests passed** with temporary fixtures, an explicit isolated fallback DB and no live collection. **TypeScript/Vite build passed**, output under `data/docs-cleanup/build/`. All **67 local Markdown links/anchors** and **9 shell blocks** passed validation; the configuration snippet loaded the same 33 source definitions from a differently named test checkout. Hash checks preserved all unrelated tracked files and moved evidence bytes. Logs/receipts are under `data/docs-cleanup/`; existing local Python/Node dependencies were reused, not freshly installed.
- No new browser suite or live-data check was run for this docs/unused-asset cleanup. The preceding interest-label task passed five Chromium fixture checks at 1366/760/390/320px; its evidence remains under `data/interest-context/` and its checkpoint is archived. Those are earlier results, not a new full-browser pass.

No main database access, live collection, service changes, commit, push or deployment. Ignored benchmark snapshot/config files are absent from this checkout, so benchmark replay instructions were removed rather than assumed valid. Historical machine-specific paths and unavailable `/tmp` links remain in frozen reports/archive as provenance; the current setup does not depend on them.

## Open work and limitations

- Optional manual-collection cleanup and larger API/React refactors are deferred. The existing local manual-collection implementation remains disabled by default, explicit nonproduction-DB and localhost/token guarded; disabled/nonlocal collection and `/api/sources` return generic 404s.
- Coverage is incomplete. Source restrictions, Tavily quota and bounded calendar/page traversal can leave events or facts unverified; provisional publisher candidates still need qualification. No live source availability or current listing count was established in this cleanup.
- The known-reference work did not establish autonomous discovery of the exact AWS website, verified Meetup RSVP controls, Conf42's no-registration status, full projection of AI Unwrapped's attendee-only restriction or general cross-platform AWS merging. Saved date conflicts and search-only HackForGov leads still require publisher evidence; do not infer fixes from newer fetch timestamps.
- Frozen benchmark files and path-coupled raw evidence remain in place. In particular, classification verification embeds LearnPossible screenshot names and source research records reference other `docs/` evidence paths. See [archive preservation notes](docs/archive/README.md#kept-in-place) before reorganizing them.

Keep this file focused on current decisions, verified state and remaining work. Put future superseded checkpoints in the archive without changing historical scores or evidence.
