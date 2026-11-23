# Prototype iteration — November 22, 2026

The combined check improved from **2/8 discovery and 2/4 actionable recall** to **8/8 and 4/4** after generic search discovery, primary-page verification, and listing fixes. Both recall gates pass. **Overall acceptance does not pass:** cybersecurity is verified only on Watchlist, a visible organizer title contains conflicting prize copy, and all four original evidence replays remain unverified because their bundle lacks HTML.

This is a known regression against the disclosed Nov 22 reference, not a new blind benchmark. The original blind score remains **0/8 discovery, 0/4 actionable**. The report below separates live collection from later offline improvements.

## Combined check first, then discovery improvements

| Stage | Evidence and database | Discovery | Actionable in first five per geography |
|---|---|---:|---:|
| Original frozen blind run | Unchanged original artifacts | 0/8 | 0/4 |
| Combined baseline | Normal collector, fresh temporary DB, existing 27-source configuration | 2/8 | 2/4 |
| Improved first live collection | Normal collector, another fresh temporary DB, public search outputs plus existing calendars | 7/8 | 2/4 |
| Final prototype | Saved improved-run responses reprocessed offline; normal API and actual browser order | 8/8 | 4/4 |

The baseline started at **2026-11-22 22:41:52.744959 Asia/Manila**. The improved collection started at **22:54:37.660330** and finished at **22:58:31.572545**. Its 45-day window is **[2026-11-22 22:54:37.660330, 2027-01-06 22:54:37.660330), Asia/Manila**. Individual adapters use their source-attempt clock, a few minutes later; none of the accepted or reference rows is at that boundary. Offline refinements use an explicitly injected capture-time clock; their timestamps are not new live observations.

The baseline's weakest area was discovery outside configured CTF publishers. `backend/extract.py` and the existing search adapter require CTF identities and Philippine scope; generic AI/developer events and international opportunities cannot pass those gates. The prior MLH and Safe AI integrations already reused collection, announcement storage, `/api/events`, and the student UI. This iteration kept those working paths and added an optional bounded search adapter with shared primary-page parsers. It did not introduce a second collector or change the production source configuration.

The baseline contained a pre-existing individual AWS conference URL in `aws-mindanao`. That seed is disclosed and was removed from improved/final inputs. Its agenda CTF segment never received conference discovery credit. The reference had already been disclosed in this conversation, so this work cannot claim blindness even though runtime discovery was not seeded with its answers.

## Actual inputs and isolation

The search-first experiment consumed the **complete 167 URL/title results from nine generic public searches**. Returned event titles and URLs are search outputs, not manually selected runtime seeds. Snippets never establish event facts. Calendar roots remain stable organizer URLs. Exact runtime queries:

1. `site:luma.com Philippines AI developer community events November December 2026`
2. `Cebu AI developer community meetup November December 2026 registration`
3. `site:gdg.community.dev/gdg-manila events November December 2026`
4. `site:meetup.com/globalaiphilippines events November December 2026`
5. `site:meetup.com/aws-sbg-at-university-of-the-philippines-mindanao-campus events November December 2026`
6. `site:devpost.com online international students AI hackathon November December 2026`
7. `online cybersecurity CTF December 2026 worldwide registration`
8. `DICT NCR cybersecurity student competition registration November December 2026`
9. `AWS User Group Philippines events November December 2026`

The search provider was the public web-search tool, explicitly separate from the repository's Tavily transport. The baseline's second Tavily query returned **HTTP 429, Retry-After 1026 seconds**; the remaining query was skipped. Native search was disabled in the improved temporary configuration. This demonstrates primary-page discovery from externally captured search outputs, **not a verified autonomous replacement for the rate-limited native search service**. Earlier exploratory generic searches were not all retained verbatim in a local manifest; that provenance gap is disclosed in `discovery-provenance.json`. Two supplemental generic cybersecurity research queries were saved separately and were not runtime inputs.

The actual improved-run command was the existing CLI under a read-only root mount, with only the new iteration directory writable:

```bash
bwrap --ro-bind / / \
  --bind /tmp/ctfinder-iteration-20261122-b6akcp1p /tmp/ctfinder-iteration-20261122-b6akcp1p \
  --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv PYTHONPATH /tmp/ctfinder-iteration-20261122-b6akcp1p/improved/instrument:/home/miguel/Documents/GitHub/ctfinder_ph \
  -- .venv/bin/python -m backend.collect \
  --config /tmp/ctfinder-iteration-20261122-b6akcp1p/improved/inputs.json \
  --database /tmp/ctfinder-iteration-20261122-b6akcp1p/improved/live.sqlite3 \
  --report /tmp/ctfinder-iteration-20261122-b6akcp1p/improved/collector-report.json
```

The baseline used the same CLI/isolation pattern with its own `baseline/` inputs, DB, report, and observation wrapper. The wrapper records timestamps, exact response bytes and hashes; it does not supply event facts. The improved log contains **377 observations** (362 successful, 15 failed), including HTTP reads and outer public-page calls, so these are not 377 distinct pages. The final UI uses a copy of the temporary DB, the normal Flask `/api/events` endpoint, and a Vite build outside the repository's existing `frontend/dist`.

No production DB, frozen blind-run artifact, prior MLH/Safe AI integration artifact, service or schedule was changed. Final hash/mtime verification covers **344 protected files** and **378 frozen improved-run capture artifacts**. Offline collection used `bwrap --unshare-net` plus a client that serves only captured responses and rejects uncaptured requests.

## Implementation and verified corrections

| Changed files in this iteration | Purpose |
|---|---|
| `backend/opportunity_search.py` | Optional generic search-first source, complete output audit, bounded calendar/event traversal, explicit deferral/failure outcomes; deterministic traversal with existing records. |
| `backend/opportunity_pages.py`, `backend/devpost.py` | Shared primary-page verification for Luma, Meetup, GDG and Devpost; independent dates, typed cutoffs, price, eligibility and signup evidence. |
| `backend/ctftime_primary.py`, `backend/adapters.py` | Opt-in international CTFtime discovery followed to organizer pages; directory dates alone are insufficient. Register the new source through the existing collector. |
| `backend/luma.py` | Reuse community-topic and organizer-ownership parsing; public/restricted tickets and hybrid PH placement remain distinct. |
| `backend/db.py`, `backend/app.py` | Optional 45-day normal listing view; undated/out-of-window and recurring signup-unverified leads go to Watchlist. Default legacy configuration remains supported. |
| `frontend/src/App.tsx`, `frontend/e2e/directory.spec.ts` | Watchlist, approval applications at current-action priority, verified-free priority, and separate submission cutoffs for AI/cyber as well as general IT. |
| `tests/test_opportunity_search.py`, `tests/test_opportunity_pages.py`, `tests/test_ctftime_primary.py`, `tests/test_devpost.py`, `tests/test_pilot_listing.py` | Discovery, trust, date precision, geography, normal API placement and replay regressions. |
| `README.md`, `docs/architecture.md`, this report | Document opt-in operation, limitations and results. |

Earlier uncommitted date, MLH and Safe AI work remains in place; it is not attributed to this iteration. No benchmark fixture or temporary configuration is committed as runtime source data.

Verified corrections include: chat/footer-only Attend controls no longer imply open signup; explicit paid/waitlist notices override generic platform zero-price metadata; conditional free offers and FAQ questions cannot establish free admission; body eligibility restrictions are retained; contradictory primary dates are withheld; event end never becomes a signup cutoff; explicit approval applications stay visible near open registrations. Existing date-only values remain dates and expire after their Manila calendar day. The final browser audit also found AI submission cutoffs hidden despite correct storage; the shared card now renders them separately from registration and event end.

## Collection-to-student trace

| Discovered route | Stored event ID | Final normal UI placement |
|---|---|---|
| `https://ghw.mlh.com/` → linked edition → organizer-designated `events.mlh.com` signup page | `943b0e0f713bf14145eea408` | International Upcoming #3; free, account required; ends Dec 11 at 02:00 Manila. |
| Safe AI organizer calendar → linked Luma event → public standard/fellow ticket evidence | `7bcbef44363eca82d57667d9` | PH Upcoming #2; one hybrid card; approval required; unknown fee/cutoffs. Search later corroborates the same event. |
| Generic Luma PH query → returned primary event → matching public host/calendar evidence | `e9ff1d4d41c81285d8ad7ff5` | PH Upcoming #1; open signup, unknown price. |
| Generic international student AI hackathon query → returned Devpost primary overview → saved-page parser | `8d0defb047f5da450e58c741` | International Upcoming #2; free; started before T, qualifying submission cutoff Nov 29 at 07:00 Manila. |

Exact discovered URLs, query provenance, response hashes, payloads and stored IDs are in the saved fetch log, collector reports, database export and normal API JSON. Individual event links below describe outputs; they were not added as discovery inputs.

## Actual student-visible shortlist

The following order comes from the rendered normal UI, with no evaluator rearrangement. The first five rows in each geography determine actionable recall. All dates shown in the exact cards below use Asia/Manila.

**PH opportunities — Upcoming & live**

| Rank | Exact displayed title / primary link | Signup | Price |
|---:|---|---|---|
| 1 | [AI: Growing Up and Leaving Home](https://luma.com/rl9jbxgv) | Registration open | Unknown |
| 2 | [Safe AI Philippines AI Governance Accelerator Cohort 2 - Demo Day](https://luma.com/6ufidrj7) | Applications open · approval required | Unknown |
| 3 | [Hands-on with Foundry Agents and Foundry IQ](https://www.meetup.com/globalaiphilippines/events/317284119/) | Unknown | Unknown |
| 4 | [DevFest Manila 2026 Main Stage](https://gdg.community.dev/events/details/google-gdg-manila-presents-devfest-manila-2026-main-stage/) | waitlisted | Paid · amount not announced |
| 5 | [AWS Student Community Day Davao](https://www.meetup.com/aws-sbg-at-university-of-the-philippines-mindanao-campus/events/316992979/) | Unknown | Unknown |
| 6 | [DevFest Cebu 2026](https://gdg.community.dev/events/details/google-gdg-cebu-presents-devfest-cebu-2026/) | Unknown | Unknown |
| 7 | [AI Unwrapped: Agents, Data & Intelligence](https://www.meetup.com/globalaiphilippines/events/317510987/) | Unknown | Unknown |

**International online opportunities — Upcoming & live**

| Rank | Exact displayed title / primary link | Signup | Price |
|---:|---|---|---|
| 1 | [Build Your First AI App](https://build-your-first-ai-app.devpost.com/) | Registration open | Free |
| 2 | [Global AI Builder’s Challenge](https://global-ai-builders-challenge.devpost.com/) | Registration open | Free |
| 3 | [Global Hack Week: Open Source Week](https://events.mlh.com/events/15199-global-hack-week-open-source-week) | Registration open | Free |
| 4 | [Ryze Hacks 2026](https://ryzehacks.devpost.com/) | Registration open | Free |
| 5 | [LaunchPad Hacks (580k In Prizes!)](https://launchpad-hacks.devpost.com/) | Registration open | Unknown |
| 6 | [FRONTIER//26](https://frontier26.devpost.com/) | Registration open | Unknown |

Watchlist contains **x3CTF 2026** (international #1, dated but signup unknown) and **ROOTCON 20 CTF · Qualifier** (PH #1, no qualifying dated opportunity established). Four historical records remain in Past & finished; they are not shortlist opportunities. LaunchPad’s displayed prize title conflicts with the organizer’s body copy; see the trust gap below.

## Benchmark score and actual placement

The final normal API and browser capture contain **19 events and 22 announcements**: 13 Upcoming/live cards, two Watchlist cards and four historical cards. Ranks below are the captured normal UI order after generic free/current-action prioritization; the evaluator did not rearrange them. The first combined baseline scored **2/8 discovery and 2/4 actionable**; the initial improved live collection scored **7/8 and 2/4**. Subsequent improvements were tested on the same saved responses.

| Reference edition | Found | Actual student placement | Actionable top-five credit |
|---|---:|---|---:|
| DevFest Manila 2026 Main Stage | Yes | PH Upcoming #4 | Not an actionable reference |
| Hands-on with Foundry Agents and Foundry IQ | Yes | PH Upcoming #3 | Not an actionable reference |
| AWS Student Community Day Mindanao 2026 | Yes | PH Upcoming #5, titled “AWS Student Community Day Davao” | Not an actionable reference |
| Safe AI Philippines Cohort 2 Demo Day | Yes | PH Upcoming #2 | Yes |
| AI: Growing Up and Leaving Home | Yes | PH Upcoming #1 | Yes |
| Global Hack Week: Open Source Week | Yes | International Upcoming #3 | Yes |
| Global AI Builder’s Challenge | Yes | International Upcoming #2 | Yes |
| x3CTF 2026 | Yes | International Watchlist #1 | Not an actionable reference |

The AWS match uses an equally authoritative organizer chapter page. Its description explicitly identifies the Davao/Mindanao 2026 conference, date and venue; the reference explicitly permits this title variant. It is distinct from the earlier unsupported conference CTF agenda segment.

| Measure | Final regression result | Required |
|---|---:|---:|
| Discovery | **8/8**; PH **5/5**, international **3/3** | **6/8** |
| Actionable within first five per geography | **4/4**; PH **2/2**, international **2/2** | **3/4**, both geographies |
| Actionable misses | **0 never collected; 0 outside top five** | — |
| Geography coverage | **2/2** | 2/2 |
| Explicit topic coverage in the two Upcoming shortlists | **2/3: AI and general IT** | 3/3 |
| Verified free options | **4**: Global AI, Build Your First AI App, MLH, Ryze | At least 1 |
| Primary event/organizer-designated signup links | **13/13 Upcoming cards; 10/10 first-five cards** | Every shown opportunity |
| Original evidence replays verified | **0/4; all 4 unverified** | 4/4 |

Cybersecurity is represented by x3CTF in **Watchlist**, with unknown signup. That earns discovery credit but does not establish a cybersecurity opportunity in the two Upcoming shortlists. **Overall acceptance is not a pass**, despite both recall thresholds passing: strict shortlist topic coverage remains incomplete, the four original evidence replays remain unverified, and LaunchPad’s visible title repeats a prize claim that conflicts with its own primary-page prize section.

## Separate field judgments

**K** = correct known fact supported by saved primary evidence. **U** = appropriately unknown. **M** = a known fact is missing; no false value is substituted. No incorrect value was confirmed in these seven requested field categories after final fixes; missing known facts remain explicitly marked. This is **not** an unrestricted zero-factual-error or full trust pass: the visible LaunchPad title retains unresolved conflicting prize copy.

| Reference | Organizer URL | Manila dates | Registration cutoff | Submission cutoff | Price | Eligibility | Signup |
|---|---|---|---|---|---|---|---|
| DevFest Manila | K | K | U | U | K: paid, amount unknown | K | K: waitlist |
| Foundry workshop | K | K | U | U | U | M: laptop omitted | U |
| AWS Davao/Mindanao | K: chapter equivalent | K | U | U | M: paid tiers not reached | K | U; advertised ticket route M |
| Safe AI Demo Day | K | K | U | U | U | K: public vs fellow tickets separate | K: approval required |
| PHPxCebu AI event | K | K | U | U | U | K | K: open |
| MLH Open Source Week | K | K | U | U | K: free | K, minor condition retained | K: open; account required |
| Global AI Builder’s Challenge | K | K | U | K: Nov 29, 07:00 PHT | K: free | M: solo/teams up to six omitted | K: open |
| x3CTF | K | K | U | U | U | K: individual/team; PH terms unconfirmed | U |

The GDG and AWS pages now supply explicit offset timestamps, stronger than the reference's date-only observation; the Manila calendar dates agree. MLH's end converts to **December 11, 02:00 PHT**. Global AI started before the window and qualifies through its **November 29, 07:00 PHT submission cutoff**. No event end was relabeled as a registration deadline. An intermediate UI defect hid AI submission cutoffs despite storing them correctly; the generic display fix is now verified in the final DOM. Global AI shows **“Submission deadline: Nov 29, 2026, 7:00 AM PHT”** and separately **“Registration deadline: Unknown”**; Build Your First AI App and LaunchPad likewise display their distinct known submission cutoffs.

Unknown fees on Luma/Meetup/GDG are retained even when platform metadata defaults to zero. DevFest Manila's explicit paid-ticket/waitlist notice takes precedence over its platform zero-price offer. AWS's captured chapter page does not state price or show a current signup route: the display is honest about that captured evidence, but the reference-known PHP199/289/349 tiers and advertised ticket route remain uncollected facts.

## Extras, duplicates and remaining gaps

These editions are outside the eight-row denominator. Their primary pages, exact edition, qualifying date and geography were checked independently from saved responses.

| Extra | Verified Manila schedule / qualifying cutoff | Fee / signup | Remaining limitation |
|---|---|---|---|
| AI Unwrapped: Agents, Data & Intelligence | Dec 10, 13:00–17:00; Makati hybrid | Fee unknown; signup unknown | Earlier false “open” inference from chat-only controls is corrected. Its live capture is not substituted for the original replay input. |
| DevFest Cebu 2026 | Nov 29, 13:00–19:00; PH in person | Fee unknown; signup unknown | Disabled Get tickets control does not establish availability. Student invitation is now retained. |
| Build Your First AI App | Started Oct 28, 00:30; submission Nov 28, 06:00 | Explicitly free; Join hackathon open | Student and local age-of-majority restrictions retained. Separate signup cutoff unknown. |
| LaunchPad Hacks | Started Oct 16, 15:45; submission Dec 5, 06:00 | Fee unknown; Join hackathon open | Source title says “580k In Prizes!” while its prize section says $300. The conflicting prize claim remains in the visible title without an uncertainty label. This is an unresolved trust gap; no award amount is independently verified. |
| Ryze Hacks 2026 | Dec 10, 16:00–Dec 18, 15:45 | Explicitly free; Join hackathon open | Ages13–22/students retained; team maximum four omitted. Separate submission cutoff stays unknown. |
| FRONTIER//26 | Dec 4, 13:00–Dec 12, 12:45 | Fee unknown; enabled Join hackathon | Primary source supports worldwide students13+; separate registration/submission cutoffs unknown. Final API and browser card match the primary schedule, age/student restrictions and enabled join route. It appears at international Upcoming #6. |

Ryze's visible Dec10–17 date range has no timezone; its explicit offset metadata converts the end to Dec18 in Manila. That unzoned local range does not establish a contradictory instant, and no timezone was invented for it.

No duplicate benchmark or extra editions were found. The first attempted duplicate replay was **not idempotent in row count**: 18→19 events and 21→22 announcements after a previously captured FRONTIER page entered the work budget; Safe AI also accumulated redundant revisions. That failed check is preserved as `offline-duplicates.json`. After deterministic traversal was fixed, `offline-stability.json` preserved **19/19 event IDs and first-seen timestamps, 22/22 announcement IDs and first-seen timestamps, and zero new event IDs**. Revisions still changed **33→36** (one evidence-quote improvement and two Safe AI source-payload revisions). The final display-cleanup replay likewise preserved 19/22 and first-seen values, with revisions **36→43** (five summary updates plus two Safe AI revisions). The result passes duplicate-edition/first-seen checks, while redundant Safe AI revision churn remains a separate gap.

Remaining known facts to improve are the AWS organizer ticket-page handoff, Foundry's laptop requirement and the two Devpost team-size limits. A dated cyber opportunity with verified current participation is still absent from the Upcoming shortlists. DICT/NCR remains unverified; other-region HackForGov leads do not establish the NCR edition/round.

## Original four evidence replays

Each final replay process received **only the unchanged `.replay[i].input`**, under network isolation with the reference/expectations hidden. The existing page adapter needs HTML; these bundles contain notes only. Verbatim text-extractor diagnostics returned no announcement, which is not a passing null/unknown field assertion.

| Replay | Expected | Actual | Verdict |
|---|---|---|---|
| AI Unwrapped | Price unknown | No page-adapter output; raw HTML absent | Unverified |
| niteCTF | Registration deadline null | No page-adapter output; raw HTML absent | Unverified |
| Devpost Manila midnight | Submission Jan12 2027, 00:00+08:00; registration deadline null | No page-adapter output; raw HTML absent | Unverified |
| CISO Philippines | Paid; PHP55,367 end-user / PHP110,795 vendor; student rate unknown | No page-adapter output; raw HTML absent | Unverified |

Saved-response parser regressions and new live captures are useful additional tests but do not replace these original four replays. Uncaptured offline requests are reported by phase: refinement lacked Bluesky `getPosts` and `hack312.devpost.com`; the failed duplicate replay lacked Bluesky `getPosts` and Luma `9mnmcshx`; the stable and final display replays lacked only Bluesky `getPosts`. Those checks remain unverified rather than successful zero-match reads. Original benchmark denominators stay **8 and 4**.

## Source completeness and leakage boundaries

The original combined baseline still contained a pre-existing AWS individual event URL. That leakage is disclosed in its baseline audit; the active entry was excluded from improved discovery inputs. The improved source configuration contains **zero exact reference titles and zero individual reference event URLs**. Discovered search results and subsequent event fetches are trace outputs, not organizer seeds. This known-reference iteration does not restore or replace the original blind score.

The improved live collection had **15 ok, 2 partial, 2 blocked, 1 policy-restricted and 7 disabled sources**. The final offline report has **14 ok, 3 partial, 2 blocked, 1 policy-restricted and 7 disabled** because a retained Bluesky post recheck lacked saved input. **Seven successful sources had zero accepted matches**: HackTheNorth, UP ACM, PUP announcements, PUP news, Luma Manila, Cyber404 news and Cisco NetConnect’s Luma calendar. DICT and NCERT were blocked by robots-check HTTP403; ROOTCON’s website was excluded by its extraction policy. These are not successful zero-match checks.

CTFtime’s two directory API reads succeeded, but primary verification was incomplete: one verified edition, six unverified edition/schedule checks, two unreadable pages, two JavaScript-only pages, three fetch errors (including a timeout), and one blocked fetch. Public search’s fixed detail budget left unvisited leads; its source status remains partial. Never drop these leads or blocked sources from the benchmark denominator.


## Validation and remaining operational gaps

- **628 backend tests passed** in 17.64 seconds. After the final display cleanup, **56 Devpost tests passed** again. These include date-only Manila rollover, already-started contests qualifying through a submission cutoff, conflicting evidence, unknown/default price handling, eligibility restrictions, primary CTF edition matching, normal API placement and cold/warm search traversal.
- **TypeScript and Vite build passed.** The build was written to temporary storage; the repository's existing built site was untouched.
- **13 browser tests passed** in 32.2 seconds, including approval/free ordering, PH hybrid tickets, Watchlist, keyboard/mobile behavior, and separate AI/cyber submission deadlines crossing the next Manila day. Actual final browser capture reported **zero page errors and no mobile horizontal overflow**.
- **Zero duplicate event editions** in the final 19-record database. The stable replay preserved all **19 event IDs/first-seen timestamps** and **22 announcement IDs/first-seen timestamps**. Redundant Safe AI revisions remain because calendar and search observations update the same announcement with different provenance. This is not a claim of byte-identical DB replay or zero revision churn.
- The search source still has an **80-page budget**, including ownership checks. Its report records **70 unvisited leads plus one verification deferred at the budget boundary**. These are not successful negative checks. A malformed Devpost primary record is also explicitly unverified in the final parser, not zero matches.
- Separate DICT/NCR research did not establish a current HackForGov NCR edition/round or registration route. Government source access was blocked; historical or other-region dates were not transferred to an NCR opportunity.
- The baseline native search quota failure, incomplete earlier research-query retention, three distinct uncaptured offline endpoints across phases, and original replay input limitations remain disclosed. No paid API, logged-in Facebook scraping, production deployment, monitor, or scheduled wait was introduced.

The 56 benchmark field judgments comprise **31 correct-known, 22 appropriately-unknown, three missing-known and zero incorrect values in the seven requested categories**. That does not erase AWS's missing advertised ticket route, Ryze's missing team limit, or LaunchPad's visible prize-copy conflict. The full trust gate remains incomplete.

The smallest next discovery change justified by these results is a **bounded follow of an already-verified organizer page's explicit ticket/registration link**, retaining separate field evidence and failures. The AWS chapter-to-ticket handoff is the demonstrated miss: it would recover advertised prices without treating a blocked form as open registration. This report does not enable that follow-up or claim it would solve the separate cybersecurity/signup and replay-evidence gaps.

## Evidence index

- [Exact final normal API](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/site-api.json)
- [Actual DOM card order and text](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/student-visible-order.json)
- [Final temporary DB](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/final.sqlite3)
- [Final database export](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/database-results.json)
- [Final collector report (offline refinement)](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/collector-report.json)
- [Improved first live collector report](/tmp/ctfinder-iteration-20261122-b6akcp1p/improved/collector-report.json)
- [Improved timestamped fetch log](/tmp/ctfinder-iteration-20261122-b6akcp1p/improved/fetch-log.jsonl)
- [Complete public search output manifest](/tmp/ctfinder-iteration-20261122-b6akcp1p/public-search-manifest.json)
- [Discovery provenance and leakage disclosure](/tmp/ctfinder-iteration-20261122-b6akcp1p/discovery-provenance.json)
- [Failed first duplicate replay](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/offline-duplicates.json)
- [Stable replay](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/offline-stability.json)
- [Final display-cleanup replay](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/offline-final-display.json)
- [Complete evaluator score and field evidence](/tmp/ctfinder-iteration-evaluator-20261122-3n0k3b27/final-score.json)
- [Original input-only replay attempts](/tmp/ctfinder-iteration-evaluator-20261122-3n0k3b27/final-original-replays.json)
- [Final backend test log](/tmp/ctfinder-iteration-20261122-b6akcp1p/backend-tests-final.txt)
- [Final browser test log](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/browser-tests.txt)
- [Final build log](/tmp/ctfinder-iteration-20261122-b6akcp1p/frontend-build-final.txt)
- [Final code hashes](/tmp/ctfinder-iteration-20261122-b6akcp1p/final-code-hashes.json)
- [Protected-file integrity check](/tmp/ctfinder-iteration-20261122-b6akcp1p/integrity-check.json)
- [Desktop screenshot](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/student-desktop.png)
- [Mobile screenshot](/tmp/ctfinder-iteration-20261122-b6akcp1p/final/student-mobile.png)

These evidence links point to local temporary artifacts, not production data. The immutable improved first-run snapshot contains 14 events; the final offline-refined snapshot contains 19. Earlier 18-record and pre-display-fix views are preserved under explicit filenames in `final/`; they must not be substituted for the final card capture.

## Exact final card text

The blocks below reproduce the visible collapsed cards captured from the normal student UI. Links are listed after each block. These are observed output, not discovery inputs.

<details>
<summary>PH · upcoming #1 — AI: Growing Up and Leaving Home</summary>

```text
Upcoming
In person
AI: Growing Up and Leaving Home

Prince John Santillan

Registration open
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 28, 2026, 10:00 AM PHT
Event ends
Nov 28, 2026, 2:00 PM PHT
Region
Region VII — Central Visayas
Who can join
Public ticket options are listed; check their current availability.
Topic
Artificial intelligence (AI)
Price
Unknown
Standard public tickets
Standard

Registration open

Price: Unknown · Deadline: Unknown

Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://luma.com/rl9jbxgv)
- [Registration](https://luma.com/rl9jbxgv)

</details>

<details>
<summary>PH · upcoming #2 — Safe AI Philippines AI Governance Accelerator Cohort 2 - Demo Day</summary>

```text
Upcoming
Hybrid
Safe AI Philippines AI Governance Accelerator Cohort 2 - Demo Day

Safe AI Philippines

Applications open · approval required
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 29, 2026, 3:00 PM PHT
Event ends
Nov 29, 2026, 6:00 PM PHT
Region
NCR
Attendance
Onsite — Quezon City · Online
Who can join
Standard public tickets are available; organizer approval required. Restricted ticket requirements apply only to their named tickets.
Topic
Artificial intelligence (AI)
Price
Unknown
Standard public tickets
Standard - Online

Applications open · approval required

Price: Unknown · Deadline: Unknown

Standard - Onsite

Applications open · approval required

Price: Unknown · Deadline: Unknown

Restricted tickets
Accelerator Fellow - Online

Those who completed the Training Phase and attending online

Applications open · approval required

Price: Unknown · Deadline: Unknown

Accelerator Fellow - Onsite

Those who completed the Training Phase and attending onsite

Applications open · approval required

Price: Unknown · Deadline: Unknown

Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://luma.com/6ufidrj7)
- [Registration](https://luma.com/6ufidrj7)

</details>

<details>
<summary>PH · upcoming #3 — Hands-on with Foundry Agents and Foundry IQ</summary>

```text
Upcoming
Hybrid
Hands-on with Foundry Agents and Foundry IQ

Global AI Manila

Registration unconfirmed
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 27, 2026, 2:30 PM PHT
Event ends
Nov 27, 2026, 5:30 PM PHT
Region
Philippines
Attendance
Onsite · Online
Who can join
All attendees who register via Meetup must also complete the Microsoft registration form to be sent to your inbox least 3 days before the event to secure building access and finalize their seat reservation. Whether you're a developer, AI practitioner, IT professional, or simply exploring agentic AI, you'll leave with practical experience and a better understanding of how Microsoft Foundry can help you move from AI experimentation to working agent solutions.
Topic
Artificial intelligence (AI)
Price
Unknown
Official announcement
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://www.meetup.com/globalaiphilippines/events/317284119/)

</details>

<details>
<summary>PH · upcoming #4 — DevFest Manila 2026 Main Stage</summary>

```text
Upcoming
In person
DevFest Manila 2026 Main Stage

Google Developer Groups

Waitlist
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 28, 2026, 9:00 AM PHT
Event ends
Nov 28, 2026, 6:00 PM PHT
Region
NCR
Attendance
Onsite
Who can join
Open to Everyone—Devs and Non-Devs Alike! DevFest is built for anyone passionate about technology and innovation. Whether you are a software engineer, product manager, designer, student, tech entrepreneur, or simply curious about the future of tech—you belong here. No matter your background or skill level, you will find inspiration, knowledge, and community.
Topic
General IT
Price
Paid · amount not announced
Account
Unknown
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://gdg.community.dev/events/details/google-gdg-manila-presents-devfest-manila-2026-main-stage/)
- [Registration](https://gdg.community.dev/events/details/google-gdg-manila-presents-devfest-manila-2026-main-stage/)

</details>

<details>
<summary>PH · upcoming #5 — AWS Student Community Day Davao</summary>

```text
Upcoming
In person
AWS Student Community Day Davao

AWS SBG at University of the Philippines - Mindanao Campus

Registration unconfirmed
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 28, 2026, 9:00 AM PHT
Event ends
Nov 28, 2026, 5:00 PM PHT
Region
Region XI — Davao
Attendance
Onsite
Who can join
The conference provides hands-on workshops, keynotes, and networking to equip student builders with practical AWS skills and connect them with career pathways across cloud, AI, and software engineering.
Topic
General IT
Price
Unknown
Account
Unknown
Official announcement
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://www.meetup.com/aws-sbg-at-university-of-the-philippines-mindanao-campus/events/316992979/)

</details>

<details>
<summary>PH · upcoming #6 — DevFest Cebu 2026</summary>

```text
Upcoming
In person
DevFest Cebu 2026

Google Developer Groups

Registration unconfirmed
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Nov 29, 2026, 1:00 PM PHT
Event ends
Nov 29, 2026, 7:00 PM PHT
Region
Philippines
Attendance
Onsite
Who can join
Whether you're a developer, student, IT professional, entrepreneur, or tech enthusiast, DevFest Cebu welcomes you to take part in the event and engage with fellow members of the local tech community.
Topic
General IT
Price
Unknown
Account
Unknown
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://gdg.community.dev/events/details/google-gdg-cebu-presents-devfest-cebu-2026/)
- [Registration](https://gdg.community.dev/events/details/google-gdg-cebu-presents-devfest-cebu-2026/)

</details>

<details>
<summary>PH · upcoming #7 — AI Unwrapped: Agents, Data & Intelligence</summary>

```text
Upcoming
Hybrid
AI Unwrapped: Agents, Data & Intelligence

Global AI Manila

Registration unconfirmed
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Dec 10, 2026, 1:00 PM PHT
Event ends
Dec 10, 2026, 5:00 PM PHT
Region
NCR
Attendance
Onsite · Online
Who can join
Whether you're building AI solutions today or simply want to understand where agents, data and enterprise AI are heading, this is a chance to
Topic
Artificial intelligence (AI)
Price
Unknown
Official announcement
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://www.meetup.com/globalaiphilippines/events/317510987/)

</details>

<details>
<summary>International online · upcoming #1 — Build Your First AI App</summary>

```text
Live now
Online
Build Your First AI App

Yasir Insights

Registration open
Registration deadline
Unknown
Submission deadline
Nov 28, 2026, 6:00 AM PHT
Event starts
Oct 28, 2026, 12:30 AM PHT
Event ends
Nov 28, 2026, 6:00 AM PHT
Region
International online
Attendance
Online
Who can join
Above legal age of majority in country of residence; Students only; Companies/professional organizations excluded from participation; All countries/territories, excluding standard exceptions (Brazil, Crimea, Cuba, Iran, North Korea, Quebec, Russia); This hackathon is designed for eligible students and beginner developers who want to gain practical experience building AI applications.
Topic
Artificial intelligence (AI)
Price
Free
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://build-your-first-ai-app.devpost.com/)
- [Registration](https://build-your-first-ai-app.devpost.com/register?flow%5Bdata%5D%5Bchallenge_id%5D=31907&flow%5Bname%5D=register_for_challenge)

</details>

<details>
<summary>International online · upcoming #2 — Global AI Builder’s Challenge</summary>

```text
Live now
Online
Global AI Builder’s Challenge

Refactor The World

Registration open
Registration deadline
Unknown
Submission deadline
Nov 29, 2026, 7:00 AM PHT
Event starts
Nov 21, 2026, 4:00 PM PHT
Event ends
Nov 29, 2026, 7:00 AM PHT
Region
International online
Attendance
Online
Who can join
Ages 13+ only; Students only; Companies/professional organizations excluded from participation; All countries/territories, excluding standard exceptions (Brazil, Crimea, Cuba, Iran, North Korea, Quebec, Russia)
Topic
Artificial intelligence (AI)
Price
Free
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://global-ai-builders-challenge.devpost.com/)
- [Registration](https://global-ai-builders-challenge.devpost.com/register?flow%5Bdata%5D%5Bchallenge_id%5D=31826&flow%5Bname%5D=register_for_challenge)

</details>

<details>
<summary>International online · upcoming #3 — Global Hack Week: Open Source Week</summary>

```text
Upcoming
Online
Global Hack Week: Open Source Week

Major League Hacking

Registration open
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Dec 4, 2026, 11:00 PM PHT
Event ends
Dec 11, 2026, 2:00 AM PHT
Region
Worldwide
Who can join
Worldwide, including the Philippines. Minors (Between 13-18); Working Professionals; Students - University; Students - Secondary/High School; Students - Other. Under 18s need a parent’s permission.
Topic
General IT
Price
Free
Account
Required to register
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://events.mlh.com/events/15199-global-hack-week-open-source-week)
- [Registration](https://events.mlh.com/events/15199-global-hack-week-open-source-week)

</details>

<details>
<summary>International online · upcoming #4 — Ryze Hacks 2026</summary>

```text
Upcoming
Online
Ryze Hacks 2026

ryze

Registration open
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Dec 10, 2026, 4:00 PM PHT
Event ends
Dec 18, 2026, 3:45 PM PHT
Region
International online
Attendance
Online
Who can join
Ages 13 to 22 only; Students only; Companies/professional organizations excluded from participation; All countries/territories, excluding standard exceptions (Brazil, Crimea, Cuba, Iran, North Korea, Quebec, Russia)
Topic
Artificial intelligence (AI)
Price
Free
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://ryzehacks.devpost.com/)
- [Registration](https://ryzehacks.devpost.com/register?flow%5Bdata%5D%5Bchallenge_id%5D=32057&flow%5Bname%5D=register_for_challenge)

</details>

<details>
<summary>International online · upcoming #5 — LaunchPad Hacks (580k In Prizes!)</summary>

```text
Live now
Online
LaunchPad Hacks (580k In Prizes!)

Hack4TodayOrg

Registration open
Registration deadline
Unknown
Submission deadline
Dec 5, 2026, 6:00 AM PHT
Event starts
Oct 16, 2026, 3:45 PM PHT
Event ends
Dec 5, 2026, 6:00 AM PHT
Region
International online
Attendance
Online
Who can join
Above legal age of majority in country of residence; Students only; Companies/professional organizations excluded from participation; All countries/territories, excluding standard exceptions (Brazil, Crimea, Cuba, Iran, North Korea, Quebec, Russia)
Topic
Artificial intelligence (AI)
Price
Unknown
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://launchpad-hacks.devpost.com/)
- [Registration](https://launchpad-hacks.devpost.com/register?flow%5Bdata%5D%5Bchallenge_id%5D=31773&flow%5Bname%5D=register_for_challenge)

</details>

<details>
<summary>International online · upcoming #6 — FRONTIER//26</summary>

```text
Upcoming
Online
FRONTIER//26

LoveHack

Registration open
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Dec 4, 2026, 1:00 PM PHT
Event ends
Dec 12, 2026, 12:45 PM PHT
Region
International online
Attendance
Online
Who can join
Ages 13+ only; Students only; Companies/professional organizations excluded from participation; All countries/territories, excluding standard exceptions (Brazil, Crimea, Cuba, Iran, North Korea, Quebec, Russia); Open to aspiring innovators worldwide, FRONTIER//26 is an opportunity to turn curiosity into ideas and ideas into something tangible.
Topic
Artificial intelligence (AI)
Price
Unknown
Official announcement
(opens in a new tab)
Registration
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://frontier26.devpost.com/)
- [Registration](https://frontier26.devpost.com/register?flow%5Bdata%5D%5Bchallenge_id%5D=32093&flow%5Bname%5D=register_for_challenge)

</details>

<details>
<summary>PH · watchlist #1 — ROOTCON 20 CTF · Qualifier</summary>

```text
Schedule TBA
Format unconfirmed
ROOTCON 20 CTF · Qualifier

ROOTCON

Registration unconfirmed
Registration deadline
Not announced
Competition starts
Schedule TBA
Competition ends
Not confirmed
Region
Unspecified
Who can join
Eligibility not announced. Check with the organizer.

The latest dated announcement is over 45 days old. Current participation and completion are unconfirmed.

Schedule TBA. This listing does not confirm that registration is open.

Watchlist: no confirmed start or cutoff in the next 45 days, or recurring signup is unverified.

Official announcement
(opens in a new tab)
Posted Sep 19, 2026
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://bsky.app/profile/did:plc:ydimusmod455q2xhqngepksy/post/3mvtlb6qlyc24)

</details>

<details>
<summary>International online · watchlist #1 — x3CTF 2026</summary>

```text
Upcoming
Online
x3CTF 2026

x3CTF

Discovered through CTFtime; matching edition and UTC schedule verified on the organizer page. Unstated registration and submission cutoffs remain unknown.

Registration unconfirmed
Registration deadline
Unknown
Submission deadline
Unknown
Event starts
Dec 5, 2026, 2:00 AM PHT
Event ends
Dec 7, 2026, 2:00 AM PHT
Region
Worldwide
Who can join
You are allowed to play either individually or with a team. Philippine-specific eligibility terms are not stated. CTFtime labels entry Open.
Topic
Cybersecurity
Price
Unknown

Watchlist: no confirmed start or cutoff in the next 45 days, or recurring signup is unverified.

Official announcement
(opens in a new tab)
Posted Unknown
First seen Nov 22, 2026
Sources & updates
1
```

- [Official announcement](https://x3c.tf/)

</details>

