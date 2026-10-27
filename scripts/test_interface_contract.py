#!/usr/bin/env python3
"""Synthetic baseline/contract regressions. Never import device dependencies."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sources"))
import ipb_ax


def invoke(case, results, error_format=None):
    """Run only main's formatter/exit mapping, with no event loop or phone."""
    def fake_run(coro):
        coro.close()
        if "error" in case:
            error = case["error"]
            raise {"ValueError": ValueError, "TimeoutError": TimeoutError,
                   "CancelledError": ipb_ax.asyncio.CancelledError}[error["type"]](error["message"])
        return results[case["result"]]

    # asyncio.run receives the bounded coroutine; populate its captured args
    # before returning/raising, rather than running any device code.
    def run_with_state(coro):
        args = coro.cr_frame.f_locals["args"]
        for key, value in case.get("state", {}).items():
            setattr(args, key, value)
        return fake_run(coro)

    env = {**os.environ, "IPB_AX_DEVICE_ID": "fixture-device", "IPB_AX_UDID": "fixture-usb",
           "IPB_AX_CLI": "/fixture/ipb"}
    env.pop("IPB_ERROR_FORMAT", None)
    if error_format is not None:
        env["IPB_ERROR_FORMAT"] = error_format
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["ipb ui", *case["argv"]]), \
         patch.object(ipb_ax, "version", return_value=case.get("dependency", "11.10.2")), \
         patch.object(ipb_ax.asyncio, "run", side_effect=run_with_state), \
         redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = ipb_ax.main()
        except SystemExit as error:
            code = error.code
    return {"code": code, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}


class DefaultGoldenTests(unittest.TestCase):
    def test_default_stdout_stderr_and_exit_match_committed_baseline(self):
        fixture = json.loads((ROOT / "docs/contracts/ax-default-v050.golden.json").read_text())
        for case in fixture["cases"]:
            for error_format in (None, "text", "JSON"):
                with self.subTest(case=case["name"], error_format=error_format):
                    self.assertEqual(invoke(case, fixture["results"], error_format), case["expected"])

    def test_shared_example_and_schema_agree(self):
        folder = ROOT / "docs/contracts"
        example = json.loads((folder / "ipb-error-v1.example.json").read_text())
        schema = json.loads((folder / "ipb-error-v1.schema.json").read_text())
        self.assertEqual(set(example), set(schema["required"]))
        self.assertEqual(example["kind"], schema["properties"]["kind"]["const"])
        self.assertEqual(example["contractVersion"], schema["properties"]["contractVersion"]["const"])
        self.assertIn(example["action"]["state"], schema["properties"]["action"]["oneOf"][1]["properties"]["state"]["enum"])


if __name__ == "__main__":
    unittest.main()
