# Historical documentation and verification

These artifacts describe earlier implementations and observations, not the current UI, running services or live-source availability. Use the [current handoff](../../PROJECT_CONTEXT.md) and [RUN_LOCAL](../../RUN_LOCAL.md) for current behavior and commands.

## Archived on November 24, 2026 (Asia/Manila)

| Previous location | Archived location | Preservation |
| --- | --- | --- |
| Superseded checkpoints in root `PROJECT_CONTEXT.md` | [November 23–24 handoff](project-context-2026-11-24.md) | Checkpoint prose and evidence paths retained; Markdown links rebased to the repository root. Includes the preceding uncommitted interest-label checkpoint. |
| `docs/verification.json` | [Initial verification](initial-verification-2026-11-21/verification.json) | Byte-identical November 21 run/verification dump. |
| `docs/desktop.png` | [Initial desktop screenshot](initial-verification-2026-11-21/desktop.png) | Byte-identical; kept beside its verification JSON. |
| `docs/mobile.png` | [Initial mobile screenshot](initial-verification-2026-11-21/mobile.png) | Byte-identical; kept beside its verification JSON. |

The JSON's relative screenshot filenames still resolve within its bundle. The [dated coverage report](../coverage.md) links to the relocated verification dump. Counts, source outcomes and screenshots have not been updated to resemble later UI results.

## Kept in place

- Frozen [November 22 prototype results](../prototype-iteration-2026-11-22.md), [November 23 benchmark report](../benchmark-2026-11-23.md), [benchmark traces](../benchmark-2026-11-23-results.json) and all other benchmark files keep their original paths, contents and scores. Existing historical references and hash comparisons depend on them.
- [Classification verification](../classification-verification.json) embeds the LearnPossible screenshot filenames; [UI verification](../learnpossible-ui-verification.json) repeats those relative names. The three `docs/learnpossible-ui-*.png` files and their reports remain together at their original locations rather than editing raw evidence to follow moves.
- Other discovery/source verification and research JSON remains in `docs/`. For example, [workflow source research](../workflow-source-research.json) records `docs/luma-verification.json` as an evidence path. Moving these files independently would break recorded provenance or require rewriting original evidence.
- Ignored `data/` snapshots/logs and absolute `/tmp` references were not moved, regenerated or added to Git. They may be missing in another checkout; historical reports do not guarantee their availability. No benchmark replay or source revalidation accompanied this cleanup.

Archived setup commands and machine-specific paths are retained only as historical provenance. Never start a backend or collector against an original benchmark database; use an isolated copy and inspect its configuration separately.
