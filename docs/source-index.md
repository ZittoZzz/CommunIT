# Publisher source index pilot — 22 November 2026

The backend now has **10 publisher records: five active monitors and five disabled candidates**. Four direct monitors are new; ROOTCON's existing Bluesky integration is reused. The public site remains an event directory. No event-submission form, Facebook login, paid fallback, or competition URL seed was added.

**Acceptance outcomes:** normal collection did not establish discovery of RAIJIN from any source, and did not find its original Facebook post. The frozen benchmark has **2/10 competitions found, versus 1/10 in the prior measurement; zero verified timely discoveries**. This pilot improves historical coverage and recurring monitoring, but is **not yet dependable as a comprehensive upcoming-event alert**, especially for personal-profile Facebook announcements.

## What changed

`source-index.json`, loaded through `sources.json`, describes publisher role, coverage, recurring endpoint, adapter, enabled status, and candidate blockers. Daily collection reads it automatically. Direct sources run before the unchanged three free keyless Tavily searches. Brave is disabled in the default zero-fee configuration; local credentials and storage settings were not changed.

The RSS/HTML adapters read relevant article bodies, including complete WordPress content and Meetup Markdown. An invitation can identify a CTF without “CTF” in its title. Recognition still requires an actual competition, an evidenced edition, and Philippine scope. Configured article selectors exclude unrelated widgets; calendar dates are not mistaken for publication dates. Resharers stay publishers, while organizer attribution requires evidence. Specific Facebook post embeds and invitation PDFs are retained as supporting links without pretending their contents were fetched.

Provenance records the recurring endpoint → announcement → event, plus publisher and source. Shared announcement/registration links can merge supporting evidence only within compatible editions, stages and regions. CREST's verified trailing-slash redirect is normalized on its event paths. Qualifiers remain separate from finals. First-seen and revision timestamps reflect completed source responses, and retained revision evidence supports conservative future registration-window measurements. Winner recaps cannot become open registration just because an older sentence says “register.”

## Pilot index

Historical example URLs below are research evidence, not inputs to the collector.

| Publisher / role / coverage | Recurring source and adapter | Advance evidence and live result |
|---|---|---|
| **UP Manila**, resharer; NCR/national university invitations | [Generic WordPress feed](https://www.upm.edu.ph/feed/?post_type=cpt_announcements&s=capture+the+flag), RSS + article body | **Active.** One invitation, one new competition. [LearnPossible invitation](https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/) published 2 September 2025, before its October program. UP Manila is publisher; Hexcore Labs PH is organizer. Historical coverage. |
| **ROOTCON**, organizer; Luzon/national/online | [Official Bluesky publisher](https://bsky.app/profile/rootcon.bsky.social), documented public author-feed API | **Active; existing integration.** 146 posts checked, three announcements, two event records. Advance [main CTF post](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvccs3acfk2z) and subsequent completion evidence; qualifier stays separate. |
| **Hack The Box Meetup Manila**, both; NCR/community | [Recurring event RSS](https://www.meetup.com/hack-the-box-meetup-ph/events/rss/), RSS complete body | **Active.** One invitation, one new competition: [Meetup #11 / CyberSecureU](https://www.meetup.com/hack-the-box-meetup-ph/events/317031526/), published 18 October 2026. Body credits AWS SBG–QCU/JPCS–QCU and restricts entrants to current QCU students. Body/calendar dates conflict; CTF schedule and registration window remain unconfirmed. |
| **AWS student communities in Mindanao**, organizer; Davao/Mindanao | [Annual publisher root](https://awsscd-mindanao.org/), HTML CTF track | **Active.** One new competition announced before the parent conference's 28 November date. A previous-year gallery and [organizer's prior recap](https://builder.aws.com/content/31yj3GtlcDPWCT8UyJwtz9EJmsn/aws-student-community-day-davao-2025-bloom-in-the-cloud) establish recurrence. Conference tickets do not establish CTF registration. CTF-specific schedule, eligibility and registration are unconfirmed. |
| **CREST**, partner resharer; Philippine events in Asia calendar | [Asia list](https://www.crest-approved.org/events/category/asia-events/list/) and its `?eventDisplay=past` view, HTML archive → article | **Active.** Three pages checked, one [ROOTCON partner announcement](https://www.crest-approved.org/event/rootcon-20-philippines-2026/), merged with the main ROOTCON event. Research found WebPage publication metadata dated 19 June 2026, before the conference. CTF times are not inferred from conference JSON-LD; Posted remains unknown because the current adapter does not extract WebPage publication metadata. This monitor currently follows the verified recurring ROOTCON partnership, not every Asia event. |
| **FEU Tech Eventually**, resharer; NCR/campus | [Campus calendar](https://paraverse.feutech.edu.ph/eventually/discover/), HTML candidate | **Disabled.** Readable recent calendar: 11 event links, no current CTF. A [historical invitation](https://paraverse.feutech.edu.ph/eventually/event/cyberxplore-xplore-xecute-xcel-1760501867) needs structured date/venue extraction outside its body; advance publication timing is unknown. Other renditions include cancellation and draft notices. |
| **UM Student Developers Community**, organizer; Davao/Mindanao | [Recurring Luma host profile](https://luma.com/user/usr-8iOKid6iGmryO2o), HTML candidate | **Disabled.** [Historical CTF registration page](https://luma.com/rqk7jyvp) exists, but the recurring profile returned no event links. Individual event URL was not seeded. |
| **OWASP Cebu**, organizer; Cebu/Visayas | [CTF index](https://www.owasp-cebu.org/ctfs), HTML candidate | **Disabled.** Redirects to login. Public advance invitation plus readable recurring CTF endpoint not established. No active Visayas publisher is claimed. |
| **Philippine Information Agency**, resharer; nationwide | [Generic CTF feed](https://pia.gov.ph/feed/?s=capture+the+flag), RSS candidate | **Disabled.** [April 2025 invitation](https://pia.gov.ph/news/dict-calls-for-participants-in-hackforgov-cybersecurity-skills-bout/) gives an advance registration window, but backend robots verification returns HTTP 403. Search-index visibility is insufficient. |
| **VEKTR Security**, sponsor/resharer; Philippine community | [Publisher website](https://vektrsec.com/), HTML candidate | **Disabled.** Website readable but no recurring news/feed/archive found. An indexed social sponsor reshare is a research lead, not a working integration. |

The index monitors future posts from configured publishers. It does not automatically trust or enable an unknown organizer. Generic search may reveal new publishers for one-time qualification. UP Manila was prioritized because the user supplied that publisher gap; its event was rediscovered from the generic feed. Other publishers were investigated independently. No acceptance-case title, author, post ID, dates or supplied URL entered runtime queries or seeds.

## A reproduced discovery path

1. Start at `https://www.upm.edu.ph/feed/?post_type=cpt_announcements&s=capture+the+flag` with no event-specific query.
2. The feed returns `https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/`.
3. Read the body: it identifies a CTF tournament, a Philippine venue, the organizer, and the event edition. The title alone would have failed the old recognition gate.
4. The normal collector creates event **`9ce2881dabb3fb36b01fa057`**, displayed as **“LearnPossible – The Hexcore Labs PH University Challenge · CTF 2025.”** Its announcement links back to UP Manila. Its supporting [invitation PDF](https://www.upm.edu.ph/wp-content/uploads/2025/09/5555_1756429668_EXPERTSPRIME_HEXCORE_UNIVERSITY_INVITATION_V1_UP.pdf) is preserved as a link; the collector did not read the PDF.

The source's October 6 event-date wording is retained as context. Registration status/deadline and CTF clock times remain unknown. Neither earlier workshop dates nor parent-program hours become invented CTF bounds. This is a historical invitation discovered today, not a timely registration alert.

Other new listings are **“Hack The Box Meetup #11 · CTF 2026”** (`a6f4e09e73b9a682104e0b25`) and **“AWS Student Community Day Mindanao · CTF 2026”** (`a2ca2700df968f8eb6fd19d6`). CREST adds supporting evidence to an existing ROOTCON competition rather than creating another one.

## Live verification

FINAL_VERIFICATION_PENDING

Existing monitors remain enabled: HackTheNorth, UP ACM, PUP announcements/news, DICT, NCERT, CTFtime, and ROOTCON Bluesky. Successful checks with no accepted competition are reported as such. DICT/NCERT stop at robots HTTP 403; ROOTCON's website remains policy-restricted with its public Bluesky feed used instead. Five index candidates and Brave report `disabled`, not successful requests.

Tavily's unchanged production queries are:

- `site:facebook.com Philippines cybersecurity CTF competition registration`
- `Philippines capture the flag CTF competition registration`
- `Philippines cybersecurity community CTF events calendar registration`

Earlier exploratory full runs checked these successfully and found regional HackForGov leads. A later attempt returned HTTP 429 / Retry-After 404 seconds; its remaining two queries were skipped, not successful zero-match searches. The pending second attempt was stopped before making another search request, and the cooldown was honored. Search availability is a material limitation of free keyless monitoring.

One generic research query, `Philippines "CTF" "register" community website event -site:facebook.com -site:instagram.com`, surfaced an indexed [LinkedIn profile](https://ph.linkedin.com/in/c-revillosa/tl) containing a sponsor reshare relevant to the acceptance case. This was a separate research-tool result, **not normal collector discovery**. The same direct keyless diagnostic was rate-limited, and the sponsor website had no repeatable announcement endpoint. That is the last successful research step; neither normal competition discovery nor original-post identity was established. Opaque Facebook URLs are not treated as equivalent without evidence. These observations do not prove that a search provider never indexed the post.

## Benchmark and usefulness

The original ten-event research and measurement files are frozen and hash-checked. The new measurement is separate: [source-index-benchmark-results.json](source-index-benchmark-results.json). ROOTCON was already covered; LearnPossible is the newly covered benchmark event. The other eight remain unobserved. Original Facebook identity is unestablished for all ten. RAIJIN is evaluated separately, outside that denominator.

**Verified timely discovery: 0.** First-seen timestamps are actual collector observations, not backdated publication dates. `registration_observations` stores reasons for unknown availability, and verified observations require contemporaneous source evidence, explicit open registration and a confirmed timed/timezoned deadline. Date-only or ambiguous windows stay unverified. The AWS competition is an advance discovery, but its conference ticket CTA does not verify CTF registration availability. Feed/body date conflicts and missing CTF boundaries remain explicit limitations.

This is useful as an additional discovery directory. It should not yet be presented as a reliable alert covering all joinable Philippine community CTFs. The next practical work is to qualify more accessible community feeds, especially Visayas and personal-profile resharing communities, then accumulate genuine daily first-seen/registration evidence. Do not fill gaps with manually inserted events or target-specific queries.

## Reproduce and next scheduled run

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
pilot_dir="$(mktemp -d /tmp/ctfinder-source-index-XXXXXX)"
.venv/bin/python -m backend.collect --database "$pilot_dir/events.sqlite3" --report "$pilot_dir/run-1.json"
# If a report returns Retry-After, wait that many seconds before the next run.
.venv/bin/python -m backend.collect --database "$pilot_dir/events.sqlite3" --report "$pilot_dir/run-2.json"
.venv/bin/python -m pytest -q
# Inspect this temporary result in the existing site:
CTF_DATABASE="$pilot_dir/events.sqlite3" PORT=5001 .venv/bin/python -m backend.app
```

Open `http://127.0.0.1:5001`. These are the normal collection entry point and default source configuration; only database/report destinations differ from the timer. Search ranking can change; a genuinely new URL is not automatically a duplicate.

The existing timer is still scheduled for **06:00 Asia/Manila on 22 November 2026**. Its next process will load `sources.json` plus the five enabled publishers in `source-index.json`, run direct monitors first, and use free keyless Tavily second. Production SQLite, running services and timer were left untouched. No frontend change or restart was performed.

Research artifacts: [publisher audit](source-index-publisher-research.json), [regional audit](source-index-regional-research.json), [FEU extraction check](source-index-feu-historical-probe.json), [CREST redirect/publication proof](source-index-canonical-probe.json), [keyless diagnostic](source-index-search-probe.json). Earlier probe artifacts describe their own intermediate configuration, not the final enabled set.
