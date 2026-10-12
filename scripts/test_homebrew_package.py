#!/usr/bin/env python3
"""Install a real CI archive via the generated binary formula on the CI VM only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

from render_formula import render_formula

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Homebrew package installation test is restricted to the disposable CI VM")
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("artifacts", type=Path)
parser.add_argument("--published", action="store_true", help="verify and install from the public branch-test Release URL")
args = parser.parse_args()
artifacts = args.artifacts.resolve()
archive, = artifacts.glob("*.tar.gz")
info = json.loads((artifacts / "BUILD_INFO.json").read_text())
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
tag = info.get("releaseTag") or "v" + info["version"]
formula = render_formula((root / "Formula/ipb.rb").read_text(), tag, sha)
url = f'https://github.com/ipbtools/ipb/releases/download/{tag}/ipb-{info["version"]}-macos27-arm64.tar.gz'
if args.published:
    if info["kind"] != "branch-release-test":
        raise ValueError("published install testing requires a disposable branch-test release")
    with urllib.request.urlopen(url + ".sha256", timeout=90) as response:
        if response.read().decode() != f"{sha}  {archive.name}\n":
            raise ValueError("public Release sidecar differs from built archive")
    with urllib.request.urlopen(url, timeout=90) as response:
        if hashlib.sha256(response.read()).hexdigest() != sha:
            raise ValueError("public Release download SHA256 mismatch")
    print("Public Release archive/sidecar downloaded and SHA256 matched")
else:
    formula = formula.replace(url, archive.as_uri())
repo = Path(subprocess.check_output(["brew", "--repository"], text=True).strip())
tap = repo / "Library/Taps/ipbtools/homebrew-ci-package"
if tap.exists():
    raise SystemExit("temporary CI tap already exists")
(tap / "Formula").mkdir(parents=True)
(tap / "Formula/ipb.rb").write_text(formula)
subprocess.run(["git", "init", str(tap)], check=True, stdout=subprocess.DEVNULL)
name = "ipbtools/ci-package/ipb"
env = dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_FROM_API="1", HOMEBREW_NO_ANALYTICS="1")
try:
    subprocess.run(["brew", "install", name], env=env, check=True, timeout=180)
    subprocess.run(["brew", "test", name], env=env, check=True, timeout=60)
    prefix = Path(subprocess.check_output(["brew", "--prefix", name], env=env, text=True).strip())
    for path, digest in info["files"].items():
        # Homebrew owns the license display; all actual installed product files must match.
        if path != "LICENSE" and hashlib.sha256((prefix / path).read_bytes()).hexdigest() != digest:
            raise ValueError("Homebrew installed file differs from CI archive: " + path)
    print("Precompiled Homebrew install/test and product hashes passed")
finally:
    subprocess.run(["brew", "uninstall", "--force", name], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tap)
