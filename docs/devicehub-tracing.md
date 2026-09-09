# Observing Device Hub: methodology and harness

Device Hub is the reference client. Every capability this project does not yet
have — the ones we cannot derive from disassembly alone — is answered by
watching what Device Hub actually sends. This document is the method for doing
that, and `Experiments/devicehub-trace/` is the tooling that implements it.

It exists because the ad-hoc alternative was measurably bad. Eight capture
rounds against Device Hub, each one a hand-written `.lldb` file of blind
`continue` commands in `/tmp`, produced two usable byte dumps, wedged Device Hub
badly enough to need a manual restart, and cost the operator a scripted phone
sequence every round. The failures were not bad luck; they were the same
structural defects repeating because nothing was ever kept.

## The constraints, measured

Every number below comes from a throwaway target
(`hid_send` in a loop, 2000 iterations), not from Device Hub, so the harness
could be validated without spending an operator round.

| Property | Measurement |
| --- | --- |
| Cost of one breakpoint hit | **4.7 ms** |
| Cost of a no-op callback | 4.73 ms |
| Cost of reading 4 registers | 4.72 ms |
| Cost of 4 registers + 2 `ReadMemory` calls | 4.75 ms |
| Saturation | **~210 hits/s** |

The cost is **entirely** the stop/resume round-trip. Capturing the payload is
free. Two things follow, and they invert how the earlier rounds were run:

1. **Always capture the full payload.** Earlier scripts recorded only `x0..x3`
   and a backtrace "to keep it cheap". That saved nothing and discarded the
   only data we actually needed — the report bytes.
2. **Hit count is the only thing to budget.** A tap on a path Device Hub drives
   continuously (it emits `AbsolutePointer` reports at pointer-move rate) will
   consume the whole round-trip budget and stop the application redrawing.
   That is exactly how Device Hub was wedged.

### `--skip-prologue false` is mandatory

`breakpoint set -n <symbol>` binds **after** the prologue. On the test function
it bound at `+32`, past:

```
<+12>: str  x8, [sp, #0x8]
<+16>: mov  x8, x0
```

By that point the argument registers have been overwritten. Every argument
register read in the earlier Device Hub captures was taken at such a point, so
those values were not trustworthy — a silent defect that produced confident
readings of clobbered registers. Every tap in the manifest binds with
`--skip-prologue false`.

## The design

`Experiments/devicehub-trace/` is four pieces:

| File | Role |
| --- | --- |
| `dhtrace.py` | The lldb tracer: one JSON record per hit, then auto-continue |
| `dhrun.py` | Bounded run control: async continue, wall-clock deadline, clean detach |
| `taps.tsv` | The tap manifest — symbol, module, and what to capture |
| `decode.py` | Capture JSONL → per-action report table |
| `actions/*.tsv` | Action scripts that drive the operator |

Three properties are structural rather than a matter of care:

**Device Hub is never left stopped.** Callbacks return `False`, so the target
resumes immediately, and a tap that exceeds its hits/sec budget calls
`SetEnabled(False)` on itself and records that it did. Shedding a noisy tap
loses one signal; freezing Device Hub costs the operator a restart and the whole
capture window. Verified: a tap shed itself at 183.9 hits/s after 184 hits.

**Runs are bounded and the target survives.** lldb's synchronous `continue`
never returns when every callback auto-continues, which is why an earlier script
parked forever. `dhrun` switches to async mode, resumes, waits out the clock,
then stops and detaches. Verified against a live process: it detaches cleanly
and the target keeps running.

**Captures are self-describing, and steps come in two kinds.** The action
script drives the operator, and the driver appends a marker to the same JSONL
stream the tracer writes, so every report lands inside a labelled window and
nobody has to remember afterwards what they did in which order.

The two kinds exist because two constraints pull against each other:

- `!<prompt>` — **setup**. Waits for ENTER, untimed, not traced. For steps that
  take as long as they take: unlocking the phone, typing a passcode, getting an
  app on screen. A first version timed these and cut the operator off mid-step.
- `<seconds><TAB><prompt>` — a **traced window**. Timed, with a live countdown,
  and the operator must not touch the terminal during it. A second version made
  every step ENTER-gated, which produced steps that were impossible to perform:
  pressing ENTER moves focus and the pointer to the terminal, and "leave the
  pointer resting on the list, then press ENTER" contradicts itself. Anything
  that depends on pointer position or window focus has to be timed.

Because step durations are unknown in advance, the run ends when the operator
finishes or when a wall-clock backstop expires, whichever comes first. The
backstop exists so an abandoned session still detaches; the repo forbids
unbounded waits.

Markers are written by the driver shell and records by lldb — two processes, one
file — so records carry absolute wall-clock `ts` alongside monotonic `t`, and
`decode.py` sorts on `ts`.

## Running a capture

```sh
# Device Hub must already be open and connected to the phone.
Experiments/devicehub-trace/dhtrace.sh \
    Experiments/devicehub-trace/actions/lock-and-scroll.tsv \
    /tmp/capture.jsonl

Experiments/devicehub-trace/decode.py /tmp/capture.jsonl --bytes
```

Setup steps wait for ENTER; take as long as they need. Timed steps print a
countdown and must be performed without touching the terminal. Idle steps are
part of the measurement: they establish the background report rate that every
other window is compared against.

## Reading a capture

`decode.py` groups records by the action that preceded them and names each
report by its ID. A window that shows only the background rate means the action
produced nothing on the tapped paths — which is a result, not a failed run, and
is what distinguishes "we did not capture it" from "Device Hub did not send it".

`!!` lines report taps that shed themselves and tap errors. A shed tap
invalidates any negative conclusion drawn from that window: the report may
simply have arrived while the tap was disabled.

## Rules for conclusions

These are the specific ways the earlier rounds produced wrong answers.

1. **A negative result is only valid if the tap was live and correct for the
   whole window.** Check the `!!` section before concluding "Device Hub does not
   send X". One earlier negative was drawn from five breakpoints on
   `init(_report:)`, which is a reinterpret wrapper and not a construction path
   at all — the test measured an empty set and looked like evidence.
2. **Verify a tap fires at all before trusting that it did not fire.** Include an
   action known to exercise it in the same run.
3. **A/B any on-device claim against a control.** "The screen is black after I
   sent X" is not evidence that X locks the screen; the device auto-locks. Two
   separate conclusions that a usage code locked the phone were wrong for
   exactly this reason. The control is the same run without the action.
4. **Validate lldb syntax on a throwaway target first.** `thread apply all` is
   not valid in this lldb build and was used against Device Hub without being
   tested. A dummy binary costs seconds; an operator round costs minutes and
   goodwill.

## Open questions this harness exists to close

- **Lock / unlock.** Cmd-L reaches `KeyboardFilter.filterEvent` and produces a
  `KeyboardReport` (ID 1), but only the all-zero release reports were ever
  captured. `KeyboardFilter.updateCopyMask(oldValue:newValue:) -> [HIDReport]`
  (UniversalHID `0x5b0bc`) takes two `HIDEventMask` values — an `OptionSet` over
  `UInt`, so plain integers in `x0`/`x1` — and returns the reports directly. It
  is the tap most likely to show the press.
- **Scroll.** Reports are accepted at every layer and the device does not
  scroll. `boundaryScroll` exists as a distinct `HIDEventType` (`0x1c`) beside
  `scroll` (`0x6`), and Device Hub sends `AbsolutePointer` (ID 19) continuously
  while we never send it at all. The capture is meant to show which of those
  Device Hub actually emits during a trackpad scroll.
