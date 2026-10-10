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
Its `AuditDoesAllowDeveloperAttributes` at `0x24fdcd750` also differs from the simulator predicate.
The previously unresolved shared-cache call at `0x2500f90b0` was resolved against raw caches
fetched from the physical 24A437 device on October 9: it branches to `task_for_pid`, and the
first argument comes from `mach_task_self_`. The predicate accepts a zero return. See the
[resolved predicate and development-app control](#axaudit-development-app-action-and-resolved-task-port-predicate-2026-10-09).
This identifies the function, not every concrete daemon caller or the kernel's authorization rule.

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

### Element geometry and action follow-up on the 12 mini (2026-09-27)

**Seed and proof layers:** macOS 26.5.1 (25F80), Xcode 27 Beta 6 / CoreDevice 642.15,
physical iPhone 12 mini / iOS 27.0 (24A437), Developer Mode and DDI enabled. The host
`AccessibilityAuditDeviceManager.framework` disassembly and iOS 26.5 simulator `axauditd`
are **static comparisons**; the AXAudit DTX replies and screenshots below are **physical iOS 27
runtime evidence**. None of these experiments establishes an ordinary-node frame API.

- The host implementation of `XDMDeviceTransportBased
  fetchElementAtNormalizedDeviceCoordinate:withCompletionBlock:` builds one `NSValue` with
  Objective-C type `{CGPoint=dd}` and sends it with `sendControlAsync:replyHandler:`. Its reply
  handler decodes the returned object. The **simulator-only** `XADAuditServer` implementation
  reads that argument with `CGPointValue`, asks `XADInspectorManager` to hit-test, and completes
  the DTX invocation with the result. Thus a `host*` event alone is not the expected answer on
  these inspected implementations. On the physical 12 mini, two correctly typed point queries
  over Calculator still returned nil; monitoring-change callbacks did not supply an element.
  Apple's exact request on this phone has not been captured, so target/state or physical-daemon
  differences remain open.
- `deviceCaptureScreenshot` on the 12 mini returned `displayBounds={{0,0},{375,812}}` and
  `displayNativeScale=2.88`, while its PNG was **1125×2436**. The PNG has three pixels per
  reported logical point on each axis, not 2.88. Any screenshot-derived rectangle must use the
  actual image dimensions and reported bounds, then account for rotation; multiplying a detected
  pixel rectangle by `displayNativeScale` would misplace it on this seed.
- AXAudit audits returned one Calculator issue with `ElementRectValue_v1={{16,234},{343,84}}`
  and two SpringBoard issues with rectangle values. The SpringBoard issues were type 1007 and
  carried no `AuditElementValue_v1` in the decoded result. These are **issue rectangles**, not
  established bounds for corresponding ordinary tree nodes. Neither the 45-node Calculator tree
  nor the 407-node App Library tree gained a per-node frame field. The cached physical iOS 27
  `AccessibilityAudit.framework` also names `AXAuditIssue.elementRect` and
  `AXAuditCategory addIssueWithClassification:auditElement:elementRect:elementDescription:`;
  those symbols identify an issue-construction path, not a normal-node rectangle getter.
- A prior 13 Pro Lab preview visibly outlined selected text, and one 12 mini Calculator capture
  showed a green outline around the `7` key. However, direct-root-token and focus-token
  `deviceInspectorPreviewOnElement:` trials on the 12 mini did not reliably outline the requested
  node; several before/after PNG pairs were identical and another preview cleared the existing
  outline. Screenshot differencing is therefore not yet a general node-to-rectangle method.
- pymobiledevice3 11.10.2's `perform_press` serializes `PlatformElementValue_v1` without the
  nested `Value` used by captured property requests; its earlier no-effect press was an
  inconclusive action test. A follow-up used the **exact focus-event element and advertised
  `AXAction-2010` descriptor** for Calculator `7` and `All Clear`. Both calls returned, but
  before/after screenshots were unchanged and the display stayed `0`. This excludes that one
  malformed serializer as the sole explanation; semantic activation is still unverified.

The initial desktop control attempt could open Xcode's Accessibility Inspector but not operate
its target picker (`elementHasNoFrame` / `noWindowsAvailable`). A later attempt reached the picker
and the connection failure below, so the UI issue is no longer the blocking boundary. The
physical iOS 27 `axauditd` executable was not present in the local Xcode symbol cache; the
simulator implementation above is not proof of its physical-device geometry or permission policy.

### Apple Inspector connection and point-reply type (2026-09-27)

After bringing Xcode 27 Beta 6 Accessibility Inspector's window to the front, its target menu
listed the wired 12 mini, and selecting **only that phone** reached “Error connecting to device.”
An LLDB trace of the selected host's `XDMDeviceMonitorEmbedded._connectToDevice:` showed
`AMDeviceConnect` and `AMDeviceStartSession` returning **0**, followed by
`AMDeviceSecureStartService` returning **-402652910 / 0xE8000112**. The call-site argument was
the CFString `com.apple.accessibility.axAuditDaemon.remoteserver`; this host's MobileDevice
`AMDErrorString` names that code `kAMDRemoteConnectError`. This is a concrete **Apple-host
service-start failure before DTX**, not evidence about an element-frame reply. A separate
`devicectl device info lockState` request failed while allocating the RSD device with
`-402653181 / kAMDNoResourcesError`; their shared underlying cause is unproven.

The physical device did accept the same **lockdown service name** through a paired USB
pymobiledevice3 11.10.2 client (`autopair=False`): `StartService` returned an SSL-enabled port,
and AXAudit DTX `deviceCapabilities` returned 45 entries. Its RSD shim remained readable and
`deviceCaptureScreenshot` showed an unlocked App Library. Thus the Apple-client failure cannot
be described as absence of the device service or a locked screen on this run; the difference
between the host MobileDevice and Python connection paths still needs isolation.

On that native lockdown DTX channel, two typed normalized-point requests returned `None` through
pymobiledevice3. Inspecting the **raw** reply clarified that `None`: a request for `(0.7,0.4)`
received message type **0 (`OK`)** with no payload at conversation index 1, rather than type 3
(`OBJECT`) carrying a null element. No further DTX message or `host*` callback arrived during a
bounded four-second observation window. A subsequent `deviceCapabilities` control received a
type-3 object reply, confirming the recorder saw ordinary replies. Enabling the inspector and
app monitoring also left a point request with an empty result. This narrows the tested path to
an empty completion on this build/state; it does not establish why hit-testing found no element,
or whether Apple's client uses additional target/cursor state. No Apple-client point or preview
DTX payload was captured from the physical device.

### iPhone 13 Pro Apple Inspector and issue geometry (2026-09-28)

On macOS 26.5.1 (25F80), Xcode 27 Beta 6 / Accessibility Inspector 5.0 (192.6), CoreDevice
642.15 / DDI 27A5252f, the wired iPhone 13 Pro on iOS 27.0 (24A437) accepted Apple's
Inspector target and completed an audit of `PDUIApp`. The UI showed nine warnings (one Contrast,
five Dynamic Type, three Hit Region). This is **runtime evidence** that the Apple client can
establish an effective AXAudit session on this physical device/host seed, unlike the 12 mini
service-start result above.
It is not a trace of Apple's individual DTX audit or point request.

Through the independent paired pymobiledevice3 11.10.2 RSD shim (`autopair=False`),
`deviceCapabilities` returned 45 entries. `deviceAllSupportedAuditTypes` advertised the string
`testTypeHitRegion`; `deviceBeginAuditTypes:` with `["testTypeHitRegion"]` returned three
`AXAuditIssue_v1` objects through `hostDeviceDidCompleteAuditCategoriesWithAuditIssues:`.
Each issue contained both `ElementRectValue_v1` and `AuditElementValue_v1`. The first rectangle
was `{{12.666666666666666, 167}, {43.111111111111114, 8.5555555555555429}}`, with a
20-byte `PlatformElementValue_v1` token. Sending that token back inside the captured
`AXAuditElement_v1`/passthrough wrapper to `deviceElement:valueForAttribute:` returned the
label `进一步了解…`; the other two issue tokens returned `接受并继续` and `关闭FaceTime通话`.
`Frame` and `AXFrame` requests on all three returned nil. The direct normalized-point requests
at `(0.5,0.5)` and `(0.7,0.4)` also returned high-level nil. These message shapes and values
are **runtime evidence** on the stated seed, recorded in the local observation summary cited by
[the dated verification](verification.md#2026-09-28--iphone-13-pro-apple-inspector-and-audit-issue-geometry).

Thus an audit issue can associate its own rectangle with an element token, but that does not
establish a rectangle getter for ordinary tree nodes. The Inspector Quick Look preview showed
a Home-screen image with a green box although the selected target was `PDUIApp` and the first
token's label was not a Home icon. Treat overlay-to-current-screen alignment as unverified.
The next decisive comparison is an Apple-client 13 Pro point selection and its DTX reply.

A bounded 40-second LLDB interception of the Apple client's
`objc_msgSend$messageWithSelector:objectArguments:` path then recorded **43 outbound
selectors** while selecting `13 Pro > All processes` and enabling inspection scope. The
observed setup included `deviceSetAuditTargetPid:` with `0`,
`deviceSetAppMonitoringEnabled:` with `1`, `deviceDidGetTargeted`,
`deviceInspectorSetMonitoredEventType:` with `2` and `deviceInspectorShowVisuals:` with `1`.
The capture did **not** contain `deviceFetchElementAtNormalizedDeviceCoordinate:`: no
on-device/mirror pointer hit-test was triggered during that window. Replaying these observed
setup calls in one direct Python session, then querying `(0.5,0.5)`, still returned nil. The
trace establishes this subset of Apple's setup, not the complete state needed for a point
reply. The debugger detached and the direct session disabled monitoring and visuals afterward.
That run did not exercise the point-selection UI; the later injected-input controls are
recorded below.

### 13 Pro point-selection follow-up (2026-09-28)

**Same seed, runtime evidence.** Apple's
[Inspector instructions](https://developer.apple.com/documentation/accessibility/inspecting-the-accessibility-of-screens)
say to choose a device/app, enable point inspection, and tap an iOS element. On this host,
Device Hub's 13 Pro `View Screen` mirror accepted a click on the Weather icon and opened
Weather, but the separately targeted Inspector continued to show `None` for the selected
element. A 50-second Apple-client LLDB trace around a change to `13 Pro > All processes`
recorded 15 calls/callbacks on the three selected methods. They included
`deviceSetAuditTargetPid: 0`, repeated `deviceInspectorFocusOnElement: <null>` and
`deviceInspectorPreviewOnElement: <null>`, and three
`hostInspectorCurrentElementChanged:` values containing section descriptors but no
`ElementValue_v1`. It recorded neither a call to
`fetchElementAtNormalizedDeviceCoordinate:withCompletionBlock:` nor a selector for a point
fetch. A second bounded trace while tapping the phone at `(0.5,0.5)` under that target had
zero hits on these methods.

For a foreground-app control, `ipb launch com.apple.calculator` made `计算器` appear in the
Inspector's 13 Pro process menu. With that explicit target and point mode enabled,
`ipb tap 0.10 0.08` opened Calculator's History sheet, proving the injected touch reached
the app; the Inspector fields stayed `None`, and a third 50-second trace again had zero hits
on the selected point/focus methods. The intercepted method set is not a complete DTX trace.
These runs show that **these injected touches and the Device Hub mirror click did not trigger
Apple's element-selection path**; they do not establish what a human finger touch would do.
The prior nine-warning `PDUIApp` audit remains valid, but rerunning the audit on the current
`PDUIApp` and Calculator targets gave an empty result outline, so the documented
[audit-issue double-click route](https://developer.apple.com/documentation/accessibility/performing-accessibility-audits-for-your-app)
could not be exercised here. No ordinary-element point result
or frame was obtained. Local trace and screenshots are listed in the
[dated verification](verification.md#2026-09-28--13-pro-point-selection-and-foreground-app-control).

### AXAudit recorder and route reassessment (offline, 2026-10-09)

This is an **offline reinspection**, not new phone evidence. Current host metadata is macOS
26.5.1 (25F80), Xcode 27 Beta 6 / Inspector build 192.6. Historical device results above retain
their original seeds; no device connection, current PID or iOS build was refreshed here.

The retained 9/28 `trace.lldb` sets only the outbound
`objc_msgSend$messageWithSelector:objectArguments:` breakpoint. Although its Python callback
contains incoming reply handling, the script never attaches that branch. The later
`point-trace.lldb` additionally observes one focus callback and the host point method, not all
DTX replies or device events. Their global counters advance before selector filtering, disable
breakpoints at a cap without a disable record, and have no trial/footer marker. Therefore zero
hits or an absent output file do not prove that no AXAudit message traversed the device session.
This source defect is reproducible by inspecting the retained scripts, without rerunning phones.

**Host disassembly evidence:** in
`/Applications/Xcode-27.0.0-Beta.6.app/Contents/Applications/Accessibility Inspector.app/Contents/Frameworks/AccessibilityAuditDeviceManager.framework/Versions/A/AccessibilityAuditDeviceManager`
(arm64 UUID `4395FC8E-A200-3221-87D7-E607746BBBBE`),
`fetchElementAtNormalizedDeviceCoordinate:withCompletionBlock:` at unslid `0x9184` receives
CGPoint in `d0/d1` and the completion block in `x2`; it boxes `{CGPoint=dd}` before constructing
the DTX request. The retained `point_trace.py` incorrectly describes `x2` as the point. This
would corrupt coordinate recording if the breakpoint fires; it does not explain a zero hit.
The observed caller at `XDMDeviceSIM._updateCurrentElementForMousePoint:` checks Simulator
resolution and converts a Simulator window point before invoking the method. This is a concrete
Simulator caller, not an exhaustive proof that no physical caller exists. Local sources are
`20260922-ax-inspector/manager.disassembly.txt:3141–3355,8406–8459` and
`20260928-13pro-axaudit/point_trace.py:30–31` beneath `~/.local/state/ipb/`.

The already-examined iOS 26.5 **Simulator** daemon also has
`eventManager:eventToHighlightPoint:` and event-monitor setup that enables snarfing for types
1/2, with stop-on-touch-up for type 2 (`sim-axauditd-annotated.txt:103–118,1423–1482` in
`20260922-element-research/`). **Inference:** physical iOS selection might push a focus event
without a host point RPC; its implementation and monitoring lifetime need real-device capture.
Do not require a host point-call hit as the sole success criterion.

Shipped Objective-C metadata in
`/Applications/Xcode-27.0.0-Beta.6.app/Contents/SharedFrameworks/DTXConnectionServices.framework/Versions/A/DTXConnectionServices`
provides `DTXConnection sendMessage:fromChannel:sendMode:syncWithReply:replyHandler:`,
`_routeMessage:` and `_scheduleMessage:toChannel:`, plus `DTXMessage` routing/type/status getters.
These are candidate bidirectional recording points, not proof that a new recorder is complete.
Use the loaded slice UUID and symbol resolution; an entry-stage identifier need not equal its
final serialized routing value. Raw archives/serializer ABI and capture overhead remain to be
validated before claiming byte-exact wire coverage.

Two historical evidence corrections constrain the next experiments. Valid focus records in
`20260922-ax-inspector/probe-events.jsonl:4`, `settings-attribute-results.jsonl:5` and
`settings-next-attribute-results.jsonl:4` advertise `AXAction-2010`, Activate and
`PerformsActionValue_v1=true`; blank sections without a selected token do not establish that
actions are universally unavailable. Conversely, `page-expand-lab-raw.jsonl:48,58,87,151,167`
reports Foreground Running for Lab, SpringBoard, PDUIApp, InputUI and AccessibilityUIServer
within roughly 66 ms of receiving events. An app-state notification alone is not a verified
unique frontmost-PID resolver. The [capture plan](devicehub-alignment.md#axaudit-capture-plan)
requires a successful selection/action reference and coherent target/token/screen controls.

### Separate iPhone Mirroring AX path (offline host, 2026-09-23)

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

### Mirroring bulk AX schema, Frame and physical server (2026-10-09)

**Evidence boundary:** static Apple code/metadata plus a **synthetic host codec** experiment.
No phone request, Mirroring session, received phone tree or latency measurement occurred in
this follow-up. The earlier unknown payload schema is narrowed below; independent session
authorization, app coverage and a complete page export remain open.

**Source identity:** host macOS **26.5.1 / 25F80**, iPhone Mirroring **1.6 / 98.5**.
Host dyld-cache image UUIDs: AccessibilityPlatformTranslation (APT)
`8BA4B0B3-D1F0-37F7-ABDB-EBE916DE97AA`, ScreenSharingKit (SSK)
`C6D042A9-EE7E-3F13-9599-69DD1CB1A572`, HIServices
`34C40608-353D-3A06-BBF1-6B927CB8B39D`. Their paths are respectively
`/System/Library/PrivateFrameworks/AccessibilityPlatformTranslation.framework/Versions/A/AccessibilityPlatformTranslation`,
`/System/Library/PrivateFrameworks/ScreenSharingKit.framework/Versions/A/ScreenSharingKit` and
`/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/HIServices`.
Phone-side source is **iPhone14,2 / d63ap, iOS 27.0 / 24A437**, from the
[Apple restore image](https://updates.cdn-apple.com/2026FallFCS/3337f675-bd6c-49e2-9d4a-7b59095d07e5/iPhone14,2_27.0_24A437_Restore.ipsw).
Only its selected components were downloaded, not the whole IPSW. SystemCryptex member
`043-68607-705.dmg.aea` has ZIP CRC32 `edf9a7c1` and SHA256
`d95887e94062dbef7fd0082828126dc148f2c856129f49d0f4abd9f20268bed2`.
After successful AEA decryption, complete `__text` sections from the matching local
DeviceSupport symbol files were found byte-for-byte in the Apple image:

The physical cache images are
`/System/Library/PrivateFrameworks/AccessibilityPlatformTranslation.framework/AccessibilityPlatformTranslation`
and `/System/Library/PrivateFrameworks/ScreenSharingKit.framework/ScreenSharingKit`.

| Physical framework | Image UUID | Matched instruction bytes |
| --- | --- | --- |
| AccessibilityPlatformTranslation | `AA0429D2-50DA-3B83-9C2A-A8D9E752581D` | 88,520; SHA256 `55d93d1e1f9def1b562e3fd6868018f6c787754b44b209b833880037ebf89027` |
| ScreenSharingKit | `6AA674A8-B0DC-3B87-AF55-B92FE8DE286B` | 2,530,132; SHA256 `e00b0045ea82c5030e8035cf206fc4e283a7cd705542b137dca3b46e084a80b8` |

DeviceSupport files are reorganized symbol files, not original signed standalone dylibs.
External selector stubs, shared-cache method names, the attribute table and priority arrays
were resolved separately from the original Apple image's cache mappings. Direct method-list
names/types use the shared selector buffer, not the method entry as their base; see Apple's
[ObjCVisitor implementation](https://github.com/apple-oss-distributions/dyld/blob/main/common/ObjCVisitor.cpp)
and [ObjC optimization header](https://github.com/apple-oss-distributions/dyld/blob/main/common/DyldSharedCache.h).

**Bulk transport and cache:** host `AXPHostCacheManager._processPlatformTranslationResponse:withToken:`
(`0x1D99F76D4`, discriminator comparison at `0x1D99F7734`) routes responses with
`associatedRequestType == 11` into tree handling. This is a **response discriminator**, not
evidence that sending request type 11 requests a snapshot. `AXPTranslator.handleUpdatedAXTree:`
(`0x1D99F29E4`) reads `resultData.treeDump` and `treeDumpType`, handles the exported string
values `AXPTreeDumpTypeInitialDump`, `AXPTreeDumpTypeAdditionalData` and
`AXPTreeDumpTypeTreeDestroyed`, and maintains the tree by `bridgeDelegateToken`.
Initial data replaces the tree; additional data merges node attributes; destruction removes
cached data. `updateMacPlatformElementCacheForUpdatedTreeDumpResponse:` (`0x1D99F30D0`) handles
multiple-attribute responses (`associatedRequestType == 5`) and populates node caches through
`AXPMacPlatformElement._cacheAXTreeDumpResult:attribute:` (`0x1D99DF148`).

Native secure-coding fields are explicit, rather than guessed from strings alone:

| Archived class | Keys | Host encoder |
| --- | --- | --- |
| `AXPTranslationObject` | `pid`, `isApplicationElement`, `didPopuldateAppInfo` (Apple spelling), `objectID`, `bridgeDelegateToken`, `rawElementData` | `0x1D99F6A18` |
| `AXPTranslatorRequest` | `parameters`, `requestType`, `actionType`, `attributeType`, `clientType`, `translation` | `0x1D99F8C14` |
| `AXPTranslatorResponse` | `resultData`, `error`, `attribute`, `notification`, `associatedRequestType`, `associatedNotificationObject`, `associatedTranslationObject` | `0x1D99FB030` |

The host `AXFrame` mapping is **21** (`_attributeTypeForMacAttribute:` at `0x1D99DBA08`,
confirmed by host-local metadata invocation); `AXChildren=8`, `AXParent=41`, `AXPosition=43`,
`AXSize=48`, `AXRole=45`, `AXValue=53`, `AXIdentifier=25`, `AXEnabled=27`.
Physical `AXPTranslator_iOS.attributeFromRequest:` (`0x24FE0E8A0`) indexes the table at
`0x24FE22D20`; entry 21 maps to native iOS attribute **2003**. Frame is included in the
28-entry priority array (`0x275E8C600`) and 99-entry full array (`0x275E8C630`), whose values
match the inspected host arrays. This is evidence that Apple's bulk implementation includes
geometry among its priority fields; it does not prove every node actually supplies a rectangle.
Host `accessibilityFrame` (`0x1D99DCE18`) obtains `AXFrame` and calls `rectValue`.
Postprocessing (`0x1D99DE294`, conversion at `0x1D99DF918`) asks the bridge delegate to convert
platform coordinates into Mac system coordinates. A future export must retain which coordinate
space it reports instead of treating Mac screen coordinates as phone points.

**Physical producer:** SSK's `AXPBackedAccessibilityServerPrimitives.startAccessibility`
body at `0x2A188EF88` loads `AXPRemoteCacheManager` through the class reference at
`0x2C807C810` (resolved class `0x2718626F8`), calls `init` at `0x2A188F034`,
`setTransportDelegate:` at `0x2A188F040` and `start` at `0x2A188F1D8`.
Its receive-handler and send-data delegate methods are at `0x2A188F918` and `0x2A188F644`.
Physical APT `AXPRemoteCacheManager.start` (`0x24FE197B8`) configures the translator's
`requestResolvingBehavior=2`, cached client type and runtime delegate, then registers its
transport receive handler. `_sendAXHierachyOnBackgroundQueue` (`0x24FE1A2E4`, Apple spelling)
calls `generateAXTreeDumpTypeOnBackgroundThread:completionHandler:` at `0x24FE1A434`.
Initial/additional callbacks are at `0x24FE1A6BC` / `0x24FE1AB68`; response sending is at
`0x24FE1AD80`. Default cached client type is 1; the translator distinguishes Oneness (1) and
DevicesApp (2). The latter is a static alternative, not a demonstrated USB subscription.

The same physical SSK's Swift field metadata identifies `AngelServer.accessibilityPrimitives`,
`accessibilityMessageProducer` and `axPrimitivesDataSubscription` (descriptor `0x2A1A4695C`),
plus `AccessibilityMessage.accessibilityData` / `clientNeedsAccessibility`
(`0x2A1A46E04`). The same restore image's MainOS member `043-69835-656.dmg.aea`
(previously extracted for the physical AXAudit analysis) also contains
`/Applications/ScreenContinuityShell.app/ScreenContinuityShell` (**2.0 / 114.56**, SHA256
`ee98211c952f6be6d147a97e0ad20432ca3f92184844420e483d63195bc324f5`).
Its imports and event-handler strings identify `AngelServer.startUp`, `bootstrapSession`,
`ScreenContinuityAngel.awaitServerReadiness` and `com.apple.rapport.matching`.
Its signed entitlements include `com.apple.accessibility.api`, `com.apple.RemoteDisplay` and
AXBackBoardServer lookup. This identifies a shipped session entry point; the complete runtime
chain from the incoming session event to AX subscription has not been observed.

**Two distinct permission boundaries:** on the host, cached-tree modes route through
`_AXPClientIsEntitledForRemoteDeviceContent` (`0x1D99F1B80`) and HIServices
`_AXCurrentRequestCanAccessRemoteDeviceContent` (`0x187BB1B30`). HIServices
`_isConnectionAllowedAPIAccess` checks the requesting audit token's
`com.apple.private.accessibility.remoteDeviceContent` entitlement (`0x187BB231C`–`0x187BB2328`)
and records the result at `0x187BB23A8`. Inspection permission has a separate flag.
Current codesign metadata shows this remote-content entitlement on **VoiceOver**, while both
installed Accessibility Inspectors expose `inspection` but lack `remoteDeviceContent`.
Self requests and other branches exist; this is a gate on external Mac AX queries, not proof
that an independently authenticated network client cannot decode incoming bytes.

On the phone, `CommandLineServerInterface` exposes only ping, current session state and stop
(method list `0x2A1A2B5A8`). `AngelServer.listener:didReceiveConnection:withContext:`
(`0x2A18257E8`, body `0x2A182736C`) checks the remote token with `hasEntitlement:` for
`com.apple.ScreenContinuityShell.commandline` at `0x2A18274A4`, branching on the result at
`0x2A18274B4`. This local command-line interface is neither a discovered remote service nor
a tree-dump API. Mirroring session authentication remains a separate unresolved boundary.

**Synthetic codec result:** native secure archive/unarchive preserved one type-5 node inside
a type-11 initial-tree response, including numeric attribute 21 with an `NSValue` rectangle.
The 1,136-byte archive returned one node and `{{18,49},{40,40}}`; these are deliberately chosen
synthetic values, not a physical readout. No manager/transport session was instantiated.
The next useful experiment is an authenticated AX data capture at the SSK/AXP boundary,
with initial/incremental packet correlation and original device-space Frame validation.
Local raw evidence and probe references are in the [dated verification](verification.md#2026-10-09--mirroring-bulk-ax-schema-frame-and-physical-producer-offline).

### Mirroring AX subscription, control codec and host trigger (2026-10-10)

**Scope:** offline physical-code analysis and host-local execution on the same **macOS
26.5.1 / 25F80**, SSK UUID `C6D042A9-EE7E-3F13-9599-69DD1CB1A572`, and physical
**iPhone14,2 / iOS 27.0 / 24A437** sources identified above. ScreenContinuityUI at
`/System/Applications/iPhone Mirroring.app/Contents/Frameworks/ScreenContinuityUI.framework/Versions/A/ScreenContinuityUI`
has SHA256 `8221a0a96e2804b9356323601f64d8b208595f8c5001ffa4b3ce0784da6737ea`.
No phone connection, active Mirroring session, actual AX packets or new authorization result
was obtained. Local framework loading and a host status getter do not establish a phone session.

**Resolved subscription switch:** physical `ProxyingAccessibilityMessageConsumer` has
`isActivated` at instance offset `0x70` and optional `accessibilityPrimitives` at `0x78`,
confirmed by original-cache ivar/reflection metadata. The dispatch path at `0x2A17D4224`
checks activation at `0x2A17D425C`; its enum handler (`0x2A17D44AC`) distinguishes data from
the Bool case and passes the latter to `0x2A17D4AA8` at `0x2A17D458C`. That handler checks
the optional primitives and dispatches **true → start**, **false → stop** at
`0x2A17D4D58`–`0x2A17D4D94`. This is a session subscription, not an AXAudit selector.

The exact dispatch is supported by the `AccessibilityServerPrimitives` protocol descriptor
at `0x2A1A48160` and original-cache witness table `0x2D1628970`: its start/stop slots
`0x2D1628978` / `0x2D1628980` resolve to `0x2A188F4CC` / `0x2A188F4F0`. Those thunks call
the already identified AXP server start/stop bodies (`0x2A188EF88` / `0x2A188F230`).
Consumer allocation initially clears the activation byte and leaves primitives nil
(`0x2A184CDF8`–`0x2A184CE0C`); setup copies an optional primitives value into that field
at `0x2A184CE48` through the value-witness assignment helper `0x2A17F1CFC`. This does not
prove that a particular session supplies a non-nil value. Thus replaying the switch outside
an activated, configured session is not a demonstrated snapshot shortcut.

**Native control codec:** the host's actual Swift `AccessibilityMessage` and private
`ControlMessage` types were resolved from loaded metadata, decoded with PropertyListDecoder,
and encoded through their own Encodable implementations. Five synthetic controls passed
dictionary/data equality, including the outer envelope:

```json
{"accessibility":{"_0":{"clientNeedsAccessibility":{"_0":true}}}}
```

False uses the same shape with `false`. The data case is
`accessibility._0.accessibilityData._0`, whose value is **Data**, not a presumed base64 string.
The native encoder produced binary plists: 82 bytes for either standalone Bool case, 105 for
the outer true envelope, and 1,245 for an envelope carrying the earlier 1,136-byte synthetic
AXP tree. Unpacking that envelope and securely decoding its AXP archive returned the one
synthetic node and rectangle `{{18,49},{40,40}}`. This validates codecs and nesting, not
captured network framing or real-phone coordinates. Physical `ControlMessageSession` reflection
also exposes `plistEncoder` / `plistDecoder` (`0x2A1A48D88`).

**Normal host activation has a separate prerequisite:** SSK's
`NotificationsBackedAccessibilityStatePrimitives` queries
`AXSSHasClientsWithAccessRemoteDeviceContent` at `0x26698DA80` and `0x26698DE20`, and observes
`AXSSHasClientsWithAccessRemoteDeviceContentDidChange`. Both were resolved from live loaded
cache pointers, rather than trusting inaccurate names attached to retained disassembly's
external calls. The getter resides in
`/System/Library/PrivateFrameworks/AccessibilitySharedSupport.framework/Versions/A/AccessibilitySharedSupport`
(UUID `FDC2353E-33CB-3E62-9530-1C8E226FCB1A`, image offset `0x35A98`). A separate Python-process
query returned **false** during this run; Mirroring was not running. The getter reads the
calling process's AX connection cache, not a machine-wide VoiceOver status. Its result does
not measure Mirroring's demand; see the live scope correction below. This is neither an
AXAudit result nor an independent network-client authorization result.

ScreenContinuityUI tests `currentStateNeedsAccessibility` at `0x80074` and guards creation of
its AX primitives; `startAccessibility(remoteDeviceID:deviceSize:)` is called at `0x8075C`.
Outgoing messages reach `ScreenSharingSession.sendAccessibilityMessage` through the async
descriptor loaded at `0x6D854`; incoming publisher/data processing call sites are `0x76CA0`
and `0x8FBB8`. There is also a server-capability check (`0x95AA4`, result branch `0x95D44`):
SSK's `Capabilities.accessibility` has raw value **2** (`0x2669A72B0`). Successful checking
starts accessibility-state monitoring; failure logs that the server does not support it.
These UI addresses are unslid offsets in ScreenContinuityUI, not SSK virtual addresses.

Do not treat `com.apple.screensharing.accessibility` as a newly discovered remote service or
stream identifier: its host getter at `0x266907FC4` is explicitly exported as
`AnnotationServiceConstants.accessibilityServiceEntitlement`, a separate annotation path.

**Next discriminator:** capture one genuine configured Mirroring session with positive host
AX demand, server capability and consumer activation, then correlate the Bool control with
the initial AXP archive and later incremental data. Inspect session establishment/authentication
and transport framing separately. The direct subscription message is now resolved; access to
an authenticated session and physical tree coverage are still open. Raw references are in the
[dated verification](verification.md#2026-10-10--mirroring-ax-subscription-and-native-envelope-controls-offline).

### Mirroring first-setup authentication (2026-10-10)

**Runtime scope:** macOS **26.5.1 / 25F80**, iPhone Mirroring **1.6 / 98.5**, the host
SSK and ScreenContinuityUI identities above; allocated physical **iPhone14,2 / iOS 27.0 /
24A437**, CoreDevice UUID `7F2FE6E9-5423-552A-A2A2-C499F1D8672F`. The native onboarding
initially chose another phone; that attempt was stopped, and System Settings' Continuity
picker was explicitly changed to the 13 Pro before the observations below. Do not attribute
the earlier default-target attempt to the 13 Pro.

At **10:25:56.985 CST**, a bounded LLDB tap captures
`SharingBackedAuthenticationPrimitives.pairDeviceForMacUnlock()` in the configured native
client. The 13 Pro's own Rapport log receives an **authentication pre-pairing request** at
**10:25:58.428**, with a 121-byte accounting entry, and sends an
**authentication response** at **10:26:48.963**, 109 bytes, link type BLE. These are device log descriptions and
byte counts, not captured/decoded wire payloads. Mac sharingd reports session failure at
**10:26:46.992**, `com.apple.sharing.authentication Code=12`; the client wraps it as
`ScreenSharingKit.RemoteAuthenticationError Code=3` and shows the target-specific timeout.
The response send occurs after the host's failure; it is not a successful pairing result.
The error code's underlying cause is not established.

After manual user setup/unlock, a second `pairDeviceForMacUnlock()` hit occurs at
**10:31:22.236**. The native host log records **authentication enablement completed** at
**10:31:26.686** and **Unlock enabled** explicitly for iPhone14,2 at **10:31:26.757**.
The UI reaches **iPhone Mirroring Is Ready to Use**. Get Started then shows **iPhone Mirroring
Is Locked**, requiring the Mac login. This establishes first-setup enablement, separately
from USB/CoreDevice pairing; it does not establish an active screen-sharing control session,
its network framing, AX capability/subscription, or a received page tree.

The user reports setting the iPhone passcode. Apple documents a passcode as a
[Mirroring prerequisite](https://support.apple.com/en-eg/120421). Nevertheless, before and
after setup a fresh Lockdown `all_values` query returns `PasswordProtected=false`. That raw
key is not used here as authoritative proof that no passcode exists, nor as a causal
explanation of Code 12. At this initial-setup checkpoint, separate Python AX-demand queries
return false and temporary VoiceOver permission is still pending; these queries do not measure
Mirroring's process-local demand. No authentication credentials or token contents
were dumped. Decoding the earlier synthetic archive still proves only decoder operation.
Raw references and capture limits are in the
[dated verification](verification.md#2026-10-10--13-pro-mirroring-first-setup-authentication-live).

### Mirroring live control session and host AX permission failure (2026-10-10)

**Scope:** the same macOS **26.5.1 / 25F80**, Mirroring **1.6 / 98.5** and allocated
**13 Pro / iOS 27.0 / 24A437** as above. These observations do not establish macOS 27 behavior.
After the user completes Mac login, Mirroring requests that the phone be locked. One explicit
`ipb -s 7F2FE6E9-5423-552A-A2A2-C499F1D8672F lock` is sent. Native retries hit
`unlockWithAuthenticationToken(Foundation.Data)` five times and fail with Sharing
authentication **Code 10 / SFAuthenticationErrorCodeInternal**. Later native UI observations
show the actual phone Home and Settings pages. The transition occurs after a debugger detach,
but there is no controlled causal comparison establishing that debugging caused the failure.

**Runtime logs, not decoded wire payloads:** at **10:53:48.744 CST**, the host receives server
initialization with protocol version **6**, platform iPhone, build **24A437**, capabilities
**31**. At **10:53:48.997**, phone `ScreenContinuityShell` receives client startup with protocol
version **3**, platform Mac, build **25F80**, capabilities **7**, and HID device properties.
Both sides log control stream **`com.apple.oneness.sessionAndHIDMessages`**. Phone Rapport
also identifies service **`com.apple.MediaContinuityKit.iPhoneMirroring`**, `using_QUIC=YES`
and an ephemeral port. The advertised server capabilities include `0x2`; this does not prove
that the host AX consumer ran or that an AX archive was sent.

**The host demand getter is process-local.** In shipped HIServices (UUID
`34C40608-353D-3A06-BBF1-6B927CB8B39D`), `AXHasClientsWithAccessRemoteDeviceContent`
(`0x187BB1B10`) counts bit `0x10` in `_gPortAccessStatusCache` via
`_activeRemoteDeviceContentConnections` (`0x187BB6B54`). Its change notification uses the
local CF notification center (`0x187BB3F38`). External Python getter results cannot substitute
for observing this state inside Mirroring.

**A genuine VoiceOver connection is observed, but its remote-content permission is cleared.**
VoiceOver's shipped signature includes `com.apple.private.accessibility.remoteDeviceContent`.
At **11:14:03.976–.993**, passive taps inside Mirroring capture:

- `_appHasEntitlement` returning **true** for that exact entitlement (`0x187BB232C`);
- the effective remote-content value becoming **false** (`0x187BB2370`);
- `_setMachPortAccessStatus` (`0x187BB70EC`) receiving the actual VoiceOver PID **54576**,
  general access **1**, protected-content **1**, inspection **1**, remote-content **0**.

Disassembly between the first two taps (`0x187BB2330–2370`) preserves the remote entitlement
for client-identification values **7–10**; otherwise it substitutes the Apple-internal-build
flag. During this call the identification override, current-request identification and
internal-build flag are all **0**, read from Mirroring memory with a validated PC slide.
The client-identification globals are identified by the shipped
`AXSetClientIdentificationOverride` and request getter code (`0x187BB1BE8–1C14`), not guessed
from their values. [WebKit's SPI declaration](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/PAL/pal/spi/mac/HIServicesSPI.h)
names value 0 as no active request and VoiceOver as 7. The follow-up below resolves the
incoming identification and check/store ordering; newer-host runtime behavior remains open.
No AX start, outgoing subscription or incoming archive
is captured. This is a specific host-side blocker, not evidence that iOS has no tree/Frame path.

**Independent host authentication has a separate enforced gate.** Current Sharing.framework
(UUID `28F48BEF-DAD2-38A7-81D1-A467BA05589D`) routes
`SFAuthenticationManager.requestEnablementForType:withIDSDeviceID:` and
`authenticateForType:withOptions:` through `SFCompanionXPCManager.unlockManagerWithCompletionHandler:`
to the corresponding `SDUnlockXPCSession` methods. Sharingd (arm64e UUID
`8623E197-9333-3873-ADD5-8E5241CF041C`) creates this session at `0x100043A00`, while its
`checkEntitlementWithHandler:` (`0x10000B124`, entitlement check `0x10000B178–190`) checks
**`com.apple.private.sharing.unlock-manager`** on the current XPC caller before authentication
operations (`0x100009A04`, `0x10000A094`). Native Mirroring carries this entitlement.
A normal local probe obtains the broker connection, then a read-only eligible-device query
returns **`SFAutoUnlockErrorDomain` / 111 / no permission**. No enablement, authentication,
credential extraction or token replay is requested. This proves denial of the tested Apple
broker path; it does not rule out every independent Rapport/network implementation.

VoiceOver is restored **off** and all owned captures detach/close. No genuine phone AX archive
or element rectangle has been received. Local references and limitations are recorded in the
[dated verification](verification.md#2026-10-10--13-pro-control-session-voiceover-permission-and-authentication-broker-live).

### Mirroring client identification ordering and macOS 27 comparison (2026-10-10)

**Runtime on macOS 26.5.1 / 25F80, static comparison on macOS 27.2 / 26B5091g.**
The physical target remains the allocated **iPhone14,2 / iOS 27.0 / 24A437**. The newer host
is Mac-M2, freshly reached over SSH; this supersedes the earlier SSH-unavailable observation,
not the historical verification record. HIServices reports version **1.22** on both hosts:
arm64e UUID **34C40608-353D-3A06-BBF1-6B927CB8B39D** on 26.5.1 and
**39A43728-ADF4-3FC1-A946-0466C3E72BBA** on 27.2.

**The caller supplies 7; the permission check runs before it is installed.** Passive taps
inside native Mirroring PID **84730**, with VoiceOver PID **62094**, capture the same-thread
sequence at **11:27:09.520–.575 CST**:

1. `_AXXMIGCopyAttributeValue` entry (`0x187BB2710`) receives identification **7** as its ninth
   argument; its audit-token peer PID is the running VoiceOver process. Override/current ID
   and Apple-internal-build flag are **0**.
2. Its call to `_isConnectionAllowedAPIAccess` (`0x187BB27C8`) still sees current ID **0**.
   Remote entitlement lookup returns **1**, the identification filter replaces it with **0**,
   and `_setMachPortAccessStatus` receives access flags **1/1/1/0** for that same peer/port.
3. Only after that check does `0x187BB27E4` store incoming ID **7**. The common epilogue
   clears it at `0x187BB2A10`; the post-reset tap reads **0**.

A second VoiceOver process, PID **63357**, reproduces the sequence. A subsequent peer-filtered
tap at `0x187BB2498` reads cached status **0x0E**: allowed/protected/inspection are present,
remote-content bit **0x10** is absent. At the attribute handler's post-identification site,
current ID is **7** while `_AXCurrentRequestCanAccessRemoteDeviceContent`'s backing byte
(`0x1EC6E9A00`) remains **0**. This establishes both the zero-ID timing and persistence for
the tested ordinary attribute route. It does not establish an Apple-wide impossibility or
that every MIG entry route has identical initialization.

**macOS 27 retains the relevant order and filter in shipped code.** In its HIServices,
`_AXXMIGCopyAttributeValue` calls the permission helper at **0x1926C3E48**, stores the request
identification at **0x1926C3E64**, and clears it at **0x1926C4090**. The helper selects the
nonzero override or current ID (`0x1926C39B0–C4`), preserves the remote entitlement for **7–10**
(`0x1926C39CC–D4`), otherwise substitutes the internal-build flag, and caches the result.
This is static instruction evidence, not a macOS 27 VoiceOver/13 Pro result.

Mac-M2 ships Mirroring **2.0 / 126.8** (UUID **C23F483F-F100-3D40-BA21-E952F144D580**),
embedded ScreenContinuityUI (UUID **79207700-721C-3C67-8D94-C901BE6400FF**) and ScreenSharingKit
**2.0 / 126.8** (UUID **06D891A4-6FCB-3949-887A-1EC073B2EE3B**). Their imports/exports retain
AX demand/state, start/stop, `clientNeedsAccessibility`, incoming data and the host cache.
The inspected app/UI/ScreenSharingKit import and dlsym tables do not reference
`AXSetClientIdentificationOverride`; indirect calls through other frameworks remain possible.
The current developer selection reports **Xcode 26.4 / 17E192**, while `devicectl` reports
**642.15** and LLDB **2100.0.16.4**; the mixed installation is not a confirmed Xcode 27
release-gate environment. After the user moves the same phone, USB serial and CoreDevice UUID
identify the allocated 13 Pro, but CoreDevice reports `pairingState=unsupported` and
`tunnelState=unavailable`. This does not establish missing USB trust or an Apple-account cause
for CoreDevice. Native Mirroring launches, but its visible default target is another phone;
that error is excluded from 13 Pro results. No authenticated native 13 Pro session is established.

[Apple's Mirroring requirements](https://support.apple.com/en-eg/120421), refreshed October 10,
require the Mac and iPhone to use the same Apple Account with two-factor authentication.
USB trust and remote Mac access do not satisfy that native session requirement. The user
identifies this prerequisite while selecting the target; account identifiers are not inspected
and no account is changed. CoreDevice visibility is not a proven prerequisite for native
Mirroring. The [Mac-M2 attempt](verification.md#2026-10-10--mac-m2-usb-identity-and-native-mirroring-account-prerequisite)
records the separate USB, developer-tool and native-session observations.

The local native window displays Settings/Home, but normal AX reads still expose only Mac
window/toolbar/menu elements. No AX start or genuine incoming AXP archive is captured; a full
phone tree and native rectangles remain unreceived. The phone's bulk Frame producer described
above is still a separate static positive. VoiceOver is restored **off**, all owned traces
detach, and local evidence is mapped in the
[follow-up record](verification.md#2026-10-10--mirroring-client-id-7-arrives-after-permission-check-macos-27-static-comparison).

## Mirroring AX consumer installation and transport providers (2026-10-11)

**Static evidence; no new phone session.** The source remains the allocated iPhone14,2 /
iOS 27.0 / **24A437** ScreenSharingKit, UUID **6AA674A8-B0DC-3B87-AF55-B92FE8DE286B**.
The full 2,530,132-byte `__text` is re-compared with the original Apple SystemCryptex
`043-68607-705.dmg`: exact match, SHA-256
`e00b0045ea82c5030e8035cf206fc4e283a7cd705542b137dca3b46e084a80b8`.
Descriptors, conformances and strings below are read from that original cache, not rewritten
DeviceSupport metadata or exports. Host observations below use macOS **26.5.1 / 25F80**;
they are not a new macOS 27 comparison.

The physical AX consumer is now connected to actual playback-server construction:

| Edge | Decisive original-code / metadata evidence |
| --- | --- |
| Continuity session initialization | Descriptor `0x2A1A4A9D4` names `SceneInteractorBackedContinuitySession`. Its source-file literal is at `0x2A1A7BBC0`; the `initializeSession()` and `received transport` references appear in continuations `0x2A1950944` and `0x2A1951050`. The async chain reaches `0x2A1952F48`, which references the exact `initializePlaybackServer(using:)` literal at `0x2A1A7C170`. |
| Concrete AX consumer | `0x2A19532D0` calls accessor `0x2A17D4110` for descriptor `0x2A1A4599C`, `ProxyingAccessibilityMessageConsumer`. Allocation initializes activation false and primitives nil, then copies supplied primitives into the optional at object `+0x78`. The object is retained in async-context `+0x420`. |
| Wrapper | Accessor `0x2A193451C` resolves original metadata `0x2CF76FDE0` to descriptor `0x2A1A4A310`, `NotifyingPlaybackEventConsumer`. At `0x2A1953464`, the AX consumer and its `PlaybackEventConsuming` witness are stored at wrapper `+0x70/+0x78`; the wrapper is retained at async-context `+0x430`. Reflection names `underlyingConsumer` and `didConsumeSubject`; conformance `0x2A1A3C4B8` verifies the wrapper's protocol. |
| Control session | Accessor `0x2A18D6598` names `ControlMessageSession` (descriptor `0x2A1A48D88`); allocation and initializer `0x2A18D1EDC` occur at `0x2A1953510–3538`, retaining the result at async-context `+0x440`. |
| Actual server installation | `0x2A1953F74` calls `PlaybackServer` accessor `0x2A1A25EAC` (descriptor `0x2A1A4D388`), then allocates the server, held in `x21`. At `0x2A1954298`, the wrapper and witness are stored into this object using the field-offset variable `0x2CD30CC20`. At `0x2A195419C`, the retained control session is stored using `0x2CD30CBE8`. This proves object installation; numerical runtime offsets and exact reflected field-to-offset names are not recovered from zero-initialized metadata. |

The parallel constructor at `0x2A184CD98` also creates the AX consumer and wraps it through
`0x2A184CE8C` (`0x2A184CF4C` store). Its enclosing owner is not yet resolved. A nearby
accessor, `0x2A18F96BC`, names **ProxyingClientStatusEventConsumer**, not the AX consumer;
the two must not be conflated. Async-context offsets are not continuity-session object fields.

The upstream transport boundary is narrower now. The original symbolic references resolve
`SceneInteractorBackedContinuitySession.transportSession` to protocol
`TransportProvidingContinuityServerSession` (descriptor `0x2A1A4A1B0`),
`PlaybackServer.session` to `ControlMessageSession`, and its `transport` to `ControlTransport`
(descriptor `0x2A1A4D22C`). A scan of this ScreenSharingKit image's 1,069 conformance records
resolves these concrete providers:

| Session provider | Control transport | Backing state established by original reflection |
| --- | --- | --- |
| `MediaTransportServerSession` (`0x2A1A3ED88` conformance) | `MediaTransportControlStream` (`0x2A1A2F700`) | Session holds `RPRemoteDisplaySession`, `streamServer` and `controlStream`; control stream holds `RPStreamSession`, `messenger` and `dataStream`. The two Objective-C type names are explicit in the type references. |
| `MCKBackedContinuityServerSession` (`0x2A1A402D8`) | `MCKControlStreamBackedControlTransport` (`0x2A1A31B30`) | Session holds `MediaContinuityKit.MediaContinuitySession` and incoming-control transport state; the adapter holds `MediaContinuityKit.ControlStream`. Both module/type names resolve through original descriptors. |

`MockControlMessageStream` is another `ControlTransport` conformance in the image; its
presence is not a production or phone-access control. These providers identify where to trace
stream creation, listener authorization and session acceptance. They do not show that a
normal computer client can instantiate an effective provider, reuse CoreDevice/USB pairing,
or subscribe without native Mirroring. Conformances in other images remain outside this scan.

The normal Mac initialization lead is also bounded. Current HIServices has 19 inspected
direct permission-helper routes: 18, including notification registration/removal, store the
incoming identification only after checking access; the keyboard-posting route has no such
store. `_loadAccessibilityBundles` dynamically calls
the token-bearing exports of **AccessibilityBundles** (UUID
**15AB226A-3C61-305A-AF55-616D941D746D**). Its required loader
`0x230F0A260` installs a dyld image callback and loads required bundles; its full loader
`0x230F0A510` checks `forceBundleLoad` / `mayNeedBundleLoad` entitlements. Neither loader
directly writes HIServices identification or remote-access cache state. The inspected
CoreAccessibility/AppKitAdditions routines register safe categories; their resolved calls
provide no such direct writer. A separate AppKit auth-stub inventory resolves ordinary AX
imports but no identification-override/remote-content import; indirect routes are not excluded.
The `AXEnhancedUserInterface` handler at `0x187BB3DE0–3EB8` can load additional bundles, but
posts the demand-change notification only when remote permission is already set. This is
not a discovered way to repair the observed zero remote permission.

**Remaining proof:** trace the two concrete provider families to their normal listener and
authorization entry, then obtain a real initial AXP archive in an eligible, identity-verified
13 Pro session. Numerical native bounds, tree coverage and independent client access remain
unproven. No code changes, entitlement changes, forced identification or permission-cache
writes were made. The [dated record](verification.md#2026-10-11--ax-consumer-installation-transport-providers-and-normal-bundle-loading)
maps retained local source controls and the current investigation boundary.

## Normal Mirroring transport entry and MCK discovery (2026-10-11)

**Runtime and original-image static evidence; no physical AX archive.** Normal host probes
run in their own unentitled processes on local **macOS 26.5.1 / 25F80** and Mac-M2
**macOS 27.2 / 26B5091g**. The latter's loaded MediaContinuityKit UUID is
**5DC6E4AD-E3CE-3505-AABE-9FB830B3ABA2**, Network UUID
**17692953-4248-35A0-A0DC-12685F10E308**. Host paths are
`/System/Library/PrivateFrameworks/MediaContinuityKit.framework/Versions/A/MediaContinuityKit`
and `/System/Library/Frameworks/Network.framework/Versions/A/Network`.
Phone static work uses the original 24A437 cryptex cache: MediaContinuityKit UUID
**9A3DABAB-BE8D-3581-9FB4-CEFE77D9CA4C**, Network UUID
**9EFD671C-0044-395F-9770-7DAAF06EB31B**. Host and phone addresses are not interchangeable.

The normal Rapport entry is a confirmed restriction: an own-process
`RPRemoteDisplayDiscovery.activateWithCompletion:` returns **RPErrorDomain -71168**,
`kMissingEntitlementErr (Missing entitlement 'com.apple.RemoteDisplay')`, immediately on
both host builds. No session or authentication method is called. This bounds this API under
the tested process identity; it does not settle MCK, a broker, or a wire client.

Mac-M2's MCK normal configuration and discovery controls produce a different result:

| Control | Observed result / proof boundary |
| --- | --- |
| Native usage | The native enum's exported case index and its own value witnesses construct and verify `iPhoneMirroring`, case **5**, size **33**, stride **36**. A locally guessed enum layout is not used. |
| Endpoint factory | `MediaContinuityEndpoint.init(usage:deviceID:)` with a synthetic own-process ID, encoded through the actual native Codable conformance, returns `endpointType=applicationService` and **`applicationServiceName=com.apple.MediaContinuityKit.iPhoneMirroring`**. This is a configuration control, not a discovered phone identity. |
| Isolated parameter factories | Native `NWParameters.browserParameters(for:)` returns `udp, multipath service: interactive, attribution: developer, include ble`; `listenerParameters(for:)` returns `udp, multipath service: interactive, no cellular, server, definite, attribution: developer`. Neither creates an active listener or session. These factory results do not identify the actual macOS 27 control-listener stack, resolved below. |
| Native scope/options | The MCK listener scope equals Network's native **personal** constant (2). Native browser options use **personal** (1), **iPhone** device types (1), empty deviceFilter, RSSI **-70**, `applicationServiceEndpointsOnly=false`, and nil customService/predicate. Scope values belong to different native types and must not be compared across them. |
| Ordinary discovery | The public `applicationService(name:)` descriptor and, separately, the native `applicationServiceWithOptions` descriptor containing the unchanged MCK options both reach **ready** with the native browser parameters. Each bounded five-second observation receives no endpoints and ends with **cancelled**. No connection, acceptance or phone response follows. Ready is not authentication or proof of 13 Pro visibility; an empty interval does not identify its cause. |

The local macOS 26 MCK export inventory lacks these macOS 27 parameter/scope/endpoint factory
exports. Its normal control is stopped before invocation; this is not a compatibility shim.
[Apple's application-service API](https://developer.apple.com/documentation/network/nwbrowser/descriptor-swift.enum/applicationservice(name:))
establishes a normal discovery mechanism, but does not promise access to Apple's private
Mirroring service. The private MCK controls above, rather than that public documentation,
establish the exact service name and options on the tested seed.

Current macOS 27 endpoint metadata further bounds a direct-port interpretation:
`MediaContinuityEndpoint` descriptor `0x2975932B4` has serverProtocolVersion and type fields;
its nested EndpointType (`0x2975932D0`) reflects only **applicationService**. CodingKeys at
`0x297593318` are serverProtocolVersion, endpointType, applicationServiceName and deviceID.
No host/port or wired endpoint variant appears in this native representation. A different
ControlConnectionMigrationManager field named isWiredInterfaceAvailable is not evidence of
a USB/CoreDevice bootstrap or an independently accessible RSD port.

Original phone code distinguishes two different listener owners:

- `NetworkBackedControlConnectionListener`, descriptor `0x28ED92908`, has separate
  `shouldAdvertise` and `serviceName` fields. Its builder `0x28EC87F5C` stores supplied
  usage and that Bool, then
  builds `serviceName` using prefix **`com.apple.MediaContinuityKit.`** at original cstring
  `0x28EDA43B0`. The Mirroring branch materializes `iPhoneMirroring` at
  `0x28EC8865C–88690`. The true-Bool path appends the usage name; the false path additionally
  appends `.` and a freshly created UUID's `uuidString`, storing the result at object `+0x98`
  (`0x28EC887C0`). Original helper resolution verifies Swift `String.append`, Foundation
  `UUID.init()` and `uuidString`. This proves name construction, not advertisement or selection
  of this provider in an active phone session.
- The **media-prerequisite** owner is `NetworkBackedMediaConnectionPrerequisitesProvider`,
  descriptor `0x28ED92D28`, resolved through metadata accessor `0x28ED0DC5C`.
  Its synchronous factory `0x28ED102C8`, called at `0x28ED0EBCC`, invokes
  `_nw_parameters_create_secure_udp` at `0x28ED1047C` and sets
  `disable_listener_datapath=1`. Its result is passed into async entry `0x28ED105C4`.
  Resume `0x28ED10714` creates a native 16-bit **zero** port value and passes it with the same
  parameters at `0x28ED10784`. Original Network helper `0x1826B2AA0` takes the zero branch to
  `_nw_listener_create` (`0x1826B2C30`); the nonzero branch uses
  `_nw_listener_create_with_port` (`0x1826B2BCC`). There is no fixed TCP port in this path.
  Actual assigned port, protection options and successful runtime startup remain unmeasured.
  Its field-offset variable `0x2CCACE7D8` belongs to **useLLW0Interface**, not
  `shouldAdvertise`; this Bool controls duplicate-state-update configuration at
  `0x28ED10564–10580`. Setup `0x28ED13B0C` installs two internal Network callbacks in this
  same media preparation path. These calls do not establish the AX control listener or
  an accepted-connection-to-`ConnectionBackedControlStream` edge.
- Control-listener service advertisement and session admission remain unresolved. A separate
  `valueForEntitlement:`
  call at `0x28ECBE4EC` passes a dynamic key. Neither `com.apple.rapport.browse` nor the Coex
  service string is proven to be that key or a gate on this Mirroring listener.

On Mac-M2, an own-process **type metadata only** control resolves the actual native class
dispatch targets without creating any session object: `MediaContinuitySession.activate`
uses metadata slot `+0x260`, async descriptor image offset `0x130A18`, code `0x350C4`;
`makeControlStream` uses `+0x280`, descriptor `0x130A98`, code `0x38B84`.
`MediaContinuityServer.activate` uses `+0xC8`, descriptor `0x130568`, code `0x2E798`.
Offsets belong to the macOS 27 MCK UUID above. Exported dispatch thunks independently
establish the slot offsets. This metadata control invokes none of those methods. The
own-server control below invokes only Server.activate/invalidate; a separate subsequent
Session control is recorded below. No live control stream is established.

**Actual macOS 27 control listener:** native reflection of an own
`MediaContinuityServer(usage: iPhoneMirroring, shouldAdvertise: false)` identifies
`NetworkBackedControlConnectionListener<SessionMessage, StreamMessage>`, descriptor
`0x297595988`. Its `shouldAdvertise` field is object `+0x91`, serviceName `+0x98`, network
listener `+0xB8`, listenerReadyContinuation `+0xC0`, state `+0xE8`. Native startup
`0x2975049B8 → 0x297507F20` reaches the configuration factory at `0x2975290BC`.
Factory closure `0x29752B92C → 0x29752AF58` constructs the concrete stack
**`PropertyList3<SessionMessage> → ApplicationServiceQUIC → IP`**. Setup at
`0x297508330–508344` calls `Listener5.init(for:using:servicePrefixing:serviceScope:)`
with servicePrefixing false and native personal scope. Exact Network export offsets,
rather than nearest-symbol names, resolve these imports. The state handler installed at
`0x29750893C` is `Listener5.stateUpdateHandler`; its readiness continuation is not an
accepted-connection callback. The precise ready/resume branch remains unverified.
Reflection after the failure below independently reports the optional concrete Listener5
type with this same stack. This is a control-channel result on the stated macOS 27 seed;
it must not be replaced with the isolated UDP factories or the phone media-prerequisite path.

**Normal own-server activation:** two bounded, ordinary arm64 processes on Mac-M2 invoke
native Server.activate with the configuration above and a framework-generated UUID service
name. Both fail with the native typed error **`Errors.missingDeviceID`** (bench exit 5).
The observed server/control states become **interrupted**, the network listener is nil,
and normal native invalidate completes with the listener still nil. No ActivationResult,
accepted peer, device connection or authentication result is obtained. This is a reachable
own-process bootstrap failure. The typed error identifies a nil ID; it does not identify an
entitlement check or a physical AX refusal.

**Which ID is missing:** the actual control-listener bootstrap getter `0x29750A7A8`
checks the weak import at `0x2D8059200` and invokes **IDSCopyLocalDeviceUniqueID** at
`0x29750A824` through stub `0x29809EE60`. Nil takes `0x29750ABA8`, constructing the
native error case 2 matching missingDeviceID. A separate normal getter confirms the symbol
exists but returns nil on Mac-M2, retaining only a presence Bool. This is the **host's IDS
identifier**, not the phone UDID or CoreDevice UUID; substituting either would not reproduce
the native bootstrap contract.

Current IDS image UUID **7D6637BC-2D2D-36BF-BFE0-4C7746E1D2D1**, path
`/System/Library/PrivateFrameworks/IDS.framework/Versions/A/IDS`: getter `0x1955805BC`
calls `IDSDaemonController.sharedInstance.blockUntilConnected`, then on the internal queue
block `0x195580740` copies `controller.listener.deviceIdentifier`.
`blockUntilConnected` at `0x1956291E4` can return early when
`IMLockdownManager.sharedInstance.isNonUIInstall` is true (`0x195629214–629224`).
That Bool is **false** in the normal Mac-M2 control. Own CLI and normal LaunchServices GUI
controls instead report **isConnected=false, isConnecting=true, remoteObjectExists=true**
and a non-nil IDSDaemonListener, with ID still nil after five seconds. Matching console/SSH
UIDs and the GUI control exclude a simple wrong-user or SSH-only explanation under these
observations. The same ordinary unentitled CLI on local macOS 26 obtains a non-nil ID and
isConnected=true; this comparison does not validate the macOS 27 MCK APIs on macOS 26 or
exclude a changed macOS 27 policy. Native `connectionComplete:withResponse:` is independently
located at `0x195636E78`; its queued body calls `setupCompleteWithInfo:` at `0x195636F94`.
A subsequent own-process interposer observes only service name, returned object type,
elapsed time and the native protocol's **granted** Bool; it leaves the original request,
response and callback unchanged. Both hosts' synchronous request to
**com.apple.identityservicesd.desktop.auth** returns a dictionary in less than one millisecond
in the retained paired runs, with setupInfo absent. The macOS 27 reply has a present Bool
**granted=false**; local macOS 26 has **granted=true**. This agrees with the uninterposed
ID/state controls. Exact native response code at `0x195638DC4–638E4C` reads setupInfo and,
when absent, granted; it inverts that Bool at `0x195638EDC` before the continuation call.
The synchronous reply itself is not hanging. The service-side refusal is localized below;
later completion behavior and other session/account prerequisites remain unverified.
The grant observation is from the instrumented own-process control, not native Mirroring or
a 13 Pro session. No ID value, setupInfo contents or account inventory is printed or retained.

**Service-side cause for the tested normal client:** the Mac-M2 executable
`/System/Library/PrivateFrameworks/IDS.framework/identityservicesd.app/Contents/MacOS/identityservicesd`
has two slices, UUIDs **38332636-ADA2-39DE-8E7C-CDE364838059** and
**8C98537D-B8A7-3E1E-91D0-714CA62D7F39**. Both contain the same admission structure;
the running slice is not measured. The concrete
`daemonInterface:shouldGrantAccessForPID:auditToken:portName:listenerConnection:setupInfo:setupResponse:`
callback starts at first-slice `0x100381790` / second-slice `0x1003788A4`.
It extracts IDS entitlements from the caller's audit token. When none is present, it tests
**IDS/EnforceFirstPartyListeners** and, when enabled, classifies the caller using
`SecTaskCreateWithAuditToken`, `SecTaskGetCodeSignStatus` and an internal-security-policy
predicate. First-slice helper `0x1003F3AA8` / second-slice `0x1003EA400` compares signing
status masks; no signing/team identifier values are required by the probe. Main resolution
of selector stub `0x100A971E0` also closes the static grant-handler call at `0x1001AD704`
to this callback selector, without assigning the unnamed handler a guessed method name.

Normal, read-only own-process controls report **EnforceFirstPartyListeners=true on Mac-M2**
and **false on local macOS 26**; both own binaries fail the native classifier's two status
mask comparisons. RejectDataSeparatedClients is true on both hosts. Crucially, a fresh
**uninterposed** normal Mac-M2 probe, PID **69622**, still returns nil ID / connecting state;
a daemon log query restricted to this PID and the static first-party-enforcement prefix
finds **one rejection event and zero allow events**, selecting
`REJECTING 3rd-party caller with no entitlements`. Only these counts/branch Bools are retained.
This confirms execution of the first-party rejection branch for that client; it is not
merely a feature-flag correlation or an interposer artifact. This normal IDS-dependent
MCK bootstrap entry is therefore restricted for the tested unentitled third-party process.
The control changes no flags, signing, entitlements or account state. It neither establishes
an authorized outgoing MCK session nor excludes a legitimate broker, another provider or
an independently reachable device wire service.

**Outgoing Session is a separate entry:** a normal own-process constructor, using a
synthetic endpoint ID and nil optional UUID, completes with state inactive. Native reflection
identifies connectionVendor as **NetworkBackedControlConnectionVendor**, with connection and
migration manager nil. The exact initializer export demangles to
`Session.init(usage:endpoint:clientSessionID:)`; the optional UUID is a **session ID**, not
clientDeviceID. No ID value is retained. Main also resolves the indirect call at
`0x29748C2E8` to a Logger value-witness copy, not a connection-vendor operation; a peer's
earlier interpretation of that instruction is excluded.

The actual activation chain reaches `0x29749ADA8 → 0x297492CB8`. Its continuation checks
Session.connection (`+0xA8`) and connectionVendor (`+0xD0`), then schedules closure
`0x2974BBC78 → 0x2974933E8`. The latter projects the vendor and copies usage, remoteEndpoint
(`+0x378`) and clientSessionID (`+0x290`) before entering async code `0x2974A5F10` through
descriptor `0x297588150`. Own metadata-only controls verify the field-offset variables;
these are not heap or identity-value reads.

In that outgoing helper, exact Network export matches establish browser options construction
at `0x2974A6530`, **ApplicationService** provider creation at `0x2974A6594`, native Browser2
allocation at `0x2974A65D0`, and its asynchronous results iterator. A result's NWEndpoint
deviceID is read at `0x2974A6B24` and compared against the supplied endpoint ID before selection
on the tested iPhoneMirroring branch. After selection, `0x2974A7550` constructs configuration
using **PropertyList3 / ApplicationServiceQUIC / IP**; `0x2974A71A0` calls exact
`Connection3.init(to:using:)`. This closes a static outgoing discovery-to-connection path;
it is not a discovered phone endpoint or authentication result. Its lower-layer policy,
successful admission and any later IDS dependency are not excluded by these instructions.

A separate normal own Session.activate control, with nil incoming video/audio configurations
and a synthetic endpoint ID that cannot match a real device, returns native
**TaskTimeoutError.timedOut after 10,253.224 ms** (bench exit 5), rather than missingDeviceID.
State becomes interrupted and normal native invalidate completes. Native event-stream metadata
and the exported thunk's indirect return convention are checked before invocation. The bench
log's `synthetic_device_filter` caption refers to the final endpoint-ID match; it does not
establish a nonempty NWBrowser.Options.deviceFilter. No makeControlStream, accepted peer or
phone operation occurs. This distinguishes the observed activation failures, without proving
that an actual phone is discoverable, that browser results are unrestricted, or that the
outgoing path can replace the provider used by native Mirroring.

The other prepared control does **not** subscribe to AX. Normal `dlopen` of the own bench
dylib in native local Mirroring is rejected first by its sandbox, then by architecture,
and finally, with matching arm64e in the native temporary directory, by platform
library validation. The handle stays nil and no bench send/publisher function executes.
Passive taps are detached without a new session hit. This is a failed loader preflight,
not an AX protocol refusal or proof that all passive observation is unavailable.

**Next discriminator:** establish which endpoint the phone's actual MCK provider publishes,
whether it uses the canonical or UUID service name, and how native Mirroring chooses and
exchanges that endpoint. Then resolve legitimate broker/provider access and acceptance into
an actual control stream. Do not infer the native host/phone listener roles from wrapper names
or treat the synthetic outgoing timeout as a successful independent entry.
Retain native personal scope and legitimate session authorization. A physical initial archive,
native rectangles, coverage and latency are still required. The
[dated record](verification.md#2026-10-11--normal-rapport-entry-mck-discovery-and-native-loader-preflight)
maps local controls and cleanup.

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

### AXAudit physical selection, action and issue handoff (2026-10-09)

**Runtime seed:** macOS 26.5.1 (25F80), Xcode 27 Beta 6 / Inspector 192.6,
CoreDevice 642.15, DDI 27A5252f; unlocked wired iPhone 13 Pro (iPhone14,2),
iOS 27.0 (24A437), Calculator PID 51031. The user explicitly reassigned this round
to the 13 Pro. Direct sessions used paired USB lockdown with pymobiledevice3 11.10.2.
This is supplemental research, not the macOS 27 release gate. Condensed reproduction
and local sources are in the [dated verification](verification.md#2026-10-09--13-pro-axaudit-finger-injection-apple-action-and-issue-handoff).

**Selection is a device push on this physical seed.** A fresh Next focus supplied a
matching Calculator token before each independent trial. The actual metadata replies
were integer `2` for `deviceInspectorSupportedEventTypes` and `false` for
`deviceInspectorCanNavWhileMonitoringEvents`; the integer is not an enumerated list.
Navigation used monitoring 0, followed by monitoring 2 and visuals true. The operator's
confirmed finger tap on History and one `ipb tap 0.10 0.08` each produced
`hostInspectorCurrentElementChanged:` with caption `历史记录, 按钮` and a 20-byte
token belonging to the current PID. Neither trial sent
`deviceFetchElementAtNormalizedDeviceCoordinate:`. Each also received monitoring 0
after selection, before host cleanup: re-arm monitoring before another point selection.
The existing Calculator value 7 was preserved; selecting did not open History.

Apple Inspector independently selected the same logical button after its **actual**
target request became 51031 and it sent monitoring 2. Earlier blank UI in this round
corresponded to target 0 and lacked that complete setup; a visible menu choice alone
is insufficient target evidence. Apple queried the ten received read-only descriptors:
Label=`历史记录`, Identifier=`SidebarButton`, traits/input labels populated, class/
address/controller nil, hierarchy one node. A subsequent independent direct session
with a newly received token reproduced these values. It sent no explicit
`deviceInspectorEnable:1`; this was a post-Apple daemon state, not a cold-start test.
The original September selection failure remains un-root-caused. The new positives
disprove an inherent inability of injected touches to select elements on this seed.

**Captured Apple action shape:** channel 0 DISPATCH, reply expected; selector
`deviceElement:performAction:withValue:` with three object arguments: the freshly
transported `AXAuditElement_v1` (including AccessibilityIdentifier), the received
`AXAuditElementAttribute_v1` for `AXAction-2010` / Activate / PerformsAction=true /
ValueType=1, and **NSNull**, not integer 0. Apple's reply was type-0 empty OK.
One independent direct submission used a fresh matching element, the captured action
descriptor, null value and reply expectation; it also received empty OK. Screenshots
after both actions still showed Calculator 7, without the History sheet. Thus an
advertised action and successful DTX completion do not establish activation effect.
The installed pmd3 `perform_press` uses integer 0, no reply, and a different token
wrapper; that is a source-level difference, not the cause of this result, since the
Apple-shaped submission also had no observed effect. No permission/entitlement cause
was established and no uncertain action was retried.

**Issue geometry is now coherently associated.** Direct and Apple audits each completed
the seven advertised audit types and returned one issue: classification 1000,
`testTypeSufficientElementDescription`, identifier `StandardInputView;value:7`,
`ElementRectValue_v1={{16, 243}, {358, 88}}`. Apple single-selection sent
`deviceHighlightIssues:` with the transported issue array. Double-click then sent
monitoring 0, visuals false, `deviceInspectorFocusOnElement:` with the issue's element,
and **`deviceInspectorLockOnCurrentElement`**. The resulting focus callback had the
same token/PID/identifier. Its label/value were nil; the identifier, displayed 7 and
highlighted output area provide the cross-check. Apple's screenshot metadata was
390×844 logical bounds, native scale 3, rotation 0; the 1170×2532 phone screenshot's
highlight agrees with the issue rectangle (48,729,1074,264 in native pixels).

Inspection read ordinary descriptors and hierarchy after the handoff; it did not
request an ordinary Frame or gain a Frame descriptor. The issue rectangle is therefore
associated with an element, but does not establish arbitrary-node bounds, a complete
view tree or a native coordinate hit-test API. Mac-target AXFrame requests also occur
in the retained Inspector capture on another DTX connection; they must not be paired
with phone replies merely by message identifier. Incoming parser identity and outgoing
transmitter identity are retained to prevent that false positive.

### AXAudit development-app action and resolved task-port predicate (2026-10-09)

**Seed/source:** same macOS 26.5.1 / Xcode 27 B6 / CoreDevice 642.15 / DDI 27A5252f /
physical iPhone14,2 iOS 27.0 **24A437** as the preceding capture. Device identity and unlock/
Developer Mode were refreshed. No Runner, installation or certificate change was used.
The [dated verification](verification.md#2026-10-09--13-pro-development-app-action-and-task-port-predicate)
records the reproduction, negative attempts and local source references.

**Runtime development-app control:** the device's InstallationProxy lookup reports existing
Looktech Lab `ai.looktech.glasses.memo.lab` 1.20.0 (514), ProfileValidated=true and
`get-task-allow=true`; it does not report `task_for_pid-allow` for that app. Calculator's returned
entitlement dictionary has neither key. This is current installation-database evidence, not
an independent extraction of the installed CodeDirectory/provisioning profile.

A new direct USB AXAudit session explicitly enabled inspection, targeted the freshly observed
Lab PID **51300**, used monitoring 0 and received the gear-button focus. It reused the received
element and advertised descriptors. Class=`SwiftUI.AccessibilityNode` and
Address=`0x1480f3200` were populated; Controller was nil. Label/traits/input labels and the
hierarchy described the same gear control. The received sections still contained the ten
ordinary read descriptors and Activate, with no ordinary Frame descriptor.

Exactly one `deviceElement:performAction:withValue:` used the freshly transported element,
its received `AXAction-2010` descriptor, null third argument and expected reply. On this
connection request **18** received conversation-1 **type-0 empty OK**. The before/after
screenshots show the Lab Home page changing to its Settings sheet. This establishes a real
runner-free semantic activation for this development-app control. The preceding Calculator
action had the same completion class but no visible effect. App/control, implementation and
entitlements differ together; this is not a single-variable proof that `get-task-allow` causes
the difference, nor a promise of activation across arbitrary applications. Empty OK still
does not encode the semantic result.

**Static physical predicate, now resolved:** the 13 Pro's RemoteFetchSymbols service supplied
the matching raw dyld cache and subcaches through a paired userspace RSD tunnel. The raw
cache image records match the cached AccessibilityAudit UUID
`43AC666C-80EB-3B45-83D2-C8236CA7A958` and libsystem_kernel UUID
`5A7DC6BE-551B-3B29-A928-A4079A90D4D2`.

| Source | Decisive mapping |
| --- | --- |
| `AccessibilityAudit` at `0x24fdcd750` | Moves PID to argument 1, loads the task-port global through `0x2681b5678`, passes a local result address as argument 2, calls `0x2500f90b0`, returns true iff the return is zero. |
| Raw `dyld_shared_cache_arm64e.47`, UUID `A0206327-4470-3275-89CD-5C4DEC7A42F4`, file offset `0x650b0` | `adrp x16, 0x237ef7000; add x16, x16, 0xcb4; br x16`: target `0x237ef7cb4`, matching the extracted libsystem_kernel export `task_for_pid`. |
| Raw `.54.dylddata`, UUID `9028CF30-E253-3E43-BED5-B6C8908E84F7`, cell file offset `0xed678` | The cell is in the retained version-5 slide chain. Raw `0x100000f00b8078` decodes to the 34-bit runtime offset `0xf00b8078`; adding value_add `0x180000000` gives `0x2700b8078`, matching `mach_task_self_`. |

The pointer interpretation follows Apple's [dyld cache format](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld_cache_format.h)
and [shared-cache fixup definition](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/fixup-chains.h),
also checked against the Xcode 27 SDK header. Thus this physical framework's predicate is
`task_for_pid(mach_task_self_, pid, &task) == KERN_SUCCESS`. It is a task-port success check,
not a literal entitlement-key comparison. This cache/DDI investigation did not supply the
standalone daemon. The following firmware investigation resolves the matching physical
property/action/parameterized handlers; the older Simulator comparison remains separate evidence.

**Geometry remains open:** no Frame was received through AXAudit in this development-app
control. The current UIKit SDK declares native `accessibilityFrame` in screen coordinates,
which suggests an app-debugger route once a valid object is available. A fresh Lab focus supplied
addresses for this bounded follow-up, but debugger attachment did not yield a usable stopped
target and no class/Frame getter executed. This is unverified, not a negative Frame result.
The extra Apple Inspector attempt also remained at Connecting to target; its four outgoing
messages and zero incoming messages do not form a physical selection/action reference.

### AXAudit physical daemon handlers, permission logs and element preview (2026-10-09)

**Seed/source:** macOS 26.5.1 (25F80), Xcode 27 B6 / Inspector 192.6 / CoreDevice 642.15 /
DDI 27A5252f, the allocated physical iPhone14,2 running iOS 27.0 **24A437**. Doctor again
reported an unlocked wired device and no failures. This is supplemental research, not the
supported macOS 27 release gate.

The daemon was extracted read-only from the OS filesystem of Apple's
[iPhone14,2 27.0 / 24A437 restore firmware](https://updates.cdn-apple.com/2026FallFCS/3337f675-bd6c-49e2-9d4a-7b59095d07e5/iPhone14,2_27.0_24A437_Restore.ipsw).
BuildManifest and SystemVersion confirm the product/build. The exact ZIP member
`043-69835-656.dmg.aea` has 8,321,499,136 bytes, a verified central-directory CRC32 of
`6da9e705` and computed SHA256 `39153f89b2d38930fbf9eee2a235b510d35ed064f00c1663ff1452693f23b935`.
The whole IPSW was not downloaded or hash-verified. AEA decryption and a read-only APFS parser
supplied `/System/Library/PrivateFrameworks/AccessibilityAudit.framework/Support/axauditd`:
179,312 bytes, SHA256 `5278c0dc4dc62cc8801840e047381924a50cdae246abf67ec986522a6e66aec8`,
arm64e Mach-O UUID **08B6FBF3-3EF9-34FD-B86F-8DCA4E4D6616**. Live daemon-only syslog reports
the **same image and process-image UUID**, linking the static binary to this phone's running
daemon. All addresses below are unslid addresses in this executable, not Simulator addresses.

**Disassembly/metadata evidence:** `otool -ov/-tvV`, `nm -m` and ipsw 3.1.732 annotated
disassembly/chained fixups resolve the following paths. Local source references are in the
[dated verification](verification.md#2026-10-09--13-pro-physical-axauditd-handlers-permission-logs-and-preview).

| Entry/source | Concrete behavior on this seed |
| --- | --- |
| `XADInspectorManager element:valueForParameterizedAttribute:withObject:completion:` at `0x1000058ec` | Five instructions invoke the supplied completion with nil. No parameterized AX request occurs. The server entry at `0x10000a5b4` decodes and forwards to this method. Thus advertising this RPC does not expose XCTest's parameterized snapshot attribute 95006. |
| `element:valueForAttribute:completion:` at `0x100005350` | Compares a fixed set of names: Label, Header, Hint, UserInputLabels, Traits, ElementClassName, ElementMemoryAddress, ElementViewControllerClassName, Identifier, TraitsHumanReadable, Value and the four imported human-readable/hierarchy attributes. The final comparison at `0x1000058c4` sends unknown names to nil at `0x100005480`. There is no Frame, AXFrame, Position or Bounds branch and no generic name-to-native-attribute forwarding. |
| `_developerOnlyAttributes` at `0x100002f7c` and constant array at `0x100019248` | The array count at `0x100019250` is 3; its chained-fixup targets are the ClassName, MemoryAddress and ViewControllerClassName strings at `0x1000186f0/710/730`. Their ordinary-property reads require `AuditDoesAllowDeveloperAttributes` at `0x100005450`; a false result reaches nil through `0x100005478–480`. The human-readable class-name branch separately checks the same predicate at `0x100005820`. |
| Property result processing at `0x1000054ac–53c` | With developer permission false, NSString and NSAttributedString results of length at least 65 are truncated to the first **64 UTF-16 code units**. This is a static bound, not a measured long-text example or a claim that every nested string is truncated. |
| Property focus-history filter at `0x1000053ac–3fc` | An element that differs from the current focus but is already in focused-element history completes nil. A cached token is therefore not an unrestricted permanent read handle. |
| `allowDeveloperActionsOnElement:` at `0x100004a1c` and action manager at `0x100004a60` | Resolve the element PID, then call the task-port predicate. False branches at `0x100004ac8` skip native action execution. Recognized `AXAction-` four-character suffixes invoke native `performAction:` at `0x100004b40` when their integer value is in 2000..10000; the native return value is discarded. Custom-action suffixes instead supply the value for action 2021. All paths invoke the same void completion at `0x100004bb0`. |
| Server action block `sub_10000a194` / completion `sub_10000a2ac` | The RPC's third argument is discarded; `0x10000a278` explicitly passes nil to the manager. Completion at `0x10000a2b0–2b8` supplies nil return value and nil error irrespective of the manager's action path. Empty OK cannot distinguish permission denial, unrecognized action or native action outcome. Changing only the null/0 third argument cannot repair that distinction on this seed. |
| Hierarchy helper `sub_10000511c`, child helper `sub_100004fb8` | Builds a parent chain and selected child/sibling context, not a recursive all-view snapshot. Parent traversal checks the task-port predicate at `0x10000527c` and stops on denial. Child serialization adds index 50 before stopping at `0x100005090`, so each such collection is capped at **51** entries. This now has physical-device binary evidence. |
| `fetchElementAtNormalizedDeviceCoordinate:` at `0x100005b6c` | Passes the received CGPoint unchanged to systemWideElement's `elementForAttribute:parameter:` with native numeric attribute **91701** at `0x100005c58–64`. Requests within **0.1 s** return the previous cached result; the constant is at `0x1000115a8`. The server reads CGPointValue at `0x10000ad68`. No coordinate scaling or explicit platform guard occurs in these two handlers. This does not establish that backend 91701 works on iOS; the earlier nil result remains unresolved. |

The daemon's embedded entitlements include `com.apple.accessibility.api`,
`com.apple.accessibility.axauditd`, `com.apple.accessibility.voiceover`, QuartzCore global/secure
capture and SpringBoard debug applications. Neither `task_for_pid-allow` nor `get-task-allow`
is present in this dictionary. These literals alone do not explain kernel task-port policy.

**Runtime permission discriminator:** paired USB AXAudit and daemon-only OsTrace syslog were
recorded together using pymobiledevice3 11.10.2. The focus-builder at `0x100003bb4` calls the
same resolved task-port predicate, then emits its YES/NO at `0x100003c24`:

| Current matching focus | Daemon log | Reads using received descriptors |
| --- | --- | --- |
| Calculator PID **51502**, History / SidebarButton | `allowDeveloperAttributes: NO` | Label=历史记录; ClassName, MemoryAddress and Controller=nil. |
| Existing Lab PID **51452**, gear button | `allowDeveloperAttributes: YES` | Label=齿轮形状; ClassName=SwiftUI.AccessibilityNode; MemoryAddress=0x15b013840; Controller=nil. |

This establishes the predicate's actual outcome during these selections and its agreement
with property filtering. It strengthens the authorization explanation for the earlier
Calculator/Lab action difference; it does not isolate which entitlement/kernel policy causes
task_for_pid success, or retroactively trace the earlier action invocation. No semantic action
was sent in these probes. An initial same-session switch to Lab produced no matching focus
and stopped before Lab reads; a fresh Lab session with app monitoring enabled succeeded.
Those state changes do not isolate the initial selection failure's cause.

**Geometry available to preview, with a positive physical control:**
`previewOnElement:` at `0x100004980` obtains the transported native element and calls
`XADDisplayManager setCursorFrameForElement:` at `0x1000049e0`. The latter clears cached frame
and visible frame, refreshes native attribute **2003**, and calls the native **frame** getter
at `0x100008734`. It passes frame/path/context to rendering at `0x100008924`. Neither of these
two handlers calls the task-port predicate. This is local geometry consumption, not a Frame
response to the host.

The physical server's `_deviceCaptureScreenshot` at `0x1000092f4` first calls
`hideVisualsSynchronously` at `0x10000931c`, then supplies **CGRectZero** to the platform plugin's
`screenshotInfoForTransportWithFrame:` at `0x100009344–354`. It does not read the renderer's
`_currentCursorFrame` getter at `0x100008994`. Thus the screenshot selector is not a demonstrated
direct export of the preview rectangle; the pixel-difference control below used ipb's separate
devicectl screenshot path, which retained the overlay.

A fresh Calculator History token (PID 51502, identifier SidebarButton) was received on a new
connection. With the daemon still logging developer permission NO, the host sent
`deviceInspectorShowVisuals:(true)` and `deviceInspectorPreviewOnElement:(received element)`.
The screenshot shows the matching top-left History control highlighted, while 7 and the page
remain unchanged. Before/after raster differences above channel threshold 8, 16 or 32 all
occupy the half-open pixel box **[54,147,174,267)** in 1170×2532 images: approximately
**x=18, y=49, width=40, height=40** logical points under the previously confirmed scale 3.
This is an **overlay extent measured from pixels**, not a transported CGRect or proof of
the element's exact accessibilityFrame. No audit issue was needed for this ordinary control.

**Inference/next boundary:** element-specific preview plus screenshot comparison is a viable
geometry fallback candidate on this seed, including this permission-denied system app.
Dynamic content, overlay padding/path, occlusion, scrolling, rotation and token lifetime still
need controls before any reusable bounds API. The renderer's internal geometry and backend
91701 are concrete investigation targets; more guessed Frame names cannot bypass these
fixed handlers. A full page snapshot and a runner-free XCTest snapshot session remain unproven.
