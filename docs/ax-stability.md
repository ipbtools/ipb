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

Simulator probes are external experiments, not a new product backend. The earlier
implementation stage excluded phone operations. On November6 the user explicitly
requested a broader physical App matrix and selected12mini; that authorizes foreground
App/page setup and AX sampling on that device.13Pro is assigned to the concurrent
PocketAgent task and remains untouched. AX-only results do not close the supported
HID/media smoke matrix. Keep legacy deep nils explicitly open.

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

Opus5.5 accepts the complete implementation58e5c32 without blocking findings. Its
wording suggestion is incorporated: traversal/options are the same, while separate
observations may differ. The isolated package passes layout/signature/checksum and
extracted startup checks. Host results apply to this unchanged production source;
the subsequent checkpoint changes documentation only.

Delivery is [PR#15](https://github.com/ipbtools/ipb/pull/15).
[CI run42077704751](https://github.com/ipbtools/ipb/actions/runs/42077704751) passes
native builds, host regressions, package verification, precompiled Homebrew install/test
and product hashes, and artifact upload. The first run's homebrew/core clone timeout
does not recur; no workflow change was needed. The dated verification record contains
the exact revision and package reference. Opus's delivery review preserves source ACCEPT
and confirms the evidence boundary. Default full nil and physical acceptance remain open;
merge requires the supported gate or an explicit maintainer exception.

## Expanded physical App matrix (2026-11-06)

Purpose: determine whether omitting2025 improves real accepted-snapshot success,
not merely query duration. This is a follow-up validation of the58e5c32 baseline;
production code, timeouts, graph budgets and action guards stay fixed.

Device: explicit12mini CoreDevice UUID1D533177-5153-5A0C-9102-8D0A8ADDAEFB,
iPhone13,1/iOS27.0/24A437, wired and unlocked, macOS27.2/26B123,
Xcode27.2/27B52. The user confirmed this allocation. Initial screen is Home.
13Pro belongs to the live PocketAgent latency comparison; other devices/sims are excluded.

Predeclared broad phase:18 launchable apps, each in its observed landing state:
Settings, Calculator, Safari, AppStore, Files, Calendar, Clock, Notes, Reminders,
Maps, Weather, Books, Shortcuts, Music, Stocks, Translate, Bitwarden and PocketAgent.
These cover system lists/grids, WebKit, dynamic/canvas views, forms and third-party
login/SwiftUI surfaces. App names alone do not prove framework internals; record actual
onboarding/permission/empty/content state from captures. A launch/setup refusal is a
matrix cell result, not silently substituted by another App or counted as a native nil.

Three arms use real isolated CLI installs: main8c227a1 full (before),58e5c32 full
(compatibility control),58e5c32 explicit core (opt-in after). Each App/state gets6
attempts per arm, ordered by the six permutations of these arms (18 total), with a
fixed3s inter-attempt gap and fresh one-shot USB/DTX connection. Rotate the first
permutation by App ordinal; record ordinal, previous arm and actual process-exit gap.
Confirm PID via fresh process inventory before each attempt. Use screenshots, lock
state and centre hit-PID checks before/after each cell, plus non-AX lock state between
permutation blocks. A failed state check or changed PID marks all attempts since the
last good foreground check state-invalid, retained separately without replacement or
inclusion in within-state success denominators. Stop on lock. Spacing is not a
native-drain guarantee; report carryover strata and first-after-setup separately. Do not retry failed measurements.
Store stdout/stderr, exit/status, wall time and query/snapshot timing outside Git.

Accepted success requires rc0 plus a validated complete schema2 tree, matching device
and explicit PID, correct profile metadata and closed connection/tunnel. Count native
nil, type2 semantic timeout, other semantic/global timeout, graph/archive budget,
identity/selection/transport and cleanup failures separately. Report per-App/state
numerators/denominators and latency; success-only timing never hides failed attempts.
No aggregate across heterogeneous Apps is a universal reliability estimate.

Then add observed reachable search/keyboard, secondary-page, Web-content and overlay
states using reversible navigation without sending messages or editing user content.
A natural failure in any arm symmetrically selects a cell for a separate, pre-fixed
30 attempts per arm and three independent state re-entries (rotating the first arm).
Do not pool selection-phase observations into confirmation rates; if a state cannot be recreated, report that explicitly.
Read-only old/new locate samples use actual unique observed selectors on representative
states. Whole-tree3002 comparison requires a separately labelled read-only physical
experiment; product input is not a read-only snapshot command and is not auto-replayed.

Opus reviews the matrix before the broad run and the actual findings afterward. Reuse
the current tested install; no new product test infrastructure or device app is added.
Use the existing compact_observe validator uniformly for all successful observations.
Old full versus new full is a compatibility/noise control, old full versus opt-in core
is a requested-attribute tradeoff, and only old/new locate is the same-default-path
before/after comparison. Report graph-count/path drift on adjacent successful samples.
Activate with devicectl process launch --activate without --terminate-existing.
Record shared-host load; the13Pro task can affect host timing even on a different phone.
Scripts and detailed personal AX/screenshot evidence stay outside Git; this plan and
verification.md retain only condensed, verified findings and artefact references.
