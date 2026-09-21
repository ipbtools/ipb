#!/bin/sh
set -eu

out="${TMPDIR:-/tmp}/ipb-bounded-sender-test.$$"
trap 'rm -f "$out"' EXIT
clang -fblocks -std=c11 -Wall -Wextra -Werror -I Sources \
  scripts/test_bounded_sender.m -lobjc -o "$out"
"$out"
