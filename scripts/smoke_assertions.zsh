# Shared smoke-gate assertions. Caller supplies ROOT, OUT, log, and fail().
check_frame_transition() {
  local label="$1" before="$2" after="$3" expectation="$4" reason="$5"
  local ratio
  ratio="$(python3 "$PNG_DIGEST" --difference "$before" "$after")" || { fail "$label: cannot measure decoded pixel difference"; return 1; }
  if [[ "$expectation" == unchanged && "$ratio" == 0.000000 ]]; then
    printf 'frame unchanged (allowed): %s (%s)\n' "$label" "$reason" | tee -a "$log"; return 0
  fi
  if [[ "$expectation" == unchanged ]]; then
    printf 'frame changed (allowed): %s (%s)\n' "$label" "$reason" | tee -a "$log"; return 0
  fi
  if [[ "$expectation" == changed && "$(awk -v ratio="$ratio" 'BEGIN { print (ratio >= 0.01) ? 1 : 0 }')" != 1 ]]; then
    fail "$label: only ${ratio} of pixels changed by >=16 per channel; expected at least 0.01"; return 1
  fi
  if [[ "$expectation" == unchanged ]]; then
    printf 'frame changed (allowed): %s (%s)\n' "$label" "$reason" | tee -a "$log"
  else
    printf 'frame changed: %s (pixel difference only; semantic effect still requires inspection)\n' "$label" | tee -a "$log"
  fi
}

lock_state_is_unlocked() {
  local rc="$1" output="$2"
  (( rc == 0 )) || return 1
  print -r -- "$output" | grep -Eq '(^|[[:space:]])passcodeRequired:[[:space:]]*false([[:space:]]|$)'
}
