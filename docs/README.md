# Documentation map

Start with [requirements and installation channels](../README.md#installation-channels),
then [command usage](../README.md#usage) and `ipb doctor`. Commands in a development
branch may be ahead of Homebrew HEAD. Check the running path with `command -v ipb`.

## User guides

| Need | Read |
| --- | --- |
| Install, update, select a device, command overview | [README](../README.md) |
| Read a UI tree, text, frames and state; understand AX/XCTest coverage | [UI guide](ui.md) |
| Mirror controls, keyboard/IME/clipboard, geometry and errors | [Mirror guide](mirror.md) |
| Stream media and its implementation plan | [README stream usage](../README.md#live-screen-stream-ipb-stream), [video plan](video-stream.md) |

## Current implementation and open work

| Question | Source of truth |
| --- | --- |
| What is implemented and why? | [Device Hub alignment plan](devicehub-alignment.md) |
| What is proven, still open, or awaiting a device/host? | [Verification: living current state](verification.md#open-items--current-state-living-section) |
| What bytes/IDs does the client send? | [Protocol: captured Wire Format](protocol.md#wire-format-captured-2026-09-07), then the feature-specific sections |
| How should Device Hub behavior be captured? | [Tracing procedure](devicehub-tracing.md) |
| How would the tool ship without Xcode? | [Standalone distribution plan](standalone-distribution.md) |

## Evidence and earlier research

The dated sections of [verification.md](verification.md) preserve what was observed on
that host, device and seed. They are historical records, not current feature support.
The living section at the top is updated when findings change. Protocol facts keep their
runtime/static sources and seed; old “not reachable” results must be read with later findings.

[Research](research/) contains capability comparisons, peer tools and independent reviews.
Use those for background and follow their references; use the current plan and verification
head for current status. Raw recordings, screenshots and one-off probes stay outside Git.
