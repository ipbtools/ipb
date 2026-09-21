# Device Hub alignment and reliability

## Scope and decisions

User request (2026-09-21): “开始修复剩余的问题，并且你实机操控下 devicehub，分析下我们还有什么功能和协议没有对齐”.
Start revision `f2e85a6`; branch `codex/devicehub-alignment`.

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
| Keyboard capture | `ipb` visibly entered Settings search; six 39 B reports on `0x200` | CLI keys work; mirror lacks ordinary key capture/typing and Unicode/IME forwarding. High practical priority. |
| Pointer / wheel | AbsolutePointer 19 B and Scroll 21 B target `0x501` | Target confirmed. Synthetic wheel only emitted zero-motion may-begin; no calibration of physical trackpad movement, acceleration or momentum. |
| Home / App Switcher | Native Home and existing button captures use typed Indigo calls | ipb functions are implemented; direct App Switcher usage differs from Device Hub's Home double press, so compare behavior rather than demand byte identity. |
| Rotate | Preview rotated left and back; native screenshot stayed portrait, no calls on ten HID taps | Mirror lacks presentation rotation and corresponding input mapping. This does not establish device-orientation control. |
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
configuration; they do not close either acceptance item below.

The macOS 27 host (26A5425a, CoreDevice 642.15) built the helpers and passed the bounded sender
fixture in an isolated directory. Its selected Xcode is **26.4**, and its paired iOS 27 device is
**unavailable**. This is host build evidence only. The declared macOS 27 + Xcode 27 + iOS 27 release
gate remains pending; historical passes do not validate this patch.

The Mac locked before the new mirror's native mouse/shortcut regression could be completed.
The computer-use tool requires manual unlock; the user has been asked. CLI/device tests and
source/host tests continue independently. Do not count a 120-second no-input mirror run as an
interactive input test. Final gate outcomes are recorded in `docs/verification.md`.

## Next work

1. Finish the supported-matrix and mirror input gates when the host/device prerequisites are available.
2. Add ordinary keyboard capture and measured pointer/scroll parity to mirror; preserve no-replay
   and sender ownership. Presentation rotation needs an explicit coordinate transform.
3. Capture a reproducible original permission prompt and locked-device Device Hub A/B before
   changing touch fields or asserting entitlement causality.
4. Give agents frame identity/PTS/orientation and verify the actual AccessibilityAudit service.
   Static framework strings alone do not prove a remotely readable UI tree.

## Rejected alternatives

- Copy Device Hub timestamp/identity values without a demonstrated failing effect.
- Treat timeout as cancellation, replay uncertain input, or force an unordered UP.
- Grade a command by rc=0 or image hash alone; arbitrary animations can satisfy either.
