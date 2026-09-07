# Live video stream (roadmap stage 2)

Goal: `ipb` delivers the phone's screen as a continuous stream (frames for an agent loop first, a file or pipe second), the way Device Hub mirrors a device, without XCTest or an on-device server.

## What the evidence says (2026-09-07, CoreDevice 642.15, DDI 27A5252f)

Sources: `nm | swift-demangle` of `CoreDeviceMediaStreamSupport.framework` (inside CoreDevice.framework), Swift field descriptors of `CoreDeviceUtilities` and `CoreDevice`, `strings` of `/usr/libexec/dtremotedisplayd` in the DDI, DeviceKit symbols in Xcode 27 beta 6, and `createservicesocket` probes against the iPhone 13 Pro.

1. **Device side** is `dtremotedisplayd`, service `com.apple.coredevice.displayservice`, features `getmediasupportinfo`, `getmediastreamserverstatus`, `startmediastream`, `startvideooutput`, `startaudiooutput`, `stopmediastream`. Actions inside: `MediaStreamGetSupportInfoAction`, `MediaStreamStartAction`, `MediaStreamStatusAction`, `MediaStreamStopAction`; streams are stopped by the daemon on sensor activity (`stopAllStreamsDueToSensorActivity`).
2. **The feature socket is a control channel, not the video path.** `createservicesocket` for `startvideooutput`, `startmediastream`, `getmediasupportinfo` all return a RemoteXPC fd (probe on the 13 Pro). The start request is `MediaStreamStartParameters` with fields `receiverIP, receiverPort, senderIP, senderPort, timeout, type, direction, negotiatorOffer, clientSupportedFeatures, options, sessionEventChannel`; the device answers with `DeviceMediaStream.ConnectionInfo` (`direction, receiver, sender {ipv6Address, port}, type, source, timeout, streamConfig, options`). `source` is one of `videoPrimaryDisplay`, `videoFromDisplayID`, `videoVirtualExternalDisplay(size)`, `videoSecondaryVirtualDisplay(size)`, `audioSystemOutput`.
3. **The video itself is RTP over the tunnel's IPv6 addresses, encrypted.** `DeviceMediaStream.MediaStreamConfig` has 48 RTP/RTCP fields (`DestIp`, `DestPort`, `Framerate`, `KeyFrameInterval`, `RTCP*`, `RXMaxBitrate`, `HDRMode`, `PixelFormat`, `LocalSSRC`, ...). CoreDeviceUtilities carries `negotiatorOffer` / `negotiatorAnswer` / `SRTPCipherSuite` strings, and the host client uses `AVCMediaStreamNegotiator*` from the private AVConference framework (the FaceTime media stack). A third-party RTP receiver would have to reimplement that negotiation; not planned.
4. **Host client is Apple's, and loadable by us.** `CoreDeviceMediaStreamSupport`: `MediaStreamSession(clientSessionID:)` → `makeVideoStream(withConfiguration:fromRemoteDevice:)` → `activate()` yields `VideoStreamEvent` (`receivedFirstFrame`, `receivedLastDecodedFrame(Data)`, `remoteVideoAttributesChanged`); `VideoStream.requestLastDecodedFrame()`. Configurations: `receiveMirroredPrimary(layer:timeout:)`, `receiveMirroredDisplayByIdentifier(_:layer:timeout:)`, `receiveVirtualExternal(layer:resolution:timeout:)`. Frames are decoded by AVConference into the supplied `CALayer`. DeviceKit wraps this as `AVConferenceVideoStreamHelper(device:clientSessionID:)` and `DisplayViewFramebufferAVC`; Device Hub draws that layer.
5. **What the client needs from us:** a `CoreDevice.RemoteDevice`, obtained through `DeviceManager(serviceConnection:)` + `deviceNamed`/tag lookup or `RemoteDevice(snapshot:)`, and a `CALayer` to render into.
6. Not related: `devicectl device capture screen-record` ("Screen Recording" capability), refused by all three test phones; `viewdevicescreen`, the older feature, refused with 1001.

## Control channel, captured 2026-09-07 evening (iPhone 13 Pro, iOS 27.0, CoreDevice 642.15)

Tool: `Experiments/probe/feature_probe.m` with `PROBE_SEND_JSON`. The service socket from `createservicesocket` for any display feature carries the same **host-style action envelope** the CoreDeviceService XPC API uses, not the `{messageType: "Request"}` envelope of the HID services (that one makes `dtremotedisplayd` drop the connection):

```text
{ CoreDevice.actionIdentifier: "com.apple.coredevice.action.<mediastreamgetsupportinfo|mediastreamstatus|mediastreamstart|mediastreamstop>",
  CoreDevice.deviceIdentifier: <CoreDevice UUID>, CoreDevice.invocationIdentifier: <UUID>,
  CoreDevice.coreDeviceVersion: {components: [642,15], originalComponentsCount: 2, stringValue: "642.15"},
  CoreDevice.CoreDeviceDDIProtocolVersion: 1, CoreDevice.input: {...} }
reply: { CoreDevice.output: {...} } or { CoreDevice.error: {domain, code, userInfo{NSDebugDescription|NSLocalizedDescription}} }
```

Verified replies:

- `mediastreamgetsupportinfo` → `supportedFeatures: 972`, "Primary video display mirrored output stream, System audio output stream, Virtual external video output stream, Video output stream by display ID, Display information, Screenshot capture", `avcFrameworkVersion: 2235.63.1.2`.
- `mediastreamstatus` → `running: false, sessions: [], runDurationSeconds: 0`.
- `mediastreamstart` input is `MediaStreamStartParameters`, decoded with Swift Codable; the device names each missing key, which gave the schema: `receiverIP` (string), `receiverPort` (uint), `timeout` (uint seconds), `type` (`"video"` accepted), `direction` (`"output"` or `"input"`, from the device's point of view; `output` = device sends), `negotiatorOffer` (data), `clientSupportedFeatures` (uint, e.g. 972), `options` (dictionary); `senderIP`/`senderPort` are then required semantically ("Missing senderIP", CoreDeviceError 9014); `sessionEventChannel` is optional. With all keys present and a bogus one-byte offer the device answers `NSPOSIXErrorDomain 49` (address not available), both with placeholder addresses and with the tunnel addresses reported by devicectl (`tunnelIPAddress fdd2:…::1` for the device, host `utun` `fdd2:…::2`), so it reaches the transport setup before it validates the offer.
- The host's `DeviceManager`-side API (`CoreDevice.action.mediastreamgetsupportinfo` sent to CoreDeviceService itself) answers "not implemented": these actions run in the client process over the feature socket, which is why Device Hub's traffic does not show in CoreDeviceService's log.

Host client facts (ObjC runtime dump, `Experiments/tools/dumpavc.m`): `AVCMediaStreamNegotiator` (`initWithMode:options:error:`, `createOffer`, `offer` NSData, `setAnswer:withError:`, `generateMediaStreamConfigurationWithError:`), `AVCMediaStreamConfig` (local/remote `AVCNetworkAddress`, SSRCs, SRTP/SRTCP cipher suites, send/receive master and media keys, RTCP settings), `AVCVideoStream` (`initWithLocalEndpoint:options:error:`, `configure:error:`, `start`, `stop`, `requestLastDecodedFrame`, delegate `AVCVideoStreamDelegate`), `AVCRemoteVideoClient` (`initWithStreamToken:delegate:`, `setVideoLayer:forMode:`, `remoteVideoAttributes`, `hasReceivedFirstFrame`). The Swift spike (`Experiments/videostream/spike.swift`) proved `DeviceManager.shared`/`allDevices()`/`listUsageAssertions()` work from our process through `@_silgen_name` shims, but `MediaStreamSupport.supportInfo` crashes inside `ActionDeclaration.forward(to:)`, so the ObjC route above is the one to pursue.

## Breakthrough: the ObjC path avoids the CoreDevice Swift client (2026-09-07 night)

The private frameworks ship no `.swiftinterface`, so Apple's Swift client (`CoreDeviceMediaStreamSupport`) can only be reached through hand-written `@_silgen_name` shims. Those crash: `MediaStreamSupport.supportInfo` faults inside `ActionDeclaration.forward(to:)` reading an uninitialised registry, because a bare process lacks the DeviceKit client bootstrap (a `CoreDeviceServiceConnection` existential plus a `DeviceManager` check-in lifecycle, `waitForPostPluginLoadCheckIn`). Reconstructing that through shims is the brittle sprawl AGENTS.md rule 2 forbids, so that route is abandoned.

The negotiation is actually done by **AVConference** (`/System/Library/PrivateFrameworks/AVConference.framework`, the FaceTime media stack), which is plain ObjC and standalone — it needs no CoreDevice client. That gives a robust architecture:

1. `AVCMediaStreamNegotiator initWithMode:options:error:` then `createOffer` / `offer`. Verified: modes 1, 2, 4 initialise (0 and 3 fail with GKVoiceChat 32032); `createOffer` returns a 432–543 byte `bplist00` offer. `Experiments/tools/avc_negotiator_probe.m`.
2. Open the `startmediastream` service socket and send the `mediastreamstart` action envelope with `negotiatorOffer` = that offer (raw XPC, no Swift). `Experiments/videostream/neg_start.m`.
3. Device replies with `negotiatorAnswer`; `AVCMediaStreamNegotiator setAnswer:withError:` then `generateMediaStreamConfigurationWithError:` yields an `AVCMediaStreamConfig` (local/remote `AVCNetworkAddress`, SRTP/SRTCP cipher suites, send/receive keys, SSRCs, RTCP).
4. `AVCVideoStream initWithLocalEndpoint:options:error:` / `configure:error:` / `start`; its delegate (`AVCVideoStreamDelegate`, `vcMediaStream:didGetLastDecodedFrame:`) receives decoded frames; `requestLastDecodedFrame` pulls one.

Current state: with a real offer the device gets past format validation to **transport setup**, failing with `NSPOSIXErrorDomain 49` (EADDRNOTAVAIL) for every working mode. So the offer format is accepted; what remains is the RTP endpoint exchange — the offer must carry the host's actual bound RTP socket address (on the CoreDevice tunnel, host `utun` `fdd2:…::2`, device `fdd2:…::1`), which means creating the local `AVCVideoStream`/endpoint first so its address goes into the offer, rather than passing placeholder `receiverIP`/`senderIP`. The screenshot loop is not an alternative: `devicectl` screenshot is ~1.4 s/frame (0.7 fps), and pymobiledevice3 offers only single-frame capture.

## Transport boundary (2026-09-07 night, definitive)

The offer is understood end to end. `Experiments/tools/avc_offer_dump.m`: the negotiator offer is a `bplist00` of `{avcMediaStreamNegotiatorMediaBlob (zlib), avcMediaStreamNegotiatorMode, avcMediaStreamOptionRemoteEndpointInfo (protobuf host identity: model "Mac17,9", avc "2205.3.1", build "25F80"), avcMediaStreamOptionCallID}`. The media blob inflates (zlib) to a 352-byte protobuf codec description: encoder "Viceroy 1.7.0", H.264 settings `FLS;MS:-1;LF:-1;LTR;CABAC;POS:0;EOD:1;HTS:2;RR:3`, and a ladder of bitrate/resolution tiers. No transport address is in the offer.

The transport is the wall. `AVCMediaStreamConfig` carries `rtpNWConnectionClientID` / `rtcpNWConnectionClientID`: the RTP/RTCP flow over **Network.framework `nw_connection`s that CoreDevice's tunnel manager (`remoted`) establishes**, referenced by client id in the start options, not over raw UDP that a client opens. Proof: the `mediastreamstart` `receiverIP`/`senderIP` are the control-tunnel ULA addresses devicectl reports (`fdd2:…::2` host, `::1` device), but that address is not bindable by any user process (`bind` → EADDRNOTAVAIL, code 49) and the `utun` carrying it is torn down and recreated between calls (`if_nametoindex` returns 0 seconds later). The device answers `mediastreamstart` with the same POSIX 49 for exactly this reason: neither side can bind the control-tunnel address for RTP; the real client never tries — it hands the daemon `nw_connection` client ids it got from the tunnel manager.

So there is no raw-socket route to the frames. The mirror is only reachable through **Apple's own media client** (`CoreDeviceMediaStreamSupport` / DeviceKit's `AVConferenceVideoStreamHelper`), which drives the tunnel manager to create those connections, runs the AVConference negotiation and SRTP, and decodes H.264 into a `CALayer`. That client, in turn, needs the full CoreDevice client bootstrap (a connected `CoreDeviceServiceConnection`, a `DeviceManager` check-in, `waitForPostPluginLoadCheckIn`) — which a bare process lacks, causing the earlier `ActionDeclaration.forward` crash.

### Conclusion and options

A fully hand-written H.264 receiver is not feasible: it would have to reproduce CoreDevice's tunnel-managed `nw_connection` transport and AVConference's SRTP negotiation. The two realistic paths, both larger than the HID work:

1. **Drive Apple's client (recommended for a real mirror).** Link `DeviceKit.framework` and use `AVConferenceVideoStreamHelper(device:clientSessionID:)` + `DisplayViewFramebufferAVC`, or `CoreDeviceMediaStreamSupport.MediaStreamSession`, after building the CoreDevice client bootstrap the way DeviceKit does. Stable across seeds because it uses Apple's supported classes rather than hand-shimmed ABI; the effort is the bootstrap, not the media. Frames arrive decoded in a `CALayer`; read them with `requestLastDecodedFrame` / `receivedLastDecodedFrame(Data)`.
2. **Ship a self-owned frame feed instead of the H.264 mirror.** No mirror transport at all: hold the `capturescreenshot` path open and serve frames for an agent loop. Fully ours and seed-robust, but bounded by screenshot latency (`devicectl` is ~1.4 s/frame today; a persistent socket + JPEG needs measuring), so a few fps at best, not a live mirror.

What is done and reusable regardless: the control channel (`stream-info`, `stream-status`, `stream-stop` are shippable now over raw XPC), the offer generation, and this transport map.

## Standalone Apple-client blocker: root cause (2026-09-07 night, definitive)

Driving Apple's own media client from our process was pursued because the RTP transport (above) can only be built by Apple's client. It is now root-caused, not merely observed.

**Crash is a missing client bootstrap, not an ABI mismatch.** Symbolicating the spike crash (`spike3-2026-09-07-215613.ips`) gives the full async chain, in order:
`MediaStreamSupport.supportInfo.getter` -> `CoreDevice.MediaStreamFunctions.mediaStreamSupportInfo.getter` -> `(extension) CoreDeviceUtilities.ActionDeclaration.forward<Input==()>(to:reportingProgressUsing:)` -> `OSAllocatedUnfairLock.read()` -> `ManagedBuffer.headerAddress` -> `EXC_BAD_ACCESS` reading `0x00f0000000008068` (`esr 0x92000004`, translation fault). The async call convention is honoured: execution runs on a real Swift concurrency task and reaches deep inside Apple code before faulting. The fault is a lock read through an object a bare process never initialised. Disassembling the getter confirms it is a genuine async getter (`...ResponseVvg` plus its `...ResponseVvgTu` async function pointer); declaring it `async throws` in the shim is correct.

**`DeviceManager.shared` is not the bootstrapped manager.** The only Apple entry that hands out a fully wired `CoreDevice.DeviceManager` is `DeviceKit.DeviceKitContext` (`deviceManager.getter : CoreDevice.DeviceManager`, `serviceConnection.getter : CoreDevice.CoreDeviceServiceConnection`). DeviceKit is the *only* binary in Xcode 27 b6 that links `CoreDeviceMediaStreamSupport`; Device Hub reaches the media stack through it.

**`DeviceKitContext.current` does resolve standalone.** A probe (`scratchpad/dkctx/probe.swift`) loads DeviceKit, reads DeviceKitContext metadata (runtime size 48 bytes = an 8-byte `deviceManager` class ref plus a 40-byte `serviceConnection` existential), and calls the static `current.getter` without trapping; it returns a struct whose first word is a live pointer. So path A is *not* categorically impossible.

**But every step past that needs another hand ABI shim into non-`.swiftinterface` private Swift types** (DeviceKitContext layout, DeviceManager, MediaStreamSession, VideoStreamConfiguration, VideoStreamEvent, the CALayer decode). A second probe that only tried to read the context's manager pointer and compare it to `DeviceManager.shared` already SIGBUSed on raw pointer inspection. This is exactly the fragility AGENTS.md rule 2 forbids in shipping code, and the stop condition the two independent gpt-6-astra reviews set: *if progress requires continuously adding Swift type-layout / generic / async-ABI guesses, stop this product path and keep the helper as a protocol oracle.* We are at that condition.

**Net:** a self-owned, smooth real-time mirror has no path that is both stable and shippable. Reconstructing Apple's private Swift client stack by hand is research-grade and breaks on every Xcode beta (rule 2); injecting into Device Hub ties the product to Xcode.app plus a code-injection step and an unproven headless mirror start. The frame source that ships without the private stack is a screenshot feed, which is not a 15 fps mirror. Which trade-off to accept is a product decision recorded for the user, not one to keep patching toward.

## Design

## Design

## Design

Two deliverables, in order.

**A. Spike (evidence, throwaway):** a separate Swift/ObjC experiment under `Experiments/videostream/` that loads `CoreDeviceMediaStreamSupport` and drives `MediaStreamSession` for the primary display into an offscreen `CALayer`, logs every `VideoStreamEvent`, and measures time-to-first-frame and steady frame interval. It answers: does the client work outside Device Hub; what `receivedLastDecodedFrame` carries (encoding, size); how to read pixels (layer render vs. decoded-frame data); what stops the stream. ABI shims are allowed here because it is an oracle, not the product (AGENTS.md rule 2).

**B. Product command `ipb stream`:** a long-lived helper process (`ipb-video`) that keeps one session open and serves frames on demand: `ipb stream --frames DIR --fps N` writes JPEG/PNG frames; `ipb stream --mjpeg PORT` serves an MJPEG stream for agents and browsers; `ipb stream --file out.mp4` (VideoToolbox re-encode) comes last. Frame contract: every frame carries a monotonic index, capture timestamp, size, and orientation, so an agent can bind an action to the frame it looked at. The command exits non-zero when the device stops the stream (sensor activity, lock, disconnect) and never restarts silently.

Host requirement stays macOS with the CoreDevice package; stage 4 (no Xcode, non-Mac hosts) cannot reuse AVConference, so its "video" is a screenshot loop over `dtscreencaptured` until something better appears.

## Acceptance

- First frame within 3 s of `ipb stream` on the verified matrix; steady state at least 15 fps at the device's native size on the 13 Pro and 12 mini.
- A frame captured after `ipb tap` shows the tap's effect within two frames.
- Locking the phone or opening the camera ends the stream with a distinct exit code and message.
- The smoke gate gains a `stream` step that checks first-frame latency and frame count over 5 s.

## Open items

- Confirm the control exchange from a real Device Hub session (host `log stream` capture on <macos27-host>; CoreDevice logging profile if fields are redacted).
- ~~Why `ActionDeclaration.forward(to:)` crashes for our `RemoteDevice` objects~~ ANSWERED: missing full-client bootstrap; `DeviceManager.shared` lacks the coordinator whose `OSAllocatedUnfairLock` `forward(to:)` reads. See "Standalone Apple-client blocker" above.
- Which address the device rejects with POSIX 49 (check `dtremotedisplayd` in the device syslog while sending a start request).
- Building a real `negotiatorOffer` with `AVCMediaStreamNegotiator` from ObjC and the answer/`streamConfig` handling that follows.
- Format of `receivedLastDecodedFrame(Data)` / `stream:didGetLastDecodedFrame:`.
- Whether `receiveVirtualExternal` (a second virtual display) is useful for agents that must not disturb the phone's own screen.

## Rejected alternatives

- Own RTP/SRTP receiver: needs AVConference's proprietary negotiator; not feasible.
- `devicectl capture screen-record`: capability absent on every tested device.
- Screenshotting Device Hub's window: operates the Mac, not the device; loses frame identity.
