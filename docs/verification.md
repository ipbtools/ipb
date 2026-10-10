# Verification Notes

## Open items — current state (living section)

**Updated 2026-10-11. This section is overwritten; dated records below are append-only.**

The latest 13 Pro AX result is now **native element trees and numerical rectangles through
DevicesApp's raw DTX service**, reached by an ordinary Python client on the existing paired
local-network tunnel. Host is supplementary macOS 26.5.1 / 25F80, Xcode 27 B6 / CoreDevice
642.15; device is iPhone14,2 / iOS 27.0 / 24A437, Developer Mode enabled. No XCTest, Runner,
new phone app, entitlement/signing/security change, VoiceOver operation or new Mirroring login
was used by this client. The supported macOS 27 product gate remains open.

Calculator bulk: **24 nodes / 24 frames**, closed observed child graph, first push about
**1.18 s after subscription**. Native and Python decoders agree. A fresh History-node centre
HID tap opens its **4-node / 4-frame** sheet and the same session pushes the changed tree.
Explicit application reads also match **Settings main 13/13**, **Battery 32/32**, **Home 29/29**.
Ordinary installed **哔哩哔哩 9.13.0** returns **40/40**, including its modal/number keyboard.
A fresh Battery-node tap opens Battery and same-session reads return the new page; screenshots
confirm the actions. This replaces the earlier no-physical-tree/native-rectangle boundary.

**Confirmed selection defect:** automatic bulk and request-type-4 frontmost results on
Home/Settings can instead name unrelated PDUIApp PID 5965. Inspector target/enable controls
leave this unchanged; its native attribute-1102 first-object selection is resolved statically,
but the reason for the wrong native PID is open. **Working alternative:** request-type-6
system hit testing chooses the displayed application's PID on tested pages, followed by
application request type 1 and attribute request type 5. A fully Python control obtains the
Battery graph in **941 ms**, including fresh tunnel/DTX setup and cleanup, excluding imports
and app launch. Automatic Calculator main takes **740 ms**; the third-party graph takes
**1744 ms**. An initial Bilibili launch-splash hit test returns nil/error 8; the later visible
page succeeds. This is a tested strategy, not universal overlay/foreground coverage.

The trees are application AX graphs rather than all UIView/CALayer objects. Arbitrary-app
coverage, overlays/keyboard, rotation, token lifetime, atomic page generations and supported
host validation still need work. Direct AX actions are untested; verified actions use HID.
One History capture's active-session screenshot timed out, although its tree and later
screenshot prove the transition; a later Home active-AX screenshot succeeds. Some stop calls
observe connection closure before acknowledgement. Retain these outcomes, rather than calling
every capture a complete passing run. No production source/CLI/MCP change or smoke gate is claimed.

Inspector's task-port-filtered XADAudit properties/actions and its ordinary Frame omission
remain valid for that separate route. Mirroring/MCK's normal admission/permission obstacles
remain documented, but they no longer block this working DevicesApp path. Existing manual
native-login/account requests are not repeated and no account data is changed.
See [wire/source evidence](protocol.md#devicesapp-ax-over-raw-dtx-2026-10-11),
[current plan](devicehub-alignment.md#ui-context-research) and the
[latest physical record](#2026-10-11--devicesapp-raw-dtx-tree-rectangles-and-explicit-application-control).

### Remaining work, in recommended order

| Item | Current evidence and root-cause status | Owner / next discriminator |
| --- | --- | --- |
| **Supported release matrix gate** | October 10 refresh reaches Mac-M2 on macOS 27.2 / 26B5091g. Its only enumerated /Applications/Xcode*.app reports Xcode 26.4 / 17E192, while devicectl reports 642.15 and LLDB 2100.0.16.4. USB/CoreDevice identifies the allocated 13 Pro, but pairing is unsupported, tunnel unavailable and DDI services unavailable. Earlier isolated build results remain historical. | Agent can diagnose the mixed developer-tool installation; a working Xcode 27/iOS 27 service environment remains unconfirmed. Local macOS 26 validation and static macOS 27 inspection do not close this gate. Native Mirroring has separate account/session prerequisites. |
| **Permission prompts / locked-device behavior** | Remove App Cancel succeeds in both ipb and Device Hub; the blanket system-dialog limitation is withdrawn. Original TCC prompt not recreated. Locked-path error 1016 is recorded; keypair/entitlement mechanism has static evidence, not a complete dynamic causal A/B. | Agent can investigate with the corresponding reproducible device state. User previously requested: “这个问题可能也需要 device hub 测试下才行”. No permanent-impossibility claim. |
| **Scroll parity** | Device Hub targets `0x501` for AbsolutePointer and Scroll. Its synthetic wheel trace produced only zero-motion may-begin. The later mirror test received a precise event with phase=0, momentum=0, dy=-872 and explicitly rejected it as `scroll_unsupported`; the list did not move. Neither run calibrates a physical trackpad. | Agent-fixable after a real reference gesture. Keep synthetic-event limitations separate from physical trackpad deltas, acceleration and momentum; ordinary mouse drag-scroll passed. |
| **Agent observation contract** | `displays --json` and `capabilities --json` are implemented; mirror uses explicit primary nativeSize with bounded refresh. Frame identity/PTS and atomic frame-orientation correlation are still absent. | Agent-fixable: frame envelope and action/observation correlation. UI-tree transport remains a separate research path. |
| **UI element / semantic context research** | DevicesApp raw DTX returns real AX trees/frames on the 13 Pro: Calculator 24/24, History 4/4, Settings main 13/13, Battery 32/32, Home 29/29, ordinary Bilibili modal/keyboard 40/40. Native/Python bulk codecs agree; node-centre HID transitions have screenshot and tree confirmation. Automatic bulk/frontmost can select unrelated PDUIApp; explicit PID reads and system hit-test-derived PID reads work on tested pages. Pure Python fresh-session capture takes 740 ms for Calculator, 941 ms for Battery and 1744 ms for Bilibili. A launch-splash hit test returns nil/error 8 before visible-page success. This is AX graph coverage, not every UIKit view. One concurrent screenshot timeout and stop-ack closure races remain undiagnosed. Earlier Inspector/Mirroring restrictions are separate entry paths. | Agent-fixable: target/overlay coverage, token/page generation contract, persistent-session latency, supported macOS 27 gate, then CLI/MCP integration. Keep one outstanding semantic read and preserve unsolicited packets. Do not use arbitrary first foreground event, replay uncertain input or claim all apps complete. The user chose **“用 13 pro 吧”** and rejected page-wide serial preview. See [current protocol](protocol.md#devicesapp-ax-over-raw-dtx-2026-10-11). |
| **Keyboard and focused text** | `ipb text` clipboard + captured Cmd-V chord inserts exact Unicode in Settings with Pinyin. An iOS paste-permission prompt was also reproduced and allowed once for synthetic test text. rc0 reports submission only; clipboard is replaced. | Implemented scoped text path. Full mirror keyboard capture/general chords remain agent-fixable; secure fields and other applications need their own validation. No automatic permission approval. |
| **Orientation and other Device Hub parity** | Mirror now selects live primary geometry, separates device/content/presentation directions, and maps clicks at all four orientations. Cmd-Left/Right works. Rotated-content edge reports match captured native direction flags; 300 ms landscape probes returned Home, ~6 ms CUA drags did not. | Physical mouse edge timing, rotated physical scroll and atomic external-rotation/frame correlation remain open. Siri/recording/new hardware buttons require effect/capability evidence. |
| **Tap/keyboard timestamp and contact identity** | The ordinary HIDReport builder still had count0 on UP; it now shares the corrected count1 wire builder with Data output. Ordinary max/identity/timestamp differences remain. New rotated-edge reports follow the captured shape including flags/time/identity. | Ordinary field differences remain known, not patched speculatively. Raw swipe probes retain their historical unverified status. |
| **Silent media loss / cold-start budgets** | Static silence is now correctly tolerated; explicit stream/connection errors fail. Silent loss without an error callback remains indistinguishable from idle until content changes. Setup/watchdog margins are policy values without cold-start calibration. | Agent-fixable measurement work; do not treat a frame-count ceiling as an established transport lifetime. |
| **Probe commands and standalone transport** | Raw reports may return 0 without visible effects. Xcode-free Python transport has a spike, not a completed CLI/MCP/screenshot implementation. | Keep probes labelled and stage-4 work separate. |

### Confirmed fixes in the current alignment work

- **Selected display/text/orientation work:** versioned metadata queries, live primary crop,
  focused clipboard paste and four-way mirror transforms are implemented. A malformed `info: []`
  query fixture now fails without crashing; active metadata children cancel on close. The first
  shortcut-during-refresh drop is fixed by retaining only unsent relative intent.
- **Text smoke false pass:** a paste-permission modal passed the pixel-change test. Search-field
  OCR now rejects it and the clipboard suggestion row; failed verification stops before a clear
  coordinate could accidentally select a permission response. Exact emoji/punctuation still need
  visual inspection.
- **Input ownership:** host fault injection reproduced two abandoned calls concurrently entering one
  sender. Per-connection ownership now lasts until the real call returns, with bounded admission
  and shutdown. Report timeouts stay fatal and uncertain input is never replayed. A forced UP cannot
  guarantee device release after a transport failure. After manual Mac unlock, native mouse drag,
  Home/App Switcher shortcuts, bottom-edge Home and normal window close passed on the local host;
  this covers all three sender connections, without claiming physical scroll calibration.
- **Media idle timeout:** stream and mirror both reproduced exit 7 on a static Settings screen.
  Both now survive the idle interval and resume after Home; first-frame, output and overall bounds
  remain. This explains the reproduced idle failure, not every historical media symptom.
- **Smoke false passes:** missing unlock proof and unexplained unchanged frames fail. Real screenshot
  inspection also exposed clock-only false positives and invalid Home-scroll/Escape fixtures; the
  gate now uses a Settings list, an actual search-key effect, and a minimum material pixel change.
  Manual semantic inspection is still required.
- **Trace validity:** all ten breakpoints must resolve and the target resume before readiness is
  announced. Fixed zero-count shell parsing and double-detach failure; decoder exposes target IDs
  and digitizer fields. Actual Device Hub taps, drag, keyboard and safe alert Cancel are captured.
- **Keyboard allocation:** the earlier 39 B fix remains in place and matches the new Device Hub trace.

### Decisions retained

- `TODO(tunnel-keepalive)`: resident `devicectl notification observe` remains the accepted workaround.
  User closed it with **“就维持现状把”**. Do not reopen without new evidence.
- Older per-record “Known, not fixed” claims remain history. This head and the current protocol
  sections supersede stale claims that no Device Hub tap/service target was ever captured.


Host:

- macOS 27 beta
- Xcode 27.0.0 Beta 2
- DeviceHub 27.0 build 244.2.3
- DeviceKit 244.2.0
- CoreDevice/CoreDeviceUtilities 636.3.0

Device:

- iPhone 13 Pro
- iOS 27.0
- Device identifier used during extraction: `<device-uuid>`

Commands verified:

```sh
bin/ipb tap 0.5 0.5
bin/ipb long 0.615 0.675 1.2
bin/ipb scroll 0.5 0.75 0 0.30
bin/ipb swipe 0.5 0.75 0.5 0.35
bin/ipb home
bin/ipb recents
bin/ipb screenshot build/smoke.png
bin/ipb service-ids
bin/ipb descriptors
bin/ipb services
bin/ipb service-id touchscreen
bin/ipb service-id gesture
bin/ipb service-id keyboard
bin/ipb pointer-report 0x501 0 0 0
bin/ipb pointer 0 0
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-event 0 0 0 undefined undefined digital-crown
bin/ipb vendor-defined 0 0 0
bin/ipb key-up
bin/ipb key escape 0.02
```

The original investigation also captured screenshots after each command, but those are intentionally not committed to keep the repository small and reviewable.

Additional protocol probe commands now exposed:

```sh
bin/ipb probe-services
HIDCTL_VERBOSE_DESCRIPTORS=1 bin/ipb descriptors
bin/ipb reset-gesture 0x101
bin/ipb button 0x0c 0x40
bin/ipb keyboard-report 0x200 escape 1
bin/ipb pointer-report 0x501 0 0 0
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-event 0 0 0
bin/ipb vendor-defined 0 0 0
bin/ipb uhid-report 0x101 0.5 0.5 0 0
bin/ipb digitizer-event 0.5 0.5 0 0 1 2 0
bin/ipb digitizer-event 0.5 0.5 0 0 1 end none
bin/ipb raw com.apple.coredevice.feature.remote.hid.digitizer cd_digitizer_ext 0.5 0.5 0 0 1 end none
bin/ipb digitizer-event 0.5 0.5 0 0 1 impossible none -> unknown digitizer event type: impossible
```

`services` is now an alias of the verified descriptor-discovery path. `probe-services` reaches the UniversalHID Mercury peer but does not decode the synchronous `connectedServices` wrapper successfully. The verified DeviceHub discovery path is `descriptors`, which calls `CoreDevice.UniversalHIDService.connectedServiceDescriptors()` through a Swift async ABI bridge and decodes the returned descriptor dictionaries.

After correcting the Mercury `sendSync(value:)` generic argument order, the `probe-services` path no longer hits the previous illegal-instruction crash path. A later guard also prevents the raw Mercury sync probe from trying to bridge a zero-word reply into `NSDictionary`. The remaining result is a remote-level `Connection invalid`, which matches the current hypothesis that DeviceHub uses the async `UniversalHIDService.connectedServiceDescriptors()` path for dynamic descriptor discovery rather than the synchronous typed Mercury path currently exposed by the CLI.

Current probe output:

```text
connected services request: UniversalHIDServiceDDIPayload.Request {connectedServices}
remote event: { "XPCErrorDescription" => "Connection invalid" }
connected services result=1 raw=0000000000000000
```

The experimental `services-async` command was removed from the public wrapper after disassembly showed that the crash was caused by a local ABI mismatch when calling Mercury's generic `send(value:replyQueue:replyHandler:)` overload. The original DeviceHub path should be re-entered through a Swift async CoreDevice shim, not by exposing that unsafe assembly call.

Current `descriptors` output, abbreviated only by omitting raw pointer diagnostics:

```text
connected descriptors count=5
connectedDescriptor[0] serviceID:0x101 string:"CoreDevice touchscreen(nil)"
  PrimaryUsagePage=uint:13
  PrimaryUsage=uint:4
  DeviceUsagePairs=array:[dictionary:{DeviceUsagePage:uint:13, DeviceUsage:uint:4}]
connectedDescriptor[1] serviceID:0x200 string:"CoreDevice keyboard"
  _CoreDevice_originalUsages=array:[dictionary:{DeviceUsage:uint:6, DeviceUsagePage:uint:1}]
connectedDescriptor[2] serviceID:0x402 string:"CoreDevice mainScreenButtons"
  DeviceUsagePairs=array:[dictionary:{DeviceUsage:uint:1, DeviceUsagePage:uint:11}, dictionary:{DeviceUsage:uint:6, DeviceUsagePage:uint:1}]
connectedDescriptor[3] serviceID:0x500 string:"CoreDevice avpCustom"
  PrimaryUsagePage=uint:65377
  PrimaryUsage=uint:91
connectedDescriptor[4] serviceID:0x501 string:"CoreDevice touchscreenGesture"
  DeviceTypeHint=string:"Trackpad"
  RouteEventsIgnoringSystemShellPolicy=bool:true
```

`service-ids` is host-side and does not require an active device socket. It is verified to return `mainTouchscreen = 0x101`, and that resolved value has been used successfully with:

```sh
service_id=$(bin/ipb service-ids | awk '/^mainTouchscreen/ {print $2}')
UHID_SERVICE_ID="$service_id" bin/ipb uhid-report "$service_id" 0.5 0.5 0 0
UHID_SERVICE_ID="$service_id" bin/ipb reset-gesture
```

`UHID_SERVICE_ID=auto` is also verified for role resolution:

```text
bin/ipb service-id touchscreen -> 0x101
bin/ipb service-id gesture -> 0x501
bin/ipb service-id keyboard -> 0x200
bin/ipb service-id buttons -> 0x402
```

Keyboard report verification:

```text
bin/ipb key-up
bin/ipb key escape 0.02
```

`key-up` sends an empty `UniversalHID.KeyboardReport` to service `0x200`; `key escape` sends usage `0x29` down, then an empty release report, followed by a UniversalHID barrier.

Pointer report verification:

```text
bin/ipb pointer-report 0x501 0 0 0
bin/ipb pointer 0 0
bin/ipb pointer-report 0x501 0 0 0 0 0 1
```

The zero-movement pointer reports are non-destructive smoke tests for construction and delivery of `UniversalHID.PointerReport` to the `CoreDevice touchscreenGesture` service. `flags=1` exercises the UInt32-backed `PointerReport.Flags.accelerated` path; other flag bits still need behavior enumeration.

Scroll report verification:

```text
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-report 0x501 0 0 256 -> Unable to build UniversalHID scroll HIDReport
```

The zero-movement scroll report is a non-destructive smoke test for construction and delivery of `UniversalHID.ScrollReport` plus `ScrollCollection` to the `CoreDevice touchscreenGesture` service. The `phase=256` probe verifies local `UInt8` raw-value validation.

Standalone HIDScroll verification:

```text
bin/ipb scroll-event 0 0 0 undefined undefined digital-crown
bin/ipb scroll-event 0 0 0 impossible -> unknown scroll phase: impossible
bin/ipb scroll-event 0 0 0 0x10000 -> HIDScroll raw values out of range
```

The zero-movement scroll event is a non-destructive smoke test for opening `com.apple.coredevice.feature.remote.hid.scroll`, dispatching `CoreDevice.HIDScroll.send(point:phase:momentum:target:)`, and following with `sendBarrier()`. The invalid phase probe verifies shell-side enum-name validation; the out-of-range probe verifies C-side raw-width validation.

Standalone HIDVendorDefined verification:

```text
bin/ipb vendor-defined 0 0 0
bin/ipb vendor-defined 0 0 0 abc -> coredevice vendor-defined: invalid hex payload
bin/ipb vendor-defined 0x10000 0 0 -> HIDVendorDefined raw values out of range
```

The zero-length vendor-defined event is a non-destructive smoke test for opening `com.apple.coredevice.feature.remote.hid.vendordefined`, dispatching `CoreDevice.HIDVendorDefined.send(usagePage:usage:version:data:)`, and following with `sendBarrier()`. The other probes verify payload and raw-width validation before send.

Keyboard / pointer capability adapter verification:

```text
strings -a -t x /Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice | rg 'feature.remote.hid'
```

Observed feature strings in CoreDevice:

```text
com.apple.coredevice.feature.remote.hid.button
com.apple.coredevice.feature.remote.hid.digitizer
com.apple.coredevice.feature.remote.hid.vendordefined
com.apple.coredevice.feature.remote.hid.scroll
```

No `feature.remote.hid.keyboard` or `feature.remote.hid.pointer` string is present on this seed. Runtime metadata shows `UniversalHIDKeyboard` and `UniversalHIDPointer` each have only one ivar, `filter` at offset `0x10`; disassembly of the keyboard witness path shows it constructs a UniversalHID keyboard report and sends through the filter-backed UniversalHID service helper.

DeviceHub / DeviceKit checks performed:

```sh
plutil -p /Applications/Xcode-27.0.0-Beta.2.app/Contents/Applications/DeviceHub.app/Contents/Info.plist
otool -L /Applications/Xcode-27.0.0-Beta.2.app/Contents/Applications/DeviceHub.app/Contents/MacOS/DeviceHub
otool -L /Applications/Xcode-27.0.0-Beta.2.app/Contents/SharedFrameworks/DeviceKit.framework/Versions/A/DeviceKit
strings -a -t x /Applications/Xcode-27.0.0-Beta.2.app/Contents/SharedFrameworks/DeviceKit.framework/Versions/A/DeviceKit | rg 'HIDManager|connectedService|createService|fetchConnectedServiceDescriptors'
nm -gU /Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice | xcrun swift-demangle | rg 'UniversalHIDService|connectedService|createService'
nm -gU /Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework/Versions/A/CoreDeviceUtilities | xcrun swift-demangle | rg 'DDIUniversalHIDServicePayload|HIDServiceDescriptor|HIDServiceID'
strings -a -t x /Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework/Versions/A/CoreDeviceUtilities | rg 'UniversalHIDServiceDDIPayload|createService|removeService|resetGestureState|connectedServices'
```

Findings:

- `DeviceHub` links `DeviceKit`, but the HID manager implementation is in `DeviceKit.framework`.
- `DeviceKit` links `CoreDevice`, `CoreDeviceUtilities`, `UniversalHID`, `HID.framework`, and weakly `UniversalHIDKit`.
- `DeviceKit.HIDManager` has strings and code paths for `fetchConnectedServiceDescriptors(generation:)`, `createService(descriptor:)`, `reset(serviceID:)`, `report(reportID:)`, and local service lookup by `serviceID`.
- `CoreDevice.UniversalHIDService` exposes synchronous report sending/reset/barrier and async descriptor/service discovery.
- `CoreDeviceUtilities` Swift metadata confirms positional coding keys for `DDIUniversalHIDServicePayload.Request`: `createService._0`, `removeService._0`, `send._0/_1`, `resetGestureState._0`, and empty `connectedServices`.
- `CoreDeviceUtilities.DDIUniversalHIDServicePayload.ConnectedServices` wraps `[CoreDevice.HIDServiceDescriptor]`, but DeviceKit's verified runtime path uses CoreDevice's async `connectedServiceDescriptors()` API.
- `CoreDevice.UniversalHIDService.connectedServiceIDs()` is a protocol extension symbol, so it cannot reuse the protocol-requirement async bridge used for `connectedServiceDescriptors()`.

## Compatibility re-check, 2026-09-05

Re-checked after the original beta 2 extraction, because macOS 27 and iOS 27 moved on by several seeds. Two hosts were used.

### macOS 27 beta host (<macos27-host>)

Host:

- macOS 27.0 beta 7 (26A5421a); Software Update also offers beta 8 (26A5425a), not installed
- Xcode 27 beta 6 (27A5252f) at `~/Downloads/Xcode-beta.app`, the newest beta listed by Apple on that date; `/Applications/Xcode.app` is Xcode 26.4
- CoreDevice / CoreDeviceUtilities 642.15, Mercury 78, embedded UniversalHID 90.1
- DeviceHub 255.2.3.5, DeviceKit 255.2.3
- iOS DDI build 1335 (27A5252f), CoreDevice 642.15 inside

Verified there without a device:

- All 113 private symbols the sources bind (link-time `_$s...` references plus the `dlsym` names) still exist in CoreDevice, CoreDeviceUtilities, UniversalHID, and Mercury 642.15/78.
- `make` builds cleanly with `DEVELOPER_DIR` pointing at the beta 6 app, no `XCODE_PATH` override needed after the Makefile default change.
- `bin/ipb service-ids` prints the same service table as on beta 2.
- The `createservicesocket` XPC request shape is still accepted by CoreDeviceService 642.15 when the client reports version 636.3 or 642.15; against an offline paired device the answer is `CoreDeviceError 4000, RemoteServiceDiscovery connectivity is not available`, i.e. the request got past decoding and version checks.
- Passing a UDID instead of the CoreDevice UUID yields `CoreDevice.ActionError: Value for key CoreDevice.deviceIdentifier not found`. The 642.15 `devicectl list devices` table prints UDIDs, so read the UUID from `devicectl list devices --json-output` for `DEVICE_ID`.
- Wire names are unchanged: the host still carries `com.apple.coredevice.hid.universal`; the DDI daemon `dtuhidd` registers `com.apple.coredevice.hid.universalhidservice`, `...hid.universalhid`, and `...hid.indigo` (button, scroll, digitizer, vendordefined) as RemoteXPC services behind the same six feature identifiers.
- Swift layouts the ABI shims depend on are unchanged in 642.15: `DDIUniversalHIDServicePayload.Request` cases are still `createService, removeService, send, resetGestureState, connectedServices` (tag 4 for `connectedServices`), `SendCodingKeys = _0,_1`, `IndigoVendorDefinedEvent = usagePage, usage, version, data`, `IndigoDigitizerEvent = pointOne, pointTwo, eventType, edge, target`. `CoreDevice.CodableValue` cases are `array, bool, data, date, decimal, dictionary, double, error, int, uint, string, url, uuid` in both 518.31 and 642.15, so the tag table in `docs/protocol.md` still holds; note that tag `0x8` is `int` and `0x9` is `uint` (the boxed `HIDServiceID` raw value), both decoded as a boxed 64-bit word.

Not verified there: every command that needs a device. No iOS 27 device was attached to <macos27-host> during the check (its paired iPhone 11 is network-only and offline). Run the following once an iOS 27 device is plugged in:

```sh
export DEVELOPER_DIR=~/Downloads/Xcode-beta.app/Contents/Developer
DEVICE_ID=$(xcrun devicectl list devices --json-output /tmp/d.json >/dev/null && python3 -c 'import json;print([d["identifier"] for d in json.load(open("/tmp/d.json"))["result"]["devices"] if d["connectionProperties"].get("tunnelState")=="connected"][0])')
DEVICE_ID=$DEVICE_ID bin/ipb descriptors
DEVICE_ID=$DEVICE_ID bin/ipb key-up
DEVICE_ID=$DEVICE_ID bin/ipb screenshot build/before.png
DEVICE_ID=$DEVICE_ID bin/ipb home
DEVICE_ID=$DEVICE_ID bin/ipb tap 0.5 0.5
DEVICE_ID=$DEVICE_ID bin/ipb screenshot build/after.png
```

`scripts/smoke_matrix.sh <repo> <out_dir>` runs the non-destructive subset above and captures before/after screenshots; add `SMOKE_INTERACTIVE=1` to also exercise `home`, `tap`, `recents`, `swipe`, `scroll`, `long`, and `key`. The first thing to check in `descriptors` output is that the five services still decode with readable product strings; the `CodableValue` tag table in `docs/protocol.md` is the part most exposed to enum reordering between seeds.

### macOS 26 host (this Mac)

Host: macOS 26.5.1 (25F80), Xcode 26.5 (17F42), CoreDevice 518.31, Mercury 70, iOS DDI build 659 (CoreDevice 518.31). Devices: iPhone 13 Pro on iOS 27.0 (24A5430a, wired, `ddiServicesAvailable: true`) and iPhone 12 mini on iOS 26.5.

Findings:

- `make` fails at link time with 25 undefined symbols: the 12 `HIDServiceID` static getters, the 4 `UniversalHIDService` dispatch thunks, the 2 `HIDVendorDefined` thunks, 4 `DDIUniversalHIDServicePayload` symbols (all CoreDevice/CoreDeviceUtilities 518.31), plus `DigitizerReport.setContactSwipe{Pending,Locked,Up}` from the OS copy of UniversalHID (80). Everything else in UniversalHID resolves against the macOS 26 SDK stub, so the OS-level frameworks are not the blocker.
- Linking the same objects against a copy of the 642.15 CoreDevice, CoreDeviceUtilities, embedded UniversalHID, and Mercury 78 from <macos27-host> succeeds with the Xcode 26.5 toolchain, and the resulting binary loads those frameworks on macOS 26.5.1 (`DYLD_FRAMEWORK_PATH`) and prints the full `service-ids` table. CoreDevice 642.15 declares `minos 14.0` and only depends on OS frameworks that exist on macOS 26.
- The device side is the harder blocker on this host: a `createservicesocket` request for any `feature.remote.hid.*`, `universalhidservice`, or even `viewdevicescreen` returns `CoreDeviceError 1001, The capability "Create Service Socket" is not supported by this device`, for the iOS 27 phone as well as the iOS 26.5 phone. The Xcode 26.5 DDI ships no `dtuhidd`; its CoreDeviceUtilities only carries the older `feature.remote.hid.*` strings. Xcode 27 beta 6's DDI adds `dtuhidd`, `dthidd`, `dtremotedisplayd`, and `dtscreencaptured`.

Conclusion for porting: the tool is tied to the CoreDevice package version, not to the macOS major. Installing Xcode 27 beta (minimum macOS 26.4) on a macOS 26 host brings CoreDevice 642.x, the embedded UniversalHID, and the DDI with `dtuhidd`, after which the same sources should build and run. Whether the beta DDI also enables the HID services on an iOS 26 device is untested.

## Device verification, 2026-09-07

Both hosts run Xcode 27 beta 6 (27A5252f) and CoreDevice 642.15; both devices run iOS 27.0 (24A5430a) with the beta 6 DDI (CoreDevice 642.15, `dtuhidd` present).

| Host | Device | Result |
| --- | --- | --- |
| <macos27-host>, macOS 27.0 beta 8 (26A5425a) | iPhone 12 mini, wired | `scripts/smoke_matrix.sh` interactive: all 39 steps rc 0 and expected output. Screenshots: `tap 0.15 0.12` launched Calendar, `recents` showed the App Switcher, `home` returned to SpringBoard, swipe/scroll on the home screen pulled down Spotlight, `long` while Calendar was foreground coincided with its location prompt. |
| This Mac, macOS 26.5.1 (25F80) | iPhone 13 Pro, wired | Same 39 steps rc 0. The icon at (0.15, 0.12) was an unverified developer build, so the tap raised the "无法验证 App" system alert, which Home cannot dismiss; `key escape` cleared it. Non-destructive gate re-run passes. |

Behaviour established on both hosts:

- Every HID socket needs `tunnelState = connected`. A freshly attached or idle device answers `createservicesocket` with CoreDeviceError 4000; the helper now exits 4 and the wrapper warms the tunnel once via `devicectl device info details` and retries. One warm-up happened per smoke run.
- The helper exits non-zero on a refused socket (3), on any dispatch result other than 0 or a remote error while the connection is active (1), and on the watchdog (5). Before this change every failure exited 0, which is why the first smoke run on 2026-09-07 looked green while every HID request was failing.
- `devicectl` from `/Library/Developer/PrivateFrameworks/CoreDevice.framework/Resources/bin` is enough for screenshots; no `DEVELOPER_DIR` is needed at runtime.
- Decoded `descriptors` fields now print `int:` for tag 0x8 and `uint:` for tag 0x9; the `serviceID:0x…` label is derived from the `_ServiceID` field.

Pairing note: a phone that has never trusted the host shows up in `devicectl list devices` only as a bare ECID row with no state, and `devicectl manage pair` reports that only a `RestorableDeviceRef` representation exists, until the phone is unlocked and the Trust prompt is accepted.

Xcode-free client spike (see `docs/standalone-distribution.md`): with pymobiledevice3 11.8.0 and its userspace tunnel, and no CoreDevice host stack in the loop, `dtuhidd` on the iPhone 13 Pro answered `connectedServices` with the same five services, and two raw `send` dictionaries (digitizer report id 0x09, 40 bytes) tapped the App Library search field at (0.15, 0.12). The `{isBarrier: true}` message got no reply within 5 s over that path.

## iOS 26 device with the Xcode 27 DDI (answered 2026-09-07)

Host <macos27-host> (macOS 27.0 beta 8, Xcode 27 beta 6, CoreDevice 642.15), device iPhone 15 Pro on iOS 26.6.1 (23G83), USB, previously paired.

- `devicectl device info ddiServices` mounted the beta 6 DDI (`buildUpdate 27A5252f`, `CoreDevice-642.15`, `isUsable: true`, `contentIsCompatible: true`). `dtuhidd` is built with `LC_BUILD_VERSION minos 17.0`, consistent with running there.
- `descriptors` returns **four** services on iOS 26: `0x101 touchscreen(nil)`, `0x200 keyboard`, `0x402 mainScreenButtons`, `0x500 avpCustom`. The `0x501 touchscreenGesture` service present on both iOS 27 phones is absent, so `service-id gesture`, `pointer`, and `scroll-report` fail with exit 3 (unresolved role). The smoke gate now skips those steps when the service is missing.
- Everything else passed: key-up, scroll-event, vendor-defined, reset-gesture, screenshot, and the full interactive set with all 13 frames distinct; `tap 0.15 0.12` launched the top-left app (Days Matter), `recents` showed the App Switcher, `home` returned to SpringBoard.
- Earlier attempt over the local network on an iOS 26.6.1 iPhone 11 failed at DDI mount (CoreDeviceError 12040); the difference was the transport, not the OS.

Conclusion: the framework does not require iOS 27 on the device. With the Xcode 27 DDI, iOS 26.6.1 supports the touchscreen, keyboard, button, Indigo digitizer/scroll/vendor paths; only the trackpad-style `touchscreenGesture` service is iOS 27-specific. Older iOS versions are untested; `dtuhidd`'s `minos 17.0` is a build fact, not a verified matrix entry.

## Rename to ipb and gate hardening (2026-09-07, evening)

The CLI is now `bin/ipb` (helper `ipb-helper`, env `IPB_HELPER`), version 0.1.0 (`ipb version`), with `make install PREFIX=` producing `bin/ipb`, `libexec/ipb-helper`, `share/ipb/`, and a Homebrew tap formula in `Formula/ipb.rb`. The installed layout was exercised from a scratch prefix on this Mac against the iPhone 13 Pro: `SMOKE PASSED`.

Gate incident worth keeping: the first run of the renamed gate on <macos27-host> reported `touchscreenGesture service present: 0` for the iOS 27 iPhone 12 mini and skipped the gesture steps, although a direct `ipb descriptors` call showed all five services. Cause: the gate probed capabilities with a second `descriptors` call whose stderr was discarded; on <macos27-host> the tunnel now drops between consecutive calls (every call logs a warm-up), that probe failed, and its failure was read as "service absent". Fix: capabilities are derived from the descriptors step that already passed, the device OS major comes from `ipb devices`, and an iOS 27 device without the gesture service is a failure instead of a skip. Re-run after the fix: 13 Pro (this Mac) and 12 mini (<macos27-host>) report `present=1 expected=1`, the 15 Pro on iOS 26.6.1 reports `present=0 expected=0` with the two gesture steps skipped; all three `SMOKE PASSED`.

Observation, not yet root-caused: with two phones attached to <macos27-host>, `tunnelState` returns to `disconnected` within seconds of each command, so nearly every `ipb` invocation there pays one warm-up (2–3 s). On this Mac with one wired phone the tunnel stayed up between calls earlier in the day.

## devicectl-backed verbs (2026-09-07, iPhone 13 Pro iOS 27.0, this Mac)

`ipb` now wraps devicectl behind adb-style verbs. Checked against the iPhone 13 Pro:

| Verb | Result |
| --- | --- |
| `apps`, `ps`, `info`, `lock-state`, `orientation` | listings returned |
| `clipboard set "ipb 你好 🚀"` then `clipboard get` | round-trips UTF-8 text, the intended Unicode input path |
| `open https://www.apple.com`, `launch com.apple.Preferences` | opened Safari / Settings (screenshot) |
| `location 37.3349 -122.0090`, `location clear` | accepted; negative values must be passed as `--longitude=-122.009`, which the wrapper does |
| `ls / --app ai.looktech.glasses.memo.lab`, `push` / `pull` round trip | 477 files listed, file content identical after pull |
| `ls / --app com.apple.Preferences` | refused (`ContainerLookupErrorDomain error 2`): system app containers are not reachable |
| `screenrecord out.mp4 3` | devicectl requires `.mp4`; the device then answers `Screen Recording is not supported by this device` (CoreDeviceError 1001). Verb kept, passes the error through |

## Rename to ipb (2026-09-07, late)

`hdb` was too close to HarmonyOS's `hdc`, so the tool is now `ipb` (iOS Physical-device Bridge): `bin/ipb`, `ipb-helper`, `IPB_HELPER`, `Formula/ipb.rb`, org `ipbtools`, tap `ipbtools/homebrew-ipb`. Dated records above keep their original command names. Availability was checked on Homebrew, PyPI, npm, crates.io, GitHub, and the local command namespace before choosing.

Lock-screen finding (15 Pro, <macos27-host>, ipb run): the phone auto-locked between steps 07 and 08, so the remaining gestures were delivered to the passcode screen, every step still returned 0, and the frames repeated. `ipb lock-state` reports `passcodeRequired: true` in that state; the gate now checks it before the interactive block and fails with "device is locked" instead of grading gestures against the lock screen. Keep test phones on auto-lock "never" while a gate runs.

## `ipb doctor` (2026-09-07, late)

Layered self-check added: local install → Apple host stack → device enumeration/selection → DDI → lock state → HID descriptor set (which warms the tunnel). Exercised in four states: 13 Pro on this Mac (all PASS, 5 services); bogus `DEVICE_ID` (FAIL at selection, device checks skipped, exit 1); <macos27-host> with three reachable devices and no `DEVICE_ID` (FAIL at selection listing the candidates); 15 Pro on iOS 26.6.1 (PASS with the four-service set and an INFO line that gesture services are iOS 27 only; transport WARN because it was on the local network at that moment).

## Clean first-use through Homebrew (2026-09-07, this Mac)

This Mac had never had ipb installed (only the scratch builds). Sequence and timings, with `xcode-select` still on Xcode 26.5 and the CoreDevice 642.15 package present from the Xcode 27 beta 6 install:

- `brew install --HEAD ipb` was refused with "untrusted tap" until `brew trust ipbtools/ipb`; the docs now include that step.
- After trusting: fetch + `make` + `make install` in 11 s; `/opt/homebrew/bin/ipb` reports `ipb 0.1.0 (macOS 26.5.1 25F80, CoreDevice 642.15)`.
- `ipb doctor`: 0 failures in 2 s.
- First real loop (`home`, `screenshot`, `tap 0.15 0.12`, `screenshot`, `home`): 8 s, before/after screenshots differ.
- The installed `share/ipb/smoke_matrix.sh` run interactively against the iPhone 13 Pro: `SMOKE PASSED`.

Stage 1–2 "out of the box" items now all have evidence: install path, doctor, gate, and first-use loop. Not covered by this run: a machine without the CoreDevice package (doctor's Apple-stack FAIL lines are the intended path there, untested end to end).

## 2026-09-07 (night) — live-stream standalone-client blocker root-caused

Host Mac (macOS 26.5.1, Xcode 27.0 b6, CoreDevice 642.15). No device command run; static + spike-crash analysis only.

- Symbolicated `~/Library/Logs/DiagnosticReports/spike3-2026-09-07-215613.ips`: `supportInfo.getter` -> `MediaStreamFunctions.mediaStreamSupportInfo` -> `ActionDeclaration.forward(to:)` -> `OSAllocatedUnfairLock.read()` -> `EXC_BAD_ACCESS 0x00f0000000008068`. Async ABI honoured; fault is an uninitialised-coordinator lock, i.e. missing client bootstrap.
- `DeviceKit.DeviceKitContext.deviceManager` returns `CoreDevice.DeviceManager`; DeviceKit is the only Xcode 27 b6 binary linking `CoreDeviceMediaStreamSupport`.
- Probe `scratchpad/dkctx/probe.swift`: `DeviceKitContext.current` resolves standalone (metadata size 48, live first word). A follow-up probe reading the manager pointer SIGBUSed — confirms further progress needs more private Swift ABI shims (AGENTS rule 2 stop condition; two gpt-6-astra reviews concur).
- Conclusion: no self-owned smooth mirror that is both stable and shippable; decision surfaced to user. Details in `docs/video-stream.md` "Standalone Apple-client blocker".

## 2026-09-08 — track C (inject DeviceHub) blocked by library validation

Host Mac (macOS 26.5.1, Xcode 27 b6), iPhone 13 Pro (iOS 27.0) attached, SIP disabled.

- Built ad-hoc arm64e frame-tap dylib (`scratchpad/inject/dhframetap.dylib`): swizzles `-[CALayer setContents:]`, dumps first frames, backtraces once.
- Launched DeviceHub with `DYLD_INSERT_LIBRARIES` (verified in process env via `ps eww`). dyld loaded 1242 libraries but never our dylib; no AMFI/sandbox denial surfaced. Same dylib loads into a fresh unsigned arm64e binary (`DYLD_PRINT_LIBRARIES` shows it).
- DeviceHub CodeDirectory `flags=0x2000 (library-validation)`; `nvram boot-args` empty. Conclusion: library validation blocks the insert; SIP-off does not relax it. Needs `amfi_get_out_of_my_way=1` + reboot, or Apple-team signing.
- Non-injection fallback identified: ScreenCaptureKit capture of DeviceHub's mirror window.

## 2026-09-08 (cont.) — injection works after AMFI boot-arg; frames are window-composited

Same host, iPhone 13 Pro (iOS 27.0), after `sudo nvram boot-args="amfi_get_out_of_my_way=1"` + reboot.

- Injection now succeeds: `DYLD_INSERT_LIBRARIES` dylib loads into DeviceHub (`vmmap` shows it mapped, constructor runs, swizzle installs). Confirms library validation was the only wall; the AMFI boot-arg removes it.
- `devices://device?id=<UUID>&action=select` DOES drive device selection: window title changed to "iPhone 13 Pro – iOS 27.0". Headless device selection confirmed.
- Frame source: NOT at `-[CALayer setContents:]`. The mirror layers (`DeviceKit.ChromeRenderLayer` 243x477 = bezel; a plain `CALayer` 259x582 = screen area; `SwiftUI.ImageLayer`) set contents once, and `isIOSurface=0 isMetal=0` — the decoded video is composited by the window server, not exposed at the layer's `contents`. `AVSampleBufferDisplayLayer.enqueueSampleBuffer:` never fires either.
- In-process window capture via `CGWindowListCreateImage` (dlsym; removed from macOS 26 SDK) returns "no own window" — sandbox/TCC filters the window list for the sandboxed app. Dead end from inside.
- Remaining frame paths: (A) hook the Swift `CoreDeviceMediaStreamSupport` decoded-frame callback `VideoStreamEvent.receivedLastDecodedFrame(Data)` / `requestLastDecodedFrame` (clean pre-composite frame + metadata; fragile Swift-ABI interpose, Experiments-only); (B) ScreenCaptureKit capture of DeviceHub's window from a separate helper (robust, needs neither injection nor the AMFI reboot, but captures chrome and loses per-frame metadata).

## 2026-09-08 (cont.) — decoded frames render cross-process; in-process capture walled

Injected into DeviceHub (arm64e), 13 Pro iOS 27.0 live mirror confirmed on screen.

- Mapped the frame architecture from inside the process (runtime ObjC introspection):
  - Video layer contents = `CASlotProxy` (one `_proxy` void*, `CA_copyRenderValue`, no surface accessor) = a render-server slot handle, not an in-process pixel buffer.
  - `AVCRemoteVideoClient` renders via `createCALayerHostForRootLayer:withContextId:`, `insertSubLayerInLayer:videoMode:videoSlot:`, `newXPCObjectForFenceHandle:` — i.e. the remote video is decoded/composited in a SEPARATE media-service process and hosted into DeviceHub as a remote CALayer by context id. **The per-frame pixels are never in the DeviceHub process.**
  - Confirms: `-[VCVideoStreamReceiver showDecodedFrame:atTime:]` (swizzled) never fires in-process; `-[...VideoStreamReceiveHelperAVC stream:didGetLastDecodedFrame:]` (swizzled) only fires on an explicit PULL, which DeviceHub does not do during normal mirroring.
- The one in-process frame path is the on-demand pull `requestLastDecodedFrame` (Swift) → delivered via the hooked `stream:didGetLastDecodedFrame:` (gives a real frame + metadata). No ObjC trigger exists (AVCRemoteVideoClient / the receive helper have none); DeviceHub triggers it only from a SwiftUI screenshot control (no reachable selector; menus are SwiftUI closures).
- Net: clean SMOOTH in-process live capture via DeviceHub injection is architecturally blocked (pixels are cross-process). Remaining: (A') drive the Swift `requestLastDecodedFrame` pull on a timer for on-demand real frames (fragile Swift call, but inside a fully-bootstrapped DeviceHub it has the context the bare-process spike lacked); (A'') inject the media-service process where pixels live; (B) ScreenCaptureKit window capture (smooth, chrome+crop, no metadata, separate process).

## 2026-09-08 (cont.) — standalone receiver: transport works, device rejects start with GKVoiceChat 32033

Host Mac (macOS 26.5.1, Xcode 27 b6), iPhone 13 Pro iOS 27.0, live tunnel `fdXX:XXXX:XXXX::1` (device) / `::2` (host) on `utun10`.

- New standalone experiment `Experiments/videostream/receiver.m` (all ObjC/C, no Swift shims): loads CoreDevice+AVConference, `_coredevice_xpc_init_services`, `AVCMediaStreamNegotiator createOffer` (538 B), opens `createservicesocket` for `com.apple.coredevice.feature.startmediastream`, binds an AF_INET6 UDP socket on the host tunnel addr, sends `mediastreamstart`.
- **Transport bind SUCCEEDS**: `bind [fdXX:XXXX:XXXX::2%utun10]:<ephemeral>` returns 0. The earlier `EADDRNOTAVAIL(49)` was purely the STALE hardcoded address (`fdd2:.../utun9`); with the live tunnel address it binds fine. The "transport can't be bound" wall is gone.
- **Device rejects `mediastreamstart`**: `CoreDevice.error` code `32033` domain `GKVoiceChatServiceErrorDomain`, userInfo `NSErrorUserInfoDetailedError = 7`, no reason string. Reproducible, clean device state (no DeviceHub running). So the control path works and the device processes our start; the rejection is at AVConference media negotiation.
- Oracle attempts to capture DeviceHub's WORKING `mediastreamstart` all failed: DYLD_INTERPOSE misses CoreDevice-internal calls; fishhook GOT-rebind (rebound 1102 images) also misses, because CoreDevice is in the dyld shared cache (inter-image calls prelinked/direct, no GOT entry); and DeviceHub does the negotiation out-of-process in `avconferenced` (its in-process `AVCMediaStreamNegotiator` hooks never fire). `avconferenced` is signed flags=0x0 (no library validation) so it is injectable, but it is a root launchd daemon.
- Open: crack `GKVoiceChat 32033 / detailed 7`. Candidates: (a) inject/observe `avconferenced` to capture the working negotiation params; (b) incorporate `mediastreamgetsupportinfo` output into the offer / fix negotiator mode+options; (c) decode AVConference error 32033.

## 2026-09-08 (cont.) — standalone start negotiation: down to options CodableValue encoding

Same host/device/tunnel. `Experiments/videostream/receiver.m` now drives the negotiation and the errors advance layer by layer as fields are corrected:

- Negotiator mode matters: `initWithMode:1` (send) -> device `GKVoiceChatServiceError 32033/7`; `mode 2` (receive) -> CoreDevice-level errors (correct mode). `mode 0/3` -> negotiator init fails `32032`.
- Mode 2 offer is a bplist with keys `avcMediaStreamOptionCallID`, `avcMediaStreamOptionRemoteEndpointInfo`, `avcMediaStreamNegotiatorMode`(=2), `avcMediaStreamNegotiatorMediaBlob`. The negotiator's `_dataSessionID` == the offer's `avcMediaStreamOptionCallID` (same UUID) — so CallID == ClientSessionID == the negotiator session id, read from the negotiator after `createOffer`.
- Empty `options` -> `CoreDeviceError 9005 "Missing ClientName, CallID, or ClientSessionID. Invalid Options passed."`
- `options` with plain-string CallID/ClientSessionID/ClientName -> `NSCocoaError 4864` (NSCoderReadCorruptError), `NSDebugDescription "dictionary required here"`, `NSCodingPath [options, CallID]` — i.e. the device decodes `options` as CoreDevice `[String: CodableValue]` and CallID's value must be a CodableValue dictionary, not a raw string.
- Wrapping each value as `{"string": <value>}` (the documented CodableValue wire shape, protocol.md) -> back to `9005 "Missing"`. So the exact CodableValue encoding for the options values is not yet right (key name / case-index / value shape). This is the current, narrow blocker; everything upstream (transport bind, control socket, negotiation mode, offer, session/call id) now works.

Next: pin CoreDevice.CodableValue's Codable encoding (CodingKeys) for a string case, or capture MSS's exact options dict; then re-send and expect an answer + RTP, then hand the socket to AVCVideoStream (RunInProcess) for in-process decode.

## 2026-09-08 (cont.) — CodableValue encoding solved; start still blocked at option validation

Same host/device/tunnel. All findings below are reproducible with `Experiments/videostream/receiver.m`.

**Solved (empirically, by sweeping against the device):**
- CoreDevice `CodableValue` XPC wire encoding is a single-key dict keyed by the case name. Sweeping candidate keys, ONLY these decode (anything else returns NSCocoaError 4864 "dictionary required here"): `{"string": <string>}`, `{"int": <int64>}`, `{"bool": <bool>}`. (`str/text/value/uuid/uuidString/_0/object/data/integer/number` all fail.) This confirms and sharpens `protocol.md`'s note.
- `CoreDevice.DeviceMediaStream.StartRequest` schema (from CoreDeviceUtilities symbols): `init(timeout: UInt, type: StreamType, direction: Direction, negotiatorOffer: Data, clientSupportedFeatures: UInt64, receiverIP: String?, receiverPort: UInt16?, options: [String: CodableValue], sessionEventChannel: Mercury.XPCSideChannel?)`. Note there is NO senderIP/senderPort in the schema.
- The AVConference option key constants (scanned from AVConference `__cstring` in memory, since it is shared-cache only): `avcMediaStreamOptionCallID`, `avcMediaStreamOptionClientName`, `avcMediaStreamOptionClientSessionID`, `avcMediaStreamOptionClientPID`, `avcMediaStreamOptionIsOriginator`, `avcMediaStreamOptionRunInProcess`, `avcMediaStreamOptionDelayNWConnectionStart`, `avcMediaStreamOptionRemoteEndpointInfo`; plus a `vcMediaStream*` family incl. `vcMediaStreamCallID/ClientName/ClientSessionID`.
- The validator is `validateAVCStreamOptions(_:)` in MSS (stripped symbol; located by xref to the error string at MSS `0x127a4`). The literal `CoreDeviceScreenSharing` is referenced in the same function (`0x12410`) and is very likely the expected ClientName value. It logs `"Missing required options: %{public}s"`, which NAMES the missing keys — but that log lands in the DEVICE's syslog.

**Still blocked:** `mediastreamstart` returns `CoreDeviceError 9005 "Missing ClientName, CallID, or ClientSessionID. Invalid Options passed."` regardless of: every key spelling tried (ClientName/clientName/avcMediaStreamOptionClientName/vcMediaStreamClientName and the CallID/SessionID equivalents, including a 14-key shotgun setting all variants at once), every ClientName value tried (ipb/DeviceHub/com.apple.dt.Devices/Xcode/CoreDevice/CoreDeviceScreenSharing), and with the full option set (ClientPID/IsOriginator/RunInProcess) added. Passing the AVC options to `AVCMediaStreamNegotiator initWithMode:options:` did NOT change the offer (still 543 bytes), i.e. the negotiator ignored them.

Inference (NOT yet proven): the device rebuilds its AVC options from the negotiator OFFER rather than from our `options` dict, so the offer must carry ClientName/ClientSessionID — and the way to put them there is not `initWithMode:options:`. Candidates to investigate: `initNegotiatorLocalConfiguration:options:`, `processOffererInitOptions:errorReason:` on the negotiator.

**Deterministic next step:** read the device syslog while sending the start; `validateAVCStreamOptions` logs the missing option names verbatim. `devicectl` has no console subcommand; use pymobiledevice3 `syslog live` (not currently installed; the previous venv was wiped by the reboot). Stop brute-forcing key names until that log is read.

### 2026-09-08 (cont.) — 9005 exhaustion round: additional negative results

- `AVCMediaStreamNegotiator initWithMode:2 options:{...}` demonstrably IGNORES the AVC options: adding `avcMediaStreamOptionClientName/ClientSessionID/ClientPID` and `AVCMediaStreamNegotiatorTransportProtocolType/AccessNetworkType` (swept values 0/1/2 x 0/1) leaves the offer at 542-544 bytes (jitter only from UUID/media-blob variance), never a structural change. So options are not reaching the offer via that initializer.
- Device-log routes are all closed on this seed: macOS 26's `log stream` has no `--device` flag; `devicectl diagnose` and `devicectl device sysdiagnose` both fail with `CoreDeviceCLISupport.DiagnoseError error 0` (empty/partial archive). pymobiledevice3 is not installed (venv wiped by the reboot) and on iOS 27 would need its own RSD tunnel, risking the working CoreDevice tunnel.
- Reconfirmed the 4864-vs-9005 boundary: plain-string option values give 4864 with coding path exactly `[options, CallID]`; `{"string":...}` values give 9005. So `options` IS decoded as `[String: CodableValue]` and our keys are seen, yet the semantic layer still reports all three missing — pointing away from key naming and toward the device rebuilding its AVC options from somewhere else (likely the offer).

Stopped brute-forcing per rule 3; dispatched a gpt-6-astra disassembly review of how MSS constructs `StartRequest.options` (brief: scratchpad/astra_9005_brief.md).

## 2026-09-08 — BREAKTHROUGH: standalone RTP stream negotiated with no DeviceHub

Host Mac (macOS 26.5.1, Xcode 27 b6), iPhone 13 Pro iOS 27.0, tunnel `fdXX:XXXX:XXXX::1`/`::2` on `utun10`. Reproduced 3/3 consecutive runs with `Experiments/videostream/receiver.m` (pure C/ObjC, no Swift shims, no DeviceHub, no injection).

```
offer: 480-481 bytes
RTP socket bound OK: [fdXX:XXXX:XXXX::2%utun10]:<ephemeral>
options: ClientSessionID=.uuid(<UUID>)
*** RTP RECEIVED: 123 bytes from [fdXX:XXXX:XXXX::1]:<port>  hdr: 90 64 6d 6e
answer: YES (430-432 bytes)
setAnswer=1 err=nil ; config=<ptr> err=nil ; initOptions=<ptr> err=nil
```

The two errors that had blocked this for the whole session, both found by gpt-6-astra disassembly (`docs/research/standalone-9005-astra-2026-09-08.md`):

1. **Negotiator mode was wrong.** AVC settings are selected by `(mode-1)` into a class table (AVConference `0x1E727C030`): mode 2 = `AirplayMirroring`, **mode 5 = `CoreDeviceScreenSharing`**, mode 6 = `CoreDeviceSystemAudio`. MSS's negotiator factory (MSS `0x13984`) does `mov w8,#5 ; cinc` — video -> 5, non-video -> 6. Mode is NOT a send/receive direction. Using mode 2 produced the AVConference 32033 / 9005 dead ends.
2. **`ClientSessionID` must be `CodableValue.uuid(Foundation.UUID)`, a native XPC UUID** (`xpc_dictionary_set_uuid(cv,"uuid",bytes)`), not a string. The earlier CodableValue key sweep never tested this because the test helper always called `xpc_dictionary_set_string`, so `{"string":...}`/`{"int":...}`/`{"bool":...}` were the only shapes probed.

Also corrected: the primary-screen receive path's `StartRequest.options` carries **only** `avcMediaStreamOptionClientSessionID`; `ClientName` (fixed value `CoreDeviceScreenSharing`) and `CallID` are produced later by the negotiator/MSS on the AVC-init side, not sent in the start request. And `senderIP`/`senderPort` DO exist in the real wire model (`CoreDeviceUtilities.MediaStreamStartParameters`), despite being absent from the `StartRequest` Swift signature.

**Status: the device now streams RTP to a socket we own, in our own process, with the full negotiation (offer -> start -> answer -> setAnswer -> configuration -> init options) completing cleanly.** Next: hand the bound socket to `AVCVideoStream` via `xpc_dictionary_set_fd(...,"avcKeySharedSocket",fd)` with `initWithNetworkSockets:options:error:` (RunInProcess) + `configure:` + `setDelegate:` + `start`, and catch decoded frames in-process.

## 2026-09-08 — MILESTONE: full in-process H.265 decode of the iPhone screen, no DeviceHub

Host Mac (macOS 26.5.1, Xcode 27 b6), iPhone 13 Pro iOS 27.0, tunnel `fdXX:XXXX:XXXX::1`/`::2` on `utun10`. `Experiments/videostream/receiver.m` (pure C/ObjC), run with `STAGE2=1`.

The complete pipeline now runs inside our own process:

1. raw XPC `createservicesocket` -> RemoteXPC to `dtremotedisplayd`
2. `AVCMediaStreamNegotiator initWithMode:5` (CoreDeviceScreenSharing) -> `createOffer`
3. our own AF_INET6 UDP socket bound on the host tunnel address
4. `mediastreamstart` with `options = {avcMediaStreamOptionClientSessionID: .uuid(<UUID>)}` -> device returns a negotiator answer
5. `setAnswer:` -> `generateMediaStreamConfigurationWithError:` -> `generateMediaStreamInitOptionsWithError:`
6. MSG_PEEK the first RTP datagram to learn the device's RTP source, then `connect()` the socket to it
7. `xpc_dictionary_set_fd(socks,"avcKeySharedSocket",fd)` -> `-[AVCVideoStream initWithNetworkSockets:options:error:]` with `avcMediaStreamOptionRunInProcess=YES` -> `configure:` -> `setDelegate:` -> `start`

Result (AVConference ViceroyTrace logs from our own pid):

```
_VCVideoStream_DidReceiveRemoteFrame: remoteVideoAttributes:[ratio:1184.00x2576.00
    orientation:Portrait videoSourceScreen:YES videoMirrored:NO ...]
VCVideoStream-DidReceiveRemoteFrame ... received first remote frame frameTime=1.150000
VTP Recv packet count:[515] byte count:[519105] interval:5.011s rate:[828.707]kbps
VCVideoPlayer Health: numAlarmsEnqueuedForDecode=297 numAlarmsProcessedForDecode=297
    numAlarmsProcessedForDisplay=296 numAlarmsDropped=0
AppleAVD: AppleAVDWrapperHEVCDecoderCreateInstance ... codecType: HEVC
```

So the device's screen is negotiated, streamed over RTP to a socket we own, and **hardware-decoded (HEVC) in our process at ~30 fps with correct resolution and orientation, with zero DeviceHub involvement and no Swift ABI shims.** `shouldRunInProcess=1`, `configure -> 1`, `stream:didStart:1 error:nil`.

**Remaining gap: extracting the decoded CVPixelBuffer.** The decoded frames go from the AppleAVD hardware decoder straight into AVConference's `VCImageQueue` (a FigImageQueue destined for a CALayer/CAContext), bypassing every ObjC seam tried. Hooks installed but never fired: `-[VCVideoStreamReceiver showDecodedFrame:atTime:]`, `decodeFrame:showFrame:`, `-[VCVideoStream onVideoFrame:frameTime:attribute:]`, `sendLastRemoteVideoFrame:`. Confirmed dead end: `-[AVCVideoStream requestLastDecodedFrame]` logs `only supported in the daemon` in RunInProcess mode (matches the earlier disassembly).

Next candidates for the frame tap: attach our own CALayer via `VCImageQueue configureCALayerWithRect:name:` / the `vcMediaStreamVideoBufferDescription` config key so frames land somewhere we can read; or intercept the decoder output (AppleAVD / VideoToolbox decompression callback) rather than an ObjC seam.

## 2026-09-08 — GOAL REACHED: standalone JPEG frames of the iPhone screen, no DeviceHub

Host Mac (macOS 26.5.1, Xcode 27 b6), iPhone 13 Pro iOS 27.0, tunnel `fdXX:XXXX:XXXX::1`/`::2` on `utun10`.
`Experiments/videostream/receiver.m`, ad-hoc signed with `Experiments/videostream/receiver.entitlements`, run `OOP=1 STAGE2=1`.

```
shouldRunInProcess=0
configure -> 1 err=nil
DELEGATE stream:didStart:1 error:nil
*** DELEGATE didGetLastDecodedFrame: class=__NSCFData
*** wrote raw frame /tmp/ipbframe_raw000.bin (315890 bytes)
... x3, distinct md5s, EXIF datetime 3 s apart
file: JPEG image data, JFIF 1.01, baseline, 1184x2576, components 3
```

The frames are **ready-to-use baseline JPEGs of the device screen at native resolution**, visually verified (iOS Settings > General, status-bar clock matching the EXIF timestamp). Pulled on demand via `-[AVCVideoStream requestLastDecodedFrame]` -> delegate `stream:didGetLastDecodedFrame:`.

**The two modes, and why the product uses out-of-process:**
- `avcMediaStreamOptionRunInProcess = YES`: RTP + HEVC decode run in our process (verified earlier: ~828 kbps, 297 frames, AppleAVD HEVC). But the decoded buffers go straight into `VCImageQueue`'s CoreAnimation slot (`createSlotAndConnectCAQueue`, `layerHost=0`, `streamOutput=nil`), and `requestLastDecodedFrame` refuses with `only supported in the daemon`. Installing our own `VCStreamOutput` after init does not divert frames because the CA slot is wired inside `init`. No ObjC seam carries the pixels (`showDecodedFrame:atTime:`, `decodeFrame:showFrame:`, `onVideoFrame:frameTime:attribute:`, `sendLastRemoteVideoFrame:`, `VCStreamOutput didReceiveSampleBuffer:` all hooked, none fire).
- `RunInProcess = NO` (out-of-process, decode in the always-running system daemon `avconferenced`): `requestLastDecodedFrame` works and delivers JPEG `NSData` to our delegate. **This is the working path.**

**Entitlement is a hard gate, and this is the honest distribution caveat.** Without it the daemon cancels the XPC connection and the delegate only sees `streamDidServerDie:`. Signing the helper ad-hoc with `com.apple.videoconference.allow-conferencing` makes it work *on this machine*, which has SIP disabled AND `amfi_get_out_of_my_way=1`. On a stock Mac, AMFI will not honour an ad-hoc binary claiming that Apple-private entitlement, so this path as-is is not distributable to normal users. That constraint is unresolved and must be stated in any release.

Still open: frame rate/latency of the pull path is unmeasured (3 pulls, ~3 s apart in this run, driven by our own timer, not a measured ceiling).

### 2026-09-08 — pull path characterised: ~40 distinct fps, 7-9 ms latency

Same host/device. `receiver.m` with `PULLTEST=1 OOP=1 STAGE2=1` (pipelined: re-request as soon as a frame arrives; a watchdog re-arms if a pull is ever dropped, so a stall cannot masquerade as a slow rate).

| screen state | pulls/s | distinct frames | avg frame |
| --- | --- | --- | --- |
| static (Settings, untouched) | 138 | 8 in 10 s | 309 KB |
| changing (`ipb recents`/`home` alternating during capture) | 108 | **405 in 10 s (~40 fps)** | 393 KB |

So the pull is not the bottleneck: ~7-9 ms per `requestLastDecodedFrame` round trip, and the distinct-frame rate simply tracks how much the screen actually changes. On a static screen it correctly yields ~1 new frame/s instead of burning bandwidth on duplicates; on a moving screen it delivers ~40 fps of genuinely different baseline JPEGs at native 1184x2576.

Frame freshness was verified independently of pixel comparison: the EXIF `DateTime` in sampled frames advances across a fast pull loop (15:03:57 -> 15:04:04), so identical bytes on a static screen mean "nothing changed", not "cached".

Note for reproduction: `ipb scroll` silently did nothing until `make` was run (the reboot wiped `build/`, and the wrapper reported `ipb-helper: No such file or directory` only on stderr). `ipb home` / `ipb recents` are reliable ways to force screen change for this measurement.

## 2026-09-08 — ENTITLEMENT-FREE in-process capture: 46 fps CVPixelBuffers, no daemon

Same host/device. gpt-6-astra disassembly (docs/research/entitlement-astra-2026-09-08.md) overturned the assumption that the CA slot is wired at init and cannot be diverted:
- `-[VCImageQueue setStreamOutput:]` (AVConference `0x1BD831BE8`) saves the output to `self+0x98`, and `_VCImageQueue_EnqueueFrame` (`0x1BD833A40`) reads `self+0x98` EVERY frame — if non-nil it wraps the pixel buffer as a sample buffer and forwards it. So installing a `VCStreamOutput` after init still captures frames.
- `_VCStreamOutput_EnqueueSampleBuffer`'s in-process block (`0x1BD804AE4`) sends the ONE-arg selector `-didReceiveSampleBuffer:` straight to the delegate (not `streamOutput:didReceiveSampleBuffer:`). The earlier sink implemented the two-arg selector, which is why it never fired.
- `-[VCStreamOutput initWithStreamToken:clientProcessID:delegate:delegateQueue:]`: when `clientProcessID == getpid()` it takes the in-process path (requires non-nil delegate + queue).

Implemented in `Experiments/videostream/receiver.m` (`SINK=1`, RunInProcess=YES, binary signed PLAIN ad-hoc with **no entitlements**): swizzle `-[VCImageQueue start]` to create a `VCStreamOutput(token=[iq streamToken], pid=getpid(), delegate=sink, queue)` and `setStreamOutput:` on the live queue; the sink's `-didReceiveSampleBuffer:` receives CVPixelBuffers.

Result: **`INPROC_RATE: 498 sample buffers, 45.9 fps over 10.9 s`**, CVPixelBuffers saved as 1184x2576 PNG. This is a PUSH feed (every decoded frame delivered automatically, no polling) and runs entirely in-process — RTP receive + AppleAVD HEVC decode + frame delivery all local, `avconferenced` not involved, so `AVConferenceXPCServer entitlementStatusForToken:` never runs. **No `com.apple.videoconference.allow-conferencing` needed.**

This is the distributable path: it removes the one known hard blocker (the Apple-private daemon entitlement). Not yet proven on a stock SIP-enabled Mac (dlopening the private frameworks and in-process decode should not need SIP-off, but this is unverified — see Astra's验证资源 step 4). The daemon JPEG-pull path stays as a documented fallback.

## 2026-09-08 — <macos27-host> (macOS 27.0, SIP ENABLED) test: entitlement gate is gone; display link is the real requirement

Ran the in-process `ipb stream` (plain ad-hoc signature, 0 entitlement keys) on <macos27-host> (`<macos27-host>`, macOS 27.0 26A5425a, **SIP enabled, no boot-args**), iPhone 12 mini (iOS 27.0), over ssh.

- The control path negotiated fine and the stream reached `VCVideoStream start`. It did **not** fail on the entitlement — no `streamDidServerDie`, no `allow-conferencing` denial. **This confirms the in-process path bypasses the Apple-private entitlement gate even under full AMFI enforcement**; the entitlement was never the in-process blocker.
- It failed at: `CVDisplayLinkCreateWithCGDisplays error -6661 due to invalid display count (0)` -> `-[VCVideoReceiverDefault initializeDisplayLink] failed` -> `startVideo failed` (`GKVoiceChatServiceError 32017`, DetailedError 1302). The ssh session is headless (no window-server / display), and `VCVideoReceiverDefault` requires a `CVDisplayLink`, which needs an active display.
- Stubbing `-[VCVideoReceiverDefault initializeDisplayLink]` to no-op did not help (startVideo still needs a valid display link). Running in <macos27-host>'s Aqua GUI session via `launchctl asuser` requires root; sudo needs a password not available to this session, so the SIP-on + display combination was not directly exercised here.

**Separated conclusion:** the in-process path needs a **display / GUI login session**, not an entitlement and not SIP-off. The two variables are cleanly separated: the SIP-enabled machine failed only on the missing display; the display-having machine (local, SIP off) works at ~46 fps. A normal user's Mac (a screen + a logged-in GUI session) should therefore run `ipb stream` regardless of SIP. Headless/ssh/CI Macs currently cannot (open item: defeat the display-link requirement, e.g. a virtual display, for headless support).

Direct SIP-on + display proof is still pending: run `ipb stream` from <macos27-host>'s own GUI session (Terminal on the desktop, not ssh), or `sudo launchctl asuser $(id -u) ./build/ipb-video ...`.

## 2026-09-08 — DEFINITIVE: works on a stock SIP-enabled Mac with zero entitlements

<macos27-host> (`<macos27-host>`, macOS 27.0 26A5425a), iPhone 12 mini (iOS 27.0). The helper was built there and signed with a **plain ad-hoc signature (no entitlements)**.

The earlier headless failure was purely the ssh session having no display. Running the same command inside <macos27-host>'s own Aqua (GUI) session — launched from ssh with `open -a Terminal /tmp/guitest.sh`, which needs no root, unlike `launchctl asuser` — gives:

```
active displays: 1
SIP: System Integrity Protection status: enabled.
entitlements on helper: 0 conferencing keys
ipb-video: saved 11 distinct frame(s) from 0 pull(s)
frames: 10        1136x2464      (12 mini native resolution)
```

**This closes the distribution question.** On a stock, SIP-enabled Mac, with a binary carrying no Apple-private entitlement, `ipb stream` captures the device screen in-process (`0 pulls` = pure push feed). The `com.apple.videoconference.allow-conferencing` gate applies only to the `--daemon` fallback, which the shipping path does not use.

**The one real requirement is a GUI display session** (`CGGetActiveDisplayList` > 0), because `VCVideoReceiverDefault` creates a `CVDisplayLink`. Every normal user Mac satisfies this. Headless/ssh contexts do not; from ssh, run it in the console session via `open -a Terminal <script>` (verified working here). A truly headless Mac (no display at all) would still need a virtual display — open item, not a blocker for ordinary use.

Matrix so far for the in-process path: macOS 26.5.1 + SIP off + iPhone 13 Pro (iOS 27) -> ~46 fps; macOS 27.0 + **SIP on** + iPhone 12 mini (iOS 27) -> frames captured, plain signature.

## 2026-09-08 — `ipb stream`: backpressure root-caused, five bounded-wait/exit-code defects fixed

This Mac (macOS 26.5.1, CoreDevice 642.15), iPhone 13 Pro (iOS 27.0 24A5430a, wired).
Reported symptom: the live view shook violently while scrolling and frames from seconds
earlier were spliced back in. `scripts/smoke_matrix.sh` PASSED after the change.

### Root cause (measured, not inferred)

The frame callback did its JPEG encode **and a synchronous `fwrite` to stdout** on
`dispatch_get_global_queue(0,0)` — a *concurrent* queue. Disassembly of AVConference
2205.3.1 (`0C061D6D-207C-3C8B-8637-40F6EC880FE1`) shows `VCStreamOutput_EnqueueSampleBuffer`
does `CFRetain(sb)` then `dispatch_async(delegateQueue, block)` with **no capacity bound, no
keep-latest, and no PTS comparison** on the in-process branch. Setting `_streamOutput` on
`VCImageQueue` also *bypasses* the Fig display queue, so `setLowLatencyEnabled:` does not
apply to this path.

So any consumer slower than the producer blocked every delivery thread inside `fwrite`,
Apple kept queueing retained frames behind them, and the backlog released concurrently and
out of order. Instrumented run, consumer stalled 6 s, 353 frames:

| metric | before | after |
| --- | --- | --- |
| peak concurrent callbacks | **75** | 1 |
| callback ms p50/p95/max | 46.4 / **3989.7** / 4318.2 | 0.070 / 0.140 / 3.250 |
| PTS regressions in emit order | **80 / 353 (23%)** | **0 / 387** |
| worst backwards jump | **2.017 s** | 0 |
| behaviour when consumer is slow | queues 75 frames | drops frames, reports the count |

Upstream ordering was never the problem: **0** PTS regressions in arrival order over 774 frames.

An unsynchronised `if(!gCI) gCI=[CIContext contextWithOptions:nil]` in that concurrent path
aborted the process (`libc++abi: Pure virtual function called!`, producer exit **134** via
`pipestatus`). Controlled test — eager single-threaded init, identical trace pressure —
took the crash rate from 100% to **0/3**. Removing the crash exposed the backlog it had been masking.

### Defects fixed

1. Consumer reads ≥1 frame then stops forever → writer timeout → `_Exit(0)`: **failure reported
   as success**. Now exit 8.
2. Invalid / non-increasing PTS frames were silently discarded and uncounted. Now reported as
   `invalidPTS` / `nonIncreasingPTS`, separate from backpressure drops.
3. `fwrite`/`fflush`/`writeToFile:` results were ignored and `gSaved` incremented regardless.
   Measured: `--dir <read-only> --count 5` returned **rc=0 claiming "saved 5"** with **0 files
   written** (three variants: read-only dir, uncreatable dir, read-only root volume). Now exit 8,
   and `saved` only counts frames that actually reached the sink.
4. `--daemon --count N` **hung without bound**: `streamDidServerDie:` only logged, `--count`
   disabled the seconds exit, and the 2 s daemon re-arm refreshed the same variable the 12 s
   stall guard reads. Measured **100 s with no exit** (49 `closed the stream` callbacks) before an
   external kill. Now request time and successful-output time are separate; exits rc=6 in ~4 s.
5. `--count <large N>` **never exited** (found while checking the scope of fix 4): measured
   1570 files and no exit until an external kill. `--seconds` now bounds `--count` too.

Fixes 4 and 5 were violations of AGENTS.md rule 2 ("No unbounded waits").

### Contract changes

- **`--seconds` now bounds `--count`.** `--count N` not reached within the budget returns **8**
  instead of 0. Agents relying on "wait as long as needed for N frames" must pass a larger
  `--seconds`. Usage text updated.
- New exit codes: **8** output failed / consumer did not drain / count not reached;
  **9** watchdog expired. 9 has three arming stages (setup·start·warmup 45 s;
  collection `seconds+5`; shutdown `writerGrace 5 + stopGrace 5 + margin 5`), each printing a
  distinct stage line via `write(2)` before `_Exit`.
- Non-finite / non-positive `--seconds` is rejected with 2. `SIGPIPE` is ignored so a broken
  stdout is reported as output failure rather than a signal death.

### Known, not fixed

- **No PTS-reset recovery.** `gNewestPTS` only advances. A same-epoch reset would reject frames
  until PTS passes the old watermark (an epoch increase is *not* rejected). Reachability within
  one run is unproven, and "reset on any regression" would re-admit genuinely late frames.
- **Hard stall returns 0 without `--count`.** If frames stop for 12 s mid-run, the guard breaks
  the loop and `saved>0` still exits 0. Pre-existing; whether a stall is a failure is a contract
  decision. Related open observation: two consecutive 15 s captures stopped at t+5.81 s (352
  frames, identical both times) and still returned rc=0; five later runs (20 s, 30 s, and with a
  rotation) ran full duration at ~41 fps. **Not reproduced, cause unknown.**
- **Watchdog budgets are policy values, not measurements.** 45 s setup and the 5 s margins have no
  cold-start data behind them; the comments say so. The watchdog covers `ipb-video` only — the
  tunnel warm-up and resolution in `bin/ipb` are outside it.
- **Exit 9 has no natural repro.** Reachable by inspection (three arming sites) but never observed;
  triggering it needs fault injection that blocks one call while leaving the watchdog queue live.
- `--daemon` cannot work in the shipped build (ad-hoc signature, no
  `com.apple.videoconference.allow-conferencing`); it fails fast with rc=6.

### Method note

Implementation was delegated to Codex across three rounds; review was intended to be independent
but the review request routed back to the implementer's own thread, which disclosed the conflict
and spun up a separate reviewer to compensate. Round 3 reverted an unrequested change that moved
the private `[vs stop]` call onto a global queue (unverified thread contract, and a normal stop
exceeding a 1 s window would have turned successful output into rc=9).

### 2026-09-08 — user acceptance of the fixed stream

The user ran the fixed build against their own device and reported the live view working well; the
scroll jitter and the seconds-old frames that started this investigation are gone. Remaining
observation: **slight frame loss, comparable to what Apple's own DeviceHub shows on the same
device.** Their read — that this is link-level rather than client-side — is consistent with our
measurements (ingress p95 0.14 ms, zero PTS regressions in emit order, drops only under deliberate
consumer stalls) but has not been measured directly; a link-level loss study is not done.

Test procedure used: `./bin/ipb` from the repo, not the Homebrew `ipb` on PATH, since the fix is not
released. The new build is identifiable by its exit line, which the old one lacks:
`saved N ...; dropped M frame(s) due to backpressure; invalidPTS X; nonIncreasingPTS Y`.

## 2026-09-08 — mirror M1: media + HID coexist in one process; host-side input p99 = 2.2 ms

This Mac (macOS 26.5.1, CoreDevice 642.15), iPhone 13 Pro (iOS 27.0), wired, GUI session.
Probe: `Experiments/mirror/mirror_probe.m` -> `build/ipb-mirror-probe`. One process holds the
AVConference media session **and** a UHID service socket, with input on its own serial queue
(state machine Idle->Pressed->Ending->Idle, bounded 64-event pending queue, generation
invalidation, `usleep` removed from the per-event path, barrier only at gesture end).

### Q1 — does the media stream degrade when the same process also drives HID?

Same binary, `--no-input` as the baseline:

| | media only | + 546 input events |
| --- | --- | --- |
| frames | 407 | 412 |
| frame interval p50 | 17.039 ms | 17.063 ms |
| frame interval p95 | 50.056 ms | 50.083 ms |
| drops / errors | 0 / 0 | 0 / 0 |

**No measurable interference.** The probe's media numbers also match an independent
`ipb stream` baseline taken the same session (p50 17.0-17.1 ms, p95 50.0-50.2 ms over 3 runs).

### Q2 — host-side per-event latency with the sleeps removed and the connection reused

| rate | events | queue+entry p50/p95/p99 | host total p50/p95/p99 | overload | max queue depth |
| --- | --- | --- | --- | --- | --- |
| 60 Hz | 546 | 0.013 / 0.055 / 0.134 ms | **0.921 / 1.486 / 2.197 ms** | 0 | 2 |
| 120 Hz | 724 | — | **0.453 / 1.172 / 1.658 ms** | 0 | 2 |
| 240 Hz | 1444 | — | **0.598 / 1.214 / 1.473 ms** | 0 | 2 |

`submitted == executed` at every rate (546/546, 724/724, 1444/1444); zero rejected, zero
overload. Gesture tail (UP -> barrier return) p50 4.05 ms, n=3.

**The 220 ms that dominated `ipb pointer` was entirely blind `usleep`.** The external sender
costs ~0.9 ms and is not an expensive synchronous block. A 60 Hz drag uses ~1 ms of its
16.7 ms budget; there is at least 4x headroom past 240 Hz.

This supersedes the earlier "~0-14 ms host-side" figure, which was a subtraction estimate from
`126-120` and `108-100` and is not a measured distribution.

### What this does NOT establish

- **Not end-to-end latency.** The probe's own banner says it: host sender return is not device
  acknowledgement. Glass-to-glass (finger -> pixel) is unmeasured, and the four timestamps do
  not cover AppKit callback delay before `t_submit` or the device's screen response after.
- **Relative pointer, not absolute touch.** `cd_pointer_report` sends deltas, so the trajectory
  mapping is an experimental approximation and does not establish absolute screen position.
  A real drag must use the absolute touch path; its timing is assumed similar (same sender) but
  not measured.
- Synthetic events at a fixed rate are not a real mouse's arrival pattern, and not an agent's
  bursty one. Longer sessions, idle sockets, screen-off and unplug are untested.

### Frame-loss characterisation (answers the "slight frame drop like DeviceHub" observation)

Over 1681 intervals from three media-only runs, classified by PTS continuity — the only sound
criterion, since arrival gaps conflate loss with bunching:

| PTS gap | count (one run) | meaning |
| --- | --- | --- |
| 1x 16.7 ms | 425 | normal |
| 2x | 13 | one frame absent |
| 3x | 127 | two frames absent |
| 4x | 1 | three absent |

**~32% of the device's 60 Hz slots never appear in the PTS sequence at all.** The device has a
60 Hz timebase but emits roughly two thirds of the slots, giving the ~41 fps effective rate.
Separately, arrival is bunched: 18 intervals in one run arrived with ~0 gap, so arrival order
and PTS order do not line up.

The frames are absent at the source, not lost by our client: our RTP socket has no
retransmission, and link loss would not produce gaps this regular. **Client-side data cannot
distinguish device capture throttling from encoder frame-dropping** — that needs device-side
logs. The user reports DeviceHub showing the same behaviour on this device, which is consistent
with a device-side producer.

Consequence for the mirror: since our wire format carries no timestamps, a viewer paces by
arrival, so the bunching shows as stutter. `AVSampleBufferDisplayLayer` schedules by PTS
natively, so M2 may look smoother than the current `ffplay` path for free — to be verified.

## 2026-09-08 — mirror M2/M3: window, drag, aspect-locked scaling, button shortcuts

This Mac (macOS 26.5.1), iPhone 13 Pro (iOS 27.0), wired, GUI session.
`Experiments/mirror/mirror_app.m` -> `build/ipb-mirror`: AppKit window rendering decoded
`CMSampleBuffer`s through `AVSampleBufferDisplayLayer` (no JPEG round-trip), real mouse events
driving the **absolute touch** path (`uhid_make_digitizer_hid_report`, service 0x101), reusing
M1's serial input queue, bounded pending queue, generation invalidation and four-point timing.

### Coordinate mapping was inverted in Y — root cause and fix

Reported as "coordinates do not line up". Diagnosed with synthesised clicks
(`CGEventCreateMouseEvent` at known screen points, window bounds from `CGWindowListCopyWindowInfo`):

| clicked (window fraction) | computed before fix |
| --- | --- |
| 0.5 | 0.502 |
| **0.1** | **0.905** |
| **0.9** | **0.101** |

Root cause, isolated in a standalone AppKit test: `-convertPointToBacking:` and
`-convertRectToBacking:` map into the **unflipped** backing store, so on a flipped view the y
coordinate is negated. Measured in isolation: view y=20 (near the top) became backing y=-40
against a bounds origin of -1688, normalising to 0.976 instead of 0.024. The midpoint is
symmetric, which is why only the ends were visibly wrong.

The backing conversion was never needed — the normalisation is a ratio, so the scale cancels.
Fix: stay in the view's own flipped point space. Re-measured on the real mirror: clicking 0.1 /
0.5 / 0.9 now yields 0.067 / 0.497 / 0.926 (residual offset is the test's title-bar estimate,
not the mapping).

### Aspect-locked scaling

`window.contentAspectRatio` is set from the video size once the first frame arrives, so resizing
keeps the device ratio. Verified: window content 387x844 (0.4585) against video 1184x2576
(0.4596), 0.24% apart, and `black_bar_rejections` went 5 -> **0**. Before the lock, a fixed
420x840 window letterboxed ~16 px each side, which is why a click at window fraction 0.2 landed
at content fraction 0.174 — arithmetically correct, but not what a scrcpy user expects.

**Known uncompensated offset:** the video frame is 1184x2576 while the 13 Pro screen is
1170x2532. The encoder pads to a 16-pixel multiple and the format description carries **no clean
aperture** (measured: `presentation=1184x2576 raw=1184x2576`), so normalising over the full frame
carries ~1.2% x / ~1.7% y error. Not compensated: we have no evidence for which side the padding
is on, and guessing could make it worse.

### Button shortcuts — evidence per shortcut

| shortcut | action | evidence |
| --- | --- | --- |
| `Cmd-H` | Home (`0x0c` / `0x40`, button feature) | **screenshot**: device left the Mail welcome screen for the home screen |
| `Cmd-Shift-H` | App Switcher (digitizer swipe, same parameters as `bin/ipb recents`) | **screenshot**: card-style switcher |
| `Cmd-Up` | Volume up (`0x0c` / `0xE9`) | **screenshot**: volume HUD visible |
| `Cmd-Down` | Volume down (`0x0c` / `0xEA`) | standard paired usage, sent rc=0; the HUD looks identical to volume up, so this was **not** separately distinguished |

`0x0c` / `0xE9` was confirmed by sending it standalone through `bin/ipb button` and screenshotting
the volume HUD before it was wired into the mirror.

**Action Button and Camera Control are deliberately not implemented.** There is no documented
usage code for either in this repo, and this device has neither (Action Button is iPhone 15 Pro
and later; Camera Control is iPhone 16). Guessing a usage code would violate rule 1. Adding them
needs a separate evidence pass on hardware that has the button.

Buttons and the switcher use the `hid.button` and `hid.digitizer` features, so the mirror opens
two additional service sockets at startup and reuses them (M1 measured a socket at 14-18 ms).
A shortcut pressed mid-drag sends UP + barrier first, then the shortcut, keeping the touch state
machine consistent.

### Still open

- The device's 5 HID descriptors expose no Consumer page (0x0C) service; Home and volume work
  through the button *feature* rather than a descriptor-backed service. Why the two paths differ
  is not investigated.
- `--present timed` vs `immediate` has not been judged; the visual comparison is the user's.
- Synthetic `CGEvent` clicks only register when the window is frontmost; several runs recorded no
  events until the app was explicitly activated. This is a test-harness limitation, not a mirror bug.

### 2026-09-08 — mirror M4: `timed` presentation removed, shortcuts aligned to DeviceHub

**Supersedes the shortcut table in the M2/M3 record above.**

`--present timed` is gone. It was not defective — instrumenting the timebase showed **no drift**
(`pts - timebase` stayed at +26 to +68 ms for a whole 20 s run, `status=1 ready=1` throughout).
That gap *is* the deliberate 50 ms headroom: every frame waits for its PTS before display, so
timed mode adds a constant ~50 ms. The user's verdict was that dragging felt disconnected in
timed and fine in immediate, so the path was deleted rather than kept behind a flag
(AGENTS.md rule 2). Frames now always carry `kCMSampleAttachmentKey_DisplayImmediately` on our
own copy.

Shortcuts were realigned to Apple's own DeviceHub rather than the invented set. The previous
`Cmd-Shift-H` for App Switcher **collided with DeviceHub's Home**, which is worse than merely
differing. DeviceHub's real menu was read at runtime through the Accessibility API
(`AXMenuItemCmdChar` / `AXMenuItemCmdModifiers`) on Xcode 27 beta 6 with the 13 Pro attached;
the full table is in `docs/research/ios-peer-tools.md`.

| shortcut | action | verification |
| --- | --- | --- |
| `Cmd-Shift-H` | Home | **screenshot**: device on the home screen |
| `Cmd-Ctrl-Shift-H` | App Switcher | **screenshot**: switcher cards |
| `Cmd-Up` / `Cmd-Down` | Volume up / down | up verified by HUD screenshot earlier |
| `Cmd-Shift-S` | Screenshot | **saved 1184x2576 PNG with correct colour**, from the latest decoded frame; no `devicectl` round trip (that costs ~1.4 s) |
| `Cmd-0` / `Cmd-1` | Zoom to fit / actual size | window went 387x872 -> 468x1050; 1:1 needs 592x1288 pt which exceeds the screen, so it falls back to fit as designed |

Volume is the one binding where DeviceHub, scrcpy and the original guess all agree.

Not implemented, and why: Lock (`Cmd-L`), Siri (`Cmd-Opt-Shift-H`), Record Screen
(`Cmd-Shift-R`), Action Button and Camera Control. Each needs a usage code we have no evidence
for. DeviceKit.framework does contain `hardwareGestureControls.actionButton` and `.sideButton`
menu identifiers, but they do not appear in the menu with a 13 Pro attached — the framework uses
`ConditionalKeyboardShortcut` to show them per device. That both confirms the 13 Pro lacks an
Action Button and gives the route to obtain its usage code: attach a 15 Pro and observe.

## 2026-09-08 — mirror promoted to an installed command (host-only verification)

The former `Experiments/mirror/mirror_app.m` is now `Sources/mirror.m`, built as
`build/ipb-mirror` and installed as `libexec/ipb-mirror`. Earlier M2/M3 records retain the
source path used at the time. `Experiments/mirror/mirror_probe.m` and its target remain unchanged.
`ipb mirror [--seconds S] [--csv PATH]` resolves the tunnel like `ipb stream`; `--help` bypasses
device selection and GUI startup. Summary fields now go to stderr. Event CSV is opt-in,
written to PATH (overwritten), and no CSV is generated without that option.

Host: macOS 26.5.1 (25F80), selected SDK under `/Applications/Xcode.app`.
No device commands or interactive/device validation were run for this packaging change.
Existing M1/M2/M3/M4 results above remain the device evidence, not a fresh acceptance run.

- `make`: exit 0; compiled `Sources/mirror.m` to `build/mirror.o`, linked and ad-hoc signed
  `build/ipb-mirror`, with no errors.
- `make install PREFIX=/private/tmp/ipb-mirror-install.CRYOIE`: exit 0. Layout includes
  `bin/ipb`, `libexec/ipb-helper`, `libexec/ipb-video`, `libexec/ipb-mirror`,
  `share/ipb/VERSION`, and `share/ipb/smoke_matrix.sh`.
- `codesign --verify --strict --verbose=2 /private/tmp/ipb-mirror-install.CRYOIE/libexec/ipb-mirror`:
  exit 0, `valid on disk`, `satisfies its Designated Requirement`;
  `codesign -dv` reports `Signature=adhoc`.
- `/private/tmp/ipb-mirror-install.CRYOIE/bin/ipb mirror --help`: exit 0, includes
  `--csv PATH`, stderr summary contract, and GUI session requirement.
- Local helper checks with an invalid UUID (rejected before CoreDevice service setup):
  default and explicit CSV both exit 2, stdout is empty and summary is on stderr;
  explicit CSV contains only its header (zero input events). A missing CSV parent directory
  exits 8. Artifacts: `/private/tmp/ipb-mirror-install.CRYOIE/{default,csv,csv-open-error}.{stdout,stderr}`
  and `/private/tmp/ipb-mirror-install.CRYOIE/events.csv`.
- `zsh -n bin/ipb` and `ruby -c Formula/ipb.rb`: exit 0 (`Syntax OK` for Ruby).

Packaging choices: the wrapper passes existing helper options through, and handles help before
resolving a device. CSV parents are not created automatically. The installed mirror's codesign
step propagates failures. No Git commands were run in this continuation; no commit was made.

### 2026-09-08 — `ipb mirror` shipped as a command, and a media-path wedge found while doing it

`Sources/mirror.m` (moved out of `Experiments/`), `ipb mirror` in the wrapper, `libexec/ipb-mirror`
in `make install`, README and Formula updated. Per-event CSV became opt-in (`--csv PATH`); the
human-readable summary goes to stderr, so a GUI command no longer dumps thousands of rows to stdout.

Verified from a temporary install prefix, not just from the build tree:

```
make install PREFIX=<tmp>            -> rc=0, layout contains libexec/ipb-mirror
<tmp>/bin/ipb mirror --seconds 14    -> window 387x872 opened, media frames=354,
                                        interval p50 16.627 ms / p95 17.542 ms, stdout empty
<tmp>/bin/ipb mirror --csv <path>    -> CSV written with the x,y columns
```

**Defect found immediately afterwards, not yet fixed: the media path wedges.**

After roughly fifteen start/stop cycles across `ipb stream` and `ipb mirror` in quick succession,
every subsequent stream start fails with:

```
GKVoiceChatServiceErrorDomain 32017 "VCVideoSteam start failed"
NSLocalizedFailureReason = VideoReceiver startVideo failed, DetailedError = 1302
```

What is established:

- It is **not specific to the new mirror code**: `ipb stream`, unchanged and working all session,
  fails identically once the wedge appears.
- **No leftover processes** of ours; the device is unlocked with a connected tunnel.
- **Restarting the host `avconferenced` does not clear it.** The daemon was idle (0 TCP
  connections, 0% CPU) and relaunches on demand, and the next start still failed.
- **It does not self-recover** within at least 60 s.
- The failing component names the *receiver*, which is our side, yet the host-side restart does not
  help — so the device's `dtremotedisplayd` session is the remaining suspect.

What is **not** established: which run wedges it, whether a normal one-session-at-a-time user ever
reaches it, and what clears it. An attempt to query `mediastreamstatus` through
`Experiments/probe/feature_probe.m` was abandoned: the probe's JSON envelope encodes the version
components as int64 and the device wants UInt, and chasing the envelope was not worth the time
against the value of the answer.

Next steps for this, in order: try physically re-attaching the device and re-testing (only the
operator can do that); if that clears it, add a `mediastreamstop` recovery path so the tool can
unwedge itself rather than requiring a cable pull. Note `docs/video-stream.md` already records
that the daemon stops streams itself on sensor activity
(`stopAllStreamsDueToSensorActivity`), so a stop action exists on the device side.

### 2026-09-09 — the media wedge, narrowed: cumulative, host-side, not ours

Continued from the 2026-09-08 entry. The Mac was rebooted, which cleared the wedge
(`ipb stream` rc=0, `ipb mirror` 413 frames at p50 16.7 ms / p95 20.2 ms), so the state was
re-created deliberately.

**It is cumulative, not triggered by any single action.** 16 consecutive `ipb stream` cycles all
passed; then 14 consecutive `ipb mirror` cycles all passed; the very next stream start failed.
So the threshold on this host is roughly **30 sessions**, and neither loop alone reaches it.
This also retires the earlier suspicion that a `kill -9`/`SIGINT` teardown was to blame: the wedge
had already returned *before* the signal test ran, so that test proved nothing about signals.

**It is host-side, and not specific to one device.** With the 13 Pro wedged, streaming the
**iPhone 12 mini** — a different device entirely — fails with the *identical*
`GKVoiceChatServiceErrorDomain 32017 / VideoReceiver startVideo failed / DetailedError 1302`,
and it gets past tunnel setup to the video start. This is the decisive test the previous entry
lacked.

**Correction to the previous entry.** It reasoned that a reboot fixing the problem pointed at the
host. That inference was unsound on its own: rebooting the Mac also drops and re-establishes the
device link, so it could equally have cleared device-side state. The second-device result above is
what actually establishes host-side.

**Ruled out as the cause:**

| checked | result |
| --- | --- |
| our own leaked RTP sockets | zero UDP bindings on the tunnel prefix, 6 udp6 entries total, no orphan holders |
| leftover processes of ours | none |
| `avconferenced` state | restarting it does not clear the wedge; it holds only 18 fds |
| signals / unclean teardown | wedge predated the signal test |
| device-side session | a second device fails identically |
| self-recovery | still wedged after 60 s and after many minutes |

**Still unknown:** which host resource is exhausted. The shape — a fixed count of sessions,
survives a user daemon restart, cleared only by reboot — fits a kernel or driver level decode
session leak, but that is a hypothesis, not a finding. `VTDecoderXPCService` and `remoted` are both
root-owned, so testing them by restart needs privileges this session does not take on its own.
Log predicates for AppleAVD / VTDecompression produced nothing.

**User impact:** anyone who runs about thirty `ipb stream` or `ipb mirror` sessions without
rebooting is blocked, with an opaque AVConference error and no in-tool recovery. Whether unplugging
and re-attaching the device clears it is untested — only the operator can do that, and it is the
cheapest candidate workaround to check next.

### 2026-09-09 — the black edge and the coordinate offset were the same bug: encoder padding

The user reported a remaining black edge in the mirror and coordinates still slightly off. Both
came from one cause: **the decoded frame carries encoder padding, and we were normalising over the
padded frame.**

Measured per-pixel across 12 frames of differing content (including mid-swipe) on the 13 Pro:

```
frame        1184 x 2576
content      x in [0,1170)  y in [0,2532)     identical in all 12 frames, zero variance
padding      right 14 columns + bottom 44 rows, pure black (mean ~0.2, max <8; content ~190)
left / top   content, no padding
```

1170x2532 is the 13 Pro's real screen resolution, so the padded region was being both drawn (the
black edge) and counted in the normalisation (1.2% x, 1.7% y of error).

**The size cannot be computed and must not be detected from content alone.** Width is 16-aligned
(1170 -> 1184) but height is not (2532 would align to 2544, yet the frame is 2576). `devicectl`
reports no screen dimensions and the format description carries no clean aperture. Detecting the
black region from frames works but breaks on a genuinely black screen — which the implementer
independently flagged as its most likely failure.

**Authoritative source found, local to Xcode:**

1. `.../Platforms/iPhoneOS.platform/usr/standalone/device_traits.db` (SQLite), `Devices` table:
   `ProductType` -> `ProductDescription` (`iPhone14,2` -> `iPhone 13 Pro`)
2. `/Library/Developer/CoreSimulator/Profiles/DeviceTypes/<ProductDescription>.simdevicetype/
   Contents/Resources/capabilities.plist` -> `capabilities/displays[0]` `width`/`height`

For the 13 Pro this yields exactly 1170x2532, matching the pixel measurement.
**`DeviceTraits.ArtworkDeviceSubtype` looks like a pixel height and is not** — it reads 2532 for the
13 Pro but 2388 or 569 for older models, so only the simulator profile is trustworthy.

A 44-entry table (iPhone 6s through 17 Pro Max / Air / 17e) generated from that join is built into
`Sources/mirror.m`; `bin/ipb` passes `hardwareProperties.productType` from the devicectl JSON it
already fetches. Resolution order is built-in table -> runtime Xcode lookup -> content detection ->
full frame, and every source is range-checked against the current frame (content positive, not
larger than the frame, within 64 px per axis) before being accepted, falling through with a logged
reason otherwise.

**Verified on device:**

```
ipb-mirror: content: frame=1184x2576 rect=(0,0 1170x2532) source=builtin-table productType=iPhone14,2
black_bar_rejections=0
```

Coordinate accuracy, from synthesised clicks at five window fractions, solving the title-bar offset
from the two extremes and back-substituting the rest:

| window fraction | predicted | measured | delta |
| --- | --- | --- | --- |
| 0.10 | 0.06548 | 0.06548 | +0.00000 |
| 0.25 | 0.22106 | 0.22143 | +0.00037 |
| 0.50 | 0.48036 | 0.48095 | +0.00059 |
| 0.75 | 0.73966 | 0.74048 | +0.00082 |
| 0.90 | 0.89524 | 0.89524 | +0.00000 |

Max deviation 0.08%, within the synthetic-click and title-bar-estimate noise. Derived content
aspect 0.46270 against the target 0.46209 — 0.13%, which is integer rounding of a 389 px window.

The `Cmd-Shift-S` screenshot now saves **1170x2532** instead of 1184x2576, and its rightmost columns
and bottom rows contain image data (mean 195-215) rather than padding, confirming a crop rather
than a rescale.

This closes the "known and uncompensated ~1.2%/1.7% offset" recorded in the M2/M3 entry above.

## 2026-09-09 — mirror gestures: bottom edge works, scroll does not, and why

User-reported gaps after the mirror shipped: the window did not forward scroll events, and a
bottom-up drag did nothing. Both are things DeviceHub does.

### Bottom-edge gesture: fixed and user-verified

A controlled experiment settled which report type is needed. Same coordinates, same duration,
only the report type differs, iPhone 13 Pro / iOS 27.0 starting from Settings, judged by the mean
saturation of the bottom 8% of a device screenshot plus looking at the image:

| condition | bottom saturation | result |
| --- | --- | --- |
| Settings baseline | 0.033 | — |
| plain touch report on 0x101, `(0.5,0.995)->(0.5,0.55)`, 420 ms | 0.033 | **nothing happened** |
| `ipb recents` (digitizer `IndigoDigitizerEvent`, `edge=bottom`) | 0.721 | App Switcher |

This corrects an earlier claim in this session that plain touch reports "do not trigger system edge
gestures" — that had been an inference; this is the experiment that establishes it, and its scope is
exactly these parameters, not every possible parameterisation.

Apple's own path was then traced by disassembly (DeviceKit 255.2.3, UniversalHID 90.1):

```
DigitizerState.handleTouch(mouseEventType:...)   DeviceKit 0x421e04
  -> TouchResult.digitizerEvent()                DeviceKit 0x4216f0   -> UniversalHID.DigitizerEvent
  -> bottom branch adds swipeUp|swipeLocked      DeviceKit 0x4219d0
  -> DigitizerFilter.filterEvent(...)            UniversalHID 0x8875c
  -> UniversalHIDService.send(report:to:)        DeviceKit 0x435b64
```

`handleTouch` stores `initialEdge` at touch-down and keeps it for the whole gesture, with
`DigitizerState.detectEdge` (0x4224a4) using inner/outer insets — so edge membership is decided on
press, not re-evaluated per move. The mirror now mirrors that: mode is frozen at mouseDown, the
bottom 2% is the hit zone (a product choice, noted as such in the source, not an Apple threshold),
and each real mouse event sends one `start`/`position`/`end` with `edge=bottom`, no interpolation,
no fixed delays, and no client-side Home-vs-App-Switcher decision. **The user confirmed dragging
now works.**

A correction worth recording: an earlier reading of this session concluded from
`UniversalHID.FluidTouchGestureReportProtocol` (fields `phase, progress, delta, velocity,
velocityX/Y, swipeMask, gestureMotion, flavor, flags, x, y`) that DeviceHub sends velocity from the
host. That inference had the direction wrong. `NavigationSwipeGesture.dispatch(report:)`
(UniversalHID 0x7372c) **consumes** a report and builds IOHIDEvents from it; it is the decoding
side. No call from the mouse path into FluidTouch report construction exists in DeviceKit.

### Scroll: sent successfully, ignored by the device

Through the mirror, one process, one connection, real timing:

```
submitted=185  executed=185  rejected=0  scroll_unsupported=0
device: 0.0% pixel change (both precise/trackpad and discrete/line synthetic events)
```

Via the CLI, all three field combinations — raw `dx/dy` only, accel only, both — also produced
**0.0%**, while `ipb scroll` (a touch swipe, not a scroll report) moved 27.7% of pixels. So the
failure is not the unverified gain constants; the whole path has no device effect.

The repo's own history explains why this was never noticed: the scroll-report record at
`docs/protocol.md:499` was a **zero-movement** send. `ipb scroll-report` has never been shown to
scroll anything since it shipped.

### Root cause candidate: report allocation uses a static bit count

Captured live with lldb on DeviceHub during a real trackpad scroll — breakpoint on
`ScrollReport.init(scrollEvent:)`, which fires only for scrolls:

```
DeviceKit sub_42874c -> UniversalHIDKit EventObserver.processEvent(_:)
  -> Sequence.reduce(into:_:) -> UniversalHIDKit sub_2777dda50
  -> UniversalHID ScrollFilter.filterEvent(_:) -> ScrollReport.init(scrollEvent:)
```

Disassembling that initialiser shows the construction order:

```
HIDReportDescriptor.reportBitCount(for: ReportID) -> Int      <- queries the descriptor
HIDReport.init(bitCount:id:)                                  <- allocates with that
ScrollCollection.init(scrollEvent:)                           <- then fills fields
```

`static ScrollReport.initialReportBitCount.getter` is `mov w0, #0x68` — **104 bits**. Apple does not
use it; it asks the descriptor every time. Our glue does the opposite:

| builder | allocation | note |
| --- | --- | --- |
| `Sources/universalhid_glue.swift:361` scroll | `uhidScrollReportInitialBitCount()` = 104 | static |
| `:409` digitizer | `uhidHIDReportInit(0x140, 0x09)` | hardcoded 320 |
| `:523` digitizer swipe | `uhidHIDReportInit(0x140, 0x09)` | hardcoded 320, while contact 0's swipe pending/locked/up bits are at **424/429/434** |

`setContactSwipePending` (UniversalHID 0x5339c) returns early when capacity is short, so oversized
field writes are **silently dropped**. That is a single systematic defect with two visible symptoms:
`ipb uhid-swipe-report` accepts `pending/locked/up` arguments and discards them, and scroll reports
go out without whatever the device needs.

**Not yet established:** the exact bit offsets and widths of the scroll fields, whether 104 is
actually short, and whether `ScrollReport.init(scrollEvent:)` also sets fields our field-by-field
construction never touches. Fixing the bit count may be necessary but not sufficient. Under
investigation; no code changed on this basis yet.

### Method note, and a mistake

An earlier attempt to capture DeviceHub put a breakpoint on `UniversalHIDService.send(report:to:)`,
which fires on every HID report — 162 hits in 16 s with a register dump each — and froze DeviceHub
badly enough that the user had to restart it. The working approach is a breakpoint on a
scroll-specific symbol with no auto-continue: it stops once, dumps, and detaches.

Synthetic `CGEvent` drags and scrolls reach our own mirror reliably but **do not** reproduce
DeviceHub's gestures, even with `kCGMouseEventDeltaX/Y` populated, so DeviceHub comparisons need
real user input. Two rounds of synthetic tests were invalidated by a stale window rectangle after
the DeviceHub window resized below a size filter in the test tool.

### Still to do

- Scroll: confirm the bit offsets, fix allocation, re-verify with a device effect (not `rc=0`).
- Horizontal scroll rides the same path; it needs no separate protocol work once scroll works.
- Lock/unlock (DeviceHub's `Cmd-L`) still has no usage code. It is now obtainable the same way:
  breakpoint the send path while the user presses the shortcut in DeviceHub.


## 2026-09-09 — Report allocation and mirror scroll fields (build only)

- Scope: `fix-reports.md` supplied brief; disassembly evidence supplied by peer, not independently recaptured: UniversalHID 90.1, UUID E3C64825-61D8-3DF4-97CE-F86D53955566, macOS 26.5.1. All three Digitizer allocations now use 464 bits; Scroll uses 168 bits. This addresses swipe-field truncation, not proof of a gesture fix.
- Mirror precise and wheel conversion now both populate raw and accel fields. Raw uses nearest rounding with ties away from zero and the brief's symmetric [-127, 127] clamp; `scroll_raw_clamped_axes` counts saturated axes. Accel retains the Double input for existing 16.16 encoding; explicit gains remain 1.0 and UNVERIFIED. Bottom-edge gestures, Y mapping, flags and timestamp handling are unchanged; no ABI shim added.
- Host: local Mac, macOS 26.5.1 (25F80). `make` first exited 2 because the sandbox denied the default Swift module-cache output. `CLANG_MODULE_CACHE_PATH=/private/tmp/ipb-fix-reports-module-cache make` exited 0; rebuilt `build/universalhid_glue.o`, `build/mirror.o`, linked `build/ipb-helper`, `build/ipb-mirror`, `build/ipb-mirror-probe`, and signed the mirror binaries.
- No device or smoke-matrix run, per the brief; device/build compatibility and actual scrolling remain unverified. Main remaining uncertainty: AppKit delta units/gain are uncalibrated, and filling both fields does not establish equivalence to Apple's conditionally selected accelerated event.

### 2026-09-09 — device results for the allocation/scroll change

Run on this Mac against the iPhone 13 Pro.

| check | result |
| --- | --- |
| `ipb recents` after the 320 -> 464 bit digitizer change | bottom saturation 0.554, App Switcher — **no regression** |
| mirror bottom-edge gesture, synthetic drag | 0.033 -> 0.005, **gesture fires** (previously only the user's real mouse triggered it) |
| mirror scroll, precise, 125 events | `submitted=125 executed=125 rejected=0`, **device 0.0%** |

**Scroll still does not work**, and the allocation change did not alter that — as predicted, since the
written fields were never out of bounds.

Eliminated as causes:

- report too small (fields were inside 104 bits; now 168 anyway)
- writing only raw or only accel (both are written now)
- per-process / per-socket effects (single connection, 125 events on it)
- events not reaching the app (`submitted == executed`, zero rejects, zero unsupported)
- **a bug in the test harness**: the synthetic scroll tool had been writing NSEventPhase constants
  into `kCGScrollWheelEventScrollPhase`, which uses CGScrollPhase — so every mid-scroll event
  arrived as `NSEventPhaseEnded` carrying a delta and the mirror correctly rejected it as an orphan
  (`scroll dropped: scroll_orphan ... phase=0x8 delta=(0,-25)`, 14 rejected). Fixed to 1/2/4; the
  events are now accepted cleanly and the device still does nothing.

Still open, in order of suspicion:

1. **flags-byte encoding.** `phase.getter` masks with `0xffffff8f`, so phase occupies bits 0-3 **and
   bit 7** of the flags byte — a non-contiguous field. Whether our glue packs it that way is unchecked.
2. Whether `0x501` (touchscreenGesture, DeviceTypeHint Trackpad) is even the right target service.
3. Whatever else `ScrollReport.init(scrollEvent:)` does that field-by-field construction does not.

The decisive next step is to capture DeviceHub's actual scroll report bytes during a real trackpad
scroll and diff them against ours, rather than continue eliminating hypotheses one at a time.

## 2026-09-09 — Device Hub tracing harness, and two retractions

Host: macOS 27 beta, Xcode 27.0.0 Beta 6, SIP disabled, `amfi_get_out_of_my_way` **not** set.
Frameworks: CoreDevice, UniversalHID 90.1, DeviceKit 255.2.3.

### Why this exists

Eight capture rounds against Device Hub, each a hand-written `.lldb` file of blind `continue`
commands in `/tmp`, produced two usable byte dumps. They also wedged Device Hub badly enough to
need a manual restart, and each round cost the operator a scripted sequence on the phone. Seven
distinct defects recurred across those rounds because nothing was kept between them. The harness in
`Experiments/devicehub-trace/` and the method in `docs/devicehub-tracing.md` replace that.

### Measurements (throwaway target, so no operator round was spent)

Target: a C program calling `hid_send` 2000 times with a fake report object.

| Configuration | Elapsed | Rate | Per hit |
| --- | --- | --- | --- |
| No debugger | 2.50 s | — | — |
| Breakpoint, no-op callback | 9.46 s | 211.4/s | 4.73 ms |
| Breakpoint, 4 registers read | 9.43 s | 212.1/s | 4.72 ms |
| Breakpoint, 4 registers + 2 `ReadMemory` | 9.50 s | 210.6/s | 4.75 ms |

The per-hit cost is entirely the stop/resume round-trip; payload capture is free. This inverts the
earlier practice of recording only registers "to keep it cheap", which discarded the report bytes
that were the point of the capture while saving nothing. It also explains the freeze: a tap on a
path Device Hub drives continuously consumes the whole ~210 hits/s budget.

**`--skip-prologue false` is mandatory.** `breakpoint set -n` bound at `+32` on the test function,
past `str x8,[sp,#0x8]` and `mov x8,x0`. Argument registers read at that point are clobbered. Every
earlier Device Hub capture read arguments this way, so those register values were not trustworthy.

### Mechanisms validated before touching Device Hub

- Python breakpoint callback returning `False` auto-continues: 2000/2000 hits recorded, full report
  bytes decoded via the `+16` pointer / `+24` length layout, target never stopped.
- One-shot breakpoint planted at `LR` from inside the entry callback captures returns: 50 entries
  and 50 returns from a function returning a struct indirectly.
- Hit-rate governor: shed its tap at 183.9 hits/s after 184 hits and logged the shed. Freezing
  Device Hub is now structurally impossible rather than a matter of care.
- Bounded run and clean detach against a live process (`dhrun`): attached, traced 4 s with payload,
  detached, and the target kept running. lldb's synchronous `continue` never returns when callbacks
  auto-continue, which is why an earlier script parked forever.
- Full harness end-to-end against a fake target: 189 records correctly bucketed into action windows
  by the marker stream, decoded to a per-action report table, target survived.

### New protocol facts (disassembly, UniversalHID 90.1)

- Complete 42-entry `HIDEventType` table decoded from constant getters; it matches IOKit's public
  `IOHIDEventType` enum. Recorded in `docs/protocol.md`.
- `symbolicHotKey` (0x18) and `power` (0x19) are event types with **no report struct**, so lock
  cannot travel as a dedicated power report.
- `boundaryScroll` (0x1c) is distinct from `scroll` (0x6).
- `initialReportBitCount` decoded for all 16 report types with one. `AbsolutePointerReport` at
  152 bits / 19 bytes independently confirms the `HIDReport` heap layout against the runtime
  `HIDReport.init(bitCount:id:)` capture (`x0=0x98`, `x1=0x13`).
- `UniversalHID.KeyboardFilter.updateCopyMask(oldValue: HIDEventMask, newValue: HIDEventMask) ->
  [HIDReport]` at `0x5b0bc`; `HIDEventMask` is an `OptionSet` over `UInt`, so both arguments are
  plain integers in `x0`/`x1`.

### Retractions

1. **"Device Hub's Lock shortcut does not hit `init(_report:)` on any of the five keyboard-family
   report types."** Invalid. `init(_report:)` is a reinterpret wrapper, not a construction path, so
   those five breakpoints measured an empty set regardless of what Device Hub sent. Withdrawn from
   `docs/protocol.md`.
2. **"Keyboard usage `0x66` locks the screen."** Wrong, concluded twice. The first rested on a
   single 39 KB black screenshot; the second checked only that the screen was black afterwards, not
   that it was bright beforehand. The A/B control (experiment 9,940,630 bytes bright vs control
   9,935,071 bytes bright) shows `0x66` does not lock; the black screenshots were the device's own
   fast auto-lock. Usages `0x82` and `0x32` were tested the same way and also do not lock.
3. **"The 104 -> 168 bit `ScrollReport` change fixed a truncation."** `ScrollReport`'s
   `initialReportBitCount` is 104, and the fields we write fit inside it. The change is harmless but
   was not a fix, and scroll remains broken. The truncation was real only for `DigitizerReport`
   (320 -> 464), where the contact-0 swipe bits at 424/429/434 were being silently dropped.

### Known, not fixed

- **Lock / unlock.** Reproduction still open; `updateCopyMask` is the next tap.
- **Scroll.** Reports accepted at every layer, device does not scroll. Open leads: the flags-byte
  phase packing (bits 0-3 and bit 7), whether `boundaryScroll` rather than `scroll` is what Device
  Hub emits, whether service `0x501` is the right target, and whether an `AbsolutePointerReport`
  (ID 19, which Device Hub sends continuously and `ipb` never sends) must establish a cursor first.
- **Media wedge.** Cumulative over ~30 stream sessions, host-side, survives an `avconferenced`
  restart, cleared only by reboot or replug. Exact resource unidentified.
- **`ipb uhid-swipe-report` semantics.** Unverified.

## 2026-09-09 — Lock solved: Consumer 0x0c/0x30, held

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.

`ipb button 0x0c 0x30 0.60` locks the screen. Shipped as `ipb lock [hold_seconds]`, default 0.7 s.

### Hold threshold

Each trial: `ipb home` to wake, then the button, then a screenshot; brightness is the mean of a
32x32 greyscale reduction.

| Hold | Brightness after | Locked |
| --- | --- | --- |
| 0.08 s | 131.5 | no |
| 0.15 s | 131.5 | no |
| 0.25 s | 131.5 | no |
| 0.40 s | 131.5 | no |
| 0.45 s | 130.9 | no |
| 0.50 s | 0.0 | yes |
| 0.55 s | 0.0 | yes |
| 0.60 s | 0.0 | yes |

### Controls

The device's own auto-lock is the confound, and it defeated the first attempt at this
measurement. Measured with no button pressed at all:

| Idle after wake | Brightness |
| --- | --- |
| 0 s | 131.6 |
| 2 s | 87.2 |
| 4 s | 87.3 |
| 6 s | 87.3 |
| 10 s | 0.0 |

So a trial must finish within ~6 s of the wake. Step costs were timed: `ipb home` 1.35 s,
`ipb screenshot` 1.75 s, `ipb button ... 0.60` 1.72 s — a minimal wake/press/screenshot path is
4.82 s, which fits. The first attempt used a wake, a screenshot, the press, a 2 s settle and a
second screenshot, well past 10 s, so **both arms blanked** and the comparison was meaningless.
That failure was caught by its own control, not by inspection.

Matched-elapsed A/B at 4.82 s, alternating:

| Trial | Press | Brightness |
| --- | --- | --- |
| e1 | yes | 0.0 |
| c1 | no | 131.5 |
| e2 | yes | 0.0 |
| c2 | no | 131.4 |

### Locked, not merely dark

Blanking the screen and then waking it produced the **lock screen** — padlock glyph, clock,
battery text, flashlight and camera affordances — rather than the Home screen. Brightness alone
cannot distinguish "screen off" from "locked", and cannot distinguish "locked" from "unlocked"
either, since a lock screen is bright. The screenshot was inspected, not just measured.

`ipb lock-state` is **not** a usable discriminator: `passcodeRequired: true` and
`unlockedSinceBoot: true` read identically when locked, awake, and auto-locked. It reports whether
a passcode is configured, not the current screen lock state.

### Why this took three failed rounds

Every earlier candidate (`0x66`, `0x82`, `0x32`) was sent on the Keyboard page through `ipb key`,
i.e. the `KeyboardReport` (ID 1) path. The Consumer page was excluded by the
`init(_report:)` breakpoint result, which was invalid — a reinterpret wrapper is not a
construction path, so the test measured an empty set. Compounding it, a short press on the
correct usage does nothing, so the right guess would still have read as a failure without the
hold. The prediction that it would be Consumer `0x30` came from a peer review reasoning from
Apple's public `IOHIDUsageTables.h` plus the already-verified Home = `0x0c/0x40`.

### Known, not fixed

- **Unlock.** A short `0x0c/0x30` press does not wake a locked device (0.0 before, 0.0 after), and
  the device requires a passcode once locked. No unlock path is known.
- **Scroll.** Still unreproduced. `boundaryScroll` is now **ruled out** as a suspect:
  `ScrollFilter.init` (UniversalHID `0x58358`) sets its event mask to `0x20040` — scroll plus
  pointer, with no boundaryScroll bit — so Device Hub's own scroll path never involves it. The
  leading hypothesis is now that `0x501` is a trackpad-hinted service and iOS delivers trackpad
  scroll to the view under the pointer, which requires an `AbsolutePointerReport` (ID 19) session
  that Device Hub maintains continuously and `ipb` never establishes.

## 2026-09-09 — First real Device Hub capture (operator-paced)

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.
Capture: 2376 records over 150 s, 11 steps, 0 tap errors, operator-ended detach,
Device Hub survived.

All five taps bound (verified in the lldb log before trusting any zero).

### Valid negatives (tap bound, zero hits, other taps firing throughout)

- **The `UInt64` `send(report:to:)` overload is never used.** Zero hits while the
  `HIDServiceID` overload took 493. Device Hub's DeviceKit call site uses the typed one.
- **`KeyboardFilter.updateCopyMask` is not on the lock path.** Zero hits across the Cmd-L
  window. The hypothesis that it was the shortest path from key transition to wire bytes was
  wrong.

### What Device Hub actually sends

Report sizes are read from word0 of the `HIDReport` ABI pair, which is a Data range
(start in the low 32 bits, end in the high 32 bits).

| Operator action | Reports Device Hub sent |
| --- | --- |
| Pointer moved over the phone view | AbsolutePointer, 19 B |
| Idle | nothing at all |
| Cmd-L (lock) | AbsolutePointer ×10, **39 B ×4** |
| Scrolling a Settings list | Scroll 21 B ×198, **Digitizer 58 B ×2**, AbsolutePointer ×31 |
| Pointer resting on the list, no gesture | AbsolutePointer ×3 |
| Two-finger scroll, pointer on the list | Scroll 21 B ×163, **Digitizer 58 B ×44**, AbsolutePointer ×29 |

Two findings that change the scroll work:

- **Device Hub's scroll reports are 21 bytes / 168 bits**, not the 104-bit
  `initialReportBitCount`. The 104 -> 168 change in `ipb` therefore matches what Device Hub
  puts on the wire. The 2026-09-09 retraction above was right that it did not fix a
  *truncation* (the fields written fit in 104 bits) but wrong to imply 168 was arbitrary.
- **Device Hub sends 58-byte Digitizer reports throughout a trackpad scroll** — 44 of them
  during a single two-finger scroll. `ipb` sends none. A two-finger trackpad gesture is being
  reported as digitizer contacts alongside the scroll reports, which is a stronger candidate
  for the missing precondition than the AbsolutePointer cursor hypothesis.

### Invalidated by the harness's own guard

All three taps shed at 121-123 s for exceeding their hit budget. The decisive
pointer-precedence window ("move the pointer outside the view, then scroll") begins at
127.6 s, **after** the shed, so its emptiness is not evidence. Per the methodology's own rule,
that comparison is void and needs a re-run. The shed was recorded, surfaced by `decode.py`,
and caught before the window was read as a result — which is what the guard is for.

Cause: the filter chain is a reduce over every filter, so `KeyboardFilter.filterEvent` and
`ScrollFilter.filterEvent` fire for *every* event regardless of type. Three taps at ~31 hits/s
each exceeded a 20/s budget. The manifest is now reduced to the single universal `send` tap and
the budget raised to 60/s; the filter taps are commented out with this evidence rather than
deleted.

### Decoder defect found and fixed

Every report came back "storage header unreadable" while the lengths decoded perfectly. The
decoder looked for the storage pointer in word0, but word0 is the Data *range* and the tagged
pointer is in word1 (top byte a discriminator, e.g. `0x4000000a89eba800`). Fixed, and the raw
storage head is now always recorded so a wrong guess about the buffer offset shows up as data.
The bytes themselves are still uncaptured; that is what the next run is for.

## 2026-09-09 — Second capture: clean, and it answers both open questions

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.
Capture: 497 reports over 127 s, one tap, **0 sheds, 0 tap errors**, operator-ended detach,
Device Hub survived. **497 of 497 reports decoded to bytes** via the storage pointer in word1.

The three fixes from the previous run all held: the manifest reduced to the single universal
`send` tap stayed at ~4 hits/s average and never approached the 60/s budget; the word1 pointer
decode produced bytes on every record; and the timed windows let the operator perform steps that
depend on pointer position, which the ENTER-gated version had made impossible.

### Per-window result

| Window | Reports |
| --- | --- |
| Pointer moved over the phone view (liveness) | AbsolutePointer ×61 |
| Idle | **nothing** |
| Cmd-L to lock | **Keyboard ×2, nothing else** |
| Two-finger scroll, pointer **on** the list | Scroll ×67, AbsolutePointer ×19 |
| Two-finger scroll, pointer **outside** the view | **Scroll ×0**, AbsolutePointer ×44 |
| Idle | **nothing** |

The liveness window was non-empty, so the negatives in this run are valid.

### Scroll: answered

The pointer-precedence comparison that the previous run lost to a shed now has a clean result.
The same gesture produces 67 scroll reports with the pointer over the list and **zero** with the
pointer outside the view. Device Hub will not emit a scroll report unless the pointer is over the
phone view.

A scroll is also a six-part sequence, not one report: AbsolutePointer to place the cursor, then
Scroll with flags `0x80` (may-begin), `0x01` (began), `0x02` ×N (the movement), `0x04` (ended),
then a momentum tail with flags `0x00` and momentum 2 then 1, deltas decaying to zero. Observed
twice, once per physical scroll. Full byte layout, verified field by field against these captures,
is in `docs/protocol.md`.

`ipb` sends a single bare movement report with no pointer, no phase opening, no end, no momentum
tail and no timestamp. That is why it is accepted and ignored.

### Lock: answered, and it is not what we were looking for

Cmd-L produces exactly two `KeyboardReport`s (ID 1, 39 bytes) differing in one byte. Byte 29 bit 3
is absolute bit 235, and `ipb`'s own builder maps usage to `bit = usage + 8`, so that is usage
`0xE3` = Keyboard Left GUI — the Command modifier. Command down, Command up, nothing else.

AppKit consumes the "L" as a menu shortcut, and no lock command reaches
`UniversalHIDService.send`. **Device Hub does not lock the phone over UniversalHID at all.** The
universal tap captured 497 reports across the run and only those two during the lock window, so
this is a valid negative rather than a missed capture.

This closes the question that three earlier rounds chased: there was never a lock report on this
path to find. `ipb lock` works by an unrelated and independently verified route (Consumer
`0x0c`/`0x30`, held).

### Corrections this run forces

- The 2026-09-09 retraction of the `ScrollReport` 104 -> 168 change was too strong. Device Hub's
  scroll reports are 21 bytes / 168 bits on the wire, so 168 is correct; the change simply was not
  a *truncation* fix, since the fields `ipb` writes fit in 104 bits.
- `KeyboardFilter.updateCopyMask` is not on the lock path (bound, zero hits). The hypothesis that
  it was the shortest route from key transition to wire bytes was wrong.
- The `UInt64` `send(report:to:)` overload is never used; Device Hub uses the `HIDServiceID` one.

### Known, not fixed

- **Scroll is understood but not yet implemented.** `ipb` needs AbsolutePointer support plus the
  full phase sequence and momentum tail.
- **Unlock.** No route known; Device Hub's own lock does not traverse UniversalHID, so this
  capture says nothing about it.
- **Media wedge.** Unchanged.

## 2026-09-09 — Correction: waking works, and the button is a toggle

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.

Two earlier records in this file say unlock is unsolved. **They are wrong**, and the operator
was right to push back.

Consumer `0x0c`/`0x30` held is the side button, and like the side button it **toggles**. The
same 0.7 s hold that locks an awake screen wakes a dark one. Shipped as `ipb power`, with
`ipb lock` and `ipb wake` as aliases for the same press.

### How the error happened

The negative rested on one trial: a locked device, a **0.08 s** press, brightness 0.0 before and
0.0 after. That is a true observation about a short press, and it was generalised into a property
of the whole route. The correct reading was available in the same session's own data — locking
had already been shown to need ≥0.5 s, so a 0.08 s press failing to wake says nothing about
whether a held press would.

A second, sloppier factor: because the press toggles, a test that does not verify the starting
state measures nothing. An intermediate run produced "hold 0.08 → 141.8 before" — the device was
already dark, so the `lock` that was supposed to darken it woke it instead, and the row was
meaningless. Every row below drives the device to a screenshot-verified state first.

### Measurement, both directions, state verified before each trial

| From | Hold | Result |
| --- | --- | --- |
| bright | 0.70 s | dark |
| dark | 0.08 s | stays dark |
| dark | 0.20 s | stays dark |
| dark | 0.40 s | stays dark |
| dark | 0.70 s | **wakes, 132.0** |

Toggle behaviour end to end, through all three command names:

```
start            132.1
after ipb lock     0.0
after ipb wake   131.8
after ipb power    0.0
after ipb power  131.9
```

Waking stops at the lock screen (padlock, clock, flashlight and camera affordances, confirmed by
inspecting the screenshot). The passcode is not bypassed.

### Superseded

- The 2026-09-09 "Lock solved" record's *Known, not fixed* entry beginning "**Unlock.** A short
  `0x0c/0x30` press does not wake a locked device" is withdrawn.
- The 2026-09-09 "Second capture" record's *Known, not fixed* entry beginning "**Unlock.** No
  route known" is withdrawn. Device Hub's own lock still does not traverse UniversalHID, which
  remains true and is unrelated to how `ipb` does it.

## 2026-09-09 — Scroll implemented from the captured sequence: works, intermittently

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.

`ipb scroll-gesture <x> <y> [dx] [dy] [service_id] [steps]` and `ipb abs-pointer <x> <y>` send
what Device Hub sends: an `AbsolutePointerReport` placing the cursor, then the scroll phase
sequence (`0x80` may-begin, `0x01` began, `0x02` ×N, `0x04` ended) and a momentum tail
(`0x00` with momentum 2 then 1, deltas decaying). The whole sequence goes over one connection,
which is why it is one helper command rather than several CLI calls.

**Status: the device now responds, but only about 3 times in 5.** This is a real change from
never responding at all, and it is not yet a finished feature.

### What was wrong, and how each was found

1. **`uhidHIDReportInitData` is not a usable way to build a report here.** Assembling a `Data`
   and passing it produced reports that built fine (`result = 16`) and then trapped inside
   CoreDevice's send — SIGTRAP, exit 133, no message. Dumping the report words showed why: for a
   report built from UniversalHID's own `Data` the storage pointer at `+16` dereferences to the
   bytes, and for a Swift-native `Data` built from an array it dereferences to null. Reports are
   now allocated with `uhidHIDReportInit` and filled with `uhidHIDReportSetBitABI`, the same way
   every working builder in this file does it. No new ABI shim was added.
2. **The timestamp was in the wrong unit.** `CLOCK_UPTIME_RAW` nanoseconds gave ~6.4e13 where
   Device Hub's captured values were ~1.4e12 — a factor of ~46, which is the 24 MHz Apple Silicon
   timebase. Device Hub stamps reports with raw `mach_absolute_time()` ticks. After the fix our
   values (~1.54e12) match Device Hub's magnitude (~1.39e12).
3. **The step rate was guessed.** 12 ms between reports; Device Hub's own median gap over a
   captured two-finger scroll is 20.7 ms (n=47, min 10.3). Now 20 ms.

### Byte comparison against Device Hub, same phase

```
ipb        07 02 00 00 f8  00 00 00 00  cd cc ff ff  a0 a4 e4 71 67 01 00 00
Device Hub 07 02 00 00 fb  f4 fd ff ff  6e da ff ff  52 0c 79 06 46 01 00 00
```

Structurally identical; the remaining differences are magnitudes and a small non-zero `accelX`
that Device Hub carries even on a vertical scroll.

### Reliability, measured

List positioned mid-way with known-good swipes, then alternating directions so it never pins
against a limit. `mean_abs_diff` is over a 32×32 greyscale reduction.

| dy | diff |
| --- | --- |
| -25 | 6.6 |
| +25 | 0.0 |
| -25 | 6.5 |
| +25 | 6.1 |
| -25 | 0.0 |
| **0 (null control)** | **0.0** |

The `dy = 0` null control reading 0.0 is what makes the non-zero rows meaningful. A swipe
control (`ipb swipe 0.5 0.75 0.5 0.35`) on the same list reads 7.5, so the successful gestures
move the list about as far as a real swipe does.

### Method notes worth keeping

- An early "control" used `ipb scroll 0.5 0.75 0 0.30`, which drags *downward* on a list already
  at the top, so it correctly did nothing and briefly looked like the measurement was broken.
  The screenshots were byte-identical, which is what prompted checking capture liveness at all:
  Settings → Home reads 149.5, so capture was live and the control was simply wrong.
- Two intermediate sweeps were void because a second phone had been plugged in and `ipb` refuses
  to guess between connected devices (exit 3). Pin `DEVICE_ID` for any measurement run.

### Known, not fixed

- **Scroll fires about 3 times in 5.** Unresolved. The next step is to trace `ipb`'s own helper
  with `Experiments/devicehub-trace` — it is our own process, so no library-validation problem
  and no operator round is needed — and diff the emitted sequence against Device Hub's captured
  one, rather than tuning parameters against a coarse screenshot diff.
- **The service ID is still an assumption.** Device Hub passes the `HIDServiceID` indirectly
  (`x2` is a pointer), and the capture never dereferenced it, so `0x501` is inherited from
  earlier work rather than confirmed. Sweeping 0x300/0x301/0x101/0x400/0x500/0x501 produced no
  difference, which is consistent with the service not being the blocker, but does not confirm
  the value. The tracer should dereference `x2` on the next capture.

## 2026-09-09 — Mirror scroll: both axes were inverted

Reported from real use of `ipb mirror`: horizontal scroll worked but ran opposite to Device Hub,
and vertical scroll did nothing on either the Home screen or Settings.

Both are one bug. `convertScroll` passed AppKit's `scrollingDeltaX/Y` through with its delivered
sign, carrying a comment that the sign was `UNVERIFIED` and needed real-device calibration. It is
now calibrated:

- A captured two-finger scroll **down** put `y = -5..-8` on the wire (`docs/protocol.md`).
- The mirror, passing AppKit's sign through, moved the device the **opposite** way from Device Hub
  for the same physical gesture.

So Device Hub negates the delivered delta on both axes. This host has natural scrolling on
(`com.apple.swipescrolldirection` unset).

The asymmetry in the report — horizontal "reversed", vertical "dead" — is explained by where the
inverted direction lands rather than by the axes differing. An inverted vertical scroll on
Settings pushes against the top of the list, and the Home screen does not scroll vertically at
all, so vertical reads as nothing happening while horizontal reads as backwards.

Also changed: the mirror now builds its reports with `uhid_make_scroll_wire_hid_report` instead
of `uhid_make_scroll_hid_report`, so they carry `remoteTimestamp`. Device Hub sets it on every
report and the shim path left it zero. Byte 1 carries the phase (`0x80`/`0x01`/`0x02`/`0x04`) and
byte 2 the momentum, which is exactly what the mirror's `scroll.phase` and `scroll.momentum`
already held.

**Verified on device** (2026-09-09, mirror session): confirmed together with the pointer fix below.
The sign fix alone was not sufficient — horizontal scrolled the right way afterwards but vertical
still did nothing, which is what led to the pointer finding.

### Still not done

Superseded by the "vertical needs a pointer" record below: the mirror now sends an
`AbsolutePointerReport` before the scroll that opens a gesture, and that is what made vertical
scrolling work.

## 2026-09-09 — Mirror scroll: vertical needs a pointer, horizontal does not

Reported after the sign fix: horizontal scroll works, vertical still does nothing on Home or
Settings. A `--csv` capture from a real mirror session settled it.

661 events, **every one `sent`, zero rejects, every `report_code = 0`**. So nothing was being
dropped or refused; the mirror was successfully sending vertical scroll reports the device did
nothing with.

Bursts, split on gaps over 1 s:

| Burst | events | Σx | Σy | median &#124;dx&#124; | median &#124;dy&#124; | rate | outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 vertical | 372 | -103 | -346 | 1 | **6** | 60 Hz | **no effect** |
| 2 horizontal | 117 | +492 | 2 | 3 | 0 | 60 Hz | worked |
| 3 horizontal | 105 | -710 | -56 | 4 | 0 | 60 Hz | worked |
| Device Hub vertical (captured) | 67 | — | — | — | 5-8 | 48 Hz | works |

This killed two hypotheses on the spot. **Magnitude is not the problem**: the failing vertical
burst had a median |dy| of 6, squarely inside Device Hub's working 5-8 band, while the *working*
horizontal bursts had smaller deltas (3 and 4). **Rounding loss is not the problem** either: the
float sums equal the integer sums exactly, so AppKit was already delivering integral deltas.
**Rate is not the problem**: all three bursts ran at 60 Hz.

What is left is the target. Horizontal scrolling on the Home screen is a page gesture that needs
no particular view under the cursor; a Settings list scroll has to be routed to the view being
scrolled. The mirror sent **no `AbsolutePointerReport` at all**, so the device had no cursor
position to route to. This also explains why `ipb scroll-gesture`, which does send one, scrolled
Settings vertically in the earlier test while the mirror could not.

Fix: the mirror now captures the pointer position on each scroll event -- for scroll events `x`
and `y` are the deltas, so the position needed its own field -- and sends an `AbsolutePointer`
report before the scroll that opens a gesture.

**Verified on device** (2026-09-09, mirror session): both axes now scroll, in the same direction as
Device Hub, on the Home screen and in Settings. Operator confirmation after a live mirror session.

Scroll is now working through `ipb mirror`. It took three separate fixes, and only the last one
mattered on its own: the report had to carry `remoteTimestamp`, both axes had to be negated, and
the device had to be given a cursor to route the gesture to.


## 2026-09-09 — Mirror: Cmd-L lock/wake, and the shortcut inventory

`ipb mirror` gained `⌘L`, which locks a lit screen and wakes a dark one. Device Hub uses the same
key for it. Device Hub's own `⌘L` never reaches UniversalHID — only the Command modifier does
(see `docs/protocol.md`, "Lock") — so the mirror sends the Consumer `0x0c`/`0x30` usage `ipb`
established instead.

The hold had to be special-cased. The shortcut sender presses at step 0 and releases at step 1
with `delay = step==0 ? .08 : .12`, i.e. an 80 ms tap, which is correct for Home and volume and
below the threshold for lock: 0.45 s does nothing, 0.50 s acts. Lock now holds 0.7 s and the
other shortcuts are unchanged.

Full inventory as of this change (`Sources/mirror.m`, `performKeyEquivalent:`), also printed to
stderr at startup:

| Shortcut | Effect | Path |
| --- | --- | --- |
| `⇧⌘H` | Home | Consumer `0x0c/0x40` |
| `⌃⇧⌘H` | App Switcher | digitizer drag sequence |
| `⌘↑` | Volume up | Consumer `0x0c/0xE9` |
| `⌘↓` | Volume down | Consumer `0x0c/0xEA` |
| `⌘L` | Lock / wake | Consumer `0x0c/0x30`, held 0.7 s |
| `⇧⌘S` | Screenshot | host-side, latest frame |
| `⌘0` | Zoom to fit | host-side |
| `⌘1` | Actual size | host-side |

Modifier matching is exact equality, not a subset test, so a stray modifier silently selects a
different binding or none. Key repeat is ignored.

**`⌘L` not yet verified on device.**

### Also in this change

- `cd_lock_button` deleted from `Sources/action_sender.m`. It hardcoded `0x0c`/`0x30` with an
  80 ms hold, was unreachable from the CLI, and would not have worked at that hold. The usage was
  right the whole time and the hold was the bug. `cd_button_click` is now the only path.
- `README.md` gained `ipb scroll-gesture` and `ipb abs-pointer`, which were only in the wrapper's
  usage text.
- The "Still not done" note in the mirror-scroll sign record contradicted the record below it
  (it said the mirror sends no `AbsolutePointerReport`, which the next record fixes); it now
  points at that record instead.

## 2026-09-09 — Correction: the lock hold was picked without an upper bound

`⌘L` in the mirror opened **Siri** instead of locking. The hold was set to 0.7 s, chosen from a
sweep that only ever established the *lower* bound — "0.45 s does nothing, 0.50 s acts" — and
never asked how long is too long. On the device a short side-button press locks and a long one
opens Siri, so 0.7 s was on the wrong side of a boundary that was never measured.

### Sweep with the upper bound included (CLI path)

From a lit Home screen, `ipb button 0x0c 0x30 <hold>`, screenshot one second later:

| Hold | Brightness | Screen |
| --- | --- | --- |
| 0.08 s | 94.0 | unchanged Home |
| 0.20 s | 94.0 | unchanged Home |
| 0.35 s | 0.0 | locked, screen off |
| 0.50 s | 0.0 | locked, screen off |
| 0.60 s | 14.9 | passcode entry |
| 0.70 s | 14.9 | passcode entry |
| 0.90 s | 14.9 | passcode entry |

The 14.9 rows were inspected, not just measured: they are the passcode keypad, **not** Siri.

### The two paths are not equivalent, and the reason is NOT established

Siri could not be reproduced from the CLI at any hold, while the mirror reached it at 0.7 s. Both
call the same `coredevice_send_hid_button_custom` with the same states.

**Retracted:** an earlier version of this record explained the difference as the CLI tearing its
connection down early, making its effective hold shorter than nominal. That is wrong.
`HIDCTL_WAIT_MS` defaults to 700 ms (`bin/ipb:30`) and is read before disconnect
(`action_sender.m:1675`), so `ipb` keeps the connection alive well past the sequence. The actual
sequence is: DOWN returns, wait `hold`, UP returns, wait 120 ms, barrier returns, wait 100 ms,
keep-alive, cancel. Nor does the barrier prove the device executed the release — the button
barrier ABI returns zero unconditionally (`Sources/mercury_abi.S:225`).

No root cause has been selected. The controlled experiment is to hold the duration fixed and vary
only the disconnect time, restoring the same starting state before each run:

```sh
DEVICE_ID=<uuid> HIDCTL_WAIT_MS=0    ./bin/ipb button 0x0c 0x30 0.08
DEVICE_ID=<uuid> HIDCTL_WAIT_MS=700  ./bin/ipb button 0x0c 0x30 0.08
DEVICE_ID=<uuid> HIDCTL_WAIT_MS=3000 ./bin/ipb button 0x0c 0x30 0.08
```

then repeat for 0.7 s, aligning DOWN/UP/cancel against host time with an external recording rather
than screenshotting "one second after the command returns" — that observation point moves with the
keep-alive.

What does hold regardless: a hold value is **path-specific and measured**, not transferable between
`ipb` and the mirror.

### Fix

The mirror's `⌘L` is now a short press (0.08 s), identical to every other shortcut there. The
special-cased hold is gone.

**`ipb lock`'s default is changed from 0.7 s to 0.5 s.** Leaving it at 0.7 s while the table above
puts 0.60/0.70/0.90 s on the passcode screen was a live regression, and this record contradicted
itself about it three paragraphs apart.

Picking the replacement needs the two sweeps read together, because they disagree:

| Hold | First sweep ("Lock solved") | Second sweep (this record) |
| --- | --- | --- |
| 0.35 s | not tested | locked |
| 0.40 s | not locked | not tested |
| 0.45 s | not locked | not tested |
| 0.50 s | locked | locked |
| 0.55 s | locked | not tested |
| 0.60 s | locked | passcode screen |

0.50-0.55 s is the only band both sweeps call a clean lock, so the default is 0.5 s. That the
sweeps disagree at 0.60 s at all is itself evidence the hold-to-outcome mapping is less stable
than either sweep alone suggests — which weakens the broader "the CLI path is verified" claim, not
just the specific number.

**Mirror `⌘L` not yet re-verified after this change.**

## 2026-09-09 — Review of the mirror changes (gpt-6-astra), and three defects fixed

An independent review of this session's `ipb mirror` changes found three defects in the ~15 lines
that had just been added, plus one wrong causal claim and one stale string. Its verdict on the
change set was **not ready to treat as accepted**.

### Fixed

1. **The pointer was placed once per *session*, not per gesture.** `starts` is only set when
   `gScrollActive == NO` (`mirror.m`, `scrollWheel:`), and a phase-less wheel has no AppKit end
   and no idle timeout, so one session can span scrolling one list, moving the mouse to another,
   and scrolling again — all against the first position. The pointer is now resent whenever the
   mapped position has moved (epsilon 0.001), not only when a session opens.
2. **A gesture starting off the phone view still scrolled** — *but see the reachability
   correction below; this path is effectively dead in the current build.* `mapEvent:` fails in the
   letterboxing and the failure was recorded but not acted on, so a scroll begun over a black bar
   would be sent anyway and act on whatever target the device still held. A new gesture in that
   state is now rejected as `scroll_off_target`. An already-running gesture is deliberately left
   alone so its END still reaches the device; dropping every out-of-bounds event would strand the
   session open.
3. **Pointer failures were swallowed.** Both the build result and the send return code were
   discarded, and the record was then marked `Sent` from the *scroll's* code. A failed pointer now
   fails the event (`BuildFailed` / `SendFailed`) and the scroll is not sent, since without a
   current pointer it would act on a stale target. Repo rule: failure is an exit code, not a log
   line.

While restructuring (3) an error was introduced and caught before commit: guarding only the
`r.reportCode` assignment with a dangling `else` left the following line to recompute
`r.result`, which would have rewritten `BuildFailed` as `SendFailed`. The guard is now an
explicit `pointerFailed` block.

### Corrected claims

- **The "connection teardown truncates the hold" explanation is withdrawn** (see the record
  above). `HIDCTL_WAIT_MS` defaults to 700 ms and is read before disconnect, so `ipb` does not
  exit immediately. No replacement root cause has been established.
- **`mirror.m` advertised `⌘L` as implemented on one line and unimplemented on the next.** Fixed.
- **The 0.5 ms per-send latency figure was over-claimed.** It comes from the scroll path in
  `/tmp/scroll.csv`, while App Switcher uses the digitizer path. It supports "no tens-of-
  milliseconds host stall was observed"; it does not establish App Switcher's per-input cost.
- **CSV recount**: 661 total events = 594 scroll + 67 touch, not 661 scroll.

### Accepted as-is, with a verification owed

- **`gScrollServiceID = 0x501` for the pointer.** Kept — it works on device — but not confirmed to
  be Device Hub's target. The capture recorded `x2` as an address without dereferencing it, and an
  address cannot be resolved offline. Next capture should run, at a `send_id` breakpoint,
  `register read x2` then `memory read --format x --size 8 --count 1 $x2`, and record the target
  **separately for the 19-byte pointer and the 21-byte scroll** rather than assuming they match.
  That earlier service sweep showed no difference does not prove any ID is correct.
- **Key mapping.** `⌘L` stays: following Device Hub inside a dedicated mirror window is better
  grounded than importing the browser address-bar convention. Exact-equality modifier comparison
  is correct and should **not** become a subset test — `⇧⌘H` is a subset of `⌃⇧⌘H`, so Home would
  capture App Switcher. Siri, recording and Action Button stay explicitly unimplemented; no usage
  codes should be guessed.

### Still owed, on device

- ~~Mirror `⌘L` at 0.08 s is unverified.~~ **Verified 2026-09-09**: `⌘L` locks and wakes in a live
  mirror session, no Siri.
- `ipb lock`'s 0.7 s default is **not** being changed on the strength of one sweep that conflicts
  with an earlier one. Re-measure with device, OS, starting state, helper binary and environment
  all pinned, covering lock and wake. Note also that the passcode screen may still be a locked
  state; "not locked" was the wrong description.
- The `HIDCTL_WAIT_MS` = 0 / 700 / 3000 experiment at fixed hold, timed against an external
  recording rather than a screenshot at a fixed delay after the command returns.
- `scripts/smoke_matrix.sh` has not been run for any of this.

### App Switcher

Not changed yet. The dwell dominates: 13 samples over ~0.36 s, a 1.05 s dwell, plus 0.25 s holding
the input drain afterwards, so the earliest a following input is processed is ~1.66 s. Suggested
experiment is to keep the path and total travel time but sample at ~60 Hz, and separately test
dwells of 0.15 / 0.25 / 0.40 / 0.60 s for the shortest that reliably enters the switcher, measuring
first-frame response, UP, card settle and when a following tap becomes usable — not just the final
screenshot. These are candidates, not verified parameters.

## 2026-09-09 — Second, independent review of the same changes

A second review ran independently of the first and converged on the same core findings (pointer
staleness, discarded pointer return code, the falsified teardown theory, no defect in the key
mapping). It surfaced two the first did not, and sharpened two more.

### New, and blocking

**`scripts/smoke_matrix.sh` has not run since any of these commits, and they are already on
`main`.** AGENTS.md Rule 4 makes that the definition of done, so none of this session's mirror
work is done regardless of the rest.

**`ipb lock`'s 0.7 s default was a live regression.** Fixed above: default is now 0.5 s, chosen as
the only band both CLI sweeps agree is a clean lock, and the record no longer contradicts itself
three paragraphs apart.

### Sharpened

- **The teardown theory is falsified at code level, not merely unsupported.** `usleep(hold)`
  happens *inside* `send_coredevice_button_event` (`action_sender.m:977`) with the connection
  alive, followed by the release, an explicit button barrier and a further 100 ms, all before the
  function returns and anything could be torn down. The hold is real and is not truncated by
  process exit. (The `HIDCTL_WAIT_MS` keep-alive is a second, separate reason the original claim
  was wrong.)
- **The Siri observation is n=1.** It was a single first attempt in the mirror, against a CLI
  sweep with repeated points across 0.6-0.9 s that never reproduced Siri once. Under Rule 3 that
  should not be theorised over further. The cheap way to settle both the mechanism and the
  CLI/mirror discrepancy is to run `ipb button 0x0c 0x30 0.7` under the `dhtrace` harness — tap
  the send on `ipb-helper` itself, which needs no operator round — and read the actual wall-clock
  gap between the press and release sends.
- **`0x501` is not a hardcoded guess.** `discoverService` (`mirror.m`) parses live CoreDevice
  descriptor output at startup, matching `"CoreDevice touchscreen("` against
  `"CoreDevice touchscreenGesture"`, so the ID is runtime-discovered for a real service. Sending
  the pointer to the same service the following scroll uses is a coherent choice. It remains
  unconfirmed only against what Device Hub itself targets, which one capture settles: tap
  `UniversalHIDService.send`, filter `report_id == 0x13`, dereference `x2`, and diff against the
  two IDs `discoverService` finds.

### Where the two reviews differed

On the once-per-gesture pointer, the second review found **no evidence of harm** — a trackpad
gesture does not move the macOS cursor mid-gesture, so one placement per gesture is architecturally
consistent with how the bottom-edge digitizer gesture already freezes its edge at touch-down. It
proposed a stress test (one deliberately long 5-10 s continuous scroll, watching for degradation)
rather than a change. The send-on-move fix already made covers that case anyway, at a measured
0.5 ms per send.

### App Switcher

Both reviews independently point at the dwell first: 1.05 s is 75% of the total, has never been
swept downward, and a real switcher animation completes in roughly 0.4-0.6 s. Suggested sweep is
0.5 / 0.7 / 0.85 / 1.05 s, taking the shortest that passes a 5/5 reliability check through the
existing `recents` smoke step, together with the 30 ms -> ~16 ms per-step change. Still not done.

## 2026-09-09 — Smoke gate for the mirror work

Host: macOS 27 beta, Xcode 27.0.0 Beta 6. Device: iPhone 12 mini, iOS 27.0 (24A5430a), localNetwork.
Commit: the mirror scroll/pointer/lock series through the `ipb lock` default fix.

```sh
DEVICE_ID=<uuid> SMOKE_INTERACTIVE=1 ./scripts/smoke_matrix.sh "$PWD" /tmp/ipb-smoke2
```

**SMOKE PASSED**, rc=0, **0 warnings, 0 identical consecutive frames** across 13 screenshots.
`05_after_recents.png` was inspected and shows the App Switcher card view, so the interactive
steps had real effect rather than merely returning zero.

This closes the Rule 4 gate that both reviews flagged as outstanding for this session's mirror
changes.

### The first attempt was a false pass, and that is a gate weakness worth recording

The run before this one reported `SMOKE PASSED` with rc=0 while the device sat on the **passcode
entry screen** for its entire duration. Every step returned rc=0 because the reports were sent
successfully; the device simply ignored all of them. 9 of 13 screenshots were identical to their
predecessor, including `after_tap`, `after_recents`, `after_long` and `after_escape`.

The script did print nine `WARN: ... identical to previous frame` lines, but **those warnings do
not affect its exit code** — it still exited 0 and printed `SMOKE PASSED`. AGENTS.md describes the
gate as exiting non-zero "on any failed step or unexpected output", and nine identical-frame
warnings on interactive steps are unexpected output. As it stands the gate reports a pass on a
locked device.

Cause of the lock state: the run was preceded by `ipb power` to light the screen, but the device
was already dark, so that press woke it to the passcode screen rather than to Home. `ipb` cannot
get past a passcode.

Procedure that avoids it, used for the passing run: take a screenshot and **look at it** before
starting, rather than assuming a wake command reached the Home screen.

### Known, not fixed

`scripts/smoke_matrix.sh` treats identical-frame warnings as advisory. It should fail the run, or
at minimum exit non-zero when an interactive step produces no visual change, so a locked or
unresponsive device cannot report a pass.


## 2026-09-09 — Reachability correction: the off-target scroll guard is near-dead code

`⌘L` at 0.08 s is **verified on device**: it locks a lit screen and wakes a dark one from a live
mirror session, with no Siri. That closes the last outstanding item from the mirror review.

The `scroll_off_target` guard added in response to review finding 4 does **not** guard a reachable
bug, and the record above overstated it.

`fitWindow` is called with `lockAspect = YES` at every site that runs once a video frame exists
(`mirror.m` 982, 1180, 1211), setting `gWindow.contentAspectRatio = gVideoSize`. The only
`lockAspect = NO` call (1205) is the placeholder window created before the first frame, when
`gVideoSize` is still zero and `mapEvent:` fails on its first check regardless. With the window
aspect locked to the video aspect, `AVMakeRectWithAspectRatioInsideRect` returns the full bounds
and every point inside the view is inside the content rect, so `pointerValid` is always true.

There are no black bars to scroll over. The path is reachable at most as a transient while
`gVideoSize` changes on device rotation, or before the first frame, where scrolling is already
rejected elsewhere.

The review read the code path correctly but did not check that the aspect ratio is locked, and I
applied the fix without checking reachability myself — which is exactly what Rule 3 exists to
prevent ("Edge cases with low reachability ... are recorded under 'known, not fixed' and are not
patched one by one"). This is the second time this session I acted on an assertion before testing
it; the first was asserting that plain touch reports cannot trigger system edge gestures, which
also only got settled by a controlled experiment after being challenged.

The guard stays — it is one condition plus an enum value, it is harmless, and the rotation
transient is real if rare — but it is recorded here as **near-dead code**, not as a defect fix.
Empirical check available at no cost: the mirror's summary prints a `black_bars` counter, which is
the number of `mapEvent:` failures. If it reads 0 across sessions, that is direct confirmation.


## 2026-09-09 — Device selection by prefix and name; grouped help

Host: macOS 26.5.1 25F74, CoreDevice 642.15, Xcode 27 beta 6.
Device: iPhone 12 mini, iOS 27.0 24A5430a, localNetwork transport.

### What changed in the contract

`ipb` now takes `-s <device>` / `--device <device>` before the command, matching adb's `-s` and
idb's `--udid`. The selector is a full CoreDevice UUID, a unique prefix of one, or a
case-insensitive substring of the device name or marketing model. `DEVICE_ID` still works and the
flag wins over it.

The reason it has to be resolved in `ipb` and not passed through: `devicectl` accepts neither form.

```
$ xcrun devicectl device info details --device 1D53
ERROR: The specified device was not found. (Name: 1D53) (com.apple.dt.CoreDeviceError error 1000)
$ xcrun devicectl device info details --device "iPhone 12 mini"
ERROR: The specified device was not found. (Name: iPhone 12 mini) (com.apple.dt.CoreDeviceError error 1000)
```

A full UUID is therefore passed straight through with no enumeration — the common case, and the one
an exported `DEVICE_ID` hits on every command, costs nothing. `devicectl list devices
--json-output` measured at 76 ms on this host, which is why the fast path exists rather than
validating every selector against the list.

Matching is most-specific-first (whole UUID, then prefix, then name/model substring) and each tier
must produce exactly one hit; ambiguity and no-match both exit 3 and print the attached devices with
transport and tunnel state. Observed with three devices attached:

```
$ ipb -s iPhone device
"iPhone" matches 3 devices; pick one with -s <uuid|uuid-prefix|name> or by setting DEVICE_ID:
  <uuid-a>  <name-a>  iPhone 15 Pro  (?, tunnel unavailable)
  <uuid-b>  <name-b>  iPhone 12 mini  (localNetwork, tunnel disconnected)
  <uuid-c>  <name-c>  iPhone 13 Pro  (wired, tunnel disconnected)
```

`ipb devices` and `ipb device` output are byte-for-byte unchanged, because `scripts/smoke_matrix.sh`
parses both.

`ipb help` now prints the ~30 user-facing commands in groups (device selection, input, screen, apps
and processes, files, system, escape hatches) instead of one flat list of 43; the HID report
commands moved behind `ipb help hid`. No command was renamed or removed. `ipb help` previously
fell through to the catch-all and exited 2; it exits 0.

### Gate

Two steps added to `scripts/smoke_matrix.sh`, right after the default device is resolved: the
default device's UUID prefix and its full name must both resolve back to the same UUID. That is the
only check that the resolver agrees with the auto-pick, and it is non-interactive.

```sh
DEVICE_ID=<uuid-b> scripts/smoke_matrix.sh . build/smoke-cli
DEVICE_ID=<uuid-b> SMOKE_INTERACTIVE=1 TAP_XY="0.15 0.12" scripts/smoke_matrix.sh . build/smoke-cli-i
```

Both `SMOKE PASSED`. The interactive run: 38 steps, all rc=0, **0 WARN lines and no identical
consecutive frames** across the 13 screenshots (checked with `md5 -q` over the frames in order).
Artefacts: `build/smoke-cli/`, `build/smoke-cli-i/`.

### Documentation

`README.md`: the overview now names `stream`, `mirror`, `power` and the devicectl verbs; a "Choosing
a device" section replaces the `DEVICE_ID`-only paragraph; the iOS-27-only list gained
`abs-pointer`, `scroll-gesture` and mirror scroll (everything on `0x501`); the mirror shortcut table
gained ⌘L and mentions scrolling; the feature matrix gained device selection, live stream and
mirror rows and splits `scroll` from `scroll-gesture`; "Interaction Backends" gained `power`,
`scroll-gesture`/`abs-pointer`, `stream` and `mirror`.

Two stale claims removed. The mirror section still described the 1184×2576 vs 1170×2532 coordinate
bias as uncompensated — commit `91ece71` crops the padding, so the window aspect matches the phone.
And it still listed Lock (⌘L) under "not implemented" after the 2026-09-09 record above verified it
on device. "Verified Scope" was a snapshot of the beta 2 run duplicating this file; it is now a
pointer to this file plus what the gate covers.


## 2026-09-10 — zsh completion, and what `brew upgrade` needs

Host: macOS 26.5.1 25F74, CoreDevice 642.15. Devices attached: iPhone 12 mini (iOS 27.0),
iPhone 13 Pro (iOS 27.0), iPhone 15 Pro (iOS 26.6.1).

`completions/_ipb` completes the command list with one-line descriptions and, after `-s` /
`--device`, the attached devices — offered twice, once by UUID and once by name, because `-s`
accepts either. Descriptions carry model, iOS version, transport and tunnel state, which is what
makes a list of three UUIDs readable. `make install` puts it in
`$(PREFIX)/share/zsh/site-functions/_ipb`, the path Homebrew links automatically.

Verified end to end in a real zsh completion run, not just by loading the file: a pty via
`script -q /dev/null zsh -i` with `fpath` pointing at `completions/`, fed a literal Tab.

```
$ ipb -s <Tab>
<uuid-b>  -- <name-b> (iPhone 12 mini, iOS 27.0, localNetwork, tunnel disconnected)
<uuid-a>  -- <name-a> (iPhone 15 Pro, iOS 26.6.1, localNetwork, tunnel disconnected)
<uuid-c>  -- <name-c> (iPhone 13 Pro, iOS 27.0, wired, tunnel disconnected)
<name-a>  -- iPhone 15 Pro, iOS 26.6.1
<name-b>  -- iPhone 12 mini, iOS 27.0
<name-c>  -- iPhone 13 Pro, iOS 27.0
```

Also checked in the same harness: `ipb scr<Tab>` lists screenrecord/screenshot/scroll/scroll-event/
scroll-gesture/scroll-report with their descriptions; `ipb service-id <Tab>` lists the five roles;
`ipb help <Tab>` completes to `hid`; and `ipb -s 12\ mini ho<Tab>` completes to `home`, so a
selector with a space does not break the command position.

A completion is user documentation that the shell executes, and a syntax error in it stays silent
until someone presses Tab, so the gate now loads it as its first step (host-only, 0 s).
`DEVICE_ID=<uuid-b> scripts/smoke_matrix.sh . build/smoke-comp` → `SMOKE PASSED`, 19 steps, all
rc=0.

### Homebrew

Nothing about the tap changed; `brew install --HEAD ipb` tracks this repository's `main`, and
`ipb update` runs `brew upgrade --fetch-HEAD ipb`. So an update needs the commits pushed to
GitHub and nothing else — the formula, its caveats and its install layout are unchanged apart from
the completion file, which `make install` handles. `VERSION` moved 0.1.0 → 0.2.0 because `-s` is a
new CLI contract and `ipb version` should tell the two apart.


## 2026-09-10 — `ipb update` reported success without updating

Host: macOS 26.5.1 25F80, Homebrew 6.0.22, CoreDevice 642.15.

### Reproduction

Homebrew install at `HEAD-047d906`, remote `main` at `9fba884`:

```
$ ipb update
ipb: Homebrew install; updating tap and formula
Warning: ipbtools/ipb/ipb HEAD-047d906 already installed
ipb: updated (ipb 0.1.0 (macOS 26.5.1 25F80, CoreDevice 642.15))
$ ipb version
ipb 0.1.0 ...
```

`brew upgrade` exits 0 when it decides there is nothing to do, and the wrapper took that as proof.
Reachability is every Homebrew user on every update; self-recovery is nil, because the next run
prints the same thing.

### Why both of Homebrew's answers are unusable here

`brew upgrade --fetch-HEAD ipb` compares the installed sha against the cached clone in
`~/Library/Caches/Homebrew/ipb--git`, which it does not refresh first. With the cache at 047d906
and the remote at 9fba884 it answered "already installed". `--greedy` and the fully qualified
`ipbtools/ipb/ipb` behaved identically.

`brew outdated --fetch-HEAD ipb` cannot be used as the gate either — it calls a HEAD formula
outdated unconditionally:

```
$ git -C ~/Library/Caches/Homebrew/ipb--git log --oneline -1
9fba884 Tab completion for -s, and the devices behind it
$ git ls-remote https://github.com/ipbtools/ipb.git HEAD
9fba8844f1ff4ec50b4fd92e28577fba6e095fda	HEAD
$ brew outdated --fetch-HEAD --verbose ipb
ipbtools/ipb/ipb (HEAD-9fba884) < latest HEAD
```

Cache, remote and installed all at 9fba884, still reported behind. An earlier draft of the fix
used this as the signal and consequently rebuilt on every run, then failed its own
did-it-move check — caught here, not shipped.

`brew reinstall ipb` is the one path that rebuilds from a fresh fetch; it moved 047d906 → 9fba884
correctly.

### The fix

Compare the shas directly: `brew list --versions ipb` gives `HEAD-<sha>`, and `git ls-remote` on
the formula's own head url (read from `brew info --json=v2`, not hardcoded, so a moved tap still
works) gives the remote. Equal is an early exit; otherwise `brew reinstall`, and the result is
checked against the remote sha before anything claims success. `brew upgrade` was removed rather
than kept as a first attempt — it cannot succeed where reinstall is needed, and two paths to one
concern is what Rule 2 forbids.

Verified after the fix was installed:

```
$ ipb update
ipb: already at the latest HEAD (HEAD-ef61d06)
$ echo $?
0
```

### Note for existing installs

The fix cannot fix its own delivery: an install predating it runs the old `update`, which will keep
reporting a false success. One `brew reinstall ipb` lands the new wrapper, and `ipb update` is
honest from then on.

### Gate

`DEVICE_ID=<uuid-b> scripts/smoke_matrix.sh . build/smoke-upd` → `SMOKE PASSED` on the iPhone
12 mini, 19 steps, all rc=0.


## 2026-09-14 — mirror freeze: a UniversalHID barrier hung 2.85 s with no timeout

Reproduced by the user with `--csv`. Raw trace kept locally at
`<scratchpad>/mirror-home-freeze.csv` (193 rows, not committed per the evidence rule); the decisive
rows are condensed below. Device/transport for this run not captured in the CSV.

### What the trace shows

The Home shortcut is **not** where the wire path failed. `seq 141 KEY_HOME` sent cleanly:

```
seq  type      result       report_return - received   barrier_return - report_return   codes
141  KEY_HOME  sent         0.6 ms                      207.3 ms                         report=0 barrier=0
```

That is the normal button click+barrier timing (press, +80 ms, +120 ms, barrier on `gButton`), so
`gButton` was healthy and Home reached the daemon. If Home had no visible effect on the device, the
cause is not in this trace and needs a screenshot to confirm.

The freeze is `seq 166`, a touch **UP** (end of a swipe, `mode=TOUCH`), five seconds after Home. Its
report — the finger lift — returned in 0.6 ms, so the gesture completed on-device. The **barrier**
that follows it (`mirror.m:767`, `coredevice_send_universalhid_barrier(gInput)`) then hung:

```
seq  type  result       report_return - received   barrier_return - report_return   codes
166  UP    interrupted  0.6 ms                      2846.2 ms                        report=0 barrier=0
```

`barrier_code=0` — the barrier eventually returned *success* on a connection that had already gone
invalid: during the 2.85 s block the connection's async error handler fired `inputError`, which bumped
`gGeneration` and marked this record `interrupted`. The return code is not trustworthy on a dropped
connection, exactly as in the button case.

Everything submitted during the hang piled up behind it on the serial input queue and drained as
rejects the instant the barrier unblocked:

```
seq 167..193  (27 events, gestures 12 and 13)  result=rejected  report_return=blank
  all t_received == 491706.56995x  (== seq 166 barrier_return; the queue moved only when it unblocked)
  submit span 491704.373 .. 491705.590  → ~1.2 s of real dragging lost
```

### Root cause (same as the 2026-09-… button-connection freeze)

The per-send barrier and report calls are synchronous with **no timeout of our own**. The only
watchdog is the whole-session one (`mirror.m:1422`, `runSeconds+10`). When a HID connection goes
invalid, the synchronous call blocks on the framework's internal timeout — measured at **2.846 s**
here, **2.988 s** and **3.188 s** in the button case — before returning (misleadingly with code 0),
and the serial input worker is dead for that whole window. This is the "no unbounded waits" clause of
AGENTS.md Rule 2 not being met at the per-send layer.

New this time: `gInput` (the touchscreen connection, the most heavily used one) dropped after 138
scroll reports plus taps and swipes — **under continuous load, not idle**. So the drop is not an
idle-reaping artifact, and a fix that adds our own timeout/cancellation to the synchronous send is
warranted independently of the earlier "idle vs never-healthy" question. Whether localNetwork
transport is the trigger (vs wired) is still open; this run's transport was not recorded.

Not yet fixed. The trace is a confirmed reproduction; the fix (bound the synchronous barrier/report
with our own deadline and treat expiry as a send failure, so the queue is released and the run exits
with a real error instead of freezing) is pending design approval.


## 2026-09-14 — mirror freeze reproduced headless on wired; transport is not the trigger

Host: macOS 26.5.1, CoreDevice 642.15. Device: iPhone 13 Pro, iOS 27.0, **wired, tunnel connected**.
Tool: the existing `Experiments/mirror/mirror_probe.m` (`build/ipb-mirror-probe`), which synthesises
its own gestures (`--gestures/--drag-seconds/--hz`) and sends report+barrier on a held `gInput`.
**No GUI input injection and no mirror window are needed to reproduce this** — the earlier claim that
it required a human at the keyboard was wrong.

### The signature matches the interactive capture exactly

```
seq 546  UP  interrupted  barrier_tail=783.3ms  report_code=0  barrier_code=0
exit=1 reason=UHID RemoteXPC error: Connection invalid; gesture abandoned
seq 547+ rejected, all t_received == the instant the barrier unblocked
```

Healthy barrier tails in the same runs are 3.5-5.3 ms. As in the interactive capture, the barrier
returns **code 0 — false success — on a connection that has already gone invalid**; the record is only
marked `interrupted` because the async error handler bumped `gGeneration` while the call was blocked.

### Wired reproduces it, deterministically

| run | rc | elapsed | died on barrier | seq | barrier tail |
| --- | --- | --- | --- | --- | --- |
| 3 s drag @ 60 Hz | 1 | 14 s | #3 | 546 | 783.3 ms |
| 3 s drag @ 60 Hz | 1 | 14 s | #3 | 546 | 762.1 ms |
| 3 s drag @ 60 Hz | 1 | 13 s | #3 | 546 | 817.3 ms |
| 3 s drag @ 30 Hz | 1 | 14 s | #3 | 276 | 744 ms |
| 1 s drag @ 60 Hz | 1 | 14 s | **#7** | 372 | 2240 ms |
| 6 s drag @ 60 Hz | 1 | 13 s | mid-drag | — | — |

**localNetwork is not required.** The open transport question from the previous record is answered:
a wired device reproduces the same failure, so the fix needs no transport caveat. Hang duration
varies (744-2240 ms here, 2846 ms on localNetwork) but the structure is identical.

### The trigger is elapsed time, not load

Event count (276 / 372 / 546 / 618) and barrier count (3 / 7 / mid-drag) both vary across configs;
what stays constant is **~13-14 s of session**. At 3 s drags that is 3 gestures, at 1 s drags 7 —
both exactly 10.5 s of input. So this is a lifetime, not a quota and not wear from traffic.

### It is not HID-specific: the media stream wedges at the same point

Media frames delivered, every run: **266, 267, 267, 322, 266, 266, 267** — essentially constant and
independent of whether any HID traffic was sent. With `--no-input` (media only, zero HID events) the
probe still died, but the connection that reported invalid was the **media** one:

```
noinput  rc=6  elapsed=41s  exit=6 reason=media RemoteXPC: Connection invalid  media frames=267
```

So the invalidation is not a property of the UniversalHID connection. Something wedges at ~266
frames and the failure then surfaces on whichever connection is next used. This lines up with the
already-recorded media wedge ("Narrow the media wedge: cumulative, host-side, and not caused by us").

**Not yet isolated:** the probe always runs media and HID together, as the mirror does, so this does
not prove the HID connection would survive without media. HID-without-media is the next experiment
and is not claimed here.

### Consequence for the fix

The barrier defect stands on its own and is now confirmed transport-independent: a synchronous
barrier with no deadline of our own, which on a dead connection blocks for hundreds of ms to seconds,
returns success, and strands every queued event behind it. Bounding it is correct regardless of what
turns out to wedge the media path.


## 2026-09-14 — Fix: synchronous HID sends are bounded by a deadline

`Sources/mirror.m`. Every synchronous CoreDevice HID send now goes through one helper,
`sendBounded`, which runs the uncancellable call on the global concurrent queue and stops waiting
after **0.5 s**. The abandoned call still runs to completion in the background; it simply no longer
owns the serial input queue. Expiry returns a distinct code (`-62`) and a distinct result
(`send_timed_out`), and is a failure — never a retry, nothing is re-sent.

Two memory-safety constraints shaped it, both real:

- The result is a `__block int` written by the still-running block. After a timeout that storage
  belongs to the block, so it is never read again on the timeout path.
- A C array cannot be captured by a block, and the report bytes must outlive an abandoned call.
  `sendReportBounded` therefore copies them to the heap and the block owns and frees the copy.
  Passing the stack array by pointer would have been a use-after-free once the call was abandoned.

`pointerFailed` was widened to include `SendTimedOut`; without that, a pointer placement that timed
out would still have gone on to scroll whatever target the device was holding.

### Verified against the deterministic reproduction

The same fix was applied to `Experiments/mirror/mirror_probe.m`, which is the harness that
reproduces the freeze in ~14 s, so the change could be measured rather than argued.

| | before | after |
| --- | --- | --- |
| barrier tail at the failing gesture | 783 / 762 / 817 ms | **505 / 501 ms** |
| `barrier_code` | `0`, a false success | `-62` |
| result | `interrupted` | `send_timed_out` |
| exit reason | `UHID RemoteXPC error: Connection invalid` | `UHID barrier exceeded the send deadline` |
| healthy barrier tails | 3.5-5.3 ms | 4-5 ms, unchanged |
| `abandoned_sends` | n/a | 1 |

The deadline is 0.5 s because healthy barriers are 3.5-5.3 ms (a 100x margin) while every observed
hang is 744 ms or longer. It is a constant, not an env knob: if evidence says it is wrong, the
constant changes with that evidence.

**What this does not fix:** the connection still goes invalid at ~14 s. This bounds the damage — the
freeze is capped at 0.5 s and reported honestly instead of a multi-second stall that returns success
— but the cause of the invalidation is the media-wedge investigation, still open.

Gate: `scripts/smoke_matrix.sh` → `SMOKE PASSED` on the wired iPhone 13 Pro. The mirror's own
interactive path is unchanged apart from these call sites and is covered by the probe, which shares
the contract; an interactive mirror run is still worth doing before relying on it.


## 2026-09-14 — Correction: it is HID traffic, not the media path

This retracts the "It is not HID-specific: the media stream wedges at the same point" section of the
earlier record today. That section rested on media frame counts landing on 266/267/267/322/266/266/267
across runs and on a single `--no-input` run dying at 41 s. Both were host-state artefacts.

### The controlled comparison

Re-run back to back in one host state, wired 13 Pro, with the deadline fix in place:

| config | rc | elapsed | media frames | outcome |
| --- | --- | --- | --- | --- |
| `--no-input` — media running, all three HID connections **open**, zero HID sends | 0 | **38 s** | 458 | completed cleanly |
| with input | 1 | **14 s** | 455 | died at executed=546 |
| with input | 1 | **14 s** | 418 | died at executed=546 |

Media frames are now 418-458, not ~266, so **the "~266 constant" was noise from the host state at
the time, not an invariant**. And media plus open HID connections, with no HID traffic, survives
nearly three times as long as the failing case. `ipb stream` — media with no HID connections at all —
also runs without the invalidation.

So the earlier inference ("something wedges at ~266 frames and the failure surfaces on whichever
connection is next used") is **wrong**. Holding HID connections open is not enough either; it takes
HID traffic. The single earlier `--no-input` death was n=1 and did not reproduce.

This is also **not** the media wedge recorded on 2026-09-08/09. That one is cumulative over ~30
sessions, makes the stream **fail to start** (`VideoReceiver startVideo failed`,
GKVoiceChatServiceErrorDomain 32017), and clears only on reboot. This one starts fine, delivers
hundreds of frames, and dies mid-session. Conflating them was a mistake.

### What the threshold actually tracks

Elapsed time after HID traffic begins, ~10.5 s — not event count and not gesture count:

| config | events executed | gestures completed | input-phase wall time | died |
| --- | --- | --- | --- | --- |
| 3 s drag @ 60 Hz | 546 | 3 | 10.5 s | yes |
| 3 s drag @ 30 Hz | 276 | 3 | 10.5 s | yes |
| 1 s drag @ 60 Hz | 372 | 7 | 10.5 s | yes |
| 6 s drag @ 60 Hz | 618 | mid-drag | ~10.5 s | yes |
| no input | 0 | 0 | n/a | **no**, survived 38 s |

Event count spans 276-618 and gesture count 3-7 while the wall time is constant, and the clock only
starts once sending starts. This is consistent with the user's interactive captures, both of which
died roughly 10 s into input.

**Open:** why ~10.5 s. A lifetime that begins at the first send, versus a lease that the barrier
fails to renew, are not yet distinguished; the discriminating test is sparse traffic — one gesture,
a long idle, then another — which the probe cannot currently express. Not claimed either way.


## 2026-09-14 — Root cause: the CoreDevice tunnel is not kept alive by HID traffic

The earlier records today characterised the symptom ("~10.5 s after the first HID send") without
naming a cause. This names it.

### The tunnel drops mid-session, before anything fails

Sampling `tunnelState` once a second across a failing run on the wired 13 Pro:

```
18:11:39  probe start
18:11:40..48  tunnel=connected   utun9=up
18:11:49      tunnel=disconnected  utun9=up      <- ~10 s in, process still running
18:11:52  probe dies: UHID RemoteXPC error: Connection invalid
```

`utun9` stays **up** throughout — the network interface is fine. CoreDevice tears down the *logical*
tunnel, and it does so **three seconds before** our failure surfaces, so it is the cause and not a
teardown artefact of our process exiting.

### Keeping the tunnel warm removes the failure completely

`devicectl device info details` every 4 s for the duration of the run, same probe, same config:

| | no keepalive | with keepalive |
| --- | --- | --- |
| rc | 1 | **0** |
| elapsed | 14 s | **37 s** (ran to completion) |
| events executed | 546 | **1820** — all 10 gestures |
| `abandoned_sends` | 1 | **0** |
| exit reason | `UHID barrier exceeded the send deadline` | **`complete`** |
| tunnel during run | `connected` -> `disconnected` at ~10 s | **`connected` throughout, only state observed** |

n=2, both clean.

### What renews the lease, and what does not

- **`devicectl device <action>`renews it.** This is exactly what `bin/ipb`'s `warm_tunnel` does.
- **`devicectl list devices` does not.** The failing run above had a `list devices` poller running
  once a second throughout and the tunnel dropped anyway.
- **HID traffic on the service socket does not.** 546 reports in 10 s did not hold it open.

### Why this produces the mirror freeze

1. The tunnel drops ~10 s after the last `devicectl device` call.
2. Every RemoteXPC connection riding it goes invalid at once.
3. The in-flight synchronous barrier blocks on the framework's internal timeout (744-2846 ms
   measured) and then returns **0**, a false success.
4. The serial input worker is stranded for that whole window and every queued event behind it is
   rejected.

It also explains the shape of everything seen so far. Short CLI commands never notice, because each
one warms the tunnel and finishes in about a second — `ipb home` was 3/3. `ipb mirror` holds a
session for minutes and **never renews**, so it dies about 10 s into use. It looked probabilistic
because what matters is how long since the last warm, not what the user did. And it is
transport-independent because a lease is not a link.

`warm_tunnel` (`bin/ipb`) warms **once, reactively, on exit code 4, before anything is sent**. There
is no concept of holding a tunnel open across a long-lived session. That is the gap.

**Open:** one `--no-input` run survived 38 s with no keepalive while another died at 41 s, so media's
role in renewal is unresolved and is not claimed here. And the renewal mechanism Device Hub itself
uses is unknown — we know only that a `devicectl device` call works, not what it does underneath.
A periodic subprocess is a workaround, not the design.


## 2026-09-14 — Workaround shipped: tunnel keepalive for `ipb mirror` (with TODOs)

`bin/ipb` now renews the CoreDevice tunnel for the life of a `mirror` session: a background loop
running `devicectl device info details --device <uuid> --timeout 20` followed by `sleep 4`, started
before the helper and reaped after it. The `mirror` branch no longer `exec`s the helper, because the
keepalive is our child and has to be killed when the session ends; `trap ... EXIT INT TERM` covers
the interrupted cases.

### Verified

- Probe, 10 gestures with the keepalive: rc=0, 37 s, **1820 events executed**, `abandoned_sends=0`,
  tunnel `connected` as the only state observed. Without it: rc=1, 14 s, 546 events. n=2 each.
- Through `bin/ipb mirror` itself: tunnel sampled every 2 s read `connected` for the entire session
  (the one `disconnected` sample is the first, taken before the keepalive had run), and no orphan
  `devicectl` or mirror process survived the exit.
- That mirror run ended `exit=7 no media frames for 12s` with 348 frames at p50 16.7 ms. That is the
  **idle-screen watchdog**, not a defect: with no input nobody is touching the phone, the screen is
  static, and no new distinct frames arrive. It is not evidence about the keepalive either way.

### Scope: `mirror` only

`ipb stream` was tested with and without the keepalive and behaved **identically** (15 s / 54 frames
vs 16 s / 57 frames), so its early finish is not the tunnel and it does not get the keepalive.

## Known, not fixed — TODO

1. **TODO(tunnel-keepalive): replace the workaround.** Spawning `devicectl` every few seconds for the
   life of a session is coarse and wasteful — a 300 s mirror session costs ~60 subprocesses. The
   real fix is to find what a `devicectl device <action>` call does underneath to renew the lease
   and do that in process. The `Experiments/devicehub-trace/` methodology can watch Device Hub
   itself renew. Marked `TODO(tunnel-keepalive)` in `bin/ipb`.
2. **TODO(stream-seconds): `ipb stream --seconds 60` stops early and still exits 0.**
   *(Diagnosis below was corrected later the same day — `--seconds` is NOT ignored. The cause is the
   12 s hard stall guard at `Sources/video_stream.m:475`: on a static screen distinct frames stop,
   the guard breaks, and only an unmet `--count` exits non-zero. The remaining defect is narrower
   than written here: **exit 0 for a run that ended early**.)* Reporting rc=0 for a session that ended early is the worse half:
   "failure is an exit code, not a log line" (Rule 2). Not the tunnel — the keepalive changes
   nothing. Unrelated to the mirror freeze; needs its own reproduction.
3. **TODO(media-lifetime): does the media path have its own ~10 s limit?** Both stream and mirror
   stop producing frames in that neighbourhood. The idle-screen explanation covers the mirror run
   above, but it has not been separated from a genuine media-side limit under a *changing* screen.
   Needs a run with continuous screen motion.


## 2026-09-14 — The lease mechanism, identified from symbols (not yet verified)

Follow-up to the root cause above, narrowing what should replace the keepalive workaround.

### Falsified first: creating a service socket does not renew the lease

Running a trivial HID command (`ipb key-up`, which opens a fresh service socket via
`com.apple.coredevice.action.createservicesocket`, sends, and closes) every 4 s for 8 rounds. Rounds
3, 5 and 7 printed the wrapper's "device tunnel not connected, warming it" line, i.e. the tunnel had
already lapsed and `ipb` re-warmed it:

```
round 1 rc=0 warmed=0     round 5 rc=0 warmed=1
round 2 rc=0 warmed=0     round 6 rc=0 warmed=0
round 3 rc=0 warmed=1     round 7 rc=0 warmed=1
round 4 rc=0 warmed=0     round 8 rc=0 warmed=0
```

Alternating on a ~10 s period measured from each `devicectl` warm. So **opening a service socket does
not renew the lease**, and neither does traffic on one. Only a `devicectl device <action>` call does.

### What does: usage assertions

`strings` and `nm` on
`/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice` (CoreDevice
642.15):

```
com.apple.coredevice.action.acquireusageassertion
com.apple.coredevice.action.listusageassertions

CoreDevice.UseAssertionProvidingDeviceRepresentation.acquireUsageAssertion(forRequest: CoreDevice.TunnelAssertionRequest) -> ()
CoreDevice.UseAssertionProvidingDeviceRepresentation.releaseAssertion(identifiedBy: Foundation.UUID) -> ()
CoreDevice.UseAssertionProvidingDeviceRepresentation.listAllAssertions() -> [CoreDevice.UsageAssertionInformation]
CoreDevice.UseAssertionProvidingDeviceRepresentation.releaseAllAssertions() -> ()
_TtC10CoreDevice20DeviceUsageAssertion, UsageAssertionOptions, UsageAssertionRequirements
```

The request type is named **`TunnelAssertionRequest`**: a client holds a *tunnel* assertion for as
long as it needs the tunnel, and with no holder the tunnel lapses. That matches every measurement —
the ~10 s period, a `devicectl device` call renewing it (it takes an assertion for the duration of
its work), and neither socket creation nor service traffic renewing it.

**This is inference from symbol evidence (Rule 1, source 3). It is NOT verified behaviour.**
`devicectl` exposes no assertion subcommand, so it could not be confirmed from the CLI.

### Concrete plan for TODO(tunnel-keepalive)

The helper already builds and sends CoreDeviceService action dictionaries (it sends
`createservicesocket`). The replacement is to send `com.apple.coredevice.action.acquireusageassertion`
once at session start, hold it, and release it at the end — no subprocess and no polling. Two
unknowns to settle first: the payload shape of `TunnelAssertionRequest` (CodableValue encoding is
already mapped in `docs/protocol.md`), and confirmation via
`com.apple.coredevice.action.listusageassertions` that the assertion is actually held. The
`Experiments/tools/rxpc_tap.c` interposer cannot capture `devicectl` (it is signed;
`DYLD_INSERT_LIBRARIES` will not attach), so the payload has to come from the Swift type layout or
from watching Device Hub with `Experiments/devicehub-trace/`.


## 2026-09-14 — Tunnel assertions: mechanism confirmed by name, request schema mapped, acquire not yet achieved

Work on `TODO(tunnel-keepalive)`. New tool: `Experiments/tools/cd_action.m` sends an arbitrary
CoreDeviceService action with an arbitrary `CoreDevice.input` and prints the reply. It exists because
the service decodes the input as a Swift `Codable` and **names the key it wanted**, so a schema can be
walked out one error at a time. It must call `_coredevice_xpc_add_bundle` /
`_coredevice_xpc_init_services` first, exactly as `Sources/action_sender.m` does; without that
registration CoreDeviceService answers `Connection invalid`.

### The mechanism is named in Apple's own binary

`strings` on CoreDevice 642.15:

```
tunnelGracePeriodWithNoActiveAssertionsADCDevice
tunnelGracePeriodWithNoActiveAssertionsRemotePairingDevice
TunnelAssertionGroup / TunnelAssertionRequest / TunnelTeardownAttemptInfo
```

**"tunnel grace period with no active assertions"** is the ~10 s we measured. This upgrades the root
cause from inference to a named mechanism: with no usage assertion held, the tunnel gets a grace
period and is then torn down. `CoreDevice.TunnelAssertionGroup.persistentTunnelAssertionGroup()` and
`.persistent: Bool` exist, which is what a long-lived session wants.

`AssertableDeviceState` has these members (`nm` + demangle): `coreDeviceServicesLoaded`,
`developerModeEnabledIfRequired`, `extendedDeviceInfoLoaded`, `powerAssertionTaken`,
`remoteServiceDiscoveryTrustedConnectivityAvailable`, `secureNetworkingAvailable`. The fifth is the
state behind `CoreDeviceError 4000: RemoteServiceDiscovery connectivity is not available`.

### `listusageassertions` works and reports zero

Sent through our own path, it returns `CoreDevice.output` as an **empty array** — no assertions held.
Consistent with the tunnel lapsing. (The helper logs "no CoreDevice.output" for it only because its
own code expects a dictionary, not an array.)

### The acquire request schema, walked out

Each line below is the key the service asked for next:

```
{}                                   -> "Expected to find key reason."
reason                               -> "Expected to find key requirements."
requirements: {}                     -> "Expected to find key deviceStates."
requirements.deviceStates: ["str"]   -> "dictionary required here" at deviceStates[0]
requirements.deviceStates: [{identifier: "<state>"}]
                                     -> "Expected to find key capabilities."
requirements.capabilities: {}        -> "array required here"
requirements.capabilities: []        -> "Expected to find key endpoint."   (top level)
endpoint: {}                         -> decode SUCCEEDS
```

So the request is `{reason, requirements:{deviceStates:[{identifier}], capabilities:[]}, endpoint}`.

### Where it stops

With the schema satisfied the error becomes **semantic**, not structural:

> The device is not able to fulfill the requested usage assertion requirements.

All six `AssertableDeviceState` identifiers were swept with the tunnel freshly warmed; all six return
that same message. So either the identifier strings are not the case names, or `endpoint: {}` means
"no endpoint" and nothing can be fulfilled. `TunnelAssertionRequest` demangles as an **enum**
(`...RequestO`), so `endpoint` is likely an enum needing a selected case rather than an empty
dictionary.

**Not achieved: acquiring an assertion.** The workaround stays and `TODO(tunnel-keepalive)` stays
open.

**Next step, unchanged from the earlier record but now better targeted:** capture a real acquire off
Device Hub with `Experiments/devicehub-trace/` and copy the payload, rather than guessing further.
`listusageassertions` returned empty even while a `devicectl device info details` ran in parallel, so
that call's assertion is either too brief to catch by polling or not visible to us — a trace is the
way, not a poll.


## 2026-09-14 — Tracing devicectl: no client-side renewal path found; the workaround is justified

Continued work on `TODO(tunnel-keepalive)`. No operator was needed for this round.

### `devicectl` can be debugged

It is signed with `flags=0x2000(library-validation)`, which blocks loading unsigned libraries — so
`Experiments/tools/rxpc_tap.c` (a `DYLD_INSERT_LIBRARIES` interposer) cannot attach — but it does
**not** block debugging. `lldb` attaches and breakpoints hit normally. New tool:
`Experiments/devicehub-trace/xpctrace.py` dumps every XPC message a process sends whose description
mentions a CoreDevice action, by calling `xpc_copy_description` on the message at the send site.

### devicectl does not acquire an assertion in its own process

Two negative results from tracing `devicectl device info details`, the call that demonstrably renews
the tunnel:

- It sends **no** `com.apple.coredevice.action.*` XPC message at all through
  `xpc_connection_send_message{,_with_reply,_with_reply_sync}`.
- `breakpoint set -r 'acquireUsageAssertion|acquireDeviceUsageAssertion|TunnelAssertionGroup'` armed
  **16 locations and took zero hits**.

So the tunnel assertion is not taken by the client. It is taken by a daemon on the client's behalf,
which fits the `DeviceManagerCheckInRequest` / `DeviceManagerCheckInCompleteEvent` pair in
devicectl's own log output.

### Our action path can use the tunnel but cannot establish or renew it

Sending `com.apple.coredevice.action.lockstate` in process via `cd_action` every 4 s:

```
round 1 (t+4s)  sent_ok=1  tunnel=connected
round 2 (t+8s)  sent_ok=1  tunnel=connected
round 3 (t+12s) sent_ok=0  tunnel=disconnected     <- dropped anyway
round 4..7      sent_ok=0  tunnel=disconnected     <- never recovers
```

Two things at once: actions do **not** renew the lease (calls at t+4 s and t+8 s did not prevent the
~t+12 s drop), and once the tunnel is down a CoreDeviceService action cannot bring it back — it just
returns `CoreDeviceError 4000` forever. Only a `devicectl device ...` call re-establishes it.

### A wrong inference, corrected before it was acted on

The trace shows the device advertising
`Acquire Usage Assertion (com.apple.coredevice.feature.acquireusageassertion): []` — an empty
capability-implementation list — which looked like "the device cannot do this" and would have
explained the semantic refusal. **It does not mean that.** `getdeviceinfo` and `launchapplication`
are also `[]`, and both demonstrably work (`ipb info`, `ipb launch`). An empty implementation list
says the capability is not provided by a plugin, not that it is unsupported. The refusal is still
unexplained.

### Where this leaves the TODO

**No in-process renewal path was found.** The `devicectl` subprocess workaround is not laziness; it is
currently the only mechanism known to work, and that is now backed by three negatives (socket
creation does not renew, actions do not renew, the client does not take the assertion). It stays.

The remaining lead is the **device-manager check-in** devicectl performs at startup, which is what
correlates with renewal — not the assertion action and not any device action. That is the next thing
to trace, and it can be traced in `devicectl` without an operator.


## 2026-09-14 — Review response: resident keepalive, a signal regression fixed, and three corrections

An independent review (Fable) of the day's work. It found a regression I shipped, a much cheaper
mechanism, and errors in two of my own records. All confirmed here.

### 1. One resident client replaces the 60-subprocess loop

The lease is bound to the **lifetime of a checked-in devicectl client**, not to individual calls. A
single `devicectl device notification observe` holds the tunnel for as long as it runs and renews
nothing — it just stays checked in. Measured through `bin/ipb mirror`: `tunnelState` sampled every
3 s read `connected` at **all 7 samples**. The notification name is never posted; observing is merely
the cheapest way to stay checked in, and `--session-timeout` (bounded to the session length + 30 s,
capped at 3630 s) means even a SIGKILL of the wrapper cannot leave it holding the device forever.

This also answers the "next thing to trace" from the earlier record: the mechanism is the
`DeviceManagerCheckInRequest` devicectl performs at startup, and the check-in lives as long as the
process. No trace needed.

### 2. Regression I shipped: `kill <ipb pid>` stopped working, and the keepalive orphaned

Removing `exec` in 632481d so the keepalive could be reaped had a consequence the commit message
claimed was covered and was not. zsh defers a trapped signal until the **foreground** child returns,
so `kill` on the wrapper did nothing for up to `--seconds` (default 300 s). An agent that starts
`ipb mirror` and later kills the pid — a stated use case — could not stop a session. Fixed by running
the helper in the **background** and `wait`ing on it, which a trapped signal interrupts.

A second, separate bug: the keepalive was backgrounded through the `devicectl()` **shell function**,
so `$!` was the subshell, not the real process. Killing it orphaned devicectl. Process ancestry made
it plain:

```
40039 wrapper zsh
  └─ 40071 zsh                 <- $! recorded this
       └─ 40073 devicectl observe   <- survived, orphaned
```

Fixed by invoking the binary directly (`${=DEVICECTL} device notification observe ...`), plus a child
sweep in `stop_tunnel_keepalive` as a backstop. `set -e` also required `|| true` on the kills so a
non-zero status could not abort the handler before the cleanup.

Verified: SIGTERM and SIGINT both end the session in 1-3 s (the helper's clean drain) with **zero
orphans of either kind**, and `observe`'s ppid is now the wrapper.

### 3. The gate now tests it, and "SMOKE PASSED" was over-cited before

`grep -i mirror scripts/smoke_matrix.sh` previously matched nothing: the gate exercised neither
`sendBounded` nor the keepalive, so citing it as evidence for 13d5fd6 and 632481d was wrong. There is
now a `mirror signal handling + orphan check` step that starts a session, signals the wrapper, and
asserts prompt exit with no surviving keepalive or helper. Writing it surfaced four bugs in the test
itself, each worth recording because they are easy to repeat:

- `${DEVICE_ID:+-s "$DEVICE_ID"}` expands to **one word** in zsh, so `bin/ipb` saw a bogus command and
  the step silently SKIPped. `DEVICE_ID` is honoured from the environment; the flag is unnecessary.
- A global `pgrep -f 'notification observe'` matched a leftover from an earlier run and reported a
  false failure. The check now watches only the pids that were children of *this* wrapper.
- `pgrep -f 'ipb-mirror'` **matched the shell running the gate**, because that command line contains
  the pattern text. Switched to `pgrep -x 'ipb-mirror'` (exact executable name).
- The helper drains on SIGTERM, so the orphan assertion needs a bounded grace, not an immediate check.

### 4. Correction: "with zero sends the clock never starts" was wrong

Record 4 today ("Correction: it is HID traffic, not the media path") over-corrected. Its own table
shows `--no-input` producing **458** frames over 38 s while the with-input runs produced 455/418 over
14 s. At ~60 fps, 458 frames is ~7.6 s of media — so **media stopped early in the no-input run too**;
that run simply had no synchronous send to fail on and ran to its scheduled end. The earlier
"frames land on a constant regardless of duration" observation was seeing the tunnel drop, not noise.

The accurate statement is: **the tunnel lapses ~10 s after the last `devicectl device` call
regardless of traffic; HID sends are only the detector.** This also dissolves the "38 s alive vs 41 s
dead" `--no-input` contradiction left open earlier — both had a dead tunnel at ~10 s.

### 5. `TODO(media-lifetime)` does NOT close

The decisive number was already in a log and unread. The two keepalive runs, identical config, tunnel
held and 1820 HID events in both:

| run | elapsed | HID events | media frames |
| --- | --- | --- | --- |
| keepalive #1 | 37 s | 1820 | **1236** |
| keepalive #2 | 37 s | 1820 | **265** |

1236 is the full duration at ~33 fps; 265 is ~4 s of it. So media *can* survive when the lease is
held, but sometimes stops anyway. That is a **separate, intermittent media stall**, not the tunnel.
The TODO stays open, now with a sharper question: why one run in two.

### 6. `TODO(stream-seconds)` diagnosis was wrong

`Sources/video_stream.m:475`: `if((t-lastSave) > 12.0) break;  // hard stall guard`. `--seconds` is
**not** ignored. On a static screen distinct frames stop, 12 s later the guard breaks, and only an
unmet `--count` exits non-zero (`:502`), so the run reports 0. That matches the 15-16 s / 54-57 frame
runs with and without the keepalive, and confirms it is not the tunnel. The remaining defect is
narrower than recorded: **exit 0 for a 60 s request that ended at 15 s** (Rule 2).

### 7. `sendBounded` caveats the record did not state

The block/ARC lifetimes check out (the `__block` result is heap-promoted when the block is copied;
the semaphore is retained by the block; the report copy is a real 16-byte `uint64_t[2]`; `gInput` is
cancelled but never released). Two things were unstated and remain open:

- **Every timeout is fatal.** `mirror.m` turns any `gFailure` into a close, so one 500 ms stall on a
  healthy connection ends the session with exit 1. The 0.5 s deadline was justified against a
  3.5-5.3 ms **wired** median; no localNetwork p95/p99 exists, and the user's original captures were
  localNetwork. Thread growth is therefore bounded (one abandoned thread, then exit), but the
  false-positive cost is "the session dies" and should be measured on Wi-Fi before 0.5 s is called
  settled.
- **Concurrency on one `xrc_t` after a timeout** is unexamined: an END event can be sent on `gInput`
  while an abandoned call is still inside Apple's sender. Nothing establishes those senders are safe
  for concurrent calls on one connection.

### 8. Smaller

`Experiments/devicehub-trace/xpctrace.py` filtered on `("coredevice.action", "assertion",
"Assertion")`, which would have discarded `DeviceManagerCheckInRequest` — the very message the record
named as the next lead. Filter widened. Still owed, and only the user can do it: **one interactive
mirror run with >10 s of real input**, since no run to date has exercised the fix with a human
driving it.

Gate: `SMOKE PASSED` on the wired iPhone 13 Pro, including the new mirror signal/orphan step.


## 2026-09-14 — localNetwork closes the last review caveat: same grace, same fix

The review's one open caveat was that everything had been measured on the **wired** 13 Pro while the
user's original failures were on the **localNetwork** iPhone 12 mini, and CoreDevice carries two
separate grace constants (`tunnelGracePeriodWithNoActiveAssertionsADCDevice` vs
`...RemotePairingDevice`). Measured on the 12 mini, three phases:

| phase | procedure | result |
| --- | --- | --- |
| A — grace | warm once, then sample `tunnelState` every second | **dropped at t+11 s** |
| B — hold | one resident `devicectl device notification observe` | **12/12 samples `connected` over 38 s, 0 failures** |
| C — release | kill the keepalive, keep sampling | **dropped 11 s later** |

So the localNetwork grace is **11 s**, materially identical to wired (~10-11 s) — the two constants
do not diverge for this device pair — and the resident keepalive holds the tunnel there too. Phase C
is what makes B more than a coincidence: removing the intervention restores the failure.

`--session-timeout`, which `bin/ipb` bounds to the session length + 30 s, therefore needs no
transport-specific value. The fix is transport-independent, as the barrier deadline already was.


## 2026-09-14 — The 0.5 s deadline was killing live sessions; raised to 2 s and made non-fatal

A real interactive run by the user failed immediately:

```
exit=1 reason=UHID barrier exceeded the send deadline
abandoned_sends=1 (deadline 0.50s)
gesture tail p50=505.025 p95=505.025 p99=505.025 n=1 (ms)
submitted=42 executed=11 rejected=31
```

**The fix was the bug.** The review had flagged this ("every timeout is fatal… the 0.5 s figure was
justified against a 3.5-5.3 ms wired median; no localNetwork p95/p99 is cited") and it was
under-weighted. Two runs side by side settle it:

| | synthetic probe | real interactive session |
| --- | --- | --- |
| gesture tail p50 | 3.5-5.3 ms | **30.6 ms** |
| gesture tail p95 | — | **346 ms** |
| observed overshoot | — | **>505 ms** (timed out) |

So the "100x margin" claimed for 0.5 s was a margin over a **synthetic** median. Against real
interactive latency on localNetwork it is about **1.4x**, and it terminated a healthy session on
latency alone.

### Two changes

1. **Deadline 0.5 s → 2.0 s.** Roughly 4-6x the observed p95, still below the ~3 s the framework
   takes on a genuinely dead connection.
2. **A barrier deadline expiry is no longer fatal.** This is the more important half. A barrier is a
   flush/sync point — a slow one strands no contact on the device — so exceeding the deadline now
   logs and the session continues. A *report* timeout stays fatal, because a lost report can leave a
   contact or a button held. In `keyStep` the barrier/report distinction has to be captured **before**
   `done=YES` is assigned on the same line, or a shortcut press timeout would wrongly become
   non-fatal; that bug was written and caught before testing.

The deeper point, now stated in the code: **legitimate latency and a dead connection overlap** —
744 ms has been measured from a dead connection and >505 ms from a healthy one — so a deadline
cannot be what decides a connection is dead. It exists only to stop one stuck call from owning the
serial input queue. The async error handler is what reports a dead connection, and the tunnel
keepalive is what prevents the death in the first place. The deadline is a backstop, not the fix.

`Experiments/mirror/mirror_probe.m` was moved to 2.0 s in step, so the harness matches the shipped
contract.

Gate: `SMOKE PASSED` on the iPhone 12 mini (localNetwork), including the mirror signal/orphan step.
Still owed: the interactive re-run that prompted this.


## 2026-09-14 — Interactive run: volume down confirmed, and real barrier latency validates the 2 s deadline

The interactive mirror run that was owed. iPhone 12 mini, localNetwork, `--csv /tmp/volume.csv`.
User's report: working and usable.

### Volume down (`0x0c` / `0xEA`) is no longer unconfirmed

Both directions were exercised — 5 × `KEY_VOLUME_UP`, 3 × `KEY_VOLUME_DOWN` — and **every one**
recorded `result=sent`, `report_code=0`, `barrier_code=0`:

```
seq=4  KEY_VOLUME_UP    sent  0/0  tail=232.6ms
seq=5  KEY_VOLUME_DOWN  sent  0/0  tail=224.5ms
seq=6  KEY_VOLUME_DOWN  sent  0/0  tail=234.2ms
seq=7  KEY_VOLUME_DOWN  sent  0/0  tail=286.7ms
seq=8..11 KEY_VOLUME_UP sent  0/0  tail=238.0-284.3ms
```

This retires the standing caveat in `Sources/mirror.m` ("EA is the paired usage, rc=0 only, HUD
unconfirmed"), which had stood since 2026-09-08 on the 13 Pro. The evidence is a user-observed effect
across repeated presses in both directions, not a captured HUD screenshot — weaker than a screenshot,
but it is a direct report of the device responding, and `0xEA` being the wrong usage is no longer a
live possibility. Comment updated in place.

Note the key tails (224-287 ms) include `keyStep`'s deliberate 80 ms + 120 ms press/release waits, so
the barrier itself is only ~25-90 ms there.

### Real interactive latency, and why 0.5 s was wrong

The touch `UP` in the same run is the interesting number, because the touch path has no deliberate
sleeps — its tail is pure `coredevice_send_universalhid_barrier`:

```
UP  tail=305.5ms  result=sent      <- healthy connection
```

Together with the 346 ms p95 measured earlier and the >505 ms overshoot that killed a session,
healthy barrier latency on localNetwork routinely runs past 300 ms. The 0.5 s deadline sat inside
the normal range. At 2.0 s the margin over the worst healthy value observed is about 6x.

**Zero `send_timed_out`, zero `rejected`, zero `overload` in the run.** Both shipped changes behave:
the keepalive kept the lease, and the deadline did not fire on healthy traffic.

Caveat worth stating: this run is 11 events. It shows the fix no longer breaks a live session, not
that the tail is fully characterised. A longer session would sharpen the p99, and the unexplained
intermittent media stall (`TODO(media-lifetime)`) is untouched by any of this.


## 2026-09-14 — Crash: `kinds[KeyLock]` read out of bounds, destroying the CSV with it

A user session crashed with `SIGSEGV`:

```
Thread 0 Crashed:: com.apple.main-thread
0  libsystem_platform.dylib  _platform_strlen + 4
1  CoreFoundation            __CFStringAppendFormatCore + 10128
3  CoreFoundation            -[__NSCFString appendFormat:] + 124
4  ipb-mirror                finish + 3316
```

`Kind` has **11** members (`Down … KeyVolumeDown, KeyLock`) but `kinds[]` at `Sources/mirror.m:237`
held **10** strings. `KeyLock` was added to the enum for the ⌘L binding without a matching entry, so
`kinds[KeyLock]` read one past the end and `%s` ran `strlen` on whatever followed.

**Reachability: any session that uses ⌘L with `--csv`.** It is not an edge case — it is every use of
the lock shortcut while recording, and it fires in `finish`, i.e. at exit.

Second consequence, worth stating because it cost the investigation: the CSV is opened truncating, so
the crash left `/tmp/volume.csv` at **0 lines** and took the previous run's data with it. The session
the user was reporting on produced no diagnostic record at all.

Fixed by adding `"KEY_LOCK"`, and by making the next such omission a **build error** rather than a
crash at exit:

```c
_Static_assert(sizeof kinds / sizeof *kinds == KeyLock + 1, "kinds[] must have one string per Kind");
_Static_assert(sizeof inputResults / sizeof *inputResults == ScrollOffTarget + 1,
               "inputResults[] must have one string per Result");
```

The second assert covers the parallel array that `SendTimedOut` was recently inserted into; it
happened to be correct, but nothing had been enforcing it.

Gate: `SMOKE PASSED` on the 12 mini.

### Still open from the same report, no data yet

Two of the user's three complaints cannot be diagnosed until a session records successfully:

- **Home-screen icons stop responding after a manual bottom-edge swipe, while taps inside other apps
  still work.** Suspicion, untested: a bottom-edge gesture that did not cleanly end leaves the
  drain's state machine at `Pressed`, after which `drainInput` rejects further gestures on an
  "invalid input state transition" and rejects every shortcut with "shortcut reached active touch".
  `ipb reset-gesture` exists for exactly this and is the first thing to try.
- **The lock shortcut stopped working.** Consistent with the same stuck state (shortcuts are rejected
  when `state != Idle`), but equally consistent with the user simply having hit the crash above.
  Not diagnosable without the CSV.

### App Switcher is slow by construction, not by accident

Measured from `keyStep` rather than guessed:

| phase | cost |
| --- | --- |
| steps 0-11, 12 × 30 ms | 0.36 s (13 position samples, ~33 Hz) |
| step 12 dwell | **1.05 s** |
| post-END settle | 0.25 s |
| **total before the next input is accepted** | **1.66 s** |

The dwell alone is **74%** of the gesture. The 1.05 s came from the `bin/ipb recents` oracle and has
never been swept. That fully explains "像 mock 慢慢滑动" — 33 Hz of motion followed by a second of
holding still. Device Hub's own gesture is not reproduced here, only approximated. Candidate work:
sweep the dwell (0.5 / 0.7 / 0.85 / 1.05) and the step interval (30 ms → 16 ms) against whether the
switcher still opens reliably. Not changed yet, because "still opens" needs a human watching.


## 2026-09-14 — App Switcher is a real button, not a gesture: `0xff01` / `0x10`

The user's objection was the right one: Home and Lock are direct usages, so App Switcher should not
have to mock a swipe. It does not.

### The existing "button" implementation never worked

`Sources/action_sender.m` already had `cd_recents_button` sending AppleVendorKeyboard page `0xff01`
usage **`0x100`**, unreferenced by any `bin/ipb` command and with no verification record. Tested by
screenshot: it returns **rc=0 and does nothing** — the device stays on the home screen. rc=0 on a
button that has no effect is why this sat undetected.

### `0x10` is the usage

Swept the plausible task-switcher usages from a known home-screen state, screenshotting after each
and comparing against the home frame:

| page / usage | result |
| --- | --- |
| `0x0c` / `0x29F` (AC Desktop Show All Applications) | no change |
| `0x0c` / `0x2A2` (AC Desktop Show All Windows) | no change |
| `0x0c` / `0x1A2` (AL Task Manager) | no change |
| `0x0c` / `0x36` | no change |
| `0xff01` / `0x04` | no change |
| **`0xff01` / `0x10`** | **App Switcher** |
| `0x01` / `0x82` | no change |

Verified by looking at the frames, not by file size alone: the result is the same card view the
digitizer swipe produces. **4/4 on the iPhone 12 mini (iOS 27.0, localNetwork), 2/2 on the iPhone
13 Pro (iOS 27.0, wired)**, plus the interactive smoke gate's `05_after_recents` frame.

### What it replaces, and the cost it removes

The mirror's `keyStep` had a dedicated 14-step digitizer branch for recents: 12 × 30 ms of motion
(~33 Hz), a **1.05 s dwell**, then a 0.25 s post-END settle — **1.66 s** before the next input, with
the dwell alone 74% of the gesture. That is exactly the "像 mock 慢慢滑动" the user described. The
button is a normal click: 80 ms press, 120 ms release, barrier — about **0.2 s**.

The whole swipe branch is **deleted** rather than kept behind a flag, so every shortcut now takes one
path (`coredevice_send_hid_button_custom` with a per-shortcut page/usage); the usage page had to
become a variable because recents is the only one not on consumer page `0x0c`. `bin/ipb recents` and
the helper's `cd_recents_button` both point at `0x10` now. End-to-end CLI time went 2.89 s → ~1.2 s,
most of which is process start and connection setup.

### Gap, stated rather than glossed

**iOS 26 is untested.** The supported matrix is iOS 27 *or iOS 26.6+*, both confirmations above are
iOS 27.0, and the iPhone 15 Pro (iOS 26.6.2) reads `tunnelState unavailable` — not connectable right
now. Since a button with no effect returns **rc=0**, a usage absent on iOS 26 would fail *silently*,
exactly as `0x100` did. This needs one screenshot check on an iOS 26 device before the matrix claim
is honest.

Gate: `SMOKE PASSED` on the 12 mini, interactive, 1 WARN. The single duplicate frame pair is
`00_before` vs `01_after_nondestructive`, which is expected — every step between them is a
deliberate zero-movement no-op.


## 2026-09-15 — ⌘L did nothing because 0.08 s does not lock; three separate causes untangled

User report after the crash fix: scroll, Home and App Switcher work; ⌘L, volume and tap/swipe do
not. The recorded CSV (`/tmp/crash-fix.csv`, 517 events over 71.4 s) shows these are **three
different problems**, not one.

### 1. ⌘L: the hold was too short — fixed

Direct comparison on the 12 mini (iOS 27.0), screenshot-verified:

| sent | hold | screenshot after | verdict |
| --- | --- | --- | --- |
| `ipb button 0x0c 0x30` | ~0.08 s (what mirror's ⌘L used) | 6 313 383 B, delta **514 B** from before | **did not lock** |
| `ipb power` | 0.5 s | **36 071 B** (black) | **locked** |

The comment in `mirror.m` asserted "the side button locks on a short press". **That premise was
wrong**, and it is why ⌘L sent cleanly (`KEY_LOCK` ×2, `result=sent`, both codes 0) while nothing
happened. The hold is now per-shortcut: `KeyLock` gets 0.5 s, everything else keeps 0.08 s. 0.5 s is
the value `bin/ipb power` already uses and the only one both earlier sweeps agreed on (0.7 s once
opened Siri).

Evidence strength: **n=1 per arm**, with real before/after screenshots. Two follow-up runs that
appeared to show 3/3 were **harness false positives** and are void — the screenshots were never
written (the device had locked, and `capture screenshot` fails on a locked device), and an empty
string in zsh arithmetic compares as `0 < 200000`. Recorded because the mistake is easy to repeat:
a missing artefact must be an explicit failure branch, never a silently-passing comparison.

### 2. Volume: the keystrokes never reached the mirror

**Zero `KEY_VOLUME_UP` / `KEY_VOLUME_DOWN` rows in 71.4 s.** Not rejected — absent. And it is not a
failure state swallowing them: `KEY_HOME` at t+53.9 s and `KEY_RECENTS` at t+55.3 s were sent
normally *after* the two locks, and no event in the whole file is `rejected`.

`git diff a362d12..HEAD -- Sources/mirror.m` confirms `performKeyEquivalent` was **not touched**
since the run where volume was confirmed working, so this is not a regression from the App Switcher
or crash changes. The binding requires `flags == command` exactly, plus
`charactersIgnoringModifiers` being the arrow function key. Cause unknown; the open question is what
the user actually pressed (⌘ + arrow keys, versus the Mac's own volume keys, which macOS consumes and
never delivers to an application).

### 3. Tap/swipe: sent, and the CLI path works

53 × DOWN and 53 × UP, every one `result=sent` with both codes 0. Independently, `ipb tap 0.15 0.12`
from the CLI **launched an app** (6 313 755 B → 437 746 B). So the touchscreen service is not dead.
Not diagnosed. `ipb home` was also measured at only ~2/3 reliability in the same window, which
suggests something flakier in the device's current state rather than a specific tap defect.

### Device left locked

Testing lock necessarily locked the phone, and it cannot be unlocked from here — `lock-state` and
`screenshot` both return `CoreDeviceError 10003` / `RemotePairingError 1016 "The device has not been
unlocked recently"`. A passcode unlock by hand is required. **The smoke gate therefore has not been
run for this change** and is owed.


## 2026-09-15 — Black edge on the 12 mini: the crop allowance was fixed-pixel, not proportional

User report: the mirror's black edge is back. It is **not a regression** from today's work — the same
`fallback=yes ... source=full-frame` lines appear in the user's runs from before the App Switcher and
crash changes. It is 12-mini-specific and had been there all along; the 13 Pro, where the edge was
originally fixed, happens to fall inside the old limit.

### Geometry, measured rather than assumed

A frame captured with `ipb stream` and analysed for its non-black bounding box (small CoreGraphics
tool, threshold 12/255):

```
frame 1136x2464
content x=0 y=27 w=1125 h=2433      padding left=0 right=11 top=27 bottom=4
```

So the 12 mini's **stream is not native**: the panel is 1080x2340 but the encoded content is
~1125x2433, about a 4% upscale, plus a little padding.

### Why it fell back

`freezeContentRect` rejected detection when the detected rect was more than a **fixed 64 px** smaller
than the frame in either axis:

| case | removes | vs 64 |
| --- | --- | --- |
| 13 Pro (works) | 14 x 44 | accepted |
| 12 mini, user's run | 12 x **92** | **rejected** |
| 12 mini, this measurement | 11 x 31 | accepted |

Detection is content-dependent (it unions the lit region over ~30 frames), so on the 12 mini it lands
either side of 64 depending on what is on screen — which is exactly why the edge came and went. A
fixed pixel budget is also the wrong shape: it does not scale with frame size.

Now proportional, `ContentDetectMaxShrink = 0.08`: every padding measured so far passes (13 Pro
14x44, 12 mini 11x31 and 12x92) while a detection that only found the lit part of a dark screen is
still rejected. Verified on the 12 mini:

```
content: frame=1136x2464 rect=(0,4 1124x2432) source=detected
content detection: ... fallback=no (frozen)
```

**The other guard was deliberately left alone.** `mirror.m:425` rejects *table/lookup* candidates
outside `[0,64]` per axis, and it is the reason the builtin entry 1080x2340 is refused here. That
refusal is correct: the stream's content is 1124x2432, not 1080x2340, so accepting the table would
crop to the wrong rectangle. Making that guard proportional too would let 1080x2340 through (56x124,
inside an 8% budget) and break the mapping. Two guards, two jobs; only the detection one should
scale.

Gate: `SMOKE PASSED` on the 12 mini, including the mirror signal/orphan step.

### Lock: still not reliable, and the ceiling is real

With the hold at 0.5 s the user reports ⌘L works but is "not sensitive enough". The ceiling is not
negotiable: **the hold must not grow much**, because a long press opens Siri (0.7 s did, once). So
there is a narrow band between "does nothing" (0.08 s, measured) and "Siri" (0.7 s, observed n=1),
and 0.5 s sits inside it but apparently not comfortably. Unchanged for now — picking a number between
0.5 s and 0.7 s without measuring would just be swapping one guess for another. What is needed is a
sweep of 0.5 / 0.55 / 0.6 / 0.65 with a screenshot after each, on a lit screen, recording both
"locked" and "Siri appeared".


## 2026-09-15 — Lock hold: transport hypothesis falsified; ~0.35 s is the side button's own floor

The hypothesis under test (user's): the lock failure is a **send-path / transport** problem, because
wired devices seemed fine and the 12 mini is a remote wireless device needing its own parameters.

Swept the hold shortest-first on both transports, stopping at the first lock, screenshot-verified
each step with an explicit "screenshot missing" branch:

| hold | iPhone 12 mini (localNetwork) | iPhone 13 Pro (**wired**) |
| --- | --- | --- |
| 0.08 s | no effect | **no effect** |
| 0.15 s | no effect | **no effect** |
| 0.25 s | no effect | **no effect** |
| 0.35 s | **locked** (6 191 446 → 36 071 B) | **locked** (8 946 698 → 38 988 B) |

**Identical on both.** The transport hypothesis is falsified: this is not wired-vs-wireless and needs
no per-transport tuning. The side button simply requires roughly **0.35 s** minimum hold, everywhere.
Corroborating detail already in hand: `KEY_HOME` at 0.08 s works reliably on the *same* localNetwork
link, so the link is not swallowing short presses — the side button is duration-gated and Home is not.

The 0.5 s now used by both `bin/ipb power` and the mirror's ⌘L sits ~1.4× above the measured floor
and below the 0.7 s that once opened Siri. Left unchanged.

### Retraction

The 2026-09-09 record stating "`⌘L` at 0.08 s is **verified on device**: it locks a lit screen and
wakes a dark one from a live mirror session" **cannot be correct**. Two devices, two transports,
three sub-threshold holds each, all no-ops. Whatever locked the screen in that session, it was not a
0.08 s side-button press — most likely the device's own auto-lock coinciding with the test. That
record is retracted; the stale premise it seeded ("the side button locks on a short press") is what
made ⌘L a no-op for everyone until today.

## 2026-09-15 — Two capability gaps vs Device Hub, recorded for follow-up

Both reported by the user from direct side-by-side use. Neither is diagnosed yet; subagent
investigations dispatched.

### Gap 1: Device Hub works on a locked device, ipb does not

Device Hub keeps operating with the iPhone physically locked. Every `ipb` CoreDevice operation fails
once the device locks:

```
CoreDeviceError 10003 "The operation failed because the device was still locked."
  RemotePairingError 1016 "The device has not been unlocked recently"
```

`screenshot`, `lock-state` and the mirror all stop. This is not cosmetic: testing the lock shortcut
locks the phone, and nothing works again until a human types the passcode — it cost two separate
investigation sessions today. Plausible and untested link: the CoreDevice **usage assertion** work
already recorded (`acquireusageassertion`, `TunnelAssertionRequest`, `AssertableDeviceState` includes
`remoteServiceDiscoveryTrustedConnectivityAvailable`) may be the same mechanism, since an assertion
holder could plausibly retain service access across a lock.

### Gap 2: Device Hub can tap system dialogs, ipb cannot

Device Hub can dismiss iOS system-presented UI — permission prompts and similar alerts. `ipb` taps
have no effect on them, while taps on ordinary app UI work. For an automation tool this is severe:
the first permission prompt strands the session.

Hypotheses to separate: synthesized HID from this path reaching only the foreground application
while system alerts are presented by another process; a different service or report used by Device
Hub for system UI (the descriptor set has `mainScreenButtons` 0x402 and `avpCustom` 0x500 whose roles
are not established); or a trust/entitlement distinction on a "secure" input path.

Both gaps are **open**, both are user-visible, and both should be weighed against the roadmap rather
than patched ad hoc.


## 2026-09-15 — Gap 1 mechanism found: remote unlock, and it is not reachable

Static investigation (no device interaction) of CoreDevice 642.15, `RemotePairingDevice.framework`
and DeviceHub.app.

### Correction first: the usage-assertion link I recorded was wrong

The Gap 1 entry above guessed that the CoreDevice usage-assertion work "may be the same mechanism".
**It is not.** `nm` + `swift-demangle` shows `AssertableDeviceState` has exactly six members
(`coreDeviceServicesLoaded`, `developerModeEnabledIfRequired`, `extendedDeviceInfoLoaded`,
`powerAssertionTaken`, `remoteServiceDiscoveryTrustedConnectivityAvailable`,
`secureNetworkingAvailable`) and `DevicePreparedness` four plus `.all` — **neither has any
lock/unlock case**, and CoreDevice contains zero references to `RemoteUnlock`. The tunnel-assertion
work is real but orthogonal. `TODO(tunnel-keepalive)` and this gap are separate problems and must not
be merged.

### The actual mechanism: an escrowed remote-unlock keypair

One layer below CoreDevice, in
`/System/Library/PrivateFrameworks/RemotePairingDevice.framework/Versions/A/RemotePairingDevice`:

```
RemotePairingDevice.RemoteUnlockKeypair                        (hostKey, deviceKey, keybagProvider)
ControlChannelConnection.requestCreateRemoteUnlockKey(onComplete:)
ControlChannelConnection.requestRemoteUnlock(hostKey:onComplete:)
ControlChannelConnection.peerDeviceSupportsRemoteUnlock
KeybagProvider.unlock(hostKey:deviceKey:) throws
(extension __C.CUPairedPeer).remoteUnlockKey : Data?          // escrowed ON the pairing record
RemoteUnlockDeviceKeyForTunnelRequest / …Response
```

with strings `"Pairing record already has a remote unlock key."`, `"The device must be unlocked to
complete the operation"`, `"The device does not support remote unlock."`, `"A failure occurred
remotely unlocking the device."`.

And our exact error is a first-class case in that enum: `RemotePairingError.unlockRequired` is case
16 → **error 1016**, sitting directly beside `remoteUnlockFailure` and `remoteUnlockKeysUnsupported`.
Apple modelled "not unlocked recently" as a gate **with a named escape hatch**, not as a wall.

So: a trusted host's pairing record can carry a keypair provisioned once while the device was
unlocked; a client holding it calls `requestRemoteUnlock(hostKey:)` and the gate is satisfied without
a passcode.

**Nuance that changes how this should be described.** This is not "operate a locked device" — it is a
real, silent **unlock** (`KeybagProvider.unlock` unwraps the keybag). It mutates device state; it
just skips the passcode prompt. Any future feature here must be described that way to users.

### Not reachable from ipb, and the blocker is structural

- The feature is **not exposed** as any `com.apple.coredevice.action.*` identifier, so
  `Experiments/tools/cd_action.m` cannot reach it with any payload. It lives behind a different XPC
  surface (`com.apple.remotepairingdevice.tunnelmanagement`).
- DeviceHub's real entitlements (from the app binary, not the `DevicesTrampoline` launcher):
  `com.apple.private.coredevice.client`, `com.apple.private.hid.client.event-{filter,monitor}`,
  `com.apple.projectsetdeviced.client`, and **`keychain-access-groups: com.apple.dt.Devices`**,
  Apple-signed (TeamIdentifier `59GAB85EFG`) with library-validation.
- The escrowed key lives on the pairing record and is guarded by that keychain access group, enforced
  by securityd regardless of the caller's own signing status.

**Conclusion: honest "not reachable".** Not a missing flag or an unmapped payload — an unsigned
helper can never join `com.apple.dt.Devices` or hold `com.apple.private.coredevice.client`. Protocol
knowledge would not help. This should be treated as a **permanent capability boundary** for the
no-entitlement design, and recorded as such in the roadmap rather than kept as an open TODO.

### Inferred, not verified

That **DeviceHub itself** invokes `requestRemoteUnlock` is *not* established: neither CoreDevice nor
DeviceHub's binary references the RemoteUnlock symbols, so the call site is presumably a daemon
(`remotepairingd.xpc` was located but not inspected). Whether our two attached iPhones have ever had
a remote-unlock key provisioned is also untested.

### Safe follow-up, if it is ever worth the time

A read-only probe against `com.apple.remotepairingdevice.tunnelmanagement` asking
`peerDeviceSupportsRemoteUnlock` for an already-paired device. A *permission/entitlement* refusal
would confirm the boundary above; a schema error would mean the gate is at the payload layer instead.
Zero device interaction. Low priority given the boundary conclusion.

### Addendum: the call site is `remotepairingd`, and it is a control-channel message

Follow-up to the above, resolving what the investigation left inferred. `remotepairingd`
(`/Library/Apple/System/Library/PrivateFrameworks/RemotePairing.framework/.../remotepairingd`, running
as pid 19048 on this host) contains the remote-unlock strings directly:

```
Error encountered saving updated paired peer object after adding remote unlock key: %@
Failed to request new remote unlock key: %@
Received remote unlock key response in invalid state: %@
Exchanging remote unlock keys is unsupported over Bluetooth.
```

It does not import the RemotePairingDevice symbols (`nm -u` count 0), so it carries its own copy, but
the strings put the logic there rather than in DeviceHub — which matches neither DeviceHub nor
CoreDevice referencing `RemoteUnlock`.

The transport is a **control-channel message**, not a CoreDeviceService action:
`ControlChannelMessage.Request.remoteUnlock(Foundation.Data)` and `.Response.remoteUnlock` are enum
cases in `RemotePairingDevice`. The Bluetooth string implies it is expected to work over USB and
network.

**What this sharpens.** The unlock is performed by a *system daemon we do not control*, and on this
host it demonstrably works (Device Hub survives a lock here), so the escrowed key **is** provisioned
and `remotepairingd` **is** willing. The difference between Device Hub and `ipb` is therefore
client-side gating, not a missing capability on the machine — consistent with
`com.apple.private.coredevice.client` being the discriminator. That is a narrower and more testable
claim than "not reachable", though it does not change the conclusion for an unsigned helper.

**Dynamic confirmation is available and cheap.** SIP is disabled on this host and `lldb` already
attached to a signed Apple binary earlier in this work (`devicectl`, where `library-validation` did
not block debugging). DeviceHub is running with only `library-validation` too. So the decisive
experiment is: attach to `remotepairingd` with auto-continue breakpoints on the remote-unlock path
(the `Experiments/devicehub-trace/` governor pattern exists precisely for this), lock the device, and
compare whether the path fires for a Device Hub action but not for an `ipb` one. A backtrace at the
hit names the gate. Not yet run — it briefly pauses a system daemon that both attached iPhones
depend on, so it should be done when the devices are not in use.


## 2026-09-15 — Gap 2 hypothesis: our digitizer reports carry `remoteTimestamp = 0`

Static investigation, no device touched. Claims below re-verified independently before recording.

### Verified

- `makeDigitizerReportData` (`Sources/universalhid_glue.swift`) builds every touch report purely
  through the ABI shims and **never writes `remoteTimestamp`** — 0 occurrences in the function.
- The field exists: `UniversalHID.DigitizerReport.remoteTimestamp: Swift.UInt64?`
  (getter/setter/modify present in `nm -gU`).
- Only **two** builders stamp it, both hand-assembled from captures:
  `makeAbsolutePointerHIDReport` at byte offset 11 and `makeScrollWireHIDReport` at byte offset 13,
  both via `reportTimestamp()` (`mach_absolute_time()` ticks). **No wire builder exists for
  `DigitizerReport`.**
- So **every synthetic touch ipb has ever sent carries `remoteTimestamp = 0`** — `bin/ipb tap`,
  `swipe`, and every click in `ipb mirror`.

`mirror.m`'s own comment already says this out loud, two lines above the code that still uses the
zero-timestamp shim for touches: the wire builder "stamps remoteTimestamp, which Device Hub sets on
every report and the shim path leaves zero".

### The inference, and its limit

Ordinary app UI accepts a zero timestamp; system-presented alerts plausibly check event recency and
drop it silently — which matches the symptom exactly (taps work in apps, do nothing on permission
prompts, no error surfaced).

**This is inferred causality, not device-tested**, and one correction to the investigation's framing:
it described the scroll case as already "root-caused", but `docs/protocol.md:790` labels that
reasoning **"Hypothesis, not …"**. What *is* established is empirical: scroll only started working
once the wire builder (which stamps the timestamp) **and** an AbsolutePointer companion were both in
place. So the timestamp may well be **necessary but not sufficient** here too, and the digitizer may
likewise need framing we do not send.

### Two rival hypotheses checked and deprioritised, with evidence

- **`DigitizerTarget`** is a *physical display selector* — `mainScreen`, `display1…display10`
  (CoreDeviceUtilities symbols) — not a window/process/trust router. `target=0` is correct for a
  phone. Ruled out.
- **`Authenticated=true`** on the `mainScreenButtons` (0x402) descriptor is the only such flag, is
  unused by any ipb command, and its usage page/usage looks like a physical hardware-button proxy
  rather than a generic trusted-input gate. Deprioritised, not refuted.

### Why this one is worth doing

Unlike Gap 1, this needs **no entitlement**: it is a data field on an already-open, unentitled
service. If the hypothesis holds, the fix is to build a `makeDigitizerWireHIDReport` mirroring the
two existing wire builders.

**The offset must be captured, not guessed** (Rule 1). The digitizer report is 464 bits / 58 bytes,
and a naive "last 8 bytes" guess collides with the swipe-flag setter bits `mirror.m` records at
424/429/434 (bytes 53-54). No digitizer wire capture exists in this repo — only Scroll and Keyboard
were ever captured.

### Experiment, for when the devices are free

1. Run `Experiments/tools/rxpc_tap.c` (the interposer used for the 2026-09-09 scroll capture) while
   an operator uses **Device Hub** to tap (a) ordinary app UI and (b) a button on a real system
   permission prompt.
2. Decode the captured `DigitizerReport` bytes and locate `remoteTimestamp`'s real offset, as was
   done for Scroll (13) and AbsolutePointer (11).
3. Record whether (a) and (b) differ in report **sequence**, not just content — scroll needed a
   companion report, so do not assume a single-field fix.
4. Add the wire builder behind a **new low-level command**, not the default `tap`, and re-run the
   alert-tap scenario. Confirms if the same coordinates now dismiss the prompt; kills it if not, in
   which case sequence/framing or a genuine trust gate is next.


## 2026-09-15 — Lock hold settled at 0.4 s; an older sweep is superseded

The user measured the side button's duration gate precisely: **0.28 s does nothing, 0.29 s locks.**
That is a sharp boundary and it refines — without contradicting — the coarse bracket measured earlier
the same day (0.25 inert / 0.35 locks, on both the localNetwork 12 mini and the wired 13 Pro).

### The conflict, and how it was resolved

`bin/ipb`'s own comment recorded an earlier CLI sweep calling **0.40 s and 0.45 s inert**, with only
0.60 s locking — which is incompatible with a 0.29 s boundary. Adjudicated by direct test rather than
by preferring the newer number:

```
hold=0.40  base=6 344 871 B  after=36 071 B  => LOCKED (black frame)
```

0.40 s locks. Three independent measurements now agree (0.29 boundary, 0.35 on two devices, 0.40
here) against that one sweep, whose own comment already warned the mapping was "measured but not
settled". The probable error is the failure mode this repo hit again today: **a screenshot that fails
to write being read as "no change"** — which silently converts "locked" into "inert", exactly the
direction of that sweep's disagreement.

### Value chosen: 0.4 s, in both the mirror and `ipb power`

Not 0.29 s, because press and release are two separate sends with the network between them and jitter
shortens the interval the device observes — barrier tails of 346 ms have been measured on
localNetwork. 0.4 s is ~1.38× the boundary. Not 0.5 s, because the extra 100 ms is latency the user
feels on every lock and the margin is not needed. 0.7 s once opened Siri, so the usable band is
roughly 0.3–0.6 s and 0.4 sits comfortably inside it.


## 2026-09-20 — Supported matrix narrowed to iOS 27+; stream no longer reports success on an early stop

### iOS 26 dropped from the supported matrix

Decision by the user. iOS 27 and macOS 27 have shipped broadly, and **no iOS 26 device remains
available** to verify against — the iPhone 15 Pro (26.6.2) is no longer connectable. Continuing to
claim iOS 26.6+ support would be an unverifiable claim, which Rule 1 does not allow.

This also resolves the open caveat on the App Switcher usage (`0xff01`/`0x10`): it was verified on
two iOS 27.0 devices and the iOS 26 gap that was recorded as owed no longer applies.

### `TODO(stream-seconds)` fixed

`ipb stream --seconds 60` ended at ~15 s and exited **0**. The cause, established earlier, is the 12 s
hard stall guard at `Sources/video_stream.m`: on a static screen distinct frames stop, the guard
breaks the collection loop, and only an unmet `--count` exited non-zero — so a run that did not do
what was asked reported success. That is the inverse of Rule 2's "failure is an exit code, not a log
line".

The loop now records **why** it ended. If the stall guard fired before the requested budget elapsed,
the run exits **7** — already documented as "no frames within the watchdog window", which is exactly
this condition — and logs `stopped early: no new frame for 12s, before the requested --seconds
elapsed`. A run that genuinely completes its budget is unaffected, and `--count` keeps its own exit 8.


## 2026-09-20 — Protocol alignment audit: Device Hub's tap was never captured

Independent audit (Fable) of how well this project actually understands the Device Hub protocol,
prompted by the user's assessment that several defects traced to fragmentary captures with the gaps
filled by guessing. Static analysis only. Seed: host `UniversalHID` 90.1, CoreDevice 642.15,
DeviceKit 255.2.3.

### The headline, and it is worse than "fragmentary"

**Device Hub's tap has never been captured.** Every byte of Device Hub traffic in this repo is
Scroll, AbsolutePointer, or the Command modifier of ⌘L. The 58-byte Digitizer reports in the first
capture were *counted but never decoded*; the second capture contained none.

So the report type behind every `ipb tap`, `swipe` and mirror click was built from Swift setter shims
with invented timings, validated only by "the app opened". Worse, the bytes at `docs/protocol.md:64`
presented as the digitizer wire reference were captured **from ipb's own helper**, not from Device
Hub — we have been checking our output against itself.

### The wire format does not have to be reverse-engineered

Every UniversalHID report type carries a real **USB-HID report descriptor**
(`static <T>.descriptor.getter`, 22 exported) and Apple's encoder sizes reports from the same
descriptor via `HIDReportDescriptor.reportBitCount(for:)`. Dumping and parsing them reproduces
**every** offset this repo obtained by capture — Scroll 168 bits, AbsolutePointer 152, Keyboard 312,
Digitizer 464 — so the method is self-validating and is the allocation authority on both sides.

Derived `DigitizerReport` layout (bits): `0-8` id 9; `8-16` contactCount; `16-24` contactCountMax;
contacts *i*=0..4 at `24+40i` (+0 identifier 5b, +5 resting, +6 Touch, +7 InRange, +8 X u16, +24 Y
u16); `224-320` embedded ScrollCollection; `320-360` per-contact identity; **`360-424`
remoteTimestamp**; `424-459` swipe flags (pending 424, locked 429, up 434); `459-464` pad.

### The remoteTimestamp hypothesis is weakened, not confirmed

The earlier Gap 2 investigation proposed that `remoteTimestamp = 0` is why system dialogs ignore our
taps. The audit puts the field at bit 360 (byte 45) — but two findings cut against the hypothesis:

- **Zero and nil are wire-identical.** The setter uses `csel x0,xzr,x0` on the Optional tag, so a
  zero *is* Apple's own nil encoding, not a malformed value.
- On the decode side `addRemoteTimestamp` begins `cbz x0` — zero simply attaches nothing, and a
  non-zero value becomes a *vendor-defined child event*, not a parent timestamp.
- A **timestamp-less KeyboardReport dismissed a system alert** (`verification.md:261`), though that
  was a "cannot verify app" alert rather than a TCC prompt.

Not refuted, but it is no longer the leading explanation and must not be implemented as though it
were established.

### The stronger candidate: our lifts are never announced

Ranked first by the audit, and **verified in code here**: `makeDigitizerReportData` sets
`contactCount = touching ? 1 : 0`, so a lift reports **zero contacts** while still writing contact 0
with Touch cleared. A decoder iterating `0..<contactCount` therefore never sees contact 0 lift — the
finger is announced down and never announced up. Standard HID practice is the opposite: the lift
report still *describes* one contact, with the tip switch clear, so the count should be 1.

This would plausibly explain both the system-dialog symptom and the user's earlier report that home
screen icons stopped responding after a bottom-edge swipe (a device believing a contact is still
down). **Untested** — see below.

### Other gaps recorded, ranked

1. Tap framing vs Device Hub — release framing (above), contact identity never set, remoteTimestamp
   never set, pointer buttons byte on click unknown.
2. **Silent no-ops are structural**: rc=0 on ineffective usages (the `0xff01/0x100` case) and on
   ignored reports. "Works" in the gate, nothing on the device.
3. Service targets `0x101`/`0x501`/`0x200` were **assumed and never read from Device Hub**; the
   capture never dereferenced `x2` (the HIDServiceID argument).
4. `KeyboardReport` is 31 B against a 312-bit (39 B) descriptor, and the timestamp setter *no-ops*
   below 39 B — adding a timestamp later would silently do nothing.
5. Scroll `accelX = dx/40` and the momentum decay are invented.
6. `nav-report`/`dock-report` rest on a **retracted premise**; `pointer-report`, `scroll-report`,
   `scroll-event`, `vendor-defined`, `uhid-swipe-report` have no device effect ever demonstrated,
   yet `docs/protocol.md` labels some "verified".

### The capture methodology itself is the root cause

`taps.tsv` only taps `UniversalHIDService.send` and never the Indigo button/digitizer sockets — so
the recorded conclusion "Device Hub locks via a non-UniversalHID channel" is an **artifact of not
tapping the right thing**. No action script ever contained a click. The 60/s governor sheds mid
tap-and-drag. And `rxpc_tap.c` cannot see shared-cache callers. The universal choke point is
`xpc_remote_connection_send_message*` under lldb — which also yields the service ID — and lldb is
known to work on signed Apple binaries on this host.

### Test attempt, and why it proved nothing

The `contactCount = 1` change was built and run, then reverted. **Both the change and its baseline
measured 0/3**, which looked like a clean negative until a screenshot showed the 13 Pro sitting on
the **passcode entry screen** the whole time — taps at (0.15, 0.12) land on empty space there. Both
rounds are void. This is the third time today a measurement was taken without first confirming
device state; the standing lesson from the earlier screenshot-missing false positives applies here
too, and should be enforced by checking a known-state screenshot *before* any input experiment,
not after.


## 2026-09-20 — Lift framing corrected: a lift now describes one contact, not zero

### The defect

`makeDigitizerReportData` sent `contactCount = touching ? 1 : 0`. Per the HID specification **and**
the report descriptor now in `docs/protocol.md` (DigitizerReport bits 8–16, logical max 5), Contact
Count is *the number of contacts described by this report*, not the number still touching. A lift
still describes contact 0 — with `Touch` cleared — so the correct value is **1**.

Sending 0 meant a decoder iterating `0..<contactCount` never saw contact 0 lift: **every synthetic
finger ipb has ever put down was never announced as lifted.**

### Tested properly this time

The three void measurements earlier today were all taken without confirming device state first. This
run confirmed state before touching anything: `passcodeRequired: false`, and a screenshot **looked at**
to verify the home screen (8 859 330 B) rather than inferred from a byte count.

| | tap launches an app |
| --- | --- |
| baseline (`touching ? 1 : 0`) | **3/3** |
| `contactCount = 1` | **3/3** |

No regression. Each trial re-verified the home screen and aborted rather than scoring if any
screenshot was missing or the pre-state was wrong.

### What this does and does not establish

**Established:** the change is spec-correct and safe. Ordinary app UI is unaffected — taps continue
to launch apps, and multi-step in-app navigation (three TestFlight screens, then the app's own UI)
worked throughout.

**Not established:** that it fixes system dialogs. No system-presented prompt could be produced on
this device to test against. The two developer apps that might prompt were tried: the BLE tool
reached its scan screen with **no Bluetooth prompt**, i.e. permission had already been granted.
Getting a real prompt needs either an app whose permission has never been granted, or the specific
app the user originally hit.

The change is committed on its own merits — it makes the report match the descriptor and the
specification — and **not** as a claimed fix for Gap 2. Gap 2 stays open.


## 2026-09-21 — KeyboardReport raised to its descriptor size, and the gap is now a build failure

Host macOS 27 beta / Xcode 27.0 Beta 6, CoreDevice 636.3, device iPhone 13 Pro on iOS 27.0, wired.

### The fix

`makeKeyboardHIDReport` allocated `uhidHIDReportInit(0xf8, 0x01)` — 248 bits, 31 bytes. The report
descriptor specifies 312. Decoded from the descriptor bytes themselves
(`Experiments/hid-descriptors/descriptors.txt`):

| descriptor item | bits |
| --- | ---: |
| `85 01` report ID 1 | 8 |
| `05 07 19 01 29 e7 96 e8 00 75 01 81 02` keyboard usages 1..0xE7, 232 × 1 bit | 232 |
| `a1 02 06 1a ff 0a f1 e0 … 75 08 95 01 81 01` vendor 0xFF1A/0xE0F1 constant byte | 8 |
| `06 00 ff 0a 02 01 75 08 95 08 81 02` vendor 0xFF00/0x0102, 8 bytes | 64 |
| **total** | **312** |

248 stopped exactly at the end of the constant byte, i.e. immediately before the last field — which
is `remoteTimestamp`, the same bytes 31-38 carried by Device Hub's captured ⌘L reports.

### Verified on the wire, not by rc=0

Traced `UniversalHIDService.send(report:to:)` in ipb's own helper while sending usage 41 (escape):

```
len=39 B   bytes: 010000000000020000000000000000000000000000000000000000000000000000000000000000
```

39 bytes, report ID `01`, and the usage bit still lands correctly — usage 41 at bit 41+8 = 49 is
byte 6 bit 1, which is the `02`. The keyboard offset mapping is unchanged by the resize.

### The reason it survived so long, and the check that now catches it

This defect was invisible from both ends: a short report is accepted by the service and returns
`rc=0`, and the field that fell off the end has a setter that **no-ops on an undersized report**.
So neither the gate nor a future "add remoteTimestamp" change would have reported anything.

`scripts/check_report_sizes.py` parses each report's own descriptor, sums the Input items, and
compares against what the builder allocates. It runs from `make` as the `check-reports` target, so
this class of bug now fails the build. It was confirmed to actually catch the original defect —
reverting to `0xf8` produces:

```
makeKeyboardHIDReport allocates 248 bits but KeyboardReport specifies 312 -- 8 bytes short.
Fields above the allocation are silently dropped.
exit=1
```

The parser independently reproduces every size already in `docs/protocol.md` — Digitizer 464,
Keyboard 312, Scroll 168, AbsolutePointer 152, AppleVendorKeyboard 88 — which is the same
self-validating property that made the descriptors worth trusting in the first place.

### Not claimed

This does **not** set `remoteTimestamp`; it only makes the field exist, so that setting it later
will do something instead of silently nothing. No claim is made about Gap 2.


## 2026-09-21 — Device Hub's buttons captured; the "lock goes somewhere we cannot see" question is closed

Host macOS 27 beta / Xcode 27.0 Beta 6, DeviceHub 27.0, CoreDevice 636.3; device iPhone 13 Pro on
iOS 27.0, wired. lldb attached to `DeviceHub` with all ten CoreDevice HID send paths bound. An
agent operator drove Device Hub's own `Controls` menu; no synthetic touch was used at any point.

### The result

| window | reports |
| --- | --- |
| baseline, no input | **0** |
| Home | `HIDButton.sendButton` ×2 — code `0x40`, states 0,1 |
| App Switcher | `HIDButton.sendButton` ×4 — code `0x40`, states 0,1,0,1 |
| Lock | `HIDButton.sendButton` ×2 — code `0x30`, states 0,1 |

`sendCustomButton`, all three `UniversalHIDService.send` overloads, and every other Indigo socket
took **zero** hits. Full layout and the dereference technique are in `docs/protocol.md`,
"Device Hub's buttons: captured".

### What it overturns

`docs/protocol.md` recorded that Cmd-L produces only the Command modifier on the wire and concluded
Device Hub "locks the phone through some channel that is not UniversalHID" — an open mystery since
2026-09-09. It is closed, and the answer is mundane: **the Indigo button socket, Consumer `0x30`,
the same usage `ipb lock` already sends.**

The reason it stayed open for twelve days is the reason the 2026-09-20 alignment audit predicted it
would: `taps.tsv` had exactly **one** active tap, `UniversalHIDService.send`. The Indigo
button/digitizer/scroll sockets were never bound, so "Device Hub does not send it over
UniversalHID" was the only conclusion the instrument could ever have produced. The audit called
this an artefact of not tapping the right thing. It was.

### What it confirms

Home (`0x0c`/`0x40`) and Lock (`0x0c`/`0x30`) are **identical** to what `ipb` already sends —
verified against Apple's own client rather than inferred. Two independently-derived routes agreeing
is the strongest evidence this repo has produced for either command.

### What it finds

**Device Hub has no dedicated App Switcher usage — it double-presses Home.** `ipb` uses
AppleVendorKeyboard `0xff01`/`0x10`, found by trial on 2026-09-14 and screenshot-verified working.
Both mechanisms work; they are not the same mechanism. `ipb` already carries
`cd_home_double_button`, which is exactly Device Hub's approach, unused by `recents`. Recorded as a
known divergence, not a defect — swapping a verified one-event path for a four-event one is a
behaviour change that needs its own evidence.

### Method note

`sendButton` is generic, so its arguments arrive as pointers and the usage page lives in the
generic type parameter. A tracer that reads argument registers directly records stack addresses and
learns nothing; `dhtrace.py` needed an explicit `deref` spec. The first run of this capture produced
exactly that useless output, which is why there were two rounds.

### Not claimed

No tap was captured — sending a synthetic touch is blocked on the operator's session. Gap 2 is
untouched by this record.


## 2026-09-21 — Gap 2's reproduction problem solved on paper; accessibility-tree route settled

Companion record to the button capture of the same date. Nothing here was measured on a device;
these are a method and a static-analysis result that would otherwise live only in a scratch
directory and a conversation.

### A reproducible system-presented alert, at last

Gap 2 has been blocked for days on **reproduction**, not on analysis: the recorded blocker was
"needs a real system-presented prompt", and every app on the attached devices had already granted
its permissions, so no TCC prompt could be produced. The open question to the user — *which app
produced the original prompt* — was never answerable.

It does not have to be a permission prompt. **The home-screen "Remove App" confirmation is a
system-presented alert**: long-press an icon, choose "Remove App", and SpringBoard puts up
"Delete 'X'?" with Delete / Remove from Home Screen / Cancel. It is available on demand, needs no
particular app state, and is **dismissible with Cancel**, so it can be raised and dismissed
indefinitely without deleting anything.

That removes the dependency on the user's original prompt entirely. Credit: proposed by the
independent reviewer (gpt-6-astra) while arguing — correctly — that the Gap 2 blocker was a
reproduction problem and not a byte-level one, and that a capture should be spent falsifying a
specific hypothesis rather than fishing.

**Experiment, for when a synthetic touch is authorised:** drive Device Hub's own mirror window to
long-press an icon, tap "Remove App", then tap **Cancel** (never Delete), with the tracer bound to
all ten CoreDevice HID paths. Two control taps on blank wallpaper first — without a baseline
showing the rig records an ordinary tap, an empty result on the alert is uninterpretable. This
answers two questions in one run:

1. **Does Device Hub itself succeed on a system alert?** Never tested. It has always been assumed
   it does. If it fails, Gap 2 is a second structural boundary like Gap 1, and no amount of
   byte-level correctness will close it.
2. **What do Device Hub's digitizer bytes actually look like?** Still never captured.

### The accessibility tree is not reachable over CoreDevice, but is over lockdown

The same review named **UI-hierarchy / accessibility-tree read** as the largest capability gap for
agent use and as absent from the roadmap, reasoning from this repo's own research notes: the
"minimum agent loop" in `docs/research/adb-capability-boundary.md` includes a hierarchy dump, and
`docs/research/agent-frameworks.md` attributes every other iOS framework's dependence on XCTest to
exactly that API never being exposed outside it. Coordinate-only control is what makes an agent
brittle.

The proposed route was that Xcode's Accessibility Inspector might read a live device tree over the
same CoreDevice/RemoteXPC mechanism as `dtuhidd`. **It does not.** Mounting the iOS DDI
(`/Library/Developer/DeveloperDiskImages/iOS_DDI/Restore/*.dmg`) and enumerating it:

- 16 daemons: `dtappserviced`, `dtconfigurationd`, `dtdebugproxyd`, `dtdeviceinfod`,
  `dtdiagnosticsd`, `dtfilesandboxd`, `dtfileserviced`, `dthidd`, `dticond`, `dtlocationd`,
  `dtpasteboardd`, `dtremotedisplayd`, `dtscreencaptured`, `dtuhidd`, `gputoolstransportd`,
  `testmanagerd`. **No accessibility daemon.**
- 54 `com.apple.coredevice.feature.*` identifiers across their launchd plists. **None is
  accessibility-related.** The nearest are settings-level actions in CoreDevice itself
  (`getlargeraccessibilitysizesenabled`, `getcustomizableappearanceelements`), which change
  accessibility *settings* and do not read a UI tree.

The capability is still reachable, by a different transport. `AccessibilityAudit.framework` in
Xcode carries `AXAuditDevicesAppRemoteServer` with an `initWithTransport:` initialiser and the
string `com.apple.accessibility.axAuditDaemon.protocolVersion`; it links no CoreDevice framework at
all. That is the **lockdown** service family, not CoreDevice/RemoteXPC — which means it belongs to
the stage-4 pymobiledevice3 client, where lockdown is already the transport, and **not** to this
helper. Recorded as a finding, not as a plan: no service name has been confirmed on the wire and
nothing has been attempted against a device.

### Other points from the same review, recorded rather than actioned

- The roadmap undersells what makes `ipb` different. Every surveyed real-device iOS automation
  framework needs a signed XCTest runner on the device; `idb` cannot do real-device UI automation
  at all. No-server, no-signing, coordinate-level injection is a different category, not a faster
  `adb`.
- **The smoke gate's advisory-only identical-frame handling is under-ranked.** It violates
  `AGENTS.md` Rule 4 in writing on every run, which undermines confidence in every other
  verification record in this file. Cheap to fix; still open.
- **"Silent no-ops are structural" deserves promotion from a note to a design decision.** It has
  now surfaced twice — the App Switcher `0xff01/0x100` dead usage, and the voided `contactCount`
  test — which is Rule 3's own "third patch means redesign the area" trigger.
- Arbitrary Unicode text entry (beyond single key usages) is part of the stated minimum agent loop
  and is not on the roadmap either. Everything else in the adb boundary list is already covered by
  `devicectl` and should not be reimplemented inside `ipb`.


## 2026-09-21 — Device Hub alignment: idle timeout, sender ownership, smoke and trace corrections

Start `f2e85a6`, branch `codex/devicehub-alignment`. Measured host macOS **26.5.1 (25F80)**,
Xcode **27 Beta 6**, Device Hub **27.0 (255.2.3.5)**, CoreDevice **642.15**; wired **iPhone 13 Pro,
iOS 27.0 (24A437)**. The phone explicitly reported `passcodeRequired: false`, with Home/Settings
visually observed. This corrects use of older host/CoreDevice seed labels for this session.
Raw evidence stays outside Git under `~/.local/state/ipb/20260921-alignment/`.

### Confirmed failures and fixes

1. **Static content caused early failure.** `launch com.apple.Preferences`, then `stream --seconds 25
   --fps 3` exited 7 after three/five distinct images. Repeated after quitting Device Hub: same
   failure, excluding concurrent viewing as a required trigger. Instrumentation separated decoded
   frame receipt from output; even decoded frames ceased during static content. An isolated mirror
   `--seconds 28` also exited 7 (350 received frames, then silence).
   After the first-frame-only policy, `stream --seconds 32 --fps 3` stayed alive to Home at t+22 s:
   first three outputs ended near t+2.61 s, new output resumed at t+22.56 s; 41 distinct / 878 decoded,
   rc=0 at 35.61 s including setup. Mirror `--seconds 32` likewise remained alive, resumed on Home,
   received 746 frames, and exited 0 at 32.82 s. This establishes an idle failure and recovery,
   not a universal diagnosis of historical stream freezes. Unread stdout still exited 8 after
   11.38 s; unattainable `--count 10000 --seconds 3` exited 8 after 6.21 s. No first-frame/stop watchdog
   was removed. Relevant logs: `stream-static-alone`, `stream-idle-resume`, `mirror-static-before`,
   `mirror-idle-resume`, `blocked-stdout`, `unmet-count`.
2. **Caller timeout did not serialize the underlying sender.** The old `sendBounded` algorithm,
   copied into a host-only semaphore-controlled fixture, produced two timed-out callers with
   `calls=2 max_active=2`. The new shared implementation keeps ownership through actual completion;
   its regression verifies no second invocation while occupied, max concurrency 1, bounded close,
   rejection after close, completion recovery and no replay. Report timeouts remain fatal.
   `old-sendbound-repro/` retains the original fault evidence. Normal native mirror mouse/shortcut
   regression remains pending because the computer-use tool later reported the Mac locked; user
   unlock was requested. CLI input success is not substituted for this mirror-specific check.
3. **The smoke gate gave false passes.** Its first revised real run still returned 0 while Home
   swipe/scroll had no intended effect; the clock icon moved (0.0343% / 0.0487% material pixels), and
   Escape left the context menu visible. That run is **not accepted**. The gate now requires >=1%
   pixels changing by >=16 in an RGB channel, with explicit no-op reasons; it uses a Settings list
   and observable `a`/Backspace search effects. An intermediate run correctly failed a scroll fixture
   sent farther into the bottom boundary; corrected `dy=+0.30` matches `y+dy` and returned toward top.
   The final **installed-layout** run passed, and key screenshots were inspected: Settings launch,
   App Switcher, list down/back up, context menu, query `a`, cleared query, final Home. Exact run:

   ```sh
   DEVELOPER_DIR=/Applications/Xcode-27.0.0-Beta.6.app/Contents/Developer \
   DEVICE_ID=<13-pro-coredevice-uuid> SMOKE_INTERACTIVE=1 \
   TAP_XY='0.61 0.696' LONG_XY='0.845 0.696' \
   <staged-prefix>/share/ipb/smoke_matrix.sh <staged-prefix> <local-evidence>/smoke-final
   ```

   Evidence runs are `smoke-local` (rejected), `smoke-settings` (failed), `smoke-final` (passed).
   This macOS 26 gate is supplementary; it does not close the macOS 27 release gate.
4. **Trace startup/status was misleading.** Zero-match `grep -c ... || print 0` produced duplicate
   zeroes and zsh arithmetic errors; double detach gave lldb exit 1 after successful capture.
   The driver now waits for resolved locations and actual Continue, detaches once and returns
   failure truthfully. Revised live capture: ten ready taps, 21 calls, no shed taps, clean rc=0
   detach, Device Hub alive. Missing-symbol host fixture: rc=4, no `.bound`, empty capture, target
   detached and alive. See `devicehub-verify.*` and `trace-fixture/`.

### Protocol and functional comparison

Before the Mac locked, Device Hub was operated directly: Settings tap/drag, Home, the cancellable
Remove App confirmation, preview rotate/restore, Siri menu, and keyboard capture into Settings
search. All test text was cleared; no app was removed and no permission prompt was granted.

- The original digitizer capture has 14 reports plus four typed button calls and a clean zero-input
  baseline. Both ordinary tap and system Cancel use `0x101`, count=1 even on UP, max=5,
  identifier/identity=2 and nonzero timestamp. **Current ipb also successfully cancelled the same
  system alert.** Original TCC/privacy prompts remain untested; no causal credit is assigned to
  the earlier contact-count fix.
- The revised capture confirms Keyboard 39 B / `0x200`, AbsolutePointer 19 B / `0x501`, and Scroll
  21 B / `0x501`. Synthetic wheel emitted only zero-motion may-begin and did not visibly scroll;
  physical trackpad acceleration/momentum remain uncalibrated. Siri sent code `0xcf` with states
  0/1 but showed no Siri UI. Rotate changed the host preview; the native screenshot stayed portrait.
- Device Hub's ordinary text forwarding works; mirror currently has shortcuts only. Record Screen
  and Action Button were disabled on this 13 Pro. No capability is claimed from these menu labels.

### Build and acceptance boundary

Local `make XCODE_PATH=/Applications/Xcode-27.0.0-Beta.6.app install PREFIX=<local-staged-prefix>`,
`scripts/test_bounded_sender.sh`, `scripts/test_smoke_matrix.sh`, shell syntax and report-size checks
passed. Native output/protocol captures and GUI observations above are kept distinct from host fault
injection. A fresh review found stale current-doc claims about uncaptured taps/31 B output; those
were corrected. It found no further reachable code defect in the reviewed change.

The remote macOS 27 host (26A5425a, CoreDevice 642.15) built helper/video/mirror and passed the sender
host test in isolated `/tmp/ipb-alignment-20260921-D2DOwc`. It currently selects **Xcode 26.4** and its
paired iOS 27 phone reports **unavailable**. Therefore the required **macOS 27 + Xcode 27 + iOS 27**
real-device gate is still open. Native mirror input also awaits manual Mac unlock. These are
acceptance limits, not evidence that the release matrix passed.


## 2026-09-21 — Mirror native input regression after manual Mac unlock

Revision `1ed76f7`; same local macOS **26.5.1 (25F80)** / Xcode **27 Beta 6** / CoreDevice
**642.15**, wired **iPhone 13 Pro / iOS 27.0 (24A437)**. `lock-state` explicitly returned
`passcodeRequired: false`. `make -q XCODE_PATH=/Applications/Xcode-27.0.0-Beta.6.app build/ipb-mirror`
confirmed the existing build was current; its executable was copied into a local test app bundle
and ad-hoc signed so the computer-use tool could select its window. No implementation changed.

The app ran through `IPB_MIRROR_HELPER=<local-test-app>/Contents/MacOS/ipb-mirror caffeinate -di
bin/ipb -s <13-pro-coredevice-uuid> mirror --seconds 600 --csv <local-evidence>/events.csv`, with
`DEVELOPER_DIR` selecting Beta 6. Direct native-window operations visibly demonstrated:

- Click Settings; drag the list down and back to the top.
- Home and App Switcher shortcuts; a bottom-edge swipe from Settings back to Home.
- Screenshot shortcut produced the expected Settings image at 1170 x 2532.
- Actual Size explicitly fell back to fit because the visible screen was too small; Zoom to Fit
  remained usable, and a resized-coordinate click opened General as intended.
- Return Home and close the window normally: helper/wrapper exit 0, reason `window closed`, with
  no surviving wrapper/helper/keepalive/caffeinate PIDs. The computer-use AX lookup after closing
  timed out because the target exited; process status and shutdown logs independently prove exit.

CSV/log totals: 24 submitted, **23 sent**, one `scroll_unsupported`, zero report/barrier errors,
zero abandoned/in-flight sends, max queue depth 2, and 8863 received media frames with zero reported
media errors. TOUCH, typed-button and BOTTOM_EDGE paths were exercised. Host sender timings are
not device-completion measurements; the visible states above are the effect evidence.

**Remaining limit:** the computer-use scroll operation emitted one precise AppKit event with
phase=0, momentum=0, delta=(0,-872). Mirror rejected it explicitly and the list did not move. This
is a reproducible synthetic-event limitation, not calibration or disproof of physical trackpad
scrolling. Volume, Lock/Wake and forced transport loss were not rerun. The macOS 27 release matrix
still lacks its previously recorded Xcode/device prerequisites.

Local artifacts: `~/.local/state/ipb/20260921-alignment/mirror-unlocked/` contains `run.json`,
`summary.json`, `mirror.log`, `events.csv` and the key device screenshots. The screenshot-shortcut
output path is recorded in `run.json`. Raw artifacts remain outside version control.


## 2026-09-21 — Deeper Device Hub keyboard, display and rotation research

Source revision `c14eed6`; macOS **26.5.1 (25F80)**, Xcode **27 Beta 6**, Device Hub
**27.0 (255.2.3.5)**, DeviceKit **255.2.3**, CoreDevice **642.15**, wired **iPhone 13 Pro /
iOS 27.0 (24A437)**. `lock-state` explicitly returned `passcodeRequired: false`.
This was a research pass with no product code changes, build or smoke rerun.

Two native Device Hub captures resolved all ten HID taps, shed none and detached with lldb exit 0:
`text-input` recorded **35 calls** (24 Keyboard, eight Digitizer, three AbsolutePointer, including
setup/cleanup); `rotation` recorded **three calls** (one AbsolutePointer, two Digitizer).
Action markers fall after the respective `.bound` readiness file and before the final trace
summary. The decoder's first-call-based window is narrower and is not the actual readiness window.

- **Key delivery is not literal text.** Shift/Command chords contain simultaneous held usage bits.
  Injected `aA1!` appeared as `啊A1!` with the phone's Pinyin keyboard visible; Command+A/Backspace
  visibly cleared it. Synthetic `中文🙂` produced no captured HID call or insertion. Host paste
  timed out waiting for the application to read the clipboard; only Command+V was captured and
  the field stayed empty. These observations do not characterize every physical keyboard/IME path.
- **Clipboard policy is independent.** Device Hub exposes Use Shared Clipboard, Get Clipboard and
  Send Clipboard; their synchronization state was not established. `pasteboard info` returned
  26006 for `com.apple.is-remote-clipboard`. No contents were read or overwritten, and this error
  is not a proven explanation for the earlier host paste timeout. Existing UTF-8 clipboard
  copy/get evidence remains valid; focused arbitrary-text insertion is still unverified.
- **The earlier presentation-only rotation inference is superseded.** Rotate Left changed queried
  device orientation to landscapeLeft, while primary display orientation stayed rot0 and native
  Settings remained portrait. No HID report accompanied the rotation itself. A rotated-preview
  click opened General; its Pointer and Digitizer coordinates differed consistently with a
  quarter-turn transform. Only this orientation was measured; see `docs/protocol.md` for values.
- **Display/capability metadata is available now.** `device info displays` returned primary
  1170x2532 bounds, scale 3, orientation and backlight. A non-primary Wireless entry present during
  viewing disappeared after quitting Device Hub. `device info details` advertised `startaudiooutput`
  but not `audiooutput`; `device info audio` returned missing-capability error 1001. Presence of an
  audio-stream feature is not proof of audio-device selection or recording support.

Local artifacts: `~/.local/state/ipb/20260921-deep/` contains `session-manifest.json`, both trace
sets and action markers, decoded reports, display/capability JSON, screenshots and targeted shipped
binary symbol/disassembly extracts. Proposed additions and their acceptance criteria are in
`docs/devicehub-alignment.md`. Raw artifacts remain outside version control.

Cleanup restored and queried portrait, cleared test search text, returned the phone Home, disabled
keyboard capture and quit Device Hub. Tracers detached cleanly. This local macOS 26 run does not
close the macOS 27 release gate. Full orientation mapping, physical trackpad calibration, real
host IME input, UI-tree transport, multi-touch, remote unlock, recording and audio streaming remain
unverified by this pass.


## 2026-09-22 — Display, literal text and orientation implementation

Source base `cc43495`, branch `codex/devicehub-alignment`. Local host **macOS 26.5.1 (25F80)**,
Xcode **27 Beta 6**, Device Hub **27.0 (255.2.3.5)**, DeviceKit **255.2.3**, CoreDevice **642.15**,
UniversalHID **90.1**, DDI **27A5252f**, unlocked wired **iPhone 13 Pro / iOS 27.0 (24A437)**.
DDI identity came from live `device info ddiServices`. This run is supplementary evidence;
the declared macOS 27 release gate remains open. A fresh SSH attempt to the prior host closed
at port 22, so its current Xcode/device prerequisites could not be checked.

### Confirmed differences and fixes

- **Display selection:** the live primary LCD is 1170 x 2532 at scale 3, while decoded video is
  1184 x 2576. A temporary non-primary Wireless entry must not determine crop or touch geometry.
  `displays --json` and `capabilities --json` now expose versioned snapshots; mirror prefers the
  explicit primary size, retains range checks and uses bounded, non-overlapping metadata queries.
- **Rotation:** Device Hub pointer/touch pairs confirm different presentation/native spaces.
  Settings can stay portrait while device orientation changes; Calculator rotates its content.
  Mirror now handles those separately and preserves unsent rotation requests during refresh.
  A malformed `info: []` host fixture also reproduced an exception, fixed by checking its type.
- **Bottom edge:** Device Hub's landscape Calculator swipe returned Home with 58-byte UHID
  digitizer reports on `0x101`, locked + native-left flags, including on UP. The first ipb
  implementation's portrait Indigo route did not work there; an unflagged UHID route also did
  not work. Rotated-content edges now use the captured direction flags. Portrait content retains
  the previously verified Indigo behavior. Static setters, capture values and limits are in
  `docs/protocol.md`, "Display, literal text and rotated edge alignment".
- **Ordinary release:** the HIDReport-returning builder still emitted count 0 on UP, unlike the
  corrected Data-returning builder. Both now share count-1 construction. Ordinary identity,
  maximum-contact and timestamp conventions were preserved; no speculative field alignment.
- **Literal text:** Device Hub and ipb both inserted exact `ipb-中文🙂 A1!` into Settings search
  with Pinyin active using clipboard + the captured four held-key sets. A subsequent paste prompt
  exposed a false-positive smoke assertion: the modal changed pixels but the field was empty.
  The gate now checks the focused field with OCR and fails before any clear/close action if absent.
  Empty-field/clipboard-suggestion and permission-modal screenshots both failed the new check.

### Verification and boundaries

`make XCODE_PATH=/Applications/Xcode-27.0.0-Beta.6.app` and staged `make install` completed.
Host checks passed: `test_device_features.py`, compiled `test_display_geometry.m` and
`test_device_control.m`, framework-backed `test_input_reports.swift`, `test_bounded_sender.sh`,
`test_smoke_matrix.sh`, report-size checks, zsh syntax and `git diff --check`. These cover exact
UTF-8/trailing-newline copy, failure ordering/no replay, held sets, touch release/direction bytes,
coordinate transforms, malformed JSON, 6-second query timeout and cancellation.

The final installed-layout interactive smoke (`smoke-complete/`) exited **0 / SMOKE PASSED**.
The operator inspected the fresh paste modal and allowed this one synthetic paste during the
gate's bounded wait; field OCR then passed in 17 seconds. No persistent paste policy was changed.
All 20 saved screenshots were inspected: Settings opened, App Switcher appeared, the list moved
in both directions, long press opened a context menu, key input changed search, exact Unicode
text appeared and cleared, and the device returned Home. The nondestructive/Home baselines stayed
semantically on Home; small status/animation pixel changes are not counted as action proof.
Earlier `smoke/` printed a false pass and is **rejected**; `smoke-final/` and `smoke-accepted/`
correctly failed while the paste prompt remained unanswered. `rc=0` for `ipb text` means submitted,
not accepted by the focused application, and it replaces the clipboard.

The final native mirror (`mirror-release.log`) opened General/back at all four device directions,
accepted rotation shortcuts, and returned Home with the retained portrait edge path. It sent
14/14 input events, with zero rejected/overloaded/in-flight/abandoned sends, max queue depth 1,
5095 media frames and zero reported media errors; normal close exited 0. Installed smoke also
verified signal shutdown with no keepalive orphan. These are host transport metrics plus visible
effects, not device-completion latency measurements.

The ipb rotated-edge trace matched Device Hub's report shape. Controlled 300 ms sequences using
the same builder returned Home in both Calculator landscape directions. Approximately 6 ms CUA
drags still had no effect; no artificial production delay/interpolation was added. Physical mouse
edge timing, physical trackpad calibration, upside-down app content and atomic frame/orientation
correlation remain unverified. Another task's concurrent orientation changes invalidated one
earlier Device Hub landscapeRight click capture; it is excluded from the mapping evidence.

Raw artifacts remain outside Git in `~/.local/state/ipb/20260922-features/`: build/install logs,
`edge.jsonl`, `ipb-edge.jsonl`, their lldb logs, static setter extracts, display/DDI JSON,
`mirror-release.log`/CSV, and the named smoke directories. Product/test/document changes are in
this branch; local probes, full transcripts and success screenshots are not committed.

## 2026-09-22 — Accessibility Inspector property path and target-dependent detail

Research from `7693ebe` after pushing all six alignment commits to
`origin/codex/devicehub-alignment`. macOS 26.5.1 (25F80), Xcode 27 Beta 6,
Accessibility Inspector 5.0 (192.6), wired iPhone 13 Pro / iOS 27.0 (24A437),
Developer Mode and DDI services enabled; pymobiledevice3 11.10.2. No product code change or
macOS 27 release-gate claim. No jailbreak/injection/helper installation or AX activation action.

**Question corrected:** caption-only output did not establish the scope of AXAudit. Apple's
Inspector displayed element class/address and a hierarchy, and its actual outgoing
`deviceElement:valueForAttribute:` descriptors were captured at the DTX constructor boundary.
Replies to `_AXHierarchyElementsAttribute` contained recursive `AXAuditNode_v1` values. The initial
two trace attempts had unresolved breakpoints and detached without collecting evidence; the valid
run resolved both taps in the main Inspector process and detached cleanly. This is not an XPC-helper
trace. Raw capture and bounded local probes remain outside Git at
`~/.local/state/ipb/20260922-ax-inspector/` (`inspector-trace.jsonl`, `lldb-trace.log`, and named probe
results); the condensed message shapes are in [protocol.md](protocol.md#accessibility-inspector-and-axaudit-2026-09-22).

**Independent reproduction:** after quitting Inspector, `PreferredRsdTunnel` connected to the
named phone and the advertised AXAudit `remoteserver.shim.remote` service. `deviceCapabilities`
included the captured property selector; `deviceApiVersion` returned 26. The focus event supplied
the actual property descriptors, which were passed back unchanged for read-only queries.

| Target / observation | Result and limit |
| --- | --- |
| Looktech Lab visible home heading | Label and traits matched the screenshot; class was UILabel, address non-null, hierarchy had 15 nodes. This establishes a partial AX hierarchy, not complete UIView ownership or all-app coverage. |
| Settings heading, then a second focus entry after a fresh launch/screenshot baseline | Labels/traits readable, class/address nil, hierarchy only one node in each case. Root cause unknown; target signing or permission is a hypothesis requiring a controlled comparison. |
| Frame/AXFrame candidate properties | Nil in these Lab and Settings reads. They were not supplied by the iOS focus descriptors. |
| Normalized-point request | Three points returned nil, with and without explicit inspector enable/target setup. CGPoint encoding derived from host disassembly + local Foundation archive; no successful Apple hit-test reference capture, so no impossibility conclusion. |
| Element preview + screenshot | Visible green outline around selected Lab text; PNG 1170×2532, logical display 390×844, scale 3, rotation 0. No structured element rectangle or borderFrame in this reply. |

The second advertised service, `remoteAXService`, says `UsesRemoteXPC=true` and `Entitlement=AppleInternal`;
it was not opened. The successfully exercised shim says `UsesRemoteXPC=false` and
`Entitlement=com.apple.mobile.lockdown.remote.trusted`. This supersedes the earlier claim that no AX
service can be reached through RSD, while keeping AX's DTX transport separate from HID's RemoteXPC
feature messages. It does not establish that a native CoreDevice feature exists for AX.

Inspector was quit, LLDB detached, app monitoring/preview were disabled, and Looktech Lab restored.
Screenshots checked the actual element text and removal of the preview outline. No settings toggle
or device permission response was selected. The production CLI still has no UI-tree command.
Next discriminators are a successful Apple hit-test capture, the focus hierarchy's completeness,
and a controlled explanation of the Lab/Settings detail difference; element coordinates remain open.

## 2026-09-22 — Page dump coverage and snapshot limitations

Follow-up to `9109c06` on the same macOS 26.5.1 / Xcode 27 Beta 6 / iPhone 13 Pro iOS 27.0
research pair. The user asked whether the complete page element tree can be dumped. No production
code changed and no supported macOS 27 release gate was run.

The bounded local probe sent `Direction.Next`, read only the descriptors supplied with each focus
event, and merged `_AXHierarchyElementsAttribute` replies by the opaque element token. It stopped
when the first focus token repeated: 36 unique focus tokens, 252 property queries, 131 merged nodes
and 130 edges under a Looktech Lab root, in approximately 14.4 seconds. Both JSON and a readable
tree were exported locally. Their `complete` field is false.

The decisive limitations are observable, not hypothetical:

- Before/after screenshots show that focus traversal auto-scrolled the page. The exported union
  includes lower-page entries; it is not a dump of just the initial viewport or an atomic snapshot.
- Two distinct UILabel tokens described the home heading. They were retained separately; caption
  equality is not a safe identity rule. The cycle establishes traversal termination only, not a
  census of hidden, ignored, unmaterialized or inaccessible views.
- A second probe recursively queried discovered handles without further focus movement. It reached
  99 nodes / 96 completed property replies before a four-second property timeout. Its screenshots
  showed Settings, while the seed and returned hierarchy root named Looktech Lab. This is a target
  mismatch observation, not a validated foreground-page dump; the synchronization cause is unknown.
- After explicitly launching Lab and checking a settled screenshot, a new session received 189
  `hostAppStateChanged:` events plus an event-type notification but no focus seed within three
  seconds. The recursive approach therefore remains unvalidated; no automatic action replay or
  protocol workaround was added.

Raw requests, outputs and screenshots are local under `~/.local/state/ipb/20260922-ax-inspector/`:
`page-dump.{json,txt}`, `page-dump-raw.jsonl`, `dump-before.png`, `dump-after.png`, and the separate
`page-expand*` outputs. Monitoring was disabled in cleanup. The final screenshot confirmed Lab's
home at the top with no preview outline. No AX activation or Settings toggle was performed.
The next implementation needs an explicit target check, bounded query errors and an honest
completeness/snapshot contract before this can become a reliable `ipb` command.

## 2026-09-22 — XCTest snapshot processor and direct-session gates

Offline follow-up to `d625705`. The user asked which device service processes XCTest snapshots
and whether the computer can establish an effective session without a runner. The iPhone 13 Pro
remained exclusively loaned to LookInside: **no device enumeration, connection, launch or input
was performed in this run**. This is static research, not a release-matrix or live denial result.

The Mac-local DDI image `022-22070-094.dmg` was mounted read-only. Its metadata records Public
DDI 27A5252f / build 1335 / XCTest 25227 / CoreDevice 642.15. `nm`, `otool`, `dyld_info`, launchd
metadata and code-signature entitlements were inspected for the arm64 slice. The traced request
reaches `XCTestSession` in device `testmanagerd`, then `XCAXManager_iOS`, `XCTAutomationSupport`
and AXRuntime's parameterized snapshot query. This establishes the XCTest receiver, not the
entire downstream AX IPC chain or snapshot completeness.

The decisive distinction is between ordinary `testmanagerd.remote` harness/control sessions and
the separate `testmanagerd.remote.automation` session. The latter contains executable snapshot
and attribute methods, but launchd declares `AppleInternal`; daemon startup also skips listener
registration unless `os_variant_allows_internal_security_policies` succeeds. Accepted automation
connections additionally require Automation Mode. Runner-local NSXPC authorization is a third
path, not an automatically available host proxy. Addresses, paths, entitlement keys and the
pymobiledevice3 control/runner sequence are condensed in
[protocol.md](protocol.md#xctest-snapshot-service-boundary-2026-09-22).

Raw static outputs, copied metadata, binary SHA-256 values and decoded CFString keys are retained
outside Git at `~/.local/state/ipb/20260922-xctest-snapshot/`. No production code changed; no
build/install/smoke run applies to this documentation-only investigation. Live advertisement,
service-start authorization, protocol exchange and snapshot output are still untested. After the
phone's explicit return, distinguish those layers with bounded probes before implementing a
client. The prior working AXAudit shim is independent of this restricted XCTest entry.

## 2026-09-22 — Runner-free element research: reply scope and concrete AXAudit comparison

Offline follow-up to `cc95213`, while the 13 Pro remained exclusively loaned to LookInside.
No device enumeration, connection, Mirroring/Inspector launch, installation or input occurred.
The user requires continued exploration until a reliable current-target tree is obtained without
installing a phone-side app, or the requested model consultations and our own investigation have
no further viable experiments. This round does not satisfy either stopping condition.

The original raw replies were re-counted separately: 36 focus hierarchy replies contain 14–46
nodes each, while 131 is their union. The expansion probe already queried the application root
(two nodes) and UIWindow (four nodes); its 96 completed queries include 13 nil results. This
rejects the suggestion that a missing single root query explains the partial result. Its next
pending handle was the tab bar, inferred from request order, not established as the timeout cause.

Cached iOS 27.0 (24A437) arm64e AXRuntime serializes application-root handles as a PID plus two
64-bit fields, zero and one on this seed. This matches the captured Lab root. All handles in both
prior unions refer to PID 7513; a later Lab event reports 7534. A local experimental probe can
construct a root from a fresh observed PID, perform bounded hierarchy expansion, stop on timeout
and preserve incomplete results. Only token/decoding/identity fixtures were checked on the Mac;
the probe has not been run against the phone and proves neither fresh-root access nor coverage.

The installed iOS 26.5 simulator runtime (23F77) provides concrete `axauditd` code unavailable in
the cached iOS 27 framework alone. Static tracing identifies target-PID matching with fallback,
first/last special-element queries, focus-history filtering, ancestor/local-child hierarchy
construction and a child-count cap. Its parameterized property receiver immediately completes
nil, before an AX query; descriptor existence is not a raw 95006 forwarding API. The iOS 27
developer-attribute predicate differs, so simulator restrictions are not reported as the cause of
the production-device behavior. Exact paths/addresses and proof boundaries are in
[protocol.md](protocol.md#axaudit-root-handles-and-hierarchy-limits-2026-09-22).

Requested consultations completed with Claude Opus 5, configured dsh Sub2API DeepSeek Flash, and
Grok 4.7 (response identifies `grok-4.7-build`). All returned further candidates. Suggestions
contradicted by the raw root-query evidence were rejected; remaining candidates are experiments,
not accepted protocol facts. The Mirroring candidate led to verified host imports for remote
accessibility data and an overlay, but no live session or externally readable remote tree.

Raw model replies, binary analyses and the unrun probe remain outside Git under
`~/.local/state/ipb/20260922-element-research/`. No product code or support matrix changed; no
build/install/smoke gate applies to this research-only update. Physical tests remain pending the
phone's explicit return, including target provenance, hierarchy coverage and service access.

## 2026-09-23 — Fresh-PID AX tree read and direct XCTest service check

Host macOS 26.5.1 (25F80), Xcode 27 Beta 6 / CoreDevice 642.15; wired iPhone 13 Pro on iOS 27.0
(24A437). LookInside explicitly returned its exclusive phone lease before this run. Lab was already
installed and on its logged-in home page; its current process PID 7720 was read from `ipb ps`,
then a screenshot verified the visible page. No phone-side helper, Runner, app install, app launch,
focus movement, scrolling or preview was used.

A seed-specific AXRuntime app-root token for PID 7720 reached `AXAudit` without a focus event.
One root request returned two nodes; bounded expansion then queried all 129 discovered handles
in 6.35 seconds with zero nil/timeout replies. A second independent session produced the same
129 handles and labels in 7.42 seconds, again with zero nil/timeout replies. Screenshots before
and after showed the same Lab home page. The raw union of reply context included two extra
SwiftUI/UIKit parent edges. Taking each handle's direct children from **its own query reply**
removed those context edges and yielded a single-root 129-node/128-edge tree, with all nodes
reachable and one parent per nonroot node. This is a verified element tree for that page and seed,
not evidence of an atomic, universally complete snapshot or element geometry. The original
131-node focus sequence remains a different, scrolling temporal union.

The same RSD inventory advertised `com.apple.dt.testmanagerd.remote.automation` and
`com.apple.accessibility.axAuditDaemon.remoteAXService`, both marked `AppleInternal`, alongside
ordinary `.remote` and the working AXAudit shim. `remoteAXService` terminated the RemoteXPC
handshake. Automation accepted a TCP connection but did not answer either a five-second generic
DTX capability handshake or a five-second proxy-channel request without that handshake.
Ordinary `.remote` completed the generic DTX handshake immediately. This is a failed host
exchange, not proof of the exact permission check or universal runner-free impossibility. No
snapshot request or Runner launch occurred; all sockets were closed.

Raw replies, normalized research-only tree, before/after screenshots and service-stage logs stay
outside Git at `~/.local/state/ipb/20260922-element-research/`. No production code changed, so
no build/install/smoke gate applies. The 13 Pro lease was then explicitly transferred back to
LookInside, and this task stopped accessing it.

The user directed further testing to the iPhone 12 mini: UUID
`1D533177-5153-5A0C-9102-8D0A8ADDAEFB`, wired, iOS 27.0 (24A437). `ipb ps` and `ipb screenshot`
both stopped before their requested operation because CoreDevice could not mount the DDI on a
locked phone: error 12040 wrapping **10003**, “The device is currently locked.” The user was
asked to unlock it manually. No AX read or XCTest service result exists for the 12 mini yet.

## 2026-09-23 — Unlocked 12 mini access boundary before Developer Mode

After the user unlocked the wired iPhone 12 mini (iOS 27.0, 24A437), `ipb ps` advanced from the
lock error to CoreDevice **12040** / **12052**, Cryptex errors **16** / **20**: “Installing cryptex
com.apple.MobileAsset.DDI is disallowed because developer mode is not enabled.” The process list
was not read. This is an explicit DDI prerequisite failure, not evidence that AXAudit requires
Developer Mode.

A separate paired `PreferredRsdTunnel` connection to this 12 mini succeeded without DDI. Its
service list contained 62 entries and advertised
`com.apple.accessibility.axAuditDaemon.remoteserver.shim.remote` at port 49343 with
`com.apple.mobile.lockdown.remote.trusted`; no `testmanagerd` service was advertised. The AXAudit
DTX transport connected, but a bounded `deviceCapabilities` call closed the channel with
`ConnectionTerminatedError: Channel is closed`. Repeated bounded attempts reached the same stage.
The tested host exchange did not obtain capabilities or a tree; the closure's precise cause is
unknown. This establishes a before-state for repeating the same probe after Developer Mode is
enabled. The research-only probe and raw JSONL stay outside Git at
`~/.local/state/ipb/20260922-element-research/probe_12mini_access.py` and `12mini-access.jsonl`.
No production code changed or build/smoke gate was run.

## 2026-09-23 — No-DDI process identity and direct AX request on 12 mini

The 12 mini still reports `developerModeStatus: disabled`, `ddiServicesAvailable: false`, booted,
wired and with its RSD tunnel connected. The existing `com.apple.os_trace_relay.shim.remote`
service answered a read-only `PidList` without DDI: 615 process entries, including SpringBoard
PID 37 and Settings (`Preferences`) PID 1843 at the time of the query. This provides a fresh-PID
source independent of `ipb ps`; it does not identify which app is foreground.

Using that Preferences PID and the captured `_AXHierarchyElementsAttribute` descriptor, one
bounded read-only `deviceElement:valueForAttribute:` request was sent on a new AXAudit DTX
connection **without first calling `deviceCapabilities`**. It ended with
`ConnectionTerminatedError: Connection closed`, without an AX reply. The process list contained no
process whose name matched `audit`, although that alone does not prove the daemon was absent or
explain why the service closed. No target setter, focus action, app launch or installation was
used. The local one-shot probe remains outside Git at
`~/.local/state/ipb/20260922-element-research/probe_12mini_no_caps.py`. The next controlled
comparison is the same read-only probe after Developer Mode and DDI become available.

## 2026-09-23 — AXAudit service lookup failure with Developer Mode disabled

On the same wired iPhone 12 mini / iOS 27.0 24A437, a bounded `os_trace_relay` stream captured
device logs while one more read-only Settings-root hierarchy request used its fresh PID 1843.
The AXAudit request again ended in `ConnectionTerminatedError: Connection closed`. In that request
window, `lockdownd` logged activation of
`com.apple.accessibility.axAuditDaemon.deviceservice.lockdown`, followed by
`failed to do a bootstrap look-up: xpc_error=[3: No such process]`, a failed init and socket
closure. This establishes the immediate missing-Mach-service boundary for this device state;
the advertised RSD shim alone was not a running AX reader.

The locally installed **iOS 26.5 simulator** launchd plist for the same Mach service declares
`LimitLoadToDeveloperMode=true`. That is corroborating static evidence on a different seed,
not a read of the iPhone's iOS 27 plist. The iPhone still reports Developer Mode disabled and
DDI unavailable. The causal A/B requires enabling Developer Mode, then repeating the capability
and read-only hierarchy requests. No focus, app launch, installation or input was sent. The
bounded, filtered logs remain outside Git at
`~/.local/state/ipb/20260922-element-research/12mini-ax-close-logs-info.json` and
`12mini-ax-close-logs.json`; the local DDI was detached after offline inspection. No product
code changed, so no build or smoke gate applies.

## 2026-09-23 — Runner-free AX trees on the enabled 12 mini

Host macOS 26.5.1 (25F80), Xcode 27 Beta 6 / CoreDevice 642.15; wired iPhone 12 mini, iOS 27.0
24A437. The user enabled Developer Mode, restarted and confirmed it on the phone. Immediately
afterward CoreDevice showed `developerModeStatus: enabled` but the tunnel was not ready. A bounded
`bin/ipb -s 1D533177-5153-5A0C-9102-8D0A8ADDAEFB ps` completed after DDI startup. A fresh
device listing then showed `ddiServicesAvailable: true` and a connected tunnel. No new phone app
or XCTest Runner was installed by this task.

The paired RSD service count rose from 62 in the disabled/no-DDI state to 85; both
`testmanagerd.remote` entries appeared. The AXAudit DTX transport and `deviceCapabilities` both
succeeded, and the process list contained `axauditd`. This is the successful side of the physical
state A/B. Because Developer Mode, reboot and DDI mount happened together, it does not isolate
which one directly registered the Mach service that was missing before.

`ipb screenshot` showed the Home page. With fresh SpringBoard PID 204 and the captured read-only
hierarchy descriptor, a single root request returned ten nodes. A 300-query experiment discovered
373 handles but ended at its budget, so it was not counted as a tree closure. Two subsequent
sessions queried **444/444 discovered handles** each, with zero nil and zero timeout replies;
their own-query child graphs each had one root. Each session's raw replies duplicated the same
child token twice inside two parent replies. Removing only those exact duplicate references
yielded **444 nodes / 443 edges** with one parent per nonroot node and no unreachable handles.
The token set and child sets matched between sessions. The clock text and order of seven children
inside the Utilities folder changed, so the resulting serialized trees were not identical.
Visible Home icons and dock matched the before/after screenshots; no focus motion was sent.

For a second target, `ipb launch com.apple.calculator` started the preinstalled system app, which
was not running beforehand. Screenshot showed a clear display (`0`) and the keypad. Fresh
Calculator PID 2450 produced **45 nodes / 44 edges** in each of two independent, all-queried
sessions, zero nil/timeouts. Their normalized tree content was identical and named the visible
digits/operators, History and Change Mode. The two candidate attributes `Frame` and `AXFrame`
returned nil on the `7 Keyboard Key`. pymobiledevice3's `AXAction-2010` press request was submitted
for that token, but the screenshot still showed `0`; this does not establish a working node
activation path or the exact reason it had no effect. The task then sent Home and verified the
original Home page by screenshot. No app data was entered or changed.

On that final Home page, advertised AXAudit queries `deviceRunningApplications` and
`deviceCurrentState` returned `[]` and `0` respectively, so this probe did not obtain a
foreground PID from AXAudit itself.

These are observed AX hierarchy closures on the named pages, not proven atomic, complete UIKit
view trees or arbitrary-app coverage. The research-only probes, raw DTX replies, normalized trees,
candidate-attribute result and before/after screenshots remain outside Git under
`~/.local/state/ipb/20260922-element-research/12mini-*`. Only documents changed in the repo;
no production build, installation or `scripts/smoke_matrix.sh` gate applies to this research run.

## 2026-09-27 — AXAudit geometry and action discrimination on 12 mini

Host macOS 26.5.1 (25F80), Xcode 27 Beta 6 / CoreDevice 642.15; wired iPhone 12 mini,
iOS 27.0 (24A437), Developer Mode and DDI enabled. The AXAudit shim connected through a
paired pymobiledevice3 11.10.2 RSD tunnel and advertised 85 services. The tested phone was
returned to Home and a final AXAudit screenshot confirmed it. No app/Runner was installed.

SpringBoard PID 204 and Calculator PID 2450 were read from the device process list. Read-only
root expansion queried every **407** discovered App Library handle and every **45** Calculator
handle in separate bounded sessions, without advancing inspector focus. These are observed
graphs, not completeness or atomicity proofs. Calculator showed the preinstalled keypad and `0`
before action tests. The AXAudit screenshot reply reported logical bounds **375×812** and
`displayNativeScale=2.88`; its PNG was **1125×2436**, making actual PNG/logical ratios exactly
3 on each axis. This invalidates using the reported native scale alone for outline-to-touch
coordinate conversion.

Following a fresh Claude Opus 5.5 read-only review, the proposed geometry routes were checked
against local evidence. Host `AccessibilityAuditDeviceManager.framework` disassembly shows
`{CGPoint=dd}` passed as an `NSValue` to `sendControlAsync:replyHandler:` for normalized-point
lookup; iOS 26.5 **simulator** `axauditd` reads `CGPointValue` and completes that invocation.
Two correctly typed Calculator point requests on the physical 12 mini returned nil; no element
arrived in monitored events. This remains an unsuccessful probe without an Apple-client wire
capture or exact physical-daemon implementation, not proof that the selector is unavailable.

The seven advertised audit types yielded one Calculator issue with
`ElementRectValue_v1={{16,234},{343,84}}` and two SpringBoard issues with rectangle values.
The SpringBoard issue records had no decoded element token. The results prove host-visible
**audit-issue regions**, not generic `AXAuditNode_v1` frames. A previous Lab preview and one
Calculator screenshot showed a green outline. Targeting several Calculator and SpringBoard
tokens for preview did not consistently produce the requested outline; multiple before/after
PNG pairs were identical. A screenshot-diff rectangle API therefore did not pass even a small
repeatability check, and no centre-tap calibration was attempted.

Inspection of installed pymobiledevice3's earlier `perform_press` call found its
`PlatformElementValue_v1` transport missing the nested `Value`. This alone cannot explain all
failures: the follow-up sent the exact focus-event element and advertised `AXAction-2010`
descriptor for Calculator `7`, then `All Clear`; both returned without a visible effect.
The three action screenshots have the same SHA-256 digest, and the display stayed `0`.
Node activation remains unverified; neither a missing permission nor an unsupported action
has been established as the cause.

The Xcode 27 Accessibility Inspector launched, but the available desktop control session could
not operate its target picker (`elementHasNoFrame` / `noWindowsAvailable`). Thus no reference
Apple-client DTX trace was obtained. The physical iOS 27 symbol cache contains
`AccessibilityAudit.framework` but no `axauditd` executable, so the simulator static comparison
cannot close the physical-daemon question. Separately, `bin/ipb screenshot` failed with
CoreDeviceError -1 / `com.apple.mobiledevice` -402653181, and `bin/ipb home` timed out at 5 s,
while the paired pymobiledevice3 AXAudit session worked. These incidental CLI failures were
not reproduced or root-caused in this research run; they are not counted as a geometry result.

Local evidence remains outside Git under
`~/.local/state/ipb/20260922-element-research/12mini-20260927-*`,
`preview-12mini-20260927/`, and `opus55-geometry.json`. Only research documents changed; no
production build, install or `scripts/smoke_matrix.sh` gate applies.

## 2026-09-27 — Apple Inspector service-start trace and lockdown point reply

Host macOS 26.5.1 (25F80), Xcode 27 Beta 6 / Accessibility Inspector 5.0 (192.6), CoreDevice
642.15; wired iPhone 12 mini / iOS 27.0 (24A437). The iPhone 13 Pro was not selected or
addressed in this run. Bringing Inspector's main window forward made the target picker usable;
it listed the 12 mini. Selecting it first displayed “Connecting to target…”, then “Error
connecting to device.” This supersedes the preceding record's **UI-picker blocker**, but no
physical-device Apple DTX request was captured.

A bounded LLDB trace on that exact Inspector process captured one complete connection attempt.
At the statically identified return sites in `XDMDeviceMonitorEmbedded._connectToDevice:`,
`AMDeviceConnect` returned 0, then `AMDeviceStartSession` returned 0 about 20 seconds later, and
`AMDeviceSecureStartService` returned **-402652910 (0xE8000112)**. LLDB read the call-site
CFString as `com.apple.accessibility.axAuditDaemon.remoteserver`; this host's MobileDevice
`AMDErrorString` maps the code to `kAMDRemoteConnectError`. A second attempt began within the
trace cap, but its later service result was **not** captured. The debugger detached successfully.
The completed attempt failed before a DTX capability, point or preview request could be sent.

Independently, `devicectl device info lockState` against both the 12 mini's CoreDevice UUID and
UDID, including one run with Xcode 27 as `DEVELOPER_DIR`, ended in “Failed to allocate RSD
device” / **-402653181 (0xE8000003)**, named `kAMDNoResourcesError` by this host's
`AMDErrorString`. This is another host-path failure; the trace does not prove it causes the
Inspector service-start error. The device was nevertheless listed as booted, wired, paired,
Developer Mode enabled, DDI available and RSD tunnel connected. A paired Python USB lockdown
client with `autopair=False` started **the same service name**, received an SSL-enabled port and
completed AXAudit DTX `deviceCapabilities` with **45** entries. Its AXAudit screenshot showed
an unlocked App Library. The device service and screen were available on that independent path.

Over the native lockdown AXAudit channel, two typed normalized-point requests returned `None`
through pymobiledevice3. A raw DTX capture of another `(0.7,0.4)` request separated the reply
from the wrapper value: message ID 1 received conversation index 1, type **0 / OK**, no payload.
No later DTX message or `host*` callback arrived in the next **four seconds**. A subsequent
`deviceCapabilities` call received type **3 / OBJECT** with the expected 45-entry payload,
validating the capture path. Enabling Inspector and app monitoring for one additional point
request also produced an empty high-level result; both were disabled in cleanup. This supports
an empty completion on the tested physical state, not an unsupported-selector, permission or
coordinate-space diagnosis. No ordinary-node rectangle was obtained.

The connection trace, bounded script and DTX metadata stay outside Git under
`~/.local/state/ipb/20260922-ax-inspector/connect-12mini-20260927.jsonl` and
`~/.local/state/ipb/20260922-element-research/12mini-20260927-point-wire.json`; the current
unlocked-screen screenshot is `12mini-20260927-regrab.png` beside the latter. Only documents
changed; no build, install or smoke gate applies.

## 2026-09-28 — iPhone 13 Pro Apple Inspector and audit-issue geometry

Host macOS 26.5.1 (25F80), Xcode 27 Beta 6 / Accessibility Inspector 5.0 (192.6), CoreDevice
642.15 / DDI 27A5252f; wired iPhone 13 Pro / iOS 27.0 (24A437), CoreDevice UUID
`7F2FE6E9-5423-552A-A2A2-C499F1D8672F`. The user requested this 13 Pro check after the
12 mini's host connection failure. No LookInside process was found running locally, and this
run did not assume a permanent change to the phone's separate allocation. The
`devicectl device info lockState` command reported `passcodeRequired: false` and
`unlockedSinceBoot: true`. Before/after `ipb screenshot` images showed the same unlocked Home
page apart from the clock.
`ipb doctor` confirmed the DDI, five HID services, wired transport and connected tunnel.

Unlike the 12 mini, Xcode's Accessibility Inspector accepted the 13 Pro target. Selecting its
`PDUIApp` target and running Apple Audit returned **nine warnings**: one Contrast, five Dynamic
Type, three Hit Region. Expanding the first Hit Region warning showed “Current size is 43 x 9”.
Its Quick Look preview showed a green rectangle on a Home-screen screenshot. That screenshot
does **not** prove the warning element was visible on Home: the selected audit target was
`PDUIApp`, and its later element label was not a Home icon. The Apple-client result proves that
this host/device pair can complete an AXAudit request; the 12 mini service-start failure is
not a universal host failure. Its device/state-dependent cause remains unknown.

Using paired pymobiledevice3 11.10.2 with `autopair=False`, AXAudit reported 45 capabilities.
Typed normalized-point queries at `(0.5,0.5)` and `(0.7,0.4)` both returned high-level `None`.
The advertised audit type is the string `testTypeHitRegion`: passing numeric classification
`100` instead timed out after 25 seconds. With the string, the audit returned **three issues**.
Each carried `ElementRectValue_v1` **and** `AuditElementValue_v1`; for example, the first had
rect `{{12.666666666666666, 167}, {43.111111111111114, 8.5555555555555429}}` and a
20-byte element token. Re-encoding that token as the captured `AXAuditElement_v1` wrapper let
`deviceElement:valueForAttribute:` return the label `进一步了解…`. The other two labels were
`接受并继续` and `关闭FaceTime通话`. Direct `Frame` and `AXFrame` queries returned nil for all three.
Passing pymobiledevice3's deserialized element object back directly raised
`DTXNSCodingError`; the wire wrapper is required for that follow-up query.

This establishes a token-to-rectangle association for **audit issues on this target**, not a
general node geometry getter or a safe screen coordinate for arbitrary clicks. The Apple-client
audit did not exercise Inspector's normalized-point lookup, so its request/reply remains the
next capture target. A 40-second LLDB trace of the functioning Apple client's outbound selector
path recorded 43 calls while selecting `13 Pro > All processes` and enabling inspection scope.
It included `deviceSetAuditTargetPid: 0`, app monitoring, `deviceDidGetTargeted`, monitored event
type `2` and `deviceInspectorShowVisuals: 1`, but no normalized-point request: the capture did
not trigger an actual pointer hit test. Replaying that observed setup in a direct session still
left a `(0.5,0.5)` point query nil; the session then disabled visuals and monitoring. LLDB
detached normally. The Inspector target and tab were restored to their prior
`Simulator > Photos` / Inspection state after the run. No device input, app launch, install or
production code change occurred. Local evidence is
`~/.local/state/ipb/20260928-13pro-axaudit/observations.json`,
`apple-inspector-dtx.jsonl`, `before.png`, `after.png` and `final.png`; only research documents
changed, so no build/install/smoke gate applies.

## 2026-09-28 — 13 Pro point selection and foreground-app control

Same macOS 26.5.1 (25F80) / Xcode 27 Beta 6 / CoreDevice 642.15 / DDI 27A5252f and wired
iPhone 13 Pro iOS 27.0 (24A437), UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`, as the
record immediately above. The phone was unlocked. This run tested whether Apple Inspector's
point mode actually sees a device element after an injected touch; it did not change product
code. Apple's [app-inspection instructions](https://developer.apple.com/documentation/accessibility/inspecting-the-accessibility-of-screens)
describe choosing the device/app and tapping an iOS element while point mode is enabled.

Device Hub's **View Screen** mirror displayed the 13 Pro Home page. A CUA click on Weather's
icon opened Weather's welcome screen, proving that the mirror click reached the phone. In
Inspector, point mode was on, but the selected element remained `None`. After choosing
`13 Pro > All processes`, `bin/ipb -s <UUID> tap 0.50 0.50` likewise left it `None`.
A 50-second LLDB trace of the Apple Inspector process, with breakpoints on its DTX-message
builder, `XDMDevice hostInspectorCurrentElementChanged:` and
`XDMDeviceTransportBased fetchElementAtNormalizedDeviceCoordinate:withCompletionBlock:`, caught
15 events during the target change. They were null focus/preview requests, target PID `0`,
settings and section-descriptor callbacks; no callback carried `ElementValue_v1` and no point
method was called. A separate 50-second trace covering the direct phone tap had **zero** hits
on these selected methods. These breakpoints are a bounded host-method trace, not a capture of
every possible DTX channel.

For a stronger foreground control, `bin/ipb -s <UUID> launch com.apple.calculator` succeeded
and Inspector's 13 Pro process menu newly listed **计算器**. With that app explicitly targeted and
point mode on, `bin/ipb -s <UUID> tap 0.10 0.08` opened Calculator's History sheet (confirmed by
`calculator-after-tap.png`), but Inspector still showed `None`; another bounded 50-second
trace had zero hits on the same methods. The existing displayed `7` in Calculator was left
untouched. The sheet was closed and `ipb home` returned the device to the same Home layout,
confirmed in `point-final.png`. Device Hub screen sharing was stopped; Inspector point mode
was turned off and its target was moved away from the phone. Its previous `Simulator > Photos`
target was no longer in the menu, so exact target restoration was unavailable.

An attempted Apple audit after selecting the current `PDUIApp` and then Calculator target
showed an empty result outline, so the documented audit-issue double-click handoff could not
be tested on this run. The earlier nine-warning audit remains a separate successful record.
The confirmed result here is narrow: the two **injected** input routes moved the phone UI but
did not enter Apple's Inspector element-selection path. A human finger tap under an explicit
foreground target is the next discriminator; do not infer that the device cannot ever return
a point-selected element or ordinary-node geometry.

Local success/failure evidence is kept outside Git in
`~/.local/state/ipb/20260928-13pro-axaudit/point-inspector-target-switch.jsonl`,
`point-before.png`, `point-after.png`, `calculator-current.png`,
`calculator-after-tap.png` and `point-final.png`. The two zero-hit traces were observed via
their bounded LLDB detach output and the absent trace file; the absence is meaningful only
for the three selected breakpoints. No build/install/smoke gate applies to this research-only
document update.

## 2026-09-28 — foreground Weather audit retest

Same host/device seed and UUID as the two 13 Pro records above. After returning the phone to
Home, `ipb launch com.apple.weather` failed with CoreDeviceError 10004 (“process identifier of
the launched application could not be determined”); this is a launcher-result failure, not
evidence that Weather could not run. `ipb tap 0.153 0.116` on the Home icon then opened the
Weather welcome screen, confirmed by `weather-current.png`. Its choices were left untouched.
With that screen foreground, Accessibility Inspector's 13 Pro process menu listed
`PDUIApp (5965)` but no Weather entry. The process/UI relationship is not established by the
menu alone. Selecting `PDUIApp` in the Audit tab, with all seven audit-type checkboxes enabled,
and pressing **Run Audit** left the results outline empty. Thus there was no issue row to
double-click; this does not invalidate the earlier successful nine-warning run.

A bounded 50-second LLDB trace of the same three host methods around the audit retry recorded
`deviceRunningApplications`, `deviceSetAuditTargetPid: 0`, null focus/preview calls,
`deviceHighlightIssue:` and one section-descriptor focus callback. It did not record a
`deviceBeginAuditTypes:` selector on that intercepted path. This is not a complete DTX trace,
so the absence cannot by itself diagnose why the Audit UI stayed empty. Inspector was returned
to the local Mac target with point mode off; `ipb home` restored the 13 Pro Home page,
confirmed by `weather-final-home.png`. Local evidence is
`~/.local/state/ipb/20260928-13pro-axaudit/weather-current.png`,
`weather-final-home.png` and `point-inspector-audit-retry.jsonl`. No product source changed;
no build/install/smoke gate applies.

## 2026-10-09 — AXAudit direction review and recorder evidence correction

Baseline `codex/devicehub-alignment` / `ec4fa4ae24d441c112647be087729c33d330eda2`.
This is an offline review, not a device run. Current host reads show macOS 26.5.1 (25F80),
Xcode 27 Beta 6 / Inspector build 192.6 and pymobiledevice3 11.10.2. No phone enumeration,
connection, input, Inspector launch or current device/PID/lock state check occurred. The 12 mini
allocation remains the default; the 13 Pro's older temporary tests do not establish ownership
today. No app/firmware/protocol consumer was changed, so build/install/smoke gates do not apply.

At the user's request, independent `claude-opus-5` and `gpt-6-astra` reviews assessed the direction
and next capture design (**source: peer**, not new runtime proof). Both read retained probe/trace
sources and results; Astra also read screenshots and checked local framework metadata. Opus
declared that some large sources were read through excerpts/summaries. Its CLI finished with
`subtype=success`, `is_error=false`, `permission_denials=[]`; model usage records the requested
Opus 5 plus CLI auxiliary reading/context processing. Main-session arbitration reopened the
decisive raw sources rather than adopting every peer assertion.

Confirmed recorder problem: the 9/28 main script installs only the outgoing-construction
breakpoint despite having unused reply-handling code. The point script adds some focus callbacks
but is not a complete receive/reply trace. It reads `x2` as point data; host disassembly shows
`d0/d1` contain CGPoint and `x2` is the completion block. Counters advance before filtering and
silently disable breakpoints at their cap, with no persistent trial/footer record. This explains
why the previous files cannot establish complete negative coverage; the register bug does not
explain zero hits. Rerunning device touches was unnecessary to establish these source defects.
The Apple-client recorder repair and live positive controls remain **pending**, not verified fixes.

The known host point caller belongs to `XDMDeviceSIM`. Simulator daemon code supplies a competing
touch-monitor/device-event route; its physical iOS 27 counterpart is unverified. Future selection
success may be an incoming event and must not require a host point RPC. Two peer overclaims were
also corrected: valid historical focus events advertise Activate, and several app-state events
report Foreground Running for different PIDs within a short receive window. Neither empty
sections nor a last-arriving app-state event can establish missing actions or a unique frontmost
PID. The [protocol reassessment](protocol.md#axaudit-recorder-and-route-reassessment-offline-2026-10-09)
retains specific script/disassembly/JSONL references and proof boundaries.

The current [R0–R3 plan](devicehub-alignment.md#axaudit-capture-plan) starts with recorder validity,
then a single-client focus baseline and human-finger/injected-input comparison, Apple's ordinary
selection/preview/Activate reference, and only then a current issue's highlight/Inspection handoff.
Each comparison requires coherent target/PID/token/screenshots and fresh tokens; action submission
is never automatically replayed. Apple pre-DTX service failure is diagnosed separately. A
completed zero-issue audit is valid and skips issue handoff. No new ordinary-node rectangle,
semantic action effect, physical-touch behavior or phone capability is claimed by this review.

A Git-external Python recorder was then prepared against the installed pymobiledevice3 11.10.2
source. It copies accepted outgoing chunks and completed/partial incoming reads before object
decoding, records markers/boundaries/footer and decodes archived streams offline. A bounded
local TCP loopback fixture passed: five messages in each direction were byte-identical to the
peer transcript, a large reply reassembled across fragments, request/reply identifiers and
signed wire channels survived, and a nested typed element token/event was preserved. Empty
type-0 OK, encoded-null type-3 object and invalid archive decode were distinguishable. Separate
fixtures verified a zero-traffic footer, explicit byte-budget failure, partial-read retention
and hook restoration. This is **local recorder validation only**, not device/Apple-client
coverage or a live-overhead measurement. Writer acceptance/drain does not prove device receipt.
No new phone session was opened after these fixtures.

Raw reviews, metadata and main arbitration stay outside Git at
`~/.local/state/ipb/20261009-axaudit-direction/` (`opus-review.json`, `opus-review.md`,
`astra-review.md`, `merged-review.md`, `raw-capture-index.json`, `dtx-runtime-methods.json`).
Local recorder/decoder and loopback results (`dtx_record.py`, `dtx_decode.py`,
`check_recorder.py`, `recorder-fixture-*/result.json`) remain there as ad hoc preparation.
Repository changes contain only condensed confirmed problems, current plan and evidence limits.

## 2026-10-09 — 13 Pro AXAudit finger, injection, Apple action and issue handoff

**Scope/seed:** research only on macOS 26.5.1 (25F80), Xcode 27 B6 / Inspector 192.6,
CoreDevice 642.15, DDI 27A5252f, paired unlocked wired iPhone 13 Pro (iPhone14,2),
iOS 27.0 (24A437). CoreDevice UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`;
USB UDID `00008110-0014711C3CC3801E`. `ipb doctor` passed unlock/Developer Mode/DDI/
HID prerequisites. The user explicitly selected this phone; this session did not operate the
12 mini. Direct AXAudit used paired USB lockdown / pmd3 11.10.2. Calculator PID 51031
was refreshed through OsTraceService and matched focus/issue tokens. Existing value 7 retained.

**Reproduction and decisive results:**

- Open Calculator with `ipb -s <UUID> launch com.apple.calculator`. With one direct AX client,
  obtain matching Next focus at monitoring 0, then arm type 2 and visuals. Actual SupportedEventTypes
  reply is integer 2, CanNavWhileMonitoring is false. The operator confirmed a real History tap;
  an independent session then used one `ipb -s <UUID> tap 0.10 0.08`. Each received matching
  `hostInspectorCurrentElementChanged:` followed by monitoring 0 before host cleanup. No host
  normalized-point fetch was sent. The finger capture decoded 41 messages cleanly; the injection
  capture decoded 44 complete messages including selection and the cleanup capability barrier,
  then retained a final inbound
  header without its body when the session closed. Its offline decoder reports that terminal
  incomplete read explicitly; it is not an empty success or full-stream-completeness proof.
  The fully captured selection window disproves an inherent injected-input restriction.
- Validate the native loaded arm64e DTX slice before attaching to Apple Inspector. The first
  fixture failed on a recorder callback bookkeeping error; it is invalid evidence. The corrected
  fixture matched its native transmitter sink byte-for-byte in both recording paths (647 bytes)
  and decoded typed token/routing. Live Apple captures resumed and detached cleanly without
  budget disable or capture errors. Incoming parser bodies are assembled, not raw fragmented wire;
  preserve the original last-fragment header and validate internal body length before derived decoding.
- Record before target selection. The first Apple attempt stayed blank with target 0/incomplete
  monitoring setup. A subsequent actual target 51031 request and monitoring 2 led to a successful
  injected History selection. Ten read-only properties and one-node hierarchy were populated as
  described in the protocol; no ordinary Frame. A fresh direct token reproduced these reads without
  an explicit Enable=1 request in that post-Apple state; this does not prove cold-start requirements.
- Apple's Perform sent an expected-reply Activate with null value, then received type-0 empty OK.
  The phone screenshot still showed 7 without History. A new independent direct session used its
  own matching token and the captured descriptor/null/reply shape once, also received empty OK,
  and showed no activation effect. This is not a successful click. The pmd3 convenience wrapper's
  differing token/null/reply shape is not a sufficient explanation. Permission cause remains unknown.
- Direct and Apple audits each completed all seven advertised types and returned one output-field
  issue: `StandardInputView;value:7`, classification 1000, rect `{{16,243},{358,88}}`. Apple single-click
  transported the issue array with `deviceHighlightIssues:`; double-click switched to Inspection,
  sent the issue element to FocusOnElement and LockOnCurrentElement, and received the same token/
  PID/identifier. Apple screenshot metadata (390×844, scale 3, rotation 0) and native 1170×2532 PNG
  agree with the highlighted output area (48,729,1074,264). Subsequent reads supplied ordinary
  descriptors/hierarchy but no Frame. This closes coherent issue association, not arbitrary-node geometry.
- Mac-target Frame messages were also captured on a different DTX connection. Pairing solely by
  message ID creates false matches; offline analysis preserves parser/transmitter identity and
  isolates phone traffic. Apple ordinary-reference and issue captures decode 288/199 messages
  across their captured connections with no decode errors after the explicit assembly treatment.

**Cleanup/limits:** close the Inspector started for this investigation; clear monitoring, visuals,
focus, preview, app monitoring, target and Inspector enable in a bounded direct session, perform
capability barrier and close sockets. The final cleanup capture likewise retains an incomplete
terminal inbound header after the barrier, explicitly reported by offline decoding. Fresh screenshot
confirmed Calculator 7 without outlines; Home restored the original page and was visually checked. All owned LLDB sessions detached.
No production code, app installation, certificate or release-matrix smoke changed/ran.

Local reproduction tools, raw bytes, summaries and screenshots remain outside Git at
`~/.local/state/ipb/20261009-13pro-axaudit/`; the local handoff lists individual captures and
connection mappings. Decisive sources include `apple-reference-2/decoded.jsonl` (phone transmitter
`0x73df841d0`, parser `0x7404a1680`, action 123 and its reply), `apple-issue-handoff/phone-only.jsonl`
(audit begin 194, issue-array highlight 195, focus 199, lock 200, completion 202 / focus event 204),
and the independent direct-reference summary. Historical dated records remain unchanged.

## 2026-10-09 — 13 Pro development-app action and task-port predicate

**Scope/seed:** refreshed `ipb -s <13-Pro-UUID> doctor` passed on macOS 26.5.1 (25F80),
Xcode 27 B6 / Inspector 192.6 / CoreDevice 642.15 / DDI 27A5252f, wired unlocked
iPhone14,2 iOS 27.0 (24A437), UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`.
Only this user's allocated 13 Pro was operated. This is supplemental research, not the macOS 27 gate.

**Reproduction/results:**

- Official `devicectl device info apps --require-container-access` found the already installed
  Lab. Scoped paired USB InstallationProxy lookup returned Lab 1.20.0 (514),
  ProfileValidated=true and get-task-allow=true. Calculator's returned dictionary lacks that
  key; installed signature bytes were not independently extracted. SwiftUIDemo also returned
  get-task-allow=true but was not launched or action-tested.
- Launch Lab, refresh its PID through OsTraceService, enable AX inspection, target that PID,
  use monitoring 0 and Next to obtain a matching gear-button focus. An initial selection
  attempt tapped the already focused gear under monitoring 2, received no second matching
  focus and stopped before any property/action request. Its cause is not isolated; 94 messages
  and cleanup decoded without errors. The following independent fresh-focus session succeeded.
- At PID 51300, the ten received read-only descriptors returned gear label/traits/input labels,
  Class=SwiftUI.AccessibilityNode, Address=0x1480f3200, nil Controller and a hierarchy containing
  the same control. No ordinary Frame descriptor. One received AXAction-2010 descriptor with
  null third argument and reply expectation was sent as request 18; its same-connection reply
  was type-0 empty OK. Screenshots before/after show Home changing to Settings. All 66 messages
  decoded without errors. This is semantic activation proof for that development-app control.
  It does not isolate a permission cause for the prior Calculator no-effect.
- Fetch the device's version-matched raw dyld files over a paired userspace RSD tunnel. The
  primary cache image UUIDs match the extracted AccessibilityAudit and libsystem_kernel.
  The missing branch island at 0x2500f90b0 in `.47` resolves to task_for_pid at 0x237ef7cb4;
  the complete `.54.dylddata` version-5 slide chain resolves the global cell to mach_task_self_
  at 0x2700b8078. The physical framework predicate is task_for_pid(self, pid, &task)==0.
  Concrete daemon callers/kernel policy are still unknown. Both read-only 27A5252f DDI image
  inventories and the cached symbols lack axauditd. A native Apple-tunnel RSD attempt reset
  and a lease-backed attempt timed out before handshake; the independent userspace path worked.
- An extra Apple Inspector reference remained at Connecting to target, with disabled target
  menu items. Its bounded native recorder retained four outgoing messages and no incoming
  messages, then detached successfully. No physical Lab selection/action was established.
  Inspector was closed and a direct cleanup captured 17 complete messages, both capability
  barriers and state clearing. No extra Apple Lab action was submitted.
- For a possible development-only native Frame path, two fresh focus sessions retained matching
  class/address (50/53 clean messages). Initial batch LLDB attachment did not produce a usable
  target; the later interactive attempt reported the old PID unavailable. Relaunch produced
  PID 51452/address 0x15b013840, with CoreDevice confirming that PID during attachment. The
  interactive attach/status then stalled; no class or Frame getter executed. The owned stalled
  LLDB was terminated, and a safe gear tap visibly opened Settings afterward, proving the app
  was responsive. This is an unverified debugger route, not a Frame denial. The current UIKit
  SDK's screen-coordinate accessibilityFrame declaration does not substitute for a device result.

**Cleanup/limits:** clear monitor/visuals/focus/preview/app monitoring/target/enable with capability
barriers; close owned sockets and Inspector, detach the native Apple tracer, end the stalled app
debugger, and detach both owned host DDI mounts. Close the Lab Settings sheet, check Calculator's
existing 7 without outlines and restore the original Home page. No production code, installation,
certificate, security setting or release-matrix smoke changed/ran.

Ad hoc probes, raw streams/caches, metadata, failed-attempt records and screenshots remain local at
`~/.local/state/ipb/20261009-13pro-handler/`; `handoff.md` maps captures to evidence boundaries.
Decisive sources are `lab-control-1791535376764185000/decoded.jsonl` (request/reply 18),
`permission-resolved.json`, `cache-image-identity.json`, `permission-function.txt`,
`permission-stub.txt`, `permission-target.txt` and the versioned cache manifests. The retained
2 MiB data prefix is explicitly incomplete; the full 225,280,000-byte cache was used for the
slide-chain check. See [current protocol](protocol.md#axaudit-development-app-action-and-resolved-task-port-predicate-2026-10-09)
for symbol addresses, UUIDs and source definitions. Raw data and success-only evidence are not committed.

## 2026-10-09 — 13 Pro physical axauditd handlers, permission logs and preview

**Scope/seed:** doctor again passed with no failures on macOS 26.5.1 (25F80), Xcode 27 B6 /
Inspector 192.6 / CoreDevice 642.15 / DDI 27A5252f, unlocked wired iPhone14,2 iOS 27.0
(24A437), UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`. Only the allocated 13 Pro was
operated. No Runner, installation, certificate or device security change. This is research;
no production code/build/release-matrix smoke was changed or run.

**Firmware source and extraction:** fetch BuildManifest/Restore and the exact OS ZIP member
from Apple's iPhone14,2 / 24A437 restore URL with bounded HTTP ranges. The member length and
central-directory CRC matched; the whole IPSW was not downloaded/hash-verified. ipsw 3.1.732
decrypted AEA, and isolated libfsapfs-python 20260921 extracted the target and SystemVersion
read-only from Rave24A437.D63OS. The standalone axauditd is 179,312 bytes, SHA256
`5278c0dc4dc62cc8801840e047381924a50cdae246abf67ec986522a6e66aec8`, arm64e UUID
`08B6FBF3-3EF9-34FD-B86F-8DCA4E4D6616`. It is the OS daemon, not a DDI/Simulator executable.
The tooling was isolated in the owned research directory on mounted CSVolume; native volume
mount attempts failed/stalled, their owned process was ended and the attached image detached.
The successful extraction used no mount or privilege change. Existing unrelated images stayed mounted.

**Decisive static findings:**

- The parameterized-property manager invokes completion(nil) directly. Ordinary reads use a
  finite name dispatcher with no geometry branch or generic native-attribute forwarding.
  The three developer-only ordinary names are ClassName, MemoryAddress and Controller;
  their task-port check and denied-nil branch are concrete. A different noncurrent element
  already in focus history is also filtered. Nondeveloper NSString/NSAttributedString results
  are truncated to 64 UTF-16 units. These limits have binary evidence, not new coverage tests.
- Actions check the same task-port predicate before native execution. The server discards
  the RPC value argument; denial, unknown action and attempted action converge on a void
  completion with nil result/error. Thus the earlier empty OK is not an outcome signal, and
  changing null/0 alone does not solve it. No action was replayed this round.
- Hierarchy builds a parent/context chain with permission-filtered parents and child collections
  capped at 51. Coordinate fetch uses backend 91701 with unchanged CGPoint and a 0.1 s cache;
  the actual iOS backend semantics/success remain unresolved.
- Preview consumes the native frame after refreshing attribute 2003 and draws frame/path/context.
  Neither inspected preview/renderer entry checks the developer predicate. Exact source
  addresses and source identities are condensed in the [protocol](protocol.md#axaudit-physical-daemon-handlers-permission-logs-and-element-preview-2026-10-09).

**Runtime reproduction/results:** use paired USB AccessibilityAudit plus daemon-PID-only
OsTrace syslog, pymobiledevice3 11.10.2. Refresh app PID, enable inspection, select the target,
use monitoring 0 and Next, then accept only an incoming focus token containing that PID.
Property reads reuse its received typed element/descriptors. No semantic action is sent.

- Calculator PID 51502 / History / SidebarButton returned Label=历史记录 and nil class/address/
  controller, while daemon focus logs explicitly reported allowDeveloperAttributes: NO.
  Live image_uuid and process_image_uuid both match the extracted daemon. The first session
  switched to Lab without app monitoring and got no matching focus; it stopped before Lab
  property reads (rc1), cleaned state and decoded 94 messages without stream errors.
- A separate fresh Lab session with app monitoring enabled received PID 51452's gear token,
  Class=SwiftUI.AccessibilityNode, Address=0x15b013840 and nil Controller. The same daemon
  explicitly logged YES. It completed rc0 with 39 decoded messages and no stream errors.
  This verifies the current predicate outcomes, not their underlying kernel/entitlement cause
  or which state change repaired the first selection attempt.
- A fresh Calculator session again matched History and NO. Capture baseline with visuals
  false, then ShowVisuals(true), Preview(received element), capability barrier and screenshot.
  The matching button was highlighted while 7 and the page stayed unchanged. Pixel differences
  above thresholds 8/16/32 all occupy [54,147,174,267) in 1170×2532 images: approximately
  (18,49,40,40) logical points at scale 3. This is raster overlay extent, not a returned
  CGRect/accessibilityFrame. No audit issue was used. This probe completed rc0 with 68
  decoded messages and no stream errors; it establishes one ordinary-node preview control.

**Cleanup/limits:** all three captures sent monitor 0, visuals false, focus nil, preview nil,
app monitoring false, target 0 and Inspector enable 0; each completed a 45-capability barrier
without cleanup errors and closed owned sockets. Final screenshots visually confirm no
Calculator outline, preserved 7 and the original Home page. No new LLDB/Inspector process or
owned filesystem mount remains. Dynamic pages, offscreen nodes, path/padding, rotation and
full-tree/native-rectangle coverage remain unverified.

Raw firmware/tools remain at `/Volumes/CSVolume/ipb-research/20261009-axaudit-daemon/`;
small sources/probes/captures remain at `~/.local/state/ipb/20261009-axaudit-daemon/`.
Local `handoff.md` maps member/build/hash metadata, annotated functions/fixups and the three
captures (`gate-log-1791542324353629000`, `gate-log-1791542548267708000`,
`gate-log-1791542591137522000`) to their boundaries. Raw logs, scripts, screenshots and
success-only evidence are not committed; historical dated records remain unchanged.


## 2026-10-09 — Bulk observation priority and screenshot-handler check (offline)

**User decision:** “耗时太久了吧，一个个来不知道要多久，没有更直接的方案吗”.
Retain the positive preview control as a single-target fallback; prioritize a device-side bulk
snapshot or a remote AX cache/data stream for page observation. No per-node timing benchmark
was run; the protocol's serial render/screenshot dependency alone does not supply a latency number.

**Static verification:** reread the extracted physical 24A437 daemon and existing Mac-local
Mirroring / DDI XCTest sources. `_deviceCaptureScreenshot` at 0x1000092f4 hides visuals and
passes CGRectZero to screenshotInfoForTransportWithFrame: at 0x100009354; it does not fetch the
current cursor rectangle. Mirroring's incoming AX data and translated host children have static
implementation evidence but unverified session/schema/external access. testmanagerd's direct
snapshot has concrete implementation and authorization gates; generic host handshakes previously
failed to establish that snapshot session. No new phone request, Mirroring launch, input,
installation, build or release smoke occurred in this offline follow-up.

Current upstream WDA source was also opened: the JSON source handler calls fb_tree, which takes
an application snapshot and recursively serializes rect/children. The official preinstalled-WDA
documentation still requires signing, and specifies RemoteXPC instead of devicectl launch on
current iOS 27. These are upstream source/documentation facts, not a local WDA device result.
Links and the revised research order are retained in [the current plan](devicehub-alignment.md#axaudit-capture-plan).

## 2026-10-09 — Mirroring bulk AX schema, Frame and physical producer (offline)

**Scope:** macOS 26.5.1 / 25F80, iPhone Mirroring 1.6 / 98.5; physical-side static sources
are iPhone14,2 / iOS 27.0 / 24A437. Read-only binary analysis and host-local synthetic codec
execution only. No device enumeration/connection/input, Mirroring launch, phone installation,
production build or supported-matrix smoke occurred.

**Resolved implementation:** the host handles type-11 tree responses with initial/additional/
destroyed data, caches multiple-attribute node responses, and exposes Frame 21. Original
physical APT metadata maps 21 to native attribute 2003 and includes it in both priority and
full attribute batches. Physical SSK starts AXPRemoteCacheManager, whose background generation
and initial/additional response callbacks are present. Full APT and SSK instruction sections
match the decrypted Apple SystemCryptex bytes, with matching image UUIDs in the retained
physical cache table. This establishes a shipped bulk producer and schema; it does not
establish full-page completeness or a current received rectangle.

**Remaining entry boundary:** original MainOS extraction identifies ScreenContinuityShell
2.0 / 114.56, its AngelServer session imports, Rapport event-handling strings and signed
accessibility/RemoteDisplay permissions. Physical metadata also resolves the local command-line
interface to ping/state/stop, with a remote-token entitlement check. That interface exposes no
tree method. Host HIServices independently checks remoteDeviceContent for external AX reads;
codesign distinguishes VoiceOver's entitlement from Inspector's inspection entitlement.
Neither finding closes independent network-session authentication.

**Codec check actually executed:** a native secure archive/unarchive of one synthetic node
preserves numeric attribute 21 and the deliberately chosen rectangle {{18,49},{40,40}}.
The retained output reports one node, 1,136 bytes and pass=YES. These values are synthetic;
no AX transport manager/session was instantiated and no phone bytes were decoded.

**Local references:** small probes, hashes, decoder metadata and disassembly are under
`~/.local/state/ipb/20261009-mirroring-ax/`; `handoff.md` maps them to the source and proof layer.
Apple images remain under `/Volumes/CSVolume/ipb-research/20261009-mirroring-ax/`.
Native SystemCryptex mounting failed with Permission denied; no owned attachment was left.
The successful decryption is in `cryptex/043-68607-705.dmg`; the earlier partial output outside
that directory is invalid and was not analyzed. The standalone Swift dump reported unresolved
cross-image pointers despite rc0; it was not accepted as a parsed result. Relevant fields and
method names were instead decoded from the original cache mappings with Apple's layout source.
Raw material and success-only evidence remain outside Git. Exact seeds, sources, addresses
and the revised discriminator are recorded in [the protocol](protocol.md#mirroring-bulk-ax-schema-frame-and-physical-server-2026-10-09).

## 2026-10-10 — Mirroring AX subscription and native envelope controls (offline)

**Scope:** host macOS 26.5.1 / 25F80, iPhone Mirroring 1.6 / 98.5; retained physical
sources are iPhone14,2 / iOS 27.0 / 24A437. Rechecked the current loaded host SSK/APT/
AccessibilitySharedSupport UUIDs and the ScreenContinuityUI SHA256 against the analyzed
sources. Phone instructions and witness pointers came from the previously validated Apple
SystemCryptex and matching DeviceSupport text. No device enumeration, phone connection/input,
Mirroring launch, installation, production build or supported-matrix smoke occurred.

**Resolved subscription:** physical consumer activation and optional-primitives checks precede
Bool handling. Its original-cache protocol descriptor/witness table resolves true to the
AXP server start body and false to stop. Setup assigns an optional primitives value; neither
the static assignment nor a codec control proves a live session supplied a non-nil value.
The underlying producer already identified on October 9 generates initial/incremental trees.
Exact addresses and source identities are in the [protocol follow-up](protocol.md#mirroring-ax-subscription-control-codec-and-host-trigger-2026-10-10).

**Host prerequisite:** original loaded instructions and bound import pointers resolve SSK's
initial query and notification-driven requery to AXSSHasClientsWithAccessRemoteDeviceContent,
plus its DidChange notification. The one host-local getter query returned false while iPhone
Mirroring was not running. Current ScreenContinuityUI separately checks server accessibility
capability (raw flag 0x2), starts state monitoring on success, guards AX-primitives creation
on the demand state, and sends/receives accessibility messages on its screen-sharing session.
This establishes normal-client triggers, not a new network authorization result or an
explanation for prior AXAudit replies. The annotation entitlement string is not a service ID.

**Native controls actually executed:** the final host-only Swift probe completed rc0 within
its 20-second alarm. Apple's actual AccessibilityMessage and ControlMessage Decodable/
Encodable implementations preserved five constructed dictionaries/data values: standalone
true, false and data; outer true; outer data carrying the October 9 synthetic archive.
The binary plist sizes were respectively 82, 82, 78, 105 and 1,245 bytes. Securely decoding
the last envelope's embedded AXP archive returned one synthetic node and the deliberately
chosen {{18,49},{40,40}} rectangle. The output explicitly marks no_session=true and
source=synthetic. No manager/session was instantiated and no phone packet was decoded.
This proves message nesting and codec compatibility, not transport framing or page coverage.

**Local references and limits:** probes, decoded metadata, annotated call sites, native
outputs and source identities are under `~/.local/state/ipb/20261010-mirroring-session/`;
its `handoff.md` maps the decisive sources and commands. Raw firmware remains in the October 9
locations. The early generic-vtable parser did not yield a valid AngelServer table; the exact
protocol witness table was resolved directly instead. Initial codec compilation/type lookup
attempts failed and were not counted; the corrected final run supplies the positive control.
Raw binaries, scripts, logs and synthetic archives remain outside Git. Next capture a genuine
configured session with positive host AX demand, device capability and consumer activation,
then correlate subscription, initial archive and incremental data while separately tracing
session authentication. Independent-client access and physical rectangles remain unverified.

## 2026-10-10 — 13 Pro Mirroring first-setup authentication (live)

**Scope:** macOS 26.5.1 / 25F80, Xcode 27 Beta 6 / 27A5252f, CoreDevice 642.15,
iPhone Mirroring 1.6 / 98.5; allocated wired iPhone14,2 / iOS 27.0 / 24A437,
CoreDevice UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`. Native onboarding initially
defaulted to the 15 Pro; that attempt was stopped and the Continuity picker explicitly
changed to the 13 Pro. Subsequent USB reads/logs and target-specific UI use only the 13 Pro.
The earlier default-target attempt is excluded from the 13 Pro evidence.

**Confirmed failure and progress:** the first 13 Pro `pairDeviceForMacUnlock()` hit is
followed by a phone Rapport pre-pairing event, then a host timeout with Sharing authentication
Code 12 / SSK RemoteAuthenticationError Code 3. The phone's 109-byte BLE response send occurs
after that failure. Following user-completed setup/unlock, the second native request produces
authentication enablement completion and `Unlock enabled` explicitly for iPhone14,2; onboarding
reaches Ready. Get Started then requires the Mac login. These distinguish first-setup enablement
from USB pairing and actual screen connection. The underlying Code 12 cause is unresolved;
the raw Lockdown `PasswordProtected=false` value persisted after the user reported a passcode
and is not treated as proof of a missing passcode. Exact timing and sources are condensed in
the [protocol](protocol.md#mirroring-first-setup-authentication-2026-10-10).

**AX proof limit:** all 13 host trace sites resolve and the target resumes. Only two pairing
request hits are recorded; no control-session, capability, demand/start or incoming AX-data
site hits, tap errors or captured AXP archives occur. A host-local demand getter returns false.
VoiceOver is not enabled: the user asked what it is, and a clarified temporary-activation
permission request remains pending. The existing synthetic archive decodes to one node and
its deliberately chosen rectangle; this remains a synthetic decoder control. No real page
tree, native element rectangle, full coverage or independent authenticated client is proven.

**Cleanup and local references:** the original passive phone syslog connection terminates
with a concrete ConnectionTerminatedError; its earlier entries remain valid, and a fresh
13 Pro log connection is opened without replaying any phone action. At the end, LLDB reports
detach `ok=True`, both active log collectors exit 0 and Mirroring remains running at the
Mac login prompt. No owned tracer/log process remains; VoiceOver was never changed. Raw logs,
stage markers, decoder, summary and restart instructions are under
`~/.local/state/ipb/20261010-mirroring-live/`, mapped by its local `handoff.md`. No authentication
credential/token contents were dumped. No production code, phone installation, production
build or supported macOS 27 smoke gate changed. Resume after manual Mac login and the pending
VoiceOver decision, refreshing PID, target identity and capture readiness before AX activation.

## 2026-10-10 — 13 Pro control session, VoiceOver permission and authentication broker (live)

**Scope and authorization:** macOS **26.5.1 / 25F80**, Xcode **27 B6 / 27A5252f**,
CoreDevice **642.15**, native Mirroring **1.6 / 98.5**, allocated **iPhone14,2 / iOS 27.0 /
24A437**, CoreDevice UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`, UDID
`00008110-0014711C3CC3801E`. The user confirms Mac login and explicitly permits temporary
VoiceOver activation/restoration. No further phone selection is changed.

**Screen/control result:** after login, native Mirroring says the iPhone is in use and must be
locked. A single targeted `bin/ipb -s <13-UUID> lock` completes; no sent HID action is replayed.
Five native unlock-stage hits are recorded between **10:53:34–10:56:13 CST**. Retries return
Sharing authentication Code 10 / `SFAuthenticationErrorCodeInternal`; its underlying cause is
not established. Nevertheless the native window later displays real 13 Pro Home and Settings
pages, including after subsequent attach/detach. The successful transition follows a detach,
but timing alone does not prove debugger causality.

At **10:53:48.744**, host logs receive server initialization: protocol **6**, iPhone build
**24A437**, capabilities **31**. At **10:53:48.997**, phone logs receive client startup:
protocol **3**, Mac build **25F80**, capabilities **7**, HID devices. Control stream ID is
`com.apple.oneness.sessionAndHIDMessages`; the phone's Rapport log identifies
`com.apple.MediaContinuityKit.iPhoneMirroring`, QUIC and ephemeral port **64150** in this
capture. These are genuine log records, not decoded packet framing. No host AX start/subscription
or incoming archive is captured. An ipb screenshot completes but inspection finds an all-black
1170×2532 image; it is not evidence of Home or a usable rectangle overlay reference. The native
window image is the positive UI observation. The black capture's cause is not established.

**Reproduced host AX blocker:** initial automation repeatedly leaves the VoiceOver Welcome/
Tutorial component active without a sustained main process. A clean Settings activation and
Return on Welcome starts the actual VoiceOver process. At **11:11:20.786**, Mirroring receives
VoiceOver PID **53389** with `_setMachPortAccessStatus` flags **1/1/1/0** (ordinary access,
protected content, inspection, remote content). At **11:14:03.976–.993**, a fresh VoiceOver
PID **54576** reproduces this and captures the remote entitlement lookup returning **1**, then
its effective value **0**. The identification override, current-request identification and
Apple-internal-build flag read **0** inside Mirroring; the PC-derived slide is **0x1E58000**.
Source identities, exact checks and the 7–10 identification condition are in
[protocol.md](protocol.md#mirroring-live-control-session-and-host-ax-permission-failure-2026-10-10).
Why the current identification is zero remains open. Do not infer that VoiceOver lacks the
entitlement, ordinary TCC access failed, or all iOS tree routes are impossible.

**Scope correction:** HIServices' demand getter counts the calling process's AX connection
cache and posts locally. Earlier external Python false values are not Mirroring demand or a
machine-wide VoiceOver state. A one-off attempted in-process getter expression in session4
fails with EXC_BAD_ACCESS and is unwound; it supplies no value. Subsequent captures use only
passive taps. Session7's auxiliary context-address calculation is superseded by session8's
validated PC-derived calculation; the entitlement/effective-value taps agree in both.

**Independent-client discriminator:** selected Sharing.framework code links SFAuthenticationManager
through SFCompanionXPCManager to SDUnlockXPCSession; sharingd checks the caller's private
`com.apple.private.sharing.unlock-manager` entitlement before enablement/authentication.
A locally compiled probe with no private entitlement obtains the factory connection, then
`eligibleAutoUnlockDevicesWithCompletionHandler:` returns **SFAutoUnlockErrorDomain / 111 /
no permission**. Probe rc0 means the denied callback was collected, not authentication success.
No enablement/unlock, credential extraction, token dump/replay or security-policy change occurs.
This is a runtime denial of the tested broker, not a complete independent network-client test.

**Cleanup, limits and local references:** all session2–session8 LLDB captures report detach
`ok=True`; owned host/phone collectors are closed. Session2's phone collector terminates with
ConnectionTerminatedError (earlier records retained); later collectors close normally. VoiceOver
is restored **off**, verified by Settings and absence of both VoiceOver and Quickstart processes.
Mirroring remains alive and displays Settings after detach. No actual AX archive/element bounds,
full tree coverage or independent authenticated network session is proven. Next compare the
normal identification setup/check ordering on this host and the supported macOS 27 host.

Raw captures/probes remain outside Git at `~/.local/state/ipb/20261010-mirroring-live/session2/`
through `session8/`; the root `handoff.md` maps them. Decisive references: session2 phone/host
logs, session6 and session8 `host-trace.jsonl`, session5 sharingd disassembly/signature metadata,
session8 source identities, selector resolution and `auth-broker-readonly.jsonl`. The existing
synthetic decoder remains only a control. Only research documentation changes; no production
code, phone installation, production build or macOS 27 smoke gate is claimed.

## 2026-10-10 — Mirroring client ID 7 arrives after permission check; macOS 27 static comparison

**Scope:** the same allocated **13 Pro / iPhone14,2 / iOS 27.0 / 24A437**, CoreDevice UUID
`7F2FE6E9-5423-552A-A2A2-C499F1D8672F`, UDID `00008110-0014711C3CC3801E`, remains on the local
macOS **26.5.1 / 25F80** host. Xcode **27 B6 / 27A5252f**, CoreDevice **642.15**, native Mirroring
**1.6 / 98.5**, PID **84730**. The existing temporary VoiceOver authorization is reused and
restored. A USB logger asserts the exact UDID/model/build before collecting. No other phone,
credential entry, phone installation or security-policy change is involved.

**Reachable trigger and reproduction:** with native 13 Pro Mirroring displaying Settings,
enable VoiceOver through Settings and press Return on the real Welcome window. Actual VoiceOver
PID **62094** starts; passive, UUID-checked taps observe ordinary `CopyAttributeValue` requests.
At **11:27:09.520–.575 CST**, on one Mirroring thread and connection port **126671**:

| Stage | Incoming ID | Current ID | Decisive result |
| --- | --- | --- | --- |
| MIG function entry | 7 | 0 | Peer PID matches actual VoiceOver. |
| Permission precheck | 7 | 0 | Override/internal-build flag are also 0. |
| Remote entitlement lookup/filter | 7 | 0 | Lookup 1 becomes effective 0; access flags are 1/1/1/0. |
| Post-identification store | 7 | 7 | Store happens after permission calculation. |
| Common epilogue | — | 0 | Current identification is reset. |

The ninth-argument stack offset is established by the shipped function prologue and load,
not inferred from a coincidental 7. Static addresses/UUIDs are recorded in the
[protocol follow-up](protocol.md#mirroring-client-identification-ordering-and-macos-27-comparison-2026-10-10).
A second activation, VoiceOver PID **63357** / port **194111**, reproduces lookup 1 → effective 0
at **11:29:51.501–.546**. A short follow-up keeps that process active and filters taps by its
audit-token PID before applying the hit budget: **20** valid cache-path hits read **0x0E**, and
**19** valid post-store hits read current ID **7** with remote-content backing byte **0**.
Thus the normal attribute path's initialization timing and retained missing permission are
established. This is not proof that all alternate Apple initialization paths are equivalent.

**Observed page/data result:** Home changes the genuine mirrored Settings page to the 13 Pro
Home screen, visibly including the development Lab app. Saved native-window pixels are usable;
the ordinary Mac AX tree still contains only window, toolbar and menu elements. No host AX
start, outgoing subscription or incoming data hit occurs in the full first capture; no AXP
archive is captured in any of these runs. Full phone tree and native rectangle export remain
unreceived. The existing synthetic tree/rectangle is not promoted to physical evidence.

**macOS 27 comparison:** a read-only agent inventory (`来源：peer`), independently checked
against its raw binary outputs and main-session SSH refresh, reaches **Mac-M2 /
HBs-Mac-mini.local / macOS 27.2 / 26B5091g**. HIServices UUID is
**39A43728-ADF4-3FC1-A946-0466C3E72BBA**, Mirroring **2.0 / 126.8** UUID
**C23F483F-F100-3D40-BA21-E952F144D580**. Its ordinary attribute route likewise checks at
`0x1926C3E48`, then stores identification at `0x1926C3E64`, then clears it at `0x1926C4090`;
the 7–10/internal-build filter remains. AX demand/start/stop/data interfaces also remain in
ScreenSharingKit and embedded ScreenContinuityUI. Their direct import/dlsym inventories show
no identification-override reference, which does not exclude indirect framework calls.

The main refresh corrects an inventory inference: selected `/Applications/Xcode.app` is
**Xcode 26.4 / 17E192**; only that Xcode app is found by `/Applications/Xcode*.app`. CoreDevice
does not enumerate this 13 Pro and no native Mirroring/VoiceOver process is running there.
This is not a native-Mirroring discovery denial or proof it requires CoreDevice: no normal
13 Pro authentication/GUI session was attempted on Mac-M2. A user question about connecting
the same phone and completing native login is pending. Static comparison does not close the
supported release or newer-host runtime gate.

**Cleanup and evidence quality:** all three owned LLDB sessions detach `ok=True`; the first
host and phone log collectors close with rc0. Settings shows VoiceOver **off**, and neither
VoiceOver nor Quickstart remains. Mirroring remains alive. Breakpoints shed when their bounded
hit budget is reached; missing later hits do not establish unlimited-duration inactivity.
Two auxiliary context events have a PC slide inconsistent with the checked module and are
excluded (session2 seq45, session3 seq34); decisive same-thread sequences and peer-filtered
cache results use the matching **0x1E58000** slide. No production code/build/smoke gate changes.

Raw probes/logs/window image and the local handoff remain outside Git at
`~/.local/state/ipb/20261010-client-id/`: `session1/host-trace.jsonl`, `session2/host-trace.jsonl`,
`session3/host-trace.jsonl`, `session1/mirroring-home.png`, `capture-summary.json`,
`mac27/hiservices-targets.txt`, the selected framework inventories, and
`mac27/current-host-prerequisites.txt`. The local handoff maps readiness, restoration and
the still-pending newer-host session prerequisite.


## 2026-10-10 — Mac-M2 USB identity and native Mirroring account prerequisite

**Scope and access:** after the user moves the allocated 13 Pro and confirms USB trust,
SSH reaches **Mac-M2 / HBs-Mac-mini.local / macOS 27.2 / 26B5091g** as console user `hb`.
The user requests **“用 rustdesk 或者 ssh 链接吧”**. RustDesk's connected remote window
visibly shows that host; no Screen Sharing login is needed for the remaining work.

**Device identity and separate tool state:** IORegistry USB serial
`000081100014711C3CC3801E` matches the allocated 13 Pro's UDID without separators.
CoreDevice UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`, model `iPhone14,2` and ECID
`5753865626681374` also match. The inventory reports `pairingState=unsupported`,
`tunnelState=unavailable`, booted, and `ddiServicesAvailable=false`. This supersedes the
pre-transfer absence recorded above. It does not prove that USB trust was omitted or that
CoreDevice depends on the same Apple Account.

Selected `/Applications/Xcode.app` reports **Xcode 26.4 / 17E192**, while its `devicectl`
reports **642.15** and `xcrun lldb` reports **2100.0.16.4 / Swift 6.3.0.123.5**. Enumeration
also prints package installation notices ending **“Authorization is required to install the
packages.”** No installation or developer-selection change is made. The mixed installation's
service readiness and the Xcode 27 release gate remain unconfirmed. `--json-output -` includes
notice text before JSON on this host; the initially failed JSON parse is a probe-format issue,
not evidence of missing device enumeration. The retained filtered JSON is parsed after the
first object delimiter.

**Native target/account prerequisite:** SSH launches the native Mirroring app, PID **39768**.
The RustDesk image shows its default target **“Enter 的 iPhone”** and an iOS-version error.
No retry or operation is sent to that other phone; its error is excluded from 13 Pro results.
An ordinary, read-only AX probe against PID 39768 returns **`AX trusted=0`** and window-read
error **-25211**. RustDesk's computer-use app access times out, so target selection is requested
from the user rather than assumed to have succeeded. The user then observes that Mirroring
requires the same account. [Apple's current requirements](https://support.apple.com/en-eg/120421)
confirm the same Apple Account with two-factor authentication on both devices. USB trust,
SSH and RustDesk access do not replace this native session requirement. Account identifiers
are not read, no mismatch is independently measured and no account is changed.

**Capture/result boundary:** passive macOS 27 taps are prepared with framework UUID checks,
module-derived slides, exact-PC guards, VoiceOver-peer filtering and bounded hit budgets.
They cover HIServices permission order/cache, ScreenSharingKit's typed AX start/stop/data
protocol thunks and AXP host cache methods. They are **not started**: there is no authenticated
13 Pro native session to compare. Protocol thunks are interface taps, not resolved concrete
implementation bodies. No physical AXP archive, complete page tree or element rectangle is
received on macOS 27. VoiceOver was not enabled there and no owned remote collector is running;
local VoiceOver and the earlier owned captures remain restored/closed. Native Mirroring is
left open for user-controlled setup. No credentials, entitlements or security policy are changed.

Raw tools and the local handoff stay outside Git under
`~/.local/state/ipb/20261010-client-id/`: `mac27/target-after-connect.json`,
`mac27/target-usb-serial.txt`, `mac27/devices-after-connect-raw.txt`,
`mac27/remote-mirroring-ax-read.txt`, `mac27/capture1/`, and `handoff.md`.
Only condensed research documentation is changed; no production build, installation or
macOS 27 smoke gate is claimed.


## 2026-10-10 — Independent AX research direction reviews and arbitration

**Scope:** the user requests several different AI opinions. The common evidence packet is
based on `6438415`, including numbered protocol/state excerpts and the first genuine
VoiceOver identification trace. Each reviewer receives the same packet without the other
reviews. GPT-6 Astra additionally reads raw traces and selected disassembly; Claude and
DeepSeek inspect only the packet. All recommendations below are **source: peer**, accepted
only within their stated evidence scope. No phone, SSH, VoiceOver or LLDB operation occurs.

**Completed reviews and provenance:** GPT-6 Astra returns a completed independent review.
Claude CLI completes successfully when requested as `claude-opus-5-5`, but its usage records
zero output tokens for that model and the main generation under `claude-opus-4-8`; this is
not represented as a pure Opus 5.5 review. DeepSeek's configured Responses endpoint returns
HTTP 200, `response.completed`, completed status and model `deepseek-flash`. Grok provides no
answer and its configured discovery endpoint returns HTTP 401; it is not counted. Two DSH
adapter failures also produce no opinion. No global model settings or credentials are changed.

**Accepted direction and main-session arbitration:** all three valid reviews preserve the
gap between a physical tree producer/Frame schema and an independently reachable USB session.
Astra identifies normal initialization, including `_loadAccessibilityBundles` after the
identification store, as a concrete static lead. Main-session rechecking confirms that order
at macOS 27 HIServices `0x1926C3E64` / `0x1926C3EAC`; its cache effect is unverified.
Claude emphasizes the separation of ordinary property requests from bulk receiving. That
separation is retained, but the stronger suggestion that client identification is unrelated
to bulk startup is not established: the resolved ScreenSharingKit calls reach the AXSS
demand getter, which calls HIServices `_activeRemoteDeviceContentConnections`; it scans
`_gPortAccessStatusCache` and reads remote bit 4 at local `0x187BB6C48`.
`_setMachPortAccessStatus` forms bit `0x10` at `0x187BB7268–7274` and the first nonzero active
count triggers a demand-change notification at `0x187BB7320`. Thus the default demand path
depends on the permission cache. This does not prove the sole root cause, exclude another
normal initialization route, or make permission success sufficient for an incoming archive.

The revised plan first maps identification/override writers, permission callers and cache
lifecycle, while tracing phone producer creation/activation back to transport, listener and
authorization. Unknown indirect dispatch stays unknown. A grounded initialization lead can
then justify two bounded legitimate startup-order controls, following one peer/port through
permission, demand, capability, subscription and real archive reception. Missing direct USB
callers is not proof of impossibility; a testmanagerd policy predicate alone is not proof of
a Runner-free snapshot session. AXAudit single-target preview and backend 91701 remain
secondary, preserving the user's rejection of page-wide serial preview due to latency.

**Result and retained evidence:** the plan and living open-item state are updated; no new
usable service, physical tree or element rectangle is proven. Raw reviews and the main
arbitration remain outside Git at `~/.local/state/ipb/20261010-ax-multimodel/`:
`shared-brief.txt`, `packet.json`, `consultation-manifest.json`, `astra-reviewed-notes.md`
(main-session condensation), `opus55-stdout.txt`, `opus55-review.md`,
`deepseek-api-result.json`, `deepseek-review.md`, and `merged-review.md`.
Rechecked static sources remain under `~/.local/state/ipb/20261010-mirroring-session/`
(`host-activation-calls.json`), `20261009-mirroring-ax/` (`axss-disassembly.txt`,
`hiservices-disassembly.txt`) and `20261010-client-id/mac27/` (`hiservices-targets.txt`).
All owned consultation jobs are closed. Documentation-only checks do not close the supported
macOS 27 real-device smoke gate.


## 2026-10-11 — AX consumer installation, transport providers and normal bundle loading

**Scope/source control:** offline follow-up to the user's request to continue toward a tree
and native element bounds without XCTest or a phone server. Local host is **macOS 26.5.1 /
25F80**. The phone source is the already retained **iPhone14,2 / iOS 27.0 / 24A437**
ScreenSharingKit, UUID **6AA674A8-B0DC-3B87-AF55-B92FE8DE286B**. Its entire 2,530,132-byte
`__text` is compared again with the complete Apple SystemCryptex image on the mounted external
volume: exact byte match, SHA-256
`e00b0045ea82c5030e8035cf206fc4e283a7cd705542b137dca3b46e084a80b8`.
Code can therefore use the DeviceSupport copy, while descriptors, type references,
conformances and literal addresses are read from the original cache. The partial sibling DMG,
rewritten metadata, unresolved exports and zero-initialized vtable/field offsets are excluded.

**Phone construction result:** the original source literal identifies
`SceneInteractorBackedContinuitySession.initializePlaybackServer(using:)`. Its async chain
creates `ProxyingAccessibilityMessageConsumer`, supplies the primitives, and wraps it in
`NotifyingPlaybackEventConsumer` with the verified `PlaybackEventConsuming` witness. Main
rechecking follows that wrapper and `ControlMessageSession` into a newly allocated object
whose original accessor/descriptor identifies **PlaybackServer**. This establishes actual
installation rather than merely a nearby class name. Numeric runtime field offsets and exact
reflected property-to-offset names are not recovered. A parallel AX constructor is confirmed,
but its enclosing owner remains unresolved; the nearby client-status consumer is a different
type. This extends the prior Bool-to-AXP start/stop trace without proving runtime activation.

**Transport boundary:** the session's original type reference resolves
`TransportProvidingContinuityServerSession`; the control session resolves `ControlTransport`.
All 1,069 ScreenSharingKit conformance records are scanned with no parse errors. They identify
two concrete session/control families: **MediaTransportServerSession /
MediaTransportControlStream**, with explicit **RPRemoteDisplaySession / RPStreamSession**
fields, and **MCKBackedContinuityServerSession / MCKControlStreamBackedControlTransport**,
whose references resolve to **MediaContinuityKit.MediaContinuitySession / ControlStream**.
`MockControlMessageStream` is not a production-access proof. This single-image result does
not establish which provider ran on the phone, any normal host entry, authorization success,
an independently reachable stream, or the absence of an external/USB implementation.

**Normal Mac initialization controls:** two read-only inventories are delegated to
GPT-6 Luna (**source: peer**); the main session rechecks decisive raw code and extends the
server-installation proof above. Among 19 direct HIServices permission-helper routes,
18 store incoming identification after the check; `PostKeyEvent` has no incoming-ID store.
The AccessibilityBundles required/full token loaders (UUID
**15AB226A-3C61-305A-AF55-616D941D746D**) perform normal image-callback/bundle loading and
`forceBundleLoad` / `mayNeedBundleLoad` checks, with no direct HIServices ID/cache writer in
their inspected bodies. CoreAccessibility/AppKitAdditions registers safe categories. A live
AppKit image inventory (UUID **CF57A4FC-4BE3-3D95-B543-D744E8718B26**) resolves 4,812 of 4,815
auth stubs, including ordinary AX imports, but no identification-override/remote-content
import. Unresolved or indirect calls and effects of subsequently loaded bundles remain open.
The native `AXEnhancedUserInterface` constant is checked directly; the handler's demand
notification still requires remote permission already set. These controls provide no new
normal cache-repair route and do not prove every possible route equivalent.

**Result/next discriminator:** continue at the two providers' constructors, listener policy
and normal session acceptance, retaining authentication boundaries and checking any usable
lead on the allocated 13 Pro. The [protocol section](protocol.md#mirroring-ax-consumer-installation-and-transport-providers-2026-10-11)
records decisive addresses. A genuine initial archive with native bounds, coverage/lifetime
and computer-only access is still required. No phone, SSH, GUI or VoiceOver operation is run;
no production code, forced identification, permission-cache writes or entitlement changes
are made. No physical AX archive or native rectangle is received. This is a documentation
and static-analysis result, not a build/install/smoke or newer-host runtime pass.

Raw scripts and evidence stay outside Git in `~/.local/state/ipb/20261011-ax-init/`:
`ssk-source-control.json`, `verified-session-literals.json`, `consumer-conformances.json`,
the `0x2a1953b8c.txt` construction body, `session-transport-typerefs.json`,
`transport-conformances.json`, `transport-reflection.json`, `mck-typerefs.json`,
`his-gate-store-order.json`, selected bundle disassembly/image inventories,
`appkit-direct-call-inventory.json`, `his-enhanced-ui-constant.json`, and `handoff.md`.
The original source is
`/Volumes/CSVolume/ipb-research/20261009-mirroring-ax/cryptex/043-68607-705.dmg`.

## 2026-10-11 — Normal Rapport entry, MCK discovery and native loader preflight

**Scope:** pursue legitimate computer-side establishment before another AX subscription
capture. Local host is macOS **26.5.1 / 25F80**; authorized SSH reaches Mac-M2 on **27.2 /
26B5091g**. The allocated target remains the **13 Pro**, UUID
**7F2FE6E9-5423-552A-A2A2-C499F1D8672F**, iOS **27.0 / 24A437**. No fresh phone session,
phone input, account inspection, credentials/token access or security-setting change occurs.
Ordinary discovery does not operate another enumerated phone.

**Normal Rapport restriction:** own unentitled `RPRemoteDisplayDiscovery` probes on both
hosts return **RPErrorDomain -71168**, missing **com.apple.RemoteDisplay**, before discovery
or session creation. Each returns nonzero; it is not a timeout or an old-host-only result.
The tested broker and direct discovery API remain distinct authorization boundaries.

**Mac-M2 MCK controls:** loaded MCK UUID **5DC6E4AD-E3CE-3505-AABE-9FB830B3ABA2** and
Network UUID **17692953-4248-35A0-A0DC-12685F10E308** are recorded from the current images.
Native enum metadata/value witnesses verify iPhoneMirroring case 5, size 33/stride 36.
The actual native endpoint initializer and Codable encoder, using the synthetic ID
`ipb-own-process-control`, return application service
**com.apple.MediaContinuityKit.iPhoneMirroring**. Native factories return UDP browser/listener
parameters; native listener scope matches personal=2. Browser options independently match
personal=1 and iPhone=1, with RSSI -70 and no device filter/custom service/predicate.
The two scope types use different numeric representations. These isolated factory controls
start no listener; the actual control stack and later own-server activation are separate below.
Main's native endpoint-field inventory resolves only applicationService in EndpointType,
with version/type and applicationServiceName/deviceID coding keys. A wired-availability
field in the migration manager does not establish a direct USB or host/port entry.

A public applicationService descriptor control and a separate native
applicationServiceWithOptions control using the unchanged MCK factory options both reach
**ready**. Each observes zero endpoints for a bounded five seconds, then **cancelled**;
the final process exits 0. This validates configuration/ordinary discovery startup, not
authentication, 13 Pro visibility, a control channel or AX response. No endpoint is connected.
Account eligibility, phone advertising/provider selection, proximity and other causes of the
empty interval remain unseparated. The local macOS 26 export inventory lacks these new
factories; its preflight stops before their invocation. Bench ABI controls expose and repair
an initial wrong direct-return declaration for resilient Scope; the native getter writes its
result indirectly. That own-process probe failure is not a phone policy denial.

**Original phone source:** MCK UUID **9A3DABAB-BE8D-3581-9FB4-CEFE77D9CA4C** and Network
UUID **9EFD671C-0044-395F-9770-7DAAF06EB31B** match retained DeviceSupport code. Main rechecking
uses original cache bytes for branch islands, strings and parameter/port flow. The full
22,335,440-byte Network text is also byte-equal to the original. The control listener's name
builder uses the canonical prefix/name when shouldAdvertise is true, and adds `.` plus UUID
when false. Main descriptor/field rechecking corrects a listener-owner conflation: the
secure-UDP parameter factory and async zero-port NWListener constructor belong to
NetworkBackedMediaConnectionPrerequisitesProvider. Its useLLW0Interface field, not
shouldAdvertise, controls duplicate-state-update configuration. These
facts do not prove which provider is chosen, service advertisement, accepted-peer identity,
authorization or ControlStream construction. Two GPT-6 Luna read-only inventories
(**source: peer**) help localize callbacks and a dynamic entitlement-key path; main checks
decisive instructions/targets. No key literal or Mirroring-listener gate follows from the
generic `Failed entitlement check` string. The [protocol section](protocol.md#normal-mirroring-transport-entry-and-mck-discovery-2026-10-11)
keeps exact addresses and seed distinctions.

**Native method resolution:** a bounded own-process Mac-M2 metadata probe, with no objects,
network or sessions, resolves MediaContinuitySession.activate and makeControlStream plus
MediaContinuityServer.activate from their class dispatch slots and native async descriptors.
Current exported thunks independently confirm the slot offsets. The actual implementation
targets replace ambiguous optimized static descriptor pointers; this metadata control invokes
no method. The server-only control invokes neither Session method; the subsequent separate
synthetic Session activation is recorded below. makeControlStream remains uninvoked.

**Actual control stack and own-server startup:** native control-listener metadata, exact
Network export resolution and reflection agree on **PropertyList3<SessionMessage> →
ApplicationServiceQUIC → IP**, with servicePrefixing=false and native personal scope on
Mac-M2. The isolated UDP factories above and original phone media listener do not establish
this stack. The installed state handler/CheckedContinuation is a readiness path; its exact
ready branch and accepted-connection callback remain unverified.
Two normal, bounded arm64 own-process Server.activate runs, using iPhoneMirroring,
shouldAdvertise=false and a framework-generated UUID service, return typed
**NetworkBackedControlConnectionListener.Errors.missingDeviceID**, bench exit 5. Observed
server/control state is interrupted, optional Network.Listener5 is nil, and native invalidate
completes with the listener still nil. No ActivationResult or peer/device connection follows.
Earlier own-fixture loader/PAC failures occur before Server construction and are repaired by
loading the shipped framework normally in the own process and using matching ordinary arm64
bench objects. These fixture failures are not product or device policy findings.

**Missing-ID source and initialization controls:** exact bootstrap instructions and IDS
export resolution identify **IDSCopyLocalDeviceUniqueID**, the host's IDS identifier. The
import exists on Mac-M2 but a separate normal getter returns nil, retaining only presence.
Current IDS UUID **7D6637BC-2D2D-36BF-BFE0-4C7746E1D2D1** getter reaches
IDSDaemonController.blockUntilConnected and then listener.deviceIdentifier on the internal
queue. The early isNonUIInstall predicate is **false**. Own normal CLI state reads
**isConnected=false, isConnecting=true, remoteObjectExists=true**, with a non-nil
IDSDaemonListener. A five-second run-loop control and a separate normal LaunchServices GUI
control retain nil ID and those same state Bools; console and SSH UIDs both equal 501.
The same ordinary unentitled CLI on local macOS 26 reports non-nil ID, isConnected=true,
isConnecting=false. This is a comparison control, not supported-release validation or proof
that macOS 27 has no policy gate. Native connectionComplete:withResponse: and its call to
setupCompleteWithInfo: are located; callback completion, daemon policy, initialization and
account eligibility remain unseparated. Source: peer GPT-6 Luna localizes state branches;
main independently checks the critical method/selector/import targets. No host IDS identifier
value or account inventory is printed or retained. Native identityservicesd is running;
neither the own GUI probe nor own MCK activation process remains active afterward.

**IDS initial grant discriminator:** an own-process, sync-only XPC interposer preserves
original requests/returns and observes only service name, object type, timing and two static
protocol fields' presence/Bools. It reads no setupInfo contents or account/identity values.
Both hosts return a dictionary from **com.apple.identityservicesd.desktop.auth** promptly:
the final macOS 27 observation is **0.238 ms**, local macOS 26 **0.356 ms**. setupInfo is
absent on both. The **granted** field is present with native Bool type, **false on Mac-M2**
and **true locally**. The observed ID/state remains consistent with the normal uninterposed
controls. Exact native code reads those keys and inverts granted before its continuation;
no request is synthesized or replayed. A synchronous-XPC-hang explanation is excluded for
these calls; the service-side cause is established by the later uninterposed control below,
while later completion behavior remains unverified.
The observation applies to instrumented own probes, not native Mirroring or the phone.
Failed initial interposer fixtures are excluded from protocol evidence; the final MRC
sync-only control preserves the XPC returned object's native ownership convention.

**Daemon policy and actual execution:** the current shipped identityservicesd executable has
slice UUIDs **38332636-ADA2-39DE-8E7C-CDE364838059** and
**8C98537D-B8A7-3E1E-91D0-714CA62D7F39**. Source: peer GPT-6 Luna extracts both slices;
main independently resolves the first-slice callback, imports, selector and decisive branches.
Both slices' callback first checks audit-token IDS entitlements, then on the no-entitlement
path tests **IDS/EnforceFirstPartyListeners** and a code-sign-status classifier. Main resolves
the grant-handler indirect call's exact callback selector using its native chained pointer,
without guessing an unnamed handler's method name. Normal own read-only feature/classifier
controls report that feature **true on Mac-M2 / false locally**, and both own binaries fail
the native mask comparisons; RejectDataSeparatedClients is true on both. No feature override,
entitlement/signing change or signing/account identifier query is performed.

A fresh **uninterposed** Mac-M2 normal getter/state probe, PID **69622**, returns nil ID,
isConnected=false and isConnecting=true. A daemon log query restricted to this PID and the
known first-party-enforcement prefix finds **one rejection event, zero allow events**,
selecting the static `REJECTING 3rd-party caller with no entitlements` branch. Only these
counts and branch Bools are retained, not full messages or identity/service values. This
establishes actual rejection of this normal client by the first-party policy and closes
the service-side cause for the tested IDS-dependent bootstrap. The running daemon slice
is not measured, but both saved slices contain the same mechanism. This is not an
authentication result, phone denial or global independent-client impossibility result;
the subsequent outgoing Session control and legitimate broker/other provider paths are separate.

**Outgoing Session discriminator:** the normal constructor succeeds with inactive state,
NetworkBackedControlConnectionVendor, nil connection and nil migration manager. Exact native
initializer demangling corrects a peer's clientDeviceID reading to **clientSessionID**.
Main also identifies the previously unresolved `0x29748C2E8` call as a Logger value-witness
copy, excluding it as a vendor edge. Main native offset controls and original code instead
connect activation through the connection-vending helper and its closure to `0x2974A5F10`.
Exact Network exports resolve ApplicationService Browser2/options/results, the selected
endpoint's deviceID comparison, the PropertyList3/ApplicationServiceQUIC/IP configuration
and Connection3.init(to:using:). See protocol.md for exact addresses and seed.

A bounded normal own Session.activate with a synthetic endpoint ID and nil incoming media
configurations returns **MediaContinuityKit.TaskTimeoutError.timedOut**, bench exit 5,
after **10,253.224 ms**, with interrupted state. Native invalidate completes normally.
The event stream's native metadata reports size/alignment 8/8; its indirect async return
convention is verified before the opaque bench declaration is invoked. The log's
`synthetic_device_filter` caption describes final endpoint-ID selection, not proof that the
NWBrowser options contain a deviceFilter. No real device can match that synthetic endpoint,
and no makeControlStream, peer acceptance or phone action occurs. This excludes an immediate
missingDeviceID outcome for this run; it does not prove successful discovery, authentication,
the absence of lower-layer policy, or a replacement for native Mirroring's selected provider.
Earlier speculative vendor-witness metadata preflights are not used as call-target evidence;
their storage-format failures belong to the own fixture, not the device protocol.

**Native AX capture preflight:** local Mirroring PID 37962 remains at manual Mac login.
Normal dlopen of an own bench dylib is denied outside its sandbox; inside its native temp
directory the first arm64 build is rejected, and the corrected arm64e build is rejected
because the platform process cannot map this non-platform library. All handles remain nil;
the AX publisher/send functions never run. Passive UUID-guarded taps record setup only and
detach normally. Both own temporary dylib copies are removed from the app container, targets
resume, and owned LLDB jobs are closed. Native enum codecs and a synthetic AXP archive/frame
decoder pass only local controls. VoiceOver remains off. The Mac becomes AX-readable again,
but the native window still asks for the user's login; the existing handoff remains pending.
The later normal CUA state request reports the Mac locked and cannot read the app surface;
no automatic unlock or input follows. Static/own-process work continues independently.

**Result:** no physical AX archive, native rectangle, tree completeness or latency result.
Next determine the actual phone service publication/name and native listener/provider roles,
including how endpoints are exchanged, followed by legitimate broker/alternate access and
accepted connection → control stream, retaining native scope
and legitimate authorization. No production code changes;
documentation checks do not close the macOS 27 product smoke gate.

Ad hoc code/raw output stays outside Git in `~/.local/state/ipb/20261011-provider/`:
`rapport-discovery-probe.log`, `rapport-discovery-macos27.log`, native loader preflight logs,
`native-session-taps.jsonl`, `mck-native-controls-macos27.log`,
`mck-native-browser-macos27.log`, image UUID/metadata controls, original listener/name/stub
controls, `mck-method-metadata-macos27.json`, actual listener/config/QUIC disassembly and exact
import controls, `mck-server-activation-macos27-observed.log`,
`ids-local-id-presence-macos27.log`, `ids-environment-presence-macos27.log`,
`ids-connection-runloop-macos27.log`, `ids-connection-gui-macos27.log`,
`ids-connection-presence-macos26.log`, `ids-xpc-grant-presence-macos27.log`,
`ids-xpc-grant-presence-macos26.log`, IDS getter/connection/callback disassembly and metadata,
`ids-feature-classifier-presence-macos27.log`, `ids-feature-classifier-presence-macos26.log`,
`ids-daemon-policy-context-macos27.log`, `ids-daemon-policy-branch-counts-macos27.json`,
daemon executable/slice disassembly, main import/selector metadata,
mck-session-constructor-macos27.log, mck-session-activation-synthetic-macos27.log,
mck-session-offset-variables-macos27.json, mck-endpoint-offset-variables-macos27.json,
mck-session-connection-vending-main.txt, mck-session-vend-dispatch-main.txt,
mck-session-outgoing-bootstrap-main.txt, mck-outgoing-imports-macos27-checked.json,
outgoing stack/connection disassembly,
synthetic decoder output, peer reports and
`handoff.md`. Remote own probes remain
in `/Users/hb/.local/state/ipb/20261011-provider/`; owned capture, probe and listener processes have exited.

## 2026-10-11 — Native MCK client alignment, phone server sequencing and browser policy control

**Scope:** documentation/static research and bounded normal own-process controls on Mac-M2
(macOS 27.2 / 26B5091g, mixed Xcode 26.4 / devicectl 642.15). Phone code is from the original
iOS 27.0 / 24A437 cache matching the allocated iPhone 13 Pro (iPhone14,2, CoreDevice UUID
7F2FE6E9-5423-552A-A2A2-C499F1D8672F). No phone operation or authenticated session occurs.
The protocol section records original paths, image UUIDs, exact exports and call sites.

**Static corrections and findings:** exact macOS 27 SSK imports resolve native MCK client
endpoint construction, Session.init(usage:endpoint:clientSessionID:) with nil UUID, and
Session.activate with nil incoming media. These agree with the prior own fixture's native
choices; its endpoint remains synthetic. Native vendor selection requires Oneness flag
RavenStreamContinuityKit and ContinuityDevice.supportsMediaContinuityKit; the latter is
confirmed with the exact property getter and field metadata, not an offset/name guess.

The original phone cache uses ADRP/ADD/BR islands omitted by the earlier decoder. Corrected
raw B/BL and island scanning recovers 26 SSK-to-MCK code edges; the empty earlier scan is
not absence-of-use evidence. Phone MCK activation passes iPhoneMirroring and
shouldAdvertise=true to native Server construction and then Server.activate. Its control
listener's true branch selects the canonical service name; UUID naming belongs to false.

Original ScreenContinuityAngel default construction stores MediaTransport as the first
vendor and MCK as the second. The first server's async success branch stores it and projects
the optional second vendor. The MCK factory witness, scene wrapper's underlying-server
projection and queued native activation descriptor close the path to MCK Server activation;
second success stores the second server. Thus this resolved path sequences MCK startup after
first-server success. The legitimate external startup trigger, other prerequisites and
actual execution on the live 13 Pro remain unconfirmed. This gives a capture discriminator;
it does not prove phone publication or a generally available desktop entry.

**Normal runtime controls:** the native endpoint constructor returns canonical
com.apple.MediaContinuityKit.iPhoneMirroring, nil endpoint tag 1 and a successful synthetic
ID roundtrip. This own value-only control creates no Session or connection. The native
read-only SSK flag getter reports RavenStreamContinuityKit=true, after checking the enum's
native metadata and exported case value 4. No feature override is made, and no 13 Pro
capability or native app branch is measured.

A fresh parameters-only control (PID 71303) constructs native MCK browser parameters/options
and canonical descriptor without starting it. A separate browser control (PID 71308) uses
the unchanged native options, reaches ready, receives zero endpoints in five seconds and
cancels; both exit 0. A daemon query restricted to these PIDs and the static first-party
listener-enforcement prefix yields zero matching/reject/allow events for both. Only counts
are retained, not daemon messages, IDs or endpoint values. The known IDS getter rejection
is therefore not reproduced by this browser control. No-event observation cannot exclude
other policy gates or establish why discovery is empty.

**Result and next step:** no physical AXP archive, native rectangle, page coverage or AX
latency result. Next trace the normal external Angel startup entry and observe first-server
success → MCK activation/publication, with actual Mac device capability and vendor choice,
in an eligible session for this same 13 Pro. Follow with legitimate endpoint/admission and
control-stream acceptance. Existing manual native-session/login questions remain pending;
no new credential, account, signing, entitlement or feature-state action is taken. Normal
probes have exited; the final own executable-path inventory on Mac-M2 is empty, local owned
capture/probe inventory is empty, and VoiceOver remains off. No production source changes
or product smoke/build/device gate is claimed.

Raw artifacts and bench source remain outside Git under
~/.local/state/ipb/20261011-provider/, with corresponding remote probes in
/Users/hb/.local/state/ipb/20261011-provider/. Local references include
ssk-image-macos27.json, ssk-mck-imports-macos27-checked.json,
ssk-native-mck-capability-getter-macos27-main.txt, ssk-raven-flag-control-macos27.log,
mck-endpoint-service-control-macos27.log, ios-ssk-fullbranch-imports-original-main.json,
ios-ssk-mck-code-edges-original-main.json, original phone constructor/activation disassembly,
ios-angel-first-then-mck-wrapper-static-main.txt,
ios-ssk-native-selected-mck-server-activate-witness-original-main.txt,
ios-selected-mck-activation-task-descriptor-main.json,
mck-browser-policy-controls-macos27.json, ids-browser-policy-branch-counts-macos27.json,
cleanup-owned-provider-probes-macos27.json and handoff.md. No raw snapshots or ad hoc scripts
are added to the repository.

## 2026-10-11 — DevicesApp raw DTX tree, rectangles and explicit application control

**Scope:** supplementary local macOS 26.5.1 / 25F80, Xcode 27 Beta 6, DeviceKit 255.2.3,
AccessibilityAudit 192.6, CoreDevice 642.15; only iPhone 13 Pro / iPhone14,2 /
iOS 27.0 / 24A437, UDID 00008110-0014711C3CC3801E, CoreDevice UUID
7F2FE6E9-5423-552A-A2A2-C499F1D8672F. Developer Mode is enabled. Physical USB is on Mac-M2;
the successful ordinary client uses the existing local paired-network tunnel. This is not a
new USB-only or supported-macOS-27 acceptance run. No production code, build or smoke gate.

**Corrected transport assumption:** DeviceKit's DeviceAccessibilityView actually opens
`com.apple.accessibility.axAuditDaemon.remoteAXService` through CoreDevice's named socket API,
then AXAuditRemoteDevice creates raw DTXSocketTransport/DTXConnection. Physical axauditd accepts
that route into AXAuditDevicesAppRemoteServer, separate from the Inspector shim. iOS subscription
true starts AXPRemoteCacheManager with cached client type 2. Host's similarly named noop method
was not the phone implementation. Exact source versions/UUIDs and original-cache call addresses
are recorded in the [protocol section](protocol.md#devicesapp-ax-over-raw-dtx-2026-10-11).

Normal own AX CoreDevice socket requests fail 4000/POSIX 83 after tunnel warmup; a same-client HID
socket control succeeds. Normal NativeRemotedTunnel reaches the exact paired phone's RSD on its
current advertised port (49557 in this run, not an assumed 58783), which advertises the AX
service. Direct TCP + raw DTX works despite UsesRemoteXPC=true / AppleInternal advertisement
metadata. A failed RemoteXPC upgrade/FD request did not prove the AX protocol inaccessible.
No key/token/account/signing/entitlement/feature-state override was used; initial inventory output
was restricted locally to this target and minimal approved service fields.

**Physical protocol:** DTX control channel 0, hostAPIVersion=7, deviceAPIVersion=26,
clientNeedsAccessibility Bool, processDataFromRemoteDevice NSData callbacks, and
processDataFromHost NSData requests. Native secure-codec comparison is followed by an ordinary
Python DTX client and bounded plist decoder. Live PID/ID, labels, children and native frame
values agree for Calculator's type-11 bulk packet. Attributed text needs NSString decoding;
non-tree notification/nil resultData is explicitly handled. No live Apple process is modified.

**Confirmed root-selection problem:** first automatic bulk gives 13 PDUIApp nodes while actual
Home/Settings screenshots show another page. A fresh native/Python Calculator subscription
instead gives its correct 24-node graph. Settings target-PID/Inspector enable/monitor controls
still leave the bulk rooted at PDUIApp. Physical generation queries native frontmost attribute
1102 and takes the first object; why it names that unrelated PID is not root-caused. Request type
4 reproduces wrong PID 5965. Do not infer full current-page coverage from a received bulk archive.

**Working request path:** sourced request type 1 with parameters.pid obtains an application
root; type 5 reads children 8, frame 21, label 3, identifier 25 and value 53. System hit-test type
6 with a native blank translation carrier and portrait logical point (195,400), displayId=0,
returns SpringBoard 39 on Home, Preferences 8642 on Settings and Calculator 51502 on Calculator.
The later all-Python encoder also selects Bilibili's actual PID 52460. It then obtains the app
root and traverses received children, without a user-supplied app PID or native AX framework.
Unit replies lack associatedTranslationObject, so only one semantic read is outstanding.
Unsolicited type-11 archives are kept separate; no guessed node identity or input replay.

| Observed page | Nodes / native frames | Timing and scope |
| --- | --- | --- |
| Calculator main | **24 / 24** | Bulk first packet 34699 B at **1181 ms after subscription**, then 129617 B additional. Automatic Python traversal child walk **443 ms**, complete fresh session **740 ms**. |
| Calculator History sheet | **4 / 4** | Fresh History frame (20,51,36,36) → one centre HID tap; same-session bulk changes to the sheet. Screenshot after closing AX confirms it. The first whole run has a concurrent screenshot TimeoutError and is **not** a fully passing run. |
| Settings main | **13 / 13** | Explicit-root child walks **1059 ms** initially and **222 ms** in the later transition control; all observed children resolve. |
| Settings Battery | **32 / 32** | Fresh Battery-node centre HID tap opens Battery. Same-session child walk **914 ms**, approximately **3276 ms** from input subprocess dispatch through completed tree. Automatic current-app fresh session **941 ms**, child walk **604 ms**. |
| Home | **29 / 29** | Explicit SpringBoard child walk **519 ms**; automatic hit-derived traversal **473 ms**, complete fresh session **768 ms**. App-icon labels/frames match screenshot. |
| Bilibili 9.13.0 login modal + number keyboard | **40 / 40** | Installed metadata builtByDeveloper=false/containerAccessible=false. Automatic hit-derived PID matches process inventory; **1420 ms** child walk, **1744 ms** fresh session. Phone field, button and digits 0–9 have numerical frames. No login/data input performed. |

Fresh-session timings run from entry into the Python coroutine through native paired-tunnel
assertion, RSD/TCP/DTX setup, reads and normal cleanup. They exclude interpreter/module-import
and app-launch time; child-walk timings exclude application/root-attribute reads. These are
sample observations, not p95 budgets. Logical portrait size is 390×844, native 1170×2532/scale3.

A second fresh Calculator Close-node centre tap closes History; same-session tree changes from
4/4 to 24/24. The actual screenshot preserves Calculator's value 7. The Bilibili first probe
runs during its visible launch splash and returns hit-test error 8/nil; a later screenshot shows
its login modal/number keyboard and the next bounded read succeeds. No input is sent after
nil selection. This is a readiness/coverage case, not a demonstrated permanent refusal.

**Limits and cleanup:** sampled graphs have unique IDs, finite frames and closed observed child
references, but are accessibility graphs, mostly flat children; they are not full UIView or
CALayer graphs or proof of all arbitrary-app/system/hidden/offscreen coverage. Centre hit testing,
rotation, page-generation consistency and token lifetime still need controls. Direct semantic
AX actions are untested. Some false-subscription stop calls see connection termination before
acknowledgement; data capture and cleanup results are recorded separately. A later Home screenshot
succeeds during a short AX read, so the one screenshot timeout is not an established universal
coexistence failure. Owned sessions close after every run, and final phone cleanup returns Home.
No new phone software, authentication credentials, certificate, security/account setting or
VoiceOver change. Existing manual Mirroring-login/account prerequisites are not repeated.

Raw packet archives, screenshots and ad hoc probes remain outside version control at
~/.local/state/ipb/20261011-provider/. Local handoff.md and the per-run summary.json files map
native source identities, exact commands, unsuccessful controls and cleanup. No raw logs,
snapshots, complex one-off scripts or success-only evidence files are committed.
