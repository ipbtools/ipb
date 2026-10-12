#!/bin/sh
set -eu
test "$(uname -m)" = arm64
test "$(sw_vers -productVersion | cut -d. -f1)" = 27
xcodebuild -version
xcodebuild -version | head -1 | /usr/bin/grep -Eq '^Xcode 27[.]'
sudo xcodebuild -runFirstLaunch
test -d "$DEVELOPER_DIR/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/PrivateFrameworks"
for framework in /Library/Developer/PrivateFrameworks/CoreDevice.framework \
  /Library/Developer/PrivateFrameworks/CoreDeviceUtilities.framework \
  /Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework \
  /Library/Apple/System/Library/PrivateFrameworks/Mercury.framework; do
  test -d "$framework" || { echo "Missing framework: $framework" >&2; exit 1; }
done
sw_vers
