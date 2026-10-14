# Native deep snapshots for `ipb ui`

Current branch: `codex/ax-native-snapshot`, based on `origin/main` (`74fb859`).
Deep snapshots and guarded element actions shipped in v0.3.0; this change separates
native observations from later supplementary AX reads.

## Problem and design

The ordinary AXChildren graph omits backing layout containers: the iPhone 13 Pro
Settings main page has 13 ordinary elements, whereas the independently verified
DevicesApp snapshot has 138 records at depth 20. Earlier request 2 / attribute 52
(native 95006) returned nil because its options lacked a nonempty array of numeric
native AX attributes. The former archive decoder also rejects that valid response
at its 100-level UID/container nesting limit.

Keep the existing paired USB userspace RSD, raw DTX channel zero, one outstanding
request and bounded cleanup. The native descendant snapshot alone supplies the deep
hierarchy, path occurrences, text and rectangles. `ui --deep` no longer walks ordinary
AXChildren or reconciles its separate generations with the snapshot. Preserve the
native root/PID, child counts, graph/archive budgets and selected PID/display checks.
Re-read the application handle to bracket the native observation; this checks identity,
not stable descendant geometry or an atomic generation. `atomic=false` remains explicit.
Ordinary `ui` retains its existing graph, Description-first reads and root signature checks.

Deep dumps use JSON schema 2 because supplemental state moves out of top-level node
fields. Ordinary dumps and hit-test/press keep schema 1. Deep `attributeSource` and
`attributePolicy` remain `native-snapshot`; optional state is stored under each node's
`supplementalAX`. Native fields are never replaced by later values. Native-only dumps
report `supplementalAX.status=not-requested`. `--deep --full-state` requests the existing
state/role fields once per unique native handle, after validating the primary snapshot.
Its separate summary records requested/completed counts and explicit failure context.
An individual supplemental failure stops further requests and returns nonzero; a complete
native tree may still be emitted only after successful cleanup. No request follows a
semantic timeout. Native failure, global cancellation/timeout or cleanup failure emits no
result. A supplementary response is a later observation, not snapshot-time or actionable
state; missing fields remain missing.

Decode keyed archives iteratively with independent byte/object/work/nesting budgets
and cycle rejection. Validate every native child array against its declared count and
the 512-record/depth-32 product limits. Nil, malformed/truncated snapshots and invalid
root/process/display checks fail without shallow fallback or a partial native tree.

## Element press and supplementary attributes

Default deep includes native hint2002 and visibility2025. `--deep --full-state` reads
AXP27/28/30/32/42/45/46/51 for every unique snapshot handle into a separate namespace.
The full-state cost and failures are explicit. AX focus/visibility do not claim XCTest
semantics; native visibility and later supplemental visibility can legitimately differ.
Never infer XCUI types from classes/traits.

`ui hit-test --point` returns the actual hit element with identity/display pre/post checks.
`ui press --identifier` resolves the displayed app and one fresh native handle, confirms
identifier/frame, requires known enabled/visible state and an exact frame-centre hit, then
rechecks PID/display and sends one type7/action5. Previous dump IDs are not action tokens.
No automatic replay/HID fallback is allowed. Native acceptance is separate from observed
UI effects; submitted/refused/accepted status survives outer timeout/cleanup and uses exit6
for failure after submission. Default `ui` remains read-only.

## Verification and delivery

Use maintained host regressions for nested UID archives, cycle/nesting/graph budgets,
numeric request options, duplicate paths, omitted/false fields, truncation, root
changes, notifications and cleanup. Build and install into an isolated prefix;
exercise source and installed `ui` on the allocated iPhone 13 Pro, including
Settings, Calculator and the previously problematic third-party title page.
Run AX smoke and the normal smoke gate where the environment permits, reporting
the supported macOS 27 / Xcode 27 gate separately from supplementary macOS 26.
Keep raw archives, screenshots and successful logs outside Git. Update protocol,
user guide and verification current state plus an append-only dated record.

## Status and open questions

PR #2 incorporates the independent review and current same-page/action work. Three paired
AX/XCTest/AX rounds on the 13 Pro match Calculator45/45, History99/99 and Settings171/171
ordered paths. Usable native rectangles match; SettingsCGRectNull stays unavailable rather
than becoming XCTest's zero rectangle. Full-state enabled matches every node; visibility and
focus have documented semantic differences. Default batch-visible Settings is about1.83s
versus WDA2.00s; full-state about3.48s. No universal benchmark or complete parity claim.

Actual Opus5.5 follow-up finds no code blocker after action-status and occlusion guards;
its empty-timeout diagnostic finding is also repaired. 59 AX regressions pass on local
macOS26.5.1 and Mac-M2 macOS27.2, with verified source hashes. Local `make check-host`,
isolated install and source/installed AX-only smoke pass. Calculator guarded press has
independent tree/screenshots, including after owned Runner removal; Mac-M2 forwarded AX
reads, hit-test and pressTwo succeed with closed connections. No production call uses XCTest.

v0.3.0 was formally published after the user's explicit release/Homebrew request;
its CI, package, tap install and local/forwarded AX evidence are recorded separately.
The full supported macOS27/Xcode27/iOS27 native HID/media/CLI-selection interactive gate
remains open because Mac-M2 native CoreDevice does not enumerate the allocated13Pro.
Earlier gate exceptions are scoped to their completed adoption/release, not this change.

The current user authorizes native-only deep observations plus separate supplemental
attributes and asks for actual13Pro Bilibili empty login-modal/numeric-keyboard controls.
Baseline v0.3.0 intermittently fails root/handle/frame reconciliation in this state; one
frame mismatch maps to an invisible moving carousel caption. Other root/handle causes
remain unisolated. Reproduce baseline, compare repeated native-only/full-state reads,
validate complete ordered edges and usable rectangles, and retain screenshots/raw data
outside Git. Implementationdde8557 passes52AX regressions on both hosts and the complete local
host suite. Ten interleaved13Pro target-page trials show v0.3.0deep6/10 versus native
10/10 and separated full-state10/10; native trees have150–152 records/depth18 and all
ten digit rectangles. Native-only mean query481ms versus old successful1578ms. The
isolated install and source/installed Settings AX smoke pass. Three forwarded macOS27
pairs also pass; native inventory still lacks this phone, so the full matrix stays open.
A follow-up live close-overlay control returns native error8 after72 state reads,
exits1 and preserves the complete170-node native tree plus explicit failed supplement.
Fresh closed/reopened reads succeed with expected keyboard presence/absence; this
negative branch is now device-proven. No further implementation defect is found.
Phone restored Settings. On 2026-10-14 the maintainer subsequently authorized merge and
v0.4.0 publication/Homebrew update, retaining the full native matrix as open. Candidate
build/package/Homebrew checks are still required before publication. Raw references:
`~/.local/state/ipb/20261014-native-deep/`.

The native Settings hierarchy changes with active reference session (171 vs inactive138),
exact flag unlocated. Direct press on a never-automated device remains untested; prior
Automation Mode authorization is still a discriminator. XCTest type mapping, broader
page/action coverage, atomicity, token lifetime and MCP remain follow-ups.

Raw evidence is outside Git at `~/.local/state/ipb/20261013-13pro-xctest/`; only condensed
problems, root-cause boundaries and protocol conclusions are committed. Earlier deep
research remains on `codex/communication-capabilities-20261013` (`03f5ce8`).

## Rejected alternatives

- Replacing the default before overlay validation: regresses a currently readable Bilibili page.
- Silent shallow fallback: hides nil/truncated native snapshots and changes coverage unnoticed.
- Requiring ordinary/native geometry equality: rejects a valid native tree when background
  animation changes geometry between serial reads. Keep observations separate instead.
- Global handle deduplication: deletes real repeated paths and their parent edges.
