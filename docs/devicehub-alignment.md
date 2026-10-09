# Device Hub alignment and reliability

## Scope and decisions

Branch `codex/devicehub-alignment`; current implementation starts from `cc43495`.
On 2026-09-22 the user selected live display/capability metadata, literal text input and mirror
orientation: “135都得解决，你继续研究下devicehub的实现，和我们现在做下对比，没问题就修复了”.
Keep the native oracle, accepted resident devicectl notification-observer keepalive, bounded
sender ownership and no uncertain input replay. No XCTest or third-party phone server.

## Current implementation

| Selected function | Implementation | Verification boundary |
| --- | --- | --- |
| Display/capability snapshot | `displays --json` and `capabilities --json` expose schemaVersion 1 + deviceIdentifier and Apple's live values. Capabilities are advertised operations, not guessed support. Mirror selects the unique primary nativeSize before table/Xcode/detection fallback. | Real primary LCD 1170x2532 / scale 3 vs padded 1184x2576; Wireless entry is not selected. Host fixtures cover missing/duplicate primary, invalid values and query errors. |
| Literal text | `text <text>` resolves keyboard, copies exact UTF-8 once, then sends `{Cmd}`, `{Cmd,V}`, `{V}`, `{}` on the existing keyboard service. Copy failure prevents paste; uncertain paste is not replayed. | Exact `ipb-中文🙂 A1!` appeared in Settings with Pinyin active. Clipboard policy can present Allow Paste; rc0 is submission, not semantic insertion. Clipboard is replaced. No implicit permission approval or clipboard synchronization in the command. |
| Orientation | Native crop, device direction, content direction and presentation coordinates are separate. Cmd-Left/Right changes actual device orientation; ordinary touch maps back to native axes, pointer uses presentation coordinates. A geometry change releases/drains old input before publishing. | Final native mirror opened/returned from General at all four device orientations. Rotated content was separately exercised in Calculator. No claim of calibrated physical trackpad behavior. |

`device_control.h` runs one background metadata query at most per second, never overlapping.
Apple timeout is 5 s with a 6 s host kill bound. Read queries do not wait on HID; explicit rotation
waits at most 2 s for old input releases. Close cancels the current query and prevents new launches.
Unsent rotation requests are coalesced while the query is busy. Query/schema failures end the session
explicitly. Polling is not frame-synchronous: external orientation may lag by a refresh interval.
`devicectl displays --stream` did not yield structured JSON updates, so its human console output is
not parsed. Saved screenshots stay cropped native pixels, independent of host preview rotation.

## Confirmed problems found while aligning

- The first rotated-content edge implementation incorrectly sent native coordinates through
  portrait Indigo edge handling. Device Hub's actual landscape Calculator capture instead uses
  58 B UHID touch on 0x101, locked + left; portrait capture uses locked + up. Static setters confirm
  all seven flag offsets. Rotated-content edges now use those native-space direction flags, frozen
  at Down through UP. Portrait content keeps the existing verified Indigo path.
- The HIDReport-returning ordinary-touch builder still used count 0 on UP, unlike the previously
  fixed Data-returning builder. They now share one byte builder with count 1 on release. Ordinary
  identity/max/timestamp conventions remain unchanged; the edge report follows its captured shape.
- A first rotation shortcut was dropped while metadata refreshed. Unsent relative intent is now
  queued and applied after the snapshot; no uncertain sent request is retried.
- A fixture with JSON `info: []` raised an Objective-C exception. The response shape is checked before
  subscripting; successful, failed, malformed, timed-out and cancelled queries have host regression tests.
- The initial new smoke text step accepted a paste-permission modal as a pixel change. It now uses
  Vision OCR within the focused Settings search field, excludes the clipboard suggestion row,
  and stops before clear/close when expected text is absent. Exact punctuation/emoji still require
  screenshot inspection. The CLI deliberately does not claim to inspect the focused application.

## Measured seed and acceptance

macOS 26.5.1 (25F80), Xcode 27 Beta 6, DeviceHub 27.0 (255.2.3.5), DeviceKit 255.2.3,
CoreDevice 642.15, UniversalHID 90.1, DDI 27A5252f, wired iPhone 13 Pro / iOS 27.0 (24A437).
Raw captures and success-only artifacts remain outside Git under the local state directory;
`docs/verification.md` records the condensed run and limits.

Build: `make XCODE_PATH=/Applications/Xcode-27.0.0-Beta.6.app`, followed by staged `make install`.
Host checks cover report bytes/held keys, all four transforms, metadata/clipboard failure contracts,
child timeouts/cancellation, sender ownership and smoke assertion failures. Device checks use the
installed layout and inspect actual screenshots, not return codes alone.
The final installed-layout interactive smoke passed, with all 20 screenshots inspected. Its text
step required the operator to allow one synthetic paste; the gate itself never answers the prompt.
Two unanswered-prompt runs correctly failed, and an earlier pixel-only false pass was rejected.

A 300 ms edge sequence using the same wire builder returned Home from Calculator
at both landscape directions. Approximately 6 ms CUA synthetic drags with correct flags did not;
no production delay or interpolation was added to hide that boundary. A physical mouse's timing
and physical trackpad calibration remain distinct from synthetic input tests.

The supported macOS 27 + Xcode 27 + iOS 27 release gate is still pending. A current SSH attempt to the
prior macOS 27 host closed at port 22; its older Xcode 26.4/unavailable-device observation is historical,
not a current prerequisite check. This local macOS 26 run is supplementary validation only.

## UI context research

SDK/source review and subsequent real-device AXAudit research on 2026-09-22. The current product
still has no element-query command. No jailbreak, injection or phone-side helper installation was
performed. A caption-only AX CLI result is not proof that the system lacks geometry.

- Apple exposes structured onscreen context through `appEntityIdentifier`,
  `appEntityUIElementProvider` and `AppEntityUIElement` (identifier, local bounds, selection state,
  subelements). These are app-provided semantic annotations, not a reader for arbitrary UIKit views.
  The local Xcode 27 Beta 6 iPhoneOS SDK declares `AppEntityUIElement` from iOS 18.4.
  [Apple contextual-cues documentation](https://developer.apple.com/documentation/appintents/providing-contextual-cues-to-apple-intelligence-and-siri)
  and [WWDC26 session 343](https://developer.apple.com/videos/play/wwdc2026/343/) explain the
  relationship between pixel understanding, entities and actions; they do not disclose Siri's full
  internal retrieval pipeline.
- iOS 27 `AppIntentsTesting.AppEntityDefinition.viewAnnotations()` is a public consumer for those
  annotations. The shipped interface returns entity + isSelected, without a frame property.
  Apple requires an XCUITest bundle signed by the same development team as the target app;
  this does not meet ipb's current no-XCTest/arbitrary-app goal.
  [Apple test-framework session](https://developer.apple.com/videos/play/wwdc2026/295/).
- The jailbreak project ios-mcp injects into SpringBoard and dynamically binds private AXRuntime
  functions to query another PID's AX handles, attributes and hit tests. Its source requests
  label/value/role/frame/children; source existence is not proof every fallback works, and its
  README's claimed iOS 13–18 range does not establish iOS 27 support.
  [Injection filter](https://github.com/witchan/ios-mcp/blob/38cafd5fbda7a4dcb3821b94cbb3523fc905c0b2/ios-mcp.plist),
  [runtime bridge](https://github.com/witchan/ios-mcp/blob/38cafd5fbda7a4dcb3821b94cbb3523fc905c0b2/MCPAXAttributeBridge.m),
  [node attributes](https://github.com/witchan/ios-mcp/blob/38cafd5fbda7a4dcb3821b94cbb3523fc905c0b2/MCPAXNodeSource.m#L2843).
  This remains AX. FLEX instead recursively reads real `UIView.subviews` inside the target process;
  it requires app integration or injection, not a remote UIKit-object API.
  [FLEX hierarchy implementation](https://github.com/FLEXTool/FLEX/blob/63a6f588841e94e4c3adaa045ff16eb8163f0bb4/Classes/ViewHierarchy/TreeExplorer/FLEXHierarchyTableViewController.m#L122).
- Accessibility Inspector's attribute-query path is now captured, and an independent pymobiledevice3
  probe has read labels, traits, class/address and a 15-node partial hierarchy in Looktech Lab through
  the advertised RSD `remoteserver.shim.remote` service. The
  [pymobiledevice3 implementation](https://github.com/doronz88/pymobiledevice3/blob/10194d12e7cf17453887b7ac3d46e1b85b5a057a/pymobiledevice3/services/accessibilityaudit.py)
  exposes focus traversal but omits the property-query wrapper and `AXAuditNode_v1` decoding used
  in this probe. On two Settings elements the same queries returned labels/traits but only a single
  hierarchy node and no class/address; the target-dependent restriction has no established cause.
  `Frame`/`AXFrame` probes returned nil. Preview + screenshot drew the selected element's green
  outline, but returned display geometry without a structured element rectangle. Normalized-point
  hit-test probes returned nil; their arguments were constructed from host disassembly, not captured
  from a successful Inspector hit test. See [captured protocol](protocol.md#accessibility-inspector-and-axaudit-2026-09-22).
  A follow-up focus cycle in Lab exported 36 focus elements and a 131-node merged hierarchy, but
  automatically scrolled the page and accumulated two distinct heading tokens. It is a temporal
  union, not a complete snapshot. Recursive expansion stopped on a timeout; that run also returned
  Lab's root while screenshots showed Settings. After restoring Lab, a fresh session had app-state
  events but no focus seed within three seconds. These failures have no established root cause.
  Rechecking individual replies shows 14–46 nodes per focus query; the app-root query already
  occurred and returned only two nodes. The missing step is not simply querying the root once.
  Cached iOS 27 AXRuntime serialization identifies an application-root handle from a real PID,
  avoiding dependence on a focus event. On the returned 13 Pro, a bounded read of Lab PID 7720
  twice reached the same 129-node/128-edge element tree, with every handle queried and no nil or
  timeout. The tool used each node's own reply for its children; two extra edges in ancestor-context
  replies would otherwise create false double parents. Before/after screenshots showed the same
  Lab home page. This proves a usable tree for that page and build without a phone-side helper or
  focus motion, not atomic capture or completeness across apps.
  Offline iOS 26.5 simulator `axauditd` provides a concrete comparison: hierarchy replies contain
  local children/siblings and an ancestor chain, child enumeration is capped, and attributes have
  target-policy and focus-history filters. Its parameterized handler immediately returns nil.
  These are simulator-specific constraints, not an established cause of the physical iOS 27
  failures. See [root and hierarchy evidence](protocol.md#axaudit-root-handles-and-hierarchy-limits-2026-09-22).
- Offline inspection of DDI 27A5252f / XCTest 25227 now traces XCTest snapshots to device
  `testmanagerd`: `XCTestSession` → `XCAXManager_iOS` → `XCTAutomationSupport` → AXRuntime's
  parameterized snapshot query. A separate `com.apple.dt.testmanagerd.remote.automation` service
  directly implements snapshot and attribute RPCs over DTX. Its launchd declaration requires
  `AppleInternal`, and startup only registers its listener when
  `os_variant_allows_internal_security_policies("com.apple.testmanagerd")` succeeds. The ordinary
  `.remote` service instead creates a harness/control session; a successful control handshake is
  not proof of snapshot access. See [service and authorization evidence](protocol.md#xctest-snapshot-service-boundary-2026-09-22).
  This establishes a specific restricted implementation, not universal impossibility of a
  runner-free AX reader. On the 13 Pro, RSD advertised the direct automation endpoint, but its
  TCP connection did not answer a generic DTX capability handshake or a bounded proxy-channel
  request; ordinary testmanagerd `.remote` completed the same DTX handshake. This does not prove
  the direct endpoint's exact rejection reason or exclude a different Apple client exchange.
  `remoteAXService` was also advertised but closed during RemoteXPC handshake. See the dated
  verification record. AXAudit remains the demonstrated element-tree path.

Element trees have now been obtained without installing a phone-side app on two devices: the
13 Pro's existing Lab page and, after Developer Mode/DDI became available, the 12 mini's
SpringBoard and Calculator pages. The 12 mini yielded bounded, zero-nil graph closure twice per
target; Calculator's 45-node tree was identical in both runs. This closes the initial
feasibility question for those seeds. Arbitrary-app coverage, geometry and snapshot atomicity
remain open. Requested Opus 5, Grok 4.7 and DeepSeek Flash
consultations returned candidates; their suggestions were treated as hypotheses, not protocol
evidence. A successful hierarchy RPC or a closed graph alone does not establish completeness.

A fresh Opus 5.5 review focused the geometry search on three discriminators: capture Apple's
actual Inspector DTX exchange, test preview-outline differencing, and determine whether audit
rectangles are ordinary element frames. The 2026-09-27 physical 12 mini checks found one
Calculator and two SpringBoard **audit-issue** rectangles, but no mapping from an issue to an
arbitrary tree node. Several targeted previews did not reproduce an outline; a node action
re-encoded from the received focus token and descriptor still left Calculator unchanged.
The host point-query method sends an `NSValue` `{CGPoint=dd}` and handles a direct DTX reply;
the older suggestion that a nil reply necessarily means a missing `host*` callback is not
supported by that implementation. Correctly typed point requests nevertheless returned nil on
the physical device, so this is still an unresolved route. The 12 mini screenshot's actual
PNG/logical ratio is 3, while `displayNativeScale` reports 2.88; any visual fallback must map
from image dimensions rather than assume that scale is the PNG ratio. See the
[physical follow-up](protocol.md#element-geometry-and-action-follow-up-on-the-12-mini-2026-09-27).

A second bounded attempt got past Inspector's target picker, but the Apple host failed before
DTX: `AMDeviceConnect` and `AMDeviceStartSession` succeeded, while
`AMDeviceSecureStartService("com.apple.accessibility.axAuditDaemon.remoteserver")` returned
`kAMDRemoteConnectError`. The same service name opened through paired Python USB lockdown and
reported 45 AXAudit capabilities, so the host failure does not establish a missing device
service. A raw physical-device point request on that lockdown channel received a DTX `OK`
without payload; there was no later message in four seconds, while a capability control returned
an object. This corrects the ambiguity in the wrapper's `None` and bounds the callback
hypothesis, but does not explain why the point had no element. See the
[Apple-client boundary](protocol.md#apple-inspector-connection-and-point-reply-type-2026-09-27).

At the user's request, the same Xcode Inspector was then tested against the unlocked wired
13 Pro. Its `PDUIApp` audit completed with nine warnings, proving that this host can establish
an effective Apple AXAudit session on that phone. Direct AXAudit `testTypeHitRegion` on the
13 Pro returned three issue records that paired element tokens with rectangles; one token also
returned a label when re-encoded into the captured wire wrapper. `Frame`/`AXFrame` and direct
point lookups still returned nil. The audit's Home-screen Quick Look image did not match the
selected `PDUIApp` target's issue label, so it is not a verified screen-to-element mapping.
The 12 mini Apple connection failure is therefore not a universal host failure; its
device/state-dependent cause and arbitrary-node geometry remain open. See the
[13 Pro follow-up](protocol.md#iphone-13-pro-apple-inspector-and-issue-geometry-2026-09-28).

A bounded Apple-client selector trace on the 13 Pro captured target PID `0`, app monitoring,
targeted notification, event type `2` and inspection visuals. That run did not exercise a
pointer hit test and captured no point query. Replaying the observed setup in a direct session
still produced a nil point reply, so these selectors alone do not explain the missing element.

A further 13 Pro control selected foreground Calculator explicitly in Apple Inspector (its
process appeared after `ipb launch com.apple.calculator`). Injected taps opened Weather from
Device Hub's mirror and Calculator's History sheet from `ipb`, but Inspector continued to show
no selected element. A bounded host trace recorded only null focus/preview and section
descriptors during an All-processes target change; two touch windows had no hit on the traced
point/focus methods. This narrows the missing trigger to Inspector's selection path for these
injected touches; it does not rule out a human finger touch. The latest Apple audit outlines
were empty, so the documented issue-double-click path still lacks a reference capture. See
the [dated follow-up](verification.md#2026-09-28--13-pro-point-selection-and-foreground-app-control).

### AXAudit capture plan

**Updated 2026-10-09 after real-device captures.** The independent `claude-opus-5` and
`gpt-6-astra` assessments (source: peer) led to main-session verification of the old trace's
missing receive coverage, silent caps and wrong CGPoint decoder. The known host point caller
is Simulator code; physical selection must also be judged by device-pushed focus. The user
then explicitly chose **“用 13 pro 吧”** for this round and confirmed a real finger tap.
This overrides the earlier 12 mini allocation for these captures; refresh ownership and
host/device/PID state before another round. Results are supplemental macOS 26.5.1 + Xcode
27 B6 + iOS 27.0 research, not the macOS 27 release gate.

1. **R0 — passed within the stated capture boundary.** Python raw stream copies/offline decode
   passed local fixtures and retained live paired USB AXAudit message prefixes. In two session
   closures a final inbound header lacked its body; the decoder reports that incomplete tail
   explicitly, while selection and cleanup barriers are fully captured. A separate native Foundation
   fixture verified the exact loaded arm64e DTX ABI and outgoing callback bytes before Apple
   Inspector attachment. Bounded Apple runs retained outgoing serialization and incoming
   assembled parser bodies, complete typed focus/attribute/action data and detach footers.
   Incoming bodies do not preserve original fragmentation; a screenshot's last-fragment
   header requires explicitly labelled post-assembly size normalization. Preserve parser/
   transmitter identity: the Mac and phone can reuse message IDs. Detailed limits are in
   [the tracing method](devicehub-tracing.md#axaudit-reference-capture-boundary).
2. **R1 — finger and injection selection both positive.** Separate sessions first obtained
   a fresh matching Calculator focus, then armed the observed monitoring type 2. The
   confirmed finger tap and one `ipb tap 0.10 0.08` each pushed the History element without
   a host point query, then pushed monitoring 0. Re-arm before another selection; navigation
   used monitoring 0 because the actual CanNav reply was false. No inherent injected-input
   filter is supported by these results. Old September failures remain un-root-caused;
   initialization, target and daemon state changed together. Keep Calculator value 7.
3. **R2 — Apple selection/property/action reference captured.** Actual target PID 51031 and
   monitoring 2 preceded Apple's positive History selection. Ten ordinary property reads
   matched an independent fresh-token direct session; no ordinary Frame was advertised or
   requested. Apple Activate sends a null third argument and expects a reply. Both Apple
   and a single direct Apple-shaped action received empty OK but did not open History.
   This is a confirmed semantic no-effect on Calculator, not an action success or a proven
   entitlement cause. The installed pmd3 wrapper's shape differs, but aligning it alone did
   not establish activation. Do not automatically replay actions after empty OK.
4. **R3 — current issue handoff positive.** Both audits completed seven advertised types and
   returned one output-field issue. Apple's selected issue rectangle, transported token,
   target PID, double-click focus/lock request, Inspection identifier and phone highlight
   all matched the existing 7. The 390×844 logical / scale-3 screenshot agrees with the
   issue rectangle. Inspection gained no ordinary Frame query or descriptor afterward.
   This validates issue-to-element association only.

The [current captured protocol](protocol.md#axaudit-physical-selection-action-and-issue-handoff-2026-10-09)
records the request shapes and [dated verification](verification.md#2026-10-09--13-pro-axaudit-finger-injection-apple-action-and-issue-handoff)
records reproduction, cleanup and local references. The follow-up below resolves the earlier
framework call target and establishes a development-app action effect. Raw probes remain
outside Git. No production AX feature was added.

**Development-app/permission follow-up:** the existing Lab 1.20.0 (514) reports
`get-task-allow=true` in the current device installation database. A fresh matching gear-button
focus at PID 51300 returned `SwiftUI.AccessibilityNode` and its address, and one captured
Activate/null/expected-reply request opened Settings. It returned the same empty OK as the
earlier Calculator no-effect. The raw 24A437 dyld subcache now resolves
`AuditDoesAllowDeveloperAttributes` to `task_for_pid(mach_task_self_, pid, &task) == KERN_SUCCESS`.
The matching physical daemon has now been extracted from Apple's iPhone14,2 / 24A437 firmware;
its Mach-O UUID matches the live daemon's syslog UUID. Concrete callers check the predicate
for developer properties, actions and parent traversal. Current paired captures report NO for
Calculator PID 51502 and YES for Lab PID 51452, agreeing with their class/address reads.
The kernel policy causing task-port success remains untraced; literal get-task-allow alone
is not the proven cause. No extra semantic action was sent to repeat the earlier controls.

**Physical daemon boundary, now resolved:** ordinary reads use a fixed attribute-name dispatch
with no Frame/Position/Bounds branch; unknown names complete nil. Parameterized reads directly
complete nil. The action server discards its third argument, and denied/attempted actions all
complete without a semantic outcome. Nondeveloper string results are limited to 64 UTF-16
code units; hierarchy serialization caps child collections at 51 and filters parent traversal.
These are now physical iOS 27 findings, superseding the Simulator-only comparison for this
seed. More guessed ordinary Frame names or parameterized snapshot requests add no value here.

**Ordinary-element preview, positive:** the physical renderer refreshes native frame attribute
2003 and consumes the element's frame without the task-port predicate in the inspected path.
On Calculator, previewing a freshly received History token highlighted that specific button
despite developer permission NO. Before/after screenshots isolate a 120×120 pixel overlay
at (54,147), approximately (18,49,40,40) logical points at scale 3. This is measured overlay
geometry, not a returned native CGRect. It required neither an audit issue nor activation.
Cleanup removed the highlight, preserved Calculator 7 and restored the original Home page.

The [physical daemon protocol](protocol.md#axaudit-physical-daemon-handlers-permission-logs-and-element-preview-2026-10-09)
and [dated verification](verification.md#2026-10-09--13-pro-physical-axauditd-handlers-permission-logs-and-preview)
record source identity, handlers, captures and limitations. A separate native accessibilityFrame
attempt still has no getter result because debugger attachment stalled; the extra Apple Lab
reference with zero incoming messages remains invalid as a physical control.

**Latency constraint / revised priority:** the user rejected page-wide serial preview with
“耗时太久了吧，一个个来不知道要多久，没有更直接的方案吗”. Preview is retained as a
bounded single-target fallback and a proof of local geometry. Do not expand it into one
render/screenshot transaction per page node or claim an unmeasured latency. The main goal is
a device-side snapshot or an existing remote AX data/cache stream carrying node properties
and geometry together. AXAudit issue batches cover reported problems, not every page node.

**Next discriminators, in order:**

1. Prioritize the separate iPhone Mirroring AX stream and its host cache: the inspected code
   now has a resolved initial/incremental tree schema, secure archive fields and Frame **21**
   in the priority attribute batch. Physical iOS 27 code maps this to native attribute **2003**;
   its `AXPBackedAccessibilityServerPrimitives` starts `AXPRemoteCacheManager`, which generates
   the tree in the background. Full instruction sections match the original Apple firmware.
   The synthetic host codec preserves a node rectangle, but no phone tree has been received.
   Trace `ScreenContinuityShell` / `AngelServer` session activation and the
   `clientNeedsAccessibility` subscription into this producer, then capture/decode actual
   initial and incremental packets. Validate target identity, geometry space, coverage and
   cancellation. The external Mac AX `remoteDeviceContent` entitlement gate is distinct from
   network-session authentication; Inspector's `inspection` entitlement does not establish
   access to this content. The phone command-line interface has its own entitlement check and
   exposes only ping/state/stop, so it is not a dump shortcut. See the
   [resolved bulk path](protocol.md#mirroring-bulk-ax-schema-frame-and-physical-server-2026-10-09).
   Independent-client access, arbitrary-app coverage and a bulk rectangle export remain
   unverified. Keep the existing testmanagerd
   direct snapshot RPC as the second structured candidate, with its internal-policy/session
   gates explicitly tracked. Do not repeat generic handshakes without a new protocol clue.
2. Resolve the existing-app debugger attachment before attempting native `accessibilityFrame`.
   Retain a fresh PID/address and explicit stopped-target proof; a hang or vanished old PID is
   not a Frame denial. Treat this as a development-app-only fallback, separately from a generic
   phone observation API. The semantic activation control and current YES/NO predicate logs
   are already positive; repeating activation adds little. Kernel authorization remains a
   separate question. Do not install a Runner or change certificates merely to repeat the
   probe. Refresh exclusive 13 Pro ownership before another run.
3. Before productizing tree traversal, define target synchronization, partial-result policy,
   token lifetime and frame/action correlation, then pass the supported macOS 27 gate. A
   traversal cycle or graph closure is not completeness. Several app-state PIDs can report
   Foreground Running together; last-event-wins is not a validated foreground resolver.

For occasional single-node selection, the coordinate RPC's concrete backend **91701** and
0.1 s cache remain a useful lead; they do not replace a page snapshot. Inspect the backend and
CGPoint decoding before another hit-test probe. The physical screenshot handler also hides
visuals and supplies CGRectZero to the platform screenshot method, so it is not a demonstrated
shortcut for retrieving the current cursor rectangle.

WDA is a separate existing bulk option if a signed Runner is accepted: current upstream
`/source?format=json` takes an application snapshot and recursively emits nodes including rect
([source handler](https://github.com/appium/WebDriverAgent/blob/master/WebDriverAgentLib/Commands/FBDebugCommands.m),
[tree serialization](https://github.com/appium/WebDriverAgent/blob/master/WebDriverAgentLib/Categories/XCUIApplication%2BFBHelpers.m)).
It has not been tested on this project's current iOS 27 device. Preinstalled startup avoids
rebuilding each session but still requires a signed Runner; current Appium documentation also
requires working RemoteXPC on iOS 27 rather than the devicectl launch fallback
([preinstalled WDA](https://appium.github.io/appium-xcuitest-driver/latest/guides/run-preinstalled-wda/)).

Keep Apple service-start failures separate from DTX/API/semantic results. A menu highlight
or one successful capability response does not validate the target. Accept a matching focus
push as selection evidence, keep empty OK distinct from object-null/error/timeout, never pair
across connections by identifier alone, and clean up each session. Generic XCTest handshakes
still have not established a runner-free snapshot session. iPhone Mirroring's bulk producer,
schema and Frame field are now resolved static evidence, with a synthetic codec control;
session authorization, received physical trees and external retrieval remain untested.

## Remaining work

1. Complete the supported release-matrix gate with an available host/device pair.
2. Full mirror keyboard capture/chord API, frame identity/PTS correlation and UI-tree transport
   remain separate work. The minimal paste chord does not claim general held-key capture.
3. Physical trackpad calibration, original privacy-prompt A/B and locked-device protocol behavior
   need their corresponding actual inputs/states. No permanent impossibility claim.
4. Siri has a captured code but no verified effect; recording and newer hardware buttons remain
   gated by capability/hardware evidence. Standalone CLI/MCP transport remains a separate spike.

## Rejected alternatives

- Treat a capability listing, rc0, pixel change or an HID barrier as proof of UI action success.
- Copy ordinary-touch identity/timestamp values without a demonstrated need; silently guess geometry.
- Replay uncertain input, add synthetic gesture delays, or replace the accepted tunnel keepalive.
