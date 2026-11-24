# Live source verification — 21 November 2026, Asia/Manila

**Follow-up:** [Discovery iteration](discovery-iteration.md) documents the later fresh-database runs, added PUP feeds, and the Facebook acceptance case that remains unverified. The table below records the original implementation run.

The Python collector itself was run against these sources. Browser/search-engine access was not treated as proof that the app could retrieve a page. The first complete job ran at 21:51 PHT; the second at 21:56 PHT. The scheduled service was also exercised immediately at 21:58 PHT.

| Source | Live result | Returned / imported |
|---|---|---|
| [ROOTCON Bluesky account](https://bsky.app/profile/rootcon.bsky.social) | Documented public author-feed API, HTTP 200; retained posts rechecked with `getPosts` | 146 author posts inspected; 3 CTF announcements; 2 competitions |
| [HackTheNorth.ph](https://hackthenorth.ph/) | Organizer HTML index and linked announcements readable; robots allowed the indexer | 11 pages; 0 accepted. TCON9 conference dates are **not** assigned to a CTF: its fetched page did not identify a specific CTF. The generic recurring “TCON Capture the Flag” description is not a dated edition. |
| [UP ACM events](https://upacm.net/events/) | HTTP 200, robots absent (404) | 1 index; 0 accepted. The archive contains older Haxxor cards but no newly discoverable, sufficiently identified CTF announcements for this adapter. |
| [DICT](https://dict.gov.ph/) | HTTP 403 on robots/page requests | 0; access challenge respected |
| [CERT-PH / NCERT](https://ncert.gov.ph/feed/) | HTTP 403 on robots/feed probes | 0. Initial config used `www`, which redirected outside its allowed host; corrected to the canonical non-`www` source, confirming the 403. |
| [ROOTCON website](https://rootcon.org/) | HTTP 200, but excluded by policy | Its [terms](https://rootcon.org/html/termsandcondition/) prohibit automated extraction. The feed is readable but not used. The former `info.rootcon.org` subdomain also failed direct DNS lookup despite cached search results. |
| [CTFtime documented API](https://ctftime.org/api/) | HTTP 200; monthly windows over 180 days back / 365 days ahead | 180 unique records; 0 met configured Philippine-organizer / Philippine-venue criteria. Global online events merely open to Filipinos were excluded. No rankings or writeups are copied. |
| Facebook announcements through [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started) | Needs credentials + contractual storage rights | No keyed request made. No Facebook full posts fetched. Fixture-tested only. |

The exact first and second run reports are in [verification.json](archive/initial-verification-2026-11-21/verification.json). Daily runtime results are in `data/last-collection.json` and the app’s source panel; those can change independently of this dated report.

## Actual listings

- **ROOTCON 20 CTF**: two posts, including the [12 September announcement](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvccs3acfk2z) and [30 September champions notice](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mwprmced2e2h). The completion notice puts this in Finished. No end timestamp is invented.
- **ROOTCON 20 CTF · Qualifier**: the [19 September qualifier post](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvtlb6qlyc24). The qualifier remains separate. Its post announces competing teams but supplies no confirmed start/end or deadline in accessible text. It is not presented as open registration or automatically marked finished. Its age is flagged.

Both runs retained **2 event rows and 3 announcement rows**. The second run inserted **0** announcements. Existing first-seen timestamps and revision counts were unchanged. No hand-entered events, search-cache facts, fixtures, or screenshot examples populate the live database.

## DICT regional and university investigation

The [CHED regional memorandum carrying the DICT HackForGov briefer](https://chedro3.ched.gov.ph/wp-content/uploads/2026/01/CHEDRO-III-MEMORANDUM-No.-118-series-of-2025.pdf.pdf) directs applicants to regional social pages. Search also found [PIA’s CALABARZON registration report](https://pia.gov.ph/news/dict-calls-for-participants-in-hackforgov-cybersecurity-skills-bout/) and DICT Region 3 Cybersecurity’s [official channel announcement](https://www.youtube.com/watch?v=Boof5DnI4Zw). They confirm that regional social channels matter; they are research evidence, not imported live listings. PIA’s own endpoints were blocked by HTTP 403 from this runtime. Speculative `region3.dict.gov.ph`, `region7.dict.gov.ph`, and `hackforgov.dict.gov.ph` hosts did not resolve and are not integrations.

For universities, [UP ACM’s own history](https://upacm.net/about/) confirms Haxxor’s CTF component and ACMastery cybersecurity activities. Its current site links the `upacm` Facebook account. DLSU’s Information Security Organization and HAU’s Cybersecurity Intelligence Alliance/Cyberfoxes appeared in research, but no verified public organizer feed was found in this investigation. They are not presented as covered. The app does not claim that every Philippine school’s competitions are discoverable.

The configured optional Facebook searches cover `cyberdictr3`, `upacm`, and `rootcon`, constrained to the organizer’s post/photo/video URL paths. The follow-up also recognizes `story.php` and `permalink.php` when the owner matches a verified configured `account_aliases` value. Add verified organizer accounts to expand coverage. Search-only records carry an explicit limitation label and never inherit detailed fields from a snippet. A successful search request still would not verify full Facebook-post access.

For conferences, ROOTCON, HackTheNorth/TCON, and [Recon Village PH](https://reconvillageph.org/) were examined. Recon Village’s current contests page describes challenge tracks without a specific new event edition; its schedule includes talks and past conference appearances. Those are not enough to invent a new dated CTF. The collector likewise does not infer a CTF from the words “security conference” or “hackathon.”

## Access and retention

Bluesky [documents public unauthenticated API reads](https://docs.bsky.app/docs/api/app-bsky-feed-get-author-feed). The ROOTCON account was linked from the organizer’s own website. The app retrieves post text via that API, stores extracted event facts, post URLs, published timestamps, and bounded evidence excerpts; it does not download images or retain raw API responses. Known posts are rechecked each run. API-confirmed unavailable/deleted posts have their cached facts and revision copies removed; a network error does not trigger removal.

HTML/RSS requests use an identifying user agent, check robots rules, enforce time/size/page limits, and restrict discovered links to configured organizer hosts. Access challenges and policy restrictions are not bypassed. Brave’s [API storage guidance](https://brave.com/search/api/) requires a plan with explicit storage rights; the collector refuses to persist results without that operator configuration. Credentials stay in backend environment variables.

Coverage remains limited by source access, indexing latency, feed/page budgets, language and title variations, and image-only details. Deterministic extractors intentionally leave unsupported fields unknown. Parser changes or additional authorized sources will improve recall; a working HTTP request alone is not complete coverage.
