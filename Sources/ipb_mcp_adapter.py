"""MCP-only CLI boundary. Never import AX, invent state, or retry a command."""
import json
import math
import re

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
READS = {"devices", "observe", "locate", "wait"}
SELECTORS = ("identifier", "label", "value", "className")
AX_ACTIONS = {"press", "input", "scroll_to_visible", "alert_press"}


def string(limit=1024, **extra):
    return {"type": "string", "minLength": 1, "maxLength": limit, **extra}


DEVICE = string(36, pattern="^" + UUID + "$")
PID = {"type": "integer", "minimum": 1, "maximum": 2147483647}
COORD = {"type": "number", "minimum": 0, "maximum": 1}
EXACT = {key: string() for key in SELECTORS}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


TOOLS = []


def tool(name, description, properties, required):
    TOOLS.append({"name": name, "description": description,
                  "inputSchema": schema(properties, required)})


tool("devices", "List physical devices via ipb TSV. No automatic device selection.", {}, ())
tool("observe", "Fresh compact native deep snapshot; IDs expire with this result. No hittable/XCTest type.",
     {"device": DEVICE, "pid": PID,
      "nativeProfile": {"type": "string", "enum": ["full", "core"]}}, ("device",))
for name in ("locate", "wait", "press", "input", "scroll_to_visible"):
    props = {"device": DEVICE, "pid": PID, **EXACT}
    required = ["device"]
    if name == "wait":
        props.update(waitFor={"type": "string", "enum": ["present", "absent"]},
                     timeout={"type": "number", "exclusiveMinimum": 0, "maximum": 15})
    if name == "input":
        props.update(text=string(4096), replaceAll={"type": "boolean", "const": True})
        required += ["text", "replaceAll"]
    tool(name, {"locate": "Exact conjunctive selectors in one fresh native snapshot.",
                "wait": "Bounded fresh native reads; ambiguous/failed reads are not absence.",
                "press": "One guarded native press; acceptance does not verify business success.",
                "input": "One guarded replacement of the current text responder. Clipboard may change; never replay.",
                "scroll_to_visible": "One native scroll for an already materialized target; no search/fallback."}[name]
         + " Supply at least one exact selector; className is native class.", props, required)
tool("alert_press", "One explicitly observed SpringBoard modal button; no automatic alert handling.",
     {"device": DEVICE, "pid": PID, "alertLabel": string(), "label": string()},
     ("device", "pid", "alertLabel", "label"))
tool("home", "Send Home once. Command success does not establish a UI/business postcondition.",
     {"device": DEVICE}, ("device",))
tool("launch", "Launch one bundle ID (existing CLI terminates an existing instance). No extra arguments.",
     {"device": DEVICE, "bundleId": string(255, pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]*$")},
     ("device", "bundleId"))
tool("tap", "One normalized coordinate tap; no element or business verification.",
     {"device": DEVICE, "x": COORD, "y": COORD}, ("device", "x", "y"))
tool("swipe", "One normalized coordinate swipe; no replay or fallback.",
     {"device": DEVICE, **{key: COORD for key in ("x1", "y1", "x2", "y2")},
      "duration": {"type": "number", "exclusiveMinimum": 0, "maximum": 2}},
     ("device", "x1", "y1", "x2", "y2"))


def validate(arguments, spec):
    """Validate precisely the small schema vocabulary emitted above (no SDK dependency)."""
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if arguments.keys() - spec["properties"].keys():
        raise ValueError("unknown tool argument")
    if any(key not in arguments for key in spec["required"]):
        raise ValueError("missing required tool argument")
    for key, value in arguments.items():
        rule = spec["properties"][key]
        kind = rule["type"]
        if ((kind == "string" and type(value) is not str) or
                (kind == "integer" and type(value) is not int) or
                (kind == "number" and type(value) not in (int, float)) or
                (kind == "boolean" and type(value) is not bool)):
            raise ValueError("invalid argument type: " + key)
        if kind == "string":
            if (not rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", 4096)
                    or "\0" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value)
                    or ("pattern" in rule and not re.fullmatch(rule["pattern"], value))):
                raise ValueError("invalid string argument: " + key)
        if kind in ("integer", "number"):
            if (not math.isfinite(value) or value < rule.get("minimum", -math.inf)
                    or value > rule.get("maximum", math.inf)
                    or ("exclusiveMinimum" in rule and value <= rule["exclusiveMinimum"])):
                raise ValueError("argument outside bounds: " + key)
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError("invalid enum argument: " + key)
        if "const" in rule and value != rule["const"]:
            raise ValueError("explicit replaceAll=true required")


def command(name, arguments):
    specs = {entry["name"]: entry["inputSchema"] for entry in TOOLS}
    if name not in specs:
        raise ValueError("unknown tool")
    validate(arguments, specs[name])
    a = dict(arguments)
    if name == "devices":
        return ["devices"]
    # Canonicalize only the lock key in Bridge. v0.5.0 query_ui compares the
    # enumerated identifier as text, so preserve the caller's observed UUID case.
    argv = ["-s", a["device"]]
    if name in {"observe", "locate", "wait"} | AX_ACTIONS:
        argv += ["ui"]
        argv += ["--deep"] if name == "observe" else [name.replace("_", "-")]
        if name == "observe" and a.get("nativeProfile", "full") == "core":
            argv += ["--native-profile", "core"]
        argv += ["--json"]
        if "pid" in a:
            argv += ["--pid", str(a["pid"])]
        if name in {"locate", "wait", "press", "input", "scroll_to_visible"}:
            if not any(key in a for key in SELECTORS):
                raise ValueError("at least one exact selector required")
            for key in SELECTORS:
                if key in a:
                    argv += ["--class" if key == "className" else "--" + key, a[key]]
        if name == "wait":
            argv += ["--wait-for", a.get("waitFor", "present"), "--timeout", str(a.get("timeout", 5))]
        if name == "input":
            argv += ["--replace-all", "--text", a["text"]]
        if name == "alert_press":
            argv += ["--alert-label", a["alertLabel"], "--label", a["label"]]
    else:
        argv += [name]
        if name == "launch":
            argv += [a["bundleId"]]
        if name == "tap":
            argv += [str(a[key]) for key in ("x", "y")]
        if name == "swipe":
            argv += [str(a[key]) for key in ("x1", "y1", "x2", "y2")]
            argv += [str(a.get("duration", 0.3))]
    return argv


def loads(raw):
    def reject(value):
        raise ValueError("non-finite JSON")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite JSON")
        return result
    return json.loads(raw, parse_constant=reject, parse_float=number, object_pairs_hook=pairs)


def compact_observe(raw, device, requested_profile="full"):
    """Project a complete schema2 observation, keeping absent and false fields distinct."""
    if requested_profile not in ("full", "core"):
        raise ValueError("invalid requested native attribute profile")
    if (not isinstance(raw, dict) or raw.get("schemaVersion") != 2
            or raw.get("deviceIdentifier", "").lower() != device.lower()
            or not isinstance(raw.get("snapshotId"), str) or not raw["snapshotId"]
            or raw.get("hierarchySource") != "AXUserTestingSnapshot"
            or raw.get("attributePolicy") != "native-snapshot"
            or raw.get("stateScope") != "native-snapshot" or raw.get("atomic") is not False
            or raw.get("rootStable") is not True
            or raw.get("rootStabilityScope") != "application-identity"):
        raise ValueError("not a complete matching native deep observation")
    has_profile = "nativeAttributeProfile" in raw
    has_visibility = "nativeVisibility" in raw
    if has_profile != has_visibility:
        raise ValueError("incomplete native attribute profile metadata")
    if not has_profile:
        returned_profile = "full"
    elif (raw["nativeAttributeProfile"], raw["nativeVisibility"]) == ("core", "not-requested"):
        returned_profile = "core"
    else:
        raise ValueError("invalid native attribute profile metadata")
    if returned_profile != requested_profile:
        raise ValueError("native attribute profile does not match request")
    cleanup = raw.get("cleanup", {})
    application = raw.get('application')
    if (not isinstance(application, dict) or type(application.get('pid')) is not int
            or application['pid'] <= 0 or raw.get('scope') != 'application-accessibility'
            or type(raw.get('uniqueElementCount')) is not int):
        raise ValueError('incomplete native application identity')
    if (cleanup.get("connectionClosed") is not True or cleanup.get("tunnelClosed") is not True
            or cleanup.get("subscriptionStop") not in ("acknowledged", "connection-closed-before-ack")):
        raise ValueError("observation cleanup not complete")
    nodes = raw.get("nodes")
    if (not isinstance(nodes, list) or not 1 <= len(nodes) <= 512
            or raw.get("nodeCount") != len(nodes)):
        raise ValueError("invalid complete native node list")
    by_id = {}
    for node in nodes:
        if (not isinstance(node, dict) or not isinstance(node.get("id"), str)
                or node["id"] in by_id or not isinstance(node.get("children"), list)
                or type(node.get("depth")) is not int or not 0 <= node["depth"] <= 32):
            raise ValueError("invalid native node record")
        if returned_profile == "core" and "visible" in node:
            raise ValueError("core observation contains native visibility")
        by_id[node["id"]] = node
    roots = [node for node in nodes if node.get("parentId") is None]
    if len(roots) != 1 or roots[0]["depth"] != 0:
        raise ValueError("invalid native root")
    seen, pending = set(), [roots[0]]
    while pending:
        node = pending.pop()
        if node["id"] in seen:
            raise ValueError("repeated native path")
        seen.add(node["id"])
        for child_id in node["children"]:
            child = by_id.get(child_id)
            if (child is None or child.get("parentId") != node["id"]
                    or child["depth"] != node["depth"] + 1):
                raise ValueError("invalid native child edge")
            pending.append(child)
    if len(seen) != len(nodes):
        raise ValueError("incomplete native tree")
    fields = ("id", "parentId", "children", "label", "identifier", "hint", "value", "frame",
              "frameUnavailable", "traits", "visible", "nativeAttributes", "processIdentifier",
              "externalProcessReference")
    meta = ("snapshotId", "deviceIdentifier", "application", "coordinateSpace", "displayFrame",
            "atomic", "rootStable", "rootStabilityScope", "hierarchySource", "attributePolicy",
            "stateScope", "nativeAttributeProfile", "nativeVisibility", "nodeCount",
            "uniqueElementCount", "snapshotMs", "queryMs")
    return {"kind": "ipb.mcp.observation", "version": 1, "sourceSchemaVersion": 2,
            **{key: raw[key] for key in meta if key in raw}, "idsScope": "this-observation-only",
            "nodes": [{key: node[key] for key in fields if key in node} for node in nodes]}


def adapt(name, device, exit_code, stdout, *, interrupted=None, requested_profile="full"):
    """v0.5.0 fallback is command-family scoped. stderr is never submission evidence."""
    read = name in READS
    result, parse_error = None, False
    expects_json = name in {"observe", "locate", "wait"} | AX_ACTIONS
    if expects_json and stdout:
        try:
            result = loads(stdout)
            if not isinstance(result, dict):
                raise ValueError("CLI JSON must be an object")
        except (ValueError, RecursionError):
            parse_error = True
    elif expects_json:
        parse_error = True
    else:
        result = stdout
    abnormal = interrupted is not None or exit_code is None or exit_code < 0 or exit_code >= 128
    action = None if read else {"state": "unknown", "native": "unknown", "childExitCode": None}
    retry_safe = read
    receipt = None
    expected_op = "ui.dump" if name == "observe" else "ui." + name.replace("_", "-")
    if (not abnormal and exit_code != 0 and isinstance(result, dict)
            and result.get("kind") == "ipb.error" and type(result.get("contractVersion")) is int
            and result["contractVersion"] == 1 and result.get("operation") == expected_op
            and result.get("exitCode") == exit_code and type(result.get("retrySafe")) is bool
            and isinstance(result.get("error"), dict)
            and (result.get("action") is None if read else isinstance(result.get("action"), dict))):
        receipt = result
        action = None if read else dict(receipt["action"])
        if action is not None:
            known = {"not-sent", "submitted", "accepted", "refused", "unknown",
                     "child-exited-zero", "child-exited-nonzero", "native-true", "native-false"}
            if action.get("state") not in known:
                action["state"] = "unknown"
            if type(action.get("native")) is not bool:
                action["native"] = "unknown"
            if type(action.get("childExitCode")) is not int:
                action["childExitCode"] = None
        retry_safe = read or (action["state"] == "not-sent" and receipt["retrySafe"])
        result = receipt.get("result")
    elif not abnormal and not read:
        if isinstance(result, dict) and "kind" not in result and not parse_error:
            native = result.get("action", {})
            if not isinstance(native, dict):
                native = {}
            if name in ("press", "alert_press") and type(native.get("nativeAccepted")) is bool:
                action.update(state="accepted" if native["nativeAccepted"] else "refused",
                              native=native["nativeAccepted"])
            elif name == "scroll_to_visible" and type(result.get("nativeResult")) is bool:
                action.update(state="native-true" if result["nativeResult"] else "native-false",
                              native=result["nativeResult"])
            elif name == "input" and type(native.get("childExitCode")) is int:
                code = native["childExitCode"]
                action.update(state=("unknown" if code < 0 or code >= 128 else
                                     "child-exited-zero" if code == 0 else "child-exited-nonzero"),
                              childExitCode=code)
        elif name in ("tap", "swipe", "home"):
            if exit_code in (2, 3, 4):
                action["state"], retry_safe = "not-sent", True
            elif exit_code == 0:
                action["state"] = "accepted"
        # No-receipt AX failures (including 1/5) and devicectl launch retain
        # unknown: a shell exit alone cannot prove a normal handled Python exit.
    ok = exit_code == 0 and not abnormal and not parse_error
    error = interrupted or ("invalid-cli-json" if parse_error and exit_code == 0 else None)
    if name == "observe" and ok:
        try:
            result = compact_observe(result, device, requested_profile)
        except (ValueError, TypeError, AttributeError, KeyError):
            ok, error = False, "invalid-native-observation"
    if name == "devices" and ok:
        try:
            devices = []
            for line in stdout.splitlines():
                cols = line.split("\t")
                if len(cols) != 6 or not re.fullmatch(UUID, cols[0]):
                    raise ValueError("invalid device TSV")
                devices.append(dict(zip(("deviceIdentifier", "name", "os", "transport", "tunnelState", "model"), cols)))
            result = {"devices": devices}
        except ValueError:
            ok, error = False, "invalid-device-list"
    if expects_json and ok and name != "observe":
        if (not isinstance(result, dict) or result.get("schemaVersion") != 1
                or not isinstance(result.get("deviceIdentifier"), str)
                or result["deviceIdentifier"].lower() != device.lower()):
            ok, error = False, "invalid-cli-result"
    if abnormal:
        action = None if read else {"state": "unknown", "native": "unknown", "childExitCode": None}
        retry_safe = read
    return {"kind": "ipb.mcp.result", "envelopeVersion": 1, "tool": name,
            "deviceIdentifier": device, "ok": ok, "cliExitCode": exit_code,
            "error": error or (None if ok else "cli-failed"), "action": action,
            "retrySafe": retry_safe, "businessVerified": "unknown", "result": result,
            "phase": receipt['phase'] if receipt and receipt.get('phase') in
                ('validation', 'dependency', 'query', 'submission', 'postcondition', 'supplemental') else 'unknown',
            "receipt": receipt}
