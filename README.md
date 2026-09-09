# ipb

`ipb` (iOS Physical-device Bridge, "the adb for iPhone"; formerly devicehubctl and briefly hdb) is a small CLI for driving basic iOS 27 device interactions through CoreDevice private services, without XCUITest or WebDriverAgent.

It was extracted from a macOS 27 / Xcode 27 beta Device Hub investigation. The current implementation covers tap, long press, swipe, scroll, keyboard keys, pointer reports, scroll reports, raw scroll events, vendor-defined HID events, Home, App Switcher, screenshots, and descriptor-based HID service discovery.

The basic interaction path is verified, and the CLI now uses DeviceHub's async descriptor-discovery path to resolve the touchscreen service when `UHID_SERVICE_ID=auto`.

## Requirements

- A host whose installed CoreDevice package is 636.x or newer. This ships with Xcode 27 beta (`XcodeSystemResources.pkg`); it is what puts `UniversalHIDService`, the `HIDServiceID` helpers, and the embedded `UniversalHID.framework` into `/Library/Developer/PrivateFrameworks`.
- Xcode 27 beta on the host. Its minimum macOS is 26.4, so macOS 26.4+ hosts qualify as well as macOS 27 beta hosts. The link step needs the beta SDK's private-framework stubs, and the beta's iOS DDI is what installs the device-side HID daemon (`dtuhidd`).
- A connected iOS 27 or iOS 26.6+ device visible to `xcrun devicectl`, with the Xcode 27 beta DDI mounted. On iOS 26 the `touchscreenGesture` service is absent, so `pointer` and `scroll-report` are iOS 27 only; see `docs/verification.md`.
- GitHub-hosted code should be treated as beta/private-ABI research, because Apple may change these interfaces between seeds.

Xcode 26.x hosts cannot run this tool as-is: CoreDevice 518.x lacks the UniversalHID service protocol, and the Xcode 26 DDI ships no HID daemon, so every `feature.remote.hid.*` / `universalhidservice` socket request is refused with "Create Service Socket is not supported by this device".

The Xcode used for building and for `screenshot` is taken from `xcode-select -p`, which honours `DEVELOPER_DIR`:

```sh
export DEVELOPER_DIR=/path/to/Xcode-beta.app/Contents/Developer
```

Override it at build time with `XCODE_PATH=/path/to/Xcode-beta.app` if you prefer.

## Install (Homebrew, stage 1 distribution)

The tap `ipbtools/homebrew-ipb` carries the same formula as `Formula/ipb.rb` here; it builds from source, so the machine needs Xcode 27 beta selected for the build and its CoreDevice package for runtime:

```sh
brew tap ipbtools/ipb
brew trust ipbtools/ipb      # current Homebrew refuses third-party taps until trusted
brew install --HEAD ipb      # builds from source; ~10 s once Xcode 27 beta's CoreDevice package is present
ipb version                  # ipb 0.1.0 (macOS ..., CoreDevice 642.15)
ipb doctor                   # layered self-check, names the next step on failure
ipb devices                  # then: ipb screenshot before.png; ipb tap 0.15 0.12; ipb home
```

`make install PREFIX=/some/dir` produces the same layout without Homebrew: `bin/ipb`, `libexec/ipb-helper`, `libexec/ipb-video`, `libexec/ipb-mirror`, `share/ipb/VERSION`, `share/ipb/smoke_matrix.sh`.

## Build

```sh
make
```

The helper binary is written to:

```sh
build/ipb-helper
```

## Usage

Touch coordinates are normalized from top-left to bottom-right, in the `0..1` range. Pointer deltas are signed relative integers.

```sh
bin/ipb devices                 # physical devices: uuid, name, os, transport, tunnel
bin/ipb device                  # the device the other commands would use
bin/ipb tap 0.5 0.5
bin/ipb launch com.apple.Preferences
bin/ipb open https://www.apple.com
bin/ipb clipboard set "你好 🚀" && bin/ipb clipboard get
bin/ipb apps | bin/ipb ps | bin/ipb lock-state | bin/ipb orientation
bin/ipb push local.txt /Documents/x.txt --app <bundle-id>
bin/ipb long 0.615 0.675 1.2
bin/ipb scroll 0.5 0.75 0 0.30
bin/ipb swipe 0.5 0.75 0.5 0.35
bin/ipb home
bin/ipb recents
bin/ipb lock                                 # lock the screen
bin/ipb screenshot build/current.png
bin/ipb stream --dir frames --count 20        # live screen frames (JPEG), no DeviceHub
bin/ipb mirror                               # interactive screen window (GUI session required)
bin/ipb service-ids
bin/ipb services
bin/ipb service-id touchscreen
bin/ipb reset-gesture
bin/ipb pointer 0 0
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-event 0 0 0
bin/ipb vendor-defined 0 0 0
bin/ipb key escape
bin/ipb button 0x0c 0x40
bin/ipb raw com.apple.coredevice.feature.remote.universalhidservice cd_uhid_tap 0x101 0.5 0.5
```

`DEVICE_ID` is optional. Without it the wrapper picks the single wired or tunnelled physical device; with several devices it lists them and exits. Use the CoreDevice UUID from `devicectl list devices --json-output` (the 642.x table view prints UDIDs, which the service rejects):

```sh
DEVICE_ID=<coredevice-uuid> bin/ipb tap 0.5 0.5
```

Useful runtime overrides:

```sh
DEVICE_ID=<coredevice-uuid>          # pick a device explicitly
UHID_SERVICE_ID=auto                 # or a fixed id such as 0x101
UHID_SERVICE_FALLBACK=0x101          # opt in to a fixed id when descriptor discovery fails; unset = error
DEVELOPER_DIR=/path/to/Xcode-beta.app/Contents/Developer   # only needed for `make`; runtime uses the CoreDevice package
DEVICECTL=/path/to/devicectl         # defaults to the copy inside CoreDevice.framework
IPB_HELPER=/path/to/ipb-helper
HIDCTL_WAIT_MS=700                   # settle time after each send
HIDCTL_TIMEOUT_S=30                  # watchdog for a single helper run
```

`UHID_SERVICE_ID` defaults to `auto`: the wrapper calls `connectedServiceDescriptors()` and selects the descriptor whose product is `CoreDevice touchscreen(nil)`. If discovery fails the command exits 3 unless `UHID_SERVICE_FALLBACK` is set.

Exit codes from the helper: 0 ok, 1 a dispatched operation or the remote connection reported failure, 2 usage or local error, 3 CoreDeviceService refused the service socket (the CoreDevice error is printed), 4 the device tunnel is not connected, 5 watchdog timeout. On 4 the wrapper warms the tunnel once with `devicectl device info details` and retries; nothing has been sent to the device at that point.

### Live screen stream: `ipb stream`

Streams the device screen without DeviceHub, without injecting any Apple process, and without any
Apple-private entitlement. Frames are native-resolution baseline JPEG; only frames whose content
actually changed are emitted, so a static screen yields ~1/s and a moving one ~40-57/s.

```sh
bin/ipb stream --dir DIR [--count N] [--fps F] [--seconds S]
bin/ipb stream --stdout        # repeated [uint32 BE length][jpeg bytes]

# live view (see the note on --framerate below)
bin/ipb stream --stdout --seconds 60 \
  | ffplay -fflags nobuffer -flags low_delay -f mjpeg -framerate 60 -i -
```

**Requires a GUI login session** (`CGGetActiveDisplayList` > 0), because in-process decoding creates
a `CVDisplayLink`. It works with SIP enabled; it does *not* work over plain ssh — from ssh, run it in
the console session with `open -a Terminal <script>`.

**The output carries no timestamps.** Frame rate varies with screen activity, so a consumer that
assumes a fixed rate will drift; ffmpeg's MJPEG demuxer defaults to 25 fps, which is below the
producer's peak, so always pass `-framerate 60` (at or above the peak) to keep the viewer from
falling behind.

`--seconds` is the total collection budget and bounds `--count` as well: if `--count N` is not
reached within it, the command exits 8 rather than reporting success with fewer frames.

Exit codes for `ipb stream`: 0 ok, 2 usage/setup, 3 service refused, 4 tunnel down, 5 negotiation
rejected, 6 stream did not start or the media server died, 7 no frames within the watchdog window,
8 output failed / the consumer did not drain stdout / `--count` not reached, 9 a watchdog expired
(the stage — setup, collection, or shutdown — is printed before exit). When the consumer is slower
than the device, frames are **dropped, not queued**; the count is reported on exit.

### Interactive mirror: `ipb mirror`

One window displays the device screen and accepts mouse control, without DeviceHub, injection
into any Apple process, or any special entitlement.

```sh
bin/ipb mirror [--seconds S] [--csv PATH]
bin/ipb mirror --help
```

Click, hold, and drag directly on the screen. The shortcuts match DeviceHub:

| Shortcut | Action |
| --- | --- |
| ⇧⌘H | Home |
| ⌃⇧⌘H | App Switcher |
| ⌘↑ / ⌘↓ | Volume up / down |
| ⇧⌘S | Save the latest decoded frame as a PNG in `~/Pictures` |
| ⌘0 | Zoom to fit |
| ⌘1 | Actual size (falls back to fit if it exceeds the available screen) |

**Requires a GUI login session**, just like `ipb stream`: in-process decoding needs
`CVDisplayLink`. It works with SIP enabled and needs no entitlement; plain ssh is unsupported.

The default run lasts 300 seconds; `--seconds` accepts values greater than 0 and at most 3600.
The existing 8192-input-event cap also ends the run. Statistics retain their existing fields and
go to **stderr**. No CSV is produced by default; `--csv PATH` writes the event header and rows to
that file (overwriting it; its parent directory must exist). CSV open/write failures exit 8.
`IPB_MIRROR_HELPER` overrides the helper; otherwise `libexec/ipb-mirror` is preferred over
`build/ipb-mirror`. The source is `Sources/mirror.m`. The helper's existing `--service-id ID`
option is also passed through for a known touchscreen ID; descriptor discovery remains the default.

Known coordinate bias on the iPhone 13 Pro: decoded frames are **1184×2576**, versus the
**1170×2532** physical screen. Encoder padding for 16-pixel alignment and a format description
without clean aperture leave approximately **1.2% horizontal / 1.7% vertical** coordinate error.
No compensation is applied because the padding's side is unknown. See the M2/M3 and M4 records
in [docs/verification.md](docs/verification.md) for the existing device evidence.

Not implemented: Lock (⌘L), Siri (⇧⌥⌘H), screen recording (⇧⌘R), Action Button, and Camera Control.
Lock, Siri, and the hardware buttons lack usage-code evidence; recording lacks capture/recording
behavior evidence. The local 13 Pro also lacks Action Button and Camera Control hardware.

Exit codes: 0 success, **1 input/connection failure**, 2 usage/local setup, 3 service socket or
descriptor discovery failure, 4 tunnel/interface/bind failure, 5 negotiation failure,
6 media/decoder/display failure, 7 no media frames for 12 seconds, **8 local I/O failure**
(including CSV output, descriptor capture, or screenshot shutdown drain), 9 setup/run/shutdown
watchdog or input-drain timeout, 130 SIGINT, 143 SIGTERM. Unlike `stream`, mirror has input
failure code 1 and no `--count` contract. Sent input is never automatically replayed.

Supported `service-id` roles:

```sh
bin/ipb service-id touchscreen
bin/ipb service-id gesture
bin/ipb service-id keyboard
bin/ipb service-id buttons
bin/ipb service-id avp
```

## First run: `ipb doctor`

`ipb doctor` checks each layer in order and names the next step for anything that fails: local install (helper, python3), Apple host stack (devicectl, CoreDevice ≥ 636, Mercury, embedded UniversalHID), device (enumeration, selection, iOS version, transport), developer disk image (mounted, usable, compatible), lock state, and finally the HID descriptor set on the device (which also warms the tunnel). It exits non-zero on any FAIL; WARN lines (locked phone, network transport, unverified iOS) do not fail it.

## Smoke gate

```sh
scripts/smoke_matrix.sh . build/smoke            # host-only, discovery, and non-destructive reports
SMOKE_INTERACTIVE=1 TAP_XY="0.15 0.12" scripts/smoke_matrix.sh . build/smoke   # adds home, tap, recents, swipe, scroll, long, key
```

Every step must exit 0 and, where stated, print the expected output; the script exits non-zero otherwise. Screenshots before and after each interactive step land in the output directory; identical consecutive frames are reported as warnings because a system alert can legitimately freeze the screen.

## Feature matrix: ipb vs adb vs idb vs devicectl

Physical devices only. "own" means ipb implements the feature itself over the CoreDevice HID socket; "devicectl" means ipb is a thin adb-style verb over `xcrun devicectl`. idb columns reflect its documented real-device behaviour (its `ui` commands are simulator-only).

| Capability | adb | ipb | idb (real device) | devicectl |
| --- | --- | --- | --- | --- |
| List devices | `adb devices` | `ipb devices` (devicectl) | `idb list-targets` | `list devices` |
| Tap / swipe / long press | `input tap/swipe` | `ipb tap/swipe/long` (own) | no | no |
| Scroll | `input swipe` | `ipb scroll` (own) | no | no |
| Key / text | `input keyevent/text` | `ipb key` (HID usages, own); Unicode via `ipb clipboard set` + paste | no | no |
| Home / App Switcher | `keyevent HOME/APP_SWITCH` | `ipb home` / `ipb recents` (own) | no | no |
| Lock screen | `input keyevent POWER` | `ipb lock` (own) | no | no |
| Screenshot | `screencap` | `ipb screenshot` (devicectl) | yes | `capture screenshot` |
| Screen recording | `screenrecord` | `ipb screenrecord` (devicectl; the tested iOS 27.0 device reports "Screen Recording" unsupported, error 1001) | yes | `capture screen-record` |
| UI hierarchy | `uiautomator dump` | no (captions only via accessibility, no frames) | `ui describe-all` (simulator) | no |
| Install / uninstall | `install` / `uninstall` | `ipb install` / `ipb uninstall` (devicectl) | yes | `install app` / `uninstall app` |
| Launch / kill / ps | `am start` / `am force-stop` / `ps` | `ipb launch` / `ipb kill <pid>` / `ipb ps` (devicectl) | launch / terminate | `process launch/signal`, `info processes` |
| Open URL / deep link | `am start -a VIEW -d` | `ipb open <url>` (devicectl) | `open` | `process openURL` |
| Installed apps | `pm list packages` | `ipb apps` (devicectl) | `list-apps` | `info apps` |
| Files | `push` / `pull` / `shell ls` | `ipb push/pull/ls ... --app <bundle>` (data container of developer-signed apps; system app containers are refused, devicectl) | `file push/pull` (app container) | `copy to/from`, `info files` |
| Clipboard | `shell cmd clipboard` (limited) | `ipb clipboard get/set` (devicectl, Unicode ok) | no | `pasteboard` |
| Location | emulator only | `ipb location <lat> <lon>` / `clear` (devicectl) | `set-location` (simulator) | `simulate location` |
| Orientation | `settings put` | `ipb orientation [value]` (devicectl) | no | `orientation` |
| Device info / lock state | `getprop` | `ipb info` / `ipb lock-state` (devicectl) | `describe` | `info details/lockState` |
| Logs | `logcat` | no (planned: syslog via RemoteXPC) | `log` | no |
| Shell | `adb shell` | no (iOS has no shell) | no | no |
| Port forward | `forward` / `reverse` | no | no | no |
| Reboot / sysdiagnose / pair | `reboot` | `ipb reboot` / `ipb sysdiagnose` / `ipb pair` (devicectl) | no | `reboot`, `sysdiagnose`, `manage pair` |
| Needs on-device server / XCTest | no (adbd is OS-provided) | no (Apple DDI daemon only) | yes for UI (XCTest) | n/a |
| Raw escape hatch | `adb shell <cmd>` | `ipb devicectl <args>` | | |

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

## License and notice

MIT (see `LICENSE`). ipb talks to undocumented Apple interfaces (CoreDevice, RemoteXPC, the developer disk image's HID daemon) and redistributes no Apple components; the CoreDevice package and the disk image come from Xcode on the user's machine. Apple may change these interfaces between releases. A future Python client built on pymobiledevice3 (GPL-3.0) will live in a separate repository so this one stays MIT.

See [docs/protocol.md](docs/protocol.md) for the current protocol map, symbol evidence, and known gaps.

See `AGENTS.md` for the four-stage roadmap (macOS 27 → macOS 26 → Xcode-free hosts) and [docs/standalone-distribution.md](docs/standalone-distribution.md) for the adb-style distribution plan and [docs/research/](docs/research/) for the 2026-09-07 landscape research (adb capability boundary, agent frameworks, peer iOS tools) and the direction review.
