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
        if key[0] != root["pid"]:
            raise ValueError("AX snapshot child belongs to another process")
        children, count, native = record.get(CHILDREN), record.get(CHILD_COUNT), record.get(NATIVE_ATTRS)
        if (not isinstance(children, list) or type(count) is not int or count != len(children)
                or not isinstance(native, dict)):
            raise ValueError("AX snapshot children/attributes unavailable or truncated")
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
        nodes.append(node)
        by_handle.setdefault(key, []).append(node)
        if parent is not None:
            nodes[int(parent[1:])]["children"].append(node_id)
        pending.extend((child, node_id, depth + 1, ancestors | {id(record)}) for child in children)
    return nodes, by_handle


def snapshot_target(snapshot, root, identifier):
    """Resolve one native handle, retaining duplicate paths only in dump output."""
    _, by_handle = snapshot_nodes(snapshot, root)
    matches = {}
    pending = [snapshot]
    while pending:
        record = pending.pop()
        token = record[ELEMENT]
        if record[NATIVE_ATTRS].get(5019) == identifier:
            matches.setdefault(identity(token), (token, record[NATIVE_ATTRS]))
        pending.extend(record[CHILDREN])
    if len(matches) != 1:
        raise ValueError(f"AX press identifier matches={len(matches)}; exactly one native element is required")
    token, native = next(iter(matches.values()))
    node = by_handle[identity(token)][0]
    target = {key: node[key] for key in ("identifier", "label", "frame", "frameUnavailable", "nativeAttributes") if key in node}
    return token, native, target


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
                        args.press_state = "submitted"
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
                            raise ValueError("AX press semantic status unavailable; do not retry automatically")
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
                suffix = "; press outcome unknown; do not retry automatically" if kind == 7 else ""
                raise TimeoutError(f"AX request type={kind}{target}{fields} timed out{suffix}") from error
            except Exception as error:
                if kind == 7 and not received_reply:
                    raise RuntimeError("AX press outcome unknown after submission; do not retry automatically") from error
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

        operation = getattr(args, "operation", None)
        pressing = operation == "press"
        if args.pid and not pressing:
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
                raise ValueError("AX press PID is not the displayed application at the selected point")
            root = await app(selected["pid"])
            selection = "explicit-pid+hit-test" if args.pid else "hit-test"

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

        if pressing:
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            token, native_attrs, target = snapshot_target(native, root, args.identifier)
            confirmed = await read(5, {"attributes": [21, 25, 27, 32]}, token)
            if not isinstance(confirmed, dict) or confirmed.get(25) != args.identifier:
                raise ValueError("AX press target identifier changed; no action sent")
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
            return {"schemaVersion": 1, "deviceIdentifier": args.device_id, "udid": rsd.udid,
                    "application": {"pid": root["pid"], "selection": selection},
                    "action": {"name": "press", "identifier": args.identifier,
                               "nativeAccepted": True, "effectVerified": False},
                    "target": target, "coordinateSpace": "device-logical-points",
                    "cleanup": cleanup, "queryMs": round((time.monotonic() - started) * 1000, 3),
                    "deviceAPIVersion": api}

        first = await node_attributes(root)
        root_text_attribute = 33 if has_description(first) else 3
        # Complete the ordinary graph before the native snapshot; all enrichment
        # uses these same captured handles and fields, without descendant re-reads.
        pending = deque([(root, first, 0)])
        seen = {}
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
        if args.deep:
            native = await read(2, {"parameter": SNAPSHOT_OPTIONS}, root)
            nodes, by_handle = snapshot_nodes(native, root)
        else:
            nodes, by_handle = ordinary_nodes(seen, root)
        missing = [key for key in seen if key not in by_handle]
        if missing:
            key = missing[0]
            raise ValueError(f"AX ordinary element absent from native snapshot: pid={key[0]} "
                             f"objectID={key[1]} missing={len(missing)}; cannot reconcile the two reads")
        if args.deep and getattr(args, "full_state", False):
            # Snapshot-only backing views also support the proven AX state reads.
            # Share each native handle's read across its repeated path records.
            pending_native = [native]
            supplemented = set(seen)
            while pending_native:
                record = pending_native.pop()
                token = record[ELEMENT]
                key = identity(token)
                if key not in supplemented:
                    state = await read(5, {"attributes": STATE_ATTRS}, token)
                    if not isinstance(state, dict):
                        raise ValueError("AX structural state attributes unavailable")
                    fields = node_fields(state)
                    for node in by_handle[key]:
                        node.update({name: val for name, val in fields.items() if name not in node})
                        node["attributeSource"] = "native-snapshot+AXAttributes"
                    supplemented.add(key)
                pending_native.extend(record[CHILDREN])
        for key, attrs in seen.items():
            fields = node_fields(attrs)
            for node in by_handle[key]:
                if "frame" in fields and "frame" in node and fields["frame"] != node["frame"]:
                    raise ValueError(f"AX frame mismatch during collection: pid={key[0]} objectID={key[1]} "
                                     f"ordinary={fields['frame']} native={node['frame']}")
                # Native snapshot owns geometry, label and native metadata. Preserve
                # separately read Description, state and role fields on AX elements.
                native_geometry = "frame" in node or "frameUnavailable" in node
                node.update({name: val for name, val in fields.items() if name not in node
                             and not (native_geometry and name in ("frame", "frameUnavailable"))})
                node["attributeSource"] = "native-snapshot+AXAttributes" if args.deep else "AXAttributes"
                if 9 in attrs:
                    navigation = [identity(c) for c in attrs[9]]
                    if any(len(by_handle.get(k, [])) > 1 for k in navigation):
                        node["navigationUnavailable"] = "ambiguous-snapshot-handle"
                    else:
                        node["navigationOrder"] = [by_handle[k][0]["id"] for k in navigation if k in by_handle]
                        node["navigationOutsideGraph"] = sum(k not in by_handle for k in navigation)
                if attrs.get(41) is not None:
                    matches = by_handle.get(identity(attrs[41]), [])
                    if len(matches) > 1:
                        node["reportedParentUnavailable"] = "ambiguous-snapshot-handle"
                    else:
                        node["reportedParentId"] = matches[0]["id"] if matches else None
                        node["reportedParentOutsideGraph"] = not matches
        max_depth = max(node["depth"] for node in nodes)
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
        return {"schemaVersion": 1, "snapshotId": str(uuid.uuid4()),
                "deviceIdentifier": args.device_id, "udid": rsd.udid,
                "application": {"pid": root["pid"], "selection": selection},
                "scope": "application-accessibility", "coordinateSpace": "device-logical-points",
                "hierarchySource": "AXUserTestingSnapshot" if args.deep else "AXChildren",
                "attributePolicy": ("native-snapshot+description-first+structural-state" if args.deep and getattr(args, "full_state", False) else
                                    "native-snapshot+description-first" if args.deep else "description-first"),
                "stateScope": ("all-native-handles" if args.deep and getattr(args, "full_state", False) else
                               "native-visible+ordinary-state" if args.deep else "ordinary-accessible-elements"),
                "ordinaryAXNodeCount": len(seen), "uniqueElementCount": len(by_handle),
                "atomic": False, "rootStable": True,
                "displayFrame": display,
                "cleanup": cleanup,
                "nodeCount": len(nodes), "maxDepth": max_depth, "nodes": nodes,
                "queryMs": round((time.monotonic() - started) * 1000, 3),
                "unsolicitedCount": len(unsolicited), "deviceAPIVersion": api}
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


def report_failure(args, error, code):
    """A nonzero exit after action submission must never invite an action replay."""
    state = getattr(args, "press_state", "not-sent")
    message = str(error) or ("AX query cancelled" if isinstance(error, asyncio.CancelledError) else
                             "AX query timed out; no partial result emitted" if isinstance(error, TimeoutError) else
                             "AX operation failed")
    if getattr(args, "operation", None) == "press" and state != "not-sent":
        status = "native press accepted" if state == "accepted" else "native press refused" if state == "refused" else "press submitted; outcome unknown"
        print(f"ipb ui: {status}; {type(error).__name__}: {message}; do not retry automatically", file=sys.stderr)
        return 6
    print("ipb ui: " + type(error).__name__ + ": " + message, file=sys.stderr)
    return code


def main():
    parser = argparse.ArgumentParser(prog="ipb ui", description="Read AX elements or press an exact identifier; no XCTest or phone app.")
    parser.add_argument("operation", nargs="?", choices=("press", "hit-test"), help="press a fresh identifier or read the actual element at a point")
    parser.add_argument("--identifier", help="exact accessibility identifier required by press")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--pid", type=int, help="read this application's PID explicitly")
    selector.add_argument("--point", type=unit_interval, nargs=2, default=(0.5, 0.5), metavar=("X", "Y"),
                          help="select the app by a read-only hit test at normalized X Y (default centre)")
    parser.add_argument("--json", action="store_true", help="emit schemaVersion 1 JSON; default is a text tree")
    parser.add_argument("--deep", action="store_true", help="read the native descendant snapshot (opt-in; overlay coverage is limited)")
    parser.add_argument("--full-state", action="store_true", help="with --deep, also read snapshot-only node state/role (extra per-handle requests)")
    args = parser.parse_args()
    if args.full_state and (not args.deep or args.operation is not None):
        parser.error("--full-state requires a --deep dump")
    args.press_state = "not-sent"
    if args.operation is not None and args.deep:
        parser.error("--deep is only used by a dump")
    if args.operation == "press" and not args.identifier:
        parser.error("press requires a nonempty --identifier")
    if args.operation == "hit-test" and args.pid is not None:
        parser.error("hit-test uses --point, not --pid")
    if args.operation != "press" and args.identifier is not None:
        parser.error("--identifier is only used by press")
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
        print("AX press accepted for " + json.dumps(args.identifier, ensure_ascii=False) + "; UI effect is not verified; observe again")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
