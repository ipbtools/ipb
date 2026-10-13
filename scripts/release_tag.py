"""Versioned release tags and the explicitly separate disposable branch-test lane."""
import datetime
import re

VERSION = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
STABLE = re.compile(r"v(?P<version>" + VERSION + r")$")
BRANCH_TEST = re.compile(r"release-test-v(?P<version>" + VERSION + r")-(?P<timestamp>[0-9]{14})$")


def parse_tag(tag, expected_version=None):
    match = STABLE.fullmatch(tag)
    kind = "release-candidate"
    if match is None:
        match = BRANCH_TEST.fullmatch(tag)
        kind = "branch-release-test"
        if match:
            datetime.datetime.strptime(match["timestamp"], "%Y%m%d%H%M%S")
    if match is None:
        raise ValueError("expected vX.Y.Z or release-test-vX.Y.Z-YYYYMMDDHHMMSS")
    version = match["version"]
    if expected_version is not None and version != expected_version:
        raise ValueError("release tag must match VERSION")
    return kind, version
