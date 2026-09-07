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
