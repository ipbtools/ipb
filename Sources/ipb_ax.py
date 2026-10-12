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
ATTRS = [8, 9, 41, *FIELDS]
BOOL_FIELDS = {27, 28, 30, 32}
MAX_NODES, MAX_DEPTH = 512, 32


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


def signature(attrs):
    return (attrs.get(21), attrs.get(3), tuple(identity(c) for c in attrs.get(8, [])))


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

        async def read(kind, params, token=None):
            nonlocal packet_bytes
            if fatal:
                raise ValueError(fatal[0])
            # Exactly one outstanding semantic request. A timeout aborts the
            # connection; late type-5 replies are never assigned to a new node.
            data = request(kind, params, translation=token)
            async with asyncio.timeout(3):
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
                    if reply.get("error") not in (None, 0):
                        raise ValueError("AX request refused: error " + str(reply["error"]))
                    return reply.get("resultData")

        async def app(pid):
            obj = await read(1, {"pid": pid})
            if identity(obj)[0] != pid or not obj.get("isApplicationElement"):
                raise ValueError("AX application mismatch")
            return obj

        async def hit(point):
            obj = await read(6, {"point": point})
            identity(obj)
            return obj

        if args.pid:
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
            root = await app(selected["pid"])
            selection = "hit-test"

        first = attributes(await read(5, {"attributes": ATTRS}, root))
        pending = deque([(root, first, None, 0)])
        seen, nodes, max_depth = {}, [], 0
        while pending:
            token, attrs, parent, depth = pending.popleft()
            key = identity(token)
            if key in seen:
                raise ValueError("AX child graph repeats an element")
            if key[0] != root["pid"]:
                raise ValueError("AX child belongs to another process")
            if depth > MAX_DEPTH or len(nodes) >= MAX_NODES:
                raise ValueError("AX graph limit reached; no partial tree emitted")
            attrs = attributes(attrs if attrs is not None else await read(5, {"attributes": ATTRS}, token))
            node_id = "n" + str(len(nodes))
            seen[key] = node_id
            node = {"id": node_id, "parentId": parent, "depth": depth, **node_fields(attrs),
                    "children": []}
            children = attrs.get(8, [])
            node["_children"] = [identity(c) for c in children]
            if 9 in attrs:
                node["_navigation"] = [identity(c) for c in attrs[9]]
            if attrs.get(41) is not None:
                node["_parent"] = identity(attrs[41])
            nodes.append(node)
            pending.extend((child, None, node_id, depth + 1) for child in children)
            max_depth = max(max_depth, depth)
        for node in nodes:
            node["children"] = [seen[key] for key in node.pop("_children")]
            navigation = node.pop("_navigation", None)
            # Navigation relations are distinct from the traversed child edges.
            if navigation is not None:
                node["navigationOrder"] = [seen[key] for key in navigation if key in seen]
                node["navigationOutsideGraph"] = sum(key not in seen for key in navigation)
            parent = node.pop("_parent", None)
            if parent is not None:
                node["reportedParentId"] = seen.get(parent)
                node["reportedParentOutsideGraph"] = parent not in seen
        last = attributes(await read(5, {"attributes": [8, 21, 3]}, root))
        if signature(first) != signature(last):
            raise ValueError("AX root changed during collection; request a new snapshot")
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
                "hierarchySource": "AXChildren", "atomic": False, "rootStable": True,
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


def main():
    parser = argparse.ArgumentParser(prog="ipb ui", description="Read the selected application's AX graph; no XCTest or phone app.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--pid", type=int, help="read this application's PID explicitly")
    selector.add_argument("--point", type=unit_interval, nargs=2, default=(0.5, 0.5), metavar=("X", "Y"),
                          help="select the app by a read-only hit test at normalized X Y (default centre)")
    parser.add_argument("--json", action="store_true", help="emit schemaVersion 1 JSON; default is a text tree")
    args = parser.parse_args()
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
    except (TimeoutError, asyncio.CancelledError):
        print("ipb ui: cancelled or AX query timed out; no partial tree emitted", file=sys.stderr)
        return 5
    except Exception as error:
        print("ipb ui: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        print(f'AX PID {result["application"]["pid"]}: {result["nodeCount"]} nodes, depth {result["maxDepth"]}; non-atomic read')
        by_id = {node["id"]: node for node in result["nodes"]}
        pending = [result["nodes"][0]["id"]]
        while pending:
            node = by_id[pending.pop()]
            label = node.get("label") or node.get("identifier") or ""
            print("  " * node["depth"] + node["id"] + " " + json.dumps(label, ensure_ascii=False)
                  + " " + json.dumps(node.get("frame")))
            pending.extend(reversed(node["children"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
