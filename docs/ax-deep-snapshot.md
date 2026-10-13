# Native deep snapshots for `ipb ui`

Branch: `codex/ax-deep-snapshot`, based on `origin/main` (`f3a57dc`).

## Problem and design

The ordinary AXChildren graph omits backing layout containers: the iPhone 13 Pro
Settings main page has 13 ordinary elements, whereas the independently verified
DevicesApp snapshot has 138 records at depth 20. Earlier request 2 / attribute 52
(native 95006) returned nil because its options lacked a nonempty array of numeric
native AX attributes. The former archive decoder also rejects that valid response
at its 100-level UID/container nesting limit.

Keep the existing paired USB userspace RSD, raw DTX channel zero, one outstanding
read and cleanup path. `ui --deep` requests the native descendant snapshot with
numeric label/frame/traits/identifier/value and class/bundle attributes. Preserve
its actual ordered child edges and every path occurrence of a repeated handle;
output IDs remain snapshot-local. Supplement the ordinary accessible elements
through the existing Description-first reads to retain state and role fields.
Structural elements have snapshot fields by default; additional states require explicit
`--full-state` reads and are never synthesized.

Retain JSON schema 1's field types and text output. For deep output, change `hierarchySource` and
`attributePolicy` to describe the new sources; add native class/bundle metadata.
Navigation/reported-parent handle references are emitted only when a single output
node resolves them; ambiguity is reported explicitly. No XCUIElementType synthesis.

Decode keyed archives iteratively, with independent byte/object/work/nesting
budgets and cycle rejection. Validate every native children array against its
declared count, the root identity, PID and the existing 512-record / depth-32
product limits. Nil, malformed/truncated snapshots or ordinary elements absent
from the snapshot fail without fallback or partial output. Root, selected process
and display pre/post checks remain; `atomic=false` remains explicit.

## Element press and supplementary attributes

Default deep includes native hint2002 and visibility2025 plus ordinary Description-first
state. `--deep --full-state` supplements snapshot-only handles with the proven AXP
27/28/30/32/42/45/46/51 fields once per unique handle. Native fields have precedence;
missing values remain missing. The full-state cost is explicit and opt-in. AX focus and
visibility do not claim XCTest semantics. Never infer XCUI types from classes/traits.

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

The full supported macOS27/Xcode27/iOS27 native HID/media/CLI-selection and interactive gate
remains open: fresh Mac-M2 native inventory lacks this13Pro. USB forwarding only validates
the AX helper. Current PR checks supply the CI/package result; no release is published.
The user explicitly authorized PR#2 adoption using the completed AX device controls and
macOS27 CI as this change's gate. This exception does not close native acceptance or waive
a future release gate. Merge preserves the segmented commit history; no release is published.

Known, not fixed: Bilibili9.14.0 login/keyboard serial reconciliation intermittently detects
changing root/handles/geometry; a moving invisible background caption explains one frame
conflict only. Keep strict failure and opt-in, not a silent shallow fallback. The native
Settings hierarchy changes with active reference session (171 vs inactive138), exact flag
unlocated. Direct press on a never-automated device has not been tested; prior Automation
Mode authorization remains a discriminator even after the Runner is removed. XCTest type
mapping, broader action/page coverage, atomicity, token lifetime and MCP remain follow-ups.

Raw evidence is outside Git at `~/.local/state/ipb/20261013-13pro-xctest/`; only condensed
problems, root-cause boundaries and protocol conclusions are committed. Earlier deep
research remains on `codex/communication-capabilities-20261013` (`03f5ce8`).

## Rejected alternatives

- Replacing the default before overlay validation: regresses a currently readable Bilibili page.
- Silent shallow fallback: hides nil/truncated native snapshots and changes coverage unnoticed.
- Global handle deduplication: deletes real repeated paths and their parent edges.
