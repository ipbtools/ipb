# MCP host bridge

> Status: implemented, device-unverified. M1 only; Python 3.11+ and a POSIX host.
> No Runner, XCTest, device app, persistent DTX connection or network listener.

The supported ipb host/device matrix is unchanged; this is not new Linux/Windows support.

## 1. Purpose and starting the server

The MCP bridge invokes an existing ipb executable once per tool call. It does not import
the AX implementation or change ordinary schema 1, native deep schema 2, CLI exit codes,
the local ipb installation or device selection in the CLI.

Start the server from either a source checkout or an installed package:

```sh
ipb mcp
# Choose Python explicitly if python3 is older than 3.11:
IPB_MCP_PYTHON=/path/to/venv/bin/python ipb mcp
```

The launcher uses the ipb executable from the same installation, never a second copy
from PATH. It chooses `IPB_MCP_PYTHON`, then `IPB_AX_PYTHON`, then `python3`. Configure
your MCP client with the absolute ipb path as `command` and `["mcp"]` as `args`. For
development, `python3 Sources/ipb_mcp.py --cli /absolute/path/to/ipb` remains available;
`--cli` is an executable path, not a shell expression. Tools use argv and stdin closed.
All device tools require a **full CoreDevice UUID**; names, UDIDs and UUID prefixes are
rejected before spawning. `devices` returns the six-column TSV from the existing CLI
as named JSON fields. Enumeration does not choose a device or establish availability.
Pass the UUID as observed: its spelling is preserved for the legacy CLI's exact metadata
comparison, while the lock key is normalized so case variants still share a lock.
`launch` retains the CLI's `--terminate-existing --activate` behavior.

The lock/state root defaults to `$XDG_STATE_HOME/ipb/mcp`, or `~/.local/state/ipb/mcp`.
Every MCP client/check-out controlling the same device must use the same canonical root;
`--state-dir` overrides it. No installer, service or phone dependency is added here.
See the [implementation plan](mcp-agent-experience.md), [UI contracts](ui.md) and
[frozen error example](contracts/ipb-error-v1.example.json).

## 2. Protocol and tools

Only MCP revision **2025-11-25** is implemented. The server returns that revision during
version negotiation; clients that cannot use it must disconnect. The bounded subset is
`initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call` and
`notifications/cancelled`. Unsupported request methods return `-32601`; invalid tool
names/arguments return `-32602`. Notifications receive no JSON-RPC response. A cancelled
call also receives no response, while cleanup and persistent isolation still complete.
No tasks, resources, prompts, subscriptions, pagination, batch requests or HTTP are exposed.

The implementation follows the pinned official
[stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) and
[cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)
specifications. stdin/stdout contain UTF-8 NDJSON only. Diagnostics use stderr and do not
echo native stderr, cancellation reasons, selectors, text, environments or command lines.

| Tool | Additional arguments / behavior |
| --- | --- |
| `devices` | No arguments; enumerate physical-device metadata |
| `observe` | Optional positive `pid`; fresh `ui --deep --json`, native-only compact tree |
| `locate` | At least one exact selector; optional `pid` |
| `wait` | Exact selectors, optional `pid`, `waitFor=present/absent`, `timeout` in (0,15] seconds |
| `press` | Exact selectors, optional `pid`; one guarded native action |
| `input` | Exact selectors, optional `pid`, nonempty `text`, explicit `replaceAll=true` |
| `scroll_to_visible` | Exact selectors, optional `pid`; one action on an already materialized target |
| `alert_press` | Required `pid`, exact `alertLabel` and button `label` |
| `home` | One Home action |
| `launch` | One `bundleId`, no arbitrary process arguments |
| `tap` | Normalized `x`,`y` in 0..1 |
| `swipe` | Normalized `x1`,`y1`,`x2`,`y2`; optional `duration` in (0,2] seconds (default 0.3) |

Exact selectors are `identifier`, `label`, string `value` and native `className`, combined
conjunctively. Their maximum length is 1024 characters; replacement text is bounded to
4096 characters. Snapshot-local `n…` IDs are never accepted as action tokens. There is
no bare text tool, coordinate/OCR fallback, automatic alert approval or automatic replay.
The tool list publishes the complete argument schemas; unknown fields are rejected.

Each input frame is at most 65536 bytes, with at most 16 active calls (including lock
waiters). The normal CLI/lock budget is 60 seconds; cancellation has a separate 22-second
grace for the backend's up-to-18.5-second cleanup, then at most one second of direct-child
reaping. stdout is bounded to 2 MiB and stderr to 64 KiB per CLI. Output has a 16-frame
queue, an 8 MiB/frame ceiling and a five-second blocked-writer budget; a stalled client
causes shutdown/cleanup. Output/parse limits fail without replay.

## 3. Results, cancellation and isolation

Each tool result is one MCP text content item containing a JSON **MCP envelope**:
`kind=ipb.mcp.result`, `envelopeVersion=1`, `tool`, `deviceIdentifier`, `ok`,
`cliExitCode`, `error`, `phase`, `action`, `retrySafe`, `businessVerified`, `result`,
`receipt` and `isolation`. `isError` reflects command/adapter failure. `ok` means only
that the command and its required result format completed; `businessVerified` remains
`unknown`. Native acceptance, child exit zero, value readback and modal disappearance keep
their original meanings inside `result`, without becoming application business success.

Actions preserve `not-sent`, `submitted`, `accepted`, `refused`, `child-exited-zero/nonzero`,
`native-true/false` or `unknown`, plus native BOOL/unknown and child exit code/null. Only an
exact `ipb.error`/integer version 1 with matching operation/exit code is consumed as a new
receipt. The bridge requests `IPB_ERROR_FORMAT=json`; v0.5.0 ignores that opt-in. Absent or
unsupported receipts still preserve complete stdout JSON. In particular, a receipt-free
AX failure (even exit 1/5) is unknown rather than proof of a normal Python return. Legacy
HID setup/socket/tunnel codes 2/3/4 retain their family-specific pre-send mapping; devicectl
launch remains unknown without a phase receipt. Signals, interrupted collection and
malformed expected JSON never establish `not-sent`. stderr text is never phase evidence.

`observe.result` has its own `kind=ipb.mcp.observation`, `version=1` and
`sourceSchemaVersion=2`. It projects the complete native tree and application/snapshot
identity, frame units, original child edges, labels/identifiers/values, native class
metadata, false visibility, unavailable frames and explicit `atomic=false`. It removes
transport metadata and redundant per-node source/depth fields. It does not synthesize
missing fields, containers, hittable state or XCTest types. It requires a complete matching
native deep graph and successful cleanup. A nonzero retained native result stays in its
original form and cannot clear isolation.

All device reads/writes acquire an in-server UUID lock and a cross-server flock. The server
owns the lock FD; CLI children do not inherit it, so input's nested `text` cannot deadlock
on a second MCP lock. **Manual CLI/mirror and different state roots are outside this lock.**
Enumeration is global/read-only and uses a separate `inventory` lock/intent, without
acquiring a device lock. An unfinished inventory intent blocks further enumeration for
operator investigation, without changing any selected device's state.

Before spawning, the server fsyncs an operation intent. It then records the PID, process
group, start identity and unique inherited marker, without argv or text. Ownership uses
host process metadata and an in-memory marker check, including detached nested sessions;
unrelated processes are never signalled. If ownership preflight is unavailable, no CLI is
spawned. PID reuse is checked before signalling. A narrowly bounded final pipe drain avoids
mistaking ordinary EOF scheduling for a surviving child.

Cancellation is an event, not repeated `Task.cancel()` calls. It sends one SIGTERM round
to proven request processes, leaving the backend its cleanup grace. A second notification
does not interrupt cleanup. If the outer group is still alive it owns cleanup of input's
separate session; if the outer CLI exited, only proven surviving request processes are
signalled. After grace, SIGKILL never counts as evidence of completed remote cleanup.

| Persistent state | Following requests and recovery |
| --- | --- |
| No isolation | Device requests may run under the lock |
| `observeRequired` | Modification blocked; only a successful complete matching fresh `observe`, after confirmed process reaping, clears it |
| `orphanPossible` | **All device requests blocked in M1**, including observe; no timer, server restart, new CLI success or observation clears it |
| Unfinished intent on server restart | Becomes `orphanPossible` before any next device CLI spawn |

This M1 restriction avoids starting another native observation while an unknown orphan may
still own the connection. No unlock tool is exposed. Recovery from `orphanPossible` requires
operator investigation/termination evidence outside MCP. Keep the state record for that
investigation; deleting it or selecting another root discards the protection. Device reads
in `observeRequired` do not restore modifications unless a complete new observe succeeds.

## 4. Host verification and remaining acceptance

Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_mcp.py`. The test executable, CLI output,
device metadata and process identity inspector are fixtures. Lifecycle tests launch real
**fake CLI** processes/sessions and two real stdio servers sharing temporary locks; they
never run ipb/devicectl or access a phone or clipboard. The injectable fixture inspector
uses cooperating fake-process identities because the development sandbox denies `/bin/ps`.
A separate host regression exercises the production inspector with fake CLI processes,
including nested independent sessions and early outer-process exit. It performs no phone operation.

Actual device cleanup duration, input's real nested text process, disconnect/cancel
behavior, native observation latency
and every device-facing tool are **implemented but unverified / pending acceptance**.
Host tests and Python compilation do not satisfy the supported physical smoke matrix.
The install/package includes all three `ipb_mcp*.py` modules, and `make check-host` runs
the maintained host regressions. This branch does not update an existing default install,
publish a release or claim the physical smoke gate passed.
