# Dump every XPC message a process sends that mentions a CoreDevice action.
#
# devicectl is signed with library-validation, which blocks loading unsigned libraries (so the
# DYLD_INSERT_LIBRARIES interposer in Experiments/tools/rxpc_tap.c cannot attach) but does NOT block
# debugging. So lldb is the way to see what a `devicectl device <action>` call actually sends --
# which is how we find the TunnelAssertionRequest payload for TODO(tunnel-keepalive).
#
#   xcrun lldb --batch -o "command script import Experiments/devicehub-trace/xpctrace.py" \
#              -o "xpctrace_arm" -o run -o quit -- <devicectl> device info details --device <uuid>
import lldb

# Widened: the DeviceManagerCheckIn pair is the lead worth chasing and did not match the
# original filter, so this tracer would have discarded the very message it was pointed at.
FILTER = ("coredevice.action", "assertion", "Assertion", "CheckIn", "checkIn", "DeviceManager")
_seen = set()

def _describe(frame, reg):
    msg = frame.FindRegister(reg).GetValueAsUnsigned()
    if not msg:
        return None
    expr = frame.EvaluateExpression('(char *)xpc_copy_description((void *)0x%x)' % msg)
    ptr = expr.GetValueAsUnsigned()
    if not ptr:
        return None
    err = lldb.SBError()
    return frame.thread.process.ReadCStringFromMemory(ptr, 65536, err) or None

def on_send(frame, bp_loc, internal_dict):
    text = _describe(frame, "x1")
    if text and any(f in text for f in FILTER):
        key = text[:400]
        if key not in _seen:
            _seen.add(key)
            print("\n=== XPC SEND (%s) ===\n%s" % (bp_loc.GetBreakpoint().GetName() or "send", text))
    return False   # auto-continue

def xpctrace_arm(debugger, command, result, internal_dict):
    target = debugger.GetSelectedTarget()
    for sym in ("xpc_connection_send_message_with_reply_sync",
                "xpc_connection_send_message_with_reply",
                "xpc_connection_send_message"):
        bp = target.BreakpointCreateByName(sym)
        if bp.GetNumLocations():
            bp.SetScriptCallbackFunction("xpctrace.on_send")
            bp.SetAutoContinue(True)
            print("armed %s (%d locations)" % (sym, bp.GetNumLocations()))

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f xpctrace.xpctrace_arm xpctrace_arm")
