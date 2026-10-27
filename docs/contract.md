# ipb interface contract v1

This is the authority for ipb client semantics, not an Apple wire specification.
The frozen starting example is [ipb-error-v1.example.json](contracts/ipb-error-v1.example.json).
The schemas and synthetic host fixtures in [contracts/](contracts/) describe this
contract. Apple protocol evidence remains in [protocol.md](protocol.md).

## Compatibility and coverage

Without `IPB_ERROR_FORMAT=json`, stdout, stderr and exit codes retain their
v0.5.0 behavior. Ordinary dumps and actions use schema 1; native deep dumps use
schema 2. Success output is unchanged even with the opt-in. Snapshot-local IDs
cannot be reused for actions. Missing AX fields stay missing; null/unknown is
never a false value, a fabricated hittable property or an XCTest type.

The first implementation covers errors handled by the Python AX entry point,
including its argument and dependency checks. zsh selection/setup errors, native
HID helpers, devicectl verbs, stream/mirror and raw `text` do **not** promise a v1
error object. Consumers must accept a nonzero exit with no receipt and use
`unknown`, never infer submission from free-form stderr or a global exit code.
An external signal, abnormal termination, malformed/missing JSON or an unsupported
contract version cannot prove `not-sent`.

## Exit codes and original results

| Family | Code | Meaning and retained result |
|---|---:|---|
| AX reads (`ui`, deep, hit-test, locate, wait) | 0 | Complete validated result; no UI action sent |
| Python AX | 2 | Usage, interpreter or pinned dependency failure |
| zsh AX preparation | 3 | Selection or UUID-to-USB resolution failure; outside Python receipt coverage |
| AX reads / actions before submission | 1 | Tunnel, graph/protocol validation or cleanup failure |
| AX reads / actions before submission | 5 | Timeout or handled cancellation |
| `ui wait` | 5 | Its deadline expired: retain the last complete observation, possibly `snapshotId=null` if none completed; empty matches then do not establish absence |
| deep `--full-state` | 1 or 5 | Requested supplemental AX failed: retain the complete validated native schema 2 result after successful cleanup; supplemental failure does not invalidate or replace its native tree |
| press/input/scroll-to-visible/alert-press | 6 | Any failure after submission, including refusal, postcondition failure or cleanup failure; do not replay |
| native HID helper | 0/1/2/3/4/5 | Helper success / dispatched failure / usage / refused service socket / tunnel down / watchdog; these codes are not AX submission receipts |
| devicectl verbs | native | Apple command exit code, not an ipb UI-effect guarantee |
| raw `text` | 1 on copy failure; paste helper code otherwise | Copy and paste are separate stages. Copy failure sends no paste; later failure may leave clipboard changed and input partially delivered. No v1 receipt in B1 |

The wrapper may warm a tunnel once after helper code 4, before an action has
been sent. It never retries a submitted action. Stream/mirror have separate
exit codes documented in their guides; do not map them through the AX table.

## Opt-in error envelope

On a handled nonzero Python return, stdout contains **one JSON document**, with
`kind="ipb.error"` and `contractVersion=1`, independently of `--json`. The exit
code stays nonzero. There is no second native JSON document. A complete result
that the old path would have emitted moves, unmodified, into `result`; otherwise
`result=null`. No partial graph is invented. Human stderr diagnostics may remain
and are not a machine contract. stdout on exit 0 remains the original output.

| Field | Meaning |
|---|---|
| `operation` | `ui.dump`, `ui.hit-test`, `ui.locate`, `ui.wait`, `ui.press`, `ui.input`, `ui.scroll-to-visible`, `ui.alert-press`; `unknown` if parsing did not identify one |
| `phase` | Known control-flow stage: `validation`, `dependency`, `query`, `submission`, `postcondition`, `supplemental`; otherwise `unknown`. It is not guessed from exception text |
| `exitCode` | Actual handled nonzero Python exit code (1, 2, 5 or 6) |
| `error.type`, `error.message` | Exception class/message, or an explicit result-failure description; no success implication |
| `action` | `null` for reads, otherwise the object below |
| `retrySafe` | True only for a read or a provable `not-sent` action; does not authorize bypassing fresh selection/guards, automatic action replay or process-quarantine handling |
| `result` | Complete old native result or null; retains original schema, units and missing fields |

Unknown enums are the literal string `unknown`. The action object has:

- `state`: `not-sent`, `submitted`, `accepted`, `refused`,
  `child-exited-zero`, `child-exited-nonzero`, `native-true`, `native-false`,
  or `unknown`. These retain the existing Python phase vocabulary.
- `native`: boolean for an actual known native true/false reply; `"unknown"`
  otherwise. Press acceptance is not verified UI effect. Scroll native false
  can coexist with a verified visible postcondition; preserve both facts.
- `childExitCode`: exact integer returned by the text child, or null. Zero is
  child completion, not proof of exact input; nonzero can mean partial input.
  Negative/signal-like (>=128) exits retain their numeric value but use state
  `unknown`. No exit-code-only mapping establishes `not-sent`.

Python records `submitted` immediately before attempting the semantic send or
invoking the input child; transport exceptions after that boundary remain
submitted/unknown. `child-unknown` from the old input path maps to `unknown`.
Known result fields (`nativeResult`, `action.nativeAccepted`,
`action.childExitCode`) may recover the corresponding receipt when a complete
result exists. Missing or ill-typed values never supply a success state.
Only normal, handled Python failures use its in-process state; a caller must
not apply that mapping to a killed/crashed CLI.

## Units, timing and cancellation

CLI coordinates are normalized 0..1 from top left. AX frames use device logical
points. Durations and CLI wait deadlines are seconds; `queryMs` and
`postconditionElapsedMs` are milliseconds. `atomic=false` stays explicit.
AX wait accepts (0,15] seconds; setup plus the main operation have a 30 second
watchdog with bounded cleanup afterward. A deadline/handled cancellation before
submission uses 5; after submission it uses 6 without replay. Cleanup failure
does not erase known action state. A receipt alone cannot prove that descendant
processes have been reaped; MCP cancellation/isolation is a separate owner.

## ipb support metadata

`support --json` is independent of `capabilities --json`, which retains its
Apple advertisement output. Support has `kind="ipb.support"`,
`contractVersion=1` and per-operation implementation, advertisement,
prerequisites and verification records. Operation status is `verified`,
`unverified`, `unsupported` or `unknown`, with a reason and scope.

B1 support is a static, host-only implementation inventory. It performs no
device query, does not select a device, reports advertisement `status=unknown`
with null data, and makes no available/verified claim. Unsupported means an
explicitly unimplemented operation, not an advertisement/query failure. A future
query must require an explicit target, retain query failure as `unknown` and
never turn null advertisement into false. A `verified` record must include
host, device, OS, command scope and an evidence reference; a host fixture or a
single page never establishes the complete supported device matrix.

## Maintenance and acceptance

Additive ignorable fields may be added without changing old semantics. Renaming,
removing or reinterpreting a field needs a contract version change. Consumers
recognize v1 only when both kind and version match. The default-output golden is
synthetic, generated from committed baseline `b3c1a63` with fake `run`/dependency
checks; it is a regression fixture, not device evidence. New errors and support
are **implemented but device-unverified** once B1 lands. No new wire claim,
Xcode-free support matrix, RSD screenshot integration or phone acceptance is
established by these host tests.
