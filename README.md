# devicehubctl

`devicehubctl` is a small CLI for driving basic iOS 27 device interactions through CoreDevice private services, without XCUITest or WebDriverAgent.

It was extracted from a macOS 27 / Xcode 27 beta Device Hub investigation. The current implementation covers tap, long press, swipe, scroll, Home, App Switcher, and screenshots.

## Requirements

- macOS 27 beta host
- Xcode 27 beta with CoreDevice private frameworks
- A connected iOS 27 device visible to `xcrun devicectl`
- GitHub-hosted code should be treated as beta/private-ABI research, because Apple may change these interfaces between seeds

The default Xcode path is:

```sh
/Applications/Xcode-27.0.0-Beta.2.app
```

Override it with either `XCODE_PATH` for build time or `DEVELOPER_DIR` for runtime.

## Build

```sh
make
```

The helper binary is written to:

```sh
build/action_sender_mercury
```

## Usage

Coordinates are normalized from top-left to bottom-right, in the `0..1` range.

```sh
bin/devicehubctl tap 0.5 0.5
bin/devicehubctl long 0.615 0.675 1.2
bin/devicehubctl scroll 0.5 0.75 0 0.30
bin/devicehubctl swipe 0.5 0.75 0.5 0.35
bin/devicehubctl home
bin/devicehubctl recents
bin/devicehubctl screenshot build/current.png
```

Set `DEVICE_ID` when more than one device is connected:

```sh
DEVICE_ID=<device-uuid> bin/devicehubctl tap 0.5 0.5
```

Useful runtime overrides:

```sh
DEVICE_ID=<device-uuid>
DEVELOPER_DIR=/Applications/Xcode-27.0.0-Beta.2.app
DEVICEHUBCTL_BIN=/path/to/action_sender_mercury
HIDCTL_WAIT_MS=700
```

## Interaction Backends

- `tap` and `swipe`: UniversalHID service
- `scroll`: UniversalHID service
- `long`: CoreDevice HID digitizer with repeated hold pulses
- `home`: CoreDevice HID button service
- `recents`: CoreDevice HID digitizer bottom-edge gesture
- `screenshot`: `xcrun devicectl device capture screenshot`

## Verified Scope

The current build has been manually verified against an iPhone 13 Pro on iOS 27.0 for:

- tap opens an app
- long press opens a context menu
- scroll moves a list
- swipe moves a list
- Home returns to SpringBoard
- Recents opens App Switcher

See [docs/verification.md](docs/verification.md) for the exact command set used.
