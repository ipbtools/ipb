#!/bin/sh
# Reusable host regressions. No phone socket, mirror window or real clipboard.
set -eu
cd "$(dirname "$0")/.."
python3 scripts/test_ax.py
python3 scripts/test_device_features.py
python3 scripts/test_update_host_only.py
sh scripts/test_bounded_sender.sh
zsh scripts/test_smoke_matrix.sh
zsh -n bin/ipb completions/_ipb scripts/smoke_matrix.sh
ruby -c Formula/ipb.rb

out="$(mktemp -d "${TMPDIR:-/tmp}/ipb-host-tests.XXXXXX")"
trap 'rm -rf "$out"' EXIT
clang -std=c11 -Wall -Wextra -Werror scripts/test_keyboard_input.c -o "$out/keyboard"
"$out/keyboard"
clang -fobjc-arc -fblocks -framework Foundation scripts/test_display_geometry.m -o "$out/geometry"
"$out/geometry"
clang -fobjc-arc -fblocks -framework Foundation scripts/test_device_control.m -o "$out/device-control"
"$out/device-control"
build/test-input-reports
build/test-mirror-keyboard
