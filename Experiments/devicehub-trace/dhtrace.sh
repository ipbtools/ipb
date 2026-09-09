#!/bin/zsh
# dhtrace — trace Apple's Device Hub while a human performs a scripted sequence.
#
#   Experiments/devicehub-trace/dhtrace.sh <action-script> [out.jsonl]
#
# The action script drives the operator. Each line is one prompt; the driver
# prints it, waits for ENTER, then records a short drain window before moving
# on. Steps are operator-paced rather than timed, because the durations are not
# knowable in advance -- unlocking a phone means typing a passcode, and a step
# that assumed a fixed number of seconds simply cut the operator off.
#
# A line beginning with "!" is a setup step: it is not traced and not recorded
# as a capture window. Use it for anything that has to happen before the run
# proper (unlock the phone, focus the window, put an app on screen).
#
# Markers go into the same JSONL stream the tracer writes, so every report lands
# inside a labelled window and nobody has to reconstruct the order afterwards.
#
# Two properties this harness guarantees, because their absence is what made
# earlier rounds expensive:
#   * Device Hub is never left stopped. Callbacks auto-continue, and a tap that
#     exceeds its hits/sec budget disables itself (see dhtrace.py).
#   * The run always ends: the operator ends it, or a wall-clock cap does, and
#     either way it detaches cleanly and the traced process survives.
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

drain=${DHTRACE_DRAIN:-2}          # seconds recorded after each action
cap=${DHTRACE_CAP:-1800}           # backstop, in case the session is abandoned
stopfile=$(mktemp -u -t dhtrace-stop)
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
  print "dhrun ${cap} ${stopfile}"
  print "dhtrace_report"
  print "quit"
} > "$lldbfile"

mark() {
  python3 -c 'import json,time,sys; print(json.dumps({"kind":"mark","ts":round(time.time(),6),"text":sys.argv[1]}))' "$1" >> "$out"
}

cleanup() { : > "$stopfile"; }
trap cleanup INT TERM

print "Device Hub pid ${pid}; output ${out}"
: > "$out"

DHTRACE_OUT=$out lldb --batch -s "$lldbfile" >|"${out%.jsonl}.lldb.log" 2>&1 &
lldbpid=$!

# Let lldb attach and bind every breakpoint before the operator is asked to act.
sleep 3

print ""
print "Press ENTER after finishing each step. Take as long as you need."
print "================================================================"
step=0
total=$(grep -vE '^\s*(#|$)' "$script" | grep -cv '^!')
while IFS= read -r line; do
  [[ $line == \#* || -z ${line//[[:space:]]/} ]] && continue
  if [[ $line == '!'* ]]; then
    print ""
    print "  SETUP  ${line#!}"
    print -n "         ...then press ENTER > "
    read -r _ < /dev/tty
    continue
  fi
  step=$((step+1))
  print ""
  print "  [${step}/${total}] ${line}"
  print -n "          ...then press ENTER > "
  mark "$line"
  read -r _ < /dev/tty
  mark "DRAIN after: ${line}"
  sleep "$drain"
done < "$script"

mark "END"
print ""
print "================================================================"
cleanup
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
print ""
print "Decode with:"
print "  ${here}/decode.py ${out} --bytes"
