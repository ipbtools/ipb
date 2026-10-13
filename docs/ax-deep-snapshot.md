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

Implementation is on PR #2, reviewed at `748e2c5`. Actual returned Opus 5.5
review and follow-up find no blocker with opt-in and strict reconciliation.
The review adds discriminating nil/root/handle/frame diagnostics and seven
regressions: all 35 AX tests pass locally and on Mac-M2; local `make check-host`
passes. Source and isolated installed AX-only gates pass on the allocated 13 Pro.
Original native build/noninteractive smoke results remain in their dated record;
this review does not claim a new full gate.

Fresh iOS 27.0 / 24A437 controls on local macOS 26.5.1 give Settings 13 ordinary
nodes versus 138 deep records / 135 handles / depth 20, Calculator 24 versus
45 / depth 16, and Bilibili 9.14.0 visible-title video 21 versus 89 / depth 19.
Settings and video each pass three pairs; Calculator is one pair. Video title
text and rectangle match in all three pairs. Counts are page/version scoped.
Mac-M2 (macOS 27.2 / Xcode 27) passes 35 tests and reads the same 138-record
Settings tree through an owned USB forward, with connection/tunnel closed.
Native discovery still lacks this 13 Pro: the full supported native HID/media,
CLI selection and interactive gate remains open.

Known, not fixed: the empty Bilibili login/numeric-keyboard page changes
intermittently during serial reads. Ordinary and deep root-children checks can
fail; deep additionally reports missing handles or frame conflicts. Successful
deep controls return 168 records / depth 18. Paired controls narrow one frame
failure to an invisible background-carousel UILabel moving horizontally, not
the cause of every root/handle change. Two native-only snapshots agree at 168
records/handle set (77/73 ms); this does not prove atomicity or warrant changing
state/output semantics. Keep ordinary AXChildren default and deep opt-in;
a fresh read can recover, without a guarantee. Native-only output and remaining
handle-lifetime research are follow-up work, not hidden fallbacks.

Research evidence is local
at `/private/tmp/ipb-ax-snapshot-20261013` and retained on research branch
`codex/communication-capabilities-20261013` (`03f5ce8`). Matching iOS 27 / 24A437
framework disassembly and live controls prove the required numeric option and
deep trees; they do not prove universal app coverage or XCTest parity.

## Rejected alternatives

- Replacing the default before overlay validation: regresses a currently readable Bilibili page.
- Silent shallow fallback: hides nil/truncated native snapshots and changes coverage unnoticed.
- Global handle deduplication: deletes real repeated paths and their parent edges.
