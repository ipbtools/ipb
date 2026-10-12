#!/usr/bin/env python3
"""Pin the maintained formula to one release archive without changing HEAD."""
import re


def render_formula(source, tag, sha256):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("expected a release tag vX.Y.Z")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("expected an archive SHA256")
    anchor = "  head do\n"
    if source.count(anchor) != 1:
        raise ValueError("maintained formula must have one HEAD block")
    version = tag[1:]
    stable = (f'  url "https://github.com/ipbtools/ipb/releases/download/{tag}/ipb-{version}-macos27-arm64.tar.gz"\n'
              f'  version "{version}"\n'
              f'  sha256 "{sha256}"\n')
    return source.replace(anchor, stable + anchor)
