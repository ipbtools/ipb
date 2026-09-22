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
  Next: establish target synchronization and query liveness, reproduce Inspector's point-query
  setup, and characterize target detail restrictions before promising arbitrary-app full snapshots,
  coordinates or element-based actions.

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
