# devicehubctl

`devicehubctl` is a small CLI for driving basic iOS 27 device interactions through CoreDevice private services, without XCUITest or WebDriverAgent.

It was extracted from a macOS 27 / Xcode 27 beta Device Hub investigation. The current implementation covers tap, long press, swipe, scroll, keyboard keys, pointer reports, scroll reports, raw scroll events, vendor-defined HID events, Home, App Switcher, screenshots, and descriptor-based HID service discovery.

The basic interaction path is verified, and the CLI now uses DeviceHub's async descriptor-discovery path to resolve the touchscreen service when `UHID_SERVICE_ID=auto`.

## Requirements

- A host whose installed CoreDevice package is 636.x or newer. This ships with Xcode 27 beta (`XcodeSystemResources.pkg`); it is what puts `UniversalHIDService`, the `HIDServiceID` helpers, and the embedded `UniversalHID.framework` into `/Library/Developer/PrivateFrameworks`.
- Xcode 27 beta on the host. Its minimum macOS is 26.4, so macOS 26.4+ hosts qualify as well as macOS 27 beta hosts. The link step needs the beta SDK's private-framework stubs, and the beta's iOS DDI is what installs the device-side HID daemon (`dtuhidd`).
- A connected iOS 27 device visible to `xcrun devicectl`, with the Xcode 27 beta DDI mounted.
- GitHub-hosted code should be treated as beta/private-ABI research, because Apple may change these interfaces between seeds.

Xcode 26.x hosts cannot run this tool as-is: CoreDevice 518.x lacks the UniversalHID service protocol, and the Xcode 26 DDI ships no HID daemon, so every `feature.remote.hid.*` / `universalhidservice` socket request is refused with "Create Service Socket is not supported by this device".

The Xcode used for building and for `screenshot` is taken from `xcode-select -p`, which honours `DEVELOPER_DIR`:

```sh
export DEVELOPER_DIR=/path/to/Xcode-beta.app/Contents/Developer
```

Override it at build time with `XCODE_PATH=/path/to/Xcode-beta.app` if you prefer.

## Build

```sh
make
```

The helper binary is written to:

```sh
build/action_sender_mercury
```

## Usage

Touch coordinates are normalized from top-left to bottom-right, in the `0..1` range. Pointer deltas are signed relative integers.

```sh
bin/devicehubctl tap 0.5 0.5
bin/devicehubctl long 0.615 0.675 1.2
bin/devicehubctl scroll 0.5 0.75 0 0.30
bin/devicehubctl swipe 0.5 0.75 0.5 0.35
bin/devicehubctl home
bin/devicehubctl recents
bin/devicehubctl screenshot build/current.png
bin/devicehubctl service-ids
bin/devicehubctl services
bin/devicehubctl service-id touchscreen
bin/devicehubctl reset-gesture
bin/devicehubctl pointer 0 0
bin/devicehubctl scroll-report 0x501 0 0
bin/devicehubctl scroll-event 0 0 0
bin/devicehubctl vendor-defined 0 0 0
bin/devicehubctl key escape
bin/devicehubctl button 0x0c 0x40
bin/devicehubctl raw com.apple.coredevice.feature.remote.universalhidservice cd_uhid_tap 0x101 0.5 0.5
```

`DEVICE_ID` is optional. Without it the wrapper picks the single wired or tunnelled physical device; with several devices it lists them and exits. Use the CoreDevice UUID from `devicectl list devices --json-output` (the 642.x table view prints UDIDs, which the service rejects):

```sh
DEVICE_ID=<coredevice-uuid> bin/devicehubctl tap 0.5 0.5
```

Useful runtime overrides:

```sh
DEVICE_ID=<coredevice-uuid>          # pick a device explicitly
UHID_SERVICE_ID=auto                 # or a fixed id such as 0x101
UHID_SERVICE_FALLBACK=0x101          # opt in to a fixed id when descriptor discovery fails; unset = error
DEVELOPER_DIR=/path/to/Xcode-beta.app/Contents/Developer   # only needed for `make`; runtime uses the CoreDevice package
DEVICECTL=/path/to/devicectl         # defaults to the copy inside CoreDevice.framework
DEVICEHUBCTL_BIN=/path/to/action_sender_mercury
HIDCTL_WAIT_MS=700                   # settle time after each send
HIDCTL_TIMEOUT_S=30                  # watchdog for a single helper run
```

`UHID_SERVICE_ID` defaults to `auto`: the wrapper calls `connectedServiceDescriptors()` and selects the descriptor whose product is `CoreDevice touchscreen(nil)`. If discovery fails the command exits 3 unless `UHID_SERVICE_FALLBACK` is set.

Exit codes from the helper: 0 ok, 1 a dispatched operation or the remote connection reported failure, 2 usage or local error, 3 CoreDeviceService refused the service socket (the CoreDevice error is printed), 4 the device tunnel is not connected, 5 watchdog timeout. On 4 the wrapper warms the tunnel once with `devicectl device info details` and retries; nothing has been sent to the device at that point.

Supported `service-id` roles:

```sh
bin/devicehubctl service-id touchscreen
bin/devicehubctl service-id gesture
bin/devicehubctl service-id keyboard
bin/devicehubctl service-id buttons
bin/devicehubctl service-id avp
```

## Smoke gate

```sh
scripts/smoke_matrix.sh . build/smoke            # host-only, discovery, and non-destructive reports
SMOKE_INTERACTIVE=1 TAP_XY="0.15 0.12" scripts/smoke_matrix.sh . build/smoke   # adds home, tap, recents, swipe, scroll, long, key
```

Every step must exit 0 and, where stated, print the expected output; the script exits non-zero otherwise. Screenshots before and after each interactive step land in the output directory; identical consecutive frames are reported as warnings because a system alert can legitimately freeze the screen.

## Interaction Backends

- `tap` and `swipe`: UniversalHID service
- `scroll`: UniversalHID service
- `pointer`: UniversalHID pointer report to the `gesture`/trackpad service
- `scroll-report`: UniversalHID scroll report to the `gesture`/trackpad service
- `scroll-event`: CoreDevice HIDScroll event to the standalone scroll feature
- `vendor-defined`: CoreDevice HIDVendorDefined event to the standalone vendor-defined feature
- `key`: UniversalHID keyboard report to the `keyboard` service
- `long`: CoreDevice HID digitizer with repeated hold pulses
- `home`: CoreDevice HID button service
- `recents`: CoreDevice HID digitizer bottom-edge gesture
- `screenshot`: `devicectl device capture screenshot`, using the copy shipped in the CoreDevice package

`CoreDevice.framework` exposes `HIDKeyboard` and `HIDPointer` protocols, but on the verified Xcode 27 beta 2 build their implementations are `UniversalHIDKeyboard` / `UniversalHIDPointer` adapters backed by the UniversalHID service, not separate `feature.remote.hid.keyboard` or `feature.remote.hid.pointer` sockets.

## Verified Scope

The interaction commands below were manually verified against an iPhone 13 Pro on iOS 27.0 with the Xcode 27 beta 2 host stack (CoreDevice 636.3). See [docs/verification.md](docs/verification.md) for the later compatibility re-check against Xcode 27 beta 6 / CoreDevice 642.15, which covers the build and host-side paths and lists what still needs an attached device.

Verified on that beta 2 stack:

- tap opens an app
- long press opens a context menu
- scroll moves a list
- swipe moves a list
- key sends a UniversalHID keyboard report to `CoreDevice keyboard`
- pointer sends a zero-movement UniversalHID pointer report to `CoreDevice touchscreenGesture`
- scroll-report sends a zero-movement UniversalHID scroll report to `CoreDevice touchscreenGesture`
- scroll-event sends a zero-movement `CoreDevice.HIDScroll` event through `IndigoHIDScroll`
- vendor-defined sends a zero-length `CoreDevice.HIDVendorDefined` event through `IndigoHIDVendorDefined`
- Home returns to SpringBoard
- Recents opens App Switcher
- descriptors returns five CoreDevice HID services on the verified device

See [docs/verification.md](docs/verification.md) for the exact command set used.

See [docs/protocol.md](docs/protocol.md) for the current protocol map, symbol evidence, and known gaps.
