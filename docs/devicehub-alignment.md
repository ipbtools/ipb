# Device Hub alignment and reliability

## Scope and decisions

User request (2026-09-21): “开始修复剩余的问题，并且你实机操控下 devicehub，分析下我们还有什么功能和协议没有对齐”.
Start revision `f2e85a6`; branch `codex/devicehub-alignment`.
Follow-up research request: “再深入研究下 devicehub，看看我们还有什么可以从中学习补齐的”.
The deeper comparison below records observations and proposed work; it adds no product implementation.

Keep the native protocol oracle and the accepted resident devicectl tunnel keepalive. No uncertain
input replay, no XCTest and no third-party phone server. UI-tree discovery, Unicode text input,
frame metadata and a Python CLI/MCP session layer are subsequent work, not implemented by this patch.

## Implemented corrections

| Problem and reachable trigger | Change | Evidence boundary |
| --- | --- | --- |
| Static Settings screen ends stream/mirror early with exit 7 | Keep the initial-frame deadline; after a valid image tolerate idle silence until the finite requested duration. Handle explicit media stop/RemoteXPC error as failure. Preserve bounded writer drain and stage watchdogs. | Isolated prechange stream and mirror failed; revised sessions survived 22 seconds of inactivity and resumed after Home. Silent loss without an error callback is still ambiguous. |
| A slow synchronous HID call outlives its caller deadline; a later call overlaps it | One owner per connection through actual completion. Admission and completion share one deadline; shutdown drains queued UP before closing admission, then drains active owners before cancel/FD close. | Controlled host fixture reproduced max concurrency 2 before, 1 after. No forced device disconnect was used. Report timeouts intentionally remain fatal; release cannot be guaranteed after a transport failure. |
| Smoke can accept stale frames or clock-only changes | Explicit unlock proof, material decoded-pixel checks, stated no-op allowances, controlled Settings list/search fixtures. Track this mirror's PID; unknown startup errors fail. Install assertion helpers with the gate. | First live run's rc=0 was rejected by screenshot review. Clock-only changes were 0.0343% / 0.0487%; gate now requires >=1% pixels with an RGB-channel difference >=16. This remains a freshness check, not a semantic oracle. |
| Tracer can signal readiness without all taps, emit zsh arithmetic errors, or double-detach | Require resolved breakpoints and successful Continue; single detach and truthful status. Capture service ID bytes and decode digitizer fields. | Live revised capture: ten taps ready, 21 calls, no shed taps, clean rc=0 detach, target alive. Missing-symbol host fixture: exit 4, no readiness file, target safely detached. |
| Current docs conflict with implementation/records | Refresh protocol gaps, 39 B keyboard/count fix status, current matrix, resident keepalive, media contract and system-dialog evidence. Label pointer probes and mirror shortcut-only keyboard support in help/completion. | Old dated verification records remain intact. No raw logs/screenshots are committed. |

## Device Hub comparison

Measured seed: local macOS **26.5.1 (25F80)**, Xcode **27 Beta 6**, Device Hub **27.0 (255.2.3.5)**,
CoreDevice **642.15**, wired **iPhone 13 Pro / iOS 27.0 (24A437)**, explicitly unlocked.
The initial capture had a zero-input baseline, 14 digitizer reports and four button calls.
Protocol bytes and source classification are in `docs/protocol.md`.

| Function | Actual Device Hub observation | ipb status / remaining gap |
| --- | --- | --- |
| Tap and drag | Settings opened and scrolled; 58 B Digitizer on `0x101` | Same target/size/count. Device Hub max=5, contact identifier/identity=2, nonzero timestamp; ipb max=1, identifier=0, identity/timestamp unset. No proven causal defect from these differences. |
| System confirmation | “Remove App” -> Cancel dismissed the alert | Current ipb also dismissed the same alert. Original TCC/privacy prompt remains untested; blanket failure claim withdrawn. |
| Keyboard capture | `ipb` visibly entered Settings search; six 39 B reports on `0x200`. Later Shift/Command chords were captured and Command+A/Backspace cleared the field. | CLI single keys work; mirror lacks ordinary capture and a held-usage set. Arbitrary focused text insertion is a separate contract; UTF-8 clipboard copy/get already exists. |
| Pointer / wheel | AbsolutePointer 19 B and Scroll 21 B target `0x501` | Target confirmed. Synthetic wheel only emitted zero-motion may-begin; no calibration of physical trackpad movement, acceleration or momentum. |
| Home / App Switcher | Native Home and existing button captures use typed Indigo calls | ipb functions are implemented; direct App Switcher usage differs from Device Hub's Home double press, so compare behavior rather than demand byte identity. |
| Rotate | Later measured Rotate Left changes device orientation to landscapeLeft while Settings display stays rot0; rotated preview clicks still work. No HID send for the rotation itself. | Mirror needs device/display/presentation orientation separation and service-specific input transforms. The earlier presentation-only inference is superseded. |
| Siri | Typed button code `0xcf`, states 0/1, ~0.509 s interval; no visible UI | Not implemented; full typed page decoding and a working-device comparison still needed. No settings were enabled to force success. |
| Recording / Action Button | Both disabled in Controls on this 13 Pro | Not validated capability gaps. Camera Control requires other hardware; `screenrecord` still has its recorded devicectl limitation. |
| Remote unlock | Not tested in this run | Static keypair/entitlement evidence remains a candidate mechanism; no new permanent-impossibility claim. |

## Verification and remaining acceptance

Local build uses `make XCODE_PATH=/Applications/Xcode-27.0.0-Beta.6.app`; installation is staged
under a local evidence directory, never into the user's global prefix. Host fixtures are
`scripts/test_bounded_sender.sh` and `scripts/test_smoke_matrix.sh`.

The smoke fixture requires an unlocked iOS 27 phone and a GUI login session. It opens Settings,
scrolls the list, types and clears `a` in Settings search, and returns Home. `TAP_XY`/`LONG_XY`
select safe home-screen icons; `KEY_XY`/`KEY_CLOSE_XY` accommodate the target search layout.
Screenshots must show the expected transitions, not merely exceed the pixel threshold.
The final installed-layout run passed on the local macOS 26.5.1 host, and its key screenshots
confirmed Settings launch, App Switcher, list down/back up, context menu, search input/clear and
final Home. The sender and smoke host fixtures also passed. These results validate this local
configuration; they do not close the supported release-matrix gate below.

The macOS 27 host (26A5425a, CoreDevice 642.15) built the helpers and passed the bounded sender
fixture in an isolated directory. Its selected Xcode is **26.4**, and its paired iOS 27 device is
**unavailable**. This is host build evidence only. The declared macOS 27 + Xcode 27 + iOS 27 release
gate remains pending; historical passes do not validate this patch.

After the user manually unlocked the Mac, native mirror regression on revision `1ed76f7` passed:
Settings tap, list drag down/back, Home/App Switcher shortcuts, bottom-edge Home, screenshot,
fit/actual-size fallback, a correctly mapped tap after resize, and normal window close. All 23
dispatched events completed with zero report/barrier codes; no abandoned/in-flight sends or child
processes remained. The one synthetic precise scroll event lacked a phase and was explicitly
rejected without moving the list. This closes the local mouse/button/digitizer regression, not
physical trackpad parity. Volume and Lock/Wake were not rerun. See `docs/verification.md`.

## Next work

1. Finish the supported-matrix gate when the host/device prerequisites are available.
2. Prioritize live display/capability metadata, held-key/chord input, and orientation transforms
   as detailed below. Preserve no-replay and sender ownership.
3. Capture a reproducible original permission prompt and locked-device Device Hub A/B before
   changing touch fields or asserting entitlement causality.
4. Give agents frame identity/PTS/orientation and verify the actual AccessibilityAudit service.
   Static framework strings alone do not prove a remotely readable UI tree.

## Deeper Device Hub lessons (2026-09-21, revision c14eed6)

The same local host/device seed was used. DeviceKit is build **255.2.3** at
`/Applications/Xcode-27.0.0-Beta.6.app/Contents/SharedFrameworks/DeviceKit.framework/Versions/A/DeviceKit`.
Two actual Device Hub captures resolved all ten taps, shed none and detached cleanly: 35 calls
for keyboard experiments and three for the rotation/click experiment. Runtime details and raw
report interpretation are in the new sections of `docs/protocol.md`; local artifacts are under
`~/.local/state/ipb/20260921-deep/`. No product code was changed in this research pass.

### Recommended additions, ordered by practical value

| Addition | New evidence / existing code gap | Smallest useful implementation and acceptance | Effort / risk |
| --- | --- | --- | --- |
| **Live display and capability snapshot** | `devicectl device info displays` returns primary bounds 1170x2532, pointScale=3, display/native orientation, backlight and display ID. `info details` provides capability feature IDs. Mirror currently begins with the product-type table (`Sources/mirror.m`, `selectTableContentRect`). | Query at session startup; select `primary` explicitly, range-check against the decoded frame, and retain explicit fallbacks. Expose structured supported/unsupported/error states. Test an unknown model, padding, multiple display entries and unsupported operations. | S–M / medium: extra query failure must not silently become a guessed size or unsupported capability. |
| **Held-key state and chords** | Shift+A and Command+A contain two simultaneous usage bits. Current `makeKeyboardReport` sets at most one bit; mirror only implements selected shortcuts. | Maintain a pressed-usage set and modifier transitions on the existing serial sender; expose chords for CLI and focused capture for mirror. Verify selection/deletion, overlapping keys, repeat policy, focus loss and healthy-session release. Preserve uncertain-send failure semantics. | M / medium: stuck modifiers or host shortcuts consumed by the wrong target. |
| **Separate text insertion from key injection** | Injecting `aA1!` produced correct key usages but the phone input method yielded `啊A1!`. Synthetic `中文🙂` produced no HID report or text. Paste emitted only Command+V. Existing UTF-8 clipboard round-trip is already documented. | Define distinct `key/chord` and focused `text` behavior. First validate clipboard copy + paste as one end-to-end operation; report clipboard policy rejection and verify focused output. Do not promise arbitrary text from a loop of physical keys, or enable continuous clipboard sync as a hidden fallback. | M spike / medium: input method, focus and clipboard policy can alter or block output. |
| **Three orientation states and per-service coordinates** | Rotate Left changed device orientation, while display orientation stayed rot0 and preview rotated. A rotated General click succeeded; Pointer and Digitizer coordinates differed by a quarter-turn relation. DeviceKit exposes `HIDEventGeometry` with window/view/unit transforms, ROI and orientationCorrection. | Bind geometry to selected display and current frame; implement forward presentation and inverse input transforms, with separate pointer/digitizer mappings where required. Verify 0/90/180/270 degrees, padding, corners and bottom-edge gestures. | M / medium-high: a single rotation applied to every service can silently mis-tap. |
| **Observation metadata for agents** | `Sources/video_stream.m` already receives and orders actual CMSampleBuffer PTS but emits JPEGs without that metadata. Display inventory changes across the live-view session. | Add a versioned optional frame envelope/sidecar with sequence, stream epoch, PTS/timebase, host receive time, display ID, content rect and orientations; correlate submissions to later observations without calling a barrier an action-success acknowledgement. | M / medium: preserve existing stdout framing and distinguish static content from stale transport. |

Effort is a coarse estimate including targeted validation: S is hours, M is roughly one to a few
days; it is not a promise that unknown private protocol paths are already solved.

### Boundaries learned from Device Hub

- **Capabilities are per operation.** This phone advertises `startaudiooutput`, but lacks
  `audiooutput` (device selection); `device info audio` returns error 1001. Screen Recording is
  absent from the current capability list, consistent with the disabled menu and earlier failed
  command. Feature presence still does not guarantee successful session setup.
- **Display inventory is live.** A non-primary Wireless display appeared alongside LCD while
  Device Hub viewed the screen and disappeared after quitting it. That is not evidence of a
  permanently attached second physical screen; never select the first/largest entry blindly.
- **Clipboard has its own policy and UI.** Device Hub exposes Use Shared Clipboard, Get Clipboard
  and Send Clipboard separately from ordinary Paste. `devicectl ... pasteboard info` returned
  26006 for `com.apple.is-remote-clipboard`; contents were not read or overwritten. This does not
  prove why the earlier CUA paste timed out, nor that every clipboard state is unsupported.
- **Do not infer multi-touch from method names.** On this binary, `magnifyWithEvent:` and
  `rotateWithEvent:` enter the shared capture/menu handler. Separate SwiftUI gesture metadata and
  UniversalHID types are leads, not proof of remote pinch/rotate emission.
- **Scroll remains an explicit research item.** The inspected ScrollCaptureNSView entry forwards
  AppKit deltas to its closure without a gain conversion; the full downstream remote report
  mapping is not established by that entry. Current mirror already has phase/momentum mapping
  and raw/accelerated fields. Do not replace it based on this partial static path.

The next focused spike should be display/capability JSON plus chord state, followed by the focused
text test. UI-tree transport, physical trackpad calibration, remote unlock, multi-touch, audio
streaming and recording were not validated by this pass.

## Rejected alternatives

- Copy Device Hub timestamp/identity values without a demonstrated failing effect.
- Treat timeout as cancellation, replay uncertain input, or force an unordered UP.
- Grade a command by rc=0 or image hash alone; arbitrary animations can satisfy either.
