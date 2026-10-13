# Application elements with `ipb ui`

This source revision provides `ipb ui --deep` to read an application's native
deep accessibility snapshot, numerical element frames and state over DevicesApp raw DTX.
Default `ipb ui` retains the ordinary AXChildren graph. Released `v0.2.0` does not include
`--deep`; use a source revision containing this feature.
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

Native snapshot fields include label, identifier, value, frame and traits. Frames are
**device logical points**; traits are decimal strings preserving all 64 bits. Native
class/type strings (5003/5004) and bundle ID (3003) retain their numeric keys under
`nativeAttributes`. They do not define XCTest element types. Unavailable properties are
omitted; `CGRectNull` is reported as `frameUnavailable`. Structural records may have no
text or state. The text renderer shows Label, Description, Identifier, then native class text.

For `--deep`, `attributePolicy="native-snapshot+description-first"` supplements ordinary
accessible elements with description, placeholder, role/subrole and enabled/focused/selected/visible
fields through the previous Description-first reads. Label 3 is only requested without
nonblank Description, avoiding the reproduced device-side rich Label encoding failure
on Bilibili. Native snapshot label 2001 is returned directly through the snapshot; it is
not a renamed Description. `attributeSource` distinguishes snapshot-only records from
`native-snapshot+AXAttributes`. Native snapshot fields retain precedence. State fields
are not invented for the extra structural records.

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
protocol, changed/incomplete graph or cleanup failure. `SMOKE_AX=1` adds the read gate
for both ordinary and deep output to the normal smoke matrix; `SMOKE_AX_ONLY=1` runs only that gate.

## AX and XCTest coverage

The earlier 12 mini comparison used ordinary AXChildren: Settings 13 nodes versus
XCTest 176, Calculator 24 versus 45. It established matching native frames for the
corresponding accessible elements, while the extra XCTest entries included layout,
text and image records. The new numeric snapshot options resolve the previous nil
response and recover real deeper hierarchy on iPhone 13 Pro: Settings 138 records /
135 unique handles / depth 20 and Calculator 45 / depth 16 in the research controls.
The same-session ordinary 13/24 elements and their native frames match the snapshots.
The installed visible-title Bilibili page also reads25 ordinary nodes versus94 deep
records at depth19, with identical title text and native rectangle; its login/keyboard
modal remains a separate failing deep case.
See [native snapshot wire/source evidence](protocol.md#devicesapp-deep-snapshot-required-attributes-and-host-decoding-2026-10-13).

These are different devices and page states; they do not establish a missing-node percentage
or complete XCTest parity. XCTest element types/state fidelity, arbitrary third-party apps,
WebViews, secure/rotated/modal pages, offscreen coverage and atomicity remain unverified.
Product validation and exact host/device scope are recorded in
[verification](verification.md#open-items--current-state-living-section).
MCP integration and direct semantic AX actions are not implemented by this command.
