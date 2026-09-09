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

**Not yet verified on device** — needs a mirror session to confirm both axes now match Device Hub.

### Still not done

The mirror sends no `AbsolutePointerReport`. Device Hub sends one continuously as the pointer
moves, and the capture showed it emits no scroll report at all unless the pointer is over the
phone view. If scrolling is still unreliable after the sign fix, establishing the pointer is the
next thing to add.

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

**Not yet verified on device.**
