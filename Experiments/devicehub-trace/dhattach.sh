#!/bin/zsh
# dhattach — trace a running process against a tap manifest, with no operator
# prompts of any kind.
#
#   dhattach.sh <pid|-n name> <taps.tsv> <out.jsonl> <stopfile> [cap-seconds]
#
# dhtrace.sh drives a *human*: it prints countdowns and waits on ENTER. When the
# operator is another agent that runs in its own process, every one of those
# prompts is a deadlock -- there is no terminal to press ENTER on. This variant
# starts the tracer, writes READY-TRACE next to the output, and then records
# until the stopfile appears or the cap expires. Correlation is by timestamp:
# the operator logs what it did and when, this logs what crossed the wire and
# when, and the two are joined afterwards. No handshake, nothing to deadlock on.
#
# Everything else is deliberately inherited from dhtrace.sh: breakpoints bind
# with --skip-prologue false (the default binds past the prologue, by which
# point the argument registers are clobbered), callbacks auto-continue, and the
# hit-rate governor disables a runaway tap rather than letting it stop the
# target.
set -u
setopt PIPE_FAIL

here=${0:A:h}
sel=${1:?usage: dhattach.sh <pid|-n name> <taps.tsv> <out.jsonl> <stopfile> [cap]}
taps=${2:?taps manifest}
out=${3:?output jsonl}
stopfile=${4:?stopfile}
cap=${5:-900}

if [[ $sel == -n ]]; then
  print -u2 "dhattach: use -n<name> or a pid"; exit 2
elif [[ $sel == -n* ]]; then
  pid=$(pgrep -x "${sel#-n}" | head -1)
else
  pid=$sel
fi
[[ -n ${pid:-} ]] || { print -u2 "dhattach: no such process: $sel"; exit 3 }
kill -0 "$pid" 2>/dev/null || { print -u2 "dhattach: pid $pid is not running"; exit 3 }
[[ -f $taps ]] || { print -u2 "dhattach: no such tap manifest: $taps"; exit 2 }

lldbfile=$(mktemp -t dhattach).lldb
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
  done < "$taps"
  print "dhrun ${cap} ${stopfile}"
  print "dhtrace_report"
  print "detach"
  print "quit"
} > "$lldbfile"

: > "$out"
rm -f "$stopfile"
print "dhattach: pid=${pid} taps=${taps} out=${out}"

DHTRACE_OUT=$out lldb --batch -s "$lldbfile" >|"${out%.jsonl}.lldb.log" 2>&1 &
lldbpid=$!

# Do not announce readiness until every breakpoint has actually bound: an
# operator that clicks during the attach window spends the action on nothing.
bound=0
for i in {1..40}; do
  sleep 0.5
  bound=$(grep -c "^Breakpoint [0-9]*:" "${out%.jsonl}.lldb.log" 2>/dev/null || print 0)
  want=$(grep -vcE '^\s*(#|$)' "$taps")
  (( bound >= want )) && break
  kill -0 $lldbpid 2>/dev/null || break
done
if ! kill -0 $lldbpid 2>/dev/null; then
  print -u2 "dhattach: lldb exited during attach; see ${out%.jsonl}.lldb.log"
  exit 4
fi
print "dhattach: ${bound} breakpoints bound"
print "$bound" > "${out%.jsonl}.bound"

wait $lldbpid
rc=$?
print "dhattach: lldb rc=${rc}; records=$(grep -c . "$out" 2>/dev/null || print 0) -> ${out}"
if kill -0 "$pid" 2>/dev/null; then
  print "dhattach: target still running."
else
  print "dhattach: WARNING target ${pid} is gone."
fi
