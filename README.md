# ipb

`ipb` (iOS Physical-device Bridge, "the adb for iPhone"; formerly devicehubctl and briefly hdb) is a small CLI for driving basic iOS 27 device interactions through CoreDevice private services, without XCUITest or WebDriverAgent.

It was extracted from a macOS 27 / Xcode 27 beta Device Hub investigation. It drives the device
itself over the CoreDevice HID path — tap, long press, swipe, drag-scroll, trackpad scroll,
keyboard keys, Home, App Switcher, side button (lock/wake), pointer and raw HID reports, plus a
live JPEG screen stream (`ipb stream`) and an interactive mirror window (`ipb mirror`) — and wraps
`xcrun devicectl` for everything Apple already exposes: install, launch, files, clipboard,
location, screenshots.

In this source revision, `ipb ui --deep` reads an application's native deep accessibility tree,
numerical element frames over the DevicesApp raw DTX service. `ui hit-test` reads
the actual element at a point; `ui press` resolves and presses a fresh element
once. v0.5.0 adds exact locators/waits, selector-qualified press, text replacement that
checks the actual first responder, one-shot scroll-to-visible and explicitly selected
system-alert buttons. Since v0.4.0, `--deep` is a native-only observation
(JSON schema 2); `--deep --full-state` adds separately
reported state/role reads under `supplementalAX`. A failed supplementary read returns
nonzero while preserving a validated native tree after successful cleanup. Default
`ipb ui` retains the ordinary AXChildren graph and JSON schema 1. It uses an optional host Python
backend; it installs nothing on the phone and starts no XCTest session. This is an AX graph, not a dump of every UIKit view.

The CLI uses DeviceHub's captured async descriptor-discovery path to resolve the touchscreen
service when `UHID_SERVICE_ID=auto`. The maintainer authorized v0.5.0 publication after
Opus 5.5 review and host/package/Homebrew checks, without further physical-device testing.
Existing scoped12mini controls remain separate evidence. The full supported physical-device
gate remains open; this release does not claim full device acceptance. See
[current verification scope](docs/verification.md#open-items--current-state-living-section).
For `ui press`, exit **6** means failure after submission: the diagnostic preserves accepted,
refused or unknown status. Never retry it automatically; read the page again first.

[Install and update](#installation-channels) · [Commands](#usage) · [UI tree](docs/ui.md) ·
[Mirror](docs/mirror.md) · [Documentation map](docs/README.md)

## Requirements

- A host whose installed CoreDevice package is 636.x or newer. This ships with Xcode 27 beta (`XcodeSystemResources.pkg`); it is what puts `UniversalHIDService`, the `HIDServiceID` helpers, and the embedded `UniversalHID.framework` into `/Library/Developer/PrivateFrameworks`.
- macOS 27 + Xcode 27 beta on the host (the supported target matrix). macOS 26.5.1 has separate development verification records; those do not expand the supported release matrix. The link step needs the beta SDK's private-framework stubs, and the beta's iOS DDI is what installs the device-side HID daemon (`dtuhidd`).
- A connected iOS 27+ device visible to `xcrun devicectl`, with the Xcode 27 beta DDI mounted. iOS 26 is no longer a supported target (dropped 2026-09-20, no device available to verify against). On iOS 26 the `touchscreenGesture` service (`0x501`) was absent, so `pointer`, `abs-pointer`, `scroll-report`, `scroll-gesture` and the mirror's scroll wheel never worked there. See `docs/verification.md`.
- GitHub-hosted code should be treated as beta/private-ABI research, because Apple may change these interfaces between seeds.

Xcode 26.x hosts cannot run this tool as-is: CoreDevice 518.x lacks the UniversalHID service protocol, and the Xcode 26 DDI ships no HID daemon, so every `feature.remote.hid.*` / `universalhidservice` socket request is refused with "Create Service Socket is not supported by this device".

The Xcode used for building and for `screenshot` is taken from `xcode-select -p`, which honours `DEVELOPER_DIR`:

```sh
export DEVELOPER_DIR=/path/to/Xcode-beta.app/Contents/Developer
```

Override it at build time with `XCODE_PATH=/path/to/Xcode-beta.app` if you prefer.

## Installation channels

The v0.5.0 source revision adds the runner-free element
operations in [PR #9](https://github.com/ipbtools/ipb/pull/9). It retains v0.4.0's
native-only deep trees/rectangles and separate supplemental state (deep JSON schema 2),
ordinary schema1 and identifier-only press output. Stable installs use the precompiled
macOS 27 ARM64 package; source/HEAD installs build locally. The supported physical-device
gate remains open; the maintainer authorized this release after Opus5.5 review and
host/package/Homebrew verification, without additional device testing. It does not claim full acceptance. See
[release verification](docs/releasing.md#current-channels).
Published archives are listed on the [latest stable Release](https://github.com/ipbtools/ipb/releases/latest);
version preparation and CI packages do not publish or update the stable tap automatically.

| Channel | What it installs | Update path |
| --- | --- | --- |
| Stable Homebrew | Pinned archive from the latest published stable release | `ipb update` or `brew upgrade ipbtools/ipb/ipb` |
| Homebrew HEAD | Source from `main`, including the merged UI and mirror additions | `brew install --HEAD ipbtools/ipb/ipb`; `ipb update` keeps it current |
| Release archive | Selected version with checksum/build metadata | Download a newer Release; keep bin/libexec/share together |
| PR CI test package | Temporary precompiled development package | Download a newer Actions artifact |
| Development source | The selected source checkout | Run `bin/ipb update` in that checkout |
| `make install PREFIX=...` | A local copy of the selected checkout | Pull/build, then repeat install with the same prefix |

### Homebrew stable release

Install the pinned stable package:

```sh
brew update
brew install ipbtools/ipb/ipb
```

To move an existing Homebrew `--HEAD` install to stable, first remove the HEAD install and
then install the stable formula. `brew reinstall` preserves the original install options.

```sh
brew update
brew uninstall ipbtools/ipb/ipb
brew install ipbtools/ipb/ipb
```

### Homebrew HEAD

The HEAD formula builds `main` from source. Select Xcode 27 beta for the build and install its
CoreDevice package for runtime. A fully qualified formula name trusts only that formula:

```sh
brew install --HEAD ipbtools/ipb/ipb
ipb version                  # source VERSION plus macOS/CoreDevice versions
ipb doctor                   # layered self-check, names the next step on failure
ipb devices                  # then: ipb screenshot before.png; ipb tap 0.15 0.12; ipb home
```

### Development source and local installation

To build the current `main` source with Xcode 27 beta selected:

```sh
git clone https://github.com/ipbtools/ipb.git
cd ipb
make install PREFIX="$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
ipb help
```

For an existing checkout, pull its selected branch and repeat `make install` with the same
prefix. `command -v ipb` shows which copy your shell runs; a Homebrew copy and a manual copy
can coexist and contain different code.

### Shell completion

A zsh completion ships with the tool and is installed to `share/zsh/site-functions/_ipb`, which
Homebrew links automatically — open a new shell and `ipb <Tab>` lists the commands with
descriptions. `-s <Tab>` completes against the attached devices, offering both the UUIDs and the
device names, each annotated with model, iOS version, transport and tunnel state:

```
$ ipb -s <Tab>
device uuid
<uuid-a>  -- <name-a> (iPhone 12 mini, iOS 27.0, wired, tunnel connected)
<uuid-b>  -- <name-b> (iPhone 13 Pro, iOS 27.0, localNetwork, tunnel disconnected)
device name
<name-a>  -- iPhone 12 mini, iOS 27.0
<name-b>  -- iPhone 13 Pro, iOS 27.0
```

From a source checkout, add it to `fpath` yourself:

```sh
fpath=(/path/to/ipb/completions $fpath)
autoload -Uz compinit && compinit
```

Only zsh is provided; bash has no completion.

### Updating the running copy

`ipb update` is host-only: it does not enumerate/select phones and needs no `-s`, regardless of
how many devices are attached. It updates the running Homebrew install or source checkout. A
manual-prefix install returns exit 2 with its exact reinstall prefix; it does not update another
Homebrew copy. Source updates follow the checkout's configured branch. A Homebrew stable install
uses `brew upgrade`; a `--HEAD` install is reinstalled from the refreshed `main` source while
retaining its HEAD option. The command only updates the copy that is running. An older HEAD wrapper predating this
fix needs a one-time `brew update` and `brew reinstall --HEAD ipbtools/ipb/ipb`, or the
stable channel switch above.

`make install PREFIX=/some/dir` produces the same layout without Homebrew: `bin/ipb`,
the helpers in `libexec/` (including the optional AX backend), `share/ipb/VERSION`,
`share/ipb/requirements-ax.txt`, `share/ipb/smoke_matrix.sh`, and `share/zsh/site-functions/_ipb`.

### Application elements (`ipb ui`)

```sh
ipb -s <device> ui
ipb -s <device> ui --json
```

Returns the application's actual AX child graph, text, logical-point rectangles and state.
JSON includes `children`, `parentId` and `depth`; the text output is indented by depth.
It needs an optional Python 3.11+ / pymobiledevice3 11.10.2 environment on the Mac,
an existing USB pairing and Developer Mode. It starts no XCTest session or phone app.

AX can merge text and omit backing containers: the tested Settings page gives AX 13 nodes
versus XCTest 176. `ipb` preserves the graph returned by the service. Description-first text
reads avoid the reproduced Bilibili rich-Label encoding failure. Other read failures remain
explicit; timeout recovery on a fresh connection is not implemented.

See [the UI guide](docs/ui.md) for setup, JSON fields, text policy, bounds and the AX/XCTest
comparison. Availability depends on the [installation channel](#installation-channels).

## Build

```sh
make
```

The helper binary is written to:

```sh
build/ipb-helper
```

## Usage

`ipb help` prints the commands grouped by what they do; `ipb help hid` prints the low-level HID
report commands used for protocol work. Touch coordinates are normalized from top-left to
bottom-right, in the `0..1` range. Pointer deltas are signed relative integers.

```sh
bin/ipb help                    # grouped command list
bin/ipb devices                 # physical devices: uuid, name, os, transport, tunnel
bin/ipb device                  # the device the other commands would use
bin/ipb tap 0.5 0.5
bin/ipb launch com.apple.Preferences
bin/ipb open https://www.apple.com
bin/ipb clipboard set "你好 🚀" && bin/ipb clipboard get
bin/ipb text "你好 🚀"             # focus a text field first; replaces the device clipboard
bin/ipb ui --deep --json                     # native application hierarchy
bin/ipb ui --deep --full-state --json        # separate supplementalAX state/role (slower)
bin/ipb ui hit-test --point 0.15 0.55 --json
bin/ipb ui press --identifier Seven --json   # Calculator; re-read to verify effect
bin/ipb ui locate --label '7' --json         # exact native label
bin/ipb ui wait --identifier Seven --timeout 5 --json # bounded read-only wait
bin/ipb ui input --class UISearchBarTextField --text Battery --replace-all --json # requires actual keyboard focus
bin/ipb ui scroll-to-visible --identifier com.apple.settings.general --json # one native scroll, then observe
bin/ipb displays --json
bin/ipb capabilities --json
bin/ipb apps | bin/ipb ps | bin/ipb lock-state | bin/ipb orientation
bin/ipb push local.txt /Documents/x.txt --app <bundle-id>
bin/ipb long 0.615 0.675 1.2
bin/ipb scroll 0.5 0.75 0 0.30
bin/ipb swipe 0.5 0.75 0.5 0.35
bin/ipb home
bin/ipb recents
bin/ipb power                                # side button: locks an on screen, wakes an off one
bin/ipb screenshot build/current.png
bin/ipb stream --dir frames --count 20        # live screen frames (JPEG), no DeviceHub
bin/ipb mirror                               # interactive screen window (GUI session required)
bin/ipb service-ids
bin/ipb services
bin/ipb service-id touchscreen
bin/ipb reset-gesture
bin/ipb pointer 0 0
bin/ipb scroll-report 0x501 0 0
bin/ipb scroll-gesture 0.5 0.5 0 -25       # trackpad-style scroll (pointer + phase sequence)
bin/ipb abs-pointer 0.5 0.5                # place the cursor
bin/ipb scroll-event 0 0 0                 # raw probe: accepted, no device effect demonstrated
bin/ipb vendor-defined 0 0 0               # raw probe: accepted, no device effect demonstrated
bin/ipb key escape
bin/ipb button 0x0c 0x40
bin/ipb raw com.apple.coredevice.feature.remote.universalhidservice cd_uhid_tap 0x101 0.5 0.5
```

v0.5.0 includes locator, input, scroll-to-visible and explicit system-alert operations.
See [the element guide](docs/ui.md) for exact selectors, paste prompts,
`alert-press`, nonzero outcomes and the tested device/host boundary.

### Choosing a device

With one device connected there is nothing to choose: `ipb` picks the single wired or tunnelled
physical device. With several, name one with `-s` / `--device` (adb's `-s`, idb's `--udid`) or by
exporting `DEVICE_ID`; the flag wins.

```sh
bin/ipb -s <coredevice-uuid> tap 0.5 0.5     # the full CoreDevice UUID
bin/ipb -s 1D533177 device                   # a unique prefix of one
bin/ipb -s "12 mini" screenshot before.png   # part of the device name or model
export DEVICE_ID=<coredevice-uuid>           # the default for this shell
```

A selector is matched most-specific-first — whole UUID, then UUID prefix, then a case-insensitive
substring of the device name or marketing model. `xcrun devicectl --device` accepts none of these
shorthands, so `ipb` resolves them itself against `devicectl list devices --json-output`; a full
UUID is passed straight through and costs no enumeration. For device commands, a selector that matches nothing or more
than one device exits 3 and lists what is attached. Host-only `help`, `version`, `update`
and `service-ids` bypass device selection. `ipb devices` prints the same list, and
`ipb device` prints the UUID the other commands would use.

Device identity is the CoreDevice UUID, not the UDID: the 642.x `devicectl list devices` table view
prints UDIDs, which the HID services reject.

Useful runtime overrides:

```sh
DEVICE_ID=<coredevice-uuid>          # pick a device explicitly (-s overrides it)
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

### Literal text and device metadata

`ipb text <text>` copies the exact UTF-8 argument to the device clipboard, then sends the captured
Command+V held-key sequence. It is separate from `key`, whose output depends on the phone's input
method. Focus an editable field first. The command replaces the device clipboard; it does not
restore it or enable continuous clipboard sharing. Discovery fails before a clipboard change;
copy failure prevents paste. A failed paste is not replayed. Exit 0 means copy and paste submission
succeeded, **not** that the focused application accepted the text. Verify the resulting field.
Chinese, emoji, spaces and punctuation were verified in iOS 27 Settings search with Pinyin active.
iOS may ask the focused app to allow pasting from `dtpasteboardd`; `text` does not answer that prompt.
Secure fields and applications that reject paste are not covered by that result.

`ipb displays --json` and `ipb capabilities --json` return a `schemaVersion: 1` envelope with the
resolved `deviceIdentifier`. Displays preserves Apple's `displays`, `orientation`, `backlightState`;
capabilities preserves the advertised entries, sorted by `featureIdentifier`. Select the explicit
primary display; the first entry need not be the phone screen. Query failure is an error, not an
empty capability list. An advertised feature is not a guarantee that its next operation will work.

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
rejected, 6 stream/connection failure, 7 no initial output within the first-frame budget,
8 output failed / the consumer did not drain stdout / `--count` not reached, 9 a watchdog expired
(the stage — setup, collection, or shutdown — is printed before exit). When the consumer is slower
than the device, frames are **dropped, not queued**; the count is reported on exit.

### Interactive mirror: `ipb mirror`

```sh
ipb -s <device> mirror
ipb mirror --help
```

A GUI window displays the phone and accepts mouse, keyboard and text clipboard input.
Click the phone view to focus it. Mac input-method composition stays on the Mac and sends
committed Unicode text by clipboard paste; iOS may show its normal paste permission prompt.
Paste/IME commits replace the iPhone text clipboard; continuous clipboard sync is not provided.

Common shortcuts: **⇧⌘H** Home, **⌃⇧⌘H** App Switcher, **⌘L** lock/wake,
**⌘C / ⌘X / ⌘V** text Copy/Cut/Paste, **⌘K** numeric keypad and **⌘W** close.
A desktop GUI login session is required. Secure-field/lockscreen keyboard acceptance and
physical trackpad parity remain unverified.

See [the mirror guide](docs/mirror.md) for all shortcuts, input behavior, geometry,
keepalive, limits and exit codes. These keyboard/clipboard additions follow the
[development installation channel](#installation-channels).

## First run: `ipb doctor`

`ipb doctor` checks each layer in order and names the next step for anything that fails: local install (helper, python3), Apple host stack (devicectl, CoreDevice ≥ 636, Mercury, embedded UniversalHID), device (enumeration, selection, iOS version, transport), developer disk image (mounted, usable, compatible), lock state, and finally the HID descriptor set on the device (which also warms the tunnel). It exits non-zero on any FAIL; WARN lines (locked phone, network transport, unverified iOS) do not fail it.

## Smoke gate

```sh
scripts/smoke_matrix.sh . build/smoke            # host-only, discovery, and non-destructive reports
SMOKE_INTERACTIVE=1 TAP_XY="0.15 0.12" scripts/smoke_matrix.sh . build/smoke   # adds home, tap, recents, swipe, scroll, long, key, text
```

Every step must exit 0 and, where stated, print the expected output; the script exits non-zero otherwise. Interactive steps require an explicitly unlocked phone and save screenshots in the output directory. Unexplained unchanged frames fail; declared no-ops carry their reason. Inspect the images for the intended effect, since a pixel change alone is not semantic proof.

The text fixture uses the iOS 27 Settings search field in portrait. Adjust its coordinates for the target layout. It replaces the device clipboard with synthetic Unicode text and waits up to 30 seconds for field OCR; handle any iOS paste prompt normally during that interval. The gate never answers the prompt itself and stops before clearing the field if text is absent. Inspect the saved image for exact emoji and punctuation, which OCR does not certify.

## Feature matrix: ipb vs adb vs idb vs devicectl

Physical devices only. "own" means ipb implements the feature itself over the CoreDevice HID socket; "devicectl" means ipb is a thin adb-style verb over `xcrun devicectl`. idb columns reflect its documented real-device behaviour (its `ui` commands are simulator-only).

| Capability | adb | ipb | idb (real device) | devicectl |
| --- | --- | --- | --- | --- |
| List devices | `adb devices` | `ipb devices` (devicectl) | `idb list-targets` | `list devices` |
| Select a device | `-s <serial>`, `$ANDROID_SERIAL` | `-s <uuid\|prefix\|name>`, `DEVICE_ID` | `--udid <udid>` | `--device <uuid>` |
| Tap / swipe / long press | `input tap/swipe` | `ipb tap/swipe/long` (own) | no | no |
| Scroll | `input swipe` | `ipb scroll` (drag) and `ipb scroll-gesture` (trackpad phases, iOS 27; own) | no | no |
| Key / text | `input keyevent/text` | `ipb key` (HID usages); `ipb text` (clipboard + paste, Settings Unicode verified; replaces clipboard) | no | no |
| Home / App Switcher | `keyevent HOME/APP_SWITCH` | `ipb home` / `ipb recents` (own) | no | no |
| Lock / wake screen | `input keyevent POWER` | `ipb power` (aliases `lock`, `wake`; own, 0.4 s hold) | no | no |
| Screenshot | `screencap` | `ipb screenshot` (devicectl) | yes | `capture screenshot` |
| Screen recording | `screenrecord` | `ipb screenrecord` (devicectl; the tested iOS 27.0 device reports "Screen Recording" unsupported, error 1001) | yes | `capture screen-record` |
| Live screen stream | scrcpy (an on-device server) | `ipb stream` (own, JPEG frames) | no | no |
| Interactive mirror | scrcpy | `ipb mirror` (own) | no | Device Hub, GUI only |
| UI hierarchy | `uiautomator dump` | `ipb ui`: actual AX tree, text, frames and state; optional `--deep` in this source revision; coverage differs from XCTest ([guide](docs/ui.md)) | `ui describe-all` (simulator) | no |
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
- `pointer` *(probe)*: UniversalHID pointer report to the `gesture`/trackpad service
- `scroll-report` *(probe)*: UniversalHID scroll report to the `gesture`/trackpad service
- `scroll-event` *(probe)*: CoreDevice HIDScroll event to the standalone scroll feature
- `vendor-defined` *(probe)*: CoreDevice HIDVendorDefined event to the standalone vendor-defined feature

  *(probe)* means the service accepts the report and returns 0, but no effect on the device has ever
  been demonstrated. The same applies to `nav-report`, `dock-report` and `uhid-swipe-report`.
- `key`: UniversalHID keyboard report to the `keyboard` service
- `long`: CoreDevice HID digitizer with repeated hold pulses
- `home`: CoreDevice HID button service
- `recents`: CoreDevice HID button, AppleVendorKeyboard page `0xff01` usage `0x10` (was a 1.66 s digitizer swipe until 2026-09-14)
- `scroll-gesture` and `abs-pointer`: UniversalHID AbsolutePointer and Scroll wire reports to the `gesture`/trackpad service, in DeviceHub's captured phase sequence
- `power` / `lock` / `wake`: CoreDevice HID button service, consumer usage `0x0c`/`0x30` held 0.4 s (the side button's own duration gate is 0.29 s; 0.7 s opens Siri)
- `screenshot`: `devicectl device capture screenshot`, using the copy shipped in the CoreDevice package
- `stream` and `mirror`: the device's own AVConference media path over the CoreDevice tunnel, decoded in process; `mirror` sends input over the same UniversalHID services as the commands above
- `ui`: an existing-paired USB userspace RSD plus DevicesApp raw DTX; optional host Python dependency

`CoreDevice.framework` exposes `HIDKeyboard` and `HIDPointer` protocols, but on the verified Xcode 27 beta 2 build their implementations are `UniversalHIDKeyboard` / `UniversalHIDPointer` adapters backed by the UniversalHID service, not separate `feature.remote.hid.keyboard` or `feature.remote.hid.pointer` sockets.

## Verified Scope

Feature verification is recorded in [docs/verification.md](docs/verification.md),
which names the host, the device, the CoreDevice and DDI builds, and the artefacts. The oldest
records are against an iPhone 13 Pro on iOS 27.0 with Xcode 27 beta 2 (CoreDevice 636.3); the
living open-items section at the top of that file names the current validation boundaries.

The smoke gate is what keeps this honest: `scripts/smoke_matrix.sh` exercises service discovery,
device selection, one report per HID feature, and — with `SMOKE_INTERACTIVE=1` — home, tap,
recents, swipe, scroll, long press and a key, with a screenshot before and after each step.
Run it in a GUI login session, including the noninteractive subset. Startup failures are failures,
not a headless success. Pixel checks detect stale/no-op results; inspect the screenshots for the
expected UI state before accepting a run. See [docs/devicehub-alignment.md](docs/devicehub-alignment.md)
for the current comparison and verification boundary.

## Known limitations

These are boundaries a user hits in normal use, not theoretical ones. Each links to a dated record;
the living open-items list is at the head of [docs/verification.md](docs/verification.md).

- **Use an unlocked device.** The recorded locked-device failure is `RemotePairingError` 1016
  (`unlockRequired`). Shipped symbols point to an escrowed remote-unlock keypair and private
  entitlements in Apple's path. A controlled locked-device A/B is still needed before treating
  that mechanism as the proven cause or a permanent impossibility for every third-party tool.
- **Permission-prompt handling remains unverified.** On 2026-09-21, both ipb and Device Hub
  dismissed the same SpringBoard “Remove App” confirmation with Cancel. The older blanket claim
  that all system dialogs ignore ipb is withdrawn; the original permission prompt was not recreated.
- **The long-running paths hold the CoreDevice tunnel by proxy.** `ipb mirror` and `ipb stream`
  keep a resident `devicectl` subscription alive because the tunnel has an idle lease and taking a
  usage assertion directly needs an entitlement. If the mirror is killed abnormally the
  subscription is swept on exit, but a hard `SIGKILL` can leave it running for the grace period.
- **`ipb screenrecord` is unsupported on the tested iOS 27.0 device** (devicectl reports error
  1001).
- **The raw probe verbs are probes.** `nav-report`, `dock-report`, `pointer` / `pointer-report`,
  `scroll-report`, `scroll-event`, `vendor-defined` and `uhid-swipe-report` are accepted by the
  service and return 0, but no device effect has ever been demonstrated for any of them.
- **Everything here rides private Apple ABI** and can break on any Xcode beta seed.

## License and notice

MIT (see `LICENSE`). ipb talks to undocumented Apple interfaces (CoreDevice, RemoteXPC, the developer disk image's HID daemon) and redistributes no Apple components; the CoreDevice package and the disk image come from Xcode on the user's machine. Apple may change these interfaces between releases. The optional AX backend requires separately installed
[pymobiledevice3 (GPL-3.0)](https://github.com/doronz88/pymobiledevice3/blob/master/LICENSE).
The current installer does not bundle that dependency. The Xcode-free client remains a
distribution plan, distinct from the optional AX backend.

See [docs/protocol.md](docs/protocol.md) for the current protocol map, symbol evidence, and known gaps.

See [the documentation map](docs/README.md) for current guides and research. `AGENTS.md`
records the roadmap; older platform rows are historical, while the current supported target
is macOS 27 + Xcode 27 + iOS 27+. [Standalone distribution](docs/standalone-distribution.md)
describes the Xcode-free direction; [research](docs/research/) contains capability and peer-tool
comparisons plus independent direction reviews.
