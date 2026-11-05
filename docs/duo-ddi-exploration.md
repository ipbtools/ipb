# Duo DDI / AX exploration

2026-11-05; branch `codex/duo-ddi-exploration`, baseline main `8c227a1` (v0.6.0).
“New” below means newly explored relative to ipb's recorded evidence. This is not
an Apple release-to-release diff. This research makes no product support expansion.

## Current result and implementation direction

The strongest DDI lead is **resizable scene management**. Shipped types, launchd
registration and server implementation strings agree, but no successful host request
or Duo arrangement effect was established. Keep physical layout unavailable.

Main's native AX snapshot is a useful basis for **window-scoped observation**.
It reveals actual window containers, classes, visibility and remote references;
it does not establish global pane coordinates. Prefer selecting a window afresh
inside a command, then reading that subtree, over enlarging the application-wide
budget or exporting reusable native/context IDs. Window/display ownership and
stable selection rules still need evidence before a public window selector.

Main's current `display_geometry` still chooses a portrait primary display;
its hit encoder supplies displayId0. Old Duo schema2 `rawFrame`/AXChildren and
main's schema2 native deep tree are different contracts. Retain main's native
hierarchy, separate supplementary state and conservative one-shot action rules.

## DDI27B52 inventory

Seed: macOS27.2/26B123, Xcode27.2/27B52, CoreDevice651.32.
DDI `iOS_DDI/version.plist`: Public, build189, ProductBuildVersion27B52.
Image: `/Library/Developer/DeveloperDiskImages/iOS_DDI/Restore/022-22446-061.dmg`,
SHA256 `0de55b0ccde9d5790c9c9f4e1a413225443fce7ea75acb503aca11e7d8156646`.
The image was mounted read-only for extraction and detached; simulator runtime
mounts were retained. The main session checked the extracted plists and symbols.

| Path inside DDI / evidence | Confirmed finding | Boundary |
| --- | --- | --- |
| `Library/LaunchDaemons/com.apple.coredevice.dtappserviced.plist`; `Library/Frameworks/CoreDeviceUtilities.framework/CoreDeviceUtilities` symbols; `usr/libexec/dtappserviced` implementation strings | `resizableappmanagement`, `streamresizabilitystate`; typed get scene state, adjust geometry, cancel session and move frontmost apps to a display. Scene state carries cornerRadius and min/max/preferred/resolved sizes. Server has `SBSAppResizingService`, display-keyed session and peer-disconnect cleanup paths. | Both features are in MachServices but absent from `RemoteServices.com.apple.coredevice.appservice.Features`. Routing, wire encoding and effects unverified. Sizes/display IDs are not arbitrary app-window frame enumeration or ordered Duo pane assignment. |
| Same appservice plist | `streamapplist`, `streamprocesslist` are advertised remote features. | Live stream message/reconciliation semantics untested. |
| `Library/LaunchDaemons/com.apple.coredevice.dtdeviceinfod.plist` | `deviceinfo` RemoteXPC service advertises `getdisplayinfo` and `displayinfoupdates`. | Current display query is known; update subscription wire/lifecycle not exercised here. |
| `Library/LaunchDaemons/com.apple.coredevice.dtscreencaptured.plist` | `screencaptureservice` RemoteXPC maps `capturescreenshot`; entitlement `com.apple.private.CoreDevice.canViewDeviceDisplay`. Utilities has optional displayUniqueID input and capture output. | This records the service mapping; it does not introduce app-only/window-only capture. |
| `Library/LaunchDaemons/com.apple.coredevice.dtuhidd.plist` | `remote.hid.keyboard` and `remote.universalhid` map to the same `hid.universalhid` remote service. | No independent keyboard transport follows. `remote.hid.pointer` was not advertised in this plist despite a host Utilities constant. |

No new AXP endpoint was found in this focused **CoreDevice RemoteServices** scan.
Existing raw AX DTX, AXAudit and XCTest evidence remain separate; this is not a
claim that system accessibility services are absent.

Simulator guest metadata confirms `SBSAppResizingService` with `status`,
`acquireAssertionForDisplay:preferredSize:resizingCornerRadius:`,
`moveFrontmostAppsToDisplay:preferredSize:resizingCornerRadius:delegate:` and
assertion-size updates. A read-only status sample stayed `Initializing` over1.5s.
No observer handshake or resize assertion was established. This is inconclusive,
not a measured unsupported state. No geometry mutation was sent. SimulatorKit's
Mac `SimDisplayView.resizeTo(size:)` is not evidence for guest scene resizing.

## Simulator native AX results

Dedicated simulator `1CA07373-09AA-4E38-82BD-937711C73565`, Duo runtime24B91016s,
inner landscapeRight, CoreSimulator1174.21, SimulatorKit1005.14; host
AccessibilityPlatformTranslation591.4.5, UUID16162041-96F3-3F3C-B532-053DED8F2603.
Live simulator displayId3, UUIDBA1145D0-F2C3-4255-93C8-D932122D10D3;
portrait native points669×951, presented951×669, panes469×669 at x0/x482.
These numbers and IDs do not establish physical-device equivalents.

| Experiment | Observation | Implication |
| --- | --- | --- |
| Main type2/attribute52 options via CoreSimulator AXP | Settings224 path records/130 unique handles vs13 AXChildren; Safari492/452 vs22 AXChildren. Overlapping frames agree13/13 and22/22. Child counts agree. Main `snapshot_nodes` accepts both after NSValue/numeric-key conversion. | Native hierarchy is richer than AXChildren. This tests semantic parsing, not main's physical DTX transport or product simulator deep command. |
| Multiple Safari windows | Four `MobileSafariWindow` children share one PID and frame `(0,0,469,669)`; one is visible. Root remains `(0,0,669,951)`. Four terminal foreign `AXRemoteElement` references are preserved. | PID alone is not window identity; neither root nor native frame supplies the right-pane global offset. Remote visibility alone is not owner proof. |
| Bookmarks and window-scoped snapshots | Application tree547 records: main's real512-record guard refuses it without partial output. Request52 on each actual window token returns176 visible-window records and118/118/122 for hidden windows. | A fresh window-subtree request is a demonstrated research path. No production budget/selector change made. |
| Window context and display reads | Host disassembly maps `_windowContextId` to type2/attribute12; observed Settings root/window/button share2778044681. Visible Safari window returns833511562; hidden windows return0. | An additional context discriminator, not a stable reusable scene token. Old window tokens later returned error0/nil. |
| Point hit / frontmost | Correctly rotated native pane centres on display3 hit the expected Settings/Safari PIDs initially; same points on0/1 return error8. Type4 frontmost returns Settings for0/1/3. Adding contextId to type6 still requires native/global transform. | Frontmost is not pane owner selection; contextId does not establish window-local point semantics. |
| Pane exchange | Screenshot shows Safari left/Settings right with unchanged app PIDs. Settings' visible window handle/frame remain unchanged after moving right. | Native frame cannot reveal that movement. One exchanged Safari centre hit failed; no complete post-exchange mapping acceptance claimed. |
| Native press/action5 | Settings Back and Safari Sidebar use two fresh snapshots, live enabled/visible/frame checks and an exact display3 hit. Native true plus separate trees/screenshots prove General and Bookmarks effects. | Specific two-app semantic controls work in this simulator fixture. No generic action/physical acceptance. |
| Native scroll/action11 | Keyboard row moves y668.6667→372 and appears in the independent screenshot. Native true; row handle differs after scrolling. | Effect observed, but not proof of main's same-identity postcondition. No action replay. |

### Stability observations handed to the AX task

- Error0/nil snapshots occur: after opening Bookmarks the next independent read
  recovered; after Safari address focus, requests with native3002 returned nil,
  while a default read once succeeded. Later default reads also returned nil,
  including after pane restoration. The final screenshot shows rendered Safari,
  and final inventory retains the original app PIDs. Cause is unresolved; do not
  attribute this to3002, focus, layout, background policy or permissions yet.
- A focus attempt immediately after dismissal found0 visible targets and refused
  before action submission. A later fresh selection succeeded. Transitional failure
  must stay distinct from a stuck channel or a false success receipt.
- SwiftUI handle replacement after scroll needs a separate same-element contract
  decision backed by reproduction; logical row text and UI effect are insufficient.

The user requested a separate AX stability session. That session now owns this
dedicated simulator; this DDI task has stopped simulator operations. Final layout
is Settings left/Safari right, editing dismissed; final settled screenshot reviewed.
Settings scroll is changed. No physical device, system ipb installation or release
was modified. Product Duo PR remains deferred.

## Evidence / reproduction

Raw evidence, external probe sources/binaries, extracted plists, demangled symbols
and screenshots stay outside Git:
`/Users/borealin/Documents/Codex/2026-11-05/ipb-duo-ddi-exploration/`.
`raw-ddi27b52/` holds the owning Apple metadata. `ax_probe.m` documents exact
CoreSimulator requests; it is a research harness, not the product backend.

Read example (first resolve the current PID in this selected guest):

```sh
E=/Users/borealin/Documents/Codex/2026-11-05/ipb-duo-ddi-exploration
"$E/ax-probe" 1CA07373-09AA-4E38-82BD-937711C73565 snapshot "$PID" '{}'
```

Key samples:01 native/ordinary comparison;04 display hit controls;05/06 context;
07/08 semantic effects;09/11 application/window trees;15–17 focus/nil controls;
19/27 exchange and stale-window reads;25/26 scroll;29 PIDs;30 final screenshot/nil.
