#!/usr/bin/env python3
"""Offline release safeguards: never overwrite published assets or lose HEAD."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from draft_release import draft
from render_formula import render_formula
from release_tag import parse_tag

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipb-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        (self.output / "BUILD_INFO.json").write_text(json.dumps({"kind": "release-candidate",
            "version": "0.2.0", "releaseTag": "v0.2.0", "commit": "a" * 40}))
        (self.output / "ipb-0.2.0-macos27-arm64.tar.gz").write_bytes(b"fixture")
        self.calls = []

    def run_draft(self, reply):
        def fake(*args):
            self.calls.append(args)
            if args[0] == "api":
                return reply
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch("draft_release.gh", fake), patch.dict(os.environ, GITHUB_REPOSITORY="ipbtools/ipb"):
            draft(self.output)

    def test_published_release_has_no_write(self):
        with self.assertRaisesRegex(ValueError, "published"):
            self.run_draft(subprocess.CompletedProcess([], 0, '{"draft":false}', ""))
        self.assertEqual([x[0] for x in self.calls], ["api"])

    def test_permission_error_does_not_create(self):
        with self.assertRaises(RuntimeError):
            self.run_draft(subprocess.CompletedProcess([], 1, "", "HTTP 403 Forbidden"))
        self.assertEqual([x[0] for x in self.calls], ["api"])

    def test_missing_release_creates_draft_at_existing_tag(self):
        self.run_draft(subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found"))
        create = next(x for x in self.calls if x[:2] == ("release", "create"))
        self.assertIn("--draft", create)
        self.assertIn("--verify-tag", create)
        upload = next(x for x in self.calls if x[:2] == ("release", "upload"))
        self.assertIn(str(self.output / "BUILD_INFO.json"), upload)
        self.assertNotIn(str(self.output / "release-notes.md"), upload)

    def test_existing_draft_uploads_without_publishing(self):
        self.run_draft(subprocess.CompletedProcess([], 0, '{"draft":true}', ""))
        self.assertEqual([x[:2] for x in self.calls], [("api", "repos/ipbtools/ipb/releases/tags/v0.2.0"),
                                                     ("release", "upload")])

    def test_ci_package_cannot_be_released(self):
        (self.output / "BUILD_INFO.json").write_text(json.dumps({"kind": "ci-test-package",
            "version": "0.2.0", "releaseTag": "v0.2.0"}))
        with self.assertRaises(ValueError):
            self.run_draft(subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found"))
        self.assertEqual(self.calls, [])

    def test_branch_test_creates_only_explicit_prerelease_draft(self):
        tag = "release-test-v0.2.0-20261012160000"
        (self.output / "BUILD_INFO.json").write_text(json.dumps({"kind": "branch-release-test",
            "version": "0.2.0", "releaseTag": tag, "commit": "a" * 40}))
        self.run_draft(subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found"))
        create = next(x for x in self.calls if x[:2] == ("release", "create"))
        for option in ("--draft", "--verify-tag", "--prerelease", "--latest=false"):
            self.assertIn(option, create)
        self.assertIn("deletable", create[create.index("--title") + 1])

    def test_branch_tag_cannot_claim_stable_candidate_kind(self):
        (self.output / "BUILD_INFO.json").write_text(json.dumps({"kind": "release-candidate",
            "version": "0.2.0", "releaseTag": "release-test-v0.2.0-20261012160000"}))
        with self.assertRaises(ValueError):
            self.run_draft(subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found"))
        self.assertEqual(self.calls, [])

    def test_tag_parser_keeps_version_and_lane_separate(self):
        self.assertEqual(parse_tag("v0.2.0", "0.2.0"), ("release-candidate", "0.2.0"))
        self.assertEqual(parse_tag("release-test-v0.2.0-20261012160000", "0.2.0"),
                         ("branch-release-test", "0.2.0"))
        for tag in ("v0.2.1", "release-test-v0.2.1-20261012160000", "release-test-v0.2.0-20261399160000", "main"):
            with self.assertRaises(ValueError):
                parse_tag(tag, "0.2.0")

    def test_branch_formula_pins_test_url_without_changing_product_version(self):
        source = (ROOT / "Formula/ipb.rb").read_text()
        tag = "release-test-v0.2.0-20261012160000"
        formula = render_formula(source, tag, "b" * 64)
        self.assertIn(f"releases/download/{tag}/ipb-0.2.0-macos27-arm64.tar.gz", formula)
        self.assertIn('version "0.2.0"', formula)

    def test_formula_pins_archive_and_preserves_head(self):
        source = (ROOT / "Formula/ipb.rb").read_text()
        result = render_formula(source, "v0.2.0", "b" * 64)
        self.assertIn('url "https://github.com/ipbtools/ipb/releases/download/v0.2.0/ipb-0.2.0-macos27-arm64.tar.gz"', result)
        self.assertIn('sha256 "' + "b" * 64 + '"', result)
        self.assertIn('url "https://github.com/ipbtools/ipb.git", branch: "main"', result)
        self.assertEqual(result.count("  head do"), 1)
        for tag, sha in (("main", "b" * 64), ("v0.2.0;bad", "b" * 64), ("v0.2.0", "not-a-hash")):
            with self.assertRaises(ValueError):
                render_formula(source, tag, sha)


if __name__ == "__main__":
    unittest.main()
