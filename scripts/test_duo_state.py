#!/usr/bin/env python3
"""Observation contract only; no simulator, phone, input or fixture framework."""
import copy
from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "Experiments/duo-state/observe.py"
spec = importlib.util.spec_from_file_location("duo_state", path)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


class ObservationContract(unittest.TestCase):
    def setUp(self):
        self.info = {"displays": [
            {"displayId": 3, "uniqueId": "inner", "active": True, "bounds": [[0, 0], [1200, 1800]],
             "pointScale": 3, "currentOrientation": "rot90"},
            {"displayId": 1, "uniqueId": "outer", "active": False, "bounds": [[0, 0], [900, 1500]],
             "pointScale": 3, "currentOrientation": "rot0"}]}
        self.guest = {"backend": "simulator-guest-frontboard", "defaultMainLayout": None}

    def observe(self, before=None, after=None, expected=None):
        return state.observation("simulator", {"runtimeBuild": "test"},
                                 before or self.info, self.guest, after or self.info, expected)

    def test_display_changes_reject_a_stale_precondition_without_inventing_a_generation(self):
        first, rc = self.observe()
        self.assertEqual(rc, 0)
        reordered = copy.deepcopy(self.info)
        reordered["displays"].reverse()
        same, rc = self.observe(after=reordered, expected=first["displayFingerprint"])
        self.assertEqual(rc, 0)
        self.assertTrue(same["expectedDisplayFingerprintMatch"])
        changed = copy.deepcopy(self.info)
        changed["displays"][0]["currentOrientation"] = "rot270"
        stale, rc = self.observe(before=changed, after=changed, expected=first["displayFingerprint"])
        self.assertEqual(rc, 6)
        self.assertFalse(stale["expectedDisplayFingerprintMatch"])
        unstable, rc = self.observe(after=changed)
        self.assertEqual(rc, 6)
        self.assertFalse(unstable["displayMetadataMatchesAcrossRead"])

    def test_equal_display_metadata_and_nil_layout_never_authorize_an_app_region(self):
        first, _ = self.observe()
        result, rc = self.observe(expected=first["displayFingerprint"])
        self.assertEqual(rc, 0)
        self.assertEqual(result["frontboard"]["layoutStatus"], "unavailable")
        for field in ("sceneBinding", "bindingFingerprint", "targetRegion", "touchTransform"):
            self.assertIsNone(result[field])
        self.assertFalse(result["actionable"])
        self.assertIn("app-window-region-unproven", result["blockers"])
        self.assertNotIn("generation", result)

    def test_unverified_target_seed_is_rejected_before_display_or_guest_requests(self):
        device = "00000000-0000-0000-0000-000000000001"
        duo = "com.apple.CoreSimulator.SimDeviceType.iPhone-Duo"
        for device_type, xcode in (("other-device", "Xcode 27.2\nBuild version 27B52"),
                                   (duo, "Xcode 27.2\nBuild version 27B5210a")):
            with self.subTest(device_type=device_type, xcode=xcode):
                replies = {
                    ("xcrun", "simctl", "list", "devices", "-j"): json.dumps({"devices": {"runtime": [
                        {"udid": device, "state": "Booted", "deviceTypeIdentifier": device_type}]}}),
                    ("xcrun", "simctl", "list", "runtimes", "-j"): json.dumps({"runtimes": [
                        {"identifier": "runtime", "buildversion": "24B91016s"}]}),
                    ("xcodebuild", "-version"): xcode,
                    ("sw_vers", "-buildVersion"): "26B123",
                }

                def fake_run(argv):
                    self.assertIn(tuple(argv), replies, "unexpected request beyond target validation")
                    return replies[tuple(argv)]

                error = io.StringIO()
                with patch.object(sys, "argv", ["observe.py", "--simulator", device]), \
                        patch.object(state, "run", side_effect=fake_run), redirect_stderr(error):
                    self.assertEqual(state.main(), 6)
                self.assertIn("unverified host/Xcode/runtime seed", error.getvalue())


if __name__ == "__main__":
    unittest.main()
