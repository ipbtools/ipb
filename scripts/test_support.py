#!/usr/bin/env python3
"""Host-only support CLI regressions; every Apple entry point is a failing fake."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import package_test_build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sources"))
import ipb_support


class SupportTests(unittest.TestCase):
    def test_capabilities_keeps_its_original_json_and_query_failure(self):
        with tempfile.TemporaryDirectory(prefix="ipb-capabilities-") as tmp:
            directory = Path(tmp)
            fake = directory / "devicectl"
            fake.write_text(f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
                            "a=sys.argv[1:]\nassert a[:3]==['device','info','details']\n"
                            "if os.environ.get('IPB_TEST_FAIL'): sys.exit(17)\n"
                            "Path(a[a.index('--json-output')+1]).write_text(json.dumps({'result':{'capabilities':[{'featureIdentifier':'fixture.feature','name':'fixture feature'}]}}))\n")
            fake.chmod(0o755)
            device = "00000000-0000-0000-0000-000000000001"
            env = {**os.environ, "DEVELOPER_DIR": "/unused", "DEVICECTL": str(fake),
                   "IPB_HELPER": str(fake), "IPB_ERROR_FORMAT": "json"}
            argv = [str(ROOT / "bin/ipb"), "-s", device, "capabilities", "--json"]
            observed = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            expected = {"schemaVersion": 1, "deviceIdentifier": device,
                        "capabilities": [{"featureIdentifier": "fixture.feature", "name": "fixture feature"}]}
            self.assertEqual(observed.stdout, json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
            observed = subprocess.run(argv, env={**env, "IPB_TEST_FAIL": "1"}, capture_output=True, text=True, timeout=5)
            self.assertEqual(observed.returncode, 17)
            self.assertEqual(observed.stdout, "")

    def test_inventory_separates_implementation_advertisement_and_verification(self):
        payload = ipb_support.support_document()
        schema = json.loads((ROOT / "docs/contracts/ipb-support-v1.schema.json").read_text())
        self.assertEqual(set(payload), set(schema["required"]))
        self.assertEqual(payload["kind"], "ipb.support")
        self.assertEqual(payload["contractVersion"], 1)
        self.assertEqual(payload["deviceQuery"], {"status": "not-requested", "deviceIdentifier": None})
        self.assertEqual(payload["supportedMatrix"]["status"], "unverified")
        names = [record["operation"] for record in payload["operations"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("ui.input", names)
        self.assertIn("screenshot", names)
        for record in payload["operations"]:
            self.assertIn(record["status"], ("unverified", "unsupported"))
            self.assertEqual(record["status"], "unverified" if record["implementation"]["present"] else "unsupported")
            self.assertEqual(record["advertisement"], {"status": "unknown", "data": None, "reason": "not queried"})
            self.assertEqual(record["verification"]["records"], [])
            self.assertTrue(record["reason"] and record["scope"])
            self.assertTrue(all(isinstance(value, str) for value in record["prerequisites"]))
        unsupported = {r["operation"] for r in payload["operations"] if r["status"] == "unsupported"}
        self.assertEqual(unsupported, {"ui.slider", "ui.picker", "ui.selection", "multitouch"})

    def test_source_and_installed_commands_never_query_even_with_selector_or_query_failure(self):
        with tempfile.TemporaryDirectory(prefix="ipb-support-") as tmp:
            directory = Path(tmp)
            calls = directory / "calls"
            fake = directory / "forbidden-apple-command"
            fake.write_text(f"#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n"
                            "with Path(os.environ['IPB_TEST_CALLS']).open('a') as f: f.write('unexpected device command\\n')\n"
                            "sys.exit(97)\n")
            fake.chmod(0o755)
            for name in ("devicectl", "xcrun"):
                (directory / name).symlink_to(fake)
            # Exercise the real install recipe without rebuilding/signing native
            # code. Every native file here is the same failing host-only fake.
            signing = directory / "codesign"
            signing.write_text("#!/bin/sh\nexit 0\n")
            signing.chmod(0o755)
            installed = directory / "installed"
            env = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                   "DEVELOPER_DIR": "/unused", "DEVICECTL": str(fake), "IPB_HELPER": str(fake),
                   "IPB_TEST_CALLS": str(calls), "DEVICE_ID": "ambiguous fake selector",
                   "IPB_ERROR_FORMAT": "json", "IPB_AX_PYTHON": "/missing-optional-python"}
            make_env = {**env}
            make_env.pop("DEVELOPER_DIR", None)  # Let macOS's make launcher find the host tool.
            result = subprocess.run(["make", "-s", "-o", "all", "install", f"PREFIX={installed}",
                            f"TARGET={fake}", f"VIDEO_TARGET={fake}", f"MIRROR_TARGET={fake}",
                            "XCODE_PATH=/unused"], cwd=ROOT, env=make_env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(package_test_build.files_under(installed), package_test_build.INSTALL_FILES)
            self.assertTrue((installed / "libexec/ipb-support.py").is_file())
            archive = directory / "package.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(installed, arcname="ipb")
            with tarfile.open(archive) as tar:
                tar.extractall(directory / "extracted", filter="data")
            installed = directory / "extracted/ipb"
            self.assertEqual((installed / "libexec/ipb-support.py").stat().st_mode & 0o111, 0o111)
            with patch.dict(os.environ, env, clear=True):
                package_test_build.verify_support(installed / "bin/ipb")
            with patch.object(package_test_build, "run", return_value='{"kind":"other","contractVersion":1}'):
                with self.assertRaisesRegex(ValueError, "support contract mismatch"):
                    package_test_build.verify_support(installed / "bin/ipb")
            for wrapper in (ROOT / "bin/ipb", installed / "bin/ipb"):
                for selector in ([], ["-s", "missing device"], ["--device=ambiguous"]):
                    with self.subTest(wrapper=str(wrapper), selector=selector):
                        observed = subprocess.run([str(wrapper), *selector, "support", "--json"], env=env,
                                                  capture_output=True, text=True, timeout=5)
                        self.assertEqual(observed.returncode, 0, observed.stderr)
                        self.assertEqual(observed.stderr, "")
                        self.assertEqual(json.loads(observed.stdout), ipb_support.support_document())
                        self.assertFalse(calls.exists())
                for argv in ([], ["--json", "extra"], ["--probe"], ["--json", "--device", "x"]):
                    observed = subprocess.run([str(wrapper), "support", *argv], env=env,
                                              capture_output=True, text=True, timeout=5)
                    self.assertEqual(observed.returncode, 2)
                    self.assertEqual(observed.stdout, "")
                    self.assertIn("usage: ipb support --json", observed.stderr)
                    self.assertFalse(calls.exists())
            # A stale package must fail locally, without a checkout fallback.
            (installed / "libexec/ipb-support.py").unlink()
            observed = subprocess.run([str(installed / "bin/ipb"), "support", "--json"], env=env,
                                      capture_output=True, text=True, timeout=5)
            self.assertEqual(observed.returncode, 2)
            self.assertIn("support helper is missing", observed.stderr)
            self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()
