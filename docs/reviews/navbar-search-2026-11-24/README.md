# Navbar search and full-page cork review

November 24, 2026 · Asia/Manila. Local work, not published.

The first view places search in the navbar and keeps both dropdowns, the first event card and selected notice title visible at 1366×768. The list occupies slightly more than half the working area. Phone layouts retain both filters and all four tabs, then open the selected notice at the available width.

Reference: [CommunIT-navbar-search.html](https://chatgpt.com/library?file_id=libfile_48057d0b3e70819183058a5678963a0a&account_id=personal). The supplied local HTML was rendered and inspected; production uses React components and canonical CSS, not its demo records, bundled app, DOM-reparenting scripts or accumulated overrides. The cork JPEG in `frontend/src/assets/cork.jpg` and the two decorative stick-figure SVG drawings come from that reference. Notes reveal below the board so they occupy no first-screen space and cannot cover controls.

## Screenshots

These use the normal events API with the existing isolated saved preview, not fixture records. Snapshot freshness is displayed as recorded; the screenshots do not assert that every event was freshly verified.

| View | Screenshot |
| --- | --- |
| Desktop arrival · 1366×768 | [desktop.png](desktop.png) |
| Phone board · 390px | [mobile.png](mobile.png) |
| Phone selected notice · 390px | [mobile-notice.png](mobile-notice.png) |
| Narrow phone board · 320px | [narrow.png](narrow.png) |
| Narrow phone selected notice · 320px | [narrow-notice.png](narrow-notice.png) |

## Verification

- Production TypeScript/Vite build passed. Output is under ignored `data/navbar-layout/build/`; installed `frontend/dist` was not replaced.
- **All 80 Chromium browser tests passed in 2.4 minutes** after the final narrow-tab fix. Ten new checks and 70 retained/updated checks cover first-screen geometry, 390/320px readability and multi-digit tab counts, combined search/interest/attendance/section filtering, empty/clear behavior, section keyboard navigation, desktop list stability, mobile Back restoration, long title/address/date/deadline/fact rules, native scrollbar pointer/wheel/keyboard/touch reveal and one-second idle hiding, reserved text width, forced colors and reduced motion.
- `git diff --check` and all local Markdown file links in the changed guidance/review documents passed. [Verification receipt](verification.json).
- Saved-data rendering at 1366×768, 390px and 320px was inspected for first-screen content, natural wrapping and horizontal overflow. No page errors were observed.
- The previous ongoing-event fix and its isolated backend tests remain separate local work; no backend changes were needed for this layout.

Reproduce with the isolated setup in [RUN_LOCAL.md](../../../RUN_LOCAL.md), then run from the repository root:

```bash
npm --prefix frontend run build -- --outDir ../data/navbar-layout/build
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run test:e2e
```

The final full-suite log is `data/navbar-layout/verified-playwright.log`; its browser artifacts are in `data/navbar-layout/verified-test-results/`. The final build log is `data/navbar-layout/build.log`. Detailed logs, fixture browser artifacts and reference captures are retained under ignored `data/navbar-layout/`. The tested local dependency environment was reused.

## Limits and publication

Chromium was used, including emulated touch, forced colors and reduced motion. Firefox, WebKit, physical touch hardware and assistive-technology sessions were not run. External organizer pages were not reverified. No live collection, main database access or deployment occurred.

[PR_DESCRIPTION.md](PR_DESCRIPTION.md) is ready for a future draft PR. The user said **dont push yet**, so no commit/push or new remote PR was made; the existing PR was not changed. Local changes remain on `feat/pinned-notice-redesign`.

## Idle gutter follow-up · November 24, 2026

The paper background and border now extend across the reserved scrollbar gutter, removing the separate idle strip. The production build and nine targeted Chromium checks passed after this CSS change; the 80-test result and screenshots above describe the preceding full-layout checkpoint. New idle/active and phone captures are under ignored `data/notice-gutter/`. Native scrolling, stable width, mobile Back and forced-colors support were rechecked. No commit or push.
