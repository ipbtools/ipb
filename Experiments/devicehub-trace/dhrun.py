"""Bounded, non-blocking run control for dhtrace.

lldb's synchronous `continue` never returns when every breakpoint callback
auto-continues, so a batch script parks there forever. `dhrun <seconds> [stopfile]`
puts the debugger in async mode, resumes the target, and waits until either the
driver creates the stop file or the wall-clock cap expires, then stops and
detaches. Verified against a live process: the target keeps running afterwards.

The stop file is what lets the operator pace the run. Capture steps wait for a
keypress rather than a fixed sleep -- unlocking a phone takes as long as it
takes -- so the driver cannot know the duration in advance. The cap remains as
a backstop so an abandoned session still detaches (the repo forbids unbounded
waits).
"""

import os
import time

import lldb


def dhrun(debugger, command, result, internal_dict):
    parts = command.split()
    duration = float(parts[0]) if parts else 1800.0
    stopfile = parts[1] if len(parts) > 1 else None

    debugger.SetAsync(True)
    process = debugger.GetSelectedTarget().GetProcess()
    process.Continue()

    deadline = time.time() + duration
    reason = "cap"
    while time.time() < deadline:
        if stopfile and os.path.exists(stopfile):
            reason = "operator"
            break
        time.sleep(0.2)

    process.Stop()
    time.sleep(0.3)
    err = process.Detach()
    print("DHRUN detached ok=%s state=%s reason=%s" %
          (err.Success(), process.GetState(), reason))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f dhrun.dhrun dhrun")
