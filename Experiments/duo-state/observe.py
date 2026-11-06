#!/usr/bin/env python3
"""Read-only, simulator-only display observation; not an input authorization."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
DISPLAY_FIELDS = ("displayId", "uniqueId", "active", "primary", "bounds",
                  "pointScale", "nativeSize", "nativeOrientation",
                  "currentOrientation", "backlightState", "type", "name", "framebufferMaskIdentifier")


def run(argv):
    result = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise ValueError(f"{argv[0]} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def display_metadata(info):
    """Hash only declared display metadata, independent of inventory order."""
    displays = info.get("displays")
    if not isinstance(displays, list) or not displays:
        raise ValueError("display inventory unavailable")
    rows, seen = [], set()
    for display in displays:
        if not isinstance(display, dict):
            raise ValueError("invalid display record")
        identifier = display.get("displayId")
        if type(identifier) is not int or identifier in seen:
            raise ValueError("invalid or duplicate displayId")
        seen.add(identifier)
        if type(display.get("active")) is not bool:
            raise ValueError("display active state unavailable")
        bounds, scale = display.get("bounds"), display.get("pointScale")
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(pair, list) or len(pair) != 2 for pair in bounds)
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for pair in bounds for v in pair)
                or any(v <= 0 for v in bounds[1])
                or type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0):
            raise ValueError("display bounds/scale unavailable")
        rows.append({key: display.get(key) for key in DISPLAY_FIELDS})
    return {"displays": sorted(rows, key=lambda row: row["displayId"]),
            "orientation": info.get("orientation"), "backlightState": info.get("backlightState")}


def fingerprint(metadata):
    data = json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def observation(device, seed, before, guest, after, expected=None):
    first, last = display_metadata(before), display_metadata(after)
    context = {"deviceIdentifier": device, "seed": seed}
    digest = fingerprint({**context, **last})
    stable = first == last
    matched = None if expected is None else expected == digest
    active = [d["displayId"] for d in last["displays"] if d["active"]]
    if guest.get("backend") != "simulator-guest-frontboard":
        raise ValueError("unexpected guest backend")
    layout = guest["defaultMainLayout"]
    blockers = ["app-window-region-unproven", "input-transform-unproven", "overlay-ownership-unproven"]
    if layout is None:
        blockers.append("frontboard-layout-unavailable")
    if not stable:
        blockers.append("display-changed-during-observation")
    if matched is False:
        blockers.append("expected-display-fingerprint-mismatch")
    if len(active) != 1:
        blockers.append("active-display-not-unique")
    result = {"schemaVersion": 1, "kind": "ipb.duo.observation", "backend": "coresimulator",
              **context, "atomic": False, **last, "activeDisplayIds": active,
              "displayMetadataMatchesAcrossRead": stable, "displayFingerprint": digest,
              "fingerprintScope": "device-seed-and-selected-coredevice-display-metadata",
              "expectedDisplayFingerprintMatch": matched,
              "frontboard": {"layoutStatus": "unavailable" if layout is None else "observed-raw",
                             "raw": guest},
              "sceneBinding": None, "bindingFingerprint": None, "targetRegion": None,
              "touchTransform": None, "actionable": False, "blockers": blockers}
    # A complete observation may report unavailable sources. A stale observation
    # is still useful JSON, but it must fail the caller's precondition.
    return result, 6 if not stable or matched is False else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", required=True, help="full UUID of an explicitly Booted simulator")
    parser.add_argument("--guest-helper", type=Path, default=ROOT / "build/ipb-duo-state-guest")
    parser.add_argument("--expect-display-fingerprint", help="reject changed display metadata; equality is not action permission")
    args = parser.parse_args()
    try:
        device = str(uuid.UUID(args.simulator)).upper()
        inventory = json.loads(run(["xcrun", "simctl", "list", "devices", "-j"]))["devices"]
        selected = [(runtime, row) for runtime, rows in inventory.items() for row in rows
                    if row["udid"].upper() == device]
        if len(selected) != 1 or selected[0][1]["state"] != "Booted":
            raise ValueError("selected simulator must already be Booted; no implicit boot or fallback")
        runtimes = json.loads(run(["xcrun", "simctl", "list", "runtimes", "-j"]))["runtimes"]
        runtime = next(row for row in runtimes if row["identifier"] == selected[0][0])
        xcode = run(["xcodebuild", "-version"]).strip()
        seed = {"hostBuild": run(["sw_vers", "-buildVersion"]).strip(),
                "xcode": xcode, "runtimeBuild": runtime["buildversion"],
                "deviceTypeIdentifier": selected[0][1]["deviceTypeIdentifier"]}
        if (seed["hostBuild"] != "26B123" or xcode.splitlines() != ["Xcode 27.2", "Build version 27B52"]
                or seed["runtimeBuild"] != "24B91016s"
                or seed["deviceTypeIdentifier"] != "com.apple.CoreSimulator.SimDeviceType.iPhone-Duo"):
            raise ValueError(f"unverified host/Xcode/runtime seed: {seed}; see docs/duo-ddi-exploration.md")
        helper = args.guest_helper.resolve()
        if not helper.is_file():
            raise ValueError("guest helper missing; run make duo-state-probe")
        with tempfile.TemporaryDirectory(prefix="ipb-duo-state-") as directory:
            path = Path(directory) / "displays.json"

            def displays():
                run(["xcrun", "devicectl", "device", "info", "displays", "--device", device,
                     "--timeout", "8", "--quiet", "--json-output", path])
                return json.loads(path.read_text())["result"]

            before = displays()
            guest = json.loads(run(["xcrun", "simctl", "spawn", device, helper]))
            after = displays()
        result, status = observation(device, seed, before, guest, after, args.expect_display_fingerprint)
        print(json.dumps(result, indent=2, allow_nan=False))
        return status
    except (ValueError, KeyError, StopIteration, OSError, subprocess.TimeoutExpired) as error:
        print(f"duo-state: {error}", file=sys.stderr)
        return 6


if __name__ == "__main__":
    sys.exit(main())
