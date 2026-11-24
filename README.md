# CommunIT

A community noticeboard for tech meetups, workshops, conferences and competitions in the Philippines, plus international online opportunities available to Filipinos.

Browse saved listings by interest, attendance format and search. The board separates upcoming events, past events, listings needing confirmation and archived leads. Dates use Philippine Time; unsupported dates, prices and signup details stay unconfirmed. **Refresh saved listings** reloads saved data—it does not collect new events.

## Run locally

Follow [RUN_LOCAL.md](RUN_LOCAL.md) for dependencies, an isolated preview database and separate Flask/Vite servers. A fresh clone does not include SQLite data: supply a populated saved snapshot with `backend.prepare_preview --source` as described there. Setup does not require live collection or access to the main database.

## Project layout

- [frontend/](frontend/): React, TypeScript and Vite; cork-board listings and pinned event details.
- [backend/](backend/): Flask API, SQLite storage and public-source collection adapters.
- [tests/](tests/) and [frontend/e2e/](frontend/e2e/): isolated backend fixtures and browser checks.
- [sources.community.json](sources.community.json): broad community profile, separate from the CTF-oriented deployment defaults in [sources.json](sources.json).

Collection is a separate maintenance task. Source admission, evidence requirements and access limits are documented in [docs/source-index.md](docs/source-index.md); source configurations and benchmark references serve different purposes.

For development, read [AGENTS.md](AGENTS.md), the concise [current handoff](PROJECT_CONTEXT.md) and the [verification commands](RUN_LOCAL.md#checks). Historical checkpoints and evidence locations are indexed in [docs/archive/](docs/archive/README.md).
