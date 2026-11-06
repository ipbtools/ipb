#!/usr/bin/env python3
"""Synthetic baseline/contract regressions. Never import device dependencies."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
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
            raise {"ValueError": ValueError, "RuntimeError": RuntimeError, "TimeoutError": TimeoutError,
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
    for key, value in case.get("env", {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["ipb ui", *case["argv"]]), \
         patch.object(ipb_ax, "version", return_value=case.get("dependency", "11.10.2"),
                      side_effect=ValueError("fixture missing dependency") if case.get("dependencyMissing") else None), \
         patch.object(sys, "version_info", case.get("pythonVersion", sys.version_info)), \
         patch.object(ipb_ax.asyncio, "run", side_effect=run_with_state), \
         redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = ipb_ax.main()
        except SystemExit as error:
            code = error.code
    return {"code": code, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}


def assert_error(test, observed):
    # json.loads rejects a second concatenated JSON document, including the
    # historical native result that must now appear only under result.
    payload = json.loads(observed["stdout"])
    schema = json.loads((ROOT / "docs/contracts/ipb-error-v1.schema.json").read_text())
    test.assertEqual(set(payload), set(schema["required"]))
    for field in ("kind", "contractVersion"):
        test.assertEqual(payload[field], schema["properties"][field]["const"])
    for field in ("operation", "phase", "exitCode"):
        test.assertIn(payload[field], schema["properties"][field]["enum"])
    test.assertEqual(payload["exitCode"], observed["code"])
    test.assertIs(type(payload["retrySafe"]), bool)
    test.assertIsInstance(payload["error"]["type"], str)
    test.assertIsInstance(payload["error"]["message"], str)
    action = payload["action"]
    if action is not None:
        test.assertEqual(set(action), {"state", "native", "childExitCode"})
        test.assertIn(action["state"], schema["properties"]["action"]["oneOf"][1]["properties"]["state"]["enum"])
        test.assertTrue(type(action["native"]) is bool or action["native"] == "unknown")
        test.assertTrue(type(action["childExitCode"]) is int or action["childExitCode"] is None)
        test.assertEqual(payload["retrySafe"], action["state"] == "not-sent")
    else:
        test.assertIn(payload["operation"], ("ui.dump", "ui.hit-test", "ui.locate", "ui.wait"))
        test.assertTrue(payload["retrySafe"])
    return payload


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


class ErrorContractTests(unittest.TestCase):
    def test_launch_passthrough_selects_device_before_app_arguments(self):
        with tempfile.TemporaryDirectory(prefix="ipb-launch-wrapper-") as tmp:
            fake = Path(tmp) / "devicectl"
            fake.write_text(f"#!{sys.executable}\nimport argparse,json,sys\n"
                            "assert sys.argv[1:4] == ['device','process','launch']\n"
                            "p=argparse.ArgumentParser(); p.add_argument('--device',required=True)\n"
                            "p.add_argument('--activate',action='store_true'); p.add_argument('app')\n"
                            "p.add_argument('arguments',nargs=argparse.REMAINDER)\n"
                            "print(json.dumps(vars(p.parse_args(sys.argv[4:]))))\n")
            fake.chmod(0o755)
            device = "00000000-0000-0000-0000-000000000001"
            env = {**os.environ, "DEVELOPER_DIR": "/unused", "DEVICECTL": str(fake), "IPB_HELPER": str(fake)}
            observed = subprocess.run([str(ROOT / "bin/ipb"), "-s", device, "devicectl", "device", "process",
                                       "launch", "--activate", "example.app", "--payload-flag"],
                                      env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(json.loads(observed.stdout), {"device": device, "activate": True,
                             "app": "example.app", "arguments": ["--payload-flag"]})

    def test_source_and_installed_wrappers_pass_the_opt_in_but_leave_zsh_errors_unwrapped(self):
        with tempfile.TemporaryDirectory(prefix="ipb-error-wrapper-") as tmp:
            directory = Path(tmp)
            fake = directory / "devicectl"
            fake.write_text(f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
                            "a=sys.argv[1:]\nassert a[:2]==['list','devices']\n"
                            "if os.environ.get('IPB_TEST_FAIL'): sys.exit(17)\n"
                            "Path(a[a.index('--json-output')+1]).write_text(json.dumps({'result':{'devices':[{'identifier':'00000000-0000-0000-0000-000000000001','hardwareProperties':{'udid':'fixture-usb'}}]}}))\n")
            fake.chmod(0o755)
            installed = directory / "installed"
            (installed / "bin").mkdir(parents=True)
            (installed / "libexec").mkdir()
            for source, target in ((ROOT / "bin/ipb", installed / "bin/ipb"),
                                   (ROOT / "Sources/ipb_ax.py", installed / "libexec/ipb-ax.py"),
                                   (ROOT / "Sources/ax_archive.py", installed / "libexec/ax_archive.py")):
                shutil.copy2(source, target)
            env = {**os.environ, "DEVELOPER_DIR": "/unused", "DEVICECTL": str(fake),
                   "IPB_HELPER": str(fake), "IPB_AX_PYTHON": sys.executable,
                   "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("IPB_ERROR_FORMAT", None)
            for wrapper in (ROOT / "bin/ipb", installed / "bin/ipb"):
                argv = [str(wrapper), "-s", "00000000-0000-0000-0000-000000000001", "ui", "press", "--json"]
                with self.subTest(wrapper=str(wrapper)):
                    default = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=5)
                    self.assertEqual({"code": default.returncode, "stdout": default.stdout, "stderr": default.stderr},
                                     invoke({"argv": ["press", "--json"]}, {}))
                    observed = subprocess.run(argv, env={**env, "IPB_ERROR_FORMAT": "json"},
                                              capture_output=True, text=True, timeout=5)
                    payload = assert_error(self, {"code": observed.returncode, "stdout": observed.stdout})
                    self.assertEqual(payload["operation"], "ui.press")
                    self.assertEqual(payload["action"]["state"], "not-sent")
                    observed = subprocess.run(argv, env={**env, "IPB_ERROR_FORMAT": "json", "IPB_TEST_FAIL": "1"},
                                              capture_output=True, text=True, timeout=5)
                    self.assertEqual(observed.returncode, 3)
                    self.assertEqual(observed.stdout, "")

    def test_every_golden_failure_is_one_envelope_and_success_is_unchanged(self):
        fixture = json.loads((ROOT / "docs/contracts/ax-default-v050.golden.json").read_text())
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                observed = invoke(case, fixture["results"], "json")
                self.assertEqual(observed["code"], case["expected"]["code"])
                if observed["code"] == 0:
                    self.assertEqual(observed, case["expected"])
                else:
                    payload = assert_error(self, observed)
                    expected_result = fixture["results"][case["result"]] if "result" in case and case["name"] != "dependency" else None
                    self.assertEqual(payload["result"], expected_result)
                    if "--json" in case["argv"] and not case["argv"][0] == "alert-press":
                        text_case = {**case, "argv": [arg for arg in case["argv"] if arg != "--json"]}
                        self.assertEqual(assert_error(self, invoke(text_case, fixture["results"], "json")), payload)

    def test_action_mapping_fixture_including_child_signals_is_preserved(self):
        cases = json.loads((ROOT / "docs/contracts/ax-error-v1.cases.json").read_text())["cases"]
        for case in cases:
            operation = case["operation"]
            field = {"press": "press_state", "alert-press": "press_state",
                     "scroll-to-visible": "scroll_state", "input": "input_state"}[operation]
            args = argparse.Namespace(operation=operation, input_exit_code=case["childExitCode"],
                                      **{field: case["state"]})
            with self.subTest(case=case), patch.dict(os.environ, {"IPB_ERROR_FORMAT": "json"}), \
                 redirect_stdout(io.StringIO()) as stdout:
                code = ipb_ax.report_failure(args, TimeoutError("fixture timeout"), 5)
                payload = assert_error(self, {"code": code, "stdout": stdout.getvalue()})
                self.assertEqual(payload["action"], case["expectedAction"])
                self.assertEqual(payload["retrySafe"], case["retrySafe"])

    def test_validation_and_dependencies_fail_before_running_any_backend(self):
        invalid = [
            ["--deep", "--full-state", "press"], ["press"], ["press", "--deep", "--identifier", "x"],
            ["hit-test", "--pid", "42"], ["--identifier", "x"],
            ["alert-press", "--label", "x"], ["alert-press", "--pid", "37", "--label", "x"],
            ["alert-press", "--pid", "37", "--alert-label", "x", "--class", "x"],
            ["alert-press", "--pid", "37", "--alert-label", "x", "--label", "x", "--identifier", "x", "--json"],
            ["alert-press", "--pid", "37", "--alert-label", "x", "--label", "x"],
            ["--alert-label", "x"], ["input", "--identifier", "x"],
            ["input", "--identifier", "x", "--text", "literal"], ["--text", "literal"],
            ["--wait-for", "present"], ["--pid", "0"], ["--point", "nan", "0"],
            ["wait", "--identifier", "x", "--timeout", "inf"],
            ["wait", "--identifier", "x", "--timeout", "not-a-number"], ["unknown-operation"],
        ]
        cases = [{"argv": argv} for argv in invalid]
        cases += [{"argv": [], "env": {"IPB_AX_DEVICE_ID": None}},
                  {"argv": ["input", "--identifier", "x", "--text", "literal", "--replace-all"],
                   "env": {"IPB_AX_CLI": "relative"}},
                  {"argv": [], "dependencyMissing": True}, {"argv": [], "dependency": "0.0"},
                  {"argv": [], "pythonVersion": (3, 10)}]
        for case in cases:
            with self.subTest(case=case):
                payload = assert_error(self, invoke(case, {}, "json"))
                self.assertEqual(payload["exitCode"], 2)
                self.assertIn(payload["phase"], ("validation", "dependency"))
                self.assertIsNone(payload["result"])

    def test_unknown_or_malformed_action_information_never_implies_success(self):
        for operation, field, states in (("press", "press_state", ("new-state", None)),
                                         ("scroll-to-visible", "scroll_state", ("new-state", None)),
                                         ("input", "input_state", ("child-unknown", None))):
            for state in states:
                args = argparse.Namespace(operation=operation, **{field: state})
                receipt = ipb_ax.error_action(args)
                self.assertEqual(receipt, {"state": "unknown", "native": "unknown", "childExitCode": None})
        for value in (None, "0", True, 1.0):
            receipt = ipb_ax.error_action(argparse.Namespace(operation="input", input_state="submitted"),
                                          {"action": {"childExitCode": value}})
            self.assertEqual(receipt["state"], "submitted")
            self.assertIsNone(receipt["childExitCode"])
        for operation, result in (("press", {"action": {"nativeAccepted": 1}}),
                                  ("scroll-to-visible", {"nativeResult": "false"}),
                                  ("input", {"action": {"childExitCode": None}})):
            receipt = ipb_ax.error_action(argparse.Namespace(operation=operation, press_state="not-sent",
                                                            scroll_state="not-sent", input_state="not-sent"), result)
            self.assertEqual(receipt["state"], "unknown")

    def test_exception_words_do_not_override_in_process_submission_state(self):
        for error in (TimeoutError(), ipb_ax.asyncio.CancelledError(), ValueError("not sent; native accepted; child exit 0")):
            with self.subTest(error=type(error).__name__), patch.dict(os.environ, {"IPB_ERROR_FORMAT": "json"}), \
                 redirect_stdout(io.StringIO()) as stdout:
                code = ipb_ax.report_failure(argparse.Namespace(operation="press", press_state="submitted"), error, 5)
                payload = assert_error(self, {"stdout": stdout.getvalue(), "code": code})
                self.assertEqual(payload["action"]["state"], "submitted")
                self.assertEqual(payload["phase"], "unknown")
                self.assertFalse(payload["retrySafe"])
                self.assertTrue(payload["error"]["message"])


class NativeFixtureReceiptTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_capture_control_flow_with_fake_dtx_preserves_receipt_and_tree(self):
        from test_ax import SessionTests
        cases = (("action-timeout", "press", "submitted"),
                 ("action-stop-timeout", "press", "accepted"),
                 ("action-refused", "press", "submitted"),
                 ("action-false", "press", "refused"),
                 ("scroll-post-snapshot-timeout", "scroll-to-visible", "native-true"),
                 ("scroll-native-false-post-timeout", "scroll-to-visible", "native-false"),
                 ("scroll-post-hidden", "scroll-to-visible", "native-true"),
                 ("input-child-failed", "input", "child-exited-nonzero"),
                 ("input-post-changed", "input", "child-exited-zero"),
                 ("input-child-timeout", "input", "unknown"),
                 ("supplement-timeout", None, None))
        for mode, operation, expected_state in cases:
            with self.subTest(mode=mode):
                kwargs = {"operation": operation} if operation else {"deep": True, "full_state": True}
                result, state, error = await SessionTests().run_capture(mode, **kwargs)
                argv = ["--deep", "--full-state", "--json"] if not operation else [operation, "--identifier", "fixture", "--json"]
                if operation == "input":
                    argv += ["--text", "fixture", "--replace-all"]
                case = {"argv": argv, "state": {key: state[key] for key in ("press_state", "scroll_state", "input_state")}, "result": "native"}
                if error:
                    case["error"] = {"type": type(error).__name__, "message": str(error)}
                payload = assert_error(self, invoke(case, {"native": result}, "json"))
                self.assertEqual(payload["result"], result)
                if expected_state:
                    self.assertEqual(payload["action"]["state"], expected_state)
                    self.assertFalse(payload["retrySafe"])
                else:
                    self.assertEqual(payload["result"]["nodeCount"], 3)
                    self.assertIsNone(payload["action"])
                self.assertLessEqual(state.get("action_submissions", 0), 1)
                self.assertLessEqual(state.get("input_child_calls", 0), 1)
                self.assertTrue(state["closed"] and state["dtx_closed"])


if __name__ == "__main__":
    unittest.main()
