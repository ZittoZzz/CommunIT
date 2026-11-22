# Classification and advance-notice audit

Observed November 22, 2026, Asia/Manila. All collection uses existing free sources. No publisher seeds, search queries, production data, services, built frontend, or frozen benchmark were changed in this iteration.

## Why LearnPossible appeared under Upcoming

The first incorrect step was **date extraction**, not the React filter. The normal collector reached the complete invitation through UP Manila's recurring generic search feed:

[WordPress announcements feed: `capture the flag`](https://www.upm.edu.ph/feed/?post_type=cpt_announcements&s=capture+the+flag) → [university invitation](https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/) → event `9ce2881dabb3fb36b01fa057`.

The fetched article has publication metadata **September 2, 2025**, pre-tournament workshops **September 16–18, 2025**, and **Event Details → Date → October 6, 2025**. HTML places the Date label and value on separate lines. The parser retained October 6 in the edition evidence and summary but discarded it as a structured competition date. SQLite therefore had no start or end, the API emitted `schedule_tba/upcoming`, and the UI correctly followed that incorrect classification. Neither the publication date nor workshop dates should become the tournament date.

| Layer | Before | Corrected |
|---|---|---|
| Extracted/stored tournament day | Absent; date only in summary/edition evidence | `competition_date: {raw: "October 6, 2025", value: "2025-10-06", precision: "date", timezone: null}` plus source quote |
| Competition start/end | Unknown | Still unknown; no midnight or full-program clock interval invented |
| API status / section | `schedule_tba` / `upcoming` | `past_date` / `past` |
| UI | Upcoming, Schedule TBA | **Past & finished → Past date · completion unconfirmed**, Tournament date October 6, 2025 |
| Registration / deadline | Unknown / unknown | Still unknown / unknown |
| Event identity and first seen | Existing values | Preserved; one announcement gains a parser-correction revision |

The general rule supports wrapped Event Details dates and explicit Tournament/Competition/CTF date labels. It rejects ambiguous/missing-year dates and avoids borrowing conference or teaching-program dates. A historical calendar date moves a listing out of Upcoming without claiming that the organizer confirmed completion. Unknown timezones use a conservative whole-date comparison, never a manufactured timestamp. Same-day reminders preserve already confirmed clock times; an actual changed date replaces stale bounds. Postponements clear the active schedule. Genuine future teasers remain **Schedule TBA**; search-only records with unknown dates say **Undated search lead**.

The article's 9 AM–6 PM is a program interval, not confirmed CTF clock times. Its linked organizer PDF is retained as a link by the normal collector. A separate research read corroborates October 6 but gives different workshop dates; that PDF research was not inserted into runtime facts. Registration remains unverified.

The corrected real API and UI were checked on isolated ports 5001 and 5174 with a separate database, without mocked responses. Browser checks found **zero LearnPossible matches in Upcoming and one in Past**, no browser errors, and no horizontal overflow at 390 px. See [desktop screenshot](learnpossible-ui-desktop.png), [card screenshot](learnpossible-ui-card.png), [mobile screenshot](learnpossible-ui-mobile.png), and [UI verification](learnpossible-ui-verification.json). The running production service and its existing build were not redeployed.

## Which recurring sources provide advance notice?

This is a small evidence audit, not a complete census. The last-12-month window is November 22, 2025–November 22, 2026. LearnPossible is the requested older worked example; the PIA row is an explicitly older access-restriction comparison. Dates below are organizer calendar dates, not invented midnight instants. “Unknown deadline” stays visible even when an invitation is genuine.

| Recurring source → historical/current example | Public announcement | Tournament / relevant date | Registration deadline | Publisher notice and what normal collection reaches |
|---|---|---|---|---|
| [UP Manila feed](https://www.upm.edu.ph/feed/?post_type=cpt_announcements&s=capture+the+flag) → [LearnPossible invitation](https://www.upm.edu.ph/cpt_announcements/learnpossible-the-hexcore-labs-ph-university-challenge/) | Sep 2, 2025 | Oct 6, 2025; workshops separate | Unknown | **34 days** before tournament. Feed → full article works. Institutional reshare; outside window. |
| [ROOTCON Bluesky](https://bsky.app/profile/rootcon.bsky.social) → [CTF teaser](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvccs3acfk2z) | Sep 12, 2026 | Sep 24–25, 2026¹ | Unknown | **12 days** before independently documented CTF start. Public author API works. Separate Sep 19 qualifier update is same-day/live coverage, not an advance entry invitation. |
| [HTB Meetup Manila RSS](https://www.meetup.com/hack-the-box-meetup-ph/events/rss/) → [CyberSecureU invitation](https://www.meetup.com/hack-the-box-meetup-ph/events/317031526/) | Oct 18, 2026 | Body Nov 4; public calendar Nov 29, 2026 — **conflict** | Unknown | 17 or 42 days to conflicting program dates; a single tournament lead is **unverified**. Feed reaches explicit CTF invitation, QCU students only. |
| [AWS Student Community Day Mindanao](https://awsscd-mindanao.org/) | Unknown | Nov 28, 2026, CTF track 12:45–15:15; timezone not explicit | Unknown | Live dated program identifies a CTF. Observed **six calendar days ahead**; publication lead unknown. Conference tickets do not establish CTF entry. |
| [CREST Asia archive](https://www.crest-approved.org/events/category/asia-events/list/?eventDisplay=past) → [ROOTCON partner announcement](https://www.crest-approved.org/event/rootcon-20-philippines-2026/) | Jun 19, 2026 | Parent conference Sep 23–25; no CTF-specific interval in this article | Unknown | **96 days before the parent conference**, not a CTF registration window. Recurring index → article works; partner announces CTF prizes. |
| [CyberPH public Luma calendar](https://api.luma.com/ics/get?entity=calendar&id=cal-ZW4YOEwv4lmL66C) → [Packet Capture listing](https://luma.com/akv0l0o1) | Unknown; calendar export time is not publication | Oct 4, 2026 kickoff; Oct 26 completion corroborated by recap | Unknown | Calendar → invitation works, but publication lead cannot be measured. Old kickoff registration control is not present-day entry evidence. |
| [KakaComputer CTF RSS](https://kakacomputer.com/tag/ctf/feed/) → [Packet Capture recap](https://kakacomputer.com/curiosity-to-cybersecurity-open-community-and-opportunity-through-packet-capturing/) | Nov 1, 2026 | Completed Oct 26, 2026 | Unknown | **Six days after completion**. Feed → recap works; corroboration/publisher discovery, not demonstrated advance notice. |
| [PIA generic feed](https://pia.gov.ph/feed/?s=capture+the+flag) → [archived HackForGov invitation evidence](https://pia.gov.ph/news/dict-calls-for-participants-in-hackforgov-cybersecurity-skills-bout/) | Apr 14, 2025² | Tournament unknown | Apr 25, 2025, date only² | **11 days to deadline** in retained research. Current robots check HTTP 403; disabled candidate, not a working recurring monitor. Outside window. |

¹ ROOTCON's CTF dates come from frozen independent research of the [organizer contest rules](https://rootcon.org/html/rc20/contests/), not from the Bluesky adapter. The website remains policy-restricted and was not scraped in this audit. The author feed returned 146 posts in two pages, including three accepted announcements.

² PIA dates are explicitly retained indexed-research evidence, not a newly fetched article body. This audit did not bypass its restriction.

Seven enabled sources in this focused audit were readable; the PIA candidate was blocked. That does not mean seven sources yielded current invitations. Feed slices are incomplete archives: UP Manila, HTB, and Kaka each returned one item; CyberPH returned three calendar events. ROOTCON has a configured lookback/page bound; CREST's configured link filter only follows its verified ROOTCON relationship. The AWS page is a current annual edition. Luma access has been intermittent historically, though this check succeeded. Full paths, request outcomes, quotes, limits, and timestamps are in [source evidence](advance-notice-source-audit.json).

The HTB public event page was followed from the RSS link during this audit. Its calendar metadata confirms November 29 while its prose still says November 4. The normal RSS adapter currently reads the complete feed body and does not fetch that page's metadata. Neither a confirmed reschedule nor open CTF registration is established by that discrepancy. CREST's publication date is available to the audit in WebPage metadata but is not currently extracted as Posted by the normal adapter.

## Publisher notice versus collector notice

**No retained observation verifies an open-registration discovery.** The deadline-backed timely count, current-live-control count, and first-seen-while-open count are all zero. An invitation found late does not become an earlier alert because its publisher supplied an old publication date.

| Example | Actual retained collector observation, Asia/Manila | What it proves |
|---|---|---|
| LearnPossible | Nov 22, 2026, stored 00:45:02; legacy receipt interval 00:45:02–00:46:18³ | **412 days late**, despite publisher's 34-day advance invitation. |
| ROOTCON main CTF | Production first seen Nov 21, 2026, 21:51:58 | **58 days after** independently documented tournament start. |
| HTB / CyberSecureU | Nov 22, 2026, legacy interval as above³ | After prose's Nov 4 date, before calendar's Nov 29; conflict and unknown registration prevent a timely claim. |
| AWS Mindanao CTF | Nov 22, 2026, legacy interval as above³ | **Six days before** the independently observed CTF program date, but no CTF-specific open-registration evidence. Short notice remains a useful lead. |
| CREST partner article | Nov 22, 2026, 00:05:32, temporary normal run | Historical discovery after parent conference. |
| CyberPH Luma invitation | Nov 22, 2026, 02:06:14, temporary normal run | Historical invitation; competition already found via recap at 01:42:36. |
| Kaka recap | Nov 22, 2026, 01:42:36, temporary normal run | Historical completion evidence, 27 calendar days after completion. |
| PIA invitation | No retained successful normal-source discovery | No collector lead-time claim. |

³ These earliest retained SQLite rows use a legacy job-start stamp, not precise response receipt. Their completed run bounds the actual receipt interval. A later response-stamped normal run records UP Manila at 00:58:46; all are November 22, 2026. Nothing was backdated. Except the explicitly marked ROOTCON production row, these are temporary normal-command verification runs, not evidence of a delivered production alert. Production still has two ROOTCON events and three announcements; the newer indexed sources have no production last-success observation yet.

The correction demonstration copied a previously verified temporary database to retain its own first-seen evidence. In that copy, LearnPossible remains first seen **November 22, 2026, 02:05:18 Manila**; an earlier observation in a different database was not substituted. See [before trace](learnpossible-before-trace.json) and [collection/API verification](classification-verification.json).

## RAIJIN and verification limits

The competition did **not** independently surface in the tested normal-source listings. Its exact original Facebook post did **not** surface in the available discovery paths, related links, or raw returned URLs either. Both supplied URL forms and decoded Facebook embed targets are evaluation-only comparisons; no title, author, post ID, event date, or supplied URL was added to runtime queries, configuration, or fixtures used by live collection. Other opaque Facebook IDs remain unresolved.

The free search check returned **HTTP 429**, then skipped its remaining generic queries and persisted Retry-After; the second completed collection skipped Tavily during that cooldown. A cooldown skip or rate-limited request is not a successful search with zero matches. Therefore this run cannot establish that the post was absent from Tavily's index. The frozen benchmark files remain unchanged: the prior **3/10 historical matches and zero verified timely discoveries** remain the current measurement.

## Next source to improve

Prioritize **Hack The Box Meetup Manila's existing RSS feed plus the public event pages it links**. It already provides a timestamped campus CTF invitation through a readable, free recurring source, but the feed-only path misses the calendar metadata and date conflict found today. A bounded linked-page follow-up that preserves conflicting dates and reads CTF-specific entry evidence could help catch student competitions and schedule changes outside the university archives.

Today verified the source-to-invitation path, CTF wording, campus eligibility, and conflicting dates. One week of normal observation could establish uptime, revisions, and actual first-seen/open-registration evidence if new information appears. It cannot prove an alert happened in the past or guarantee a new invitation. No new schedule or publisher monitor was installed as part of this audit; the existing daily timer will continue using the unchanged default sources.

## Reproduction and checks

The completed verification runs use the normal daily entry point with the default source index against a **copy of an existing temporary verification database**, preserving source cooldowns and first-seen timestamps. Production is not used:

```bash
cd /home/miguel/Documents/GitHub/ctfinder_ph
check_dir=/tmp/ctfinder-classification-78w9wp7j
.venv/bin/python -m backend.collect \
  --database "$check_dir/events.sqlite3" --report "$check_dir/recheck.json"
```

For a new isolated installation, use `check_dir="$(mktemp -d /tmp/ctfinder-classification-XXXXXX)"` instead. Its first-seen timestamps will correctly be new; it cannot reproduce historical discovery times. Normal collection honors a persisted Retry-After and does not require a special event argument.

Both completed collections retained **11 events, 14 announcements, and 22 publisher candidates**, with no duplicate identities/announcement URLs and unchanged first-seen timestamps. The first refresh added nine revisions because the extracted schema gained the tournament-day field; these are parser corrections, not evidence of nine publisher edits. LearnPossible's one announcement changed from one to two revisions. The second completed run added no announcements, events, candidates, or revisions. An intervening process exited 143 before producing a report; its incomplete run record was retained, and the same database was then checked normally. It was not counted as a completed successful collection.

Each completed normal run had **15 successful source checks**, two robots-403 blocks (NCERT and DICT), one policy restriction (ROOTCON website), six disabled configurations, and Tavily unavailable/rate-limited. Earlier data and source successes survived these failures. The focused seven-readable-source audit above is a subset of this full default-source run.

Validation and per-source outcomes are retained in [classification-verification.json](classification-verification.json). The full backend suite passed **353 tests**; TypeScript and **six Playwright tests** passed. Tests cover the wrapped date label, unrelated competition invitations, conference/workshop exclusions, genuine future teasers, unconfirmed search leads, rescheduling, matching-date reminders, registration separation, and preserved first-seen timestamps.
