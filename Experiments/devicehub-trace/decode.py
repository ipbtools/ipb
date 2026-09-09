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


# Byte length -> the report type that is that size, for captures where the
# bytes could not be read. Sizes come from each type's initialReportBitCount
# plus the grown sizes observed on the wire (see docs/protocol.md).
LEN_HINTS = {
    19: "AbsolutePointer(19)", 21: "Scroll(7), grown", 58: "Digitizer(9), grown",
    13: "Scroll(7), initial", 31: "Keyboard(1), initial", 17: "Pointer(5)",
    9: "Consumer(2)", 5: "AppleVendorTopCase(4)", 3: "AppleVendorKeyboard(3)",
}


def report_name(rep):
    """Name a report by its first byte, falling back to its length."""
    if not isinstance(rep, dict):
        return "?"
    b = rep.get("bytes")
    if b:
        rid = int(b[0:2], 16)
        return "%s(%d)" % (REPORT_IDS.get(rid, "Unknown"), rid)
    n = rep.get("len")
    if n is None and rep.get("w0"):
        # Captures made before the range decode landed carry only the raw
        # words; the length is still recoverable from word0's range.
        w0 = int(rep["w0"], 16)
        n = ((w0 >> 32) & 0xFFFFFFFF) - (w0 & 0xFFFFFFFF)
    if n:
        return "%s [%dB, bytes unread]" % (LEN_HINTS.get(n, "unknown"), n)
    return "?"


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
                name = report_name(rep)
                kinds[name] += 1
                if show_bytes:
                    b = rep.get("bytes")
                    if b:
                        print("      %-26s %s" % (name, b))
                    else:
                        alt = {k: v for k, v in rep.items()
                               if k.startswith("bytes_at_")}
                        if alt:
                            for k, v in alt.items():
                                print("      %-26s %s=%s" % (name, k, v))
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
