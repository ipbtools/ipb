#!/usr/bin/env python3
"""Turn a dhtrace JSONL capture into a readable per-action report table.

    Experiments/devicehub-trace/decode.py capture.jsonl [--bytes]

Records are grouped by the action marker that preceded them, so the output
answers "what did Device Hub send while the operator did X" directly.
"""

import json
import sys
from collections import Counter

# Report ID -> name. Statically decoded from each report type's `reportID`
# getter (a plain `movz w0, #imm`); see docs/protocol.md.
REPORT_IDS = {
    1: "Keyboard", 2: "Consumer", 3: "AppleVendorKeyboard",
    4: "AppleVendorTopCase", 5: "Pointer", 6: "Button", 7: "Scroll",
    9: "Digitizer", 11: "DockSwipe", 12: "FluidTouchGesture",
    13: "NavigationSwipe", 14: "ZoomToggle", 15: "Scale", 16: "Rotation",
    17: "Translation", 18: "GameController", 19: "AbsolutePointer",
    20: "GenericGesture", 21: "TouchSensitiveButton",
}


def report_name(hexbytes):
    if not hexbytes:
        return "?"
    rid = int(hexbytes[0:2], 16)
    return "%s(%d)" % (REPORT_IDS.get(rid, "Unknown"), rid)


def iter_reports(rec):
    """Yield every {len, bytes} dict anywhere in a record."""
    r = rec.get("report")
    if isinstance(r, dict):
        yield r
    res = rec.get("result")
    if isinstance(res, dict):
        for sub in res.get("reports") or []:
            if isinstance(sub, dict):
                yield sub


def main():
    path = sys.argv[1]
    show_bytes = "--bytes" in sys.argv

    records = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    records.sort(key=lambda r: r.get("ts", 0))

    action = "(before first marker)"
    groups = []
    current = (action, [])
    for rec in records:
        if rec.get("kind") == "mark":
            groups.append(current)
            current = (rec.get("text", "?"), [])
        else:
            current[1].append(rec)
    groups.append(current)

    shed = [r for r in records if r.get("kind") == "shed"]
    errors = [r for r in records if r.get("kind") == "tap_error"]

    for label, recs in groups:
        if not recs and label.startswith("("):
            continue
        print("\n=== %s ===" % label)
        if not recs:
            print("    (no reports)")
            continue
        by_label = Counter(r.get("label") for r in recs if r.get("kind") == "call")
        print("    taps: %s" % (dict(by_label) or "-"))
        kinds = Counter()
        for rec in recs:
            for rep in iter_reports(rec):
                b = rep.get("bytes")
                kinds[report_name(b)] += 1
                if show_bytes and b:
                    print("      %-22s %s" % (report_name(b), b))
            if rec.get("words"):
                print("      words %s" % rec["words"])
        if kinds:
            print("    reports: %s" % dict(kinds))

    if shed:
        print("\n!! taps shed for exceeding their hit budget:")
        for s in shed:
            print("   %s at %.1f hits/s after %d hits" %
                  (s.get("label"), s.get("rate", 0), s.get("total", 0)))
    if errors:
        print("\n!! %d tap errors (first: %s)" % (len(errors), errors[0].get("error")))


if __name__ == "__main__":
    main()
