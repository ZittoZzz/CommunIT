# Publisher monitoring and registration opportunities — 22 November 2026

**Working publisher sources:** CyberPH’s public Luma subscription is enabled and independently returned its historical CTF announcement. Cisco NetConnect’s public subscription also works and is enabled as an exploratory community monitor; it has not demonstrated a CTF invitation. WorkFlow PH has no qualified CTF announcement route yet.

**Competitions first observed while registration was open: 0.** There were also 0 verified current-open control observations and 0 deadline-backed timely discoveries. No new upcoming CTF came from the publisher calendars. Historical coverage does not establish registration opportunity.

**RAIJIN competition independently discovered: No (not observed). Exact supplied Facebook post independently discovered: No (not observed).** The frozen ten-event selection still measures 3/10, with zero verified timely discoveries. All prior benchmark files were preserved and hash-checked.

## Publisher qualification paths

The starting identities were saved by the earlier normal collector from [KakaComputer’s CTF feed](https://kakacomputer.com/tag/ctf/feed/) and its discovered recap: [CyberPH](https://www.facebook.com/learncyberph), [WorkFlow PH](https://www.facebook.com/workflowph), and [Cisco NetConnect PUP](https://www.facebook.com/cisconetconnectpup). Facebook profile HTML was not requested. A profile link alone was never treated as a recurring reader.

**CyberPH:** publisher-only query `"CyberPH" Luma events calendar` → [public non-CTF webinar](https://luma.com/79gspr7h) → public calendar/account identifiers in that page → [documented calendar iCal mechanism](https://help.luma.com/p/ical-syncing) → [recurring subscription](https://api.luma.com/ics/get?entity=calendar&id=cal-ZW4YOEwv4lmL66C). The public UI code establishes `entity=calendar`; the calendar ID was read from the independently found webinar, not guessed from a private API. This is search-assisted one-time publisher qualification. The subscription itself is the only runtime starting URL.

That subscription returned **three links** on both normal runs: [AI defenses workshop](https://luma.com/mz5bi1ln), [online OT-security webinar](https://luma.com/79gspr7h), and [historical CTF activity](https://luma.com/akv0l0o1). All descriptions were readable. The first two lacked competition evidence and were dropped; the third was accepted. The webinar body explicitly identifies Microsoft Teams even though its structured location type is unknown. Thus this publisher feed includes online events; it does not prove comprehensive coverage or an online CTF discovery. No publication timestamp establishes when the CTF landing page was first announced.

The saved Facebook and new Luma account have no verified reciprocal identity link. Their relationship to the same historical competition helps research qualification, but the backend keeps their account identities separate instead of merging display names. The Luma profile itself lists three hosted events but returns zero event links; the subscription is the working route. See [CyberPH research](cyberph-source-research.json).

**WorkFlow PH:** publisher-name query `"WorkFlow PH" community calendar events` → [organization website](https://workflowph.org/) → [showcase archive](https://workflowph.org/showcase). The website footer links the exact saved Facebook account, confirming ownership. The archive is readable and has **23 detail links: eight historical records and fifteen TBC stubs**, including online activities. It did not expose a sufficiently documented CTF invitation or registration window. It is not enabled. The known competition’s direct link → WorkFlow’s [Luma host profile](https://luma.com/user/usr-eL9qAMoNyJQl2iV) was **research-assisted**: the profile advertises six hosted events but returns no event links/calendar subscription. A separately searched non-CTF cohosted event belongs to a different calendar owner and was rejected as WorkFlow’s source. See [WorkFlow research](workflow-source-research.json).

**Cisco NetConnect:** independent saved candidate → publisher-only search → [non-CTF launch listing](https://luma.com/2ntq5ce1) → owning public calendar/account → [subscription](https://api.luma.com/ics/get?entity=calendar&id=cal-eaknIQWG6bEHiP7). It returned **nine readable event pages: four online (`location_type=meet`), five in person, all historical, zero CTFs**. This is a working exploratory publisher calendar, not verified advance CTF coverage. Luma’s `meet` value is now treated as online with regression coverage. A separate [university academic calendar](https://oneccisko.site/calendar.ics) returned 101 academic/exam entries and was not added as a CTF source. SYNX had no established owned reader; CYBERSOCPH’s website was a login shell. Those remain research candidates.

Each calendar uses the existing Luma adapter, has a 60-detail cap, rechecks retained announcements, and disables city-page fallback for its ICS URL. Only three/nine links were available; no complete-history claim or undocumented pagination. Both feeds advertise a 12-hour refresh interval. Online CTFs still need Philippine venue/organizer evidence in their own description: a calendar name or timezone alone is insufficient. This conservative scope rule may miss genuine online events that omit that evidence.

## Actual normal discovery and listing

[CyberPH recurring subscription](https://api.luma.com/ics/get?entity=calendar&id=cal-ZW4YOEwv4lmL66C) → [announcement automatically returned by the feed](https://luma.com/akv0l0o1) → event **`503205322bd9e4e23a9562f4`**, displayed as **HCDG PH x Packet Capture: Beneath the Network · CTF 2026**.

The event’s first-seen timestamp in this fresh database is **2026-11-22T02:06:06+08:00 (Asia/Manila)**; the new Luma announcement was first seen **2026-11-22T02:06:14+08:00**. These are observation times, not publication dates. The final listing is **finished / registration closed**, retaining both the organizer landing page and [completion recap](https://kakacomputer.com/curiosity-to-cybersecurity-open-community-and-opportunity-through-packet-capturing/). The recap establishes completion; the Luma kickoff slot does not establish the complete competition interval. The old raw open/approval flag is not evidence that someone could still enter. Registration deadline, eligibility and full competition times remain unconfirmed.

Compared with the preceding verified baseline, this iteration adds **1 announcement URL and 0 distinct competitions**. The new information is a recurring organizer route, official host/relationship evidence, and an additional supporting announcement for an already known historical competition. It is not a new benchmark hit. The run retains 22 publisher identity records, up from 11; names without linked identities stay scoped to their establishing announcement. Same-name records are not asserted to be distinct organizations or merged without evidence.

## Recognition and duplicate protection

The historical page was readable but the old recognition gate rejected it because it declared a CTF activity and participant challenges without using a competition/contest noun. The new rule accepts that combination with cybersecurity evidence, rejects teaching-only workshops/tutorials/labs, and permits an explicitly separate competition track alongside teaching. Its body evidence is retained even if the title omits CTF. Such recognition alone never borrows a parent event’s ticket or complete schedule. [Exact evaluation wording and unrelated synthetic tests](publisher-luma-recognition.json) are recorded separately; direct opening and fixtures do not establish automatic discovery. The feed path above supplies that evidence.

The recap and calendar use different headlines. They join only with an explicitly named complete program subject, matching kickoff date and edition/stage, and compatible geography. Exact venue corroboration was available here. Conflicting qualifiers/finals/regions/years and ambiguous multiple matches stay separate. Both links and first-seen are retained. This avoids a second listing without an event-specific alias.

A new observation metric can retain a live open registration control with a confirmed future/live competition time even when no deadline is published. The deadline remains null. Static “register now” prose, stale past-event controls, approval requirements and waitlists do not qualify as verified open entry. A later closure preserves an earlier supported observation; a later opening does not backdate first-seen. The original deadline-backed benchmark measure is unchanged.

## Two normal runs

Both used the default configuration and normal daily CLI, starting from an empty temporary database at `/tmp/ctfinder-publisher-verified-up_1_buq`. No event seed, source filter, evaluation data or imported result cache was supplied. The small `meet` format correction was made after run 1; it does not change any accepted event in these runs, and run 2 exercised the final code. No current Cisco entry qualifies as a CTF.

| Measurement | Run 1 | Run 2 |
|---|---:|---:|
| Events | 11 | 11 |
| Announcements | 14 | 14 |
| Deadline-backed timely discoveries | 0 | 0 |
| Verified live-open observations | 0 | 0 |
| First seen while live-open | 0 | 0 |
| Publisher identities | 22 | 22 |

Run 2 created zero events, announcements, publisher identities or relationships. All shared first-seen timestamps stayed stable. Logical duplicate checks returned zero groups; evidence revisions were compared as well. Source health distinguishes blocked requests, cooldown skips, disabled monitors and successful empty checks.

| Source | Run 1 / 2 status | Discovered 1 / 2 | Accepted 1 / 2 |
|---|---|---:|---:|
| rootcon-bluesky | ok / ok | 146 / 146 | 3 / 3 |
| hackthenorth | ok / ok | 11 / 11 | 0 / 0 |
| up-acm | ok / ok | 1 / 1 | 0 / 0 |
| pup-announcements | ok / ok | 10 / 10 | 0 / 0 |
| pup-news | ok / ok | 10 / 10 | 0 / 0 |
| ncert | blocked / blocked | 0 / 0 | 0 / 0 |
| dict | blocked / blocked | 0 / 0 | 0 / 0 |
| rootcon-website | policy_restricted / policy_restricted | 0 / 0 | 0 / 0 |
| ctftime | ok / ok | 178 / 178 | 0 / 0 |
| up-manila | ok / ok | 1 / 1 | 1 / 1 |
| htb-meetup-ph | ok / ok | 1 / 1 | 1 / 1 |
| aws-mindanao | ok / ok | 1 / 1 | 1 / 1 |
| feu-eventually | disabled / disabled | 0 / 0 | 0 / 0 |
| crest-asia | ok / ok | 3 / 3 | 1 / 1 |
| um-sdc | disabled / disabled | 0 / 0 | 0 / 0 |
| owasp-cebu | disabled / disabled | 0 / 0 | 0 / 0 |
| pia | disabled / disabled | 0 / 0 | 0 / 0 |
| vektr-community | disabled / disabled | 0 / 0 | 0 / 0 |
| luma-manila | ok / ok | 6 / 6 | 0 / 0 |
| kakacomputer-ctf | ok / ok | 1 / 1 | 1 / 1 |
| cyber404-news | ok / ok | 2 / 2 | 0 / 0 |
| cyberph-luma-calendar | ok / ok | 3 / 3 | 1 / 1 |
| cisco-netconnect-luma-calendar | ok / ok | 9 / 9 | 0 / 0 |
| tavily-keyless | partial / rate_limited | 40 / 0 | 5 / 0 |
| facebook-search | disabled / disabled | 0 / 0 | 0 / 0 |

DICT and NCERT remained blocked. ROOTCON’s restricted website and disabled monitors made no extraction requests. CyberPH and Cisco succeeded on both runs. Luma Manila returned six ordinary events and no CTF. Previous listings survived failures.

Tavily’s first two generic queries returned 20 results each. Its third query returned HTTP 429 with `Retry-After: 773`; the next run honored the persisted cooldown and made no Tavily request. This is not a successful zero-result check. These unchanged production queries were:

- `site:facebook.com Philippines cybersecurity CTF competition registration` — ok; 20 retained results.
- `Philippines capture the flag CTF competition registration` — ok; 20 retained results.
- `Philippines cybersecurity community CTF events calendar registration` — error; 0 retained results.

The raw returned URLs, decisions and both supplied Facebook URL forms (including decoded embed targets) were checked only during evaluation. No matching competition or exact post appeared. The last successful discovery steps were the two broad search responses and readable recurring sources; none supplied a matching announcement to recognize. The third query and second run’s search coverage remain unavailable due to the cooldown. Other opaque Facebook IDs were not equated with the supplied post. This does not prove that the post was never indexed. No acceptance-case identifiers occur in runtime inputs or tests.

## Listings, first-seen and registration evidence

All rows below are newly stored in the fresh experimental database; they are not all new coverage. The JSON audit contains each recurring source → announcement → event path, raw returned links, field evidence and registration reasons. Table links point to one supporting announcement per listing; additional links remain in the API.

| Displayed event | First seen, Asia/Manila | State / registration | Supporting announcement / evidence |
|---|---|---|---|
| HackForGov edition-5 · MIMAROPA | 2026-11-22T02:06:26+08:00 | upcoming / unknown | [Tavily · Free Philippine CTF discovery](https://www.facebook.com/dictr4b/posts/-%F0%9D%90%87%F0%9D%90%80%F0%9D%90%82%F0%9D%90%8A%F0%9D%90%85%F0%9D%90%8E%F0%9D%90%91%F0%9D%90%86%F0%9D%90%8E%F0%9D%90%95-%F0%9D%90%8C%F0%9D%90%88%F0%9D%90%8C%F0%9D%90%80%F0%9D%90%91%F0%9D%90%8E%F0%9D%90%8F%F0%9D%90%80-%F0%9D%9F%90%F0%9D%9F%8E%F0%9D%9F%90%F0%9D%9F%94-%F0%9D%90%91%F0%9D%90%84%F0%9D%90%86%F0%9D%90%88%F0%9D%90%92%F0%9D%90%93%F0%9D%90%91%F0%9D%90%80%F0%9D%90%93%F0%9D%90%88%F0%9D%90%8E%F0%9D%90%8D-%F0%9D%90%8D%F0%9D%90%8E%F0%9D%90%96-%F0%9D%90%8E%F0%9D%90%8F%F0%9D%90%84%F0%9D%90%8D-%F0%9D%90%80%F0%9D%90%9B%F0%9D%90%A8%F0%9D%90%AE%F0%9D%90%AD-%F0%9D%90%AD%F0%9D%90%A1%F0%9D%90%9E-%F0%9D%90%82%F0%9D%90%A8%F0%9D%90%A6%F0%9D%90%A9%F0%9D%90%9E%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7the-hackfor/1089592793724382); Search result only; full post and current registration unavailable |
| HackForGov 2026 · Region V — Bicol · Qualifier | 2026-11-22T02:06:26+08:00 | upcoming / unknown | [Tavily · Free Philippine CTF discovery](https://www.facebook.com/DICTRegionVBicol/posts/%F0%9D%90%82%F0%9D%90%9A%F0%9D%90%A5%F0%9D%90%A5%F0%9D%90%A2%F0%9D%90%A7%F0%9D%90%A0-%F0%9D%90%81%F0%9D%90%A2%F0%9D%90%9C%F0%9D%90%A8%F0%9D%90%A5%F0%9D%90%AC-%F0%9D%90%A7%F0%9D%90%9E%F0%9D%90%B1%F0%9D%90%AD-%F0%9D%90%A0%F0%9D%90%9E%F0%9D%90%A7%F0%9D%90%9E%F0%9D%90%AB%F0%9D%90%9A%F0%9D%90%AD%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7-%F0%9D%90%A8%F0%9D%90%9F-%F0%9D%90%9C%F0%9D%90%B2%F0%9D%90%9B%F0%9D%90%9E%F0%9D%90%AB%F0%9D%90%AC%F0%9D%90%9E%F0%9D%90%9C%F0%9D%90%AE%F0%9D%90%AB%F0%9D%90%A2%F0%9D%90%AD%F0%9D%90%B2-%F0%9D%90%A9%F0%9D%90%AB%F0%9D%90%A8%F0%9D%90%9F%F0%9D%90%9E%F0%9D%90%AC%F0%9D%90%AC%F0%9D%90%A2%F0%9D%90%A8%F0%9D%90%A7%F0%9D%90%9A%F0%9D%90%A5%F0%9D%90%AC%EF%B8%8Fdict-bicol-invites/1040492329050739); Search result only; full post and current registration unavailable |
| HackForGov 2026 · Region IV-A — CALABARZON | 2026-11-22T02:06:26+08:00 | upcoming / unknown | [Tavily · Free Philippine CTF discovery](https://www.facebook.com/dictr4a/posts/%F0%9D%97%9B%F0%9D%97%94%F0%9D%97%A3%F0%9D%97%A3%F0%9D%97%98%F0%9D%97%A1%F0%9D%97%9C%F0%9D%97%A1%F0%9D%97%9A-%F0%9D%97%A1%F0%9D%97%A2%F0%9D%97%AA-%F0%9D%97%9B%F0%9D%97%AE%F0%9D%97%B0%F0%9D%97%B8%F0%9D%97%99%F0%9D%97%BC%F0%9D%97%BF%F0%9D%97%9A%F0%9D%97%BC%F0%9D%98%83-%F0%9D%9F%B1-%F0%9D%9F%AE%F0%9D%9F%AC%F0%9D%9F%AE%F0%9D%9F%B2-%F0%9D%97%96%F0%9D%97%94%F0%9D%97%9F%F0%9D%97%94%F0%9D%97%95%F0%9D%97%94%F0%9D%97%A5%F0%9D%97%AD%F0%9D%97%A2%F0%9D%97%A1-%F0%9D%97%A5%F0%9D%97%B2%F0%9D%97%B4%F0%9D%97%B6%F0%9D%97%BC%F0%9D%97%BB%F0%9D%97%AE%F0%9D%97%B9-%F0%9D%97%96%F0%9D%97%BC%F0%9D%97%BA%F0%9D%97%BD%F0%9D%97%B2%F0%9D%98%81%F0%9D%97%B6%F0%9D%98%81%F0%9D%97%B6%F0%9D%97%BC%F0%9D%97%BB%F0%9D%99%8F%F0%9D%99%9D%F0%9D%99%9A-%F0%9D%99%98%F0%9D%99%A4%F0%9D%99%A2%F0%9D%99%A5%F0%9D%99%9A%F0%9D%99%A9%F0%9D%99%9E%F0%9D%99%A9%F0%9D%99%9E%F0%9D%99%A4%F0%9D%99%A3-%F0%9D%99%9E/1534594968700265); Search result only; full post and current registration unavailable |
| HackForGov 2026 · Region VII — Central Visayas | 2026-11-22T02:06:26+08:00 | upcoming / unknown | [Tavily · Free Philippine CTF discovery](https://www.facebook.com/DICTr7/posts/-hackforgov-central-visayas-2026-registration-now-open-dict-region-7-proudly-lau/1522802749891574); Search result only; full post and current registration unavailable |
| HackForGov 2026 · Negros Island Region | 2026-11-22T02:06:26+08:00 | upcoming / unknown | [Tavily · Free Philippine CTF discovery](https://www.facebook.com/DICTNIR/posts/%F0%9D%90%91%F0%9D%90%84%F0%9D%90%86%F0%9D%90%88%F0%9D%90%92%F0%9D%90%93%F0%9D%90%91%F0%9D%90%80%F0%9D%90%93%F0%9D%90%88%F0%9D%90%8E%F0%9D%90%8D-%F0%9D%90%8E%F0%9D%90%85%F0%9D%90%85%F0%9D%90%88%F0%9D%90%82%F0%9D%90%88%F0%9D%90%80%F0%9D%90%8B%F0%9D%90%8B%F0%9D%90%98-%F0%9D%90%82%F0%9D%90%8B%F0%9D%90%8E%F0%9D%90%92%F0%9D%90%84%F0%9D%90%83-thank-you-to-all-the-participating-schools-and-st/122190659228889201); Search result only; full post and current registration unavailable |
| HCDG PH x Packet Capture: Beneath the Network · CTF 2026 | 2026-11-22T02:06:06+08:00 | finished / closed | [CyberPH · Public Luma calendar](https://luma.com/akv0l0o1); [Completion/registration evidence](https://kakacomputer.com/curiosity-to-cybersecurity-open-community-and-opportunity-through-packet-capturing/) |
| AWS Student Community Day Mindanao · CTF 2026 | 2026-11-22T02:05:20+08:00 | upcoming / unknown | [AWS student communities · Mindanao](https://awsscd-mindanao.org/); No current CTF registration window established |
| Hack The Box Meetup #11 · CTF 2026 | 2026-11-22T02:05:19+08:00 | upcoming / unknown | [Hack The Box Meetup Manila · Community feed](https://www.meetup.com/hack-the-box-meetup-ph/events/317031526/); No current CTF registration window established |
| LearnPossible – The Hexcore Labs PH University Challenge · CTF 2025 | 2026-11-22T02:05:18+08:00 | upcoming / unknown | [UP Manila · Competition invitations](https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/); No current CTF registration window established |
| ROOTCON 20 CTF | 2026-11-22T02:04:26+08:00 | finished / closed | [CREST · Philippine partner announcements](https://www.crest-approved.org/event/rootcon-20-philippines-2026/); [Completion/registration evidence](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mwprmced2e2h) |
| ROOTCON 20 CTF · Qualifier | 2026-11-22T02:04:26+08:00 | upcoming / unknown | [ROOTCON · Bluesky](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvtlb6qlyc24); No current CTF registration window established |

Validation: **334 tests passed**; Flask temporary-database `/`, `/api/events`, `/api/sources`, and `/api/health` returned HTTP 200. The historical combined listing is finished/closed with both announcements. [Full verification and current frozen-selection measurement](publisher-opportunity-verification.json) retains all paths, timestamps, source failures, benchmark hashes and duplicate checks. Production counts remain **2 events, 3 announcements, 5 runs**. Production data, web service, timer, credentials and UI were not changed in this iteration.

## Reproduce

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
pilot_dir="$(mktemp -d /tmp/ctfinder-publisher-XXXXXX)"
.venv/bin/python -m backend.collect --database "$pilot_dir/events.sqlite3" --report "$pilot_dir/run-1.json"
# The same database retains and enforces each provider's Retry-After cooldown.
.venv/bin/python -m backend.collect --database "$pilot_dir/events.sqlite3" --report "$pilot_dir/run-2.json"
.venv/bin/python -m pytest -q
# Optional: serve only this experimental database on a separate local port.
CTF_DATABASE="$pilot_dir/events.sqlite3" PORT=5001 .venv/bin/python -m backend.app
```

Do not create a new database to evade a currently reported provider cooldown. This run’s next Tavily retry time was 22 November 2026 around 02:19:20 Asia/Manila. The two-run experiment reused its database, and no paid fallback was used.

The existing daily job reloads `source-index.json`: **15 records, ten enabled monitors**, including these two publisher subscriptions, alongside legacy sources and the secondary free search adapter. It follows newly returned public event links and rechecks retained announcements. Publisher qualification is one-time; no individual competition submission is required.

**The single most promising source to monitor next is CyberPH’s public iCal subscription.** It has actually returned a cybersecurity CTF announcement and an online event through the same reusable route. Continue observing its daily first-seen and registration evidence. This is a useful coverage improvement at ₱0 API fees, but it is not yet evidence of dependable early registration alerts or coverage of personal-profile Facebook announcements.
