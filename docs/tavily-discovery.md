# Tavily keyless discovery — 21 November 2026

This iteration tests Tavily directly from the project Python environment, then uses the same free keyless API in the daily collector. No API key, Facebook credentials, cookies, paid plan, or paid fallback is used. Brave settings are unchanged.

## Queries and transport

1. Facebook only: `site:facebook.com Philippines cybersecurity CTF competition registration`
2. Unrestricted web: `Philippines capture the flag CTF competition registration`

Requests use `POST https://api.tavily.com/search`, `X-Tavily-Access-Mode: keyless`, basic search, 20 maximum results, and no Authorization header. The Facebook query also sets `include_domains: ["facebook.com"]` with restrict mode. Generated answers, raw content, and images are disabled. No event title, author, event dates, Facebook IDs, or sample URL enters either request. The provider may return a normalized query echo; the audit preserves the exact requested query separately.

Tavily documents [free keyless search](https://docs.tavily.com/documentation/keyless) and [permission to retain search output](https://help.tavily.com/articles/1612400809-storing-caching-retaining-output), subject to underlying publisher rights. This application retains URL/title audits and extracted facts, not complete snippets or media.

## Initial live attempts

- At 23:20 PHT, both direct requests returned HTTP 429 with `daily_cap_reached` and Retry-After values of 15 and 14 seconds. These were errors, not successful searches with zero matches.
- At 23:21 PHT, a bounded retry after that interval returned HTTP 200 for both queries. Facebook leads included DICT MIMAROPA, Philippines National CERT, and DICT Bicol announcements, alongside unrelated foreign results. The unrestricted query also returned generic CTF resources. No organizer filters were applied to these diagnostic responses.
- A later check at 23:25 PHT returned a longer HTTP 429 cooldown of approximately 15 minutes. Subsequent live verification was scheduled after the advertised interval. A retry interval is an instruction about when another request is permitted, not a guarantee that quota will be available then.

## Implementation

`backend/tavily.py` runs both configured queries and records every returned URL/title under `sources[].searches[].results` **before** applying scope or organizer checks. `sources[].decisions` records acceptance/rejection reasons. Unknown, failed, and skipped requests remain distinguishable from successful empty responses.

Search snippets can contain unrelated posts or “related reels.” They are never used to extract dates, registration, eligibility, publication time, or event identity. A result title must identify a competition edition and independently support Philippine scope. A configured publisher counts as organizer only for its verified series or when the title explicitly names it as host. Otherwise, organizers remain unconfirmed. The link is labeled “Search result · verify source.” This conservative rule may withhold legitimate leads; the unfiltered audit remains available for analysis.

Equivalent numeric Facebook URLs deduplicate using an explicit post identity. Opaque permalink tokens do not establish equivalence to a supplied numeric ID. Existing full-source facts take precedence over search results. Failed searches preserve earlier listings and do not stop other sources. A short quota interval permits one retry; a longer or exhausted limit skips the remaining Tavily queries without attempting paid or keyed access.

## Reproduce

Unfiltered diagnostic; no SQLite database is opened:

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
.venv/bin/python -m backend.tavily_check --report /tmp/ctf-search-audit.json
```

Optional `--title` and `--post-id` arguments only compare returned results locally. They never alter the queries. A snippet-only name match is a lead requiring verification, not proof that the result is the original announcement.

The normal daily collector, isolated to a fresh temporary database:

```bash
CTF_CHECK_DIR="$(mktemp -d)"
.venv/bin/python -m backend.collect --database "$CTF_CHECK_DIR/events.sqlite3" --report "$CTF_CHECK_DIR/run-1.json"
.venv/bin/python -m backend.collect --database "$CTF_CHECK_DIR/events.sqlite3" --report "$CTF_CHECK_DIR/run-2.json"
CTF_DATABASE="$CTF_CHECK_DIR/events.sqlite3" PORT=5001 .venv/bin/python -m backend.app
```

Inspect each query's status and attempts as well as listing counts: unchanged counts after HTTP 429 demonstrate failure preservation, not a successful second search. Respect any advertised long cooldown before retrying. Search ranking and availability can change between runs.

## Observed verification results

The complete [unfiltered URL list](tavily-search-results.md) preserves all 40 results from the first normal run before organizer checks. [Machine-readable verification](tavily-verification.json) includes both full collection reports, titles, URLs, filter decisions, resulting listings, and comparisons. Both normal runs used the repository’s default source configuration with no event-specific arguments, seeded records, or response cache.

| Query | Status in both runs | Results per run | Facebook results | Target title/URL matches | Exact numeric post matches |
| --- | --- | ---: | ---: | ---: | ---: |
| `site:facebook.com Philippines cybersecurity CTF competition registration` | HTTP 200 | 20 | 20 | 0 | 0 |
| `Philippines capture the flag CTF competition registration` | HTTP 200 | 20 | 3 | 0 | 0 |

**A — RAIJIN competition independently discovered: not verified.** No returned title or URL identified it. The last successful step was retrieving both complete broad result sets; this is a retrieval gap in these queries, before organizer filtering. No published listing was created for it.

**B — original Facebook post independently discovered: not verified.** None of the returned Facebook URLs matched numeric post ID `1803852510919263`. No opaque permalink was resolved as equivalent. No Facebook post was fetched. These searches do not prove that Tavily never indexed the post.

The target name and ID were used only to compare the returned title/URL audit offline. Full snippets were not retained and were not used as identity evidence. No known-title search was performed.

Four useful Facebook results became search-only listings:

| Listing | Result URL | Schedule / registration |
| --- | --- | --- |
| HackForGov edition-5 · MIMAROPA | [Returned Facebook result](https://www.facebook.com/dictr4b/posts/-%F0%9D%90%87%F0%9D%90%80%F0%9D%90%82%F0%9D%90%8A%F0%9D%90%85%F0%9D%90%8E%F0%9D%90%91%F0%9D%90%86%F0%9D%90%8E%F0%9D%90%95-%F0%9D%90%8C%F0%9D%90%88%F0%9D%90%8C%F0%9D%90%80%F0%9D%90%91%F0%9D%90%8E%F0%9D%90%8F%F0%9D%90%80-%F0%9D%9F%90%F0%9D%9F%8E%F0%9D%9F%90%F0%9D%9F%94-%F0%9D%90%91%F0%9D%90%84%F0%9D%90%86%F0%9D%90%88%F0%9D%90%92%F0%9D%90%93%F0%9D%90%91%F0%9D%90%80%F0%9D%90%93%F0%9D%90%88%F0%9D%90%8E%F0%9D%90%8D-%F0%9D%90%8D%F0%9D%90%8E%F0%9D%90%96-%F0%9D%90%8E%F0%9D%90%8F%F0%9D%90%84%F0%9D%90%8D-%F0%9D%90%80%F0%9D%90%9B%F0%9D%90%A8%F0%9D%90%AE%F0%9D%90%AD-%F0%9D%90%AD%F0%9D%90%A1%F0%9D%90%9E-%F0%9D%90%82%F0%9D%90%A8%F0%9D%90%A6%F0%9D%90%A9%F0%9D%90%9E%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7the-hackfor/1089592793724382) | Schedule TBA / unconfirmed |
| HackForGov 2026 · Region V — Bicol · Qualifier | [Returned Facebook result](https://www.facebook.com/DICTRegionVBicol/posts/%F0%9D%90%82%F0%9D%90%9A%F0%9D%90%A5%F0%9D%90%A5%F0%9D%90%A2%F0%9D%90%A7%F0%9D%90%A0-%F0%9D%90%81%F0%9D%90%A2%F0%9D%90%9C%F0%9D%90%A8%F0%9D%90%A5%F0%9D%90%AC-%F0%9D%90%A7%F0%9D%90%9E%F0%9D%90%B1%F0%9D%90%AD-%F0%9D%90%A0%F0%9D%90%9E%F0%9D%90%A7%F0%9D%90%9E%F0%9D%90%AB%F0%9D%90%9A%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7-%F0%9D%90%A8%F0%9D%90%9F-%F0%9D%90%9C%F0%9D%90%B2%F0%9D%90%9B%F0%9D%90%9E%F0%9D%90%AB%F0%9D%90%AC%F0%9D%90%9E%F0%9D%90%9C%F0%9D%90%AE%F0%9D%90%AB%F0%9D%90%A2%F0%9D%90%AD%F0%9D%90%B2-%F0%9D%90%A9%F0%9D%90%AB%F0%9D%90%A8%F0%9D%90%9F%F0%9D%90%9E%F0%9D%90%AC%F0%9D%90%AC%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7%F0%9D%90%9A%F0%9D%90%A5%F0%9D%90%AC%EF%B8%8Fdict-bicol-invites/1040492329050739) | Schedule TBA / unconfirmed |
| HackForGov 2026 · Region VII — Central Visayas | [Returned Facebook result](https://www.facebook.com/DICTr7/posts/-hackforgov-central-visayas-2026-registration-now-open-dict-region-7-proudly-lau/1522802749891574) | Schedule TBA / unconfirmed |
| HackForGov 2026 · Region IV-A — CALABARZON | [Returned Facebook result](https://www.facebook.com/dictr4a/posts/%F0%9D%97%9B%F0%9D%97%94%F0%9D%97%A3%F0%9D%97%A3%F0%9D%97%98%F0%9D%97%A1%F0%9D%97%9C%F0%9D%97%A1%F0%9D%97%9A-%F0%9D%97%A1%F0%9D%97%A2%F0%9D%97%AA-%F0%9D%97%9B%F0%9D%97%AE%F0%9D%97%B0%F0%9D%97%B8%F0%9D%97%99%F0%9D%97%BC%F0%9D%97%BF%F0%9D%97%9A%F0%9D%97%BC%F0%9D%98%83-%F0%9D%9F%B1-%F0%9D%9F%AE%F0%9D%9F%AC%F0%9D%9F%AE%F0%9D%9F%B2-%F0%9D%97%96%F0%9D%97%94%F0%9D%97%9F%F0%9D%97%94%F0%9D%97%95%F0%9D%97%94%F0%9D%97%A5%F0%9D%97%AD%F0%9D%97%A2%F0%9D%97%A1-%F0%9D%97%A5%F0%9D%97%B2%F0%9D%97%B4%F0%9D%97%B6%F0%9D%97%BC%F0%9D%97%BB%F0%9D%97%AE%F0%9D%97%B9-%F0%9D%97%96%F0%9D%97%BC%F0%9D%97%BA%F0%9D%97%BD%F0%9D%97%B2%F0%9D%98%81%F0%9D%97%B6%F0%9D%98%81%F0%9D%97%B6%F0%9D%97%BC%F0%9D%97%BB%F0%9D%99%8F%F0%9D%99%9D%F0%9D%99%9A-%F0%9D%99%98%F0%9D%99%A4%F0%9D%99%A2%F0%9D%99%A5%F0%9D%99%9A%F0%9D%99%A9%F0%9D%99%9E%F0%9D%99%A9%F0%9D%99%9E%F0%9D%99%A4%F0%9D%99%A3-%F0%9D%99%9E/1534594968700265) | Schedule TBA / unconfirmed |

Discovery path for each listing: the generic Facebook query → the returned Facebook URL above → the corresponding event in SQLite → the site’s Upcoming & live section. The UI labels the link **Search result · verify source**, shows the original query in announcement history, and keeps the organizer, posted time, eligibility, competition dates, and registration status unconfirmed. Explicit edition/year and regional identity come from the result title; the URL slug is not used to invent facts.

These were found without adding their publisher accounts to the organizer configuration. This verifies discovery of posts from previously unconfigured publishers. It does not verify their full-post content or general discovery of every Philippine organizer. The unrestricted query supplied other potential leads, including Ateneo and LearnCyberPH, but none met the current title-only publication requirements.

| Normal run | Started (UTC) | Events | Announcements | New announcements | Tavily |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | 2026-11-21T15:40:51.362927+00:00 | 6 | 7 | 7 | both queries succeeded |
| 2 | 2026-11-21T15:41:38.876776+00:00 | 6 | 7 | 0 | both queries succeeded |

The second run created **zero duplicates or new announcements**. Announcement IDs, event IDs, URLs, first-seen timestamps, revision counts, and stored payloads were identical. This was a successful second live search, not merely unchanged data after a failed fetch.

Other working sources remained operational: ROOTCON Bluesky returned 146 posts and accepted 3 announcements; HackTheNorth returned 11 links; UP ACM 1 link; both PUP feeds returned 10 entries; CTFtime returned 180 records and accepted none. DICT and CERT-PH remained blocked by HTTP 403 when verifying robots.txt. ROOTCON’s website remains policy-restricted. Brave remains `needs_credentials`; its storage setting was not changed.

**Validation:** 117 backend tests passed, 5 Playwright tests passed, and the frontend production build passed. A separate mobile browser check against the newly collected temporary database displayed all four HackForGov cards, the search-only labels, query provenance, and a fitting 390-pixel layout. Fixtures cover successful repeated search, failed-fetch preservation, numeric URL equivalence, opaque identity uncertainty, full-source precedence, and separate years/regions/competition stages.

Temporary live database: `/tmp/ctfinder-tavily-live-g1p3r4t5/events.sqlite3`. Preview: `http://127.0.0.1:5001`. The production database, services, and timer were not changed or restarted. Updated source configuration will be used on the next normal collection invocation.

**Smallest next discovery experiment:** test additional generic Philippine university/community query variants through the same unfiltered diagnostic. This improvement already catches indexed regional HackForGov announcements and can catch future explicit Philippine CTF titles, but it has not solved discovery of the supplied competition. Keep any new query reusable and assess its raw results before changing organizer filters.
