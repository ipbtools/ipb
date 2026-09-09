"""Bounded, non-blocking run control for dhtrace.

lldb's synchronous `continue` never returns when every breakpoint callback
auto-continues, so a batch script parks there forever. `dhrun <seconds>` puts
the debugger in async mode, resumes the target, waits out the wall clock, then
stops and detaches. Verified against a live process: the target keeps running
after detach.
"""

import time

import lldb


def dhrun(debugger, command, result, internal_dict):
    duration = float(command.strip() or "30")
    debugger.SetAsync(True)
    process = debugger.GetSelectedTarget().GetProcess()
    process.Continue()
    deadline = time.time() + duration
    while time.time() < deadline:
        time.sleep(0.2)
    process.Stop()
    time.sleep(0.3)
    err = process.Detach()
    print("DHRUN detached ok=%s state=%s" % (err.Success(), process.GetState()))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f dhrun.dhrun dhrun")
