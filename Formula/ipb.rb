# Homebrew formula for ipb (iOS Physical-device Bridge).
# The source formula exposes the --HEAD channel. A tagged stable release formula adds
# a pinned prebuilt archive above this block; runtime still needs compatible CoreDevice.
class Ipb < Formula
  desc "Drive a physical iPhone from a Mac like adb: tap, swipe, keys, home, screenshot, live stream, interactive mirror"
  homepage "https://github.com/ipbtools/ipb"
  head do
    url "https://github.com/ipbtools/ipb.git", branch: "main"
  end
  license "MIT"

  depends_on :macos
  depends_on xcode: :build if build.head?

  def install
    if build.head?
      system "make"
      system "make", "install", "PREFIX=#{prefix}"
    else
      odie "the prebuilt ipb release supports ARM64 only" unless Hardware::CPU.arm64?
      odie "the prebuilt ipb release requires macOS 27" if MacOS.version.major != 27

      %w[bin libexec share].each do |directory|
        odie "release package is missing #{directory}/" unless Pathname.new(directory).directory?
      end
      prefix.install "bin", "libexec", "share"
      prefix.install "BUILD_INFO.json" if File.file?("BUILD_INFO.json")
    end
  end

  def caveats
    <<~EOS
      ipb needs CoreDevice 636.x or newer (verified seed: 642.15, from Xcode 27 beta) and an
      iOS 27+ device paired over USB, unlocked, Developer Mode on.
      Start with `ipb doctor`; it checks every layer and names the next step.

      `ipb stream` (live screen frames) additionally needs to run in a normal GUI
      login session -- it decodes in-process and that needs a display. It works
      with SIP enabled and needs no special entitlement. Over ssh it will fail with
      "VideoReceiver startVideo failed"; run it from the desktop session instead
      (from ssh: `open -a Terminal <script>`).

      `ipb mirror` also requires a GUI login session: in-process decoding needs
      CVDisplayLink. It is unavailable over plain ssh; use the desktop session.

      The tagged stable formula installs the pinned prebuilt macOS 27 ARM64
      package. The `--HEAD` channel builds current main and requires Xcode 27 for build.
      Both channels require compatible Apple CoreDevice components at runtime; neither
      installs Xcode components or Python dependencies automatically.

      For a source revision that includes `ipb ui`, Python 3.11+ and the optional
      dependency in #{share}/ipb/requirements-ax.txt are needed. See docs/ui.md;
      no Python packages or phone application are installed automatically.

      Update later with `ipb update`.
    EOS
  end

  test do
    assert_match "ipb", shell_output("#{bin}/ipb version")
  end
end
