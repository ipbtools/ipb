#!/usr/bin/env zsh
# Smoke gate for ipb. Exits non-zero if any step fails.
# usage: [DEVICE_ID=<uuid>] [SMOKE_INTERACTIVE=1] [TAP_XY="x y"] [LONG_XY="x y"] smoke_matrix.sh <repo_root> <out_dir>
# Interactive iOS 27 fixture: Settings list/search; KEY_XY and KEY_CLOSE_XY override search coordinates.
# Inspect screenshots: a material pixel change is still not semantic proof.
set -uo pipefail
ROOT="${1:?repo root}"; OUT="${2:?out dir}"; mkdir -p "$OUT"
CTL="$ROOT/bin/ipb"
log="$OUT/smoke.log"; : > "$log"
failures=0
SCRIPT_DIR="${0:A:h}"
PNG_DIGEST="$ROOT/scripts/png_pixels_digest.py"
[[ -r "$PNG_DIGEST" ]] || PNG_DIGEST="$SCRIPT_DIR/png_pixels_digest.py"
ASSERTIONS="$ROOT/scripts/smoke_assertions.zsh"
[[ -r "$ASSERTIONS" ]] || ASSERTIONS="$SCRIPT_DIR/smoke_assertions.zsh"
if [[ ! -r "$ASSERTIONS" || ! -r "$PNG_DIGEST" ]]; then
  print -u2 "smoke gate missing installed assertion helper or pixel decoder"
  exit 1
fi
source "$ASSERTIONS" || exit 1
COMPLETION_DIR="${SMOKE_COMPLETIONS_DIR:-$ROOT/completions}"
[[ -d "$COMPLETION_DIR" ]] || COMPLETION_DIR="$SCRIPT_DIR/../zsh/site-functions"
TAP_XY="${TAP_XY:-0.15 0.12}"     # first home-screen icon on an iPhone 12 mini / 13 Pro grid
LONG_XY="${LONG_XY:-$TAP_XY}"
KEY_XY="${KEY_XY:-0.5 0.935}"  # iOS 27 Settings search field; verify on the target layout
KEY_CLOSE_XY="${KEY_CLOSE_XY:-0.915 0.569}" # search cancel beside the focused field

fail() { failures=$((failures + 1)); printf 'FAIL: %s\n' "$*" | tee -a "$log"; }

# run <name> [--expect <regex>] -- <cmd...>: rc must be 0 and, if given, stdout must match regex
run() {
  local name="$1"; shift
  local expect=""
  if [[ "${1:-}" == "--expect" ]]; then expect="$2"; shift 2; fi
  [[ "${1:-}" == "--" ]] && shift
  printf '\n### %s\n$ %s\n' "$name" "$*" | tee -a "$log"
  local start=$(date +%s) rc=0 out
  out="$("$@" 2>>"$log")" || rc=$?
  LAST_OUT="$out"
  printf '%s\n' "$out" >>"$log"
  printf 'rc=%d (%ds)\n' "$rc" $(( $(date +%s) - start )) | tee -a "$log"
  if (( rc != 0 )); then fail "$name: rc=$rc"; return 1; fi
  if [[ -n "$expect" ]] && ! print -r -- "$out" | grep -Eq -- "$expect"; then
    fail "$name: output did not match /$expect/"; return 1
  fi
  return 0
}

shot() {
  local file="$OUT/$1.png"
  rm -f "$file"
  run "screenshot $1" -- "$CTL" screenshot "$file" || return 1
  if [[ ! -s "$file" ]] || ! sips -g pixelWidth "$file" >/dev/null 2>&1; then
    fail "screenshot $1: missing or undecodable PNG"; return 1
  fi
}

echo "host: $(sw_vers -productVersion) $(sw_vers -buildVersion)  DEVICE_ID=${DEVICE_ID:-auto}" | tee -a "$log"
# The completion is user documentation the shell executes; a syntax error in it is silent
# until someone presses Tab. Loading it here is host-only and costs nothing.
run "zsh completion loads" -- zsh -c 'fpath=("$1" $fpath); autoload -Uz _ipb; autoload +X _ipb' -- "$COMPLETION_DIR"
run "service-ids (host only)" --expect '^mainTouchscreen +0x101' -- "$CTL" service-ids
run "descriptors" --expect 'connected descriptors count=[1-9]' -- "$CTL" descriptors
# Capability expectations come from the device OS: iOS 27 exposes five HID services (adds
# touchscreenGesture 0x501), iOS 26 exposes four. Derived from the descriptors step that just ran,
# never from a separate probe whose failure could pass for "absent".
run "descriptors list >=4 services" --expect 'connectedDescriptor\[3\]' -- "$CTL" descriptors
HAS_GESTURE=0; print -r -- "$LAST_OUT" | grep -q 'touchscreenGesture' && HAS_GESTURE=1
SEL="$("$CTL" device 2>/dev/null || true)"
# Device selection: a UUID prefix and the device name must resolve to the same device the
# default pick returns. devicectl accepts neither, so this is the only check that ipb's own
# resolver works. A name that is a substring of another device's name is a genuine ambiguity
# and fails here by design.
if [[ -z "$SEL" ]]; then
  fail "device selection: 'ipb device' printed nothing"
else
  run "select by uuid prefix" --expect "^$SEL\$" -- "$CTL" -s "${SEL:0:8}" device
  SEL_NAME="$("$CTL" devices 2>/dev/null | awk -F'\t' -v id="$SEL" '$1 == id {print $2}')"
  if [[ -n "$SEL_NAME" ]]; then
    run "select by device name" --expect "^$SEL\$" -- "$CTL" --device "$SEL_NAME" device
  else
    fail "device selection: no name for $SEL in 'ipb devices'"
  fi
fi
OS_MAJOR="$("$CTL" devices 2>/dev/null | awk -F'\t' -v id="$SEL" '$1 == id {split($3, v, "."); print v[1]}')"
EXPECT_GESTURE="${EXPECT_GESTURE:-}"
if [[ -z "$EXPECT_GESTURE" ]]; then
  case "$OS_MAJOR" in
    <27->) EXPECT_GESTURE=1 ;;
    <1-26>) EXPECT_GESTURE=0 ;;
    *) EXPECT_GESTURE=unknown ;;
  esac
fi
echo "device $SEL iOS major ${OS_MAJOR:-?}; touchscreenGesture present=$HAS_GESTURE expected=$EXPECT_GESTURE" | tee -a "$log"
if [[ "$EXPECT_GESTURE" == 1 && $HAS_GESTURE -eq 0 ]]; then fail "touchscreenGesture service missing on an iOS ${OS_MAJOR} device"; fi
if [[ "$EXPECT_GESTURE" == unknown ]]; then echo "WARN: could not determine the device OS; gesture steps follow the descriptor set" | tee -a "$log"; fi
run "service-id touchscreen" --expect '^0x101$' -- "$CTL" service-id touchscreen
if (( HAS_GESTURE )); then run "service-id gesture" --expect '^0x501$' -- "$CTL" service-id gesture; fi
run "service-id keyboard"    --expect '^0x200$' -- "$CTL" service-id keyboard
run "service-id buttons"     --expect '^0x402$' -- "$CTL" service-id buttons
run "service-id avp"         --expect '^0x500$' -- "$CTL" service-id avp
# A mirror session must die when its wrapper is signalled, and must leave nothing behind. This is a
# regression test: removing `exec` so the tunnel keepalive could be reaped made the wrapper defer its
# trap until the helper returned, so `kill <ipb pid>` did nothing for up to --seconds; and the
# keepalive was backgrounded through the devicectl() shell function, so $! was a subshell and killing
# it orphaned the real devicectl. Both are fixed; this keeps them fixed. Startup failures are gate
# failures; this is a GUI-session gate, including in noninteractive mode.
mirror_signal_test() {
  local out="$OUT/mirror_kill.log"
  # DEVICE_ID is honoured from the environment; do not pass -s here (in zsh an unquoted
  # ${VAR:+-s "$VAR"} expands to ONE word and bin/ipb would reject it as an unknown command).
  "$CTL" mirror --seconds 60 >"$out" 2>&1 &
  local wrapper=$!
  local i helper_pid=""
  for i in $(seq 1 20); do
    helper_pid="$(pgrep -P "$wrapper" -x 'ipb-mirror' | head -1)"
    [[ -n "$helper_pid" ]] && break
    sleep 0.5
  done
  if ! kill -0 $wrapper 2>/dev/null || [[ -z "$helper_pid" ]]; then
    local startup_reason="$(head -2 "$out" | tr '\n' ' ')"
    [[ -n "$startup_reason" ]] || startup_reason="unknown startup failure"
    local startup_rc=0
    if kill -0 "$wrapper" 2>/dev/null; then kill -TERM "$wrapper" 2>/dev/null; fi
    wait "$wrapper" 2>/dev/null || startup_rc=$?
    fail "mirror startup failed (rc=$startup_rc): $startup_reason"
    return 0
  fi
  # Record THIS session's keepalive before signalling. A global pgrep would also match a keepalive
  # belonging to another session or left over from an earlier run, and report a false failure.
  local keepalive_pids=$(pgrep -P "$wrapper" 2>/dev/null | grep -v -x "$helper_pid" | tr '\n' ' ')
  local start=$(date +%s)
  kill -TERM $wrapper 2>/dev/null
  for i in $(seq 1 24); do kill -0 $wrapper 2>/dev/null || break; sleep 0.5; done
  local elapsed=$(( $(date +%s) - start ))
  if kill -0 $wrapper 2>/dev/null; then
    kill -KILL $wrapper 2>/dev/null; fail "mirror kill: wrapper still alive ${elapsed}s after SIGTERM"
  else
    echo "mirror kill: wrapper exited ${elapsed}s after SIGTERM" | tee -a "$log"
  fi
  # The helper drains on SIGTERM before exiting, so allow a bounded grace rather than asserting
  # immediately; only a helper that outlives it is an orphan.
  local i
  for i in $(seq 1 20); do kill -0 "$helper_pid" 2>/dev/null || break; sleep 0.5; done
  local pid survivors=""
  for pid in ${=keepalive_pids}; do
    if kill -0 "$pid" 2>/dev/null; then survivors="$survivors $pid"; kill -TERM "$pid" 2>/dev/null; fi
  done
  if [[ -n "$survivors" ]]; then
    fail "mirror kill: tunnel keepalive orphaned after session end (pids:$survivors)"
  else
    echo "mirror kill: no keepalive orphan (watched: ${keepalive_pids:-none})" | tee -a "$log"
  fi
  if kill -0 "$helper_pid" 2>/dev/null; then
    fail "mirror kill: mirror helper still running after session end (pid:$helper_pid)"
  fi
}
printf '\n### mirror signal handling + orphan check\n' | tee -a "$log"
mirror_signal_test

shot 00_before
run "key-up (empty keyboard report)" -- "$CTL" key-up
if (( HAS_GESTURE )); then
  run "pointer 0 0" -- "$CTL" pointer 0 0
  run "scroll-report 0x501 0 0" -- "$CTL" scroll-report 0x501 0 0
else
  echo "SKIP: pointer / scroll-report (no touchscreenGesture service on this device)" | tee -a "$log"
fi
run "scroll-event 0 0 0" -- "$CTL" scroll-event 0 0 0
run "vendor-defined 0 0 0" -- "$CTL" vendor-defined 0 0 0
run "reset-gesture" -- "$CTL" reset-gesture
shot 01_after_nondestructive

if [[ "${SMOKE_INTERACTIVE:-0}" == 1 ]]; then
  # A locked phone accepts HID reports but shows nothing; refuse to grade gestures against the lock screen.
  LOCK_STATE_OUT="$($CTL lock-state 2>&1)"; LOCK_STATE_RC=$?
  if ! lock_state_is_unlocked "$LOCK_STATE_RC" "$LOCK_STATE_OUT"; then
    if (( LOCK_STATE_RC != 0 )); then
      fail "device lock-state check failed (rc=$LOCK_STATE_RC): ${LOCK_STATE_OUT//$'\n'/ }"
    elif print -r -- "$LOCK_STATE_OUT" | grep -Eq '(^|[[:space:]])passcodeRequired:[[:space:]]*true([[:space:]]|$)'; then
    fail "device is locked (passcodeRequired: true); unlock it before the interactive steps"
    else
      fail "device lock-state is unknown; expected passcodeRequired: false"
    fi
  else
  run "home" -- "$CTL" home; sleep 1; shot 02_home
  run "tap $TAP_XY (icon)" -- "$CTL" tap ${=TAP_XY}; sleep 1.5; shot 03_after_tap
  run "home" -- "$CTL" home; sleep 1; shot 04_home
  run "recents" -- "$CTL" recents; sleep 1.5; shot 05_after_recents
  run "home" -- "$CTL" home; sleep 1; shot 06_home
  run "open Settings for scrollable fixture" -- "$CTL" launch com.apple.Preferences; sleep 1
  shot 06_before_swipe
  run "swipe 0.5 0.75 -> 0.5 0.35" -- "$CTL" swipe 0.5 0.75 0.5 0.35; sleep 1; shot 07_after_swipe
  shot 07_before_scroll
  run "scroll Settings back toward top" -- "$CTL" scroll 0.5 0.35 0 0.30; sleep 1; shot 08_after_scroll
  run "home" -- "$CTL" home; sleep 1; shot 09_home
  run "long $LONG_XY 1.2 (icon)" -- "$CTL" long ${=LONG_XY} 1.2; sleep 1; shot 10_after_long
  run "home dismisses context menu" -- "$CTL" home; sleep 1; shot 11_after_home
  run "open Settings for keyboard fixture" -- "$CTL" launch com.apple.Preferences; sleep 1
  run "focus Settings search" -- "$CTL" tap ${=KEY_XY}; sleep 1; shot 12_before_key
  run "key a" -- "$CTL" key a 0.02; sleep 1; shot 13_after_key
  run "clear test key" -- "$CTL" key backspace 0.02; sleep 1; shot 14_after_clear
  run "close Settings search" -- "$CTL" tap ${=KEY_CLOSE_XY}
  run "home" -- "$CTL" home; sleep 1; shot 15_final_home
  # Each no-op allowance has an explicit reason. Other transitions must change
  # decoded pixels; this is a freshness check, not proof of semantic correctness.
  check_frame_transition "nondestructive reports" "$OUT/00_before.png" "$OUT/01_after_nondestructive.png" unchanged "reports intentionally do not alter the display" || true
  check_frame_transition "home" "$OUT/01_after_nondestructive.png" "$OUT/02_home.png" unchanged "Home on an already-home screen is a valid no-op" || true
  check_frame_transition "tap" "$OUT/02_home.png" "$OUT/03_after_tap.png" changed "tap should leave the home baseline" || true
  check_frame_transition "home after tap" "$OUT/03_after_tap.png" "$OUT/04_home.png" changed "return from the tapped app" || true
  check_frame_transition "recents" "$OUT/04_home.png" "$OUT/05_after_recents.png" changed "open App Switcher" || true
  check_frame_transition "home after recents" "$OUT/05_after_recents.png" "$OUT/06_home.png" changed "return from App Switcher" || true
  check_frame_transition "swipe" "$OUT/06_before_swipe.png" "$OUT/07_after_swipe.png" changed "Settings list should move" || true
  check_frame_transition "scroll" "$OUT/07_before_scroll.png" "$OUT/08_after_scroll.png" changed "Settings list should move back" || true
  check_frame_transition "home after scroll" "$OUT/08_after_scroll.png" "$OUT/09_home.png" changed "return from Settings" || true
  check_frame_transition "long" "$OUT/09_home.png" "$OUT/10_after_long.png" changed "long press should produce a visible result" || true
  check_frame_transition "home after long" "$OUT/10_after_long.png" "$OUT/11_after_home.png" changed "Home dismisses the context menu" || true
  check_frame_transition "key a" "$OUT/12_before_key.png" "$OUT/13_after_key.png" changed "search query and results should change" || true
  check_frame_transition "clear key" "$OUT/13_after_key.png" "$OUT/14_after_clear.png" changed "clear query restores search suggestions" || true
  check_frame_transition "final home" "$OUT/14_after_clear.png" "$OUT/15_final_home.png" changed "return from Settings search" || true
  fi
fi

echo; echo "=== summary"; grep -E '^(###|rc=)' "$log" | paste - - | awk -F'\t' '{printf "%-45s %s\n", substr($1,5), $2}'
if (( failures )); then echo "SMOKE FAILED: $failures failure(s)"; exit 1; fi
echo "SMOKE PASSED"
