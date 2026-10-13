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
    13: "Scroll(7), initial", 31: "Keyboard(1), old short allocation", 39: "Keyboard(1)", 17: "Pointer(5)",
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


def _bytes(value):
    """Decode a captured hex string without changing or reformatting the source."""
    if not value:
        return None
    try:
        return bytes.fromhex(value)
    except (TypeError, ValueError):
        return None


def service_id(rec):
    """Return the HIDServiceID value captured by the dereferenced x2 argument."""
    raw = _bytes((rec.get("deref") or {}).get("x2"))
    if raw is None or len(raw) < 8:
        return None
    return int.from_bytes(raw[:8], "little")


def digitizer_fields(rep):
    """Decode the 464-bit DigitizerReport descriptor from docs/protocol.md.

    The report is little-endian at the bit level. Keep the raw report separate;
    these fields are a view of it, not a replacement for captured evidence.
    """
    raw = _bytes(rep.get("bytes"))
    if raw is None or len(raw) < 58 or raw[0] != 9:
        return None

    def bits(offset, width):
        value = int.from_bytes(raw, "little")
        return (value >> offset) & ((1 << width) - 1)

    count = bits(8, 8)
    maximum = bits(16, 8)
    contacts = []
    for index in range(min(count, 5)):
        base = 24 + index * 40
        contacts.append({
            "index": index,
            "identifier": bits(base, 5),
            "resting": bits(base + 5, 1),
            "touch": bits(base + 6, 1),
            "inRange": bits(base + 7, 1),
            "x": bits(base + 8, 16),
            "y": bits(base + 24, 16),
            "identity": bits(320 + index * 8, 8),
        })
    return {
        "contactCount": count,
        "contactCountMaximum": maximum,
        "contacts": contacts,
        "remoteTimestamp": bits(360, 64),
    }


def digitizer_summary(rep, rec):
    fields = digitizer_fields(rep)
    if fields is None:
        return None
    sid = service_id(rec)
    sid_text = "unknown" if sid is None else "0x%x" % sid
    contacts = []
    for contact in fields["contacts"]:
        contacts.append(
            "#%d id=%d resting=%d touch=%d inRange=%d x=%d y=%d identity=0x%02x"
            % (contact["index"], contact["identifier"], contact["resting"],
               contact["touch"], contact["inRange"], contact["x"],
               contact["y"], contact["identity"])
        )
    return ("service_id=%s service_id_raw=%s count=%d max=%d contacts=[%s] "
            "remoteTimestamp=%d" %
            (sid_text, (rec.get("deref") or {}).get("x2", "-"),
             fields["contactCount"], fields["contactCountMaximum"],
             "; ".join(contacts), fields["remoteTimestamp"]))


def load_actions(path):
    """Read the operator's action log and turn it into marker records.

    dhtrace.sh injected markers into the trace itself, because the operator and
    the tracer shared one terminal. With an agent operator they are separate
    processes, so the only thing they share is the clock: the operator logs
    {"ts", "action"} immediately before acting, and those timestamps become the
    grouping markers here. A marker whose timestamp is outside the trace's own
    range means the two halves did not overlap and is reported rather than
    silently producing empty groups.
    """
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "ts" in rec:
                out.append({"kind": "mark", "ts": float(rec["ts"]),
                            "text": rec.get("action") or rec.get("text") or "?"})
    return out


def main():
    path = sys.argv[1]
    show_bytes = "--bytes" in sys.argv
    actions = None
    if "--actions" in sys.argv:
        actions = load_actions(sys.argv[sys.argv.index("--actions") + 1])

    records = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if actions:
        lo = min((r["ts"] for r in records if r.get("ts")), default=None)
        hi = max((r["ts"] for r in records if r.get("ts")), default=None)
        if lo is not None:
            inside = [a for a in actions if lo <= a["ts"] <= hi]
            print("actions: %d of %d fall inside the trace window "
                  "(%.1f s wide)" % (len(inside), len(actions), hi - lo))
            if not inside:
                print("!! no action overlaps the trace: the two halves did not "
                      "run at the same time; nothing below is attributable.")
        records.extend(actions)

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
                if name.startswith("Digitizer("):
                    summary = digitizer_summary(rep, rec)
                    if summary:
                        print("      %s" % summary)
            if rec.get("words"):
                print("      words   %s" % rec["words"])
            if rec.get("doubles"):
                # The Indigo digitizer and scroll entry points carry their
                # coordinates here, not in the x registers.
                print("      doubles %s" % rec["doubles"])
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
