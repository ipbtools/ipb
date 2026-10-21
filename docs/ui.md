# Application elements with `ipb ui`

v0.4.0 provides `ipb ui --deep` to read an application's native
deep accessibility snapshot and numerical element frames over DevicesApp raw DTX.
v0.4.0 separates later state reads from the native observation;
`v0.3.0` still uses the earlier ordinary/native reconciliation described in its tagged guide.
`ui hit-test` reads the element at a point. v0.5.0 adds exact locators and waits,
qualified press, one-shot scroll-to-visible, guarded text replacement and explicit modal
button actions. Supplementary12mini controls are distinct from the still-open supported
macOS27 native device gate. Same-process ordinary and deep dump schemas are unchanged.
Default `ipb ui` retains the ordinary AXChildren graph. `v0.3.0` includes the
deep/state/action additions; earlier `v0.2.0` has only ordinary AXChildren reads.
See the [installation channels](../README.md#installation-channels) for stable and `--HEAD`
packages.

## Setup

The host backend needs Python 3.11+ and the verified `pymobiledevice3==11.10.2`.
It uses an existing USB pairing, Developer Mode and the advertised iOS 27 AX service.
It does not pair automatically or fall back to another phone/transport. Other ipb commands
do not depend on this optional Python package.

Create an optional environment once (from a source checkout; an installed copy puts the
requirements file in `<prefix>/share/ipb/requirements-ax.txt`):

```sh
python3.12 -m venv "$HOME/.local/share/ipb/ax-venv"
"$HOME/.local/share/ipb/ax-venv/bin/python" -m pip install -r requirements-ax.txt
ipb -s '12 mini' ui
ipb -s '12 mini' ui --json > page.json
ipb -s '13 Pro' ui --deep --json > deep-page.json
```

ipb prefers that environment (or `$XDG_DATA_HOME/ipb/ax-venv` when set), then `python3`.
`IPB_AX_PYTHON=/path/to/python` selects another existing environment. Installation/update
does not install Python packages automatically.

## Select and read a page

By default, a read-only hit test at the screen centre selects the displayed application's
PID. `--point 0.3 0.4` chooses another normalized point; `--pid 1234` selects a known app
explicitly. A background/suspended app may refuse the AX request (observed error17).
A keyboard/overlay can select a different process.
Hit-test selection currently requires portrait `rot0`; explicit PID reads retain the raw
AX coordinate space. Failed or nil hit tests fail the command, with no automatic replay.

## Returned graph and text policy

Ordinary dumps keep JSON schema 1 and the existing AXChildren/Description-first contract.
Deep dumps use **schema 2**: `hierarchySource="AXUserTestingSnapshot"`,
`attributePolicy="native-snapshot"` and `stateScope="native-snapshot"`. Each node has a
snapshot-local `id`, `parentId`, ordered `children`, depth and actual native attributes.
Repeated handles keep distinct path records; `nodeCount` counts records and
`uniqueElementCount` counts handles. Deep no longer walks ordinary AXChildren, so it does
not report `ordinaryAXNodeCount` or ordinary navigation/reported-parent relations.
IDs are valid only within that output; they are not reusable action tokens.

Native fields include label, hint, identifier, value, frame, traits and AX visibility
(2025). Frames use **device logical points**; traits are decimal strings preserving all
64 bits. Native class/type strings (5003/5004) and bundle ID (3003) retain their numeric
keys under `nativeAttributes`. These do not define XCTest element types. Unavailable
properties are omitted; `CGRectNull` is reported as `frameUnavailable`. Structural records
may have no text or state. The text renderer shows native Label, Identifier, then class.

A native tree can contain a terminal `AXRemoteElement` reference to another process.
Only its proven zero-child shape is accepted. Such nodes add `processIdentifier` and
`externalProcessReference=true`; their remote descendants are not synthesized and actions
cannot target them. Other cross-process shapes fail. Ordinary AXChildren remains same-process.

`ui --deep` obtains the tree and rectangles from one native response. It does not require
separately read ordinary handles, rectangles or root children to match that observation.
The application root handle, selected PID and display are checked around collection.
`rootStable=true` with `rootStabilityScope="application-identity"` describes only that
application identity check; it does not claim stable descendant geometry. `atomic=false`
remains explicit. `snapshotMs` is elapsed query time through validation of this primary
observation; `queryMs` also includes optional supplementary reads. Both exclude tunnel
startup and cleanup, and neither measures only device snapshot computation.

### Supplementary state

Native-only dumps report `supplementalAX.status="not-requested"`. Add
`--deep --full-state` to read enabled/focused/selected/visible, placeholder and role/subrole
once per unique native handle. Repeated path records share one read. Results live in
**`node.supplementalAX`**, not the native node fields. For example:

```json
{
  "id": "n12",
  "visible": false,
  "supplementalAX": {"enabled": true, "visible": true, "roleCode": 2}
}
```

The two visibility values come from different reads and may disagree. Supplementary
attributes are later observations with AX semantics, not snapshot-time or XCTest state.
They cannot be used to bypass the fresh guards in `ui press`. Missing fields remain missing;
false values stay false. No rich Label, ordinary child list or frame request is needed.

The top-level `supplementalAX` summary reports `status`, `scope="all-native-handles"`,
requested/attempted/completed unique-element counts, requested AXP attribute IDs and its
own `queryMs`. `status="complete"` means every handle's reply was read and validated,
not that every optional field exists or all reads share one generation. This costs one
request per unique handle and remains subject to the 30 s command budget.

On an individual supplementary request/validation error, further semantic reads stop.
Global command timeout/cancellation is excluded from this retained-tree case. If the primary tree
was valid and cleanup succeeds, JSON still contains that **complete native tree**, any
completed supplementary results and `supplementalAX.status="failed"` with error type,
message and affected snapshot node IDs. The command prints a diagnostic and exits **1**
(or **5** for a request timeout). Consumers may use the native observation while treating
supplementation as failed; exit 0 never hides a failed requested read. Text output also
prints the native tree and a stderr diagnostic. There is no retry or shallow fallback.

### Collection failures

Collection is bounded to 512 records and depth 32, with a 30 s main budget plus
bounded cleanup.
The keyed archive has separate byte/object/work/nesting limits and is decoded iteratively.
Every native child array must agree with its declared count. Native nil/malformed/truncated
snapshots, invalid root/PID/display checks, global timeout/cancellation or cleanup failures
return nonzero **without JSON or a partial native tree**. Cleanup separately reports the
known close-before-stop-ack case.

Ordinary `ui` keeps its serial root text/frame/children checks and can still fail when a
page changes. The former deep path also required ordinary/native geometry agreement; a
Bilibili login-modal background carousel could move between those reads and reject a valid
snapshot. The new path separates the observations; current device verification and any
remaining native/supplementary failures are recorded in [verification](verification.md).

For `ui`, exit 2 means usage/Python/dependency failure, 3 means device selection or
UUID-to-USB resolution failure, 5 means timeout/cancellation, and 1 means tunnel,
protocol, changed/incomplete graph or cleanup failure. For `press`, `input`,
`scroll-to-visible` and `alert-press`, any failure after submission returns **6**,
preserving accepted/refused/unknown status and warning against automatic retry.
A successful ordinary press reports `nativeAccepted=true`, `effectVerified=false`: observe
the page again to establish the effect. `SMOKE_AX=1` adds the read gate
for both ordinary and deep output to the normal smoke matrix; `SMOKE_AX_ONLY=1` runs only that gate.

## Locating, waiting for, and pressing an element

```sh
ipb -s '13 Pro' ui hit-test --point 0.15 0.55 --json
ipb -s '13 Pro' ui --deep --json
ipb -s '13 Pro' ui locate --label 'Seven' --json
ipb -s '13 Pro' ui wait --identifier Seven --wait-for present --timeout 5 --json
ipb -s '13 Pro' ui press --identifier Seven --json
ipb -s '13 Pro' ui --deep --json
```

`hit-test` returns the actual native element at the normalized point, its available fields,
and checks the same hit identity/display again. It is read-only. It does not compute XCTest's
`isHittable`. Portrait selection restrictions still apply; `hit-test` cannot use `--pid`.

`locate` reads one fresh native snapshot and returns every public match, its match count,
uniqueness, and snapshot-local path IDs. It does not expose or retain native object IDs. The
`identifier`, `label`, string `value`, and native `--class` selectors are exact and conjunctive: every supplied
field must match the same native element. There is no fuzzy matching or automatic first match.
For example, a repeated button label and its child UILabel may both match `--label 'Continue'`;
use an identifier observed in the tree, or combine the label with another known exact field.
`--class` matches native attribute5003, not an invented XCTest element type.
Repeated paths to one native handle are reported as path IDs for that single match.

`wait` polls fresh snapshots after device setup for one unique match (`present`) or no matches
(`absent`). Its requested deadline is at most 15 seconds (default 5); an ambiguous selector or
read/validation error fails rather than being treated as absence. The overall command watchdog
is 30 seconds, including setup. A timed-out wait reports `timed_out` and exits nonzero. Neither
operation changes the UI or reuses a handle from an earlier snapshot.

`press` accepts one or more exact `--identifier`, `--label`, `--value`, and `--class` selectors. It resolves
one distinct native element in a fresh snapshot; label/value/class-qualified selections are resolved
again from a second native snapshot immediately before the live-state checks. It then confirms
the identifier when present, frame stability, known enabled/visible state, usable frame,
frame-centre hit identity, foreground PID, and display before sending one native press. Missing,
ambiguous, changed, hidden/disabled, zero-frame, or centre-occluded targets fail before sending.
This conservative guard can reject some valid targets whose centre hits a child; it is not an
XCTest hittability implementation. Snapshot-local `n…` path IDs are never action tokens.

After action submission, failures preserve accepted/refused/unknown status and warn against
automatic retry; there is no HID-coordinate fallback. A successful native reply means the press
was accepted, not that the expected UI transition occurred. Re-read with `locate`/`wait` or
inspect a screenshot to check the effect. `--deep`/`--full-state` are dump options and cannot be
combined with these operations. The maintainer authorized v0.5.0 publication after
Opus5.5 review and host/package checks, without further device testing. The supported
native physical matrix remains unverified; publication does not expand seed support.

Calculator digits/History, Settings navigation and search focus have real-device effect checks.
On a previously authorized12mini, a temporary user-approved read-only diagnostic App recorded
27 actual Automation Mode BOOL replies, all false, overlapping native reads and direct actions.
Thus those paths do not require currently enabled Automation Mode on iOS27.0/24A437.
First-use behavior on a never-authorized phone is still untested. The diagnostic App is not an
ipb dependency; the product installs no Runner and starts no XCTest session.

## Text replacement and scroll-to-visible

```sh
ipb -s '12 mini' ui press --class UISearchBarTextField --json
ipb -s '12 mini' ui input --class UISearchBarTextField --text 'Battery' --replace-all --json
ipb -s '12 mini' ui scroll-to-visible --identifier com.apple.settings.general --json
```

`input` requires an explicit nonempty whole-field replacement. It resolves a unique fresh
text-entry element and checks that native attribute3002 identifies it as the application's
actual first responder. AX focus alone is insufficient. It does not focus another control
automatically. Two fresh observations and live state/frame/hit/PID/display checks precede one
invocation of the same installation's `text --replace-all` command. That command copies the
device clipboard once and sends Command-A followed by Command-V on the existing HID path.
It does not use the AX whole-value setter. Input-only snapshots request3002; normal dumps do not.
Keep other controllers and manual focus changes idle during input: wrapper startup and
clipboard transfer happen after the final focus check. If focus changes in that interval,
HID can reach another field; later checks can report failure but cannot undo the input.

The result verifies exact fresh value readback on the same native identity, rather than
reusing an old value selector. It does not prove every app's business callback. A paste prompt,
changed target, child failure or uncertain outcome exits nonzero and must not trigger an
automatic repeat. The clipboard or field may already have changed. Explicitly handle the
observed prompt and read the page again before deciding what to do next. The text argument is
not echoed in input output. `text <text>` remains the current-caret/selection primitive;
`text --replace-all <text>` explicitly selects the whole focused field first.

`scroll-to-visible` sends one native action11 to an element already present in a fresh native
snapshot. It allows an offscreen target, checks stable identity/frame and known state, then
observes the result. `nativeResult` preserves Apple's BOOL; `postconditionVerified` separately
requires the same unique target, fresh enabled/visible state, full frame inside the display
and an exact centre hit. An already visible target can return native false and still satisfy
that postcondition. Failure exits nonzero without another scroll or coordinate fallback.
This cannot find a virtual-list row that has not been materialized in the snapshot.

## Explicit system alert buttons

Read the observed SpringBoard PID from `ipb ps`, then inspect its native tree. For example,
replace1234 below with that PID and use the exact alert/button labels from the current tree:

```sh
ipb -s '12 mini' ps
ipb -s '12 mini' ui --deep --pid 1234 --json
ipb -s '12 mini' ui alert-press --pid 1234 \
  --alert-label '“Settings” would like to paste from “dtpasteboardd”' \
  --label 'Allow Paste' --json
```

`alert-press` is a separate explicit semantic action for the tested SpringBoard native
UIAlert container/button classes. It requires PID, exact container title, exact button label
and JSON output; it accepts no other selectors. Two fresh observations must agree on the
unique visible modal, descendant button, identities and frames. Live enabled/visible state,
full display containment, SpringBoard identity and display are checked before one native
action5. A child UILabel may repeat the title without becoming a second modal. Foreign
references, another app root, unknown classes, ambiguous or changed targets fail before sending.

This operation does **not** claim point hittability: `hitTestVerified=false` is explicit.
On the real12mini paste prompt, global point hit tests return error8 despite usable native
modal/button records. Ordinary `press` keeps its point-hit guard. After an accepted semantic
action, read-only observations wait at most two seconds for the original modal and button
to disappear or become known invisible. Unknown visibility, read errors, timeout or persistent
visibility never count as disappearance. Native acceptance and verified disappearance are
separate results; neither authorizes another press, an input replay or automatic alert handling.
Here `effectVerified` means the original modal/button disappeared or became known invisible;
it does not establish that the button's application-specific consequence succeeded.
This covers the tested modal shape, not every system sheet, WebView alert or credential page.

## AX and XCTest coverage

Fresh iPhone 13 Pro / iOS 27.0 / 24A437 same-page comparisons, each with three AX/XCTest/AX
rounds, match every ordered path: Calculator main **45/45**, History overlay **99/99**,
Settings **171/171**. Calculator native rectangles all match. Settings has 169–170 usable
rectangles matching exactly; the remaining AX `CGRectNull` records correspond to XCTest
zero rectangles. They are kept unavailable rather than fabricated. The v0.3.0 `--full-state` enabled
values matched every XCTest node on both main pages. One Calculator focus value and 52 Settings
visibility values differ; final batch-visible controls report 53 Settings differences and
22 History-overlay differences, all AX false / XCTest true. These are separate semantics.

The 17 nonempty Settings XCTest values lacking a separate AX value field are already present
in that node's AX label/Description. Native class strings, role codes and raw traits do not
supply the complete XCTest element-type taxonomy; no type mapper is invented. AX hint and
placeholder remain distinct fields.

An active reference session changes the native Settings hierarchy: the same product reads
138 records / 135 handles / depth20 after Runner stops. The precise system flag responsible
has not been isolated. Historical 12 mini counts (13 ordinary / 176 XCTest) and inactive
13 Pro counts cannot be used to calculate missing nodes. Current same-page controls establish
parity on these pages only. The v0.3.0 combined deep/state mean query time with the reference active was
about **1.83 s Settings / 1.18 s History**, versus **2.00 s / 1.44 s** for WDA JSON source;
full structural state is slower. These timings exclude some startup costs and are not a
universal benchmark.

The visible-title Bilibili controls from the preceding review remain valid for v0.3.0.
Its combined deep/state path could fail on a changing login/keyboard background; this
v0.4.0 separates the native snapshot from later attributes. Arbitrary third-party apps,
WebViews, secure/rotated pages, offscreen coverage, atomicity, complete XCTest type/state
parity, persistent sessions and MCP integration remain open. See
[native wire/source evidence](protocol.md#devicesapp-deep-snapshot-required-attributes-and-host-decoding-2026-10-13)
and [verification](verification.md#open-items--current-state-living-section) for exact scope.
