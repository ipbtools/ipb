#!/bin/zsh
# dhtrace — trace Apple's Device Hub while a human performs a scripted sequence.
#
#   Experiments/devicehub-trace/dhtrace.sh <action-script> [out.jsonl]
#
# The action script drives the human: each line is "<seconds><TAB><prompt>".
# The driver prints the prompt, appends a marker to the same JSONL stream the
# tracer writes, then waits. Every report captured in that interval is
# therefore labelled by the action that produced it, with no after-the-fact
# narration from the operator.
#
# Two properties this harness guarantees, because their absence is what made
# earlier rounds expensive:
#   * Device Hub is never left stopped. Callbacks auto-continue, and a tap that
#     exceeds its hits/sec budget disables itself (see dhtrace.py).
#   * The run is bounded and detaches cleanly; the traced process survives.
set -u
setopt PIPE_FAIL

here=${0:A:h}
script=${1:?usage: dhtrace.sh <action-script> [out.jsonl]}
out=${2:-/tmp/dhtrace-$(date +%Y%m%d-%H%M%S).jsonl}
[[ -f $script ]] || { print -u2 "no such action script: $script"; exit 2; }

pid=$(pgrep -x DeviceHub | head -1)
if [[ -z $pid ]]; then
  print -u2 "Device Hub is not running. Open it from Xcode (Window > Devices) first."
  exit 3
fi

total=$(awk -F'\t' '!/^#/ && NF>=2 {s+=$1} END {print s+3}' "$script")
lldbfile=$(mktemp -t dhtrace).lldb

{
  print "settings set interpreter.stop-command-source-on-error false"
  print "command script import ${here}/dhtrace.py"
  print "command script import ${here}/dhrun.py"
  print "process attach --pid ${pid}"
  n=0
  while IFS=$'\t' read -r label module symbol spec; do
    [[ $label == \#* || -z ${label:-} ]] && continue
    n=$((n+1))
    print "breakpoint set -n \"${symbol}\" -s ${module} --skip-prologue false"
    print "breakpoint command add -s python -F dhtrace.on_hit ${n}"
    print "dhtrace_tap ${n} ${label} ${spec}"
  done < "${here}/taps.tsv"
  print "dhrun ${total}"
  print "dhtrace_report"
  print "quit"
} > "$lldbfile"

print "Device Hub pid ${pid}; tracing ${total}s; output ${out}"
: > "$out"

DHTRACE_OUT=$out lldb --batch -s "$lldbfile" >|"${out%.jsonl}.lldb.log" 2>&1 &
lldbpid=$!

mark() {
  python3 -c 'import json,time,sys; print(json.dumps({"kind":"mark","ts":round(time.time(),6),"text":sys.argv[1]}))' "$1" >> "$out"
}

# Let lldb attach and bind every breakpoint before the human is asked to act.
sleep 3
print ""
print "==================== BEGIN ===================="
while IFS=$'\t' read -r secs prompt; do
  [[ $secs == \#* || -z ${secs:-} ]] && continue
  mark "$prompt"
  print ""
  print ">>> ${prompt}"
  print "    (${secs}s)"
  sleep "$secs"
done < "$script"
mark "END"
print ""
print "===================== END ====================="

wait $lldbpid
rc=$?
print ""
print "lldb rc=${rc}; log ${out%.jsonl}.lldb.log"
print "captured $(grep -c . "$out") records -> ${out}"
if pgrep -x DeviceHub >/dev/null; then
  print "Device Hub still running."
else
  print "WARNING: Device Hub is gone; restart it before the next run."
fi
