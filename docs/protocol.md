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

`connectedServices` is the next important gap: the Swift async protocol methods are visible, but the current generic `sendSync(value:)` ABI shim does not decode a reply successfully yet.

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

- `connectedServices` and `connectedServiceIDs` are visible in symbols but not yet successfully decoded through the current CLI.
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
