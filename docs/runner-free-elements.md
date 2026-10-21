# Runner-free element automation

Branch: `codex/runner-free-elements`, based on main `3842611` / release v0.4.0.

## Objective and order

Replace the common WDA-dependent agent interaction loop without installing or starting
any third-party phone Runner. Apple system/DDI services and existing pairing remain
the transport. The user authorized implementation, real-device acceptance and a PR
on 2026-10-21, in this order:

1. Establish whether native deep reads and direct actions work with XCTest Automation
   Mode explicitly disabled. A previously authorized phone without a current Runner
   is not a clean negative control.
2. Extend fresh element location and guarded actions, preserving exact-identifier
   compatibility and rejecting ambiguous targets.
3. Add element-targeted input with explicit edit semantics and effect observation;
   cover clipboard/HID and separately proven AX capabilities without automatic fallback.
4. Add bounded scroll-to-target and explicit alert discovery/button actions.
5. Exercise the affected flows on physical devices, run applicable host/installed/smoke
   checks and create a PR. Do not merge or release as part of this request.

## Current evidence and first discriminator

The October13/14 deep tree, frame and Calculator action controls remain as documented
in `ui.md` and the dated verification records. They do not establish prior-authorization
independence. The user has no never-authorized device available; use the existing
phones and investigate an explicit status/disable mechanism first.

The installed CoreDevice642.15 command help exposes no named Automation Mode getter
or setter. Developer Mode is a distinct state. The documented testmanagerd automation
connection can enable Automation Mode during session construction and must not be
used as a status-only probe. Shipped symbols include a state getter and client-scoped
disable method; their availability to an independent host and reset semantics remain
unverified. No phone setting is changed by this static observation.

Current local host is supplementary macOS26.5.1/25F80, active Xcode26.5/17F42 with
CoreDevice642.15 installed. USB inventory lists12mini and13Pro on iOS27.0/24A437;
15Pro is network-available on27.0.1/24A446. Initial13Pro native CoreDevice lock/process
reads both time out at10s, before any interaction; stale discovery versus device-state
cause is unresolved. A selected-USB AX baseline is a separate transport check, not
proof of Automation Mode state. Keep raw observations outside Git.

## Implementation constraints

- One shared fresh locator/resolver for supported actions; snapshot node IDs never
  become reusable device handles. Preserve selected PID/display and ambiguity checks.
- Every effect has explicit not-sent/submitted/accepted/refused/unknown handling.
  Never replay a submitted action or switch input mechanisms after an uncertain result.
- Waits and scroll loops are bounded. A sent gesture is distinct from reaching a target;
  observe the fresh page after each intentional action.
- Input acceptance requires actual edit/business behavior where observable. AX value
  replacement alone can miss UIKit/SwiftUI multiline business callbacks, as recorded
  in research commit193cba7; do not generalize that setter to all text controls.
- Alerts require observed, explicitly selected buttons; no automatic acceptance or
  generic dismissal policy. Credential entry remains human-operated.
- Preserve default ordinary UI output and the native/supplemental schema separation.
  Do not weaken existing guards to imitate XCTest visibility or hittability.

## Verification and delivery boundary

First obtain explicit state evidence for the Automation Mode discriminator and run
native reads/direct harmless actions in that state, without any test session. If no
trustworthy negative state can be established, keep this gate open and report exactly
what remains unknown instead of claiming independence. Independent source/design work
can proceed while waiting for that evidence; dependent capability acceptance cannot.

Use maintained host fixtures for selector ambiguity/freshness and action boundaries.
Real-device flows must verify visible/effective outcomes and cleanup, with raw artifacts
outside Git. The full supported macOS27/Xcode27/iOS27 smoke remains distinct from
supplementary local or USB-forwarded AX controls. Only request PR acceptance after
the requested physical flows have passed within their declared scope.

## Rejected alternatives

- Start XCTest to query authorization: may change the state being measured and violates
  the requested no-Runner acceptance route.
- Treat Runner removal or reboot as authorization reset: reset semantics are unproved.
- Generalize the AX whole-value setter: prior controlled multiline cases changed text
  without updating the business model.
