# CoreDevice HID Protocol Map

This document tracks the protocol surface currently extracted from macOS 27 / Xcode 27 beta 2. It distinguishes verified CLI behavior from symbol-level evidence and unfinished reverse-engineering work.

## Transport

The host opens `com.apple.CoreDevice.CoreDeviceService` and sends a synchronous XPC action request:

```text
CoreDevice.actionIdentifier = com.apple.coredevice.action.createservicesocket
CoreDevice.deviceIdentifier = <device UUID>
CoreDevice.coreDeviceVersion = { components = [636, 3], stringValue = "636.3" }
CoreDevice.CoreDeviceDDIProtocolVersion = 1
CoreDevice.invocationIdentifier = <UUID>
CoreDevice.input.featureIdentifier = <feature>
```

The reply contains:

```text
CoreDevice.output.fileDescriptor
CoreDevice.output.remoteXPCVersionFlags = 0x0100000000000006
CoreDevice.output.featureIdentifiers = [<feature>]
```

The file descriptor is upgraded with `xpc_remote_connection_create_with_connected_fd`, then wrapped as a Mercury peer for Swift protocol dispatch.

## Features

Verified features:

| Feature identifier | Backing class/protocol | Current use |
| --- | --- | --- |
| `com.apple.coredevice.feature.remote.universalhidservice` | `CoreDevice.UniversalHIDService` / `DDIUniversalHIDService` | touch reports, swipe, scroll, gesture reset |
| `com.apple.coredevice.feature.remote.hid.button` | `CoreDevice.HIDButton` / `IndigoHIDButton` | Home and generic button clicks |
| `com.apple.coredevice.feature.remote.hid.digitizer` | `CoreDevice.HIDDigitizer` / `IndigoHIDDigitizer` | long press and bottom-edge App Switcher gesture |

Additional feature strings present in CoreDevice but not yet wired in this CLI:

```text
com.apple.coredevice.feature.remote.hid.keyboard
com.apple.coredevice.feature.remote.hid.pointer
com.apple.coredevice.feature.remote.hid.scroll
com.apple.coredevice.feature.remote.hid.vendordefined
com.apple.coredevice.feature.remote.devicecontrol.orientation
com.apple.coredevice.feature.remote.universalhid
```

## UniversalHID Service

Symbol evidence from `CoreDevice.UniversalHIDService`:

```text
send(report: UniversalHID.HIDReport, to: CoreDevice.HIDServiceID)
send(report: UniversalHID.HIDReport, to: UInt64)
sendBarrier()
resetGestureState(service: CoreDevice.HIDServiceID)
resetGestureState(service: UInt64)
createService(descriptor: CoreDevice.HIDServiceDescriptor)
createService(properties: UniversalHID.HIDServiceProperties)
remove(service: CoreDevice.HIDServiceID)
removeService(serviceID: UInt64)
connectedServices()
connectedServiceDescriptors()
connectedServiceIDs()
primaryPointer()
primaryKeyboard()
findServiceMatching(usage: UniversalHID.HIDUsage)
```

The verified main touchscreen service is:

```text
mainTouchscreen(0x101)
```

The CLI exposes this as `UHID_SERVICE_ID`, defaulting to `0x101`. The value is now verified by calling CoreDeviceUtilities `HIDServiceID` static getters through an indirect-return ABI shim:

```sh
bin/devicehubctl service-ids
```

Observed output:

```text
mainTouchscreen              0x101 (257)
touchscreen(displayID:1)     0x101 (257)
touchscreen(displayID:2)     0x102 (258)
touchscreenGesture           0x501 (1281)
mainKeyboard                 0x200 (512)
keyboard(identifier:1)       0x201 (513)
mainPointer                  0x300 (768)
pointer(identifier:1)        0x301 (769)
mainScreenButtons            0x402 (1026)
digitalCrown                 0x400 (1024)
dial                         0x401 (1025)
avpCustom                    0x500 (1280)
userDefinedBase              0xff0000 (16711680)
```

Encoding inferred from disassembly and verified by the getters:

| Kind | Encoding |
| --- | --- |
| Touchscreen display `n` | `0x100 + n` |
| Keyboard identifier `n` | `0x200 + n` |
| Pointer identifier `n` | `0x300 + n` |
| Digital Crown | `0x400` |
| Dial | `0x401` |
| Main screen buttons | `0x402` |
| AVP custom | `0x500` |
| Touchscreen gesture | `0x501` |
| User-defined base | `0xff0000` |

The getter ABI is indirect for resilient Swift structs: the caller provides an output buffer in `x8`, and the getter writes the 64-bit id into that buffer.

## DeviceHub / DeviceKit Path

DeviceHub itself is a thin SwiftUI/AppKit shell. On Xcode 27.0 beta 2:

```text
DeviceHub.app CFBundleIdentifier = com.apple.dt.Devices
DeviceHub.app CFBundleVersion = 244.2.3
DeviceKit.framework current version = 244.2.0
CoreDevice.framework current version = 636.3.0
CoreDeviceUtilities.framework current version = 636.3.0
```

`DeviceHub` links `DeviceKit.framework`, `CoreDevice.framework`, and `CoreDeviceUtilities.framework`, but the HID logic is in:

```text
/Applications/Xcode-27.0.0-Beta.2.app/Contents/SharedFrameworks/DeviceKit.framework/Versions/A/DeviceKit
```

`DeviceKit` links:

```text
/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice
/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/Frameworks/UniversalHID.framework/Versions/A/UniversalHID
/Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework/Versions/A/CoreDeviceUtilities
/System/Library/PrivateFrameworks/HID.framework/Versions/A/HID
/System/Library/PrivateFrameworks/UniversalHIDKit.framework/Versions/A/UniversalHIDKit
```

The important classes and strings are:

```text
DeviceKit.HIDManager
DeviceKit.HIDManager.EventSender
DeviceKit.HIDManagerProtocol
DeviceKit.SyntheticTouchEventProcessor
DeviceKit.DigitizerState
DeviceKit.HIDEventGeometry
DeviceKit/DeviceKit/HIDManager.swift
createService(descriptor:
reset(serviceID:
report(reportID:
fetchConnectedServiceDescriptors(generation:)
Failed to lookup service for 0x%s
Creating new service with descriptor %s
Starting initializeHIDServices generation %{public}ld
Available HID services from %{public}s are %{public}s
Touchscreen service %{public}s
Created HID service: %{public}s
Sent Reset HID Service State
```

The DeviceKit implementation appears to be a two-stage pipeline:

1. Initialization starts an async HID service task. The task logs `Starting initializeHIDServices generation`, fetches connected HID service descriptors, logs `Available HID services from ...`, then filters descriptors using `CoreDeviceUtilities.HIDServiceDescriptor` helpers.
2. When a touchscreen descriptor qualifies, `DeviceKit` records it and builds the local processing state used by `SyntheticTouchEventProcessor`.
3. Event delivery goes through `DeviceKit.HIDManager.EventSender`. It first queries the local HID event system client's `services`, compares each service's `serviceID`, and uses the matching local service if present.
4. If the local HID service is missing, it logs `Creating new service with descriptor ...`, creates a local UniversalHID/HID service from the `CoreDevice.HIDServiceDescriptor`, computes report/event masks, and caches the service keyed by `HIDServiceID`.
5. The final remote delivery still uses the CoreDevice UniversalHID protocol surface: `send(report:to:)`, `resetGestureState(service:)`, and `sendBarrier()`.

Representative disassembly evidence from `DeviceKit`:

| Address | Evidence | Interpretation |
| --- | --- | --- |
| `0x412e04` | calls `_objc_msgSend$services` | Enumerates local HID services before sending an event |
| `0x412e90` | calls `_objc_msgSend$serviceID` | Reads each local service id |
| `0x412e9c` | calls a CoreDevice HIDServiceID getter/raw helper, then compares | Matches local service by CoreDevice service id |
| `0x4131bc` | logs `Failed to lookup service for 0x%s` | No local HID service exists for the target id |
| `0x413514` | logs `Creating new service with descriptor %s` | Starts dynamic local service creation |
| `0x413604` | witness-call using the descriptor | Copies/initializes descriptor-shaped value |
| `0x413610` | stores enum tag `4` before helper calls | Builds a descriptor-related Swift enum payload |
| `0x41362c` | witness-call using the service id | Associates created local service with `HIDServiceID` |
| `0x4136ac`-`0x413708` | iterates descriptor-derived report ids/masks | Computes event/report mask set for the local service |
| `0x413788` | inserts into a dictionary/cache | Caches the created local service |
| `0x418438` | async task frame setup | HID service initialization task |
| `0x418864` | logs `Starting initializeHIDServices generation` | Initialization has entered descriptor discovery |
| `0x418ff0` | logs `Available HID services from ...` | Descriptor array has been fetched |
| `0x4191a8` | loops over descriptor array | Filters connected descriptors |
| `0x4192e0` | allocates touchscreen processing object | Touchscreen descriptor accepted |
| `0x4195b8` | logs `Touchscreen service %{public}s` | Touchscreen service selected |

This means DeviceHub UI interaction is not a separate public command channel. It uses DeviceKit to translate local Mac mouse/touch/key events into UniversalHID reports and then sends those reports over the same CoreDevice service socket.

For this CLI, the useful abstraction is therefore:

```text
CoreDevice service socket
  -> Mercury peer for com.apple.coredevice.hid.universalhidservice
  -> CoreDevice.DDIUniversalHIDService
  -> UniversalHID.HIDReport
  -> HIDServiceID, usually 0x101 for the main touchscreen
```

The current CLI intentionally bypasses DeviceKit's local `HIDEventSystemClient`, `UniversalHIDKit.EventObserver`, and event translation layer. It constructs `UniversalHID.HIDReport` values directly and dispatches them through `CoreDevice.UniversalHIDService`.

## UniversalHID Requests

`CoreDeviceUtilities.DDIUniversalHIDServicePayload.Request` has symbol-level constructors for:

| Request case | Fields observed | Status |
| --- | --- | --- |
| `send` | `Data`, `CoreDevice.HIDServiceID` | Verified through CoreDevice protocol dispatch |
| `resetGestureState` | `CoreDevice.HIDServiceID` | CLI exposed, needs broader device testing |
| `connectedServices` | no payload | Symbol present, current Mercury typed sync bridge returns `result=1` |
| `createService` | `CoreDevice.HIDServiceDescriptor` | Legacy XPC wrapper exists, not verified |
| `removeService` | `CoreDevice.HIDServiceID` | Symbol present, not yet wired |

The Mercury peer service name discovered in strings and successful typed send experiments is:

```text
com.apple.coredevice.hid.universal
```

The generated/observed request and reply types are:

```text
CoreDeviceUtilities.DDIUniversalHIDServicePayload.Request
CoreDeviceUtilities.DDIUniversalHIDServicePayload.ConnectedServices
```

`ConnectedServices` is a struct wrapping:

```text
[CoreDevice.HIDServiceDescriptor]
```

The raw enum layout observed for `Request.connectedServices` is a 32-byte value with tag byte `4` at offset `24`; its description prints `{connectedServices}`.

`connectedServices` and the synchronous `DDIUniversalHIDServicePayload.Request.connectedServices` wrapper are not the path DeviceHub uses for discovery. The DeviceHub/DeviceKit path calls the Swift async protocol method:

```text
CoreDevice.UniversalHIDService.connectedServiceDescriptors() async throws -> [CoreDevice.HIDServiceDescriptor]
```

Descriptor-discovery probe matrix:

| Probe | Result | Interpretation |
| --- | --- | --- |
| Raw RemoteXPC async wrapper carrying `{connectedServices}` | Remote `Connection invalid` | Not the wrapper shape used by DeviceHub |
| Raw Mercury one-way XPC dictionary | Remote `Connection invalid` | The UniversalHID peer expects typed CoreDevice/Mercury values |
| Mercury `sendSync(value:)` with `Request.connectedServices` | Reaches the peer, but reply is currently zero/empty and the remote event is `Connection invalid` | Synchronous typed request is not the DeviceHub path, or still misses a session/metadata detail |
| Mercury `send(value:replyQueue:replyHandler:)` hand-written ABI experiment | Removed from the public CLI after an ABI crash | Crash was local Swift generic/closure ABI misuse, not a valid protocol result |
| `CoreDevice.UniversalHIDService.connectedServiceDescriptors()` | Verified through a Swift async shim plus a small ARM64 ABI bridge | DeviceHub's real descriptor path |

The async dispatch detail that mattered: CoreDevice's async function pointer descriptor uses two 32-bit words, a signed relative target and an async frame size. The `connectedServiceDescriptors()` witness entry is an async descriptor, and the concrete DDI implementation expects the UniversalHID existential self in `x20`. The CLI bridge therefore sets `x20` to a one-word service box and exposes a matching `Tu` async descriptor for Swift concurrency.

The returned value is native Swift Array storage for `[CoreDevice.HIDServiceDescriptor]`. Runtime value witness metadata shows `HIDServiceDescriptor` is an 8-byte resilient value whose single word is its storage dictionary. The dictionary is `[String: CoreDevice.CodableValue]`; the currently decoded `CodableValue` tags are:

| Tag | Meaning | Payload |
| --- | --- | --- |
| `0x0` | array | Swift Array storage of nested `CodableValue` |
| `0x1` | bool | boxed UInt64, nonzero is true |
| `0x5` | dictionary | Swift Dictionary storage of `String -> CodableValue` |
| `0x8` | unsigned integer | boxed UInt64 |
| `0x9` | `HIDServiceID` | boxed UInt64 service id |
| `0xa` | string | boxed Swift `String` |

On the verified iPhone 13 Pro/iOS 27 device, `bin/devicehubctl descriptors` decodes:

| Service | Product | Primary usage page | Primary usage | Notable fields |
| --- | --- | --- | --- | --- |
| `0x101` | `CoreDevice touchscreen(nil)` | `13` | `4` | `DeviceTypeHint=Digitizer`, `Built-In=true` |
| `0x200` | `CoreDevice keyboard` | `0` | `0` | `DeviceTypeHint=Keyboard`, original usage `{page=1, usage=6}` |
| `0x402` | `CoreDevice mainScreenButtons` | `11` | `1` | `Authenticated=true`, `DisplayIntegrated=true`, also usage `{page=1, usage=6}` |
| `0x500` | `CoreDevice avpCustom` | `65377` | `91` | AVP/vendor custom service |
| `0x501` | `CoreDevice touchscreenGesture` | `1` | `2` | `DeviceTypeHint=Trackpad`, suppresses mouse pointer |

`HIDCTL_VERBOSE_DESCRIPTORS=1 bin/devicehubctl descriptors` prints raw Array, metadata, and value-witness details for future ABI checks.

The current `sendSync(value:)` ABI shim was corrected during this analysis. The short generic overload orders arguments as:

```text
request value
request metadata
reply metadata
request Decodable witness
request Encodable witness
reply Decodable witness
reply Encodable witness
reply out buffer in x8
self in x20
error in x21
```

## HID Reports

Currently generated via `UniversalHID.framework` private Swift symbols:

| Report | Report ID / size | Fields currently set |
| --- | --- | --- |
| `UniversalHID.DigitizerReport` | `reportID = 0x09`, `bitCount = 0x140` | contact index, touch, range, resting, x, y, contact count, max count |
| `UniversalHID.NavigationSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |
| `UniversalHID.DockSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |

Low-level CLI commands:

```sh
bin/devicehubctl uhid-report 0x101 0.5 0.5 1 1
bin/devicehubctl uhid-swipe-report 0x101 0.5 0.5 1 1 0 0 0
bin/devicehubctl nav-report 0x101 1 1 0x0d 5 0.0 0.5 0.99
bin/devicehubctl dock-report 0x101 1 1 0x0d 3 0.0 0.5 0.99
```

## HID Button

`CoreDevice.HIDButton` exposes:

```text
sendCustomButton(usagePage: Int, usageCode: Int, state: HIDButtonState)
sendButton(page: HIDUsageStaticMember, code: HIDUsageCode, state: HIDButtonState)
sendBarrier()
```

Observed state mapping:

```text
0 = down
1 = up
```

Verified Home button sequence:

```text
usagePage = 0x0c
usageCode = 0x40
down -> up -> barrier
```

Generic CLI:

```sh
bin/devicehubctl button 0x0c 0x40
```

## HID Digitizer

`CoreDevice.HIDDigitizer` exposes:

```text
send(pointOne: DigitizerPoint, pointTwo: DigitizerPoint?, eventType: DigitizerEventType, edge: DigitizerEdge, target: DigitizerTarget)
send(pointOne: CGPoint, pointTwo: CGPoint?, eventType: DigitizerEventType, edge: DigitizerEdge, target: DigitizerTarget)
sendBarrier()
```

Observed event values:

```text
0 = start
1 = position / move
2 = end
```

The CLI exposes the raw digitizer event:

```sh
bin/devicehubctl digitizer-event <x1> <y1> <x2> <y2> <point2_tag> <event_type> <edge> [target_low] [target_high]
```

Verified high-level use:

- long press: start, repeated position pulses, end
- App Switcher: bottom-edge swipe with `edge = 3`

## Current Gaps

- `connectedServiceDescriptors()` is decoded on the current macOS 27/Xcode 27 beta 2 host and iOS 27 device, but the ABI is private Swift framework ABI and should be re-verified on each beta seed.
- `connectedServices` and `connectedServiceIDs` remain symbol-mapped but are not exposed because the verified DeviceHub path is `connectedServiceDescriptors()`.
- `createService` and `removeService` request cases are identified but not verified.
- Keyboard, pointer, scroll-specific, vendor-defined HID feature protocols are symbol-mapped but not implemented.
- Multi-touch second point, `DigitizerTarget`, and `DigitizerEdge` values need systematic enumeration.
- The current implementation still relies on private Swift framework ABI and can break across Xcode 27 beta seeds.

## Reproducing Symbol Evidence

Useful local commands:

```sh
nm -gU /Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice \
  | rg 'UniversalHID|IndigoHID|HIDButton|HIDDigitizer|HIDScroll|HIDKeyboard|HIDPointer|VendorDefined' \
  | xcrun swift-demangle

nm -gU /Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework/Versions/A/CoreDeviceUtilities \
  | rg 'DDIUniversalHIDServicePayload|HIDServiceID|HIDUsagePair' \
  | xcrun swift-demangle

nm -gU /Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework/Versions/A/UniversalHID \
  | xcrun swift-demangle \
  | rg 'Digitizer|NavigationSwipe|DockSwipe|HIDReport|Pointer|Keyboard|Scroll|Vendor'

strings /Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice \
  /Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework/Versions/A/CoreDeviceUtilities \
  /Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework/Versions/A/UniversalHID \
  | rg 'com\.apple\.coredevice\.(feature|action|hid)|UniversalHIDService|ConnectedServices|mainTouchscreen' \
  | sort -u
```
