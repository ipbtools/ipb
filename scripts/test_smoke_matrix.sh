#!/usr/bin/env zsh
# Host-only regression fixtures for the smoke gate. No device, DeviceHub, or
# mirror process is started; the gate's own assertion functions are exercised.
set -u
ROOT="${0:A:h:h}"
OUT="$(mktemp -d /tmp/ipb-smoke-fixtures.XXXXXX)"
trap 'rm -rf "$OUT"' EXIT
log="$OUT/test.log"; : > "$log"; failures=0
fail() { failures=$((failures + 1)); print -r -- "FAIL: $*" | tee -a "$log"; }
PNG_DIGEST="$ROOT/scripts/png_pixels_digest.py"
source "$ROOT/scripts/smoke_assertions.zsh"
test_dir="$OUT/fixtures"; mkdir -p "$test_dir"
print -r -- 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAADXRFWHRjYXB0dXJlAGZpcnN04HWsnwAAABVJREFUeJxjFNGw+c/AwMDABCJAGAAVgAF7fIOmOAAAAABJRU5ErkJggg==' | base64 -D > "$test_dir/same-a.png"
print -r -- 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAADnRFWHRjYXB0dXJlAHNlY29uZCPSX6kAAAAVSURBVHicYxTRsPnPwMDAwAQiQBgAFYABe3yDpjgAAAAASUVORK5CYII=' | base64 -D > "$test_dir/same-b.png"
print -r -- 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEXRFWHRjYXB0dXJlAGRpZmZlcmVudHaHyrAAAAAVSURBVHicYxTVsPnPwMDAwAQiQBgAFZEBfIwL3RMAAAAASUVORK5CYII=' | base64 -D > "$test_dir/different.png"
python3 - "$test_dir" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
width = height = 100
for name, box in (("large-base", None), ("localized", (10, 10, 11, 11)), ("material", (10, 10, 30, 30))):
    pixels = bytearray([20, 40, 60] * width * height)
    if box:
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                i = (y * width + x) * 3
                pixels[i:i + 3] = bytes((220, 220, 220))
    (out / (name + ".ppm")).write_bytes(b"P6\n100 100\n255\n" + pixels)
PY
for name in large-base localized material; do sips -s format png "$test_dir/$name.ppm" --out "$test_dir/$name.png" >/dev/null; done
check_frame_transition "metadata-only fixture" "$test_dir/same-a.png" "$test_dir/same-b.png" unchanged "no-op fixture explicitly allowed" || exit 1
before_failures=$failures
if check_frame_transition "negative unchanged fixture" "$test_dir/same-a.png" "$test_dir/same-b.png" changed "must reject silent no-op"; then
  print -u2 'negative unchanged fixture unexpectedly passed'; exit 1
fi
(( failures > before_failures )) || { print -u2 'negative unchanged fixture did not record a failure'; exit 1; }
failures=0
if check_frame_transition "localized clock-like fixture" "$test_dir/large-base.png" "$test_dir/localized.png" changed "small local updates must not count as a screen transition"; then
  print -u2 'localized fixture unexpectedly passed'; exit 1
fi
failures=0
check_frame_transition "material transition fixture" "$test_dir/large-base.png" "$test_dir/material.png" changed "material screen transition" || exit 1
if lock_state_is_unlocked 0 'passcodeRequired: false'; then :; else fail 'false lock-state was rejected'; fi
if lock_state_is_unlocked 0 'passcodeRequired: true'; then fail 'true lock-state was accepted'; fi
if lock_state_is_unlocked 1 'passcodeRequired: false'; then fail 'error lock-state was accepted'; fi
if lock_state_is_unlocked 0 'unexpected response'; then fail 'unknown lock-state was accepted'; fi
(( failures == 0 )) && print 'smoke assertion fixtures passed'
layout="$OUT/prefix/share"
mkdir -p "$layout/ipb" "$layout/zsh/site-functions"
cp "$ROOT/scripts/smoke_assertions.zsh" "$layout/ipb/"
cp "$ROOT/scripts/png_pixels_digest.py" "$layout/ipb/"
cp "$ROOT/completions/_ipb" "$layout/zsh/site-functions/"
ROOT="$OUT/prefix" SCRIPT_DIR="$layout/ipb" PNG_DIGEST="$layout/ipb/png_pixels_digest.py" \
  zsh -c 'source "$SCRIPT_DIR/smoke_assertions.zsh" || exit; fpath=("$SCRIPT_DIR/../zsh/site-functions" $fpath); autoload -Uz _ipb; autoload +X _ipb' || exit 1
print 'installed-layout helper and completion fixture passed'
exit "$failures"
