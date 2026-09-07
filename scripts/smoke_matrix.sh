#!/usr/bin/env zsh
# Smoke gate for devicehubctl. Exits non-zero if any step fails.
# usage: [DEVICE_ID=<uuid>] [SMOKE_INTERACTIVE=1] [TAP_XY="0.15 0.12"] [LONG_XY="0.15 0.12"] smoke_matrix.sh <repo_root> <out_dir>
set -uo pipefail
ROOT="${1:?repo root}"; OUT="${2:?out dir}"; mkdir -p "$OUT"
CTL="$ROOT/bin/devicehubctl"
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
run "service-ids (host only)" --expect '^mainTouchscreen +0x101' -- "$CTL" service-ids
run "descriptors" --expect 'connected descriptors count=[1-9]' -- "$CTL" descriptors
run "descriptors list 5 services" --expect 'connectedDescriptor\[4\]' -- "$CTL" descriptors
run "service-id touchscreen" --expect '^0x101$' -- "$CTL" service-id touchscreen
run "service-id gesture"     --expect '^0x501$' -- "$CTL" service-id gesture
run "service-id keyboard"    --expect '^0x200$' -- "$CTL" service-id keyboard
run "service-id buttons"     --expect '^0x402$' -- "$CTL" service-id buttons
run "service-id avp"         --expect '^0x500$' -- "$CTL" service-id avp
shot 00_before
run "key-up (empty keyboard report)" -- "$CTL" key-up
run "pointer 0 0" -- "$CTL" pointer 0 0
run "scroll-report 0x501 0 0" -- "$CTL" scroll-report 0x501 0 0
run "scroll-event 0 0 0" -- "$CTL" scroll-event 0 0 0
run "vendor-defined 0 0 0" -- "$CTL" vendor-defined 0 0 0
run "reset-gesture" -- "$CTL" reset-gesture
shot 01_after_nondestructive

if [[ "${SMOKE_INTERACTIVE:-0}" == 1 ]]; then
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

echo; echo "=== summary"; grep -E '^(###|rc=)' "$log" | paste - - | awk -F'\t' '{printf "%-45s %s\n", substr($1,5), $2}'
if (( failures )); then echo "SMOKE FAILED: $failures failure(s)"; exit 1; fi
echo "SMOKE PASSED"
