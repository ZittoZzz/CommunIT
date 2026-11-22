# Luma Manila and publisher discovery — 22 November 2026 (Asia/Manila)

The calendar monitor works, but it did **not** find a current CTF. The RSS route independently discovered a genuine **past** competition and new publisher candidates. **No timely registration discovery was verified.** The unchanged ten-event benchmark now measures **3/10**, up from 2/10 through historical Packet Capture coverage. RAIJIN and Ivan Dizon's exact Facebook post were **not independently found** in these runs.

## Working recurring sources

| Source | Live result on each normal run | Accepted competitions / new publishers |
|---|---|---|
| [Luma Manila](https://luma.com/manila), public city iCal primary | Six event links; six detail pages inspected | Zero CTFs; zero publisher candidates |
| [KakaComputer CTF RSS](https://kakacomputer.com/tag/ctf/feed/) | One entry and its full article | One finished CTF; nine publisher candidates |
| [Cyber404 RSS](https://cyber404.net/blog/feed.xml) | Two entries and both full articles | Zero CTFs; two partnership publisher candidates |

Luma's [documented city iCal subscription](https://help.luma.com/p/ical-syncing) is available without credentials. Starting from the city page's public **Add iCal Subscription** control produced `https://api.luma.com/ics/get?entity=discover&id=discplace-XeAvnK62YmCW54R`. It returned six entries with a 12-hour advertised refresh interval. The public page also returned six links, despite advertising seven events. No supported public pagination was verified, so this is a bounded visible slice, not complete city coverage. The city calendar excludes online and private events. Both routes returned successfully during qualification; the two normal runs used iCal. No live Luma 403 or 429 occurred in these checks; regression fixtures cover those conditions.

The six inspected events were AMIHAN Festival, FL Demo Day, ClaudePH Community Launch, Build with AI coding workshops, U.S.-ASEAN Futures Fair, and Slow Sunday Brunch. None established an actual cybersecurity CTF. Every found URL and rejection reason is in [the normal-run audit](luma-verification.json); [route qualification](luma-live-research.json) records the separate page test. Ordinary event hosts do not become cybersecurity publisher candidates.

## Actual discovery path and resulting listing

[Recurring CTF feed](https://kakacomputer.com/tag/ctf/feed/) → [article discovered from its entry](https://kakacomputer.com/curiosity-to-cybersecurity-open-community-and-opportunity-through-packet-capturing/) → event `503205322bd9e4e23a9562f4` in `/api/events`.

The resulting listing is **Packet Capture CTF: Uniting Networking & Cybersecurity 2026**, **Finished · Registration closed**. It links to the KakaComputer article as a publisher recap, not an official organizer registration notice. The article explicitly describes the competition and completion; the source states that it closed with an awarding ceremony on October 26. It was published on November 1, 2026; the collector first saw it at `2026-11-21T17:42:36.873158+00:00`. This is historical backfill. No complete competition interval, registration window, eligibility or clock times were invented.

The original RSS recognition failed before ingestion: the feed title omitted CTF, and the existing Philippine-scope check did not understand the article's explicit local community relationship. The enabled monitor follows the feed-discovered article, reads its metadata title and selected article body, and accepts the evidenced competition/edition/Philippine relationship. A completion notice overrides stale registration language. The configured inputs contain only the recurring feed and general parsing options.

This is a **new accepted listing** compared with the frozen 2/10 checkpoint. Packet Capture had already appeared as a raw Tavily lead in earlier research, but those title-only results lacked enough evidence for ingestion. This RSS improvement supplies the missing full-source evidence; it does not claim the event was never mentioned previously. The final runs also returned a Packet Capture Facebook lead in raw search results. Its recorded rejection reason was “Philippine organizer or venue not established by title/source”; the collector does not automatically turn newly harvested profile candidates into verified search-organizer rules. That returned URL is retained in the raw audit, but its identity as the original announcement is unverified.

The article also yielded nine explicit relationships. Cyber404's two partnership articles yielded two more candidates without creating events. All 11 candidates are new to this initially empty database; 9 have stable linked identities, and 2 have evidence-scoped identities only. No candidate was automatically enabled as an unverified monitor.

| Candidate | Role supported by discovered article | Identity |
|---|---|---|
| A1SBERG | challenge-partner | [https://www.facebook.com/a1sberg](https://www.facebook.com/a1sberg) |
| Appkademiya | sponsor | No linked identity; evidence-scoped |
| Cisco NetConnect PUP | contributor | [https://www.facebook.com/cisconetconnectpup](https://www.facebook.com/cisconetconnectpup) |
| CyberPH | contributor | [https://www.facebook.com/learncyberph](https://www.facebook.com/learncyberph) |
| CYBERSOCPH | community-partner | [https://www.facebook.com/cybersocph](https://www.facebook.com/cybersocph) |
| Huawei Cloud Developer Group Philippines | contributor | [https://www.facebook.com/groups/1923181361612194](https://www.facebook.com/groups/1923181361612194) |
| ICPEP.SE PUP | contributor | [https://www.facebook.com/icpepse.pupmanila](https://www.facebook.com/icpepse.pupmanila) |
| MQ CyberSec (Australia) | contributor | [https://www.linkedin.com/company/mqcybersec/](https://www.linkedin.com/company/mqcybersec/) |
| Philippine Data Guardians (PDG) | community-partner | No linked identity; evidence-scoped |
| SYNX | challenge-partner | [https://www.facebook.com/synx.network](https://www.facebook.com/synx.network) |
| WorkFlow PH | contributor | [https://www.facebook.com/workflowph](https://www.facebook.com/workflowph) |

“Made possible by” is retained as contributor evidence; it does not establish organizer or host status. The foreign contributor is retained as a relationship lead, not asserted to be a Philippine organization. The recap's Philippine connection comes from its explicit local community/venue relationship. Public profile links identify candidates, not original Facebook event posts. The known Luma host names were never inserted into extraction rules.

Candidate storage deduplicates stable public URLs/account IDs and preserves each role and source relationship. Unlinked names are scoped to the establishing article; matching display names cannot merge unrelated organizations. One-time qualification can add a recurring permitted source with `publisher_identity_urls` or `publisher_account_ids` to the source index. A successful source-health check then links the candidate to that monitor. Facebook profiles without a verified recurring reader remain candidates. See [architecture](architecture.md#discovered-publisher-candidates) for the workflow.

## Evaluation references remain separate

The historical Packet Capture Luma page was opened separately from the frozen research **after** calendar discovery. It confirms public host accounts for CyberPH and WorkFlow PH, and names Appkademiya among sponsors. It was absent from the upcoming city feed. That direct opening is **not automatic discovery**, and its host IDs were not imported into the experiment's database. Its kickoff schedule is not a confirmed full competition interval. The new conservative Luma parser also rejects that page's CTF-topic/workshop wording without a sufficiently explicit competition cue; the RSS recap is the actual qualifying evidence. An old raw `open` field there does not establish that registration was possible now.

VEKTR's LinkedIn announcement remains a separate evaluation reference, not a seed or an independently discovered current announcement. RAIJIN and Ivan Dizon's original post likewise remain evaluation-only. Neither supplied Facebook URL form, numeric post ID, nor a matching decoded embed target appeared in the retained output of these runs. Other opaque IDs were not assumed equivalent. No new source returned a matching RAIJIN announcement; this is a source-coverage miss, not a demonstrated parser rejection. Search availability limits are below. These results do not prove that a search provider never indexed the post.

The original benchmark research and earlier 2/10 measurement files retain their hashes. [The new measurement](luma-benchmark-results.json) uses the same ten selections: LearnPossible, ROOTCON 20, and Packet Capture now match accepted listings; seven remain unmatched. Original Facebook identities are unknown for the ten benchmark selections. RAIJIN is measured separately. All three matches are historical coverage, with **zero verified timely discoveries**.

## Two normal runs and source health

Runs began at `2026-11-21T17:41:18.076117+00:00` and `2026-11-21T17:43:06.742771+00:00` against the same initially empty temporary database. Both used the default configuration and normal daily CLI; no source selection, event arguments, cache import, or evaluation data were supplied.

| Measurement | Run 1 | Run 2 |
|---|---:|---:|
| Events | 11 | 11 |
| Announcements | 13 | 13 |
| Publisher candidates | 11 | 11 |
| Verified timely observations | 0 | 0 |

Run 2 added 0 announcements, 0 publisher candidates, and 0 publisher relationships. Existing event, announcement, candidate and relationship first-seen timestamps stayed unchanged. Logical duplicate checks for event identity, per-event announcement URL, stable publisher URL and publisher relationship returned zero duplicate groups. Revisions and IDs were compared in [verification JSON](luma-verification.json). Qualifiers remain separate from main events.

| Source | Status run 1 / 2 | Discovered run 1 / 2 | Accepted run 1 / 2 | New announcements run 1 / 2 |
|---|---|---:|---:|---:|
| rootcon-bluesky | ok / ok | 146 / 146 | 3 / 3 | 3 / 0 |
| hackthenorth | ok / ok | 11 / 11 | 0 / 0 | 0 / 0 |
| up-acm | ok / ok | 1 / 1 | 0 / 0 | 0 / 0 |
| pup-announcements | ok / ok | 10 / 10 | 0 / 0 | 0 / 0 |
| pup-news | ok / ok | 10 / 10 | 0 / 0 | 0 / 0 |
| ncert | blocked / blocked | 0 / 0 | 0 / 0 | 0 / 0 |
| dict | blocked / blocked | 0 / 0 | 0 / 0 | 0 / 0 |
| rootcon-website | policy_restricted / policy_restricted | 0 / 0 | 0 / 0 | 0 / 0 |
| ctftime | ok / ok | 179 / 179 | 0 / 0 | 0 / 0 |
| up-manila | ok / ok | 1 / 1 | 1 / 1 | 1 / 0 |
| htb-meetup-ph | ok / ok | 1 / 1 | 1 / 1 | 1 / 0 |
| aws-mindanao | ok / ok | 1 / 1 | 1 / 1 | 1 / 0 |
| feu-eventually | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |
| crest-asia | ok / ok | 3 / 3 | 1 / 1 | 1 / 0 |
| um-sdc | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |
| owasp-cebu | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |
| pia | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |
| vektr-community | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |
| luma-manila | ok / ok | 6 / 6 | 0 / 0 | 0 / 0 |
| kakacomputer-ctf | ok / ok | 1 / 1 | 1 / 1 | 1 / 0 |
| cyber404-news | ok / ok | 2 / 2 | 0 / 0 | 0 / 0 |
| tavily-keyless | ok / ok | 60 / 60 | 6 / 6 | 5 / 0 |
| facebook-search | disabled / disabled | 0 / 0 | 0 / 0 | 0 / 0 |

NCERT and DICT access failures did not remove listings or stop other sources. ROOTCON's restricted website was not fetched. Disabled candidates and Brave made no requests. Source last-success times are retained on unsuccessful checks; each successful check advances its own health timestamp.

Tavily remains free and keyless, using unchanged generic queries. The audit below distinguishes successful responses from HTTP 429 errors and skipped queries. A provider error with zero returned results is **not a successful zero-result search**. `Retry-After` is retained in each attempt audit and persisted in source health; subsequent runs skip requests until the provider may be retried. Both full source reports retain their actual attempt times, returned URLs, rejection reasons, and next-retry times.

| Run | Query | Status | Returned results | Provider message |
|---|---|---|---:|---|
| 1 | `site:facebook.com Philippines cybersecurity CTF competition registration` | ok | 20 | — |
| 1 | `Philippines capture the flag CTF competition registration` | ok | 20 | — |
| 1 | `Philippines cybersecurity community CTF events calendar registration` | ok | 20 | — |
| 2 | `site:facebook.com Philippines cybersecurity CTF competition registration` | ok | 20 | — |
| 2 | `Philippines capture the flag CTF competition registration` | ok | 20 | — |
| 2 | `Philippines cybersecurity community CTF events calendar registration` | ok | 20 | — |

Two earlier verification attempts encountered live Tavily 429 responses (134 and 111 seconds), while the other monitors continued; those audits remain separately retained in the verification JSON. The initial completion evidence excerpt was then corrected to preserve the actual source assertion, and the final two runs above were repeated on a new empty database. No earlier events or cached responses were imported.

The backend suite passed **284 tests**. Flask's temporary-database `/`, `/api/events`, `/api/sources`, and `/api/health` all returned HTTP 200; the new recap was served as finished/closed. TypeScript/Vite built successfully into `/tmp/ctfinder-luma-frontend`. Only compatibility labels for approval/waitlist/source-health states changed in frontend source; no layout changes or deployment were made. Production database counts stayed at 2 events, 3 announcements and 5 runs, and services were not restarted or modified.

## Reproduce and next scheduled run

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
pilot_dir="$(mktemp -d /tmp/ctfinder-luma-XXXXXX)"
.venv/bin/python -m backend.collect \
  --database "$pilot_dir/events.sqlite3" \
  --report "$pilot_dir/run-1.json"
# Honor any reported Retry-After before retrying that provider.
# The collector also persists and enforces next_retry_at.
.venv/bin/python -m backend.collect \
  --database "$pilot_dir/events.sqlite3" \
  --report "$pilot_dir/run-2.json"
.venv/bin/python -m pytest -q
```

To view only this temporary experiment, run `CTF_DATABASE="$pilot_dir/events.sqlite3" PORT=5001 .venv/bin/python -m backend.app` and open `http://127.0.0.1:5001`. This does not start or restart the production web service.

The existing daily timer was observed scheduled for **22 November 2026, 06:00 Asia/Manila**. It reloads the current index and will use the new Luma Manila, KakaComputer and Cyber404 monitors alongside the five previously enabled index monitors, legacy sources, and secondary free Tavily queries. The index has 13 records: eight enabled and five disabled candidates. The eleven dynamically discovered publisher candidates are a separate backend collection, pending recurring-source qualification; their Facebook accounts are not automatically scraped.

This is a useful expansion of automatic historical discovery and publisher research at ₱0 API fees. It is **not yet a dependable upcoming-CTF alert**, especially for personal-profile Facebook announcements and online events outside public city calendars. The smallest evidence-supported next step is to qualify recurring public feeds/calendars for the discovered Philippine communities, then measure real future first-seen timestamps against confirmed registration windows. No per-event submissions are needed.
