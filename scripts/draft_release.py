#!/usr/bin/env python3
"""Attach a verified candidate only to an unpublished GitHub Draft Release."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)


def draft(package_dir):
    info = json.loads((package_dir / "BUILD_INFO.json").read_text())
    tag = info["releaseTag"]
    if info["kind"] != "release-candidate" or tag != "v" + info["version"]:
        raise ValueError("expected a versioned release candidate")
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
        created = gh("release", "create", tag, "--repo", repo, "--draft", "--verify-tag",
                     "--title", f"ipb {info['version']}", "--notes-file", str(notes))
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
