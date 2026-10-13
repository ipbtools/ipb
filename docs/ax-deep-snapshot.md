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
Structural elements have only the fields actually returned by the snapshot.

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

Implementation is complete on this local branch. Both hosts build and pass complete host
regressions; final28 AX tests pass. Source/installed ordinary+deep AX gates and installed
noninteractive smoke pass on the local13Pro; Calculator JSON/text deep reads pass.
Installed Bilibili visible-title default25/depth1 and deep94/depth19 both pass with
matching title and native frame; the previous Label timeout does not recur.
Mac-M2 (macOS27/Xcode27) reads the same138-record Settings tree through owned USB forwarding.
Its native CoreDevice cannot discover this13Pro (error1000), so full supported native/interactive
acceptance remains open. The main Bilibili login/numeric
keyboard page reads40/41 ordinary nodes, while deep+state reads fail geometry/root
stability or handle-set reconciliation. Cause remains open. Keep ordinary AXChildren as
the default and require `--deep` explicitly; deep failures never silently fall back.

Research evidence is local
at `/private/tmp/ipb-ax-snapshot-20261013` and retained on research branch
`codex/communication-capabilities-20261013` (`03f5ce8`). Matching iOS 27 / 24A437
framework disassembly and live controls prove the required numeric option and
deep trees; they do not prove universal app coverage or XCTest parity.

## Rejected alternatives

- Replacing the default before overlay validation: regresses a currently readable Bilibili page.
- Silent shallow fallback: hides nil/truncated native snapshots and changes coverage unnoticed.
- Global handle deduplication: deletes real repeated paths and their parent edges.
