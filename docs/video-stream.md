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
- Why `ActionDeclaration.forward(to:)` crashes for our `RemoteDevice` objects (only if the Swift route is revisited; the ObjC route does not need it).
- Which address the device rejects with POSIX 49 (check `dtremotedisplayd` in the device syslog while sending a start request).
- Building a real `negotiatorOffer` with `AVCMediaStreamNegotiator` from ObjC and the answer/`streamConfig` handling that follows.
- Format of `receivedLastDecodedFrame(Data)` / `stream:didGetLastDecodedFrame:`.
- Whether `receiveVirtualExternal` (a second virtual display) is useful for agents that must not disturb the phone's own screen.

## Rejected alternatives

- Own RTP/SRTP receiver: needs AVConference's proprietary negotiator; not feasible.
- `devicectl capture screen-record`: capability absent on every tested device.
- Screenshotting Device Hub's window: operates the Mac, not the device; loses frame identity.
