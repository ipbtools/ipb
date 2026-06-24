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
bin/devicehubctl screenshot build/smoke.png
bin/devicehubctl service-ids
```

The original investigation also captured screenshots after each command, but those are intentionally not committed to keep the repository small and reviewable.

Additional protocol probe commands now exposed:

```sh
bin/devicehubctl services
bin/devicehubctl reset-gesture 0x101
bin/devicehubctl button 0x0c 0x40
bin/devicehubctl uhid-report 0x101 0.5 0.5 0 0
bin/devicehubctl digitizer-event 0.5 0.5 0 0 1 2 0
```

`services` currently reaches the UniversalHID Mercury peer but does not yet decode `connectedServices` successfully; this is tracked in `docs/protocol.md`.

`service-ids` is host-side and does not require an active device socket. It is verified to return `mainTouchscreen = 0x101`, and that resolved value has been used successfully with:

```sh
service_id=$(bin/devicehubctl service-ids | awk '/^mainTouchscreen/ {print $2}')
UHID_SERVICE_ID="$service_id" bin/devicehubctl uhid-report "$service_id" 0.5 0.5 0 0
UHID_SERVICE_ID="$service_id" bin/devicehubctl reset-gesture
```
