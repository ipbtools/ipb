#!/usr/bin/env zsh
# Smoke gate for ipb. Exits non-zero if any step fails.
# usage: [DEVICE_ID=<uuid>] [SMOKE_INTERACTIVE=1] [TAP_XY="0.15 0.12"] [LONG_XY="0.15 0.12"] smoke_matrix.sh <repo_root> <out_dir>
set -uo pipefail
ROOT="${1:?repo root}"; OUT="${2:?out dir}"; mkdir -p "$OUT"
CTL="$ROOT/bin/ipb"
log="$OUT/smoke.log"; : > "$log"
failures=0
TAP_XY="${TAP_XY:-0.15 0.12}"     # first home-screen icon on an iPhone 12 mini / 13 Pro grid
LONG_XY="${LONG_XY:-$TAP_XY}"

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
run "zsh completion loads" -- zsh -c "fpath=($ROOT/completions \$fpath); autoload -Uz compinit; compinit -u -d \$(mktemp -t ipbzcd); autoload -Uz _ipb; functions _ipb >/dev/null"
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
  if "$CTL" lock-state 2>/dev/null | grep -q 'passcodeRequired: true'; then
    fail "device is locked (passcodeRequired: true); unlock it before the interactive steps"
  else
  run "home" -- "$CTL" home; sleep 1; shot 02_home
  run "tap $TAP_XY (icon)" -- "$CTL" tap ${=TAP_XY}; sleep 1.5; shot 03_after_tap
  run "home" -- "$CTL" home; sleep 1; shot 04_home
  run "recents" -- "$CTL" recents; sleep 1.5; shot 05_after_recents
  run "home" -- "$CTL" home; sleep 1; shot 06_home
  run "swipe 0.5 0.75 -> 0.5 0.35" -- "$CTL" swipe 0.5 0.75 0.5 0.35; sleep 1; shot 07_after_swipe
  run "home" -- "$CTL" home; sleep 1
  run "scroll 0.5 0.75 dy=0.30" -- "$CTL" scroll 0.5 0.75 0 0.30; sleep 1; shot 08_after_scroll
  run "home" -- "$CTL" home; sleep 1; shot 09_home
  run "long $LONG_XY 1.2 (icon)" -- "$CTL" long ${=LONG_XY} 1.2; sleep 1; shot 10_after_long
  run "key escape" -- "$CTL" key escape 0.02; sleep 1; shot 11_after_escape
  run "home" -- "$CTL" home; sleep 1; shot 12_final_home
  # Frame-to-frame changes are reported, not enforced: a system alert (unverified app, permission
  # prompt) can legitimately freeze the screen, and Home on the home screen is a no-op.
  prev=""
  for f in "$OUT"/[0-9][0-9]_*.png; do
    h=$(md5 -q "$f")
    [[ -n "$prev" && "$h" == "$prev" ]] && printf 'WARN: %s identical to previous frame; inspect the screenshots\n' "$(basename "$f")" | tee -a "$log"
    prev="$h"
  done
  fi
fi

echo; echo "=== summary"; grep -E '^(###|rc=)' "$log" | paste - - | awk -F'\t' '{printf "%-45s %s\n", substr($1,5), $2}'
if (( failures )); then echo "SMOKE FAILED: $failures failure(s)"; exit 1; fi
echo "SMOKE PASSED"
