#!/usr/bin/env python3
"""Stage only ipb-owned install files and verify the final CI tarball on the host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import tempfile

from release_tag import parse_tag

ROOT = Path(__file__).resolve().parents[1]
INSTALL_FILES = {
    "bin/ipb", "libexec/ipb-helper", "libexec/ipb-video", "libexec/ipb-mirror",
    "libexec/ipb-ax.py", "libexec/ax_archive.py", "share/ipb/requirements-ax.txt",
    "share/ipb/VERSION", "share/ipb/smoke_matrix.sh", "share/ipb/smoke_assertions.zsh",
    "share/ipb/png_pixels_digest.py", "share/ipb/assert_search_text.swift",
    "share/zsh/site-functions/_ipb",
}
EXTRAS = {"LICENSE", "BUILD_INFO.json", "TEST_PACKAGE.md"}
BINARIES = ("ipb-helper", "ipb-video", "ipb-mirror")
EXECUTABLES = {"bin/ipb", "libexec/ipb-ax.py", *("libexec/" + x for x in BINARIES),
               "share/ipb/smoke_matrix.sh", "share/ipb/smoke_assertions.zsh",
               "share/ipb/png_pixels_digest.py"}


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=120).strip()


def files_under(prefix):
    paths = list(prefix.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("unexpected symlink in package")
    return {p.relative_to(prefix).as_posix() for p in paths if p.is_file()}


def verify(prefix):
    if files_under(prefix) != INSTALL_FILES | EXTRAS:
        raise ValueError("package file list differs from the ipb install contract")
    for name in EXECUTABLES:
        if (prefix / name).stat().st_mode & 0o111 != 0o111:
            raise ValueError("executable mode missing: " + name)
    deps = {}
    for name in BINARIES:
        binary = prefix / "libexec" / name
        if run("lipo", "-archs", str(binary)) != "arm64":
            raise ValueError("unexpected architecture: " + name)
        run("codesign", "--verify", "--strict", str(binary))
        deps[name] = run("otool", "-L", str(binary)).splitlines()[1:]
    return deps


def package(output, release_tag=None):
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty")
    revision = run("git", "rev-parse", "HEAD")
    if run("git", "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked source changes must be committed before packaging")
    version = (ROOT / "VERSION").read_text().strip()
    if not version or any(c not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-" for c in version):
        raise ValueError("invalid VERSION for package filename")
    kind = "ci-test-package"
    if release_tag:
        kind, _ = parse_tag(release_tag, version)
        if run("git", "rev-parse", "refs/tags/" + release_tag + "^{commit}") != revision:
            raise ValueError("release tag does not identify this checkout")
    name = f"ipb-{version}-macos27-arm64" if release_tag else f"ipb-{version}-ci.{revision[:12]}-macos27-arm64"
    with tempfile.TemporaryDirectory(prefix="ipb-package-") as tmp:
        prefix = Path(tmp) / name
        subprocess.run(["make", "install", f"PREFIX={prefix}"], cwd=ROOT, check=True, timeout=120)
        if files_under(prefix) != INSTALL_FILES:
            raise ValueError("make install file list differs from the package contract")
        shutil.copyfile(ROOT / "LICENSE", prefix / "LICENSE")
        # Hash only after install has finished its ad-hoc signing.
        hashes = {p: hashlib.sha256((prefix / p).read_bytes()).hexdigest() for p in sorted(INSTALL_FILES | {"LICENSE"})}
        info = {
            "schemaVersion": 1, "kind": kind, "version": version, "releaseTag": release_tag, "commit": revision,
            "pullRequestHead": os.environ.get("IPB_PR_HEAD") or None,
            "runUrl": (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                       if os.environ.get("GITHUB_RUN_ID") else None),
            "os": {key.strip(): value.strip() for key, value in (line.split(":", 1) for line in run("sw_vers").splitlines())},
            "architecture": run("uname", "-m"),
            "xcode": run("xcodebuild", "-version"),
            "coreDevice": plistlib.loads(Path("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Resources/Info.plist").read_bytes()).get("CFBundleVersion"),
            "files": hashes,
            "verification": "native build, host regressions and extracted package startup; no physical device gate",
            "runtimeRequirements": "macOS 27 ARM64, compatible Xcode 27 Apple development components, paired iOS 27+; UI additionally needs optional host Python dependencies",
        }
        (prefix / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
        (prefix / "TEST_PACKAGE.md").write_text("""# ipb package

This package has passed host checks only; it does not prove physical-device acceptance. BUILD_INFO.json identifies the
built commit, PR head, compiler environment and file hashes. No Apple framework,
DDI or Python dependency is bundled. Compatible Apple development components
must already be installed; see https://github.com/ipbtools/ipb#requirements.

After downloading the Actions artifact, unzip it, verify with
`shasum -a 256 -c *.sha256`, then extract the `.tar.gz`. Run the extracted
`bin/ipb version` and `bin/ipb help` by their full paths. Helpers resolve relative
to that bin directory; keep bin, libexec and share together. Avoid replacing
an existing installation while trying the package. To use UI reads, install the
optional requirements in share/ipb/requirements-ax.txt in your own Python
virtual environment, as described in docs/ui.md in the source repository.

Mirror/stream require a GUI login session. Physical device functionality and
browser-download quarantine behavior are not proven by host CI. This package
uses ad-hoc signatures, not Developer ID signing or notarization. Fetch a newer
CI package to update this extracted copy; `ipb update` does not upgrade it.
""")
        info["dependencies"] = verify(prefix)
        (prefix / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
        archive = output / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(prefix, arcname=name)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output / (archive.name + ".sha256")).write_text(f"{digest}  {archive.name}\n")
        extracted = Path(tmp) / "extracted"
        with tarfile.open(archive) as tar:
            tar.extractall(extracted, filter="data")
        installed = extracted / name
        verify(installed)
        for path, expected in hashes.items():
            if hashlib.sha256((installed / path).read_bytes()).hexdigest() != expected:
                raise ValueError("extracted file hash mismatch: " + path)
        cli = installed / "bin" / "ipb"
        if f"ipb {version}" not in run(str(cli), "version"):
            raise ValueError("installed CLI version mismatch")
        run(str(cli), "help")
        run(str(cli), "help", "hid")
        # Start each Mach-O without device arguments; usage errors are expected,
        # but loader errors, crashes and missing private symbols must fail CI.
        for binary in BINARIES:
            result = subprocess.run([str(installed / "libexec" / binary)], capture_output=True, text=True, timeout=10)
            expected = "no device identifier given" if binary == "ipb-helper" else "usage:"
            if result.returncode != 2 or expected not in (result.stdout + result.stderr).lower():
                raise ValueError(f"{binary} host startup failed: rc={result.returncode} {result.stdout} {result.stderr}")
        shutil.copyfile(installed / "BUILD_INFO.json", output / "BUILD_INFO.json")
        shutil.copyfile(installed / "TEST_PACKAGE.md", output / "TEST_PACKAGE.md")
        if release_tag:
            from render_formula import render_formula
            (output / "ipb.rb").write_text(render_formula((ROOT / "Formula/ipb.rb").read_text(), release_tag, digest))
        print(f"Verified {kind}: {archive.name}\nSHA256: {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--release-tag", help="existing version or release-test tag at this checkout")
    args = parser.parse_args()
    package(args.output.resolve(), args.release_tag)
