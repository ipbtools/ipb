# Experiments

Evidence-gathering tools. Nothing here ships; AGENTS.md rule 2 allows Swift ABI shims only in this directory.

- `probe/feature_probe.m`: asks CoreDeviceService for a service socket for a feature (`createservicesocket`), optionally sends one JSON-described XPC message over it (`PROBE_SEND_JSON`, with `u64:`/`i64:`/`hex:` typed values) and prints the reply. Also runs arbitrary host actions (`PROBE_ACTION`, `PROBE_NO_FEATURE`). Build: `clang -fobjc-arc -framework Foundation -F/Library/Developer/PrivateFrameworks -F/System/Library/PrivateFrameworks -framework CoreDevice -framework RemoteXPC feature_probe.m -o feature_probe`.
- `tools/rxpc_tap.c`: `DYLD_INSERT_LIBRARIES` interposer that logs every RemoteXPC send/reply/event of an unsigned process; this is how the HID wire format in `docs/protocol.md` was captured.
- `tools/fieldmd.py`: dumps Swift field descriptors (enum cases, struct fields, coding keys) from a Mach-O.
- `tools/dumpavc.m`: prints ObjC method lists and protocols of AVConference classes via the runtime.
- `tools/symcrash.py`: symbolicates a `.ips` crash report against the private frameworks by nearest exported symbol.
- `videostream/spike.swift`: stage-1/2 spike driving CoreDevice's `DeviceManager` and `CoreDeviceMediaStreamSupport` from our process with `@_silgen_name` shims; `listUsageAssertions` works, `supportInfo` crashes inside Apple's in-process action forwarder (see `docs/video-stream.md`).
