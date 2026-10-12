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

**Provenance.** The envelope shapes above were captured at the send boundary. The early examples
below came from **ipb's own helper**, not Device Hub: the old helper emitted a 31 B KeyboardReport
and a 40 B DigitizerReport, with `09 01 01 c0 ff 7f ff 7f 00…` down and
`09 00 01 00 ff 7f ff 7f 00…` up at (0.5, 0.5). They are historical pre-fix output, not current
framing or a Device Hub oracle.

Current ipb allocations are Keyboard **39 B** and Digitizer **58 B**, and its digitizer lift keeps
count=1. Device Hub's actual tap, drag, keyboard and system-confirmation Cancel reports were captured
on 2026-09-21; see “Device Hub digitizer, keyboard and target IDs” below for the measured seed, raw
bytes, service IDs, remaining field differences and effect boundaries.

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
| `UniversalHID.DigitizerReport` | `reportID = 0x09`, `bitCount = 0x140` initial, grown to `0x1d0` (464) when contact-0 swipe bits are set | contact index, touch, range, resting, x, y, contact count, max count |
| `UniversalHID.KeyboardReport` | `reportID = 0x01`, `bitCount = 0x138` (312, the descriptor size; was `0xf8` = 248 until 2026-09-21) | keyboard usage bit at `usage + 8` |
| `UniversalHID.PointerReport` | queried from framework | x, y, button mask, accel x, accel y, raw UInt32 flags |
| `UniversalHID.ScrollReport` + `ScrollCollection` | queried from framework | collection flags, phase, momentum, x, y, accel x, accel y |
| `UniversalHID.NavigationSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |
| `UniversalHID.DockSwipeReport` | queried from framework | phase, swipe mask, gesture motion, flavor, progress, x, y |

Low-level CLI commands. **These are raw probes, not working features.** Every one of them is
accepted by the service and returns `rc=0`; for `uhid-swipe-report`, `pointer-report`,
`scroll-report`, `scroll-event`, `vendor-defined`, `nav-report` and `dock-report` **no device effect
has ever been demonstrated**, and `nav-report`/`dock-report` additionally rest on a premise that was
later retracted. Use them to probe the protocol, not to drive a device.


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

The CLI constructs `UniversalHID.HIDReport(bitCount: 0x138, id: 0x01)` — `initialReportBitCount` is `0xf8`, but the descriptor specifies 312 bits and Apple's own reports are 39 bytes on the wire, so the builder allocates the descriptor size —, sets the usage bit through `HIDReport`'s Swift subscript setter, and sends it to `CoreDevice keyboard` service `0x200`.

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

The living list of open items for the project as a whole is the head of `docs/verification.md`;
this section covers only the protocol-level gaps, refreshed after the 2026-09-22 capture:

1. **Tap fields differ, but the observed differences are not a demonstrated failure cause.**
   The 2026-09-21 capture below shows Device Hub's count/max, identity and nonzero timestamp;
   ipb's count/size and service target agree, while max/identity/timestamp differ.
2. **Keyboard size is fixed at 39 B.** Device Hub's 39 B reports and `0x200` target were captured
   while typing `ipb` into Settings search; timestamp parity is still absent.
3. **Service targets are now observed:** digitizer `0x101`, keyboard `0x200`, AbsolutePointer and
   Scroll `0x501`. Button menu actions use the typed Indigo socket, not a UniversalHID report.
4. **Scroll acceleration and momentum remain uncalibrated.** The complete historical phase
   sequence is captured, but `accelX = dx/40` and the decay are not established by it. The latest
   synthetic wheel produced only a zero-movement may-begin report and no visible scroll.
5. **Permission prompts remain operation-specific.** Remove App Cancel works in both clients;
   Settings Allow Paste was reproduced and accepted for synthetic test text. The original TCC
   prompt remains unverified; neither success generalizes to every privacy prompt.

Older ABI-surface gaps, still accurate:

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

**This question is now closed, and `updateCopyMask` was not the answer.**
`UniversalHID.KeyboardFilter.updateCopyMask(oldValue:newValue:) -> [HIDReport]` (UniversalHID
`0x5b0bc`) was proposed as the next tap and then bound: **zero hits** across the ⌘L capture
(`docs/verification.md`, 2026-09-09 second capture). The capture that did land is below, under
"Lock: Device Hub does not send it over UniversalHID" — ⌘L puts only the Command modifier on the
wire, and Device Hub locks through some other channel. `ipb lock` reaches the same result by an
independently verified route (Consumer `0x0c`/`0x30`, held).

## Lock (source: runtime capture + on-device A/B)

**`ipb power` sends Consumer page `0x0c`, usage `0x30` (`kHIDUsage_Csmr_Power`), held.**
`ipb lock` and `ipb wake` are the same press under different names.

This is the side button, and like the side button it **toggles**: a screen that is on goes off
and locks, a screen that is off wakes to the lock screen. Verified by driving it in both
directions from a state confirmed by screenshot each time:

| From | Hold | Result |
| --- | --- | --- |
| bright | 0.70 s | dark |
| dark | 0.08 s | stays dark |
| dark | 0.20 s | stays dark |
| dark | 0.40 s | stays dark |
| dark | 0.70 s | **wakes** |

The hold is the whole trick, and the threshold is the same in both directions. Measured on
iPhone 12 mini / iOS 27, locking an awake screen:

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

Waking stops at the **lock screen** — padlock, clock, camera and flashlight affordances. The
passcode itself is not bypassed and remains the user's to enter.

**Correction.** An earlier record here stated that unlock was unsolved, on the grounds that a
short `0x0c/0x30` press does not wake a locked device. The press does not wake it because it is
short, not because waking is impossible: the same 0.7 s hold that locks also wakes. The
conclusion generalised a single 0.08 s trial into a property of the whole route.

## Scroll: the full sequence Device Hub sends (source: runtime capture)

Captured at `UniversalHIDService.send(report:to:)` (the `HIDServiceID` overload) while an operator
performed two two-finger trackpad scrolls over a Settings list, 2026-09-09.

A single trackpad scroll is **not** one report. It is:

| Order | Report | flags | momentum | x, y | Meaning |
| --- | --- | --- | --- | --- | --- |
| 1 | AbsolutePointer (19) ×N | — | — | position | establishes where the pointer is |
| 2 | Scroll (7) ×1 | `0x80` | 0 | 0, 0 | may-begin; carries no movement |
| 3 | Scroll (7) ×1 | `0x01` | 0 | first delta | began |
| 4 | Scroll (7) ×N | `0x02` | 0 | deltas | changed — the actual movement |
| 5 | Scroll (7) ×1 | `0x04` | 0 | 0, 0 | ended; carries no movement |
| 6 | Scroll (7) ×N | `0x00` | 2, then 1 | decaying deltas | momentum / inertia tail |

Observed twice in one window, once per physical scroll.

### Wire layout, confirmed against these bytes

21 bytes / 168 bits (not the 104-bit `initialReportBitCount`):

```
07 02 00 00 fb f4 fd ff ff 6e da ff ff 52 0c 79 06 46 01 00 00
|  |  |  |  |  \__________/ \__________/ \____________________/
|  |  |  |  |   accelX       accelY       remoteTimestamp
|  |  |  |  y (int8)
|  |  |  x (int8)
|  |  momentum
|  flags (phase)
report ID 7
```

`accelX`/`accelY` are 32-bit signed 16.16 fixed point. `remoteTimestamp` occupies bytes 13-20 and
is populated on every report.

### Why `ipb`'s scroll is accepted and ignored

`ipb` sends a single `ScrollReport` and nothing else. Compared with the above it is missing:

1. **Any `AbsolutePointer` report.** Device Hub keeps the pointer position current; `ipb` never
   sends report ID 19 at all.
2. **The `0x80` may-begin and `0x01` began reports.** `ipb` sends a bare movement report with no
   phase opening.
3. **The `0x04` ended report and the momentum tail.**
4. **`remoteTimestamp`**, which `ipb`'s builder leaves unset.

The pointer requirement is directly evidenced rather than inferred: with the pointer resting on
the list, a two-finger scroll produced 67 `Scroll` reports; with the pointer moved outside the
phone view, the same gesture produced **zero** `Scroll` reports and only `AbsolutePointer` traffic.
Device Hub itself will not emit a scroll report unless the pointer is over the view.

## Lock: Device Hub does not send it over UniversalHID

Cmd-L in Device Hub produces exactly **two** reports at the send boundary, both `KeyboardReport`
(ID 1), 39 bytes:

```
press    01 00 ... 00 08 00 4a 52 10 bd 45 01 00 00
                     ^^ byte 29
release  01 00 ... 00 00 00 91 aa ce bf 45 01 00 00
```

They differ in one byte. Byte 29 bit 3 is absolute bit **235**; `ipb`'s own builder maps a usage to
`bit = usage + 8`, so bit 235 is usage **227 = 0xE3 = Keyboard Left GUI**, i.e. the Command
modifier. Bytes 31-38 are `remoteTimestamp`.

So what crosses the wire for Cmd-L is **Command down, Command up, and nothing else**. The "L" is
consumed by AppKit as a menu shortcut and never reaches the device, and no lock command appears at
`UniversalHIDService.send` either — during that window the universal tap captured these two reports
and no others, while capturing 497 reports across the run as a whole.

Device Hub therefore locks the phone through some channel that is not UniversalHID. **That channel
was identified on 2026-09-21 and it is not exotic: it is the Indigo button socket,
`CoreDevice.HIDButton.sendButton`, carrying the same Consumer usage `ipb` already sends.** See
"Device Hub's buttons: captured" below. The open question in this section is closed; what kept it
open was that `taps.tsv` bound only `UniversalHIDService.send`, so the Indigo sockets could not
have produced a hit no matter what Device Hub did.

At the time of this capture, `ipb` allocated 31 B for the 39 B keyboard report. The allocation
was fixed to `0x138` = 312 bits on 2026-09-21; ipb still does not set its remote timestamp.


## Report descriptors: the authoritative field map (2026-09-20)

Source: `static <T>.descriptor.getter` in host `UniversalHID` 90.1 (CoreDevice 642.15), dumped and
parsed by `Experiments/hid-descriptors/`. This is **Rule 1 source 3** (shipped metadata), and it is
stronger than the captures below it: Apple's encoder sizes reports from the same descriptor via
`HIDReportDescriptor.reportBitCount(for:)`, so it is the allocation authority on both sides.

The method is self-validating — parsing reproduces every offset previously obtained by capture:

| report | descriptor | ipb allocates | agrees? |
| --- | --- | --- | --- |
| DigitizerReport (ID 9) | 464 bits / 58 B | 464 (`digitizerReportBitCount`) | yes |
| ScrollReport (ID 7) | 168 bits / 21 B | 168 (`scrollReportBitCount`) | yes |
| AbsolutePointerReport (ID 19) | 152 bits / 19 B | 152 | yes |
| **KeyboardReport (ID 1)** | **312 bits / 39 B** | **312 bits / 39 B** (`uhidHIDReportInit(0x138, …)`, fixed 2026-09-21; was `0xf8` = 248) | **yes** |
| AppleVendorKeyboardReport | 88 bits / 11 B | n/a | — |

**The KeyboardReport gap was a live defect, fixed on 2026-09-21** (verified on the wire: the report
is now 39 bytes, with the usage bit still at `usage + 8`). The missing 8 bytes were the trailing
`remoteTimestamp` field, and the timestamp setter *no-ops* on a report shorter than 39 B — so adding
a timestamp later without fixing the allocation would silently do nothing.

### DigitizerReport (ID 9), 464 bits

| bits | field | notes |
| --- | --- | --- |
| 0–8 | report ID = 9 | |
| 8–16 | `Digitizer/ContactCount` | **number of contacts described by THIS report**, logical max 5 |
| 16–24 | `Digitizer/ContactCountMaximum` | |
| 24–224 | five finger collections, 40 bits each at `24 + 40i` | |
| … +0 | `Digitizer/ContactIdentifier` (5b) | what ipb sets via `SetIndex` |
| … +5 | `0xff1a/0xe0f2` (1b) | resting |
| … +6 | `Digitizer/Touch` (1b) | |
| … +7 | `Digitizer/InRange` (1b) | |
| … +8 | `GenericDesktop/X` (16b) | |
| … +24 | `GenericDesktop/Y` (16b) | |
| 224–320 | embedded ScrollCollection | flags 224, momentum 232, X i8 240, Y i8 248, accelX 256, accelY 288 |
| 320–360 | `0xff1a/0xe0f4` × 5 (8b each) | per-contact identity — **ipb never sets this** |
| 360–424 | `AppleVendor/0x102` × 8 (8b each) | **`remoteTimestamp`** — ipb never sets this |
| 424–459 | `0xff1a/0xe062…0xe068`, seven × 5b | swipe flags: pending424, locked429, up434, down439, left444, right449, cancel454 (setters verified2026-09-22) |
| 459–464 | padding | |

### What this says about `ContactCount`

`makeDigitizerReportData` now sends `contactCount = 1` on both down and lift, describing contact 0
with Touch/InRange cleared on lift. The earlier `touching ? 1 : 0` implementation is historical.
The latest Device Hub down/up capture independently confirms count 1 on both reports. The earlier
locked-screen experiment remains void; neither this agreement nor the later Cancel success proves
that the count change fixed the original permission-prompt failure.


## Device Hub's buttons: captured (source: runtime capture, 2026-09-21)

Seed: host macOS 27 beta, Xcode 27.0 Beta 6, DeviceHub 27.0, CoreDevice 636.3, device iPhone 13 Pro
on iOS 27.0, wired. lldb attached to `DeviceHub` with **all ten** CoreDevice HID send paths bound
(`Experiments/devicehub-trace/taps-full.tsv`); an agent drove Device Hub's own `Controls` menu while
the tracer recorded. A no-input baseline window recorded **zero** reports, so the counts below are
traffic, not noise.

Every hit landed on `CoreDevice.HIDButton.sendButton<A>(page:code:state:)` — the **typed generic**
overload. `sendCustomButton` (the non-generic `Int, Int, state` variant) took zero hits, as did all
three `UniversalHIDService.send` overloads and every other Indigo socket.

| Device Hub menu action | usage code | states sent | calls |
| --- | ---: | --- | ---: |
| Home | `0x40` | 0, 1 | 2 |
| **App Switcher** | **`0x40`** | **0, 1, 0, 1** | **4** |
| Lock | `0x30` | 0, 1 | 2 |

State `0` is the press and `1` the release (they arrive in that order); this is the Swift enum's
case index, which the wire encoding renders as `1|2` — see the Indigo payload shape above.

### Reading the page requires dereferencing

`sendButton` is generic over `HIDUsagePageProtocol`, so `page`, `code` and `state` are passed
**indirectly**: the argument registers hold pointers, not values, and the usage page is carried by
the *generic type parameter* rather than by any value. Reading the registers directly yields stack
addresses and says nothing about which button was pressed — the tracer needs an explicit
dereference (`"deref"` in the tap spec). The page's type-metadata pointer was identical across all
three actions in a run, so all three ride one page; the usage values themselves
(`0x40` = Consumer AC Home, `0x30` = Consumer Power) match Consumer page `0x0c` exactly.

### What this confirms, and the one place ipb differs

- **Home** — `ipb` sends Consumer `0x0c`/`0x40` (`cd_home_button`). **Identical to Device Hub.**
  Confirmed against Apple's own client for the first time rather than assumed.
- **Lock** — `ipb` sends Consumer `0x0c`/`0x30` (`ipb power`/`lock`/`wake`). **Identical to Device
  Hub.** The route `ipb` arrived at independently is the route Apple uses.
- **App Switcher — this is the divergence.** Device Hub has **no dedicated App Switcher usage**. It
  presses **Home twice**. `ipb`'s `cd_recents_button` instead sends AppleVendorKeyboard
  `0xff01`/`0x10`, found by trial and screenshot-verified working (2026-09-14), which is a
  different mechanism that happens to produce the same result. `ipb` already contains
  `cd_home_double_button` (`send_coredevice_button_double_click(remote, 0x0c, 0x40)`), which is
  exactly what Device Hub does; it is simply not what `recents` is wired to.

  Both work on device. Recorded as a known divergence, not a defect: switching `recents` to the
  double-press would trade a verified one-event path for Apple's four-event path, and that is a
  behaviour change that needs its own on-device evidence before it is made.


## Device Hub digitizer, keyboard and target IDs (runtime capture, 2026-09-21)

Seed measured for this run: **macOS 26.5.1 (25F80), Xcode 27 Beta 6, Device Hub 27.0 (255.2.3.5), CoreDevice 642.15,
iPhone 13 Pro iOS 27.0 (24A437), wired**. This is distinct from the seed labels in older records.
All ten entries in `Experiments/devicehub-trace/taps-full.tsv` resolved before input. The initial
capture had a zero-input baseline, 14 digitizer reports and 4 typed button calls, with no shed taps.
The follow-up capture had 21 calls, no shed taps, and clean detach/target survival. The decoder
reads the first eight little-endian bytes of dereferenced `x2` as the service ID.

| Actual operation | Entry/report | Observed target and fields |
| --- | --- | --- |
| Settings tap; Settings drag; Remove App menu and Cancel | `uhid_send_id`, Digitizer ID 9, 58 B | `0x101`; count=1, max=5; contact identifier=2, identity=2; Touch/InRange=1/1 down, 0/0 up; timestamp nonzero |
| Type `ipb` in Settings search | `uhid_send_id`, Keyboard ID 1, 39 B, six reports | `0x200`; down/up pairs; timestamps nonzero; text visibly arrived |
| Pointer movement | `uhid_send_id`, AbsolutePointer ID 19, 19 B | `0x501`; four reports in follow-up capture |
| Synthetic wheel on Settings list | `uhid_send_id`, Scroll ID 7, 21 B | `0x501`; only phase `0x80`, zero movement; no visible scrolling |
| Siri menu | `indigo_button_typed` | dereferenced code `0xcf`, states 0 then 1 about 0.509 s apart; full page representation not decoded; no visible Siri UI |
| Rotate Left then Right | Native window observation | phone preview rotated and restored; native device screenshot remained portrait; zero calls on the ten HID taps during rotation |

Representative normal tap, preserving raw bytes:

```text
down 090105c2189c28b200000000000000000000000000000000000000000000000000000000000000000200000000159c521a3b1800000000000000
up   09010502189c28b200000000000000000000000000000000000000000000000000000000000000000200000000d89c551a3b1800000000000000
service ID bytes: 0101000000000000
```

The system Cancel pair also used `0x101`, count=1/max=5, contact identifier/identity=2,
X=32798, Y=41395, and timestamps 26648605825097 / 26648606276108. The current ipb tap uses
max=1, identifier=0, and unset identity/timestamp. These are measured differences, not reasons to
change fields blindly: the same Cancel action succeeded with current ipb and with Device Hub.

The synthetic wheel trace does **not** characterize a physical trackpad gesture or disprove Device
Hub scrolling. It confirms target selection only. A later orientation query proved that Rotate
also changes device orientation, despite no HID sends; see the next section. Record Screen and
Action Button were disabled in Device Hub's Controls menu on this phone. No capability is inferred
merely from a menu label. See `docs/devicehub-alignment.md` for outstanding functional parity work.


## Deeper keyboard, display and orientation observations (2026-09-21)

**Sources:** actual Device Hub HID captures, devicectl JSON/error output and shipped binary symbols.
Same seed as above: macOS 26.5.1 (25F80), Xcode 27 Beta 6, Device Hub 255.2.3.5, CoreDevice 642.15,
iPhone 13 Pro / iOS 27.0 (24A437). DeviceKit build 255.2.3 is at
`/Applications/Xcode-27.0.0-Beta.6.app/Contents/SharedFrameworks/DeviceKit.framework/Versions/A/DeviceKit`.
Raw evidence is local in `~/.local/state/ipb/20260921-deep/`; source revision `c14eed6`.

### Keyboard reports describe a set of held usages

With Capture Keyboard enabled and Settings search focused, `typeText("aA1!")` produced 12 reports
of 39 B targeting `0x200`. Decoding usage bits at `usage + 8` gave:

```text
{4}, {}, {225}, {4,225}, {4}, {}, {30}, {}, {225}, {30,225}, {30}, {}
```

These are A, Shift, and digit-1 combinations. Command+A followed by Backspace emitted
`{227}, {4,227}, {4}, {}, {42}, {}` and visibly cleared the field. The single-key builder currently
sets one usage bit, so repeatedly invoking that builder cannot preserve a held modifier across
another key. A chord/capture implementation needs a set, not just independently timed key clicks.

The actual text from `aA1!` was **`啊A1!`**, with the phone's Pinyin keyboard visible. This shows
that correct key reports do not guarantee literal text. The exact input-method transformation was
not separately instrumented. Synthetic `typeText("中文🙂")` emitted no call on the ten HID taps and
left the search field empty. Native host paste of test text timed out waiting for a clipboard read;
only four `0x200` reports appeared: `{227}, {25,227}, {25}, {}` (Command+V), with no visible insertion.
These are CUA-operation observations, not a proof that every real IME path is unsupported.

Device Hub's Edit menu separately exposes **Use Shared Clipboard / Get Clipboard / Send Clipboard**;
ordinary Paste was disabled when inspected. Installed `devicectl device pasteboard --help` exposes
copy, paste, info, monitor, transfer and sync-with-host. The existing ipb UTF-8 clipboard round-trip
is historical device evidence; focused Unicode insertion is not yet verified. In the current
clipboard state, `pasteboard info` failed with **26006**, identifying `com.apple.is-remote-clipboard`
as a transient/confidential/already-synchronized type. The contents were not read or overwritten.
That error is not assigned as the proven cause of the earlier paste timeout.

### Device, content and preview orientations are distinct

Before Rotate Left, `ipb orientation` and `device info displays` reported portrait. After clicking
Device Hub's Rotate Left button:

- `orientation.currentDeviceOrientation` and `currentDeviceNonFlatOrientation` became
  `landscapeLeft`; `currentDeviceOrientationLocked` remained false.
- The primary display's `currentOrientation` stayed **rot0**, with native size/bounds
  **1170 x 2532**. Settings remained portrait in the native screenshot.
- Device Hub displayed a rotated phone preview. Clicking General in that preview opened General.
- The rotation itself produced no call on the ten HID taps. The typed CoreDevice
  `OrientationControl.rotate(direction:)` symbol is separately present (0x39b348); it is a static
  candidate for the non-HID path, not a captured call in this run.

The rotated click emitted Pointer ID 19 on `0x501` with raw x/y **55659 / 46451**, then Digitizer
ID 9 on `0x101` with contact x/y **19084 / 55658**. Using the respective report scales, these are
approximately pointer **(0.8493, 0.7088)** and touch **(0.2912, 0.8493)**. Their relationship is
consistent with `(touchX,touchY) = (1-pointerY,pointerX)` for this one orientation. Do not generalize
it to all orientations without the remaining matrix. It does demonstrate that the two service
coordinate pairs need not be identical. Portrait was restored and queried afterward.

Static support for a geometry layer: DeviceKit `HIDEventGeometry.init` at **0x4241e8** accepts
windowToViewTransform, viewToUnitTransform, viewFrame, edgeSwipeRegion, roiUnitRect and
orientationCorrection. `DisplayInfo.normalizedCurrentOrientation` is at **0x6c79ec** and
`displaySizeAtCurrentOrientation` at **0x6c7ab4**. These symbols support the separation above;
the exact internal matrix composition remains untraced.

### Current display/capability JSON is available without a new ABI shim

`devicectl device info displays --device <uuid> --json-output <path>` returned:

```text
result.backlightState = activeOn
result.displays[primary=true]:
  displayId=1, type.integrated={}, bounds=[[0,0],[1170,2532]], nativeSize=[1170,2532],
  pointScale=3, nativeOrientation=rot0, currentOrientation=rot0
result.orientation:
  currentDeviceOrientation, currentDeviceNonFlatOrientation, currentDeviceOrientationLocked
```

While Device Hub viewed the phone, a second non-primary **Wireless** entry had displayId=2,
nativeSize=1184x2544 and pointScale=1. After quitting Device Hub only the primary LCD remained.
This is a session-dependent inventory observation, not proof of a persistent external display.

`device info details` returned `result.capabilities` entries with featureIdentifier and name.
The list contains `getdisplayinfo`, `remote.devicecontrol.orientation`, `pasteboard` and
`startaudiooutput`. It does **not** contain Screen Recording or `audiooutput` (Audio Output Device
Selection). `device info audio` failed with **1001**, naming the missing `audiooutput` capability.
Media audio transport, audio-device selection and screen recording must therefore be represented
separately. Advertised presence alone is not proof that opening or using a feature will succeed.


## Display, literal text and rotated edge alignment (2026-09-22)

**Seed:** macOS 26.5.1 (25F80), Xcode 27 Beta 6, DeviceHub 27.0 (255.2.3.5), DeviceKit 255.2.3,
CoreDevice 642.15, UniversalHID 90.1, DDI 27A5252f (live `device info ddiServices` metadata),
wired iPhone 13 Pro / iOS 27.0 (24A437). These findings supersede the earlier single-orientation/text
uncertainty only within the measured scope.

### Display and input spaces — runtime plus static evidence

`device info displays` supplies one explicit primary LCD (`displayId:1`, nativeSize 1170x2532,
pointScale 3, nativeOrientation rot0) and separate device/content orientation values. During landscape
Calculator, device landscapeRight accompanied display rot90; landscapeLeft accompanied rot270.
Settings can retain display rot0 while device direction changes. A non-primary Wireless entry
was present while Device Hub viewed the screen and must not replace the primary screen's geometry.

Additional captured Device Hub pointer→native touch pairs, with report quantization:

| Device direction | Pointer x,y | Digitizer x,y | Observed inverse mapping |
| --- | --- | --- | --- |
| portrait | .27690,.84976 | .27689,.84974 | x,y |
| landscapeLeft | .84929,.74358 | .25643,.84929 | 1-y,x |
| portraitUpsideDown | .72270,.14868 | .27729,.85132 | 1-x,1-y |

The first landscapeRight click capture was invalidated by another task's concurrent device
orientation changes and is not evidence. The inverse quarter-turn mapping for that direction was
subsequently validated by ipb's actual Settings/Calculator click effects, not a claimed valid
Device Hub pointer pair. Final native mirror clicks worked at all four device directions.

Static DeviceKit at the path in the preceding section: `windowToUnitTransform` at 0x424400 composes
its matrices without the extra pointer rotation; pointer variant 0x424464 adds a centered rotation.
This supports keeping pointer and touchscreen mappings separate. The current implementation uses
explicit inverse device rotation for touch and presentation coordinates for pointer; content
orientation is used for edge classification. Physical rotated-scroll calibration remains open.

`devicectl device info displays --stream --json-output - --timeout 5` emitted human updates on
stderr, with only a final timeout JSON envelope on stdout. The mirror therefore polls structured
snapshots, one in flight, rather than treating human text as a protocol. A snapshot is not an atomic
frame-orientation epoch; the preview may lag an external change by a refresh interval.

### Literal focused paste — actual effect evidence

Device Hub Command+V after copying `ipb-中文🙂 A1!` inserted that exact text into Settings search
with Pinyin active. The new `ipb text` did the same with Device Hub keyboard capture disabled.
It writes the device clipboard once, then sends the earlier captured 39 B held sets
`{0xe3}`, `{0xe3,0x19}`, `{0x19}`, `{}` on the resolved keyboard service. This does not imply a
Unicode HID report or full mirror keyboard capture. Clipboard contents are replaced, not restored.

A later fresh test displayed Settings' “Allow Paste from dtpasteboardd” permission prompt. After
explicitly allowing this synthetic test paste, the exact field appeared. Thus clipboard copy and
HID submission can succeed while insertion awaits application policy; rc0 cannot certify text
acceptance. `ipb text` does not approve permission dialogs. The smoke field check now rejects
that modal instead of accepting its large pixel difference.

### Rotated bottom-edge touch flags — capture and setter evidence

A separate Device Hub trace resolved all 10 taps, captured 8 calls, shed none and detached with rc0.
The landscapeRight Calculator bottom swipe returned Home using four 58 B Digitizer reports on 0x101;
no Indigo digitizer call occurred. Native x moved 65535→53538→40026 with y=32802; the final report
cleared Touch/InRange but still described one contact. All four tails at bytes 53–57 were
`20 00 10 00 00`. The portrait Settings edge control also returned Home; its tails were
`20 04 00 00 00`. These tails are locked+left and locked+up respectively, including on UP.

Static setters in
`/Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework/UniversalHID`
(version 90.1) confirm the contact-index-relative offsets:

| Field | Setter address | Base bit |
| --- | --- | --- |
| pending |0x53344|424|
| locked |0x533d0|429|
| up |0x5345c|434|
| down |0x534e8|439|
| left |0x53574|444|
| right |0x53600|449|
| cancel |0x5368c|454|

The corresponding immediate adds are 0x1a8, 0x1ad, 0x1b2, 0x1b7, 0x1bc, 0x1c1, 0x1c6.
The new rotated-edge builder uses the captured count 1 / max 5, identifier 2 / identity 2, native x/y,
remote timestamp, locked plus exactly one native direction, and retains flags on UP. Mapping
content rot0/90/180/270 to up/left/down/right follows the native-axis transform; the down case is
static/geometry evidence only, without a real upside-down-content app in this run.

A trace of ipb confirmed its rotated edge bytes and count-1 UP matched this shape. Controlled 300 ms
sequences from the same builder returned Home at both landscape directions. Approximately 6 ms
CUA mirror drags did not; no production timing interpolation was added. Portrait-content mirror
edges retain the existing Indigo path, which still returned Home with CUA's short drag.

The ordinary HIDReport-returning builder had retained count 0 on UP even though the separate Data
builder was already fixed. Both now share the byte construction with count 1 on UP. Ordinary
max 1 / identifier 0 / identity 0 / timestamp 0 remains unchanged. Host tests inspect actual framework-backed
reports, and the installed real-device gate exercises tap/swipe/key/text again. Raw swipe probes
are not promoted to verified high-level commands by this change.

## Accessibility Inspector and AXAudit (2026-09-22)

**Evidence boundary.** macOS 26.5.1 (25F80), Xcode 27 Beta 6, Accessibility Inspector 5.0
(192.6), production iPhone 13 Pro / iOS 27.0 (24A437), Developer Mode and DDI services enabled.
This is a research path, not an ipb command or the supported macOS 27 release gate.
Apple's DTX message-construction arguments and property-reply objects were captured with LLDB;
independent pymobiledevice3 11.10.2 requests then reproduced the reads. No XCTest runner,
jailbreak, injected code or additional phone-side server was installed for these tests.

### Transport and service discovery

Host disassembly of Xcode's bundled `AccessibilityAuditDeviceManager.framework` shows
`XDMDeviceMonitorEmbedded._connectToDevice:` calling `AMDeviceSecureStartService`, then
`AMDServiceConnectionGetSocket` and `initWithConnectedSocket:disconnectAction:`. Its query path
constructs `DTXMessage` and calls `sendControlAsync:replyHandler:`. These are **static** host facts;
the AMDevice service-start argument was not captured in this run.

The iPhone's **live RSD advertisement** contains:

| Service | UsesRemoteXPC | Advertised entitlement | This run |
| --- | --- | --- | --- |
| `com.apple.accessibility.axAuditDaemon.remoteserver.shim.remote` | false | `com.apple.mobile.lockdown.remote.trusted` | Connected through `PreferredRsdTunnel` and exercised DTX control-channel reads |
| `com.apple.accessibility.axAuditDaemon.remoteAXService` | true | `AppleInternal` | Advertisement only; not opened and no access outcome established |

The working path is RSD tunnel → AXAudit remoteserver shim → DTX → Apple's AXAudit service.
It is distinct from the HID feature/Mercury dictionaries above. The absence of an AX daemon in a
DDI inventory or of CoreDevice linkage in one host framework cannot establish that AX is absent
from RSD; the older lockdown-only architectural inference is superseded. `deviceApiVersion`
returned **26** on this iOS 27 device; this number is not the OS version.

### Focus, property descriptors and partial hierarchy

`deviceCapabilities` advertised property reads, parameterized reads, focus navigation, preview,
normalized-coordinate lookup and screenshot selectors. Advertisement does not establish effects.
The independent probe used the existing pmd3 focus setup (`deviceSetAppMonitoringEnabled:`,
`deviceInspectorSetMonitoredEventType:`, `deviceInspectorMoveWithOptions:`). The resulting
`hostInspectorCurrentElementChanged:` event carries `AXAuditInspectorFocus_v1`, including:

- `ElementValue_v1`: an `AXAuditElement_v1` whose `PlatformElementValue_v1` was 20 bytes here.
  Treat the token as opaque; no lifetime or cross-session stability is established.
- `CaptionTextValue_v1`, `SpokenDescriptionValue_v1`.
- `InspectorSectionsValue_v1`: `AXAuditInspectorSection_v1` objects containing
  `ElementAttributesValue_v1` descriptors. The caption-only CLI omits these descriptors.

Inspector's captured read is `deviceElement:valueForAttribute:` with **two object arguments**:
the transported element and the transported descriptor supplied by the device. Using `P(x)` below
solely as shorthand for `{"ObjectType":"passthrough","Value":x}`, the captured hierarchy request is:

```text
element = {ObjectType: "AXAuditElement_v1", Value: P({
  PlatformElementValue_v1: P(<opaque bytes>)
})}
attribute = {ObjectType: "AXAuditElementAttribute_v1", Value: P({
  AttributeNameValue_v1: P("_AXHierarchyElementsAttribute"),
  HumanReadableNameValue_v1: P("Hierarchy"),
  DisplayAsTree_v1: P(true), DisplayInlineValue_v1: P(false),
  IsInternal_v1: P(false), PerformsActionValue_v1: P(false),
  SettableValue_v1: P(false), ValueTypeValue_v1: P(2)
})}
```

Other captured/read descriptor names include `Label`, `Value`, `TraitsHumanReadable`, `Identifier`,
`Hint`, `UserInputLabels`, `ElementClassName`, `ElementMemoryAddress` and
`ElementViewControllerClassName`. Their type/flag values vary: reuse the received descriptor.
Do not accidentally execute descriptors marked `PerformsActionValue_v1` while enumerating values.

The hierarchy reply is recursively transported `AXAuditNode_v1`, containing
`AuditElementValue_v1`, optional `ChildrenValue_v1`, `HumanReadableDescriptionValue_v1`,
`HumanReadableRoleDescriptionValue_v1`, and `IsIgnoredValue_v1`.
The Looktech Lab heading query returned 15 nodes, a `UILabel` class and its address; screenshot
inspection confirmed the visible heading. This is a focus-related AX hierarchy, **not proof of a
complete UIView dump or enumeration of all visible/offscreen nodes**. In Settings, two different
focus entries returned labels/traits but only one hierarchy node and nil class/address. The cause
of this difference is not established; do not infer a signing/entitlement rule from two apps.

### Geometry and remaining unknowns

**Page-dump follow-up on the same seed.** Moving focus with `Direction.Next` until an opaque
element token repeated produced 36 distinct focus tokens. Querying each focus element's supplied
read-only descriptors and merging hierarchy replies by token yielded 131 nodes / 130 observed
edges under one Looktech Lab root. The 252 property reads took about 14.4 seconds including
traversal. The result includes window/container structure, buttons, text, images and tab controls;
the JSON and readable tree remain local research outputs, not a product command.

This is a **temporal union**, not an atomic or completeness-verified tree. Before/after screenshots
show that focus traversal automatically scrolled from the top to the lower part of the page.
Two distinct UILabel tokens both described the home heading; equal labels must not be used to
merge identities. A repeated focus token proves a traversal cycle, not coverage of ignored,
unmaterialized or otherwise inaccessible views. Element bounds remain unresolved.

A separate attempt to recursively query discovered hierarchy handles, without advancing focus
after its seed, reached 99 nodes before a property timeout. Its before/after screenshots showed
Settings while the returned root still named Looktech Lab: foreground pixels and the AX target
can disagree in this probe. After relaunching and visually confirming Lab, a fresh session received
app-state events but no focus seed within the three-second budget. Neither attempt validates a
static full-tree algorithm. Target synchronization and query liveness require investigation;
their causes are unknown, and app monitoring was disabled during cleanup.

- `Frame` and `AXFrame` were **candidate names**, based on host-side strings; they were not advertised
  descriptors in these iOS focus events. Both returned nil in the tested Lab and Settings queries.
- `deviceFetchElementAtNormalizedDeviceCoordinate:` exists in the host implementation and device
  capabilities. Host disassembly packages a `CGPoint` in `NSValue`. A local Foundation archive
  established `NS.pointval` + `NS.special=1` encoding. Constructed requests at three normalized
  points returned nil, both before and after explicit inspector setup. No successful Apple
  reference request was captured, so these negatives do not establish an unsupported API.
- `deviceInspectorPreviewOnElement:` followed by `deviceCaptureScreenshot` returned a PNG plus
  `displayBounds={{0,0},{390,844}}`, `displayNativeScale=3`, `rotationRadians=0`, and
  `shouldFlipOutline=true`. The PNG was 1170×2532 and visibly outlined the selected text in green.
  This reply had no `borderFrame` or structured element rectangle. Display geometry is not element
  geometry. Preview was cleared and cleanup was checked with a fresh screenshot.
- The `ElementRectValue_v1` seen in pmd3 belongs to **audit issues**, not to ordinary focus/node
  values. It is not a substitute for a verified element-frame query.

Host sources are under
`Xcode-27.0.0-Beta.6.app/Contents/Applications/Accessibility Inspector.app/Contents/Frameworks/AccessibilityAuditDeviceManager.framework`
and `Contents/SharedFrameworks/AccessibilityAudit.framework`.
The upstream comparison is
[pymobiledevice3 at 10194d12](https://github.com/doronz88/pymobiledevice3/blob/10194d12e7cf17453887b7ac3d46e1b85b5a057a/pymobiledevice3/services/accessibilityaudit.py),
which lacks wrappers for these property/point queries and an `AXAuditNode_v1` decoder.

### AXAudit root handles and hierarchy limits (2026-09-22)

This follow-up separates **reanalysis of the recorded physical-device replies** from **offline
binary evidence**. No device connection was made while the iPhone was loaned to LookInside.

The 36 recorded Lab hierarchy replies contain **14–46 nodes per reply**; 131 is their temporal
union. In the separate expansion run, querying the captured application root returned **two
nodes**, UIWindow returned four, and deeper queries added local context and ancestors. Thus a
root query has already been tried; these recordings do not show a single full-page reply.
The 96 completed expansion queries include 13 nil replies. The next queued handle at the timeout
was the tab bar, inferred from the probe's iteration order; this does not establish the timeout's
cause. DTX replies are matched by message ID, so queued app events alone do not prove starvation
or explain the previously observed target mismatch.

**Physical iOS 27 static source:** the arm64e AXRuntime in Xcode's cached
`iPhone14,2 27.0 (24A437)/Symbols/System/Library/PrivateFrameworks/AXRuntime.framework/AXRuntime`.
`_AXUIElementCreateData` at `0x18f83384c` serializes 4 + 8 + 8 bytes from fields at offsets
`0x10`, `0x14`, `0x1c`; `_AXUIElementCreateWithData` at `0x18f83377c` reverses that layout.
`_AXUIElementCreateWithPIDAndID` at `0x18f833680` identifies the first field as PID.
`_AXUIElementCreateAppElementWithPid` at `0x18f82a0d8` sets the two remaining fields to zero and
the global at `0x1e45262e8`, whose stored initializer is one. For a remote application's PID,
the resulting candidate is `struct.pack("<IQQ", pid, 0, 1)` on this seed. The captured Lab root
matches `(7513, 0, 1)` exactly. Every handle in the recorded 131-node and 99-node unions carries
PID 7513; a later Lab app-state event reports PID 7534. Old handles cannot be assumed to identify
that later process instance. At this offline stage a directly constructed root remained untested;
the dated live result follows below. Product
handles remain opaque, and this layout is not a cross-version contract.

**Concrete implementation comparison, simulator only:** the local iOS 26.5 runtime `iOS_23F77`
contains arm64 `System/Library/PrivateFrameworks/AccessibilityAudit.framework/Support/axauditd`.
Its Objective-C method metadata and selector stubs establish the following executable paths:

| Path | Static behavior on the simulator seed |
| --- | --- |
| `XADInspectorManager.fetchSpecialElement:` at `0x1000056d4` | Value 0 obtains `firstElementInHierarchy:` from `frontmostAppForTargetPid`; value 1 obtains `lastElementInHierarchy:`; other values produce nil. This is not an arbitrary application-root enum. |
| `XADAuditServer.deviceSetAuditTargetPid:` at `0x10000b9a8` | Calls the superclass and manager's `setTargetPid:`. The manager at `0x10000551c` matches `AXAuditPidForElement` against current applications. `frontmostAppForTargetPid` at `0x100005660` falls back to the first current application when no match exists. With visuals enabled the server can also change focus; target selection is not necessarily observational. |
| Normal property handler at `0x100004f1c` | Returns nil for a previously focused element that differs from the current element. It checks `AuditDoesAllowDeveloperAttributes(PID)` for restricted attributes; an arbitrary attribute name does not imply a generic AX read. |
| `_AXHierarchyElementsAttribute` branch at `0x1000054d0` | Calls helper `0x100004cdc`, which combines the queried node's children, its siblings and an ancestor chain. It does not recursively enumerate every descendant. Walking parents also checks the developer-attribute predicate. |
| Direct-child helper at `0x100004b88` | Adds children through index 50, then stops (`0x100004c10`, `0x100004c60`–`0x100004c64`): at most 51 children. Closure over returned handles cannot prove that unreturned siblings do not exist. |
| Parameterized RPC at `0x10000a038` | Decodes typed `AXAuditElement` and `AXAuditElementAttribute` objects, then forwards `withObject:`. The concrete manager at `0x10000550c` immediately calls completion with nil; it never reaches `AXUIElementCopyParameterizedAttributeValue`. Supplying numeric 95006 is not an established forwarding mechanism. |

These paths explain why the simulator interface must not be treated as a generic AX proxy. They
do **not** prove the physical iOS 27 daemon has the same filters, cap, fallback or nil handler.
The cached iOS 27 AccessibilityAudit image contains base stubs rather than this concrete daemon.
Its `AuditDoesAllowDeveloperAttributes` at `0x24fdcd750` also differs from the simulator predicate:
it calls an unresolved shared-cache target at `0x2500f90b0` with process/task-like arguments and
accepts a zero return. The image imports `task_for_pid` and `mach_task_self_`, but the call target
has not been conclusively resolved; do not equate this with a verified entitlement rule.

Physical probes use a fresh observed PID, validate every reply's process identity, stop on
timeout, retain partial/nil results and avoid declaring an observed graph complete.
Root construction, target binding, service access and tree coverage are separate experiments.

### Physical root query and separate Mirroring AX channel (2026-09-23)

On the wired iPhone 13 Pro, iOS 27.0 **24A437**, an RSD/AXAudit session accepted an application
root handle constructed from the **freshly observed** Looktech Lab PID 7720 using the seed-specific
`<IQQ` layout above. The read-only `_AXHierarchyElementsAttribute` descriptor was copied from the
earlier captured Inspector reply. A one-call root probe returned exactly two nodes, as before.
Two independent bounded expansions then queried **129 handles each**, with **zero nil replies**
and **zero timeouts**, taking 6.35 and 7.42 seconds. Both runs produced identical token-labelled
node content. The screenshots before and after showed the same Lab home page; no focus move,
scroll, install, Runner or UI activation was sent.

Hierarchy replies repeat ancestors and context. Merging all returned child edges created two
false double-parent edges. Selecting the queried node's children **from that node's own reply**
produced a connected **129-node, 128-edge tree**, one root, one parent per other node, and all
discovered handles queried. The tree included the visible Home heading, Settings button,
connection card, reminder/translation/notes controls and tab bar, as well as reachable elements
below the viewport. This proves an executable runner-free element-tree read on this page/seed.
It does not prove a single atomic device snapshot, a complete UIKit `subviews` tree, a lack of
AX child caps, cross-app coverage, or usable element rectangles. The local research probe retains
`complete_ui_snapshot=false`, `atomic=false`, and labels graph closure separately.

The same device advertised these RSD entries: `remoteAXService` (`UsesRemoteXPC=true`,
`AppleInternal`), `testmanagerd.remote.automation` (`UsesRemoteXPC=false`, `AppleInternal`), and
ordinary `testmanagerd.remote` (`UsesRemoteXPC=false`, private client entitlement). Advertisement
did not establish access. `remoteAXService` terminated its RemoteXPC handshake. The automation
port accepted TCP, but a five-second generic DTX capability exchange timed out; a second bounded
attempt with no capability exchange and proxy identifier
`dtxproxy:XCTDRemoteAutomationClient:XCTDRemoteAutomationServer` also timed out. Ordinary
`testmanagerd.remote` completed the generic DTX exchange immediately on this same device/host.
All sockets were closed. These results establish the tested host exchanges' limits, not the
internal-policy predicate's value or the exact reason automation failed. No snapshot RPC was sent.

On a **different device state**, the wired iPhone 12 mini / iOS 27.0 24A437 exposed a paired RSD
tunnel while Developer Mode was disabled. Its 62 advertised services included only the ordinary
AXAudit `remoteserver.shim.remote` entry among the services tested here; no `testmanagerd` entry
was present. The AXAudit DTX connection opened, then `deviceCapabilities` ended with
`ConnectionTerminatedError: Channel is closed`. CoreDevice separately refused DDI installation
with Cryptex error 20, explicitly citing disabled Developer Mode. This is an observed correlation,
not proof that the AXAudit channel closed because of that setting; repeat after a Developer Mode
state change before claiming causality. A subsequent bounded test obtained Settings PID 1843
from the already advertised `com.apple.os_trace_relay.shim.remote` `PidList` service without DDI.
It sent a read-only `_AXHierarchyElementsAttribute` request on a fresh AXAudit DTX connection
**without** capability preflight; the connection closed without an AX reply. Thus preflight alone
does not explain the failure. A bounded on-device `os_trace_relay` capture around a repeat request
shows `lockdownd` activating the Mach name
`com.apple.accessibility.axAuditDaemon.deviceservice.lockdown`, then reporting
`failed to do a bootstrap look-up: xpc_error=[3: No such process]`; its socket closes without an
AX reply. This directly places the immediate failure at service lookup on this physical device.
Separately, the **iOS 26.5 simulator** runtime `iOS_23F77` contains
`System/Library/LaunchDaemons/com.apple.accessibility.axAuditDaemon.deviceservice.plist` with the
same Mach name and `LimitLoadToDeveloperMode=true`. That simulator metadata is consistent with
the 12 mini's disabled Developer Mode, but the physical iOS 27 launchd plist has not been read and
no enabled/disabled A/B was performed. Do not promote the inferred setting-to-service causality
to a physical-device fact yet. No successful tree query was obtained on this device in that state.

### 12 mini enabled-state AXAudit cross-target check (2026-09-23)

After the user enabled Developer Mode and restarted the **same iPhone 12 mini** (iOS 27.0
24A437), `ipb ps` succeeded and CoreDevice reported `ddiServicesAvailable=true`. RSD advertised
85 services, including both `testmanagerd.remote` entries, versus 62 in the disabled/no-DDI
state. `axauditd` was present in the process list, and `deviceCapabilities` now replied with
`deviceElement:valueForAttribute:`. The physical before/after comparison establishes that the
combined Developer Mode, reboot and DDI state change restores this AXAudit path. It does not
isolate the precise launchd gate; the iOS 27 device plist remains unread.

A screenshot showed the SpringBoard Home page. Its fresh PID 204 was obtained through the
existing `os_trace_relay` `PidList` service. The seed-specific `<IQQ>(204,0,1)` app root plus the
captured read-only `_AXHierarchyElementsAttribute` descriptor returned ten nodes in one request.
A 300-query budget discovered 373 handles and stopped at its budget, so that result is partial.
Two larger independent sessions each queried **444 discovered handles**, with zero nil or timeout
replies and an observed closure. Each queried node's direct children were taken from its **own**
reply, not from repeated ancestor context. Two parent replies each repeated one identical child
token; deduplicating these exact duplicates yielded one connected **444-node/443-edge** tree per
session. The sessions had the same token set, descriptions except the changing clock, and child
sets; Utilities-folder child order differed. They were not byte-identical snapshots. Before/after
screenshots showed the same Home icons and dock, with the expected clock change.

For an ordinary foreground app, `ipb launch com.apple.calculator` opened the preinstalled
Calculator without installing anything. A fresh PID 2450 root produced a **45-node/44-edge**
single-root observed tree twice, with zero nil/timeout replies and identical normalized
tree content. The keys `7`, `8`, `9`, operators, History and Change Mode matched the screenshot; the
read-only queries did not move focus or press a key. Candidate `Frame` and `AXFrame` descriptors
sent against the `7 Keyboard Key` both returned nil. A separate `AXAction-2010` press submitted
through installed pymobiledevice3 11.10.2's `AccessibilityAudit.perform_press` did not change
the calculator's displayed zero; submission was not a verified activation. The phone was
returned to Home afterward. These two targets establish
runner-free element-tree reads across SpringBoard and a system app on this device/seed, not an
atomic/all-views snapshot, a usable element rectangle, or element-activation support.
On the final Home page, the advertised read-only `deviceRunningApplications` returned `[]` and
`deviceCurrentState` returned `0`; neither supplied a foreground PID in this check. The working
root queries therefore used a separately observed process list plus screenshots for target
selection. A production foreground-binding contract remains unresolved.

A separate **offline** host path exists in macOS 26.5.1 (25F80), iPhone Mirroring 1.6,
`ScreenSharingKit` dyld-cache image UUID `C6D042A9-EE7E-3F13-9599-69DD1CB1A572`.
`ScreenContinuityUI` uses `ScreenSharingSession.accessibilityDataPublisher`,
`AccessibilityClientPrimitives.startAccessibility` and `processAccessibilityDataFromClient`.
The concrete `AXPBackedAccessibilityClientPrimitives` uses
`AccessibilityPlatformTranslation.AXPHostCacheManager`'s translation transport. Its
`AXPHostCacheOverlayView.accessibilityChildren` (`0x1D99F878C`–`0x1D99F8874`) obtains a translated
application element, converts it to `AXPMacPlatformElement`, and returns its accessibility
children. This is executable host code for an NSAccessibility tree backed by remote data;
Mirroring session authentication, AX payload schema and access by an independent host client were
not tested. No Mirroring session was started.

## XCTest snapshot service boundary (2026-09-22)

**Static evidence only.** Inspected the arm64 slices in the Mac-local image
`/Library/Developer/DeveloperDiskImages/iOS_DDI/Restore/022-22070-094.dmg`, mounted read-only.
Its `version.plist` records DDI **27A5252f**, variant **Public**, build **1335**, XCTest **25227**
and CoreDevice **642.15**; host is macOS 26.5.1 with Xcode 27 Beta 6. This is not a new device
DDI inspection or live service test. The iPhone was exclusively loaned to another task throughout.

Sources below are image-relative paths; addresses are unslid arm64 virtual addresses from
`nm -arch arm64 -nm`, `otool -arch arm64 -tvV` and `dyld_info -arch arm64 -fixups`:

- **T:** `usr/libexec/testmanagerd` (installed program path `/System/Developer/usr/libexec/testmanagerd`).
- **U:** `Library/Frameworks/XCUIAutomation.framework/XCUIAutomation`.
- **A:** `Library/PrivateFrameworks/XCTAutomationSupport.framework/XCTAutomationSupport`.
- **P:** `Library/LaunchDaemons/com.apple.dt.testmanagerd.plist`.

### Snapshot processing is in the device daemon

The traced classic runner path is:

```text
XCAXClient_iOS / XCTRunnerDaemonSession (XCUIAutomation in the caller)
  → _XCT_requestSnapshotForElement:attributes:parameters:reply:
  → XCTestSession in device testmanagerd
  → XCAXManager_iOS.snapshotForElement:attributes:parameters:timeoutControls:error:
  → XCTElementSnapshotRequest (XCTAutomationSupport)
  → XCTAccessibilityFramework.userTestingSnapshotForElement:options:error:
  → AXUIElementCopyParameterizedAttributeValue(element, 95006, options)
```

| Evidence | Address and observed call |
| --- | --- |
| Client RPC | U `XCTRunnerDaemonSession` snapshot delegate at `0x6fa70` calls `daemonProxy` and `_XCT_requestSnapshotForElement:attributes:parameters:reply:` at `0x6fbb8`. Its newer `fetchSnapshot…` variant starts at `0x6fbf4`. |
| Device receiver | T `XCTestSession._XCT_requestSnapshot…` at `0x10002f41c` first checks UI-testing readiness, then calls its `axManager` snapshot method at `0x10002f4b4`. `_XCT_fetchSnapshot…` starts at `0x10002f538`. |
| Snapshot construction | T `XCAXManager_iOS.snapshotForElement…` at `0x10000c080` creates `XCTElementSnapshotRequest` and calls `loadSnapshotAndReturnError:`. A implements that method at `0x1073c`, then `accessibilitySnapshotOrError:` at `0x12d04`. |
| AX request | A `XCTAccessibilityFramework.userTestingSnapshotForElement…` at `0x9a38` calls `AXUIElementCopyParameterizedAttributeValue` at `0x9b94`; the preceding instructions construct parameterized attribute `0x1731e` / **95006** and pass the element and options. |

This identifies the device-side XCTest RPC processor and its AX query boundary. It does not trace
all downstream AX IPC, establish a live snapshot's completeness, or imply a raw `UIView.subviews`
dump. The daemon's code signature includes `com.apple.accessibility.api` and
`com.apple.springboard.testautomation`; the host does not acquire those privileges by linking U/A.

### Three distinct connection paths

| Entry | Session/transport | Established boundary |
| --- | --- | --- |
| `com.apple.dt.testmanagerd.runner` | Device-local NSXPC → `XCTestSession` | P declares a Mach service; T startup calls `startAcceptingTestConnectionsFromListener:` at `0x1000049d0`. This is the runner-side RPC path, not an advertised host stream in P. |
| `com.apple.dt.testmanagerd.remote` | Remote stream → DTX → `XCTDPendingHarnessSession` → `XCTDHarnessSession` | P declares `UsesRemoteXPC=false`, `RequireEntitlement=com.apple.private.dt.testmanagerd.client`. Startup registers service type **0** at `0x100004954`. This is the host test-control path. |
| `com.apple.dt.testmanagerd.remote.automation` | Remote stream → DTX → `XCTDRemoteAutomationSession` | P declares `UsesRemoteXPC=false`, `RequireEntitlement=AppleInternal`. Startup registers service type **1** at `0x1000049a4`, conditionally as described below. This object directly implements snapshot/attribute requests. |

`UsesRemoteXPC=false` does not mean no RSD tunnel; it describes the service payload transport.
Remote-service entitlement metadata is not, by itself, proof that a host executable must carry the
same signing entitlement. P also lists `com.apple.dt.testmanagerd.remote.runner` under
**MachServices**, not RemoteServices; its name alone does not establish another host entry.

T's service dispatch at `0x100034f74` distinguishes types 0 and 1. The type-0 branch constructs
`XCTDPendingHarnessSession` at `0x100035018`; its proxy handler constructs `XCTDHarnessSession`
at `0x10007c530`. Type 1 constructs `XCTDRemoteAutomationSession` at `0x1000350e4`.
The latter's initializer at `0x10001f438` uses `DTXSocketTransport` and `DTXConnection` and
registers the protocol pair `XCTDRemoteAutomationServer` / `XCTDRemoteAutomationClient` at
`0x10001f6d0`. Class/protocol identities were resolved using fixups and symbol addresses, not
otool's unresolved `bad class ref` annotations.

The direct protocol has `_XCTD_requestSnapshotForElement:attributes:parameters:` and
`_XCTD_fetchSnapshotForElement:attributes:parameters:`. The fetch implementation begins at
`0x100021f3c`; its block calls `automationServices.axManager.snapshotForElement…` at
`0x100022248`. `_XCTD_fetchAttributes:forElement:` begins at `0x10002240c`.
Thus the direct snapshot implementation is real code, not just an unused selector string.
Its on-wire object encoding and a valid live capability/session exchange remain unverified.

### Authorization gates and what they prove

1. **Listener registration gate.** T startup calls `hasAppleInternalSecurityPolicies` at
   `0x100004964`; a false result skips the automation listener. That class method at
   `0x100034304` directly calls
   `os_variant_allows_internal_security_policies("com.apple.testmanagerd")`.
   This is a device OS-policy gate in addition to P's `AppleInternal` declaration.
2. **Automation Mode gate.** After constructing a remote automation session, T calls
   `enableAutomationModeForClient:error:` at `0x100035114`. Failure reaches socket closure,
   with the log “Rejecting connection for remote automation because Automation Mode is not
   enabled”. A listener/socket alone is not a usable snapshot session.
3. **Runner-local gate.** `XCTestSession` initialization at `0x10002bb6c` reads its NSXPC
   peer's `com.apple.private.dt.xctest.internal-client` and `get-task-allow` entitlements.
   `canSkipAutomationMode` at `0x10002c4f0` returns the internal-client flag;
   `allowsUITestControl` at `0x10002c52c` otherwise checks `isAutomationModeEnabled`.
   `ensureUITestingIsReadyWithTimeout:error:` at `0x10002e800` rejects a failed check with
   code **41**, “Not authorized for performing UI testing actions.” These are actual gate
   conditions, not a claim that `get-task-allow` alone authorizes every snapshot.

Automation Mode here is the daemon's named state; it must not be equated with the Settings
Developer Mode switch without additional evidence. The actual value of the internal-policy
predicate on the loaned production phone was **not measured**.

The installed pymobiledevice3 **11.10.2** source independently distinguishes transport/session
setup from running tests. `services/dvt/testmanaged/xcuitest.py:54-68,136-202` selects ordinary
`.remote`, initializes control/main proxy sessions, then launches a runner, authorizes its PID,
waits for its reverse driver channel and starts the test plan. Its
`dtx_services.py:551-581` declares the control/session/PID interfaces. This proves what that
implementation does; it does not prove a live runner-free snapshot path or that every control
RPC needs a runner PID.

**Current conclusion:** the inspected seed contains a direct remote snapshot implementation,
but behind explicit internal-policy and Automation Mode gates. Connecting the ordinary host
control service is insufficient evidence that it exports the runner/automation snapshot object.
This does not prove all runner-free AX approaches impossible; the separately exercised AXAudit
shim above remains relevant. No ipb feature or support promise follows from this static result.

**Next device experiment, only after exclusive ownership returns:** inventory the actual RSD
services, then use bounded connection attempts to distinguish advertisement, service-start
permission and DTX/session success. Record exact errors. Ordinary control-session negotiation
can be measured separately, without launching a runner or fabricating a PID; it is not a snapshot
success criterion. If the automation service is accessible, establish its protocol/capabilities
and valid element handles before attempting one snapshot. Connection establishment can itself
request Automation Mode, so account for that state change and clean up the session. If this
entry is unavailable, keep that seed-specific result and continue AXAudit target/liveness work.
