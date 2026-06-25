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
| `com.apple.coredevice.feature.remote.universalhidservice` | `CoreDevice.UniversalHIDService` / `DDIUniversalHIDService` | touch, keyboard, pointer, swipe, scroll, gesture reset |
| `com.apple.coredevice.feature.remote.hid.button` | `CoreDevice.HIDButton` / `IndigoHIDButton` | Home and generic button clicks |
| `com.apple.coredevice.feature.remote.hid.digitizer` | `CoreDevice.HIDDigitizer` / `IndigoHIDDigitizer` | long press and bottom-edge App Switcher gesture |
| `com.apple.coredevice.feature.remote.hid.scroll` | `CoreDevice.HIDScroll` / `IndigoHIDScroll` | raw scroll event probes |
| `com.apple.coredevice.feature.remote.hid.vendordefined` | `CoreDevice.HIDVendorDefined` / `IndigoHIDVendorDefined` | raw vendor-defined event probes |

Additional related CoreDevice/DeviceKit feature strings observed in this seed:

```text
com.apple.coredevice.feature.remote.devicecontrol.orientation
com.apple.coredevice.feature.remote.universalhid
```

`CoreDevice.framework` does not contain `com.apple.coredevice.feature.remote.hid.keyboard` or `com.apple.coredevice.feature.remote.hid.pointer` strings on the verified Xcode 27 beta 2 host. Keyboard and pointer protocols exist, but their built-in implementations are UniversalHID capability adapters rather than independent feature sockets.

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

The CLI can still use this as an explicit `UHID_SERVICE_ID=0x101`, but the wrapper default is now `UHID_SERVICE_ID=auto`. In auto mode, the CLI calls `connectedServiceDescriptors()` and selects the descriptor whose product is `CoreDevice touchscreen(nil)`, falling back to `0x101` if discovery fails. The static value is also verified by calling CoreDeviceUtilities `HIDServiceID` getters through an indirect-return ABI shim:

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

The shell wrapper exposes descriptor-derived service resolution:

```sh
bin/devicehubctl services              # alias of descriptors
bin/devicehubctl descriptors
bin/devicehubctl service-id touchscreen
bin/devicehubctl service-id gesture
bin/devicehubctl service-id keyboard
bin/devicehubctl service-id buttons
bin/devicehubctl service-id avp
```

High-level UniversalHID commands (`tap`, `swipe`, `scroll`, `reset-gesture`, `recents-nav`, and `recents-dock`) pass through this resolver when `UHID_SERVICE_ID=auto`.

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
| `UniversalHID.KeyboardReport` | `reportID = 0x01`, `bitCount = 0xf8` | keyboard usage bit at `usage + 8` |
| `UniversalHID.PointerReport` | queried from framework | x, y, button mask, accel x, accel y, raw UInt32 flags |
| `UniversalHID.ScrollReport` + `ScrollCollection` | queried from framework | collection flags, phase, momentum, x, y, accel x, accel y |
| `UniversalHID.NavigationSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |
| `UniversalHID.DockSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |

Low-level CLI commands:

```sh
bin/devicehubctl uhid-report 0x101 0.5 0.5 1 1
bin/devicehubctl uhid-swipe-report 0x101 0.5 0.5 1 1 0 0 0
bin/devicehubctl keyboard-report 0x200 escape 1
bin/devicehubctl pointer-report 0x501 0 0 0
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-event 0 0 0
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl key-up
bin/devicehubctl nav-report 0x101 1 1 0x0d 5 0.0 0.5 0.99
bin/devicehubctl dock-report 0x101 1 1 0x0d 3 0.0 0.5 0.99
```

## CoreDevice HID Vendor-Defined Feature

The standalone vendor-defined feature is implemented through the typed CoreDevice protocol path:

```text
feature = com.apple.coredevice.feature.remote.hid.vendordefined
class = CoreDevice.IndigoHIDVendorDefined
protocol = CoreDevice.HIDVendorDefined
send(usagePage: UInt16, usage: UInt16, version: UInt32, data: Foundation.Data)
sendBarrier()
```

Runtime metadata shows `IndigoHIDVendorDefined` stores the normal HIDXPC service fields plus a `deviceIdentifier` Swift string:

| Offset | Field |
| --- | --- |
| `0x10` | Mercury peer object |
| `0x18` | `Mercury.XPCPeerConnection` witness |
| `0x20` | feature identifier Swift string |
| `0x30` | device identifier Swift string |

`CoreDeviceUtilities.IndigoVendorDefinedEvent` confirms the event layout:

| Offset | Field | Type |
| --- | --- | --- |
| `0x00` | `usagePage` | `UInt16` |
| `0x02` | `usage` | `UInt16` |
| `0x04` | `version` | `UInt32` |
| `0x08` | `data` | `Foundation.Data`, 16-byte Swift value |

CLI usage:

```sh
bin/devicehubctl vendor-defined <usage_page> <usage> <version> [hex_payload]
```

The optional payload is a hex string. Separators ` `, `:`, `_`, and `-` are accepted; odd-length or non-hex payloads are rejected before send.

Verified non-destructive sequence:

```sh
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl vendor-defined 0 0 0 abc
bin/devicehubctl vendor-defined 0x10000 0 0
```

The first command sends an empty vendor-defined event and follows it with `sendBarrier()`. The latter two commands verify invalid payload and raw-width validation.

Non-empty payload behavior is intentionally not interpreted by the CLI; callers must know the device/vendor usage they are targeting.

## CoreDevice HID Scroll Feature

The standalone scroll feature is implemented through the typed CoreDevice protocol path:

```text
feature = com.apple.coredevice.feature.remote.hid.scroll
class = CoreDevice.IndigoHIDScroll
protocol = CoreDevice.HIDScroll
send(point: CoreDevice.ScrollPoint, phase: CoreDevice.ScrollPhase, momentum: CoreDevice.ScrollMomentum, target: CoreDevice.ScrollTarget)
sendBarrier()
```

The CLI opens the scroll feature socket, builds an `IndigoHIDScroll` object around the Mercury peer, and dispatches the protocol method directly. This is a different path from `UniversalHID.ScrollReport`; it is closer to DeviceKit's Codable event model.

`CoreDeviceUtilities.IndigoScrollEvent` confirms the event layout:

| Offset | Field | Type |
| --- | --- | --- |
| `0x00` | `point.x` | `Double` |
| `0x08` | `point.y` | `Double` |
| `0x10` | `point.z` | `Double` |
| `0x18` | `phase` | `CoreDevice.ScrollPhase`, raw `UInt16` |
| `0x1a` | `momentum` | `CoreDevice.ScrollMomentum`, raw `UInt8` |
| `0x1b` | `target` | `CoreDevice.ScrollTarget`, single-byte enum payload |

Raw values confirmed from `CoreDeviceUtilities.framework` disassembly:

| Type | Name | Raw value |
| --- | --- | --- |
| `ScrollPhase` | `undefined` | `0x00` |
| `ScrollPhase` | `began` | `0x01` |
| `ScrollPhase` | `changed` | `0x02` |
| `ScrollPhase` | `ended` | `0x04` |
| `ScrollPhase` | `cancelled` | `0x08` |
| `ScrollPhase` | `mayBegin` | `0x80` |
| `ScrollMomentum` | `undefined` | `0x00` |
| `ScrollMomentum` | `continue` | `0x01` |
| `ScrollMomentum` | `start` | `0x02` |
| `ScrollMomentum` | `end` | `0x04` |
| `ScrollMomentum` | `willBegin` | `0x08` |
| `ScrollMomentum` | `interrupted` | `0x10` |
| `ScrollTarget` | `digitalCrown` | `0x00` |
| `ScrollTarget` | `dial` | `0x01` |

Verified non-destructive sequence:

```sh
bin/devicehubctl scroll-event 0 0 0 undefined undefined digital-crown
bin/devicehubctl scroll-event 0 0 0 impossible
```

The first command sends a zero-movement event through `CoreDevice.HIDScroll` and follows it with `sendBarrier()`. The second command verifies shell-side name validation before a socket is opened.

Non-zero behavior is not fully enumerated yet. The point values are native `Double` scroll deltas, not normalized touchscreen coordinates.

## UniversalHID Scroll Report

Native scroll report construction is implemented through the verified UniversalHID service report path. The high-level `scroll` command still uses the older touch-swipe implementation; `scroll-report` exposes the lower-level `UniversalHID.ScrollReport` path directly.

Symbol evidence from `UniversalHID.framework`:

```text
UniversalHID.ScrollReport.reportID -> UniversalHID.ReportID.scroll
UniversalHID.ScrollReport.initialReportBitCount
UniversalHID.ScrollReport.init(_report:)
UniversalHID.ScrollReport.scrollCollection setter
UniversalHID.ScrollCollection.init()
UniversalHID.ScrollCollection.flags -> UInt8 setter
UniversalHID.ScrollCollection.phase -> HIDEventPhase setter
UniversalHID.ScrollCollection.momentum -> HIDScrollMomentum setter
UniversalHID.ScrollCollection.x/y -> Swift.Int setters
UniversalHID.ScrollCollection.accelX/accelY -> Double setters
```

The CLI constructs `UniversalHID.HIDReport(bitCount:id:)`, wraps it with `UniversalHID.ScrollReport(_report:)`, creates and populates a `ScrollCollection`, assigns the collection into the report, and sends it to `CoreDevice touchscreenGesture` service `0x501` by default for low-level probes.

Verified non-destructive sequence:

```sh
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-report 0x501 0 0 256
```

The first command sends a zero-movement scroll report successfully. The second command verifies local validation: `phase`, `momentum`, and `flags` are `UInt8`-sized raw values, so `phase=256` is rejected before a report is sent.

## HID Pointer

Pointer input is currently implemented through the verified UniversalHID service report path. There is no standalone `com.apple.coredevice.feature.remote.hid.pointer` feature string in `CoreDevice.framework` on Xcode 27 beta 2.

Symbol evidence from `UniversalHID.framework`:

```text
UniversalHID.PointerReport.reportID -> UniversalHID.ReportID.pointer
UniversalHID.PointerReport.initialReportBitCount
UniversalHID.PointerReport.x/y -> Swift.Int setters
UniversalHID.PointerReport.buttonMask -> UInt8 setter
UniversalHID.PointerReport.accelX/accelY -> Double setters
UniversalHID.PointerReport.flags -> PointerReport.Flags OptionSet setter
UniversalHID.PointerReport.Flags.rawValue -> UInt32 getter
UniversalHID.PointerReport.Flags.init(rawValue:) -> UInt32-backed OptionSet initializer
UniversalHID.PointerReport.Flags.accelerated -> raw value 0x1
```

The CLI constructs `UniversalHID.HIDReport(bitCount:id:)`, wraps it with `UniversalHID.PointerReport(_report:)`, sets relative x/y deltas, button mask, acceleration fields, and raw `PointerReport.Flags` bits, then sends it to the `CoreDevice touchscreenGesture` service (`0x501`) by default.

Verified non-destructive sequence:

```sh
bin/devicehubctl service-id gesture
bin/devicehubctl pointer-report 0x501 0 0 0
bin/devicehubctl pointer-report 0x501 0 0 0 0 0 1
bin/devicehubctl pointer 0 0
```

`PointerReport.Flags` is a UInt32-backed Swift `OptionSet`. Its setter takes an indirect `Flags` value, so the CLI uses a small ABI shim that places the raw UInt32 value on the stack and passes that address to the private setter. `flags=1` matches the framework's static `accelerated` getter; other flag bits still need behavior enumeration.

## HID Keyboard

Keyboard input is implemented through the verified UniversalHID service report path. There is no standalone `com.apple.coredevice.feature.remote.hid.keyboard` feature string in `CoreDevice.framework` on Xcode 27 beta 2.

Symbol and disassembly evidence from `UniversalHID.framework`:

```text
UniversalHID.KeyboardReport.reportID -> 0x01
UniversalHID.KeyboardReport.initialReportBitCount -> 0xf8
UniversalHID.KeyboardReport.index(for:) -> rawUsage + 8
UniversalHID.KeyboardReport.update(with:) -> HIDReport[rawUsage + 8] = 1
UniversalHID.KeyboardReport.keyboardState -> HIDReport byte/bit region at index 0xf0
```

The CLI constructs `UniversalHID.HIDReport(bitCount: 0xf8, id: 0x01)`, sets the usage bit through `HIDReport`'s Swift subscript setter, and sends it to `CoreDevice keyboard` service `0x200`.

Verified sequences:

```sh
bin/devicehubctl key escape
bin/devicehubctl key-down escape
bin/devicehubctl key-up
bin/devicehubctl keyboard-report 0x200 0x29 1
```

## CoreDevice Keyboard / Pointer Capability Adapters

CoreDevice still exposes typed protocols for keyboard and pointer capability use:

```text
CoreDevice.HIDKeyboard
CoreDevice.HIDPointer
CoreDevice.UniversalHIDKeyboard
CoreDevice.UniversalHIDPointer
```

Runtime metadata shows both implementation classes are tiny Swift objects with a single ivar:

| Class | Instance size | Ivar |
| --- | --- | --- |
| `UniversalHIDKeyboard` | `24` bytes | `filter` at offset `0x10` |
| `UniversalHIDPointer` | `24` bytes | `filter` at offset `0x10` |

The `filter` is not the Mercury peer or a feature identifier string. Disassembly shows it contains a boxed UniversalHID capability/filter path:

- `UniversalHIDKeyboard.send(key:state:)` dispatches through witness slot `0x10` to file offset `0x2aa354`, then into `0x2a99ac`.
- The implementation constructs a `UniversalHID.KeyboardReport`-style report, reads `self + 0x10`, and passes the report through the common UniversalHID send helper at `0x2a7b00`.
- `UniversalHIDKeyboard.sendBarrier()` at `0x2a8794` reads `self + 0x10`, projects a boxed existential, and calls the underlying UniversalHID service witness.
- `UniversalHIDPointer` uses async protocol dispatch thunks and the same one-ivar `filter` object shape; no separate pointer feature socket backing class is present.

So the practical CLI abstraction is:

```text
keyboard/pointer reports -> UniversalHIDService.send(report:to:)
button/digitizer/scroll/vendor events -> IndigoHID* typed feature sockets
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
0 = start / begin / began
1 = position / move / changed
2 = end / ended
```

Observed edge values:

```text
0 = none / undefined
3 = bottom / bottom-edge
```

The CLI exposes the raw digitizer event:

```sh
bin/devicehubctl digitizer-event <x1> <y1> <x2> <y2> <point2_tag> <event_type|start|position|end> <edge|none|bottom> [target_low] [target_high]
```

The raw numeric values are still accepted for protocol probing. The named event values are verified through long-press/tap sequencing; `bottom` is verified through the App Switcher edge gesture. Other `DigitizerEdge` and `DigitizerTarget` values are intentionally left raw until enumerated.

Verified high-level use:

- long press: start, repeated position pulses, end
- App Switcher: bottom-edge swipe with `edge = 3`

## Current Gaps

- `connectedServiceDescriptors()` is decoded on the current macOS 27/Xcode 27 beta 2 host and iOS 27 device, but the ABI is private Swift framework ABI and should be re-verified on each beta seed.
- `connectedServices` and `connectedServiceIDs` remain symbol-mapped but are not exposed because the verified DeviceHub path is `connectedServiceDescriptors()`.
- `createService` and `removeService` request cases are identified but not verified.
- The UniversalHID `PointerReport` base fields and raw UInt32 flags are implemented, but flag behavior beyond `accelerated = 0x1` still needs systematic enumeration.
- The UniversalHID `ScrollReport` base fields and standalone `CoreDevice.HIDScroll` zero-event path are implemented and verified, but non-zero scroll behavior, momentum semantics, and target behavior still need full behavior verification.
- The standalone `CoreDevice.HIDVendorDefined` feature is implemented for raw hex payload dispatch, but vendor-specific non-empty payload semantics are not enumerated.
- `CoreDevice.HIDKeyboard` and `CoreDevice.HIDPointer` are symbol-mapped as capability protocols, but their built-in implementations are `UniversalHIDKeyboard` / `UniversalHIDPointer` filter-backed adapters, not standalone feature sockets in this seed.
- Multi-touch second point, `DigitizerTarget`, and `DigitizerEdge` values beyond `none = 0` / `bottom = 3` need systematic enumeration.
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
