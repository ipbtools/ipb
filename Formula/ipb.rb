# Homebrew formula for ipb (iOS Physical-device Bridge).
# Install:  brew tap ipbtools/ipb && brew install --HEAD ipb
# Build needs Xcode 27 beta selected (xcode-select or DEVELOPER_DIR); runtime needs the
# CoreDevice package that Xcode 27 beta installs (/Library/Developer/PrivateFrameworks).
class Ipb < Formula
  desc "Drive a physical iPhone from a Mac like adb: tap, swipe, keys, home, screenshot"
  homepage "https://github.com/ipbtools/ipb"
  head "https://github.com/ipbtools/ipb.git", branch: "main"
  license "MIT"

  depends_on :macos
  depends_on xcode: :build

  def install
    system "make"
    system "make", "install", "PREFIX=#{prefix}"
  end

  def caveats
    <<~EOS
      ipb needs CoreDevice 642.x (installed by Xcode 27 beta) on the host and an
      iOS 27 or iOS 26.6+ device paired over USB, unlocked, Developer Mode on.
      Start with `ipb doctor`; it checks every layer and names the next step.
    EOS
  end

  test do
    assert_match "ipb", shell_output("#{bin}/ipb version")
  end
end
