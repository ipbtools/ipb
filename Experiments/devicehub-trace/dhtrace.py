"""
dhtrace — an lldb tracer for Apple's Device Hub.

Loaded inside lldb with `command script import dhtrace`. Every breakpoint hit
appends one JSON record to $DHTRACE_OUT and then AUTO-CONTINUES, so the traced
GUI application is never left stopped.

Measured properties of this design (see docs/devicehub-tracing.md for the runs):

  * A breakpoint hit costs ~4.7 ms, and that cost is entirely the stop/resume
    round-trip. A no-op callback, a callback that reads four registers, and a
    callback that reads four registers plus two blocks of target memory all
    measured within 0.03 ms of each other. Payload capture is therefore free
    and hit count is the only cost variable.
  * ~210 hits/s saturates the round-trip. A GUI application driven at that rate
    stops redrawing, which is how an earlier session wedged Device Hub badly
    enough to need a manual restart.

Both facts drive the governor below: each breakpoint gets a hits/sec budget and
disables itself when it exceeds it. Shedding a noisy tap is recoverable, a
frozen Device Hub costs the human a restart and a lost capture window.
"""

import json
import os
import struct
import time

import lldb

# Per-breakpoint budget. 20/s is ~10% of the measured saturation rate, which
# leaves Device Hub visibly responsive.
BUDGET_HITS_PER_S = float(os.environ.get("DHTRACE_BUDGET", "20"))
BUDGET_WINDOW_S = 1.0

# A HIDReport wraps a Foundation Data value, which is a tagged representation
# rather than a plain object pointer. `HIDReport.reportID.getter`
# (UniversalHID 0x5cae4) begins `lsr x16, x1, #62`, branching on the top two
# bits of the second word:
#
#   tag 0  bytes are inline in the two words; length in word1 bits 48..55
#   other  heap-backed; the storage object carries a bytes pointer at +16 and
#          a length at +24, which is the layout validated earlier against
#          HIDReport.init(bitCount:id:) (x0=0x98 bits, x1=0x13 bytes)
#
# Both are decoded, and anything unrecognised is recorded raw rather than
# guessed at, so a wrong assumption shows up as data instead of as silence.
INLINE_MAX = 14
STORAGE_BYTES_PTR_OFF = 16
STORAGE_LEN_OFF = 24
REPORT_LEN_MAX = 512

# Swift array storage: count at +0x10, elements from +0x20. A HIDReport element
# is two words, so the stride is 16 bytes, not 8 (disassembly of
# KeyboardFilter.updateCopyMask, which writes elements at array+0x20 and
# array+0x30).
ARRAY_COUNT_OFF = 0x10
ARRAY_ELEMS_OFF = 0x20
ARRAY_STRIDE = 16
ARRAY_COUNT_MAX = 64

_out = None
_t0 = time.monotonic()
_seq = 0
_bp_state = {}
_pending_returns = {}


def _sink():
    global _out
    if _out is None:
        path = os.environ.get("DHTRACE_OUT", "/tmp/dhtrace.jsonl")
        _out = open(path, "a", buffering=1)
    return _out


def emit(rec):
    # Absolute wall clock, because the action markers that label each capture
    # window are appended to the same file by the driver shell, in a different
    # process. Monotonic time is kept too, for intra-run deltas.
    rec.setdefault("ts", round(time.time(), 6))
    rec.setdefault("t", round(time.monotonic() - _t0, 6))
    _sink().write(json.dumps(rec) + "\n")


def _read(proc, addr, size):
    if not addr:
        return None
    err = lldb.SBError()
    data = proc.ReadMemory(addr, size, err)
    return data if err.Success() else None


def decode_report_words(proc, word0, word1):
    """Decode a HIDReport from its two ABI words. Never raises."""
    tag = (word1 >> 62) & 0x3
    if tag == 0:
        n = (word1 >> 48) & 0xFF
        if n <= INLINE_MAX:
            raw = struct.pack("<QQ", word0, word1)[:n]
            return {"repr": "inline", "len": n, "bytes": raw.hex()}
        return {"repr": "inline", "len": n, "error": "inline length out of range",
                "w0": hex(word0), "w1": hex(word1)}
    hdr = _read(proc, word0 + STORAGE_BYTES_PTR_OFF, 16)
    if hdr is None:
        return {"repr": "heap", "tag": tag, "w0": hex(word0), "w1": hex(word1),
                "error": "storage header unreadable"}
    ptr, length = struct.unpack("<QQ", hdr)
    if not ptr or not (0 < length <= REPORT_LEN_MAX):
        return {"repr": "heap", "tag": tag, "w0": hex(word0), "w1": hex(word1),
                "bytes_ptr": hex(ptr), "len": length,
                "error": "implausible storage length"}
    body = _read(proc, ptr, length)
    if body is None:
        return {"repr": "heap", "tag": tag, "len": length,
                "error": "storage body unreadable"}
    return {"repr": "heap", "tag": tag, "len": length, "bytes": body.hex()}


def read_report_array(proc, arr):
    """Decode a Swift [HIDReport]. Records raw storage when the shape is off."""
    if not arr:
        return None
    hdr = _read(proc, arr + ARRAY_COUNT_OFF, 8)
    if hdr is None:
        return {"ref": hex(arr), "error": "count unreadable"}
    (count,) = struct.unpack("<Q", hdr)
    if count > ARRAY_COUNT_MAX:
        raw = _read(proc, arr, 64)
        return {"ref": hex(arr), "count": count, "error": "implausible count",
                "raw": raw.hex() if raw else None}
    out = []
    for i in range(count):
        cell = _read(proc, arr + ARRAY_ELEMS_OFF + ARRAY_STRIDE * i, 16)
        if cell is None:
            out.append({"error": "element unreadable"})
            continue
        w0, w1 = struct.unpack("<QQ", cell)
        out.append(decode_report_words(proc, w0, w1))
    return {"count": count, "reports": out}


def _regs(frame, names):
    out = {}
    for n in names:
        v = frame.FindRegister(n)
        out[n] = v.GetValueAsUnsigned() if v.IsValid() else None
    return out


def _governed(bp, label):
    """Return True if this hit is within budget; disable the tap when it is not."""
    now = time.monotonic()
    st = _bp_state.setdefault(bp.GetID(), {"total": 0, "win_t": now, "win_n": 0})
    st["total"] += 1
    st["win_n"] += 1
    elapsed = now - st["win_t"]
    if elapsed >= BUDGET_WINDOW_S:
        rate = st["win_n"] / elapsed
        if rate > BUDGET_HITS_PER_S:
            bp.SetEnabled(False)
            emit({"kind": "shed", "label": label, "bp": bp.GetID(),
                  "rate": round(rate, 1), "total": st["total"],
                  "note": "tap disabled to keep Device Hub responsive"})
            return False
        st["win_t"] = now
        st["win_n"] = 0
    return True


def on_return(frame, bp_loc, extra, internal_dict):
    """One-shot breakpoint planted at the caller's return address."""
    global _seq
    bp = bp_loc.GetBreakpoint()
    ctx = _pending_returns.pop(bp.GetID(), {})
    proc = frame.GetThread().GetProcess()
    _seq += 1
    regs = _regs(frame, ("x0", "x1"))
    rec = {"kind": "return", "n": _seq, "label": ctx.get("label"),
           "of": ctx.get("entry_seq"),
           "regs": {k: (hex(v) if v is not None else None) for k, v in regs.items()}}
    want = ctx.get("returns")
    if want == "report_array":
        # Which register holds the array depends on the function: updateCopyMask
        # returns it in x0, filterEvent in x1 (w0 is `notify`). Both are read;
        # the implausible one decodes to an error record rather than silence.
        rec["result"] = read_report_array(proc, regs.get("x0") or 0)
    elif want == "report_array_x1":
        rec["notify"] = (regs.get("x0") or 0) & 1
        rec["result"] = read_report_array(proc, regs.get("x1") or 0)
    elif want == "report":
        rec["result"] = decode_report_words(
            proc, regs.get("x0") or 0, regs.get("x1") or 0)
    elif want == "indirect" and ctx.get("x8"):
        buf = _read(proc, ctx["x8"], 64)
        rec["indirect_x8"] = buf.hex() if buf else None
    emit(rec)
    frame.GetThread().GetProcess().GetTarget().BreakpointDelete(bp.GetID())
    return False


def on_hit(frame, bp_loc, extra, internal_dict):
    """Entry tap. Always auto-continues, even on internal error."""
    global _seq
    bp = bp_loc.GetBreakpoint()
    try:
        spec = internal_dict.get("dhtrace_taps", {}).get(bp.GetID(), {})
        label = spec.get("label") or frame.GetFunctionName() or "?"
        if not _governed(bp, label):
            return False
        _seq += 1
        thread = frame.GetThread()
        proc = thread.GetProcess()
        regs = _regs(frame, ("x0", "x1", "x2", "x3", "x8", "lr"))
        rec = {
            "kind": "call",
            "n": _seq,
            "label": label,
            "tid": thread.GetThreadID(),
            "regs": {k: (hex(v) if v is not None else None)
                     for k, v in regs.items() if k != "lr"},
        }
        arg = spec.get("report_arg")
        if arg:
            # The report arrives as two ABI words in consecutive registers.
            pair = {"x0": "x1", "x1": "x2", "x2": "x3"}.get(arg)
            w1 = regs.get(pair) or 0 if pair else 0
            rec["report"] = decode_report_words(proc, regs.get(arg) or 0, w1)
        if spec.get("args_are_words"):
            rec["words"] = {k: regs.get(k) for k in spec["args_are_words"]}
        if spec.get("returns"):
            lr = regs.get("lr") or 0
            if lr:
                tgt = proc.GetTarget()
                rb = tgt.BreakpointCreateByAddress(lr)
                rb.SetOneShot(True)
                rb.SetScriptCallbackFunction("dhtrace.on_return")
                _pending_returns[rb.GetID()] = {
                    "label": label, "entry_seq": _seq,
                    "returns": spec["returns"], "x8": regs.get("x8"),
                }
        emit(rec)
    except Exception as exc:  # never let a tap stop the target
        try:
            emit({"kind": "tap_error", "bp": bp.GetID(), "error": repr(exc)})
        except Exception:
            pass
    return False


def install(debugger, command, result, internal_dict):
    """`script dhtrace.install(...)` is not used; taps are installed by dhtrace.sh."""
    pass


def register_tap(debugger, command, result, internal_dict):
    """Called as: dhtrace_tap <bp_id> <label> <json spec>"""
    parts = command.split(" ", 2)
    bp_id = int(parts[0])
    spec = json.loads(parts[2]) if len(parts) > 2 else {}
    spec["label"] = parts[1]
    internal_dict.setdefault("dhtrace_taps", {})[bp_id] = spec


def mark(debugger, command, result, internal_dict):
    """Called as: dhtrace_mark <text> — writes an action marker into the stream."""
    emit({"kind": "mark", "text": command.strip()})


def report(debugger, command, result, internal_dict):
    elapsed = time.monotonic() - _t0
    totals = {str(k): v["total"] for k, v in _bp_state.items()}
    emit({"kind": "summary", "elapsed": round(elapsed, 2), "records": _seq,
          "per_bp": totals})
    print("DHTRACE records=%d elapsed=%.1fs per_bp=%s" % (_seq, elapsed, totals))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
        "command script add -f dhtrace.register_tap dhtrace_tap")
    debugger.HandleCommand("command script add -f dhtrace.mark dhtrace_mark")
    debugger.HandleCommand("command script add -f dhtrace.report dhtrace_report")
