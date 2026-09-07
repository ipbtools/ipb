# AGENTS.md — devicehubctl

Guidance for any AI agent (Claude, Codex, others) working in this repository. Repository-local rules here override the machine-wide `~/.claude/CLAUDE.md`.

## What this project is

devicehubctl drives a physical iPhone from a Mac the way `adb` drives an Android phone: tap, swipe, long press, keys, Home, App Switcher, screenshot. It does this **without XCTest and without any third-party server on the phone**, by speaking to the HID daemon (`dtuhidd`) that Apple ships inside the Xcode 27 developer disk image, over the same CoreDevice / RemoteXPC path Xcode 27's Device Hub uses. The long-term goal is an adb-class tool for the agent era; see the roadmap below.

**Current release scope (v1, "simple validation build"): macOS 27 + Xcode 27 beta host, iOS 27 device.** Nothing else is a supported target. Do not add compatibility shims for other combinations without a matrix entry in `docs/verification.md` proving they work.

## Documents and what each one is for

| Document | Purpose | Update when |
| --- | --- | --- |
| `README.md` | Project purpose, requirements, build, usage, exit codes, smoke gate, pointers to everything below | Any user-facing behaviour or requirement changes |
| `docs/protocol.md` | Protocol map: transport, features, Swift symbol evidence, service IDs, **captured wire format** (the `Wire Format` section is the authoritative reference for message shapes) | Any new message, field, feature, or evidence |
| `docs/verification.md` | Dated, host+device-specific verification records and the compatibility matrix; what was proven, how, with what artefacts | Every verification run; never edit older records, append |
| `docs/standalone-distribution.md` | Plan for shipping without Xcode.app (host options A/B/C, recommendation, open items, rejected alternatives) | When the distribution plan changes |
| `docs/research/adb-capability-boundary.md` | What adb offers and what an iOS equivalent must provide | Reference; rarely |
| `docs/research/agent-frameworks.md` | Arbigent, Maestro, Appium MCP, mobile-mcp, agent-device, research agents, benchmarks; what primitives agents consume | Reference; refresh when the landscape moves |
| `docs/research/ios-peer-tools.md` | idb, pymobiledevice3, go-ios, libimobiledevice, WDA, devicectl, Device Hub, device clouds | Reference |
| `docs/research/direction-brief-2026-09-07.md`, `direction-review-astra-2026-09-07.md` | Evidence brief and the independent (Codex gpt-6-astra) direction review with a four-week plan | Superseded by newer reviews; keep for history |
| `scripts/smoke_matrix.sh` | The acceptance gate: exits non-zero on any failed step or unexpected output; interactive mode captures screenshots | Whenever a command's contract changes |

Plan documents for feature-level work go in `docs/` next to the ones above, named after the feature; small fixes are recorded in `docs/verification.md`, not in new files. Overwrite plans in place; history lives in git.

## Rule 1: every protocol claim has a cited source

The protocol is private Apple ABI/wire format. Nothing goes into code or `docs/protocol.md` as fact unless it is backed by one of:

1. **Apple documentation or shipped metadata**: `xcrun devicectl` output, launchd plists inside the DDI (`RemoteServices`, `Features`, entitlements), Info.plist/version.plist, headers when they exist.
2. **Runtime evidence**: captured messages (the RemoteXPC interposer in `docs/verification.md`), log output, replies from the device, screenshots proving an effect.
3. **Disassembly / symbol evidence**: `nm`/`swift-demangle` output, Swift reflection field descriptors, `strings`, `otool -l` (record the binary path and version).

Each fact in `docs/protocol.md` says which of the three it rests on and on which seed (host build, CoreDevice version, DDI build, iOS build). Inferences are labelled as inferences. When a seed changes, re-verify before trusting a stored assumption; the helper prints exact CoreDevice errors so that drift shows up as a concrete error string, never as a silent fallback.

## Rule 2: keep the code small, and let the architecture prevent whole classes of bugs

- One transport path per concern, no duplicates. The wire format is plain XPC dictionaries (see `protocol.md`); prefer building those dictionaries in one place over hand-written Swift ABI shims. The remaining ABI shims exist only as the oracle for what Apple's own client sends; do not add new ones.
- **Failure is an exit code, not a log line.** The helper returns 0 only when every step reported success; every refused socket, dispatch error, active-connection error, or watchdog fires a distinct non-zero code (`README.md`, "Exit codes"). The wrapper never converts a failure into a default value silently; fallbacks are explicit opt-ins (`UHID_SERVICE_FALLBACK`).
- No unbounded waits: every helper run has a watchdog (`HIDCTL_TIMEOUT_S`).
- Actions that have been sent to the device are never replayed automatically. Retry is allowed only before anything has been sent (socket creation, tunnel warm-up).
- Device selection, tunnel state, service discovery, and sending are separate steps with separate errors, so a failure names the layer that failed.
- Prefer deleting a code path over adding a flag. If two commands differ by one argument, they share one function.
- Coordinates are normalised (0..1) at the CLI boundary; nothing downstream sees pixels.

## Rule 3: fixes need a reproduction and a reachable trigger

Before changing code to fix a problem:

1. Reproduce it with a command from this repo (ideally a `scripts/smoke_matrix.sh` step or a one-line `bin/devicehubctl` invocation) and record host, device, and builds.
2. State how a user reaches it: which command, in which device state. "Could happen in theory" is not a bug report.

Review findings are triaged by **reachability × self-recovery**: a finding is worth a fix on top of the planned work only if a normal user hits it (high reachability) and the system does not recover by itself (low self-recovery, e.g. a stuck tunnel, a silent wrong tap, a misleading exit code). Edge cases with low reachability or that self-heal on the next call are recorded in `docs/verification.md` under "known, not fixed" and are not patched one by one. Do not chase corner cases with successive patches; if the same area needs a third patch, redesign the area.

## Rule 4: verification is part of the change

A change is done when `scripts/smoke_matrix.sh` passes on the supported matrix and the result (host, device, builds, artefact paths) is appended to `docs/verification.md`. Interactive steps need screenshot evidence; identical consecutive frames are a warning that must be explained (system alert, Home on Home), not ignored. `rc=0` alone is never evidence.

## Working notes

- Device identity is the CoreDevice UUID from `devicectl list devices --json-output`; the 642.x table view prints UDIDs, which the service rejects.
- A fresh or idle device has `tunnelState = disconnected`; HID sockets fail with CoreDeviceError 4000 until any `devicectl device ...` call warms the tunnel. The wrapper does this once on exit code 4.
- `bin/devicehubctl` (zsh) is the CLI; `build/action_sender_mercury` (ObjC + Swift glue + arm64 shims) is the helper; both are invoked by `scripts/smoke_matrix.sh`.
- The macOS 27 test host is <macos27-host> (see the machine-level memory notes); it sleeps after one idle minute, run `caffeinate` for long sessions.

## Roadmap (see the direction review for detail)

1. v1 simple validation build, macOS 27 + iOS 27 only, current helper + wrapper + smoke gate.
2. Python client on pymobiledevice3 (CLI + MCP sharing one session layer), keeping the helper as the protocol oracle; persistent session, screenshot contract with frame id/orientation, Unicode input via pasteboard.
3. Decide on a native single-binary implementation only if licence, performance, or install cost measured in step 2 demand it.

Answered 2026-09-07 (`docs/verification.md`): the device does **not** need iOS 27. With the Xcode 27 DDI, an iOS 26.6.1 iPhone 15 Pro passed the full interactive smoke; the only OS-dependent difference is that the `touchscreenGesture` (0x501) service, used by `pointer` and `scroll-report`, exists on iOS 27 only. Widening the v1 support statement beyond iOS 27 is a product decision; the smoke gate already handles both service sets.
