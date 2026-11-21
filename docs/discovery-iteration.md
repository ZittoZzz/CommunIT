# Discovery iteration — 21 November 2026

**The supplied acceptance case remains unmet.** The collector was improved and tested live, but neither outcome was established:

| Outcome | Result | Last successful step / blocker |
|---|---|---|
| A — competition independently discovered | **Not verified; absent from the fresh database** | Public publisher feeds and their articles were enumerated, but none returned the competition. The existing source set does not cover the announcement path. |
| B — exact Facebook post independently discovered | **Not verified; no independently found permalink** | No fetched feed/article linked to the post. The optional Brave provider stopped before its first request because a server-side key and storage entitlement were unavailable. |

The sample could be inspected during research, and a sample-led search found a readable event website. Neither is a reusable discovery path. They were not inserted into the database, source configuration, collector queries, tests, or fallback logic. There is **no resulting acceptance-event listing**, including no fabricated “Schedule TBA” listing: even the event's identity must first arrive through a configured discovery source.

## Reproduce the actual normal job

These commands use the exact collector module and default source configuration used by the daily timer. Only the output database and report paths differ. The temporary directory starts empty; no URL, event name, source selection, or prior cache is supplied.

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
CTF_CHECK_DIR="$(mktemp -d)"
.venv/bin/python -m backend.collect --database "$CTF_CHECK_DIR/events.sqlite3" --report "$CTF_CHECK_DIR/run-1.json"
.venv/bin/python -m backend.collect --database "$CTF_CHECK_DIR/events.sqlite3" --report "$CTF_CHECK_DIR/run-2.json"
CTF_DATABASE="$CTF_CHECK_DIR/events.sqlite3" PORT=5001 .venv/bin/python -m backend.app
```

Open **http://127.0.0.1:5001** to view those collected records. The built frontend is already present; on a new checkout, follow the dependency/build commands in [README](../README.md). The existing local service remains at **http://127.0.0.1:5000**. Its scheduled job was also run after these changes.

The final clean run started at **22:28:59 PHT** and completed at **22:29:32 PHT**. The second ran **22:29:33–22:30:02 PHT**. Both returned **2 events and 3 announcements**; the second inserted **0 announcements**. Announcement IDs, event associations, URLs, first-seen timestamps, revision counts, and stored payloads were identical. Full reports, source states, and resulting API listings are saved in [discovery-verification.json](discovery-verification.json), alongside the baseline report from before the changes.

## Where discovery failed

The baseline fresh run found the existing two ROOTCON competitions. It never obtained a candidate announcement for the acceptance competition. This is a **source-coverage failure before event recognition, Philippine filtering, deduplication, or date extraction**. A separate raw CTFtime November–December window also contained no matching event, before applying the Philippine filter. There is no evidence that our parser discarded the acceptance event.

Facebook URL discovery and full-post access remain separate. The research browser/search tool was not turned into an undeclared runtime integration. No supported search API request was tested with credentials, so this investigation cannot establish whether Brave indexes the post. The current optional Brave queries cover three configured organizers, not arbitrary Facebook authors; supplying a key alone does not establish coverage of this case.

The user-provided December 1–4 range was a research clue only. No year, clock times, registration status, eligibility, or end date from sample-led research was published.

## Changes implemented

- Added the recurring [PUP announcements feed](https://www.pup.edu.ph/rss/announcements/) and [PUP news feed](https://www.pup.edu.ph/rss/news/). The example revealed a gap in coverage of university communities, prompting investigation of PUP and its campus cybersecurity community. This adds a **configured publisher**, not automatic discovery of previously unknown organizers. Neither current feed contains the acceptance announcement.
- RSS can follow every new permitted article link, including a generic teaser whose feed excerpt omits “CTF.” Previously, only already accepted articles were revisited. Known articles remain eligible for rechecks after leaving the feed window. Failed fetches preserve their previous facts and links.
- Configurable article/title selectors exclude university navigation, related-news blocks, and footers. A regression check prevents an evergreen CTF description from borrowing a conference edition elsewhere on the page. PUP records additionally require explicit evidence that the university organizes or hosts the contest; a story about students participating in a foreign CTF is insufficient.
- Retain a discovery path and outbound Facebook post links found in an accepted announcement. An independently found university article can now preserve both its own URL and the linked post URL. The UI labels the latter **“Linked only · Full post not accessed.”** It does not turn the linked post into a second fetched announcement.
- Recognize Facebook `story.php` and `permalink.php` URLs as well as post/photo/video paths. The optional search adapter requires the result owner to match a configured account or verified alias. No acceptance-case account or ID was configured.
- Attach field-specific source URLs and short evidence excerpts to extracted facts, and display them under “Sources & updates.” Explicit named-month date ranges retain date precision. Missing years remain ambiguous, and no midnight starts are invented.
- Include accepted URLs, their discovery paths, and related links in collection reports. This makes live discovery auditable without claiming that an offline fixture proves coverage.

## What the live collector returned

| Configured source | Final fresh run | Accepted announcements |
|---|---|---:|
| ROOTCON Bluesky public API | 146 posts read | 3, grouped into 2 competitions |
| HackTheNorth.ph | 11 pages read | 0 |
| UP ACM events | 1 index read | 0 |
| PUP announcements RSS | 10 entries and 10 article URLs checked | 0 |
| PUP news RSS | 10 entries and 10 article URLs checked | 0 |
| CTFtime | 180 event records read across configured windows | 0 Philippine matches |
| DICT and CERT-PH | Robots requests returned HTTP 403 | 0; prior data preserved |
| ROOTCON website | Disabled because of its published automated-extraction restriction | 0; Bluesky remains operational |
| Brave Facebook search | `needs_credentials`; no keyed HTTP request made | 0 |

The two actual listing paths are:

1. [ROOTCON author profile](https://bsky.app/profile/rootcon.bsky.social) → documented `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=rootcon.bsky.social&limit=100&filter=posts_no_replies` → [initial announcement](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvccs3acfk2z) and [completion notice](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mwprmced2e2h) → **ROOTCON 20 CTF**, event ID `775f475db77bea2c6cd288ec`, displayed in **Finished**.
2. Same author feed → [qualifier announcement](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvtlb6qlyc24) → **ROOTCON 20 CTF · Qualifier**, event ID `b33d89e59bd6589135a41f58`, displayed in **Upcoming & live** with **Schedule TBA**, unknown registration, and an age warning. Its accessible text does not confirm an end, so the collector cannot move it to Finished solely because its post is old.

Those URLs were actually found by the normal job. No comparable chain exists for the acceptance case. **Social-post discovery is live-verified for ROOTCON on Bluesky; Facebook discovery is not live-verified.**

## Additional paths investigated

The following were research probes, not added live sources or proof of acceptance:

- PUP's main news/announcement pages were readable; the Santa Maria campus page was under construction. The campus community's `a1sberg.tech` host failed DNS from this runtime.
- Creator portfolios, public blog manifests/feeds, GitHub repositories, and partner announcement pages returned no usable recurring acceptance announcement. An indexed LinkedIn sponsor reshare surfaced during sample-led research, but no supported, configured API was available to discover it during the daily job.
- `vektrsec.com` exposed service pages without a recurring announcement archive. Webverse's readable blog contained technical writeups, not the acceptance event.
- Cyber404's blog and Hackathons PH were excluded after their published terms prohibited the contemplated automated collection. Appkademiya and Opportune PH returned access challenges. No workaround was attempted.
- The documented Bluesky search endpoint returned HTTP 403 for generic Philippine CTF queries; the working author-feed API was retained.

## Verification and future coverage

Backend verification: **46 tests pass**. These include independent fictional feed → article → Facebook-link discovery, a teaser becoming a dated announcement without adding an event, separate qualifiers/finals, failed article/feed preservation, publisher scope, ambiguous/yearless date ranges, Facebook owner validation, provenance updates, and duplicate-run behavior. Fixtures are never imported by the collector. The frontend production build passes. **All 4 Playwright browser tests pass**, covering real collected listings, mobile layout, filters, source health, time precision, error recovery, and an isolated linked-post/evidence fixture. An expanded real listing was also visually inspected at 390px width with no horizontal overflow.

This improvement should catch future explicitly identified PUP-hosted CTF announcements in the configured feeds, including announcements whose full article has details missing from the feed excerpt. It can preserve Facebook links when those articles provide them. Coverage still depends on a publisher actually carrying an announcement, the finite feed window, accessible article text, and the conservative identity/scope parser. A readable recurring source or an authorized search integration that returns this competition is still needed to satisfy A; an independently obtained matching Facebook permalink is still needed to satisfy B.
