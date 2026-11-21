# Free community CTF discovery investigation

**A — RAIJIN independently discovered: no verified discovery.** Neither successful normal run returned an identifiable matching URL/title or produced an event listing. No independently investigated recurring source produced it.

**B — Ivan Dizon’s exact Facebook post independently discovered: no verified discovery.** Both supplied URL forms, including decoded Facebook post-embed hrefs, were checked. No retained match was found; old unretained snippets remain untraceable.

**C — Benchmark: 1 of 10 became a listing; 0 timely discoveries verified.** The one listing was ROOTCON 20, found after completion. A Hexcore recap was retrieved but rejected; Packet Capture had ambiguous search-only leads. Original Facebook identities are unknown for all ten, so zero verified originals is not ten proven Facebook misses. RAIJIN is an additional supplied acceptance case, not part of the ten independent events.

Investigated on 21–22 November 2026, Asia/Manila. Production database and services were left alone. All collector API searches used Tavily's free keyless mode; no paid fallback, Facebook login, cookies, or manual event submissions were used.

## Evaluation rules

The independently selected benchmark has ten documented Philippine competitions across multiple organizers. It was frozen without consulting collector output. RAIJIN is a separate supplied acceptance case, excluded from that denominator. [Research evidence](community-benchmark-research.json) records dates, sources, registration evidence, and uncertainty. None of the ten has an independently established original personal-profile Facebook post; this benchmark cannot establish coverage across several such organizers.

An event counts as a collected listing only when a normal run creates its event record. A returned but rejected search result is separately recorded as a candidate. A publication date is never substituted for collector first-seen. Timely discovery requires an actual first-seen timestamp supported by evidence that registration was still possible then. Current retrieval of an old invitation or winner recap is historical coverage only.

The supplied title, author, two Facebook URL forms, date clues, and registration information were used only for evaluation. They are absent from production queries, seeds, source configuration, and regression fixtures.

## Earlier evidence audit

Checked `docs/tavily-verification.json`, `docs/tavily-search-results.md`, retained reports under `docs/`, `data/`, `/tmp/ctfinder*`, and six retained SQLite databases opened read-only. Comparison included both supplied forms and up to six passes of HTML-entity and percent decoding, including `plugins/post.php?href=...` wrappers.

Neither supplied post URL nor a matching Facebook embed appeared in retained result URLs/titles. The target name and numeric ID occurred only in comparison metadata and conclusions. There was no target-specific accept/reject decision to reverse. Other opaque Facebook IDs remain unknown.

The earlier successful runs started at 15:40:51 and 15:41:38 UTC on 21 November. Each returned 20 Facebook-query results and 20 unrestricted results. Each accepted the same four HackForGov announcements. Rejections were: 29 without established Philippine scope, five without an identifiable CTF in the title, and two without an unambiguous edition.

**Evidence limit:** these artifacts are unfiltered URL/title audits, not full raw response archives. If an ordinary permalink or embed existed only in an unretained snippet, its presence and handling are now untraceable. The earlier conclusion must be read as “no matching retained URL/title,” not proof that every earlier response lacked the post. The 15:25 diagnostic contains rate-limit errors, not successful zero-result searches.

## Small live experiments

[Complete query results and pre-change filter decisions](community-discovery-experiment.json) record these reusable queries:

1. `Philippines cybersecurity community CTF events calendar registration`
2. `Philippines cybersecurity student club CTF registration`
3. `Philippines CTF community registration announcement`

All three succeeded without credentials. The third experiment also inspected URLs present in returned snippets without promoting snippet text to event facts. It found no matching target link or post embed. Research tools also searched generic Philippine club, calendar, and registration terms; those searches informed source investigation but are not counted as normal collector discovery.

## Reusable change supported by live evidence

The first query returned [CREST's ROOTCON sponsor announcement](https://www.crest-approved.org/event/rootcon-20-philippines-2026). A permitted public-page read confirmed an actual ROOTCON CTF sponsorship. Its current filter decision was “Philippine organizer or venue not established by title/source”: the adapter's verified publisher relationships only matched Facebook accounts.

The collector now supports exact `publisher_hosts` for verified organizer/series relationships. CREST's website hosts were added to the existing ROOTCON mapping, with the existing ROOTCON series guard. The generic calendar query was added to the default source configuration. No individual event URL was seeded. A foreign competition promoted by the same partner remains excluded, as do lookalike domains. The resulting announcement remains search-only, not verified full-post evidence. This is partner-announcement coverage, not proof of personal-profile discovery.

No date parser or UI changes were made. The new query and publisher relationship should catch future indexed ROOTCON CTF partner announcements. They do not guarantee coverage of other community organizers.

This repair added a previously rejected sponsor announcement to ROOTCON's existing listing. It did not increase the number of benchmark events covered: ROOTCON was already discoverable through Bluesky. The additional regional HackForGov listing in verification came from changed search results, not from the partner-host rule.

## Other investigated routes and stopping points

| Starting source | Actual next step | Observation / stopping point |
| --- | --- | --- |
| Generic calendar query | [Hexcore media archive](https://hexcore-labs.com/media) → [Philippine tournament article](https://hexcore-labs.com/post/hexcore-labs-philippines-launches-with-nationwide-cybersecurity-and-ai-competition) | Readable archive and article. This is an October 2025 winner recap. Search title lacks an identifiable CTF; current adapter withholds it. The article contains an ordinary Facebook photo link, not the supplied post. |
| Generic club research | [JPCS–OLSHCo](https://jpcsolshco.org/) → public `/api/news` and `/api/events` used by its own page | Robots allows access. Three news articles and two events were readable. Central Luzon CTF appears in a June 2026 winner recap; no specific Facebook post/embed or registration link. Generic publisher/profile links do not count. No recurring JSON adapter was added solely to import recaps. |
| Generic student-calendar research | [FEU Eventually discovery calendar](https://paraverse.feutech.edu.ph/eventually/discover/) → [CyberXplore event](https://paraverse.feutech.edu.ph/eventually/event/cyberxplore-xplore-xecute-xcel-1761732412) | Readable calendar/event; event is cancelled. Only a generic Facebook footer, not a post. Some organizer/tag listing pages require client loading. No target found. |
| Independently documented community event | [CyberPH Luma profile](https://luma.com/user/usr-Xf0H4hjDiw6f0tp), [WorkFlow PH profile](https://luma.com/user/usr-eL9qAMoNyJQl2iV) | Public profiles readable but returned no event hyperlinks in server-rendered content. The known historical event page is not a reusable discovery seed. No login or undocumented private API was attempted. |
| Generic university research | [UP Manila announcements feed](https://www.upm.edu.ph/feed/?post_type=cpt_announcements) → new announcement pages | Readable RSS with ten recent entries, none a CTF. Its independently found [LearnPossible invitation](https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/) is an actual advance announcement from September 2025 and links an organizer PDF. It has aged out of the current feed. This proves a useful publisher class, not present discovery of that event. |
| Existing [HackTheNorth](https://hackthenorth.ph/) source | TCON conference registration site | Recurring CTF description on the organizer homepage, but latest registration page does not identify a particular CTF. Conference dates cannot become CTF dates. |
| Generic community research | [Recon Village PH](https://reconvillageph.org/) → contests page | Generic CTF format and duration, schedule TBA, only publisher/profile links. No identifiable edition or supplied post. |

The inspected recurring pages did not return the target. The sponsor result did reach the collector and fail its scope check, which is the stage fixed. Unretained historical snippet content remains the specific untraceable part of the earlier evidence.

## Reproduce

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
CTF_COMMUNITY_CHECK="$(mktemp -d)"
.venv/bin/python -m backend.collect --database "$CTF_COMMUNITY_CHECK/events.sqlite3" --report "$CTF_COMMUNITY_CHECK/run-1.json"
.venv/bin/python -m backend.collect --database "$CTF_COMMUNITY_CHECK/events.sqlite3" --report "$CTF_COMMUNITY_CHECK/run-2.json"
.venv/bin/python -m pytest -q
```

These are the same collector and default source configuration used by the daily service. Inspect every source/query status: successful job exit alone does not prove every source succeeded. Respect `Retry-After`; there is no paid fallback.

## Normal-run verification

[Complete reports, result URLs/titles, filter decisions, listing records, and comparisons](community-verification.json). Both runs used a fresh temporary database and the default configuration, with no target-specific arguments or prepopulated cache.

| Query | Run 1 | Run 2 |
| --- | --- | --- |
| `site:facebook.com Philippines cybersecurity CTF competition registration` | ok, 20 results | ok, 20 results |
| `Philippines capture the flag CTF competition registration` | ok, 17 results | ok, 19 results |
| `Philippines cybersecurity community CTF events calendar registration` | ok, 20 results | ok, 20 results |

| Run | Start (UTC) | Events | Announcements | New announcements |
| --- | --- | ---: | ---: | ---: |
| 1 | 2026-11-21T16:05:32.190229+00:00 | 7 | 9 | 9 |
| 2 | 2026-11-21T16:06:12.194886+00:00 | 7 | 9 | 0 |

Each run accepted six unique Tavily announcements: five regional HackForGov leads plus CREST’s ROOTCON sponsor announcement. ROOTCON’s three Bluesky posts produced the main event and a separate qualifier; the new sponsor announcement attached to the main event rather than duplicating it. The five HackForGov regions were MIMAROPA, Bicol, CALABARZON, Central Visayas, and Negros Island Region. The additional Negros result reflects changed live search ranking, not an event-specific seed.

**No duplicate events or announcements:** IDs, URLs, and first-seen timestamps remained stable. Saved snapshots were not byte-identical: one Central Visayas announcement gained a second discovery query and its revision counter advanced from 1 to 2. Its event facts were unchanged. The reports preserve the varying search results; the second run added zero announcements.

Working on both runs: Tavily (all three queries), ROOTCON Bluesky, HackTheNorth, UP ACM, PUP announcements, PUP news, and CTFtime. DICT/CERT-PH remained HTTP 403 failures during robots verification; ROOTCON website remained policy-restricted; Brave still required credentials/storage entitlement. These failures did not stop the working sources or delete listings.

**Regression tests:** 125 backend tests passed, including eight new partner-publisher cases. No parser/UI changes required browser testing in this iteration. Production remained at 2 events / 3 announcements and 5 historical runs. Services and timer were not changed.

Temporary verification database: `/tmp/ctfinder-community-live-urfa2bwv/events.sqlite3`.

## Benchmark measurements

[Per-event evidence and measurements](community-benchmark-results.json) retain source URLs, registration evidence, first-seen values, raw candidates and rejection stages. Selection and source evidence are separately preserved in [the frozen research benchmark](community-benchmark-research.json). One newsletter-based row has weaker publisher provenance, explicitly marked. This is a small convenience benchmark, not a representative coverage estimate.

| Competition | Normal listing | Source actually found / failure stage | Original Facebook | Timely registration discovery |
| --- | --- | --- | --- | --- |
| LearnPossible: Hexcore Labs PH University Challenge — CTF tournament 2025 | No | Raw Hexcore recap URL returned; title recognition rejected | Unknown original | Not verified; historical recap |
| ROOTCON 20 Capture The Flag 2026 | Yes | Bluesky organizer announcements/completion + CREST sponsor announcement | Unknown original | No: first seen after September completion |
| Packet Capture: Beneath the Network 2026 | No | Possible Facebook registration leads; scope/identity not established | Unknown original | Not verified; no accepted listing |
| JISSA Capture The Flag 2026: Signal Lost | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| JISSA-APC and Resecurity CTF Showdown 2026 | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| AdU CTF: Hackademic Showdown 2025 | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| HackQuest Iligan 2025: Capture the Flag | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| CyberCONNECT: Capture the Flag Training and Challenge 2025 | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| Trend University Capture the Flag 2025 — Preliminary Round | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |
| Central Luzon Capture The Flag 2026 | No | No identifiable matching result in normal runs | Unknown original | Not verified; not discovered |

ROOTCON's fresh-database first-seen timestamp was `2026-11-21T16:05:32.190229+00:00` (22 November, Asia/Manila), after the documented September competition. Even the earliest retained production observation on 21 November was too late. Its sponsor announcement did not verify a current registration opportunity.

The remaining seven benchmark events beyond ROOTCON, Hexcore, and Packet Capture were documented by independent research but were not identifiable in normal collector results. Their missed stage is current source coverage/search retrieval, not a demonstrated parser rejection. Specific original Facebook post identity is unknown for them; unrelated opaque IDs cannot establish a match.

## Recommendation

The free collector is **not ready to be relied on as an upcoming-event registration alert**. It is a useful supplementary discovery directory, but this experiment verifies historical coverage of only one benchmark event as a listing and no timely registrations. The personal-profile acceptance case remains missed. The benchmark’s lack of independently documented personal-profile originals limits broader conclusions about that source class.

The next useful work is to validate more recurring pre-event university/community feeds and registration pages, preserving daily first-seen observations so timeliness can be measured prospectively. UP Manila shows that pre-event partner invitations exist, but its current short feed cannot recover an older invitation. Expanding search titles alone does not establish registration availability, and importing recaps or manually adding the supplied post would not solve the requested problem.
