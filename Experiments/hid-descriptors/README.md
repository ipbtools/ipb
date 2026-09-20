# HID report descriptors: the authoritative field map

Every `UniversalHID` report type carries a real USB-HID report descriptor, exposed as
`static <T>.descriptor.getter` (22 of them are exported). Apple's own encoder sizes reports from that
same descriptor via `HIDReportDescriptor.reportBitCount(for:)`, so it is the allocation authority on
**both** sides of the wire.

This matters because it replaces reverse-engineering a field at a time. Parsing these descriptors
reproduces every offset this repo previously obtained by capture — Scroll 168 bits, AbsolutePointer
152, Keyboard 312, Digitizer 464 — which is what validates the method.

## Files

| file | what it is |
| --- | --- |
| `dump_descriptors.swift` + `trampoline.S` | dlopen UniversalHID, dlsym each `descriptor.getter`, call it through a 3-instruction trampoline (the getter returns the 16-byte `HIDReportDescriptor` indirectly via `x8`), and print the bytes |
| `parse_descriptor.py` | standard USB-HID report-descriptor parser; per report ID, walks Input items and prints exact bit offsets and sizes |
| `descriptors.txt` | the raw descriptor bytes captured from host UniversalHID 90.1 (CoreDevice 642.15) |

## Use

```sh
python3 parse_descriptor.py descriptors.txt
```

Re-dump `descriptors.txt` when the CoreDevice seed changes; the offsets below are seed-specific and
Rule 1 requires re-verifying them against a new seed rather than assuming they carry over.
