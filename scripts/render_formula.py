#!/usr/bin/env python3
"""Pin the maintained formula to one release archive without changing HEAD."""
import re
from release_tag import parse_tag


def render_formula(source, tag, sha256):
    _, version = parse_tag(tag)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("expected an archive SHA256")
    anchor = "  head do\n"
    if source.count(anchor) != 1:
        raise ValueError("maintained formula must have one HEAD block")
    stable = (f'  url "https://github.com/ipbtools/ipb/releases/download/{tag}/ipb-{version}-macos27-arm64.tar.gz"\n'
              f'  version "{version}"\n'
              f'  sha256 "{sha256}"\n')
    return source.replace(anchor, stable + anchor)
