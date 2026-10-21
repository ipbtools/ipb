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
5. Exercise the affected flows, run applicable host/installed/smoke checks and create a PR.
   On 2026-10-21 the user subsequently waived additional physical testing and authorized
   merge/publication after Opus5.5 review without unresolved blocking findings. Prepare
   v0.5.0 and update stable Homebrew under that version-specific decision; keep the full
   supported native device matrix explicitly unverified.

## Current evidence and first discriminator

The October13/14 deep tree, frame and Calculator action controls remain as documented
in `ui.md` and the dated verification records. They do not establish prior-authorization
independence. The user has no never-authorized device available; use the existing
phones and investigate an explicit status/disable mechanism first.

The installed CoreDevice642.15 command help exposes no named Automation Mode getter
or setter. Developer Mode is a distinct state. The documented testmanagerd automation
connection can enable Automation Mode during session construction and must not be
used as a status-only probe. The matching iOS27/24A437 AutomationMode framework's
reader getter resolves to the phone-local `com.apple.dt.automationmode.reader` and
`requestAutomationModeEnabledStateWithReply:`; a client-scoped disable is not a
global reset. No supported host forwarding path for the local reader is established.

The user approved a temporary ordinary read-only diagnostic App, without XCTest,
tests or a control service; it must be removed after validation and is not an ipb
dependency. Its actual reader BOOL replies on13Pro were DISABLED at03:04:19.371Z
and03:08:04.880Z. Between those replies, release-source native Settings189-node
reads/full-state, Back and Developer-row press, Calculator45-node read and the new
ordinary App's11-node read/Query press succeeded. Independent screenshot/fresh-page
controls confirm the Settings navigation. No phone setting was changed. A centre
point in the probe's blank area returned error8; an explicit point on its button
selected the app successfully. This is a selection boundary, not a false Mode value.

Continuous during-action sampling was not started: another task changed13Pro's
foreground and the fresh target guard stopped before sending an action. The user
authorized coordination. Agreed allocation on2026-10-21: this task exclusively uses
12mini; “Review PR 1 兼容性” exclusively uses13Pro. That peer plans to enable Mode
for its separate NSXPC research;13Pro's earlier negative replies cannot describe
later state. Re-establish the negative control on12mini before dependent acceptance.
The peer was asked to remove only this task's temporary probe from13Pro.

On the exclusively allocated12mini, the same read-only reader returned DISABLED.
A bounded monitoring task then recorded27 real BOOL replies from03:19:25.995Z
through03:19:40.537Z, all DISABLED and none UNKNOWN. These replies overlap the
release-source Settings184-node native/full-state read, Back, Settings143-node
read, Calculator45-node read, SidebarButton press and History95-node read.
The independent screenshot confirms the History overlay. No XCTest connection,
Runner or Mode-setting call is part of this control. This establishes current-Mode
independence for these tested paths on this previously authorized iOS27/24A437
phone; it does not replace a never-authorized-device control or expand seed support.

Current local host is supplementary macOS26.5.1/25F80, active Xcode26.5/17F42 with
CoreDevice642.15 installed. USB inventory lists12mini and13Pro on iOS27.0/24A437;
15Pro is network-available on27.0.1/24A446. Initial13Pro native CoreDevice lock/process
reads both time out at10s, before any interaction; stale discovery versus device-state
cause is unresolved. A selected-USB AX baseline is a separate transport check, not
proof of Automation Mode state. Keep raw observations outside Git.

## Implementation progress

The branch shares one fresh native selector resolver: exact string
identifier/label/value/class conjunction, distinct-handle ambiguity checks,
snapshot-local locate results and bounded presence/absence wait. Qualified presses
re-resolve before live state/frame/hit/PID/display guards. Identifier-only press
output and same-process dump schemas remain unchanged. A real paste-modal tree
required preserving proven terminal foreign-PID AXRemoteElement references;
foreign action targets and other foreign structures remain rejected.

Explicit replacement uses one existing clipboard/HID path: select-all then paste,
without an AX value setter. Element input first requires the unique fresh target to
be native3002's actual text-entry first responder; it never focuses automatically.
It invokes the same source/installed wrapper once, bounds/reaps the child process
group and checks same-identity exact value readback. A real paste modal leaves the
result nonzero/unverified; explicitly allowing it and rereading confirms Unicode
and Battery/Bluetooth search business results, without resending text.

Native scroll-to-visible is one action11 followed by fresh state/frame/hit checks.
12mini General moves y806→389; an already-visible call preserves native false
while independently verifying its postcondition. No gesture loop is introduced.
Explicit alert-press requires observed SpringBoard PID, exact native container
title and exact descendant button label. It has separate semantic-action policy
and reports hitTestVerified=false; ordinary press guards are unchanged. The real
container/UILabel duplicate title is handled at the container, and a bounded2s
read-only settle checks disappearance after exactly one native action5.

Source and isolated-install12mini modal actions return native acceptance plus
verified disappearance. Locator/History close and missing-target wait controls
pass.87 maintained AX tests and the complete local host checks pass, including
real owned child-process cancellation cleanup and source/installed wrapper-path
fixtures. Isolated-install AX-only smoke passes14 ordinary/142 native/142 full-state
records, with closed child graphs and complete cleanup. An unfocused-input negative
control fails before input and leaves the Battery clipboard unchanged. The final
reader reply at04:23:08.614Z is DISABLED. The12mini probe is uninstalled, absent from
fresh app inventory/process observations, and Settings is restored with keyboard closed.
The peer reports removing our13Pro probe (来源：peer); this task does not contact that
device. Implementation commit is `c4f29f2`, reviewed in
[PR#9](https://github.com/ipbtools/ipb/pull/9). The user's subsequent decision removes
the additional-device-test hold for v0.5.0; it does not mark that matrix as passed.
Opus5.5's review of `01f0d9a` returns ACCEPT, requesting a pre-tag fix for a wait
deadline interrupting an in-flight read. Host-only regression reproduces the missing JSON;
the correction preserves the last complete observation and distinguishes an independent
request timeout. All89 AX tests pass after the correction. Opus5.5's focused follow-up
at `d3ba9bd` also returns ACCEPT, confirming both items resolved without remaining
source-review blockers. Host/package/Homebrew checks remain publication gates.
Review/build results and raw references stay
outside Git. Default local installation is outside this release task.

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

The current-Mode negative control is established for the recorded12mini paths,
without a test session. Keep never-authorized first use and other seeds explicitly
open; a successful previously authorized device is not a substitute for that control.

Use maintained host fixtures for selector ambiguity/freshness and action boundaries.
Real-device flows must verify visible/effective outcomes and cleanup, with raw artifacts
outside Git. The full supported macOS27/Xcode27/iOS27 smoke remains distinct from
supplementary local or USB-forwarded AX controls. For v0.5.0 the user explicitly
waived additional physical testing and authorized publication after Opus5.5 review
and host/package checks. Do not resume device operations or infer a general waiver.

## Rejected alternatives

- Start XCTest to query authorization: may change the state being measured and violates
  the requested no-Runner acceptance route.
- Treat Runner removal or reboot as authorization reset: reset semantics are unproved.
- Generalize the AX whole-value setter: prior controlled multiline cases changed text
  without updating the business model.
