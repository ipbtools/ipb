# Application elements with `ipb ui`

This source revision provides `ipb ui --deep` to read an application's native
deep accessibility snapshot, numerical element frames and state over DevicesApp raw DTX.
`ui hit-test` reads the element at a point; `ui press` activates a freshly resolved identifier.
Default `ipb ui` retains the ordinary AXChildren graph. Released `v0.2.0` does not include
the deep/state/action additions; use a source revision containing this feature.
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

JSON schema 1 retains `snapshotId`, application PID/selection, a `nodes` array with
snapshot-local `id`, `parentId`, ordered `children`, depth and available attributes.
`--deep` sets `hierarchySource="AXUserTestingSnapshot"` and identifies the native descendant hierarchy.
Repeated element handles keep distinct path records and output IDs; `nodeCount` counts
records, while `uniqueElementCount` counts native handles. `ordinaryAXNodeCount` counts
ordinary accessible elements whose state was supplemented. IDs are valid only within
that output; they are not reusable action tokens.

Native snapshot fields include label, hint, identifier, value, frame, traits and native AX
visibility (2025). `stateScope="native-visible+ordinary-state"` describes default deep output. Frames are
**device logical points**; traits are decimal strings preserving all 64 bits. Native
class/type strings (5003/5004) and bundle ID (3003) retain their numeric keys under
`nativeAttributes`. They do not define XCTest element types. Unavailable properties are
omitted; `CGRectNull` is reported as `frameUnavailable`. Structural records may have no
text or additional state. The text renderer shows Label, Description, Identifier, then native class text.

For `--deep`, `attributePolicy="native-snapshot+description-first"` supplements ordinary
accessible elements with description, placeholder, role/subrole and enabled/focused/selected/visible
fields through the previous Description-first reads. Label 3 is only requested without
nonblank Description, avoiding the reproduced device-side rich Label encoding failure
on Bilibili. Native snapshot label 2001 is returned directly through the snapshot; it is
not a renamed Description. `attributeSource` distinguishes snapshot-only records from
`native-snapshot+AXAttributes`. Native snapshot fields retain precedence. State fields
are not invented for the extra structural records.

Use `--deep --full-state` to supplement every unique snapshot-only handle with the proven
enabled/focused/selected/visible, placeholder and role/subrole attributes. Repeated path
records share one read. `stateScope="all-native-handles"` and
`attributePolicy="native-snapshot+description-first+structural-state"` identify this mode;
missing fields remain omitted and snapshot fields retain precedence. This costs one extra
request per snapshot-only handle: the same-page Settings controls took about 3.5 s versus
1.8 s for default deep, excluding fresh tunnel/import startup. Larger pages remain subject
to the 30 s budget. Native AX visibility and focus are not XCTest visibility/focus; false
values are preserved even when XCTest reports true.

Parent edges come from the actual native snapshot. Navigation order and reported AX parent
are separate handle relations. Ambiguous references to repeated handles are omitted and
marked `navigationUnavailable` / `reportedParentUnavailable="ambiguous-snapshot-handle"`;
the client does not choose an arbitrary path.

Collection is serial and bounded (512 records, depth 32, 30 s plus bounded cleanup).
The keyed archive has separate byte/object/work/nesting limits and is decoded iteratively.
Every native child array must agree with its declared count. Nil/malformed/truncated
snapshots, missing ordinary elements, changed geometry/roots, exhausted budgets or cleanup
failures return nonzero without a partial tree or shallow fallback. `atomic=false` remains
intentional: ordinary root text/frame/children, selected PID and display checks do not prove
an atomic generation for all descendants. Cleanup reports the known close-before-stop-ack
case separately from acknowledged teardown.

Without `--deep`, the existing AXChildren tree and Description-first policy remain.
Bilibili login/numeric-keyboard reads can fail on root/geometry/handle changes in both
ordinary and deep modes. Deep additionally reconciles ordinary state with native geometry.
A paired control identified one frame conflict on an invisible carousel caption behind the
login overlay: its horizontal position moved between reads. Two native-only snapshots on
that page agreed, but other missing-handle/root changes remain unexplained.
Root errors name the changed component; reconciliation errors include the first missing
handle/count or both frames. They do not guarantee that a retry will succeed. This is why deep
reads are opt-in. They fail explicitly rather than silently returning shallow data.

For `ui`, exit 2 means usage/Python/dependency failure, 3 means device selection or
UUID-to-USB resolution failure, 5 means timeout/cancellation, and 1 means tunnel,
protocol, changed/incomplete graph or cleanup failure. For `ui press`, any failure after
submission returns **6**, preserving accepted/refused/unknown status and warning against
automatic retry. Success reports `nativeAccepted=true`, `effectVerified=false`: observe
the page again to establish the effect. `SMOKE_AX=1` adds the read gate
for both ordinary and deep output to the normal smoke matrix; `SMOKE_AX_ONLY=1` runs only that gate.

## Hit testing and pressing an element

```sh
ipb -s '13 Pro' ui hit-test --point 0.15 0.55 --json
ipb -s '13 Pro' ui --deep --json
ipb -s '13 Pro' ui press --identifier Seven --json
ipb -s '13 Pro' ui --deep --json
```

`hit-test` returns the actual native element at the normalized point, its available fields,
and checks the same hit identity/display again. It is read-only. It does not compute XCTest's
`isHittable`. Portrait selection restrictions still apply; `hit-test` cannot use `--pid`.

`press` resolves the displayed app and a fresh native snapshot. The exact accessibility
identifier must match one native handle; repeated paths of that same handle are allowed.
It confirms identifier/frame, known enabled/visible state, actual frame-centre hit identity,
foreground PID and display before sending one native press. Missing/ambiguous/hidden/disabled,
zero-frame or centre-occluded targets fail before sending. This conservative guard can reject
some valid targets whose centre hits a child or whose AX visibility is false. It is not an
XCTest hittability implementation. A previous dump's `n…` IDs cannot be used for actions.
There is no label match, automatic replay or HID fallback. `--deep`/`--full-state` are dump
options and cannot be combined with either operation. The single native reply confirms
acceptance, not a generic UI transition; re-read or inspect a screenshot after success.

Calculator digits and the History button have real-device effect checks. Press still lacks
fresh-device authorization A/B and broader app coverage: the tested 13 Pro previously enabled
XCTest Automation Mode for the reference comparison. Removing/stopping the task-owned Runner
still permits the product action; whether prior Automation Mode is necessary is unresolved.
The product itself installs no Runner and starts no XCTest session.

## AX and XCTest coverage

Fresh iPhone 13 Pro / iOS 27.0 / 24A437 same-page comparisons, each with three AX/XCTest/AX
rounds, match every ordered path: Calculator main **45/45**, History overlay **99/99**,
Settings **171/171**. Calculator native rectangles all match. Settings has 169–170 usable
rectangles matching exactly; the remaining AX `CGRectNull` records correspond to XCTest
zero rectangles. They are kept unavailable rather than fabricated. `--full-state` enabled
values match every XCTest node on both main pages. One Calculator focus value and 52 Settings
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
parity on these pages only. Default deep's mean query time with the reference active was
about **1.83 s Settings / 1.18 s History**, versus **2.00 s / 1.44 s** for WDA JSON source;
full structural state is slower. These timings exclude some startup costs and are not a
universal benchmark.

The visible-title Bilibili controls from the preceding review remain valid; its changing
login/keyboard background can still fail strict reconciliation. Arbitrary third-party apps,
WebViews, secure/rotated pages, offscreen coverage, atomicity, complete XCTest type/state
parity, persistent sessions and MCP integration remain open. See
[native wire/source evidence](protocol.md#devicesapp-deep-snapshot-required-attributes-and-host-decoding-2026-10-13)
and [verification](verification.md#open-items--current-state-living-section) for exact scope.
