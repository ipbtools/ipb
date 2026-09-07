# Homebrew formula for hdb (HID / Hub Debug Bridge for iOS).
# Install from a tap:  brew tap <owner>/hdb <repo-url> && brew install --HEAD hdb
# Build needs Xcode 27 beta selected (xcode-select or DEVELOPER_DIR); runtime needs the
# CoreDevice package that Xcode 27 beta installs (/Library/Developer/PrivateFrameworks).
class Hdb < Formula
  desc "Drive a physical iPhone from a Mac like adb: tap, swipe, keys, home, screenshot"
  homepage "https://github.com/borealin/devicehubctl"
  head "https://github.com/borealin/devicehubctl.git", branch: "main"
  license :cannot_represent # set once the project LICENSE is decided

  depends_on :macos
  depends_on xcode: :build

  def install
    system "make"
    system "make", "install", "PREFIX=#{prefix}"
  end

  def caveats
    <<~EOS
      hdb needs CoreDevice 642.x (installed by Xcode 27 beta) on the host and an
      iOS 27 or iOS 26.6+ device paired over USB. Run `hdb version` and
      `hdb service-ids` first; `hdb descriptors` verifies the device path.
    EOS
  end

  test do
    assert_match "hdb", shell_output("#{bin}/hdb version")
  end
end
