@AGENTS.md

Claude-specific notes:

- Follow `AGENTS.md` in this directory; it overrides the machine-wide guidance where they conflict.
- Run device commands through `bin/hdb` and `scripts/smoke_matrix.sh`, never by hand-assembling helper invocations, so exit codes and logs stay comparable with the recorded verification runs.
- When a verification run is part of the task, append the record to `docs/verification.md` in the same change.
- Protocol facts require a cited source (Apple metadata, runtime capture, or disassembly) before they are written into code or `docs/protocol.md`.
