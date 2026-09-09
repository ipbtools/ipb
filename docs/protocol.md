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

## Wire Format (captured 2026-09-07)

Interposing `xpc_remote_connection_send_message*` in the helper on Xcode 27 beta 6 / CoreDevice 642.15 shows that every typed CoreDevice path ends up as a plain XPC dictionary on the RemoteXPC socket. There is no Mercury type-name wrapper on the wire, so a client that only speaks XPC dictionaries (C, or pymobiledevice3 from Python) can drive the same device daemon.

UniversalHID service (`featureIdentifier = com.apple.coredevice.feature.remote.universalhidservice`):

```text
send report        {messageType: "Request", featureIdentifier, payload: {send: {_0: <HID report bytes>, _1: <uint64 serviceID>}}}
reset gesture      {messageType: "Request", featureIdentifier, payload: {resetGestureState: {_0: <uint64 serviceID>}}}
connected services {messageType: "Request", featureIdentifier, payload: {connectedServices: {}}}   (sent with reply)
  reply            {connectedServices: [ {Product, DeviceUsagePairs, PrimaryUsagePage, PrimaryUsage, DeviceTypeHint, _ServiceID, ...,
                                          _CoreDevice_codablePropertyStorage: {<key>: {int|uint|bool|string|array|dictionary: value}}} ]}
barrier            {isBarrier: true}   (synchronous, empty dictionary reply)
```

Report bytes seen: keyboard `KeyboardReport` is 31 bytes with report id `0x01`; the touchscreen `DigitizerReport` is 40 bytes with report id `0x09`, for example `09 01 01 c0 ff 7f ff 7f 00…` for a contact at (0.5, 0.5) and `09 00 01 00 ff 7f ff 7f 00…` for the release.

Indigo features (`hid.button`, `hid.digitizer`, `hid.scroll`; `hid.vendordefined` follows the same shape):

```text
{messageType: "IndigoButtonEvent",    featureIdentifier, payload: {usagePage: 12, usageCode: 64, state: 1|2}}
{messageType: "IndigoDigitizerEvent", featureIdentifier, payload: {pointOne: {x, y}, eventType: 0|1|2, edge: 0|3, target: 0}}   (pointTwo omitted when nil)
{messageType: "IndigoScrollEvent",    featureIdentifier, payload: {point: {x, y, z}, phase, momentum, target}}
barrier: {isBarrier: true} as above
```

The device side is `/usr/libexec/dtuhidd` from the Xcode 27 beta DDI. Its launchd plist registers the RemoteXPC services `com.apple.coredevice.hid.universalhidservice` (feature `universalhidservice`), `com.apple.coredevice.hid.universalhid`, and `com.apple.coredevice.hid.indigo` (features button, scroll, digitizer, vendordefined), all with `UsesRemoteXPC = true` and entitlement `com.apple.private.CoreDevice.hid`. `dtuhidd` is absent from the Xcode 26.x DDI (CoreDevice 518.x), which is why those hosts refuse every HID socket with CoreDeviceError 1001.

Host-side prerequisites for the socket path are a connected CoreDevice tunnel (`tunnelState = connected`; otherwise `createservicesocket` fails with CoreDeviceError 4000) and the CoreDevice UUID of the device, not its UDID.

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
bin/ipb service-ids
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
| `send` | positional `_0 = Data`, `_1 = CoreDevice.HIDServiceID` | Verified through CoreDevice protocol dispatch |
| `resetGestureState` | positional `_0 = CoreDevice.HIDServiceID` | CLI exposed, needs broader device testing |
| `connectedServices` | no payload | Symbol present, current Mercury typed sync bridge returns `result=1` |
| `createService` | positional `_0 = CoreDevice.HIDServiceDescriptor` | Legacy XPC wrapper exists, not verified |
| `removeService` | positional `_0 = CoreDevice.HIDServiceID` | Symbol present, not yet wired |

Swift metadata in `CoreDeviceUtilities.framework` confirms the request coding-key layout:

```text
Request.CodingKeys = connectedServices, createService, removeService, send, resetGestureState
CreateServiceCodingKeys = _0
RemoveServiceCodingKeys = _0
SendCodingKeys = _0, _1
ResetGestureStateCodingKeys = _0
ConnectedServicesCodingKeys = <empty>
```

The Mercury peer service name discovered in strings and successful typed send experiments is:

```text
com.apple.coredevice.hid.universal
```

The generated/observed request and reply types are:

```text
CoreDeviceUtilities.DDIUniversalHIDServicePayload.Request
CoreDeviceUtilities.DDIUniversalHIDServicePayload.CreatedServiceID
CoreDeviceUtilities.DDIUniversalHIDServicePayload.ConnectedServices
```

`ConnectedServices` is a struct wrapping:

```text
[CoreDevice.HIDServiceDescriptor]
```

`CreatedServiceID` is a struct wrapping:

```text
serviceID: CoreDevice.HIDServiceID
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

`connectedServiceIDs()` is a protocol extension, not a protocol requirement thunk. A requirement-style async shim is not valid for it; it needs a separate ABI analysis before exposing it safely.

The returned value is native Swift Array storage for `[CoreDevice.HIDServiceDescriptor]`. Runtime value witness metadata shows `HIDServiceDescriptor` is an 8-byte resilient value whose single word is its storage dictionary. The dictionary is `[String: CoreDevice.CodableValue]`; the currently decoded `CodableValue` tags are:

| Tag | Meaning | Payload |
| --- | --- | --- |
| `0x0` | array | Swift Array storage of nested `CodableValue` |
| `0x1` | bool | boxed UInt64, nonzero is true |
| `0x5` | dictionary | Swift Dictionary storage of `String -> CodableValue` |
| `0x8` | unsigned integer | boxed UInt64 |
| `0x9` | `HIDServiceID` | boxed UInt64 service id |
| `0xa` | string | boxed Swift `String` |

On the verified iPhone 13 Pro/iOS 27 device, `bin/ipb descriptors` decodes:

| Service | Product | Primary usage page | Primary usage | Notable fields |
| --- | --- | --- | --- | --- |
| `0x101` | `CoreDevice touchscreen(nil)` | `13` | `4` | `DeviceTypeHint=Digitizer`, `Built-In=true` |
| `0x200` | `CoreDevice keyboard` | `0` | `0` | `DeviceTypeHint=Keyboard`, original usage `{page=1, usage=6}` |
| `0x402` | `CoreDevice mainScreenButtons` | `11` | `1` | `Authenticated=true`, `DisplayIntegrated=true`, also usage `{page=1, usage=6}` |
| `0x500` | `CoreDevice avpCustom` | `65377` | `91` | AVP/vendor custom service |
| `0x501` | `CoreDevice touchscreenGesture` | `1` | `2` | `DeviceTypeHint=Trackpad`, suppresses mouse pointer |

`HIDCTL_VERBOSE_DESCRIPTORS=1 bin/ipb descriptors` prints raw Array, metadata, and value-witness details for future ABI checks.

The shell wrapper exposes descriptor-derived service resolution:

```sh
bin/ipb services              # alias of descriptors
bin/ipb descriptors
bin/ipb service-id touchscreen
bin/ipb service-id gesture
bin/ipb service-id keyboard
bin/ipb service-id buttons
bin/ipb service-id avp
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
bin/ipb uhid-report 0x101 0.5 0.5 1 1
bin/ipb uhid-swipe-report 0x101 0.5 0.5 1 1 0 0 0
bin/ipb keyboard-report 0x200 escape 1
bin/ipb pointer-report 0x501 0 0 0
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-event 0 0 0
bin/ipb vendor-defined 0 0 0
bin/ipb key-up
bin/ipb nav-report 0x101 1 1 0x0d 5 0.0 0.5 0.99
bin/ipb dock-report 0x101 1 1 0x0d 3 0.0 0.5 0.99
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
bin/ipb vendor-defined <usage_page> <usage> <version> [hex_payload]
```

The optional payload is a hex string. Separators ` `, `:`, `_`, and `-` are accepted; odd-length or non-hex payloads are rejected before send.

Verified non-destructive sequence:

```sh
bin/ipb vendor-defined 0 0 0
bin/ipb vendor-defined 0 0 0 abc
bin/ipb vendor-defined 0x10000 0 0
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
bin/ipb scroll-event 0 0 0 undefined undefined digital-crown
bin/ipb scroll-event 0 0 0 impossible
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
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-report 0x501 0 0 256
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
bin/ipb service-id gesture
bin/ipb pointer-report 0x501 0 0 0
bin/ipb pointer-report 0x501 0 0 0 0 0 1
bin/ipb pointer 0 0
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
bin/ipb key escape
bin/ipb key-down escape
bin/ipb key-up
bin/ipb keyboard-report 0x200 0x29 1
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
bin/ipb button 0x0c 0x40
```

Verified volume keys (2026-09-09, iPhone 13 Pro / iOS 27.0, evidence: sent standalone through
`bin/ipb button`, then `bin/ipb screenshot` showed the system volume HUD on the device):

| Key | usagePage | usageCode | Evidence |
| --- | --- | --- | --- |
| Home | `0x0c` | `0x40` | earlier capture, above |
| Volume up | `0x0c` | `0xE9` | **screenshot: volume HUD visible** |
| Volume down | `0x0c` | `0xEA` | standard paired Consumer usage; send returns 0, but the HUD is
  visually identical to volume up so this was **not** distinguished on its own |

These are HID Consumer-page usages sent through the **button feature**
(`com.apple.coredevice.feature.remote.hid.button`), which is a different service socket from the
UniversalHID touchscreen. Note that none of the device's five HID descriptors advertises the
Consumer page (`0x0c`) in `DeviceUsagePairs` — the button feature accepts these usages regardless,
so the descriptor list is not the authority on what the button path will take.

Not established: usage codes for Lock/side button, Siri, Action Button and Camera Control. Apple's
DeviceHub does expose all of them (`DeviceKit.framework` carries
`com.apple.devicekit.menu.controls.hardwareGestureControls.{actionButton,sideButton,lock,siri}`),
but the last two do not appear in its menu with a 13 Pro attached, because that framework gates them
per device with `ConditionalKeyboardShortcut`. Attaching a device that has the button is the route to
observing their codes.

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
bin/ipb digitizer-event <x1> <y1> <x2> <y2> <point2_tag> <event_type|start|position|end> <edge|none|bottom> [target_low] [target_high]
```

The raw numeric values are still accepted for protocol probing. The named event values are verified through long-press/tap sequencing; `bottom` is verified through the App Switcher edge gesture. Other `DigitizerEdge` and `DigitizerTarget` values are intentionally left raw until enumerated.

Verified high-level use:

- long press: start, repeated position pulses, end
- App Switcher: bottom-edge swipe with `edge = 3`

## Current Gaps

- `connectedServiceDescriptors()` is decoded on the current macOS 27/Xcode 27 beta 2 host and iOS 27 device, but the ABI is private Swift framework ABI and should be re-verified on each beta seed.
- `connectedServices` remains symbol-mapped but is not exposed because the verified DeviceHub path is `connectedServiceDescriptors()`.
- `connectedServiceIDs()` is symbol-mapped as a protocol extension; it still needs a separate extension ABI bridge before exposure.
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

## UniversalHID report IDs

Decoded statically from `static UniversalHID.<T>Report.reportID.getter` in
`/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/Frameworks/UniversalHID.framework/Versions/A/UniversalHID`
(UniversalHID 90.1) — each getter is a single `movz w0, #imm`, read directly from the Mach-O.

| ID | Report | ID | Report |
| ---: | --- | ---: | --- |
| 2 | `ConsumerReport` | 13 | `NavigationSwipeReport` |
| 3 | `AppleVendorKeyboardReport` | 14 | `ZoomToggleReport` |
| 4 | `AppleVendorTopCaseReport` | 15 | `ScaleReport` |
| 5 | `PointerReport` | 16 | `RotationReport` |
| 6 | `ButtonReport` | 17 | `TranslationReport` |
| 7 | `ScrollReport` | 18 | `GameControllerReport` |
| 9 | `DigitizerReport` | 19 | `AbsolutePointerReport` |
| 11 | `DockSwipeReport` | 20 | `GenericGestureReport` |
| 12 | `FluidTouchGestureReport` | 21 | `TouchSensitiveButtonReport` |

`ipb` currently builds only ID 7 (scroll), ID 9 (digitizer) and ID 5 (pointer).

### Captured: DeviceHub sends AbsolutePointerReport continuously

Captured live with lldb on Xcode 27 beta 6's DeviceHub, breakpoint on
`CoreDevice.UniversalHIDService.send(report:to:)`, following the report object's pointer at +16
(the object header is isa / refcount / bytes pointer / length, with length 19 here). Three
consecutive sends while the operator was using the window:

```
13 d1 8b 00 00 22 03 01 00 00 00 60 87 c2 d6 13 01 ...
13 46 8b 00 00 6d 02 01 00 00 00 bd 35 11 d8 13 01 ...
13 4a 85 00 00 f6 fc 00 00 00 00 7c 1d 12 d8 13 01 ...
```

Byte 0 is the report ID, `0x13` = 19 = **`AbsolutePointerReport`**. Bytes 1-2 and 5-7 vary per send
and look like coordinates; bytes 11-15 increase monotonically and look like a timestamp.

Call site (matching the path traced by disassembly):

```
CoreDevice  UniversalHIDService.send(report:to:)
DeviceKit   sub_435b04 + 100
libswift_Concurrency   (async task)
```

**This is a report type `ipb` never sends.** It suggests DeviceHub keeps an absolute cursor position
on the device, which may be a precondition for scroll reports to have any effect — our scroll
reports are accepted and ignored, and we never establish a pointer position. **Hypothesis, not
established:** testing it needs `AbsolutePointerReport` construction plus a same-connection
sequence, since a per-process CLI test cannot carry pointer state between invocations.

There is no lock/unlock action among CoreDevice's 61 `com.apple.coredevice.action.*` identifiers
(only the read-only `lockstate`), so Lock is delivered as a HID report. How, exactly, is still
unknown; see "Lock: what is ruled out" below.

**Retracted.** An earlier record here reported that DeviceHub's Lock shortcut does not hit
`init(_report:)` on any of the five keyboard-family report types. That test was invalid:
`init(_report:)` is a reinterpret wrapper, not a construction path, so breakpoints on it measure an
empty set regardless of what DeviceHub sends. Only three event-based constructors exist in
UniversalHID. The negative proved nothing and is withdrawn.



## HIDEventType (source: disassembly, UniversalHID 90.1)

Each `HIDEventType` static member's getter is a single `mov w0, #imm; ret`, decoded statically.
All 42 values match IOKit's public `IOHIDEventType` enum, so this is Apple's standard event
vocabulary rather than a UniversalHID-private one.

| Value | Name | Value | Name | Value | Name |
| --- | --- | --- | --- | --- | --- |
| 0x00 | null | 0x0f | temperature | 0x1e | unicode |
| 0x01 | vendorDefined | 0x10 | navigationSwipe | 0x1f | atmosphericPressure |
| 0x02 | button | 0x11 | pointer | 0x20 | force |
| 0x03 | keyboard | 0x12 | progress | 0x21 | motionActivity |
| 0x04 | translation | 0x13 | multiAxisPointer | 0x22 | motionGesture |
| 0x05 | rotation | 0x14 | gyro | 0x23 | gameController |
| 0x06 | scroll | 0x15 | compass | 0x24 | humidity |
| 0x07 | scale | 0x16 | zoomToggle | 0x25 | collection |
| 0x08 | zoom | 0x17 | dockSwipe | 0x26 | brightness |
| 0x09 | velocity | 0x18 | **symbolicHotKey** | 0x27 | genericGesture |
| 0x0a | orientation | 0x19 | **power** | 0x29 | forceStage |
| 0x0b | digitizer | 0x1a | led | 0x2a | touchSensitiveButton |
| 0x0c | ambientLightSensor | 0x1b | fluidTouchGesture | | |
| 0x0d | accelerometer | 0x1c | **boundaryScroll** | | |
| 0x0e | proximity | 0x1d | biometric | | |

Three of these matter for open questions and are highlighted above:

- `symbolicHotKey` (0x18) and `power` (0x19) exist as event types but **have no corresponding
  report struct**. UniversalHID ships exactly 20 report structs and neither appears among them, so
  a lock cannot be sent as a dedicated power report; it has to travel inside one of the
  keyboard-family reports.
- `boundaryScroll` (0x1c) is a *distinct* event type from `scroll` (0x6). Our `ScrollReport` is
  accepted and ignored; whether DeviceHub emits scroll, boundaryScroll, or both during a trackpad
  scroll is unresolved.

## Report sizes (source: disassembly, UniversalHID 90.1)

`static <T>.initialReportBitCount` is likewise a constant getter. This is the size a report starts
at; setting fields in a higher bit range grows it, which is why `DigitizerReport` starts at 320 bits
but needs 464 once contact-0 swipe bits (424/429/434) are written.

| Report | ID | Initial bits | Bytes |
| --- | --- | --- | --- |
| ButtonReport | 6 | 16 | 2 |
| ZoomToggleReport | 14 | 16 | 2 |
| AppleVendorKeyboardReport | 3 | 24 | 3 |
| RotationReport | 16 | 32 | 4 |
| ScaleReport | 15 | 32 | 4 |
| AppleVendorTopCaseReport | 4 | 40 | 5 |
| GenericGestureReport | 20 | 48 | 6 |
| TranslationReport | 17 | 48 | 6 |
| ConsumerReport | 2 | 72 | 9 |
| ScrollReport | 7 | 104 | 13 |
| PointerReport | 5 | 136 | 17 |
| AbsolutePointerReport | 19 | 152 | 19 |
| KeyboardReport | 1 | 248 | 31 |
| GameControllerReport | 18 | 304 | 38 |
| DigitizerReport | 9 | 320 | 40 |
| TouchSensitiveButtonReport | 21 | 440 | 55 |

`AbsolutePointerReport` at 152 bits / 19 bytes independently confirms the `HIDReport` heap layout:
the `HIDReport.init(bitCount:id:)` call captured at runtime had `x0 = 0x98` (152) and `x1 = 0x13`
(19 — which is also the AbsolutePointer report ID), and produced a 19-byte buffer at `+16` with its
length at `+24`.

Note that `ScrollReport`'s initial size is 104 bits, matching what `ipb` originally hardcoded. The
104 -> 168 change made earlier was therefore not a truncation fix for scroll — the fields we write
all fit inside 104 bits. It remains correct for `DigitizerReport` (320 -> 464), which is where the
truncation was real.

## Lock: what is ruled out (source: runtime capture + disassembly)

Established:

- Cmd-L in DeviceHub reaches `UniversalHID.KeyboardFilter.filterEvent(_:)` via
  `UniversalHIDKit.EventObserver.processEvent(_:)` and a `Sequence.reduce(into:_:)` filter chain
  (25 breakpoint hits with the full stack).
- It does **not** reach `CoreDevice.HIDButton.sendCustomButton`, `CoreDevice.HIDKeyboard.send`, or
  `CoreDevice.HIDVendorDefined.send` (0 hits across the same capture).
- Only all-zero `KeyboardReport` (ID 1) **release** reports were captured (`01 00 00 ... 00`). The
  press report carrying the key was never captured.
- Keyboard usages `0x66`, `0x82` and `0x32` were each sent to the device and none lock the screen.
  This was A/B controlled against a no-action run (experiment 9,940,630 bytes bright vs control
  9,935,071 bytes bright) after two earlier conclusions that `0x66` locks were both traced to the
  device's own fast auto-lock rather than to the report.

The next tap is `UniversalHID.KeyboardFilter.updateCopyMask(oldValue:newValue:) -> [HIDReport]`
(UniversalHID `0x5b0bc`). It takes two `HIDEventMask` values — an `OptionSet` over `UInt`, so plain
integers in `x0`/`x1` — and returns the built reports directly, which makes it the shortest path
from a key transition to wire bytes. See `docs/devicehub-tracing.md`.

## Lock (source: runtime capture + on-device A/B)

**`ipb lock` sends Consumer page `0x0c`, usage `0x30` (`kHIDUsage_Csmr_Power`), held.**

The hold is the whole trick. Measured on iPhone 12 mini / iOS 27:

| Hold | Result |
| --- | --- |
| 0.08 s | no effect |
| 0.15 s | no effect |
| 0.25 s | no effect |
| 0.40 s | no effect |
| 0.45 s | no effect (brightness 130.9) |
| 0.50 s | **locks** (brightness 0.0) |
| 0.60 s | **locks** (brightness 0.0) |

`ipb lock` defaults to 0.7 s for margin above the 0.45/0.50 edge.

Evidence that this is a real lock and not the device's own auto-lock:

- Matched-elapsed A/B, two pairs, every step timed to keep the trial inside the
  device's auto-lock window: experiment 0.0 brightness, control 131.5. The earlier failed
  attempt at this used a window longer than the device's auto-lock (which dims at ~2 s and
  blanks between 6 s and 10 s), so both arms blanked and the result was meaningless.
- Waking the device afterwards shows the **lock screen** — padlock, clock, flashlight and
  camera affordances — not the Home screen, so the device is locked rather than merely dark.

Why three earlier rounds missed it: every candidate tried (`0x66`, `0x82`, `0x32`) was sent on
the Keyboard page via `ipb key`, i.e. the `KeyboardReport` (ID 1) path. The Consumer page was
never tested, because the "ConsumerReport is not hit" result that ruled it out came from
breakpoints on `init(_report:)` — a reinterpret wrapper rather than a construction path, so that
test measured an empty set. A short press on the correct usage also does nothing, so even a
correct guess would have looked like a failure without the hold.

Consistent with the rest of the device's Consumer mapping already verified here: Home is
`0x0c/0x40` (`kHIDUsage_Csmr_Menu`) and volume is `0x0c/0xE9`/`0xEA`.

**Unlock is not solved.** A short `0x0c/0x30` press does not wake a locked device
(0.0 brightness before and after), and the device requires a passcode once locked.
