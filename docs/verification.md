# Verification Notes

Host:

- macOS 27 beta
- Xcode 27.0.0 Beta 2
- DeviceHub 27.0 build 244.2.3
- DeviceKit 244.2.0
- CoreDevice/CoreDeviceUtilities 636.3.0

Device:

- iPhone 13 Pro
- iOS 27.0
- Device identifier used during extraction: `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`

Commands verified:

```sh
bin/devicehubctl tap 0.5 0.5
bin/devicehubctl long 0.615 0.675 1.2
bin/devicehubctl scroll 0.5 0.75 0 0.30
bin/devicehubctl swipe 0.5 0.75 0.5 0.35
bin/devicehubctl home
bin/devicehubctl recents
bin/devicehubctl screenshot build/smoke.png
bin/devicehubctl service-ids
bin/devicehubctl descriptors
bin/devicehubctl services
bin/devicehubctl service-id touchscreen
bin/devicehubctl service-id gesture
bin/devicehubctl service-id keyboard
bin/devicehubctl pointer-report 0x501 0 0 0
bin/devicehubctl pointer 0 0
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-event 0 0 0 undefined undefined digital-crown
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl key-up
bin/devicehubctl key escape 0.02
```

The original investigation also captured screenshots after each command, but those are intentionally not committed to keep the repository small and reviewable.

Additional protocol probe commands now exposed:

```sh
bin/devicehubctl probe-services
HIDCTL_VERBOSE_DESCRIPTORS=1 bin/devicehubctl descriptors
bin/devicehubctl reset-gesture 0x101
bin/devicehubctl button 0x0c 0x40
bin/devicehubctl keyboard-report 0x200 escape 1
bin/devicehubctl pointer-report 0x501 0 0 0
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-event 0 0 0
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl uhid-report 0x101 0.5 0.5 0 0
bin/devicehubctl digitizer-event 0.5 0.5 0 0 1 2 0
bin/devicehubctl digitizer-event 0.5 0.5 0 0 1 end none
bin/devicehubctl raw com.apple.coredevice.feature.remote.hid.digitizer cd_digitizer_ext 0.5 0.5 0 0 1 end none
bin/devicehubctl digitizer-event 0.5 0.5 0 0 1 impossible none -> unknown digitizer event type: impossible
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
service_id=$(bin/devicehubctl service-ids | awk '/^mainTouchscreen/ {print $2}')
UHID_SERVICE_ID="$service_id" bin/devicehubctl uhid-report "$service_id" 0.5 0.5 0 0
UHID_SERVICE_ID="$service_id" bin/devicehubctl reset-gesture
```

`UHID_SERVICE_ID=auto` is also verified for role resolution:

```text
bin/devicehubctl service-id touchscreen -> 0x101
bin/devicehubctl service-id gesture -> 0x501
bin/devicehubctl service-id keyboard -> 0x200
bin/devicehubctl service-id buttons -> 0x402
```

Keyboard report verification:

```text
bin/devicehubctl key-up
bin/devicehubctl key escape 0.02
```

`key-up` sends an empty `UniversalHID.KeyboardReport` to service `0x200`; `key escape` sends usage `0x29` down, then an empty release report, followed by a UniversalHID barrier.

Pointer report verification:

```text
bin/devicehubctl pointer-report 0x501 0 0 0
bin/devicehubctl pointer 0 0
bin/devicehubctl pointer-report 0x501 0 0 0 0 0 1
```

The zero-movement pointer reports are non-destructive smoke tests for construction and delivery of `UniversalHID.PointerReport` to the `CoreDevice touchscreenGesture` service. `flags=1` exercises the UInt32-backed `PointerReport.Flags.accelerated` path; other flag bits still need behavior enumeration.

Scroll report verification:

```text
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-report 0x501 0 0 256 -> Unable to build UniversalHID scroll HIDReport
```

The zero-movement scroll report is a non-destructive smoke test for construction and delivery of `UniversalHID.ScrollReport` plus `ScrollCollection` to the `CoreDevice touchscreenGesture` service. The `phase=256` probe verifies local `UInt8` raw-value validation.

Standalone HIDScroll verification:

```text
bin/devicehubctl scroll-event 0 0 0 undefined undefined digital-crown
bin/devicehubctl scroll-event 0 0 0 impossible -> unknown scroll phase: impossible
bin/devicehubctl scroll-event 0 0 0 0x10000 -> HIDScroll raw values out of range
```

The zero-movement scroll event is a non-destructive smoke test for opening `com.apple.coredevice.feature.remote.hid.scroll`, dispatching `CoreDevice.HIDScroll.send(point:phase:momentum:target:)`, and following with `sendBarrier()`. The invalid phase probe verifies shell-side enum-name validation; the out-of-range probe verifies C-side raw-width validation.

Standalone HIDVendorDefined verification:

```text
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl vendor-defined 0 0 0 abc -> coredevice vendor-defined: invalid hex payload
bin/devicehubctl vendor-defined 0x10000 0 0 -> HIDVendorDefined raw values out of range
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

### macOS 27 beta host (Mac-M2)

Host:

- macOS 27.0 beta 7 (26A5421a); Software Update also offers beta 8 (26A5425a), not installed
- Xcode 27 beta 6 (27A5252f) at `~/Downloads/Xcode-beta.app`, the newest beta listed by Apple on that date; `/Applications/Xcode.app` is Xcode 26.4
- CoreDevice / CoreDeviceUtilities 642.15, Mercury 78, embedded UniversalHID 90.1
- DeviceHub 255.2.3.5, DeviceKit 255.2.3
- iOS DDI build 1335 (27A5252f), CoreDevice 642.15 inside

Verified there without a device:

- All 113 private symbols the sources bind (link-time `_$s...` references plus the `dlsym` names) still exist in CoreDevice, CoreDeviceUtilities, UniversalHID, and Mercury 642.15/78.
- `make` builds cleanly with `DEVELOPER_DIR` pointing at the beta 6 app, no `XCODE_PATH` override needed after the Makefile default change.
- `bin/devicehubctl service-ids` prints the same service table as on beta 2.
- The `createservicesocket` XPC request shape is still accepted by CoreDeviceService 642.15 when the client reports version 636.3 or 642.15; against an offline paired device the answer is `CoreDeviceError 4000, RemoteServiceDiscovery connectivity is not available`, i.e. the request got past decoding and version checks.
- Passing a UDID instead of the CoreDevice UUID yields `CoreDevice.ActionError: Value for key CoreDevice.deviceIdentifier not found`. The 642.15 `devicectl list devices` table prints UDIDs, so read the UUID from `devicectl list devices --json-output` for `DEVICE_ID`.
- Wire names are unchanged: the host still carries `com.apple.coredevice.hid.universal`; the DDI daemon `dtuhidd` registers `com.apple.coredevice.hid.universalhidservice`, `...hid.universalhid`, and `...hid.indigo` (button, scroll, digitizer, vendordefined) as RemoteXPC services behind the same six feature identifiers.
- Swift layouts the ABI shims depend on are unchanged in 642.15: `DDIUniversalHIDServicePayload.Request` cases are still `createService, removeService, send, resetGestureState, connectedServices` (tag 4 for `connectedServices`), `SendCodingKeys = _0,_1`, `IndigoVendorDefinedEvent = usagePage, usage, version, data`, `IndigoDigitizerEvent = pointOne, pointTwo, eventType, edge, target`. `CoreDevice.CodableValue` cases are `array, bool, data, date, decimal, dictionary, double, error, int, uint, string, url, uuid` in both 518.31 and 642.15, so the tag table in `docs/protocol.md` still holds; note that tag `0x8` is `int` and `0x9` is `uint` (the boxed `HIDServiceID` raw value), both decoded as a boxed 64-bit word.

Not verified there: every command that needs a device. No iOS 27 device was attached to Mac-M2 during the check (its paired iPhone 11 is network-only and offline). Run the following once an iOS 27 device is plugged in:

```sh
export DEVELOPER_DIR=/Users/hb/Downloads/Xcode-beta.app/Contents/Developer
DEVICE_ID=$(xcrun devicectl list devices --json-output /tmp/d.json >/dev/null && python3 -c 'import json;print([d["identifier"] for d in json.load(open("/tmp/d.json"))["result"]["devices"] if d["connectionProperties"].get("tunnelState")=="connected"][0])')
DEVICE_ID=$DEVICE_ID bin/devicehubctl descriptors
DEVICE_ID=$DEVICE_ID bin/devicehubctl key-up
DEVICE_ID=$DEVICE_ID bin/devicehubctl screenshot build/before.png
DEVICE_ID=$DEVICE_ID bin/devicehubctl home
DEVICE_ID=$DEVICE_ID bin/devicehubctl tap 0.5 0.5
DEVICE_ID=$DEVICE_ID bin/devicehubctl screenshot build/after.png
```

`scripts/smoke_matrix.sh <repo> <out_dir>` runs the non-destructive subset above and captures before/after screenshots; add `SMOKE_INTERACTIVE=1` to also exercise `home`, `tap`, `recents`, `swipe`, `scroll`, `long`, and `key`. The first thing to check in `descriptors` output is that the five services still decode with readable product strings; the `CodableValue` tag table in `docs/protocol.md` is the part most exposed to enum reordering between seeds.

### macOS 26 host (this Mac)

Host: macOS 26.5.1 (25F80), Xcode 26.5 (17F42), CoreDevice 518.31, Mercury 70, iOS DDI build 659 (CoreDevice 518.31). Devices: iPhone 13 Pro on iOS 27.0 (24A5430a, wired, `ddiServicesAvailable: true`) and iPhone 12 mini on iOS 26.5.

Findings:

- `make` fails at link time with 25 undefined symbols: the 12 `HIDServiceID` static getters, the 4 `UniversalHIDService` dispatch thunks, the 2 `HIDVendorDefined` thunks, 4 `DDIUniversalHIDServicePayload` symbols (all CoreDevice/CoreDeviceUtilities 518.31), plus `DigitizerReport.setContactSwipe{Pending,Locked,Up}` from the OS copy of UniversalHID (80). Everything else in UniversalHID resolves against the macOS 26 SDK stub, so the OS-level frameworks are not the blocker.
- Linking the same objects against a copy of the 642.15 CoreDevice, CoreDeviceUtilities, embedded UniversalHID, and Mercury 78 from Mac-M2 succeeds with the Xcode 26.5 toolchain, and the resulting binary loads those frameworks on macOS 26.5.1 (`DYLD_FRAMEWORK_PATH`) and prints the full `service-ids` table. CoreDevice 642.15 declares `minos 14.0` and only depends on OS frameworks that exist on macOS 26.
- The device side is the harder blocker on this host: a `createservicesocket` request for any `feature.remote.hid.*`, `universalhidservice`, or even `viewdevicescreen` returns `CoreDeviceError 1001, The capability "Create Service Socket" is not supported by this device`, for the iOS 27 phone as well as the iOS 26.5 phone. The Xcode 26.5 DDI ships no `dtuhidd`; its CoreDeviceUtilities only carries the older `feature.remote.hid.*` strings. Xcode 27 beta 6's DDI adds `dtuhidd`, `dthidd`, `dtremotedisplayd`, and `dtscreencaptured`.

Conclusion for porting: the tool is tied to the CoreDevice package version, not to the macOS major. Installing Xcode 27 beta (minimum macOS 26.4) on a macOS 26 host brings CoreDevice 642.x, the embedded UniversalHID, and the DDI with `dtuhidd`, after which the same sources should build and run. Whether the beta DDI also enables the HID services on an iOS 26 device is untested.

## Device verification, 2026-09-07

Both hosts run Xcode 27 beta 6 (27A5252f) and CoreDevice 642.15; both devices run iOS 27.0 (24A5430a) with the beta 6 DDI (CoreDevice 642.15, `dtuhidd` present).

| Host | Device | Result |
| --- | --- | --- |
| Mac-M2, macOS 27.0 beta 8 (26A5425a) | iPhone 12 mini, wired | `scripts/smoke_matrix.sh` interactive: all 39 steps rc 0 and expected output. Screenshots: `tap 0.15 0.12` launched Calendar, `recents` showed the App Switcher, `home` returned to SpringBoard, swipe/scroll on the home screen pulled down Spotlight, `long` while Calendar was foreground coincided with its location prompt. |
| This Mac, macOS 26.5.1 (25F80) | iPhone 13 Pro, wired | Same 39 steps rc 0. The icon at (0.15, 0.12) was an unverified developer build, so the tap raised the "无法验证 App" system alert, which Home cannot dismiss; `key escape` cleared it. Non-destructive gate re-run passes. |

Behaviour established on both hosts:

- Every HID socket needs `tunnelState = connected`. A freshly attached or idle device answers `createservicesocket` with CoreDeviceError 4000; the helper now exits 4 and the wrapper warms the tunnel once via `devicectl device info details` and retries. One warm-up happened per smoke run.
- The helper exits non-zero on a refused socket (3), on any dispatch result other than 0 or a remote error while the connection is active (1), and on the watchdog (5). Before this change every failure exited 0, which is why the first smoke run on 2026-09-07 looked green while every HID request was failing.
- `devicectl` from `/Library/Developer/PrivateFrameworks/CoreDevice.framework/Resources/bin` is enough for screenshots; no `DEVELOPER_DIR` is needed at runtime.
- Decoded `descriptors` fields now print `int:` for tag 0x8 and `uint:` for tag 0x9; the `serviceID:0x…` label is derived from the `_ServiceID` field.

Pairing note: a phone that has never trusted the host shows up in `devicectl list devices` only as a bare ECID row with no state, and `devicectl manage pair` reports that only a `RestorableDeviceRef` representation exists, until the phone is unlocked and the Trust prompt is accepted.

Xcode-free client spike (see `docs/standalone-distribution.md`): with pymobiledevice3 11.8.0 and its userspace tunnel, and no CoreDevice host stack in the loop, `dtuhidd` on the iPhone 13 Pro answered `connectedServices` with the same five services, and two raw `send` dictionaries (digitizer report id 0x09, 40 bytes) tapped the App Library search field at (0.15, 0.12). The `{isBarrier: true}` message got no reply within 5 s over that path.

## Open question: does the device need iOS 27?

Evidence so far (2026-09-07):

- `dtuhidd` in the Xcode 27 beta 6 DDI is built with `LC_BUILD_VERSION minos 17.0, sdk 27.0`, and the DDI is the single personalized image Apple uses for iOS 17+, so the binary itself is not iOS 27 specific.
- An iPhone 11 on iOS 26.6.1 (23G83), paired to Mac-M2 but reachable only over the local network, could not mount that DDI: `devicectl device info ddiServices` returned CoreDeviceError 12040 and the HID socket was refused with 1001. This does not separate "iOS 26 unsupported" from "network-only mount unsupported"; a USB-attached iOS 26 device is required to answer it.
- On iOS 27 the device fetched the 642.15 DDI by itself as a `com.apple.MobileAsset.DDI` cryptex; whether iOS 26 does the same or relies on the host-supplied image is untested.

Until a USB test exists, the supported matrix stays macOS 27 + Xcode 27 beta + iOS 27.
