# AX snapshot workload and explicit core observations

Branch: `codex/ax-stability`. Base: main `8c227a1` (v0.6.0).
The separate Duo branch was rebased onto that main; this PR contains AX work only.

## Problem and evidence

Safari simulator application snapshots can spend several seconds computing native
visibility2025 across visible/hidden windows. An external client receives error0/nil
around3s while native computation can finish later. Removing2025 produced the same
664 ordered path records/identities and other fields in0.326s in one captured state.
That graph exceeds the product's512-record limit, so this is workload evidence,
not an already demonstrated product failure-to-success case. See verification.md's
November5/6 records. Exact intermediate deadline ownership remains unknown.

Locate/wait/press/input request2025 without consuming it. Their existing target
identity, value, live state/frame and exact-hit guards must remain unchanged.
Default deep dumps, scroll and alert operations consume native visibility and keep
their current requests. Root-only3002 is rejected as a shortcut: retained samples
have truncated children and lack responder traits/value.

## Design

- Derive one core attribute list from the existing full list by excluding2025.
  Use it for locate/wait/press and for input with whole-tree3002 added. Keep the
  structural validation, action guards, timeouts, graph budgets and no-replay
  behavior unchanged. Project only requested native attributes in the parser.
- Add opt-in `ui --deep --native-profile core`; `full` remains the default and
  preserves its current output. Profile selection is valid only for deep dumps.
  Core keeps complete structure/geometry/text, omits native node.visible, and adds
  `nativeAttributeProfile:"core"`, `nativeVisibility:"not-requested"`. Extra server
  visibility is not published as requested core state. Later full-state values
  remain separately attributed under supplementalAX.
- MCP observe accepts optional `nativeProfile` with the same full/core values.
  Its adapter validates and propagates core provenance; incomplete/contradictory
  metadata or request/result profile mismatch fails before a successful observe
  can clear isolation. Existing callers keep the full profile. There is no fallback.
- This provides a cheaper explicit observation path; it does not claim to cure all
  legacy full-profile nils, oversized graphs or identity changes after scroll.

## Stages and supervision

1. **Evidence and design:** use only task-owned simulator state, fixed-count
   independent full/core comparisons and core+3002 timing. Seek a<=512-record
   reachable failing state; distinguish empirical benefit from unverified scope.
   Opus reviews the concrete evidence and design before production edits.
2. **Unused-state queries:** implement operation-specific core requests; reproduce
   the nil contract through the existing host transport fixture and retain guards.
   Commit code, focused tests and confirmed verification; Opus checks this stage.
3. **Explicit observations:** add CLI/MCP core profile and provenance with matching
   help, completion, user/protocol documentation and existing-fixture regressions.
   Commit the complete implementation; Opus reviews the complete fixed diff.
4. **Delivery:** finish relevant host/package/CI checks, record their actual results,
   resolve confirmed findings, and open a PR. Do not merge or publish a release.

## Validation boundaries

Pin three observable contracts using the existing AX/MCP fixtures: expensive-state
failure versus successful cheap requests; unchanged pre-submit guards and one-shot
post-submit failures; honest core provenance with unchanged default output. Keep
tests compact and reuse existing negatives. No new phone app/test framework.

Simulator probes are external experiments, not a new product backend. No physical
device operation is authorized here; host/CI/simulator results cannot close the
supported physical smoke matrix. Keep legacy deep nils explicitly open.

## Current state

Stage1 cadcefa is accepted by actual Opus5.5 source review with no blocking finding.
Its existing-fixture regression failed before the production change; the integrated
implementation now passes91 AX,44 MCP,9 interface tests and the complete native host
gate. Stage2 implements the explicit CLI/MCP profile and provenance, requested/result
validation, help/completion and documentation. Its complete fixed diff is the first
complete implementation offered for review; later fixes retain this scope baseline.

Task-owned simulator9FE94853-1660-4DB1-98D8-C22A608CC76A shows lower cost within512
records, including core+3002, and the real captured responder passes the input resolver.
No natural nil was found in that clean state; later activations did not add scenes.
The simulator is now shut down. No physical-device acceptance is claimed.

Next delivery gates: Opus review of the complete committed implementation, isolated
package verification, PR and actual CI results. Legacy full nil remains open by design.
