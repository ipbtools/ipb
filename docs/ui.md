# Application elements with `ipb ui`

`ipb ui` is included in the merged `main` source and the stable `v0.2.0` package. It reads an
application's accessibility graph, numerical element frames and state over DevicesApp raw DTX.
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
```

ipb prefers that environment (or `$XDG_DATA_HOME/ipb/ax-venv` when set), then `python3`.
`IPB_AX_PYTHON=/path/to/python` selects another existing environment. Installation/update
does not install Python packages automatically.

## Select and read a page

By default, a read-only hit test at the screen centre selects the displayed application's
PID. `--point 0.3 0.4` chooses another normalized point; `--pid 1234` selects a known app
explicitly, including a background app. A keyboard/overlay can select a different process.
Hit-test selection currently requires portrait `rot0`; explicit PID reads retain the raw
AX coordinate space. Failed or nil hit tests fail the command, with no automatic replay.

## Returned graph and text policy

JSON schema 1 contains `snapshotId`, application PID/selection, a `nodes` array with
snapshot-local `id`, `parentId`, ordered `children`, depth and available attributes:
label, identifier, value, description, placeholder, frame, role/subrole codes, traits and
enabled/focused/selected/visible flags. Frames are **device logical points**. Traits are a
decimal string to preserve all 64 bits. Unavailable properties are omitted; `CGRectNull`
is reported as `frameUnavailable`. Parent edges come from actual AX children, and navigation
order is separate. IDs are valid only within that output; they are not reusable action tokens.

`attributePolicy="description-first"` queries Description before the optional Label field.
When Description contains text, Label is not requested; otherwise a separate Label read is
made. This avoids a reproduced iOS AX Label timeout on Bilibili's video title. JSON preserves
`description` and `label` separately and omits fields not queried/returned. The text tree shows
Label, then Description, then Identifier. Trees and rectangles are still fully validated;
an actual request timeout fails with its request type, node identity and attribute IDs.
The captured rich Label reply fails device-side secure encoding; its plain Description succeeds.

Collection is serial and bounded (512 nodes, depth 32, 30 s plus bounded cleanup).
`atomic=false` is intentional: pre/post checks confirm root text (Description, or Label when
Description has no text), frame/children and selected PID
stability, not an atomic page snapshot. Missing children, changed roots, exhausted budgets
or cleanup failures return nonzero without a partial tree. The cleanup field records the
known phone-close-before-stop-ack case separately from acknowledged teardown.

For `ui`, exit 2 means usage/Python/dependency failure, 3 means device selection or
UUID-to-USB resolution failure, 5 means timeout/cancellation, and 1 means tunnel,
protocol, changed/incomplete graph or cleanup failure. `SMOKE_AX=1` adds the read gate
to the normal smoke matrix; `SMOKE_AX_ONLY=1` runs only that gate.

## AX and XCTest coverage

On the tested 12 mini Settings page, AX returns 13 nodes while XCTest returns 176. The
163 additional entries consist of 121 structural entries, 19 StaticText, 19 Image,
3 Button and 1 Switch. Two residual Buttons are invisible accessible rows; the third is
a duplicate Dictate entry. The 12 nonroot AX frames exactly match XCTest native frames
on this tested page, but equal identifiers/frames do not establish unique object identity.
These counts do not represent 163 missing actions. Richer attributes do not restore that
backing hierarchy: Parent was
absent and navigation children matched ordinary children. The integration exposes the real
AX graph without inventing containers. See [protocol findings](protocol.md#settings-structure-and-richer-attributes-2026-10-12).

Real-device development verification covers macOS 26.5.1 locally and the AX helper on macOS
27.2 through an SSH-forwarded USB connection. The latter host still has Xcode 26.4; this does
**not** close the full supported macOS 27 + Xcode 27 smoke gate. MCP integration and direct
semantic AX actions are not implemented by this command.
