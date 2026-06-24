# Verification Notes

Host:

- macOS 27 beta
- Xcode 27.0.0 Beta 2

Device:

- iPhone 13 Pro
- iOS 27.0
- Device identifier used during extraction: `<device-uuid>`

Commands verified:

```sh
bin/devicehubctl tap 0.5 0.5
bin/devicehubctl long 0.615 0.675 1.2
bin/devicehubctl scroll 0.5 0.75 0 0.30
bin/devicehubctl swipe 0.5 0.75 0.5 0.35
bin/devicehubctl home
bin/devicehubctl recents
```

The original investigation also captured screenshots after each command, but those are intentionally not committed to keep the repository small and reviewable.
