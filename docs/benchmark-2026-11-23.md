# November 23 community-event benchmark

Evaluated **2026-11-23, Asia/Manila**, against the user's 5:07 p.m. reference set and November 23–January 7 window. This is a ten-event reference set, not an estimate of all available events.

**Result: baseline 1/10 event matches → improved 10/10 event matches, all visible through the normal API.** Nine final matches use the supplied reference URLs. The tenth is the AWS co-organizer's Meetup listing, rather than the supplied standalone website. This is **not a 10/10 exact-URL or complete-field pass**. The standalone website's price/date verification is a separate assisted result below.

## Method and boundaries

- Ran the existing `backend.collect` CLI, normal adapters, SQLite ingestion, API, and frontend. Each scored live run began with an empty isolated database under `data/benchmark-2026-11-23/`.
- Runtime configurations contained recurring calendars and generic queries, not benchmark titles, individual reference URLs, expected answers, or replay pages. Removed the pre-existing individual `aws-mindanao` seed from scored discovery inputs. The main database, existing preview database, deployment configuration, and earlier frozen scores were protected.
- Baseline used the existing configured routes with that seed excluded. It recovered MLH; other routes were absent or did not return the reference URL. Tavily was rate-limited. A sandbox network-failure attempt is retained separately and is not the baseline score.
- Improvements were developed with knowledge of this reference set. Generic ChatGPT public-web searches helped identify recurring calendars; the search provider behind that tool is unspecified. The final scored run did **not** consume those search results or a manifest. This is a **known-reference improvement/regression evaluation**, not a blind evaluation or a Tavily benchmark.
- Final normal profile: [`sources.community.json`](../sources.community.json). It inherits the original CTF sources and adds recurring Meetup, Luma, Conf42 and Devpost calendars plus generic month-generated searches. `sources.json` and `source-index.json` remain unchanged. The local preview configuration now extends this profile; an already-running preview must restart to load it.
- The complete fetched response capture is observation-only instrumentation around the normal network client. It records URL, status, timestamp, bytes and SHA-256 without changing returned content. No paid API, credentials, logged-in Facebook scraping, or access-challenge bypass was used.

## Per-event runtime trace

Every row below was fetched, parsed, accepted, stored, and present in the normal API's Upcoming & live section. Expanded traces, capture paths/hashes, parsed fields and time/price citations are in [`benchmark-2026-11-23-results.json`](benchmark-2026-11-23-results.json). Full accepted/rejected decisions, including unrelated results, are in the local final collector report.

| Reference | Actual discovery route → event page | Parsed outcome and limits |
| --- | --- | --- |
| 120th Agile Philippines Meetup | Meetup Cebu technology calendar → `agilephilippines/events/317188117/` | Nov 25, 18:00–21:00 PHT; PH online established by the matched event's PH group metadata; fee and signup status unknown. |
| PhRUG: Czech Mate! | Meetup Manila technology calendar → `ruby-phil/events/317362935/` | Nov 26, 18:00–21:00 PHT; PH onsite; bring-ID requirement retained; fee unknown. |
| Foundry Agents and Foundry IQ | Meetup Manila technology calendar → `globalaiphilippines/events/317284119/` | Nov 27, 14:30–17:30 PHT; hybrid; laptop and additional Microsoft registration-form requirement retained. No available-seat claim. |
| AWS Student Community Day Mindanao | Recurring UP Mindanao AWS chapter calendar → `aws-sbg-at-university-of-the-philippines-mindanao-campus/events/316992979/` | Accepted under the organizer's title **AWS Student Community Day Davao**. Same Nov 28 date, Ateneo de Davao venue, explicit Davao/Mindanao edition and co-organizer establish the match. This source explicitly gives 09:00–17:00; these are source-provided times, not an inference from the reference's date-only website. Price remains unknown in this autonomous record. |
| Cafe Compute Meetup: Manila | Recurring Luma Cerebras calendar → `luma.com/yneq6wv7` | Nov 30, 18:00–20:00 PHT; PH onsite; approval required; fee unknown. |
| Manila DevOps User Group Event 07 | Meetup Manila technology calendar → `manila-devops-user-group/events/317321759/` | Dec 6, 12:00–15:00 PHT; free from affirmative organizer wording; signup status unknown. |
| AI Unwrapped | Meetup Manila technology calendar → `globalaiphilippines/events/317510987/` | Dec 10, 13:00–17:00 PHT; hybrid; fee unknown. Separate event ID from Foundry despite shared organizer and venue. |
| Conf42: Chaos Engineering | Recurring `conf42.com/` calendar → `conf42.com/chaos2026` | Dec 4, 01:00 PHT, preserving GMT rollover; free online YouTube premiere. Public viewing link retained; the fetched page did not explicitly establish “no registration required,” so account/signup facts remain unknown. |
| MLH Open Source Week | Recurring `ghw.mlh.com/` calendar → organizer edition → `events.mlh.com/events/15199-global-hack-week-open-source-week` | Dec 4, 23:00–Dec 11, 02:00 PHT; free; international online; eligibility retained from organizer evidence. |
| QNX Global Hackathon | Recurring Devpost AI category → `qnx.devpost.com/` → actually linked `/rules` | Registration **and** submission deadline Dec 16, 03:00 PHT; actual start Nov 3 remains separate. Free entry, 18+ rules, Devpost account requirement and readable excluded-country list retained; Philippines is not excluded. |

The five reference Meetup pages did not expose a verifiable RSVP control in the fetched HTML. Their primary organizer pages remain available to the student, but the collector does not turn a presumed RSVP button into an open registration or available seat. The Foundry extra-form requirement is retained. AI Unwrapped's attendee-only link restriction is not projected as a separate parsed fact.

## What changed and why the baseline missed events

| Failure stage | Change |
| --- | --- |
| Source not enabled | Added the reusable community source profile and a bounded `opportunity_calendar` adapter using the existing verification/storage path. Existing CTF behavior is retained. |
| Calendar discovery did not return the URL | Added public city, chapter, publisher and Devpost category calendars. Luma Manila alone did not expose Cafe Compute; the recurring Cerebras calendar did. |
| Found URL, scope filter rejected PH online event | Match Meetup Event → Group metadata, including event ID, organizer URL and PH country. Unrelated recommended groups cannot establish scope. |
| Page shape/topic/price not recognized | Expanded supported technical program wording, dated directory links and Luma category shape; added a conservative standalone organizer-page fallback. Free claims reject negated, conditional and question wording. |
| Typed cutoff/eligibility evidence not followed | Follow the linked Devpost rules within the same bounded page budget; require explicit registration/submission labels, timezone consistency and readable country exclusions. |
| Trace omitted parsed facts | Collector reports now retain parsed fields and field evidence with accepted discoveries, alongside queries, route checks and rejection reasons. |
| Larger listing timed out in browser checks | Hoisted a repeated whole-description title check out of the topic sentence loop. Measured listing projection fell from 2.463 seconds (profiled) to 0.351 seconds; all 35 API event objects were identical before/after. These are local observations, not a general performance guarantee. |
| Minimum advertised ticket price could not display | UI supports `minimum_amount` as “From PHP 199,” preserving individual tiers and unknown inventory. |

Discovery remains bounded. The final Conf42 source hit its eight-page budget and Devpost hit its fifty-page budget; unchecked links are reported as deferred, not absent. Tavily returned HTTP 429 with a 600-second retry instruction; subsequent generic queries were skipped. The final ten matches came from calendar routes, not successful Tavily queries.

## Separate AWS website verification

An earlier complete generic ChatGPT public-search output included `https://awsscd-mindanao.org/`. Re-running **all** results through the normal collector after parser repairs accepted that website in `supplemental-final/`. This assisted manifest is isolated from the final autonomous run and is not an eleventh event or extra autonomous discovery credit.

The website yields **November 28 with date-only precision**, advertised ticket tiers **PHP 199 / 289 / 349**, minimum price PHP 199, and **unknown** ticket availability and signup deadline. The 08:00 registration agenda block never becomes a deadline or invented event start. Its retained cloud-technology program supports Cloud & DevOps; a bare CTF agenda heading does not rename the conference or classify it as a cybersecurity competition. The standalone and Meetup records were kept in separate databases; cross-platform identity merging was not tested or implemented here.

This confirms the website parser and price rendering, but automatic discovery of that exact website remains dependent on search availability or another genuine directory link. Recurring-calendar recovery of the event does not remove that limitation.

## Verification and retained evidence

- Backend suite: **781 passed** after the final parser and listing-performance fixes.
- TypeScript/Vite build passed with isolated output in `data/benchmark-2026-11-23/build/`; deployment assets were not rebuilt.
- Browser suite: **29 passed** after the performance fix. Additional desktop/mobile proof is recorded in the handoff and `verification.json`. Initial loading timeouts are retained in the earlier logs; they prompted the measured topic-projection fix.
- Frozen November 22 results remain unchanged: original blind 0/8 and later known-reference 8/8 are historical scores for a different set.

Useful local files (ignored by Git, retained in this workspace):

| Path under `data/benchmark-2026-11-23/` | Purpose |
| --- | --- |
| `baseline-live/inputs.json`, `report.json`, `collector.log`, `captures/` | Baseline configuration and complete runtime evidence. |
| `final-live/inputs.json`, `report.json`, `collector.log`, `captures/`, `events.sqlite3` | Scored fresh run and saved normal database; finished 18:48:05 PHT. |
| `evaluation.json`, `api.json`, `evaluate.py` | Post-run scoring and API visibility. Scoring code is never a collector input. |
| `supplemental/manifest.json`, `search-*.txt` | Complete generic public-search output, with provider explicitly unspecified. |
| `supplemental-final/`, `supplemental-api.json` | Separate assisted website verification and normal API projection. |
| `backend-tests-final.log`, `frontend-build.log`, `browser-tests-final.log`, `browser-proof.json` | Final checks and browser evidence. |
| `api-profile.prof`, `api-performance.json` | Slow-listing diagnosis and unchanged-output check. |
| `protected-before.json`, `verification.json` | Protected DB/frozen-report checks and final status. |

No claim is made about exhaustive recall, available seats, a blind pass, unchanged future source access, or complete reproduction of every reference fact. Remaining gaps are exact AWS website discovery in the autonomous run, unknown Meetup signup controls, Conf42's unproven no-registration wording, bounded coverage, and search rate limits.
