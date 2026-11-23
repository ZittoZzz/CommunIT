# IT_Community_PH repository guidance

## Start here

- Read [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) before making changes. It records the latest verified state, completed work, limitations, and evidence paths.
- Use [RUN_LOCAL.md](RUN_LOCAL.md) for preview startup and shutdown. Some README examples use the main database and installed services; do not run those as routine development setup.
- Inspect the current code, `git status`, and relevant configuration. This checkout contains substantial uncommitted work; preserve changes unrelated to the user's task.
- Treat the handoff as a dated checkpoint. Verify current files, database selection, and running processes before acting; do not assume recorded counts or process IDs are still current.

## Scope and data boundaries

- Keep the student-facing brand **IT_Community_PH**. Keep repository/package names unchanged unless the user requests otherwise.
- Reuse the existing collector, storage, normal API, and student listing paths. Preserve existing CTF behavior and the current visual style.
- Use an explicit preview/test database for development. Protect `data/ctfinder.sqlite3` (the main/production database); do not modify it, deployment services, or schedules without user authorization for that action.
- Starting the backend can initialize schema and register source metadata. Set `CTF_DATABASE` explicitly before starting it, even for UI checks.
- Do not run discovery merely to test display changes. When collection is requested, use the authorized public-source workflow and an isolated database. No paid APIs or logged-in Facebook scraping.
- Preserve frozen benchmark artifacts and original scores. Known-reference regression checks are not blind evaluations. Never seed runtime discovery with benchmark titles, individual event URLs, expected answers, or replay fixtures.
- Keep useful local databases and verification output under ignored `data/` paths. `/tmp` is suitable for disposable tests, not the only copy of a useful snapshot. Do not commit databases, credentials, or captured private data.

## Event behavior

- Preserve date-only precision. Use Asia/Manila calendar days; do not invent start times or deadlines. Keep conflicting dates unresolved.
- Keep the preview's 45-day listing window and separate PH opportunities from international online opportunities. Unverified recurring signups and undated leads belong in Watchlist under that view.
- Classify topics from supported event evidence. An organizer name alone does not prove Cloud, and “hackathon” alone does not prove Software Development. Events without supported topics stay visible under All topics.
- HackForGov/Hack4Gov series identity may establish Cybersecurity from a retained matching title citation, including a search-only lead. This does **not** verify its schedule, price, eligibility, organizer identity, or signup.
- A bare CTF agenda heading does not establish a separate competition or make an entire conference a cybersecurity event. Preserve official titles and distinguish conference tickets from competition entry.
- Keep unknown price, deadlines, eligibility, and signup facts unknown. Distinguish blocked/unreadable sources from successful checks with zero matches.

## Verification and handoff maintenance

- Run checks appropriate to the change. For backend behavior, use isolated pytest fixtures; for frontend behavior, use browser checks and the frontend build. Do not launch a production service or collector as a substitute for tests.
- Before finishing a task that changes the system, **update PROJECT_CONTEXT.md** with the resulting behavior, affected paths, verification actually run, and remaining gaps. Use the Asia/Manila date and distinguish new verification from earlier results.
- Update this `AGENTS.md` when durable project rules change. Update `RUN_LOCAL.md` when startup, shutdown, database preparation, ports, or environment variables change. Keep the files consistent.
- Keep the handoff concise and current: revise superseded state, retain significant decisions, and link to detailed reports instead of copying chat transcripts. Do not rewrite frozen historical reports to match later results.
- For unfinished work, record the exact remaining task and blocker. Never claim a check passed if it was skipped, blocked, or only inferred.
- In the final response, state what changed, verification results, material limitations, and whether the handoff was updated.
