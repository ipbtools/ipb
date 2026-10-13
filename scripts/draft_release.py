#!/usr/bin/env python3
"""Attach a verified candidate only to an unpublished GitHub Draft Release."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from release_tag import parse_tag


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)


def draft(package_dir):
    info = json.loads((package_dir / "BUILD_INFO.json").read_text())
    tag = info["releaseTag"]
    kind, _ = parse_tag(tag, info["version"])
    if info["kind"] != kind:
        raise ValueError("expected a versioned release candidate")
    branch_test = kind == "branch-release-test"
    repo = os.environ["GITHUB_REPOSITORY"]
    existing = gh("api", f"repos/{repo}/releases/tags/{tag}")
    if existing.returncode == 0:
        if not json.loads(existing.stdout)["draft"]:
            raise ValueError("refusing to replace published release assets")
    elif "HTTP 404" not in existing.stderr:
        raise RuntimeError(existing.stderr)
    else:
        notes = package_dir / "release-notes.md"
        notes.write_text(f"""ipb {info['version']} release candidate, commit {info['commit']}.

Provides runner-free AX graphs/element rectangles and mirror keyboard/clipboard controls.
Requires macOS 27 ARM64, compatible Xcode 27 development components and paired iOS 27+.
Optional UI Python dependencies are installed separately; no Apple components are bundled.

This draft contains a native build, host regressions and verified package. Full physical
HID/media/AX acceptance and download behavior must be checked before publishing. Ad-hoc
signatures are used; this is not a Developer ID notarized distribution.

After acceptance, review/edit these notes, publish the draft, then run the tap's Prepare
stable formula workflow with this tag. Its output branch requires a reviewed PR/merge.
""")
        if branch_test:
            notes.write_text(f"""Disposable branch release test for ipb {info['version']}, commit {info['commit']}.

This prerelease tests GitHub Actions build, draft creation, asset upload, publication,
public download/checksum and precompiled Homebrew installation. It is not a supported
physical-device release. It does not update main, Latest, or the stable Homebrew tap.

Delete this release and tag after testing if desired. Package host requirements and
verification scope are recorded in BUILD_INFO.json and TEST_PACKAGE.md.
""")
        title = f"ipb {info['version']} branch release test (deletable)" if branch_test else f"ipb {info['version']}"
        options = ["--prerelease", "--latest=false"] if branch_test else []
        created = gh("release", "create", tag, "--repo", repo, "--draft", "--verify-tag",
                     "--title", title, "--notes-file", str(notes), *options)
        if created.returncode:
            raise RuntimeError(created.stderr)
    assets = [p for p in package_dir.iterdir() if p.is_file() and p.name != "release-notes.md"]
    result = gh("release", "upload", tag, *map(str, assets), "--repo", repo, "--clobber")
    if result.returncode:
        raise RuntimeError(result.stderr)
    print(f"Draft release assets prepared for {repo} {tag}; publication remains manual")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    draft(parser.parse_args().package_dir.resolve())
