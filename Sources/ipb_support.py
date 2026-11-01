#!/usr/bin/env python3
"""Static ipb implementation inventory. No device imports, probing or selection."""
import argparse
import json


# Source/contract facts only. A listed implementation is not device availability.
# Keep operation names aligned with contract.md and the actual CLI, not XCTest.
AX_PREREQUISITES = ["supported macOS 27 + Xcode 27 beta host stack", "Python 3.11+", "pymobiledevice3==11.10.2", "selected existing USB pairing",
                    "Developer Mode", "iOS 27 advertised AX service"]
NATIVE_PREREQUISITES = ["supported macOS 27 + Xcode 27 beta host stack", "iOS 27+ device",
                        "existing pairing", "Developer Mode", "appropriate DDI services"]


def support_document():
    operations = []

    def add(name, mechanism, prerequisites, *, implemented=True, error_contract=False, scope=None):
        operations.append({
            "operation": name,
            "status": "unverified" if implemented else "unsupported",
            "reason": ("implementation exists; no selected-device verification in this report" if implemented
                       else "no ipb implementation; no substitute mechanism is selected"),
            "scope": scope or "implementation inventory only; target runtime not queried",
            "implementation": {"present": implemented, "mechanism": mechanism,
                               "errorContract": "ipb.error/v1 opt-in (Python entry point only)" if error_contract else None},
            "advertisement": {"status": "unknown", "data": None, "reason": "not queried"},
            "prerequisites": prerequisites,
            "verification": {"status": "unverified" if implemented else "unsupported", "records": []},
        })

    for operation in ("ui.dump", "ui.deep", "ui.deep.full-state", "ui.hit-test", "ui.locate", "ui.wait",
                      "ui.press", "ui.scroll-to-visible", "ui.input", "ui.alert-press"):
        add(operation, "DevicesApp raw AX DTX", AX_PREREQUISITES, error_contract=True)
    for operation in ("tap", "swipe", "home"):
        add(operation, "CoreDevice HID", NATIVE_PREREQUISITES)
    add("text", "devicectl clipboard copy followed by CoreDevice HID paste", NATIVE_PREREQUISITES,
        scope="clipboard copy and paste are separate stages; no Python error envelope; no Unicode HID claim")
    add("screenshot", "devicectl", NATIVE_PREREQUISITES,
        scope="formal screenshot command only; no RSD screenshot integration")
    add("capabilities", "devicectl advertised CoreDevice metadata", NATIVE_PREREQUISITES)
    for operation in ("ui.slider", "ui.picker", "ui.selection", "multitouch"):
        add(operation, None, [], implemented=False)
    return {"kind": "ipb.support", "contractVersion": 1,
            "scope": "static implementation inventory; not the complete CLI command list",
            "deviceQuery": {"status": "not-requested", "deviceIdentifier": None},
            "supportedMatrix": {"host": "macOS 27 + Xcode 27 beta", "device": "iOS 27+",
                                "status": "unverified", "reason": "matrix gate not run by this report"},
            "operations": operations}


def main():
    parser = argparse.ArgumentParser(prog="ipb support", description=__doc__)
    parser.add_argument("--json", action="store_true", required=True,
                        help="emit the static ipb.support v1 inventory; no device query")
    parser.parse_args()
    print(json.dumps(support_document(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
