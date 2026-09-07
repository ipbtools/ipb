# Standalone distribution (adb-style) plan

Goal: ship device control (tap, swipe, keys, home, recents, screenshot) without requiring Xcode.app on the host, ideally as a single tool a tester can install like `adb`.

## What the device side needs

- The HID daemon `dtuhidd` lives in the iOS DDI that ships with Xcode 27 beta (CoreDevice 642.x). On iOS 27 the device fetches this DDI itself as a `com.apple.MobileAsset.DDI` cryptex once a host asks for developer services; the iPhone 13 Pro on this macOS 26 host had the 642.15 image mounted at `/System/Developer` without any manual mount.
- `dtuhidd` exposes three RemoteXPC services (`com.apple.coredevice.hid.universalhidservice`, `...universalhid`, `...indigo`). The wire format is plain XPC dictionaries; see `protocol.md`, "Wire Format".

## Host-side options

| Option | Runtime dependencies | Verified | Notes |
| --- | --- | --- | --- |
| A. Current helper (typed CoreDevice calls) | XcodeSystemResources.pkg (CoreDevice 642.x, 138 MB), MobileDevice.pkg (Mercury, 15 MB), OS RemoteXPC. No Xcode.app needed at runtime: `devicectl` ships inside the CoreDevice package. | macOS 27 b8 + 12 mini, macOS 26.5.1 + 13 Pro | Still binds ~110 private Swift symbols; breaks when Apple changes the ABI. The two packages are Apple-signed installers extracted from an Xcode xip, so "distribution" means an installer script, not a redistributable bundle. |
| B. Raw-XPC helper (C only) | Same two packages for `CoreDeviceService` (tunnel, pairing, DDI), but no Swift ABI shims: the helper builds the dictionaries from `protocol.md` itself and links only libxpc/RemoteXPC plus the two C registration calls in CoreDevice. | Wire format captured; not yet reimplemented | Survives CoreDevice minor updates as long as the dictionary shapes hold. Recommended next step for the helper regardless of distribution. |
| C. pymobiledevice3 client (Python) | None from Apple beyond the OS. `UserspaceRsdTunnel` creates the tunnel without root or extra daemons; `mounter auto-mount` handles the DDI if the device has not fetched it; RemoteXPC is implemented in Python. Cross-platform in principle. | `connectedServices` answered and a digitizer tap delivered (App Library search field opened) over a userspace tunnel with no CoreDevice involvement, 2026-09-07, iPhone 13 Pro iOS 27.0 | This is the adb-like path: `pip install` plus the device pairing prompt. Screenshot needs a different service (`dtscreencaptured` / `com.apple.coredevice.feature.viewdevicescreen`, not yet mapped). |

## Recommendation

1. Keep the current helper as the reference implementation and oracle (it can print exactly what Apple's client sends).
2. Build option C as `devicehubctl-py` (or a subcommand set) using pymobiledevice3: tunnel, `connectedServices`, `send`/`resetGestureState`/barrier, Indigo button and digitizer events. Add screenshot once the `dtscreencaptured` protocol is captured with the same interposer.
3. Fold option B into the C helper only if a macOS-native binary without Python is required.

## Open items

- Barrier over pymobiledevice3: `{isBarrier: true}` sent with `wanting_reply` did not get a reply within 5 s in the first attempt; the reports themselves are one-way and were delivered. Needs a look at how CoreDevice tags the barrier message on the wire (message id / flags).
- Screenshot protocol for `dtscreencaptured`.
- Pairing UX: pymobiledevice3 autopair shows the Trust prompt on the phone; document it.
- Entitlement `com.apple.private.CoreDevice.hid` is declared on the device service but was not enforced against the Python client.

## Rejected alternatives

- Copying only the DDI `.dmg` files or frameworks onto a host: the device fetches its own DDI on iOS 27, and the host frameworks are only needed for option A/B.
- Reviving the old `services-async` raw ABI experiment: known local ABI crash, superseded by the wire-format capture.
