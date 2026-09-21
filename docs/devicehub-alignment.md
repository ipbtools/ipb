# Device Hub alignment and reliability

## Scope and decisions

The user requested implementation of the remaining confirmed reliability fixes and direct
operation of Device Hub to compare its functionality and HID protocol with ipb (2026-09-21).
Start revision: `f2e85a6`. Branch: `codex/devicehub-alignment`.

Keep the current native helper and accepted resident devicectl tunnel keepalive. Do not replay
input whose delivery is unknown. Do not introduce XCTest or a phone-side third-party server.
UI-tree discovery, a new Python backend, and a general MCP server remain separate roadmap work.

## Work and acceptance

1. Reproduce and fix smoke false passes: require explicit explanations for expected unchanged
   screenshots, fail on unknown interactive preconditions, and distinguish unsupported GUI
   execution from real mirror startup errors. Exercise failure cases with host-only regression
   fixtures and then run the real-device smoke gate with screenshots inspected.
2. Observe Device Hub on the connected device with bounded, auto-continuing tracing. Include
   baseline, normal tap, drag, scroll, buttons and a safely cancellable system alert. Record actual
   service targets and report bytes; compare with ipb on the same screen and device state.
   A test of one system alert does not establish behavior on all permission prompts.
3. Reproduce media idle/stall behavior. Separate receipt/decoding progress from deduplicated output;
   retain output backpressure and finite watchdogs. Test a static screen and a screen that changes
   again after an idle interval, plus continuously changing media.
4. Reproduce the input timeout ordering problem with controlled fault injection. Give in-flight
   sends a bounded, ordered lifecycle; never promise an UP reached a disconnected device. Preserve
   finite shutdown, genuine errors, and the no-replay rule. Validate healthy real input afterward.
5. Update README, protocol, media and tracing current-state descriptions, and overwrite the head
   of verification.md. Preserve dated historical records. Record confirmed failures and fixes
   concisely, with success-only captures and full logs retained locally outside Git.

## Evidence and host boundary

The current Mac reports macOS 26.5.1 (25F80), CoreDevice 642.15, with Device Hub from Xcode
27 Beta 6. The wired iPhone 13 Pro reports iOS 27.0 (24A437). These are observations from this
session, not the host labels copied from older records. This host is outside the currently
declared macOS 27 release matrix; its results must be reported separately from that release gate.
The default selected Xcode is the older Xcode.app, so builds select the Beta 6 developer directory
explicitly. Raw local evidence root: `~/.local/state/ipb/20260921-alignment/`.

## Open questions

- Does the recorded system-dialog failure still reproduce after the contact-count fix? Root cause
  unknown; Device Hub versus ipb must be compared before changing report fields.
- Does a missing new image reflect idle content, decoder failure, or output blockage? Earlier
  frame-count observations do not distinguish these.
- Can a slow sender be drained without overlapping a subsequent call on the same connection?
  Current global-queue timeout code does not establish that guarantee.
- Device Hub remote-unlock and AccessibilityAudit transport have static evidence only; do not
  upgrade either to an end-to-end capability or permanent impossibility claim.

## Rejected alternatives

- Guess timestamp/identity values to fix system UI without a matching Device Hub capture.
- Retry an uncertain click, or issue unordered cleanup while an earlier send still runs.
- Treat rc=0, a changed PNG hash, or a historical smoke run as proof of the expected UI transition.
