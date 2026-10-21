#!/usr/bin/env python3
"""One-shot DevicesApp AX graph. See docs/protocol.md for captured wire evidence."""
import argparse
import asyncio
from collections import deque
import functools
from importlib.metadata import version
import json
import logging
import math
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
import uuid

from ax_archive import decode, request

SERVICE = "com.apple.accessibility.axAuditDaemon.remoteAXService"
# Verified by the host mapping and iOS 27.0 / 24A437 read replies. Missing fields
# stay missing; querying Parent/RoleDescription does not invent a container tree.
FIELDS = {3: "label", 21: "frame", 25: "identifier", 27: "enabled", 28: "focused",
          30: "selected", 32: "visible", 33: "description", 42: "placeholder",
          45: "roleCode", 46: "roleDescription", 51: "subroleCode", 53: "value", 77: "traits"}
# Label 3 can stall a text node even when Description 33 already supplies its
# text (13 Pro Bilibili title, iOS 27 / 24A437; verification.md). Keep the fields
# distinct: query Label only when Description has no text, never synthesize it.
ATTRS = [8, 9, 41, *(key for key in FIELDS if key != 3)]
BOOL_FIELDS = {27, 28, 30, 32}
MAX_NODES, MAX_DEPTH = 512, 32
# Native AX IDs, not AXP field IDs. Required numeric attributes and descendant
# options: matching iOS 27 / 24A437 source and 13 Pro controls (protocol.md).
SNAPSHOT_ATTRS = [2001, 2002, 2003, 2004, 5019, 2006, 2025, 5003, 5004, 3003]
STATE_ATTRS = [27, 28, 30, 32, 42, 45, 46, 51]
SNAPSHOT_OPTIONS = {"attributes": SNAPSHOT_ATTRS, "maxDepth": 48,
                    "maxChildren": 512, "maxArrayCount": 512,
                    "traverseFromParentsToChildren": True,
                    "snapshotKeyHonorModalViews": False}
ELEMENT = "UIAccessibilitySnapshotKeyElement"
CHILDREN = "UIAccessibilitySnapshotKeyChildren"
CHILD_COUNT = "UIAccessibilitySnapshotKeyChildrenCount"
NATIVE_ATTRS = "UIAccessibilitySnapshotKeyAttributes"


def snapshot_nodes(snapshot, root):
    """Keep native path occurrences; handles can legitimately have two parents."""
    if snapshot is None:
        raise ValueError("AX snapshot unavailable: device returned nil")
    if not isinstance(snapshot, dict):
        raise ValueError("invalid AX snapshot record")
    actual_root, expected_root = identity(snapshot.get(ELEMENT)), identity(root)
    if actual_root != expected_root:
        raise ValueError(f"AX snapshot root mismatch: expected={expected_root} actual={actual_root}")
    nodes, by_handle = [], {}
    pending = deque([(snapshot, None, 0, frozenset())])
    while pending:
        record, parent, depth, ancestors = pending.popleft()
        if depth > MAX_DEPTH or len(nodes) >= MAX_NODES:
            raise ValueError("AX snapshot limit reached; no partial tree emitted")
        if not isinstance(record, dict) or id(record) in ancestors:
            raise ValueError("invalid or cyclic AX snapshot")
        key = identity(record.get(ELEMENT))
        children, count, native = record.get(CHILDREN), record.get(CHILD_COUNT), record.get(NATIVE_ATTRS)
        if (not isinstance(children, list) or type(count) is not int or count != len(children)
                or not isinstance(native, dict)):
            raise ValueError("AX snapshot children/attributes unavailable or truncated")
        external = key[0] != root["pid"]
        if external and (native.get(5003) != "AXRemoteElement" or children or count != 0):
            raise ValueError("AX snapshot foreign child is not a proven leaf AXRemoteElement")
        fields = node_fields({mapped: native[native_id] for native_id, mapped in
                              ((2001, 3), (2003, 21), (2004, 77), (5019, 25), (2006, 53), (2025, 32))
                              if native_id in native})
        if native.get(2002) is not None:
            if not isinstance(native[2002], str):
                raise ValueError("invalid AX native hint")
            fields["hint"] = native[2002]
        metadata = {}
        for native_id in (5003, 5004, 3003):
            if native.get(native_id) is not None:
                if not isinstance(native[native_id], str):
                    raise ValueError("invalid AX native class/bundle attribute")
                metadata[str(native_id)] = native[native_id]
        if metadata:
            fields["nativeAttributes"] = metadata
        node_id = "n" + str(len(nodes))
        node = {"id": node_id, "parentId": parent, "depth": depth, "children": [],
                "attributeSource": "native-snapshot", **fields}
        if external:
            node["processIdentifier"] = key[0]
            node["externalProcessReference"] = True
        nodes.append(node)
        by_handle.setdefault(key, []).append(node)
        if parent is not None:
            nodes[int(parent[1:])]["children"].append(node_id)
        pending.extend((child, node_id, depth + 1, ancestors | {id(record)}) for child in children)
    return nodes, by_handle


def native_matches(snapshot, root, selectors):
    """Match exact string selectors against one fresh native snapshot."""
    nodes, by_handle = snapshot_nodes(snapshot, root)
    matches = {}
    pending = [snapshot]
    while pending:
        record = pending.pop()
        token = record[ELEMENT]
        native = record[NATIVE_ATTRS]
        values = {"identifier": native.get(5019), "label": native.get(2001), "value": native.get(2006),
                  "className": native.get(5003)}
        if all(type(values[key]) is str and values[key] == value
               for key, value in selectors.items()):
            key = identity(token)
            matches.setdefault(key, {"token": token, "native": native,
                                     "node": by_handle[key][0],
                                     "nodeIds": [node["id"] for node in by_handle[key]]})
        pending.extend(record[CHILDREN])
    return nodes, list(matches.values())


def resolve_native_target(snapshot, root, selectors, *, operation="AX locator"):
    """Resolve exactly one distinct native AX element; never accept a cached handle."""
    _, matches = native_matches(snapshot, root, selectors)
    if len(matches) != 1:
        raise ValueError(f"{operation} selector matches={len(matches)}; exactly one native element is required")
    match = matches[0]
    return match["token"], match["native"], match["node"]


TEXT_ENTRY_TRAIT = 0x200000


def resolve_input_target(snapshot, root, selectors):
    """Require one selected native element to be the root's live text-entry responder."""
    root_attrs = snapshot.get(NATIVE_ATTRS) if isinstance(snapshot, dict) else None
    responder = root_attrs.get(3002) if isinstance(root_attrs, dict) else None
    if not isinstance(responder, dict):
        raise ValueError("AX input first responder is unavailable; no input submitted")
    responder_token = responder.get(ELEMENT)
    responder_attrs = responder.get(NATIVE_ATTRS)
    responder_key = identity(responder_token)
    if responder_key[0] != root["pid"] or not isinstance(responder_attrs, dict):
        raise ValueError("AX input first responder is not a same-process native element; no input submitted")
    _, matches = native_matches(snapshot, root, selectors)
    if len(matches) != 1:
        raise ValueError(f"AX input selector matches={len(matches)}; exactly one native element is required")
    match = matches[0]
    target_key = identity(match["token"])
    if target_key[0] != root["pid"]:
        raise ValueError("AX input target belongs to another process; no input submitted")
    if target_key != responder_key:
        raise ValueError("AX input target is not the current first responder; no input submitted")
    traits, responder_traits = match["native"].get(2004), responder_attrs.get(2004)
    if (type(traits) is not int or traits < 0 or not traits & TEXT_ENTRY_TRAIT or
            type(responder_traits) is not int or responder_traits < 0 or
            not responder_traits & TEXT_ENTRY_TRAIT):
        raise ValueError("AX input first responder is not a known text-entry element; no input submitted")
    value, responder_value = match["native"].get(2006), responder_attrs.get(2006)
    if type(value) is not str or type(responder_value) is not str or responder_value != value:
        raise ValueError("AX input current value is unavailable or inconsistent; no input submitted")
    return match, value


def native_records_for_identity(snapshot, target_key):
    """Find fresh snapshot occurrences by exact native identity, without stale selectors."""
    matches, pending = [], [snapshot]
    while pending:
        record = pending.pop()
        if identity(record.get(ELEMENT)) == target_key:
            matches.append(record)
        pending.extend(record[CHILDREN])
    return matches


async def stop_input_child(process):
    """Boundedly terminate/reap the dedicated child process group."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), 0.5)
    except (TimeoutError, ProcessLookupError):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), 1.0)
    except (TimeoutError, ProcessLookupError):
        pass


async def run_input_child(cli, device_id, text):
    """Run the existing replace-all CLI once in its own bounded process group."""
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            cli, "-s", device_id, "text", "--replace-all", text,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=None,
            start_new_session=True)
        try:
            async with asyncio.timeout(12):
                return await process.wait()
        except TimeoutError as error:
            raise TimeoutError("replace-all child exceeded its 12 second deadline") from error
    finally:
        if process is not None:
            # Reap the leader and terminate any helper left in its private group.
            await stop_input_child(process)


def public_matches(matches):
    """Expose snapshot-local path IDs and public AX fields, never native handles."""
    output = []
    for match in matches:
        node = match["node"]
        item = {key: node[key] for key in
                ("id", "parentId", "depth", "identifier", "label", "value", "frame", "frameUnavailable")
                if key in node}
        if "5003" in node.get("nativeAttributes", {}):
            item["nativeAttributes"] = {"5003": node["nativeAttributes"]["5003"]}
        for key in ("processIdentifier", "externalProcessReference"):
            if key in node:
                item[key] = node[key]
        item["pathIds"] = list(match["nodeIds"])
        output.append(item)
    return output


def public_scroll_state(match, state):
    """Report selected public fields and live state, never the native token."""
    node = match["node"]
    item = {key: node[key] for key in
            ("id", "parentId", "depth", "identifier", "label", "value", "frame", "frameUnavailable")
            if key in node}
    if "5003" in node.get("nativeAttributes", {}):
        item["nativeAttributes"] = {"5003": node["nativeAttributes"]["5003"]}
    for key in ("processIdentifier", "externalProcessReference"):
        if key in node:
            item[key] = node[key]
    item["pathIds"] = list(match["nodeIds"])
    for key, source in (("enabled", 27), ("focused", 28), ("selected", 30), ("visible", 32)):
        if source in state:
            item[key] = bool(state[source])
    return item


def frame_within_display(rect, display):
    """Require the full native frame to fit in current logical display bounds."""
    if not isinstance(rect, dict) or not isinstance(display, dict):
        return False
    x, y, width, height = (rect.get(key) for key in ("x", "y", "width", "height"))
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in (x, y, width, height)) or width <= 0 or height <= 0:
        return False
    return (x >= display["x"] and y >= display["y"] and
            x + width <= display["x"] + display["width"] and
            y + height <= display["y"] + display["height"])


ALERT_CONTAINER_CLASS = "_UIAlertControllerPhoneTVMacView"
ALERT_BUTTON_CLASS = "_UIInterfaceActionCustomViewRepresentationView"
ALERT_POSTCONDITION_SETTLE_S = 2.0
ALERT_POSTCONDITION_POLL_S = 0.1


def _native_true(value):
    return type(value) in (bool, int) and value in (0, 1) and bool(value)


def _has_path_under(match, ancestor, nodes_by_id):
    ancestor_paths = set(ancestor["nodeIds"])
    for node_id in match["nodeIds"]:
        current = nodes_by_id[node_id]
        while current is not None:
            if current["id"] in ancestor_paths:
                return True
            parent_id = current.get("parentId")
            current = nodes_by_id.get(parent_id) if parent_id is not None else None
    return False


def resolve_alert_press_targets(snapshot, root, alert_label, button_label):
    """Resolve one visible native system alert and its exact descendant button."""
    nodes, _ = snapshot_nodes(snapshot, root)
    nodes_by_id = {node["id"]: node for node in nodes}
    _, modal_matches = native_matches(snapshot, root, {"className": ALERT_CONTAINER_CLASS})
    modals = [match for match in modal_matches
              if identity(match["token"])[0] == root["pid"] and _native_true(match["native"].get(2025))]
    if len(modals) != 1:
        raise ValueError("alert-press requires exactly one visible native alert container")
    modal = modals[0]
    if modal["native"].get(2001) != alert_label:
        raise ValueError("alert-press requires the unique visible native alert container to have the exact title")
    _, button_matches = native_matches(snapshot, root,
                                       {"label": button_label, "className": ALERT_BUTTON_CLASS})
    buttons = [match for match in button_matches
               if identity(match["token"])[0] == root["pid"] and
               _native_true(match["native"].get(2025)) and
               _has_path_under(match, modal, nodes_by_id)]
    if len(buttons) != 1:
        raise ValueError("alert-press requires exactly one visible exact-label native button in the alert")
    if (not modal["native"].get(2003) or not buttons[0]["native"].get(2003)):
        raise ValueError("alert-press modal or button frame is unavailable")
    return modal, buttons[0]


def validate_springboard_snapshot(snapshot, root):
    if identity(snapshot.get(ELEMENT)) != identity(root):
        raise ValueError("alert-press SpringBoard snapshot root changed")
    native = snapshot.get(NATIVE_ATTRS)
    if (not isinstance(native, dict) or native.get(5003) != "SpringBoard" or
            native.get(3003) != "com.apple.springboard"):
        raise ValueError("alert-press requires a SpringBoard root")


def ordinary_nodes(captured, root):
    """The existing AXChildren graph, using the same bounded attribute reads."""
    nodes, by_handle = [], {}
    pending = deque([(identity(root), None, 0)])
    while pending:
        key, parent, depth = pending.popleft()
        attrs = captured[key]
        node_id = "n" + str(len(nodes))
        node = {"id": node_id, "parentId": parent, "depth": depth, "children": [],
                "attributeSource": "AXAttributes", **node_fields(attrs)}
        nodes.append(node)
        by_handle[key] = [node]
        if parent is not None:
            nodes[int(parent[1:])]["children"].append(node_id)
        pending.extend((identity(child), node_id, depth + 1) for child in attrs[8])
    return nodes, by_handle


def identity(obj):
    if not isinstance(obj, dict) or type(obj.get("pid")) is not int or type(obj.get("objectID")) is not int:
        raise ValueError("invalid AX element handle")
    if obj["pid"] <= 0 or not 0 <= obj["objectID"] < 2 ** 64:
        raise ValueError("invalid AX element identity")
    return obj["pid"], obj["objectID"]


def attributes(obj):
    if not isinstance(obj, dict):
        raise ValueError("AX attributes unavailable")
    if 8 not in obj:
        raise ValueError("AX children unavailable; no complete graph emitted")
    for key in (8, 9):
        if key in obj and not isinstance(obj[key], list):
            raise ValueError("invalid AX child list")
    return obj


def frame(obj):
    if not isinstance(obj, dict) or set(obj) != {"x", "y", "width", "height"}:
        raise ValueError("AX frame unavailable")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in obj.values()):
        raise ValueError("invalid AX frame")
    if obj["width"] < 0 or obj["height"] < 0:
        raise ValueError("invalid AX frame dimensions")
    return obj


def node_fields(attrs):
    result = {}
    for key, name in FIELDS.items():
        if key not in attrs or attrs[key] is None:
            continue
        val = attrs[key]
        if key == 21:
            if val == {"unavailable": "CGRectNull"}:
                result["frameUnavailable"] = "CGRectNull"
            else:
                result[name] = frame(val)
        elif key in BOOL_FIELDS:
            if type(val) not in (bool, int) or val not in (0, 1):
                raise ValueError("invalid AX state field")
            result[name] = bool(val)
        elif key == 77:
            if type(val) is not int or not -(1 << 63) <= val < (1 << 64):
                raise ValueError("invalid AX traits")
            result[name] = str(val & ((1 << 64) - 1))
        elif key in (45, 51):
            if type(val) is not int:
                raise ValueError("invalid AX role")
            result[name] = val
        elif isinstance(val, (str, int, float, bool)):
            if isinstance(val, float) and not math.isfinite(val):
                raise ValueError("invalid AX numeric field")
            result[name] = val
        else:
            raise ValueError("unrecognized AX semantic field")
    return result


def has_description(attrs):
    text = attrs.get(33)
    return isinstance(text, str) and bool(text.strip())


def signature(attrs, text_attribute):
    return (attrs.get(21), attrs.get(text_attribute), tuple(identity(c) for c in attrs.get(8, [])))


def display_geometry(info):
    if not isinstance(info, dict) or not isinstance(info.get("displays"), list):
        raise ValueError("display metadata unavailable; select --pid")
    primary = [d for d in info["displays"] if isinstance(d, dict) and d.get("primary") is True]
    if len(primary) != 1:
        raise ValueError("ambiguous primary display; select --pid")
    display = primary[0]
    bounds, scale = display.get("bounds"), display.get("pointScale")
    if (not isinstance(bounds, list) or len(bounds) != 2 or
            any(not isinstance(v, list) or len(v) != 2 for v in bounds) or
            any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for pair in bounds for v in pair) or
            not isinstance(scale, (int, float)) or isinstance(scale, bool) or not math.isfinite(scale) or scale <= 0 or
            any(v <= 0 for v in bounds[1])):
        raise ValueError("invalid display bounds/scale; select --pid")
    if display.get("nativeOrientation") != "rot0" or display.get("currentOrientation") != "rot0":
        raise ValueError("unverified AX hit-test orientation; select --pid")
    # Effective display bounds account for scaled modes (12 mini: 1125x2436,
    # while nativeSize is 1080x2340). AX logical points use bounds/pointScale.
    return {"x": bounds[0][0] / scale, "y": bounds[0][1] / scale,
            "width": bounds[1][0] / scale, "height": bounds[1][1] / scale}


async def capture(rsd, args):
    # This service overrides channel zero; pymobiledevice3 is pinned because
    # channel registration below uses its connection implementation directly.
    from pymobiledevice3.dtx import DTXConnection
    from pymobiledevice3.dtx.service import DTXControlService, dtx_on_invoke
    from pymobiledevice3.exceptions import ConnectionTerminatedError

    queue = asyncio.Queue(maxsize=128)
    fatal = []
    received_bytes = 0

    def fail(message):
        if not fatal:
            fatal.append(message)
            try:
                queue.put_nowait(b"")
            except asyncio.QueueFull:
                pass

    class Control(DTXControlService):
        @dtx_on_invoke("hostAPIVersion")
        async def host_version(self):
            return 7

        @dtx_on_invoke("processDataFromRemoteDevice:")
        async def packet(self, data):
            nonlocal received_bytes
            if not isinstance(data, bytes) or len(data) > 20 * 1024 * 1024:
                fail("invalid AX packet")
            else:
                received_bytes += len(data)
                if received_bytes > 40 * 1024 * 1024 or fatal:
                    fail("AX incoming data budget")
                    return
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    fail("AX notification queue limit")

    desc = rsd.peer_info.get("Services", {}).get(SERVICE)
    if not isinstance(desc, dict) or not str(desc.get("Port", "")).isdigit():
        raise ValueError("AX service is not advertised; check Developer Mode and DDI")
    conn = await asyncio.wait_for(rsd.create_service_connection(int(desc["Port"])), 4)
    dtx = DTXConnection(conn.reader, conn.writer)
    ctrl = Control(dtx._control_svc._ctx)
    dtx._control_svc = ctrl
    dtx._services[0] = ctrl
    subscribed = False
    cleanup = {"subscriptionStop": "not-started", "connectionClosed": False}
    unsolicited = []
    packet_bytes = 0
    started = time.monotonic()
    try:
        await asyncio.wait_for(dtx.connect(), 4)
        api = await asyncio.wait_for(dtx._ctrl_channel.invoke("deviceAPIVersion"), 3)
        if api != 26:
            raise ValueError("unverified device AX API version")
        await asyncio.wait_for(dtx._ctrl_channel.invoke("clientNeedsAccessibility:", True), 3)
        subscribed = True

        async def read(kind, params, token=None, *, action=0):
            nonlocal packet_bytes
            if fatal:
                raise ValueError(fatal[0])
            # Exactly one outstanding semantic request. A timeout aborts the
            # connection; late type-5 replies are never assigned to a new node.
            data = request(kind, params, translation=token, action=action)
            received_reply = False
            try:
                async with asyncio.timeout(3):
                    if kind == 7:
                        if action == 5:
                            args.press_state = "submitted"
                        elif action == 11:
                            args.scroll_state = "submitted"
                    await dtx._ctrl_channel.invoke("processDataFromHost:", data)
                    while True:
                        raw = await queue.get()
                        packet_bytes += len(raw)
                        if packet_bytes > 40 * 1024 * 1024 or fatal:
                            raise ValueError(fatal[0] if fatal else "AX response budget")
                        reply = decode(raw)
                        if not isinstance(reply, dict):
                            raise ValueError("invalid AX response")
                        if reply.get("associatedRequestType") != kind:
                            unsolicited.append(reply)
                            if len(unsolicited) > 256:
                                raise ValueError("AX notification budget")
                            continue
                        received_reply = True
                        if kind == 7 and ("error" not in reply or type(reply["error"]) is not int):
                            action_name = "scroll-to-visible" if action == 11 else "press"
                            raise ValueError(f"AX {action_name} semantic status unavailable; do not retry automatically")
                        if reply.get("error") not in (None, 0):
                            raise ValueError("AX request refused: error " + str(reply["error"]))
                        if kind == 2 and (reply.get("attribute") != 52 or
                                          identity(reply.get("associatedTranslationObject")) != identity(token)):
                            raise ValueError("AX snapshot response attribute/element mismatch")
                        return reply.get("resultData")
            except TimeoutError as error:
                target = (f" pid={token['pid']} objectID={token['objectID']}" if token else "")
                fields = (f" attributes={params['attributes']}" if kind == 5 else
                          " attribute=52" if kind == 2 else "")
                action_label = "scroll-to-visible" if action == 11 else "press"
                suffix = f"; {action_label} outcome unknown; do not retry automatically" if kind == 7 else ""
                raise TimeoutError(f"AX request type={kind}{target}{fields} timed out{suffix}") from error
            except Exception as error:
                if kind == 7 and not received_reply:
                    action_label = "scroll-to-visible" if action == 11 else "press"
                    raise RuntimeError(f"AX {action_label} outcome unknown after submission; do not retry automatically") from error
                raise

        async def node_attributes(token):
            attrs = attributes(await read(5, {"attributes": ATTRS}, token))
            if not has_description(attrs):
                label = await read(5, {"attributes": [3]}, token)
                if not isinstance(label, dict):
                    raise ValueError("AX label attributes unavailable")
                if 3 in label:
                    attrs[3] = label[3]
            return attrs

        async def app(pid):
            obj = await read(1, {"pid": pid})
            if identity(obj)[0] != pid or not obj.get("isApplicationElement"):
                raise ValueError("AX application mismatch")
            return obj

        async def hit(point):
            obj = await read(6, {"point": point})
            identity(obj)
            return obj

        async def validate_snapshot_selection():
            if identity(await app(root["pid"])) != identity(root):
                raise ValueError("AX application root identity changed during native snapshot")
            if hit_point is not None and identity(await hit(hit_point))[0] != root["pid"]:
                raise ValueError("displayed AX process changed during native snapshot")
            if display is not None:
                from pymobiledevice3.remote.core_device.device_info import DeviceInfoService
                async with DeviceInfoService(rsd) as service:
                    if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                        raise ValueError("AX display changed during native snapshot")

        operation = getattr(args, "operation", None)
        selecting_action = operation in ("press", "scroll-to-visible", "input")
        selectors = {key: getattr(args, attr, None) for key, attr in
                     (("identifier", "identifier"), ("label", "label"), ("value", "value"),
                      ("className", "class_name"))
                     if getattr(args, attr, None) is not None}
        if args.pid and not selecting_action:
            root = await app(args.pid)
            selection = "explicit-pid"
            hit_point = None
            display = None
        else:
            from pymobiledevice3.remote.core_device.device_info import DeviceInfoService
            async with DeviceInfoService(rsd) as service:
                rect = display_geometry(await asyncio.wait_for(service.get_display_info(), 4))
            display = rect
            hit_point = (rect["x"] + rect["width"] * args.point[0],
                         rect["y"] + rect["height"] * args.point[1])
            selected = await hit(hit_point)
            if args.pid and selected["pid"] != args.pid:
                action_name = {"scroll-to-visible": "scroll", "input": "input"}.get(operation, "press")
                raise ValueError(f"AX {action_name} PID is not the displayed application at the selected point")
            root = await app(selected["pid"])
            selection = "explicit-pid+hit-test" if args.pid else "hit-test"

        if operation == "locate":
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            await validate_snapshot_selection()
            _, matches = native_matches(native, root, selectors)
            return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                    "application": {"pid": root["pid"], "selection": selection},
                    "scope": "native-locator", "snapshotId": str(uuid.uuid4()),
                    "selectors": dict(selectors), "matchCount": len(matches),
                    "unique": len(matches) == 1, "matches": public_matches(matches),
                    "atomic": False, "cleanup": cleanup,
                    "queryMs": round((time.monotonic() - started) * 1000, 3),
                    "deviceAPIVersion": api}

        if operation == "wait":
            deadline = time.monotonic() + args.timeout
            last = None
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = "timed_out"
                    break
                try:
                    async with asyncio.timeout(remaining) as budget:
                        native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
                        await validate_snapshot_selection()
                except TimeoutError:
                    if not budget.expired():
                        raise
                    status = "timed_out"
                    break
                _, matches = native_matches(native, root, selectors)
                if len(matches) > 1:
                    raise ValueError(f"AX wait selector is ambiguous: matches={len(matches)}")
                satisfied = (len(matches) == 1) if args.wait_for == "present" else (len(matches) == 0)
                last = {"snapshotId": str(uuid.uuid4()), "matchCount": len(matches),
                        "matches": public_matches(matches)}
                if satisfied:
                    status = "satisfied"
                elif time.monotonic() >= deadline:
                    status = "timed_out"
                else:
                    await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
                    continue
                break
            return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                    "application": {"pid": root["pid"], "selection": selection},
                    "scope": "native-wait", "status": status, "waitFor": args.wait_for,
                    "selectors": dict(selectors), **(last or {"snapshotId": None, "matchCount": 0, "matches": []}),
                    "atomic": False, "cleanup": cleanup,
                    "queryMs": round((time.monotonic() - started) * 1000, 3),
                    "deviceAPIVersion": api}

        if operation == "hit-test":
            fields = node_fields(await node_attributes(selected))
            if identity(await hit(hit_point)) != identity(selected):
                raise ValueError("AX hit target changed during collection")
            async with DeviceInfoService(rsd) as service:
                if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                    raise ValueError("AX display changed during hit test")
            return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                    "application": {"pid": selected["pid"], "selection": "hit-test"},
                    "scope": "point-hit-test", "coordinateSpace": "device-logical-points",
                    "point": {"x": hit_point[0], "y": hit_point[1]}, "target": fields,
                    "atomic": False, "targetStable": True, "cleanup": cleanup,
                    "queryMs": round((time.monotonic() - started) * 1000, 3), "deviceAPIVersion": api}

        if operation == "alert-press":
            from pymobiledevice3.remote.core_device.device_info import DeviceInfoService
            async with DeviceInfoService(rsd) as service:
                display = display_geometry(await asyncio.wait_for(service.get_display_info(), 4))

            async def validate_alert_context():
                if identity(await app(root["pid"])) != identity(root):
                    raise ValueError("alert-press SpringBoard root identity changed")
                async with DeviceInfoService(rsd) as service:
                    if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                        raise ValueError("alert-press display changed")

            first_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            validate_springboard_snapshot(first_native, root)
            first_modal, first_button = resolve_alert_press_targets(
                first_native, root, args.alert_label, args.label)
            await validate_alert_context()

            second_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            validate_springboard_snapshot(second_native, root)
            modal, button = resolve_alert_press_targets(
                second_native, root, args.alert_label, args.label)
            await validate_alert_context()

            def same_native_observation(left, right, fields):
                return (identity(left["token"]) == identity(right["token"]) and
                        all(left["native"].get(field) == right["native"].get(field) for field in fields))

            if not same_native_observation(first_modal, modal, (2001, 2003, 5003)):
                raise ValueError("alert-press modal identity/frame/class/label changed before action")
            if not same_native_observation(first_button, button, (2001, 2003, 5003)):
                raise ValueError("alert-press button identity/frame/class/label changed before action")

            modal_frame = modal["native"].get(2003)
            button_frame = button["native"].get(2003)
            if (not frame_within_display(modal_frame, display) or
                    not frame_within_display(button_frame, display)):
                raise ValueError("alert-press modal or button frame is not fully within the display")
            live = await read(5, {"attributes": [21, 25, 27, 32]}, button["token"])
            expected_identifier = button["native"].get(5019)
            if (not isinstance(live, dict) or
                    (expected_identifier is not None and live.get(25) != expected_identifier) or
                    live.get(21) != button_frame or
                    any(type(live.get(key)) not in (bool, int) or live[key] not in (0, 1) or not live[key]
                        for key in (27, 32))):
                raise ValueError("alert-press button live state/frame is not known enabled and visible")
            await validate_alert_context()

            accepted = await read(7, None, button["token"], action=5)
            if type(accepted) not in (bool, int) or accepted not in (0, 1):
                raise ValueError("alert-press returned no known native result; do not retry automatically")
            base_result = {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                           "application": {"pid": root["pid"], "selection": "explicit-pid"},
                           "scope": "springboard-modal-action", "alertLabel": args.alert_label,
                           "buttonLabel": args.label, "hitTestVerified": False,
                           "modal": {"label": modal["native"].get(2001), "frame": modal_frame,
                                     "nativeAttributes": {"5003": ALERT_CONTAINER_CLASS}},
                           "button": {"label": button["native"].get(2001), "frame": button_frame,
                                      "enabled": True, "visible": True,
                                      "nativeAttributes": {"5003": ALERT_BUTTON_CLASS}},
                           "action": {"name": "alert-press", "nativeAccepted": bool(accepted),
                                      "effectVerified": False},
                           "postconditionVerified": False, "effectVerified": False,
                           "atomic": False, "cleanup": cleanup,
                           "queryMs": round((time.monotonic() - started) * 1000, 3),
                           "deviceAPIVersion": api}
            if not accepted:
                args.press_state = "refused"
                base_result["status"] = "native_refused"
                base_result["postconditionFailure"] = "native-action-refused"
                return base_result

            args.press_state = "accepted"
            def no_longer_visible(records):
                if not records:
                    return True
                return all(type(record[NATIVE_ATTRS].get(2025)) in (bool, int) and
                           record[NATIVE_ATTRS].get(2025) in (0, 1) and
                           not record[NATIVE_ATTRS].get(2025) for record in records)

            settle_started = time.monotonic()
            settle_deadline = settle_started + ALERT_POSTCONDITION_SETTLE_S
            observations = 0
            modal_gone = button_gone = False
            while True:
                remaining = settle_deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    async with asyncio.timeout(remaining):
                        post_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
                        validate_springboard_snapshot(post_native, root)
                        snapshot_nodes(post_native, root)
                        await validate_alert_context()
                        modal_after = native_records_for_identity(post_native, identity(modal["token"]))
                        button_after = native_records_for_identity(post_native, identity(button["token"]))
                        modal_gone = no_longer_visible(modal_after)
                        button_gone = no_longer_visible(button_after)
                        observations += 1
                except TimeoutError as error:
                    raise TimeoutError("alert-press postcondition observation exceeded its settle deadline") from error
                if (modal_gone and button_gone) or time.monotonic() >= settle_deadline:
                    break
                await asyncio.sleep(min(ALERT_POSTCONDITION_POLL_S, settle_deadline - time.monotonic()))

            verified = modal_gone and button_gone
            base_result["postcondition"] = {"originalModalNoLongerVisible": modal_gone,
                                            "originalButtonNoLongerVisible": button_gone}
            base_result["postconditionObservations"] = observations
            base_result["postconditionElapsedMs"] = round((time.monotonic() - settle_started) * 1000, 3)
            base_result["postconditionVerified"] = verified
            base_result["effectVerified"] = verified
            base_result["action"]["effectVerified"] = verified
            base_result["queryMs"] = round((time.monotonic() - started) * 1000, 3)
            if not verified:
                base_result["status"] = "alert_postcondition_failed"
                base_result["postconditionFailure"] = "original-modal-or-button-still-visible"
            return base_result

        if operation == "input":
            input_options = {**SNAPSHOT_OPTIONS,
                             "attributes": [*SNAPSHOT_ATTRS, 3002]}
            native = await read(2, {"parameter": input_options}, root)
            await validate_snapshot_selection()
            match, before_value = resolve_input_target(native, root, selectors)
            token, native_attrs, node = match["token"], match["native"], match["node"]
            await validate_snapshot_selection()

            # Recheck the target's live state and exact hit before invoking the
            # existing CLI, which owns clipboard mutation and keyboard delivery.
            before_live = await read(5, {"attributes": [21, 25, 27, 32]}, token)
            expected_identifier = (args.identifier if "identifier" in selectors
                                   else native_attrs.get(5019))
            if (not isinstance(before_live, dict) or
                    (expected_identifier is not None and before_live.get(25) != expected_identifier)):
                raise ValueError("AX input target native identifier changed; no input submitted")
            if before_live.get(21) != native_attrs.get(2003):
                raise ValueError("AX input target frame changed; no input submitted")
            if any(type(before_live.get(key)) not in (bool, int) or before_live[key] != 1
                   for key in (27, 32)):
                raise ValueError("AX input target is not known enabled and visible; no input submitted")
            rect = node.get("frame")
            if not rect or rect["width"] <= 0 or rect["height"] <= 0:
                raise ValueError("AX input target has no usable frame; no input submitted")
            center = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
            if identity(await hit(center)) != identity(token):
                raise ValueError("AX input target is not the frame-centre hit element; no input submitted")
            if identity(await hit(hit_point))[0] != root["pid"]:
                raise ValueError("AX displayed process changed; no input submitted")
            async with DeviceInfoService(rsd) as service:
                if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                    raise ValueError("AX display changed; no input submitted")

            # A final fresh snapshot verifies the selector, actual responder,
            # same process, and current string value immediately before input.
            final_native = await read(2, {"parameter": input_options}, root)
            await validate_snapshot_selection()
            final_match, final_value = resolve_input_target(final_native, root, selectors)
            if identity(final_match["token"]) != identity(token):
                raise ValueError("AX input target changed before submission; no input submitted")
            if final_value != before_value:
                raise ValueError("AX input target value changed before submission; no input submitted")
            token, native_attrs, node = final_match["token"], final_match["native"], final_match["node"]
            final_live = await read(5, {"attributes": [21, 25, 27, 32]}, token)
            if (not isinstance(final_live, dict) or
                    (expected_identifier is not None and final_live.get(25) != expected_identifier) or
                    final_live.get(21) != native_attrs.get(2003) or
                    any(type(final_live.get(key)) not in (bool, int) or final_live[key] != 1
                        for key in (27, 32))):
                raise ValueError("AX input target state changed before submission; no input submitted")
            rect = node.get("frame")
            if not rect or rect["width"] <= 0 or rect["height"] <= 0:
                raise ValueError("AX input target has no usable frame; no input submitted")
            center = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
            if identity(await hit(center)) != identity(token):
                raise ValueError("AX input target is not the frame-centre hit element; no input submitted")
            if identity(await hit(hit_point))[0] != root["pid"]:
                raise ValueError("AX displayed process changed; no input submitted")
            async with DeviceInfoService(rsd) as service:
                if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                    raise ValueError("AX display changed; no input submitted")

            args.input_state = "submitted"
            try:
                child_exit = await run_input_child(args.input_cli, args.device_id, args.text)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                args.input_state = "child-unknown"
                return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                        "application": {"pid": root["pid"], "selection": selection},
                        "scope": "native-first-responder-input", "selectors": dict(selectors),
                        "action": {"name": "replace-all-input", "childExitCode": None,
                                   "textLength": len(args.text), "childErrorType": type(error).__name__},
                        "before": {"identifier": node.get("identifier"), "label": node.get("label"),
                                   "frame": node.get("frame"), "valueAvailable": type(before_value) is str},
                        "after": None, "postconditionVerified": False,
                        "status": "child_outcome_unknown",
                        "postconditionFailure": "child-timeout-or-launch-failure",
                        "atomic": False, "cleanup": cleanup,
                        "queryMs": round((time.monotonic() - started) * 1000, 3),
                        "deviceAPIVersion": api}
            args.input_exit_code = child_exit
            args.input_state = "child-exited-zero" if child_exit == 0 else "child-exited-nonzero"

            post_native = await read(2, {"parameter": input_options}, root)
            await validate_snapshot_selection()
            _, post_by_handle = snapshot_nodes(post_native, root)
            post_records = native_records_for_identity(post_native, identity(token))
            post = None
            verified = False
            failure = None
            if not post_records:
                failure = "target-not-found-after-input"
            elif identity(post_records[0][ELEMENT])[0] != root["pid"]:
                failure = "target-process-changed-after-input"
            elif any(record[NATIVE_ATTRS].get(2006) != args.text or
                     type(record[NATIVE_ATTRS].get(2006)) is not str for record in post_records):
                failure = "exact-value-not-observed-after-input"
            else:
                post_node = post_by_handle[identity(token)][0]
                post = {key: post_node[key] for key in
                        ("id", "parentId", "depth", "identifier", "label", "frame", "frameUnavailable")
                        if key in post_node}
                if "nativeAttributes" in post_node:
                    post["nativeAttributes"] = dict(post_node["nativeAttributes"])
                post_live = await read(5, {"attributes": [21, 25, 27, 32]}, token)
                expected_post_identifier = (args.identifier if "identifier" in selectors
                                            else post_node.get("identifier"))
                if (not isinstance(post_live, dict) or
                        (expected_post_identifier is not None and
                         post_live.get(25) != expected_post_identifier) or
                        post_live.get(21) != post_node.get("frame") or
                        any(type(post_live.get(key)) not in (bool, int) or post_live[key] != 1
                            for key in (27, 32))):
                    failure = "target-state-not-verified-after-input"
                else:
                    rect = post_node.get("frame")
                    if not rect or rect["width"] <= 0 or rect["height"] <= 0:
                        failure = "target-frame-not-usable-after-input"
                    else:
                        center = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
                        if identity(await hit(center)) != identity(token):
                            failure = "target-center-hit-changed-after-input"
                        else:
                            await validate_snapshot_selection()
                            verified = True
            result = {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                      "application": {"pid": root["pid"], "selection": selection},
                      "scope": "native-first-responder-input", "selectors": dict(selectors),
                      "action": {"name": "replace-all-input", "childExitCode": child_exit,
                                 "textLength": len(args.text)},
                      "before": {"identifier": node.get("identifier"), "label": node.get("label"),
                                 "frame": node.get("frame"), "valueAvailable": type(before_value) is str},
                      "after": post, "postconditionVerified": verified,
                      "atomic": False, "cleanup": cleanup,
                      "queryMs": round((time.monotonic() - started) * 1000, 3),
                      "deviceAPIVersion": api}
            if child_exit != 0:
                result["status"] = "child_failed"
                result["postconditionFailure"] = failure
            elif not verified:
                result["status"] = "postcondition_failed"
                result["postconditionFailure"] = failure
            return result

        if operation == "press":
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            token, native_attrs, node = resolve_native_target(native, root, selectors, operation="AX press")
            if identity(token)[0] != root["pid"]:
                raise ValueError("AX press target belongs to another process; no action sent")
            if "label" in selectors or "value" in selectors or "className" in selectors:
                # Selector qualifiers are re-resolved from a second observation
                # immediately before the existing live-state/hit/display guards.
                confirmed_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
                confirmed_token, native_attrs, node = resolve_native_target(
                    confirmed_native, root, selectors, operation="AX press")
                if identity(confirmed_token) != identity(token):
                    raise ValueError("AX press selector target changed; no action sent")
                if identity(confirmed_token)[0] != root["pid"]:
                    raise ValueError("AX press target belongs to another process; no action sent")
                token = confirmed_token
            target = {key: node[key] for key in
                      ("identifier", "label", "frame", "frameUnavailable", "nativeAttributes")
                      if key in node}
            confirmed = await read(5, {"attributes": [21, 25, 27, 32]}, token)
            expected_identifier = (args.identifier if "identifier" in selectors
                                   else native_attrs.get(5019))
            if (not isinstance(confirmed, dict) or
                    (expected_identifier is not None and confirmed.get(25) != expected_identifier)):
                raise ValueError("AX press target native identifier changed; no action sent")
            if 2003 in native_attrs and confirmed.get(21) != native_attrs[2003]:
                raise ValueError("AX press target frame changed; no action sent")
            if any(type(confirmed.get(key)) not in (bool, int) or confirmed[key] != 1 for key in (27, 32)):
                raise ValueError("AX press target is not known enabled and visible; no action sent")
            target.update(enabled=True, visible=True)
            rect = target.get("frame")
            if not rect or rect["width"] <= 0 or rect["height"] <= 0:
                raise ValueError("AX press target has no usable frame; no action sent")
            candidate = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
            if identity(await hit(candidate)) != identity(token):
                raise ValueError("AX press target is not the frame-centre hit element; no action sent")
            if identity(await hit(hit_point))[0] != root["pid"]:
                raise ValueError("AX displayed process changed; no action sent")
            async with DeviceInfoService(rsd) as service:
                if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                    raise ValueError("AX display changed; no action sent")
            accepted = await read(7, None, token, action=5)
            if type(accepted) not in (bool, int) or accepted not in (0, 1):
                raise ValueError("AX press returned no known native result; do not retry automatically")
            if not accepted:
                args.press_state = "refused"
                raise ValueError("AX native press refused the element")
            args.press_state = "accepted"
            action = {"name": "press", "nativeAccepted": True, "effectVerified": False}
            if "identifier" in selectors:
                action["identifier"] = args.identifier
            if "label" in selectors or "value" in selectors or "className" in selectors:
                action["selectors"] = dict(selectors)
            return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                    "application": {"pid": root["pid"], "selection": selection},
                    "action": action,
                    "target": target, "coordinateSpace": "device-logical-points",
                    "cleanup": cleanup, "queryMs": round((time.monotonic() - started) * 1000, 3),
                    "deviceAPIVersion": api}

        if operation == "scroll-to-visible":
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            await validate_snapshot_selection()
            _, matches = native_matches(native, root, selectors)
            if len(matches) != 1:
                raise ValueError(f"AX scroll-to-visible selector matches={len(matches)}; exactly one native element is required")
            match = matches[0]
            token, native_attrs, node = match["token"], match["native"], match["node"]
            if identity(token)[0] != root["pid"]:
                raise ValueError("AX scroll-to-visible target belongs to another process; no action sent")
            if "label" in selectors or "value" in selectors or "className" in selectors:
                confirmed_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
                await validate_snapshot_selection()
                _, confirmed_matches = native_matches(confirmed_native, root, selectors)
                if len(confirmed_matches) != 1:
                    raise ValueError(f"AX scroll-to-visible selector changed or became ambiguous: matches={len(confirmed_matches)}")
                confirmed_match = confirmed_matches[0]
                if identity(confirmed_match["token"]) != identity(token):
                    raise ValueError("AX scroll-to-visible selector target changed; no action sent")
                if identity(confirmed_match["token"])[0] != root["pid"]:
                    raise ValueError("AX scroll-to-visible target belongs to another process; no action sent")
                match = confirmed_match
                token, native_attrs, node = match["token"], match["native"], match["node"]

            frame_rect = node.get("frame")
            if not frame_rect or frame_rect["width"] <= 0 or frame_rect["height"] <= 0:
                raise ValueError("AX scroll-to-visible target has no usable frame; no action sent")
            snapshot_visible = native_attrs.get(2025)
            if type(snapshot_visible) not in (bool, int) or snapshot_visible not in (0, 1):
                raise ValueError("AX scroll-to-visible target visibility is unavailable; no action sent")
            before_live = await read(5, {"attributes": [21, 25, 27, 32]}, token)
            if not isinstance(before_live, dict):
                raise ValueError("AX scroll-to-visible target state unavailable; no action sent")
            expected_identifier = (args.identifier if "identifier" in selectors
                                   else native_attrs.get(5019))
            if expected_identifier is not None and before_live.get(25) != expected_identifier:
                raise ValueError("AX scroll-to-visible target identifier changed; no action sent")
            if 2003 not in native_attrs or before_live.get(21) != native_attrs[2003]:
                raise ValueError("AX scroll-to-visible target frame changed; no action sent")
            enabled = before_live.get(27)
            visible = before_live.get(32)
            if type(enabled) not in (bool, int) or enabled not in (0, 1) or not enabled:
                raise ValueError("AX scroll-to-visible target is not known enabled; no action sent")
            if (type(visible) not in (bool, int) or visible not in (0, 1) or
                    bool(visible) != bool(snapshot_visible)):
                raise ValueError("AX scroll-to-visible target visibility is unavailable or changed; no action sent")
            await validate_snapshot_selection()
            before = public_scroll_state(match, before_live)

            native_result = await read(7, None, token, action=11)
            if type(native_result) not in (bool, int) or native_result not in (0, 1):
                raise ValueError("AX scroll-to-visible returned no known native result; do not retry automatically")
            args.scroll_state = "native-true" if bool(native_result) else "native-false"

            post_native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            await validate_snapshot_selection()
            _, post_matches = native_matches(post_native, root, selectors)
            post, post_reason = None, None
            postcondition_verified = False
            if len(post_matches) == 0:
                post_reason = "target-not-found-after-action"
            elif len(post_matches) != 1:
                post_reason = "target-ambiguous-after-action"
            else:
                post_match = post_matches[0]
                post = public_matches([post_match])[0]
                if identity(post_match["token"]) != identity(token):
                    post_reason = "target-identity-changed-after-action"
                else:
                    after_live = await read(5, {"attributes": [21, 25, 27, 32]}, token)
                    if not isinstance(after_live, dict):
                        raise ValueError("AX scroll-to-visible post-action target state unavailable; do not retry automatically")
                    post = public_scroll_state(post_match, after_live)
                    await validate_snapshot_selection()
                    after_identifier = (args.identifier if "identifier" in selectors
                                        else post_match["native"].get(5019))
                    after_enabled = after_live.get(27)
                    after_visible = after_live.get(32)
                    frame_after = after_live.get(21)
                    if after_identifier is not None and after_live.get(25) != after_identifier:
                        post_reason = "target-identifier-changed-after-action"
                    elif (not isinstance(frame_after, dict) or
                          frame_after != post_match["native"].get(2003)):
                        post_reason = "target-frame-unavailable-or-changed-after-action"
                    elif type(after_enabled) not in (bool, int) or after_enabled not in (0, 1) or not after_enabled:
                        post_reason = "target-not-known-enabled-after-action"
                    else:
                        native_after_visible = post_match["native"].get(2025)
                        if (type(after_visible) not in (bool, int) or after_visible not in (0, 1) or
                                not after_visible or type(native_after_visible) not in (bool, int) or
                                native_after_visible not in (0, 1) or not native_after_visible):
                            post_reason = "target-not-known-visible-after-action"
                        elif not frame_within_display(frame_after, display):
                            post_reason = "target-frame-outside-display-after-action"
                        else:
                            center = (frame_after["x"] + frame_after["width"] / 2,
                                      frame_after["y"] + frame_after["height"] / 2)
                            if identity(await hit(center)) != identity(token):
                                post_reason = "target-center-hit-changed-after-action"
                            else:
                                await validate_snapshot_selection()
                                postcondition_verified = True

            result = {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                      "application": {"pid": root["pid"], "selection": selection},
                      "scope": "native-scroll-to-visible", "selectors": dict(selectors),
                      "nativeResult": bool(native_result), "before": before, "after": post,
                      "postconditionVerified": postcondition_verified,
                      "atomic": False, "cleanup": cleanup,
                      "queryMs": round((time.monotonic() - started) * 1000, 3),
                      "deviceAPIVersion": api}
            if not postcondition_verified:
                result["status"] = "postcondition_failed"
                result["postconditionFailure"] = post_reason
            return result

        seen = {}
        if args.deep:
            # One native observation owns the whole hierarchy and its geometry.
            # A separate AXChildren walk samples another generation and can fail
            # on animations/overlays even when this native snapshot is complete.
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            nodes, by_handle = snapshot_nodes(native, root)
            if identity(await app(root["pid"])) != identity(root):
                raise ValueError("AX application root identity changed during native snapshot")
        else:
            first = await node_attributes(root)
            root_text_attribute = 33 if has_description(first) else 3
            pending = deque([(root, first, 0)])
            while pending:
                token, attrs, depth = pending.popleft()
                key = identity(token)
                if key in seen:
                    raise ValueError("AX child graph repeats an element")
                if key[0] != root["pid"]:
                    raise ValueError("AX child belongs to another process")
                if depth > MAX_DEPTH or len(seen) >= MAX_NODES:
                    raise ValueError("AX graph limit reached; no partial tree emitted")
                attrs = attributes(attrs if attrs is not None else await node_attributes(token))
                seen[key] = attrs
                pending.extend((child, None, depth + 1) for child in attrs[8])
            nodes, by_handle = ordinary_nodes(seen, root)
            for key, attrs in seen.items():
                node = by_handle[key][0]
                if 9 in attrs:
                    navigation = [identity(c) for c in attrs[9]]
                    node["navigationOrder"] = [by_handle[k][0]["id"] for k in navigation if k in by_handle]
                    node["navigationOutsideGraph"] = sum(k not in by_handle for k in navigation)
                if attrs.get(41) is not None:
                    matches = by_handle.get(identity(attrs[41]), [])
                    node["reportedParentId"] = matches[0]["id"] if matches else None
                    node["reportedParentOutsideGraph"] = not matches
            last = attributes(await read(5, {"attributes": [8, 21, root_text_attribute]}, root))
            before, after = signature(first, root_text_attribute), signature(last, root_text_attribute)
            if before != after:
                changed = ",".join(name for name, old, new in zip(("frame", "text", "children"), before, after)
                                   if old != new)
                raise ValueError(f"AX root changed during collection: pid={root['pid']} "
                                 f"objectID={root['objectID']} changed={changed}")
        if hit_point is not None and identity(await hit(hit_point))[0] != root["pid"]:
            raise ValueError("displayed AX process changed during collection")
        if display is not None:
            async with DeviceInfoService(rsd) as service:
                if display_geometry(await asyncio.wait_for(service.get_display_info(), 4)) != display:
                    raise ValueError("AX display changed during collection")
        if fatal:
            raise ValueError(fatal[0])
        snapshot_ms = round((time.monotonic() - started) * 1000, 3)
        supplemental = {"status": "not-requested"}
        if args.deep and getattr(args, "full_state", False):
            supplemental = {"status": "complete", "scope": "all-native-handles",
                            "attributeSource": "AXAttributes", "atomic": False,
                            "requestedAttributes": STATE_ATTRS,
                            "requestedElementCount": len(by_handle),
                            "attemptedElementCount": 0, "completedElementCount": 0}
            pending_native, supplemented = deque([native]), set()
            state_started = time.monotonic()
            while pending_native:
                record = pending_native.popleft()
                token = record[ELEMENT]
                key = identity(token)
                pending_native.extend(record[CHILDREN])
                if key in supplemented:
                    continue
                supplemented.add(key)
                supplemental["attemptedElementCount"] += 1
                try:
                    state = await read(5, {"attributes": STATE_ATTRS}, token)
                    if not isinstance(state, dict):
                        raise ValueError("AX supplemental state attributes unavailable")
                    # Ignore unsolicited fields: later geometry/text never changes
                    # the native observation, even if the device returns extra keys.
                    fields = node_fields({key: state[key] for key in STATE_ATTRS if key in state})
                except Exception as error:
                    # No further requests on a failed/timed-out semantic stream.
                    # The complete primary tree survives only if cleanup succeeds.
                    supplemental.update(status="failed", exitCode=5 if isinstance(error, TimeoutError) else 1,
                                        error={"type": type(error).__name__, "message": str(error) or "AX supplemental read failed",
                                               "nodeIds": [node["id"] for node in by_handle[key]]})
                    break
                for node in by_handle[key]:
                    node["supplementalAX"] = dict(fields)
                supplemental["completedElementCount"] += 1
            supplemental["queryMs"] = round((time.monotonic() - state_started) * 1000, 3)
        result = {"schemaVersion": 2 if args.deep else 1, "snapshotId": str(uuid.uuid4()),
                  "deviceIdentifier": args.device_id, "udid": rsd.udid,
                  "application": {"pid": root["pid"], "selection": selection},
                  "scope": "application-accessibility", "coordinateSpace": "device-logical-points",
                  "hierarchySource": "AXUserTestingSnapshot" if args.deep else "AXChildren",
                  "attributePolicy": "native-snapshot" if args.deep else "description-first",
                  "stateScope": "native-snapshot" if args.deep else "ordinary-accessible-elements",
                  "uniqueElementCount": len(by_handle), "atomic": False, "rootStable": True,
                  "displayFrame": display, "cleanup": cleanup,
                  "nodeCount": len(nodes), "maxDepth": max(node["depth"] for node in nodes), "nodes": nodes,
                  "queryMs": round((time.monotonic() - started) * 1000, 3),
                  "unsolicitedCount": len(unsolicited), "deviceAPIVersion": api}
        if args.deep:
            result.update(rootStabilityScope="application-identity", snapshotMs=snapshot_ms,
                          supplementalAX=supplemental)
        else:
            result["ordinaryAXNodeCount"] = len(seen)
        return result
    finally:
        try:
            if subscribed:
                try:
                    await asyncio.wait_for(dtx._ctrl_channel.invoke("clientNeedsAccessibility:", False), 2)
                    cleanup["subscriptionStop"] = "acknowledged"
                except ConnectionTerminatedError:
                    # A known close-before-ack race is reported explicitly.
                    cleanup["subscriptionStop"] = "connection-closed-before-ack"
        finally:
            try:
                await asyncio.wait_for(dtx.aclose(), 6)
            finally:
                await asyncio.wait_for(conn.close(), 3)
                cleanup["connectionClosed"] = True


async def run(args):
    import pymobiledevice3.remote.userspace_tunnel as userspace
    from pymobiledevice3.lockdown import create_using_usbmux
    # Restrict to the selected existing USB pairing. The pinned tunnel factory
    # has no cache/connection-type parameters, so bind them in this one-shot
    # process. Keep pairing material in a private temporary folder, then remove.
    cache = Path(tempfile.mkdtemp(prefix="ipb-ax-pair-"))
    userspace.create_using_usbmux = functools.partial(create_using_usbmux, connection_type="USB",
                                                     pairing_records_cache_folder=cache)
    tunnel = userspace.UserspaceRsdTunnel(serial=args.udid, autopair=False, remotepairing_fallback=False)
    result = None
    try:
        rsd = await asyncio.wait_for(tunnel.aopen(), 10)
        if rsd.udid != args.udid:
            raise ValueError("AX tunnel returned another device")
        if not rsd.product_version.startswith("27."):
            raise ValueError("unverified iOS version for AX")
        result = await capture(rsd, args)
        result["deviceOSVersion"] = rsd.product_version
        result["productType"] = rsd.product_type
        return result
    finally:
        try:
            await asyncio.wait_for(tunnel.aclose(), 6)
            if result is not None:
                result["cleanup"]["tunnelClosed"] = True
        finally:
            shutil.rmtree(cache)


def unit_interval(text):
    number = float(text)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("coordinate must be in 0..1")
    return number


def positive_timeout(text):
    try:
        number = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timeout must be a number in (0, 15]") from error
    if not math.isfinite(number) or not 0 < number <= 15:
        raise argparse.ArgumentTypeError("timeout must be a number in (0, 15]")
    return number


def report_failure(args, error, code):
    """A nonzero exit after action submission must never invite an action replay."""
    state = getattr(args, "press_state", "not-sent")
    scroll_state = getattr(args, "scroll_state", "not-sent")
    input_state = getattr(args, "input_state", "not-sent")
    message = str(error) or ("AX query cancelled" if isinstance(error, asyncio.CancelledError) else
                             "AX query timed out; no partial result emitted" if isinstance(error, TimeoutError) else
                             "AX operation failed")
    if getattr(args, "operation", None) in ("press", "alert-press") and state != "not-sent":
        prefix = "native alert press" if getattr(args, "operation", None) == "alert-press" else "native press"
        submitted = "alert press submitted; outcome unknown" if prefix == "native alert press" else "press submitted; outcome unknown"
        status = f"{prefix} accepted" if state == "accepted" else f"{prefix} refused" if state == "refused" else submitted
        print(f"ipb ui: {status}; {type(error).__name__}: {message}; do not retry automatically", file=sys.stderr)
        return 6
    if getattr(args, "operation", None) == "scroll-to-visible" and scroll_state != "not-sent":
        native = {"native-true": "true", "native-false": "false"}.get(scroll_state, "unknown")
        print(f"ipb ui: scroll-to-visible submitted; native result {native}; "
              f"{type(error).__name__}: {message}; do not retry automatically", file=sys.stderr)
        return 6
    if getattr(args, "operation", None) == "input" and input_state != "not-sent":
        exit_code = getattr(args, "input_exit_code", None)
        if exit_code is None:
            status = "input submitted; outcome unknown"
        elif exit_code != 0:
            status = (f"replace-all child exited {exit_code}; clipboard may have changed and input delivery "
                      "may be partial")
        else:
            status = "replace-all child exited 0; exact-value postcondition is unverified"
        print(f"ipb ui: {status}; {type(error).__name__}: {message}; do not retry automatically",
              file=sys.stderr)
        return 6
    print("ipb ui: " + type(error).__name__ + ": " + message, file=sys.stderr)
    return code


def main():
    parser = argparse.ArgumentParser(prog="ipb ui", description="Read, locate, wait for, press, scroll or input through fresh AX elements; no XCTest or phone app.")
    parser.add_argument("operation", nargs="?", choices=("press", "alert-press", "scroll-to-visible", "input", "hit-test", "locate", "wait"),
                        help="press once, press one observed SpringBoard modal button, scroll an element into view, input to a current text responder, read a point, locate fresh native AX matches, or wait for presence/absence")
    parser.add_argument("--identifier", help="exact native accessibility identifier selector (conjunctive)")
    parser.add_argument("--label", help="exact native AX label selector (conjunctive)")
    parser.add_argument("--value", help="exact native AX value selector (conjunctive string only)")
    parser.add_argument("--class", dest="class_name", help="exact native AX class selector (conjunctive)")
    parser.add_argument("--alert-label", help="exact visible native alert title; only for alert-press")
    parser.add_argument("--text", help="text for ui input; never echoed by this command")
    parser.add_argument("--replace-all", action="store_true",
                        help="required explicit confirmation to replace the current text value")
    parser.add_argument("--wait-for", choices=("present", "absent"),
                        help="wait for one unique match or for no matches (default: present)")
    parser.add_argument("--timeout", type=positive_timeout,
                        help="wait deadline in seconds, at most 15 (default: 5)")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--pid", type=int, help="read this application's PID explicitly")
    selector.add_argument("--point", type=unit_interval, nargs=2, default=(0.5, 0.5), metavar=("X", "Y"),
                          help="select the app by a read-only hit test at normalized X Y (default centre)")
    parser.add_argument("--json", action="store_true", help="emit JSON (deep schema 2; ordinary/actions schema 1); default is a text tree")
    parser.add_argument("--deep", action="store_true", help="read the native descendant tree and geometry without an AXChildren walk")
    parser.add_argument("--full-state", action="store_true", help="with --deep, read state/role separately into supplementalAX (extra per-handle requests)")
    args = parser.parse_args()
    if args.full_state and (not args.deep or args.operation is not None):
        parser.error("--full-state requires a --deep dump")
    args.press_state = "not-sent"
    args.scroll_state = "not-sent"
    args.input_state = "not-sent"
    args.input_exit_code = None
    if args.operation is not None and args.deep:
        parser.error("--deep is only used by a dump")
    selector_values = (args.identifier, args.label, args.value, args.class_name)
    selector_operations = ("press", "alert-press", "scroll-to-visible", "input", "locate", "wait")
    if args.operation in selector_operations and not any(value is not None for value in selector_values):
        parser.error(f"{args.operation} requires at least one of --identifier, --label, --value, or --class")
    if args.operation == "hit-test" and args.pid is not None:
        parser.error("hit-test uses --point, not --pid")
    if args.operation not in selector_operations and any(value is not None for value in selector_values):
        parser.error("AX selectors require press, alert-press, scroll-to-visible, input, locate, or wait")
    if args.operation == "alert-press":
        if args.pid is None:
            parser.error("alert-press requires --pid")
        if not args.alert_label:
            parser.error("alert-press requires a non-empty --alert-label")
        if not args.label:
            parser.error("alert-press requires a non-empty --label")
        if any(value is not None for value in (args.identifier, args.value, args.class_name)):
            parser.error("alert-press accepts only --label, not identifier/value/class selectors")
        if not args.json:
            parser.error("alert-press requires --json")
    elif args.alert_label is not None:
        parser.error("--alert-label is only used by alert-press")
    if args.operation == "input":
        if args.text is None or args.text == "":
            parser.error("input requires a non-empty --text")
        if not args.replace_all:
            parser.error("input requires explicit --replace-all")
        args.input_cli = os.environ.get("IPB_AX_CLI")
        if not args.input_cli or not os.path.isabs(args.input_cli):
            parser.error("input requires an absolute IPB_AX_CLI path")
    elif args.text is not None or args.replace_all:
        parser.error("--text and --replace-all are only used by input")
    if args.operation != "wait" and (args.wait_for is not None or args.timeout is not None):
        parser.error("--wait-for and --timeout are only used by wait")
    if args.operation == "wait":
        args.wait_for = args.wait_for or "present"
        args.timeout = args.timeout if args.timeout is not None else 5.0
    args.device_id = os.environ.get("IPB_AX_DEVICE_ID")
    args.udid = os.environ.get("IPB_AX_UDID")
    if not args.device_id or not args.udid:
        parser.error("run through ipb so the selected device is resolved")
    if args.pid is not None and args.pid <= 0:
        parser.error("--pid must be positive")
    if sys.version_info < (3, 11):
        print("ipb ui: Python 3.11+ is required; set IPB_AX_PYTHON", file=sys.stderr)
        return 2
    try:
        if version("pymobiledevice3") != "11.10.2":
            raise ValueError("ipb ui requires the verified pymobiledevice3 11.10.2")
    except Exception:
        print("ipb ui: install requirements-ax.txt in a Python 3.11+ environment and set IPB_AX_PYTHON to its interpreter", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.ERROR)

    async def bounded():
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, task.cancel)
        async with asyncio.timeout(30):
            return await run(args)

    try:
        result = asyncio.run(bounded())
    except TimeoutError as error:
        return report_failure(args, error, 5)
    except asyncio.CancelledError as error:
        return report_failure(args, error, 5)
    except Exception as error:
        return report_failure(args, error, 1)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    elif args.operation == "hit-test":
        print("AX hit-test PID " + str(result["application"]["pid"]) + ": " + json.dumps(result["target"], ensure_ascii=False))
    elif args.operation == "press":
        target = (json.dumps(args.identifier, ensure_ascii=False) if args.identifier is not None
                  else json.dumps({key: getattr(args, key) for key in ("label", "value", "class_name")
                                   if getattr(args, key) is not None}, ensure_ascii=False))
        print("AX press accepted for " + target + "; UI effect is not verified; observe again")
    elif args.operation == "scroll-to-visible":
        print(f'AX scroll-to-visible nativeResult={str(result["nativeResult"]).lower()} '
              f'postconditionVerified={str(result["postconditionVerified"]).lower()}')
    elif args.operation == "input":
        print(f'AX input childExitCode={result["action"]["childExitCode"]} '
              f'postconditionVerified={str(result["postconditionVerified"]).lower()}')
    elif args.operation == "locate":
        print(f'AX locate: {result["matchCount"]} native match(es); unique={str(result["unique"]).lower()}')
        for match in result["matches"]:
            print("  " + json.dumps(match, ensure_ascii=False))
    elif args.operation == "wait":
        print(f'AX wait {result["status"]}: {result["waitFor"]}; {result["matchCount"]} native match(es)')
    else:
        print(f'AX PID {result["application"]["pid"]}: {result["nodeCount"]} nodes, depth {result["maxDepth"]}; non-atomic read')
        by_id = {node["id"]: node for node in result["nodes"]}
        pending = [result["nodes"][0]["id"]]
        while pending:
            node = by_id[pending.pop()]
            text = (node.get("label") or node.get("description") or node.get("identifier")
                    or node.get("nativeAttributes", {}).get("5003") or "")
            print("  " * node["depth"] + node["id"] + " " + json.dumps(text, ensure_ascii=False)
                  + " " + json.dumps(node.get("frame")))
            pending.extend(reversed(node["children"]))
    supplemental = result.get("supplementalAX", {})
    if supplemental.get("status") == "failed":
        error = supplemental["error"]
        print(f"ipb ui: supplemental AX {error['type']}: {error['message']}; complete native snapshot emitted", file=sys.stderr)
        return supplemental["exitCode"]
    if result.get("status") == "timed_out":
        return 5
    if result.get("status") == "postcondition_failed":
        print(f'ipb ui: {args.operation} postcondition is not verified; do not retry automatically',
              file=sys.stderr)
        return 6
    if result.get("status") == "child_failed":
        print("ipb ui: replace-all child failed; clipboard may have changed and input delivery may be partial; "
              "do not retry automatically", file=sys.stderr)
        return 6
    if result.get("status") == "child_outcome_unknown":
        print("ipb ui: replace-all child outcome is unknown; clipboard may have changed or input may be partial; "
              "do not retry automatically", file=sys.stderr)
        return 6
    if result.get("status") == "native_refused":
        print("ipb ui: native alert press was refused; do not retry automatically", file=sys.stderr)
        return 6
    if result.get("status") == "alert_postcondition_failed":
        print("ipb ui: native alert press was accepted, but the original modal/button disappearance was not verified; "
              "do not retry automatically", file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
