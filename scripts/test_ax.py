#!/usr/bin/env python3
"""AX wire and failure-contract checks, without a phone or optional host packages."""
import argparse
import asyncio
import copy
import io
from contextlib import redirect_stderr
from pathlib import Path
import plistlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Sources"))
import ax_archive
import ipb_ax


def archive(value):
    objects = ["$null"]
    def add(obj):
        objects.append(obj)
        return plistlib.UID(len(objects) - 1)
    def encode(obj):
        if obj is None:
            return plistlib.UID(0)
        if isinstance(obj, dict):
            cls = add({"$classname": "NSDictionary", "$classes": ["NSDictionary", "NSObject"]})
            return add({"$class": cls, "NS.keys": [encode(k) for k in obj], "NS.objects": [encode(v) for v in obj.values()]})
        if isinstance(obj, list):
            cls = add({"$classname": "NSArray", "$classes": ["NSArray", "NSObject"]})
            return add({"$class": cls, "NS.objects": [encode(v) for v in obj]})
        return add(obj)
    root = encode(value)
    return plistlib.dumps({"$archiver": "NSKeyedArchiver", "$version": 100000, "$objects": objects,
                          "$top": {"root": root}}, fmt=plistlib.FMT_BINARY)


class ArchiveTests(unittest.TestCase):
    def test_object_id_is_boxed_and_keeps_all_64_bits(self):
        token = {"pid": 42, "objectID": (1 << 64) - 17, "isApplicationElement": True, "didPopuldateAppInfo": True}
        data = ax_archive.request(5, {"attributes": [8, 21]}, translation=token)
        wire = plistlib.loads(data)
        objects = wire["$objects"]
        root = objects[wire["$top"]["root"].data]
        translated = objects[root["translation"].data]
        self.assertIsInstance(translated["objectID"], plistlib.UID)
        self.assertEqual(objects[translated["objectID"].data], token["objectID"])
        self.assertEqual(ax_archive.decode(data)["translation"]["objectID"], token["objectID"])

    def test_cycle_is_refused(self):
        bad = {"$archiver": "NSKeyedArchiver", "$objects": ["$null", {"again": plistlib.UID(1)}],
               "$top": {"root": plistlib.UID(1)}}
        with self.assertRaises(ValueError):
            ax_archive.decode(plistlib.dumps(bad, fmt=plistlib.FMT_BINARY))

    def test_missing_children_is_not_a_leaf(self):
        with self.assertRaisesRegex(ValueError, "children unavailable"):
            ipb_ax.attributes({21: {"x": 0, "y": 0, "width": 10, "height": 20}})
        self.assertEqual(ipb_ax.attributes({8: []}), {8: []})

    def test_missing_and_false_states_are_distinct(self):
        self.assertNotIn("enabled", ipb_ax.node_fields({}))
        self.assertIs(ipb_ax.node_fields({27: 0})["enabled"], False)
        with self.assertRaises(ValueError):
            ipb_ax.node_fields({27: "0"})

    def test_invalid_geometry_is_not_zero(self):
        with self.assertRaises(ValueError):
            ipb_ax.frame({"x": float("nan"), "y": 0, "width": 10, "height": 20})
        self.assertEqual(ipb_ax.node_fields({21: {"unavailable": "CGRectNull"}}), {"frameUnavailable": "CGRectNull"})

    def test_effective_display_bounds_include_scaled_mode(self):
        info = {"displays": [{"primary": True, "bounds": [[0, 0], [1125, 2436]], "nativeSize": [1080, 2340],
                             "pointScale": 3, "nativeOrientation": "rot0", "currentOrientation": "rot0"}]}
        self.assertEqual(ipb_ax.display_geometry(info), {"x": 0, "y": 0, "width": 375, "height": 812})
        info["displays"].append(copy.deepcopy(info["displays"][0]))
        with self.assertRaises(ValueError):
            ipb_ax.display_geometry(info)

    def test_full_state_cli_requires_a_deep_dump_without_operation(self):
        for argv in (("ipb ui", "--full-state"),
                     ("ipb ui", "press", "--deep", "--full-state", "--identifier", "fixture-id"),
                     ("ipb ui", "hit-test", "--deep", "--full-state"),
                     ("ipb ui", "press", "--deep", "--identifier", "fixture-id"),
                     ("ipb ui", "hit-test", "--deep")):
            with self.subTest(argv=argv), patch("sys.argv", list(argv)), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    ipb_ax.main()
                self.assertEqual(raised.exception.code, 2)


TOKEN = {"pid": 42, "objectID": (1 << 63) + 9, "isApplicationElement": True, "didPopuldateAppInfo": True}
CHILD = {"pid": 42, "objectID": 101, "isApplicationElement": False, "didPopuldateAppInfo": True}
FRAME = {"x": 0, "y": 0, "width": 375, "height": 812}


def snapshot(token, children=None, attrs=None):
    children = [] if children is None else children
    return {ipb_ax.ELEMENT: token, ipb_ax.CHILDREN: children,
            ipb_ax.CHILD_COUNT: len(children),
            ipb_ax.NATIVE_ATTRS: {2003: FRAME} if attrs is None else attrs}


class SnapshotTests(unittest.TestCase):
    def test_deep_keyed_archive_exceeds_old_wrapper_limit(self):
        tree = snapshot(CHILD)
        for _ in range(24):
            tree = snapshot(CHILD, [tree])
        decoded = ax_archive.decode(archive(tree))
        nodes, _ = ipb_ax.snapshot_nodes(decoded, CHILD)
        self.assertEqual(len(nodes), 25)
        self.assertEqual(nodes[-1]["depth"], 24)

    def test_native_request_has_numeric_attributes_and_parameter_wrapper(self):
        data = ax_archive.request(2, {"parameter": ipb_ax.SNAPSHOT_OPTIONS}, translation=TOKEN)
        decoded = ax_archive.decode(data)
        self.assertEqual((decoded["requestType"], decoded["attributeType"], decoded["actionType"]), (2, 52, 0))
        options = decoded["parameters"]["parameter"]
        self.assertTrue(options["attributes"] and all(type(v) is int for v in options["attributes"]))
        self.assertTrue(options["traverseFromParentsToChildren"])
        with self.assertRaises(ValueError):
            ax_archive.request(2, {})

    def test_press_action_request_requires_kind_seven_action_five_and_token(self):
        data = ax_archive.request(7, {"identifier": "fixture-id"}, translation=TOKEN, action=5)
        decoded = ax_archive.decode(data)
        self.assertEqual((decoded["requestType"], decoded["actionType"]), (7, 5))
        self.assertEqual({key: decoded["translation"][key] for key in TOKEN}, TOKEN)
        self.assertEqual(decoded["parameters"]["identifier"], "fixture-id")
        with self.assertRaises(ValueError):
            ax_archive.request(7, {"identifier": "fixture-id"}, action=5)

    def test_action_code_is_rejected_for_non_action_request(self):
        with self.assertRaises(ValueError):
            ax_archive.request(5, {"attributes": [8]}, translation=TOKEN, action=5)

    def test_kind_seven_rejects_any_action_other_than_five(self):
        for action in (0, 1, 6):
            with self.subTest(action=action), self.assertRaises(ValueError):
                ax_archive.request(7, {"identifier": "fixture-id"}, translation=TOKEN, action=action)

    def test_duplicate_handles_keep_distinct_path_nodes(self):
        nodes, handles = ipb_ax.snapshot_nodes(snapshot(TOKEN, [snapshot(CHILD), snapshot(CHILD)]), TOKEN)
        self.assertEqual(nodes[0]["children"], ["n1", "n2"])
        self.assertEqual([n["parentId"] for n in nodes[1:]], ["n0", "n0"])
        self.assertEqual(len(handles[ipb_ax.identity(CHILD)]), 2)

    def test_native_fields_keep_unavailable_geometry_and_numeric_metadata(self):
        native = {2001: "Title", 2003: {"unavailable": "CGRectNull"}, 2004: -(1 << 63),
                  5019: "title-id", 2006: "中文🙂", 5003: "UIButton", 5004: "UIControl", 3003: "example.app"}
        node = ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs=native), TOKEN)[0][0]
        self.assertEqual(node["traits"], str(1 << 63))
        self.assertEqual(node["frameUnavailable"], "CGRectNull")
        self.assertNotIn("frame", node)
        self.assertNotIn("enabled", node)
        self.assertEqual(node["value"], "中文🙂")
        self.assertEqual(node["nativeAttributes"], {"5003": "UIButton", "5004": "UIControl", "3003": "example.app"})

    def test_native_hint_is_preserved_only_as_native_ax_hint(self):
        node = ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs={2002: "Search"}), TOKEN)[0][0]
        self.assertEqual(node["hint"], "Search")
        self.assertNotIn("placeholder", node)
        self.assertNotIn("description", node)
        empty = ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs={2002: None}), TOKEN)[0][0]
        self.assertNotIn("hint", empty)
        for invalid in (17, [], {}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs={2002: invalid}), TOKEN)

    def test_native_snapshot_visible_preserves_false_and_rejects_invalid_values(self):
        for value in (False, True):
            with self.subTest(value=value):
                node = ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs={2025: value}), TOKEN)[0][0]
                self.assertIs(node["visible"], value)
        for invalid in (2, "false", [], {}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ipb_ax.snapshot_nodes(snapshot(TOKEN, attrs={2025: invalid}), TOKEN)

    def test_nil_truncated_cross_process_and_cyclic_snapshots_fail(self):
        bad_count = snapshot(TOKEN, [snapshot(CHILD)])
        bad_count[ipb_ax.CHILD_COUNT] = 2
        missing = snapshot(TOKEN); del missing[ipb_ax.CHILDREN]
        cycle = snapshot(TOKEN); cycle[ipb_ax.CHILDREN].append(cycle); cycle[ipb_ax.CHILD_COUNT] = 1
        other_pid = snapshot(TOKEN, [snapshot({**CHILD, "pid": 43})])
        for tree in (None, bad_count, missing, cycle, other_pid):
            with self.subTest(tree=type(tree).__name__), self.assertRaises(ValueError):
                ipb_ax.snapshot_nodes(tree, TOKEN)

    def test_record_and_depth_budgets(self):
        tree = snapshot(TOKEN, [snapshot(CHILD) for _ in range(511)])
        self.assertEqual(len(ipb_ax.snapshot_nodes(tree, TOKEN)[0]), 512)
        tree[ipb_ax.CHILDREN].append(snapshot(CHILD)); tree[ipb_ax.CHILD_COUNT] += 1
        with self.assertRaisesRegex(ValueError, "snapshot limit"):
            ipb_ax.snapshot_nodes(tree, TOKEN)
        tree = snapshot(CHILD)
        for _ in range(32):
            tree = snapshot(CHILD, [tree])
        self.assertEqual(ipb_ax.snapshot_nodes(tree, CHILD)[0][-1]["depth"], 32)
        with self.assertRaisesRegex(ValueError, "snapshot limit"):
            ipb_ax.snapshot_nodes(snapshot(CHILD, [tree]), CHILD)

    def test_archive_nesting_still_bounded_without_python_recursion(self):
        objects = ["$null"] + [{"next": plistlib.UID(n + 1)} for n in range(1, 601)] + ["end"]
        data = plistlib.dumps({"$archiver": "NSKeyedArchiver", "$objects": objects,
                              "$top": {"root": plistlib.UID(1)}}, fmt=plistlib.FMT_BINARY)
        with self.assertRaisesRegex(ValueError, "nesting limit"):
            ax_archive.decode(data)


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def run_capture(self, mode, *, deep=True, full_state=False, operation="capture", pid=42, identifier="fixture-id"):
        state = {"requests": [], "attribute_requests": [], "structural_state_requests": [], "closed": False,
                 "dtx_closed": False, "root_reads": 0, "wire_requests": [],
                 "events": [], "display_calls": 0, "action_submissions": 0}
        class Terminated(Exception):
            pass
        class Service:
            def __init__(self, ctx):
                self._ctx = ctx
        class Channel:
            def __init__(self, conn):
                self.conn = conn
            async def invoke(self, selector, *args):
                if selector == "deviceAPIVersion":
                    return 26
                if selector == "clientNeedsAccessibility:":
                    if not args[0] and mode == "stop-error":
                        raise RuntimeError("stop refused")
                    if not args[0] and mode == "action-stop-timeout":
                        raise TimeoutError("fixture subscription-stop timeout after accepted action")
                    return None
                req = ax_archive.decode(args[0])
                kind = req["requestType"]
                state["requests"].append(kind)
                state["wire_requests"].append(copy.deepcopy(req))
                if kind == 6:
                    state["events"].append("hit")
                    hit_number = state["requests"].count(6)
                    hit_pid = 99 if (mode == "hit-pid-mismatch" or
                                     (mode == "foreground-changed" and hit_number >= 3)) else 42
                    if operation == "press":
                        hit_object = (606 if mode == "center-hit-other" and hit_number == 2 else 201)
                    else:
                        hit_object = 607 if mode == "hit-target-changed" and hit_number > 1 else 606
                    result = {"pid": hit_pid, "objectID": hit_object, "isApplicationElement": False, "didPopuldateAppInfo": True}
                elif kind == 7:
                    state["action_submissions"] += 1
                    state["events"].append("action-submit")
                    if mode == "action-timeout":
                        raise TimeoutError("fixture type-7 transport timeout")
                    if mode == "action-connection-error":
                        raise ConnectionError("fixture type-7 connection error")
                    result = mode != "action-false"
                    if mode == "action-unknown":
                        result = {"unexpected": True}
                elif kind == 1:
                    state["events"].append("application-root")
                    result = TOKEN
                elif kind == 2:
                    state["events"].append("fresh-snapshot")
                    if mode == "snapshot-timeout":
                        raise TimeoutError("fixture type-2 transport timeout")
                    if operation == "press":
                        target = {"pid": 42, "objectID": 201, "isApplicationElement": False, "didPopuldateAppInfo": True}
                        target_frame = {"x": 0, "y": 0, "width": 0, "height": 0} if mode == "action-empty-frame" else FRAME
                        target_attrs = {2003: target_frame, 5019: identifier}
                        if mode == "action-no-match":
                            target_attrs[5019] = "other-id"
                        if mode == "action-ambiguous":
                            other = {"pid": 42, "objectID": 202, "isApplicationElement": False, "didPopuldateAppInfo": True}
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs), snapshot(other, attrs={2003: FRAME, 5019: identifier})])
                        elif mode == "action-repeat-same-handle":
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs), snapshot(target, attrs=target_attrs)])
                        else:
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs)])
                    else:
                        result = snapshot(TOKEN, [snapshot(CHILD)])
                    if mode in ("native-duplicate", "native-parent-duplicate"):
                        result = snapshot(TOKEN, [snapshot(CHILD), snapshot(CHILD)])
                    if mode == "native-deep":
                        container = {**CHILD, "objectID": 102}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs={2003: FRAME, 2025: False})])
                    if mode in ("native-deep-state", "native-deep-known-false", "native-deep-visible-priority"):
                        container = {**CHILD, "objectID": 102}
                        container_attrs = {2003: FRAME, 5019: "container-id", 2025: False}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs=container_attrs)])
                    if mode == "native-structural-duplicate":
                        container = {**CHILD, "objectID": 102}
                        container_attrs = {2003: FRAME, 5019: "container-id", 2025: False}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs=container_attrs),
                                                  snapshot(container, [snapshot(CHILD)], attrs=container_attrs)])
                    if mode == "native-nil":
                        result = None
                    if mode == "native-truncated":
                        result[ipb_ax.CHILD_COUNT] = 2
                    if mode == "native-missing-element":
                        result = snapshot(TOKEN)
                    if mode == "native-root-mismatch":
                        result = snapshot({**TOKEN, "objectID": TOKEN["objectID"] + 1}, [snapshot(CHILD)])
                    if mode == "native-frame-mismatch":
                        result[ipb_ax.NATIVE_ATTRS][2003] = {"x": 1, "y": 2, "width": 31, "height": 40}
                    if mode == "native-null-frame":
                        result[ipb_ax.NATIVE_ATTRS][2003] = {"unavailable": "CGRectNull"}
                elif kind == 5:
                    token = req["translation"]
                    requested = req["parameters"].get("attributes", [])
                    state["attribute_requests"].append((token["objectID"], requested))
                    if operation == "press":
                        state["events"].append("target-recheck")
                        id_value = identifier
                        frame_value = {"x": 0, "y": 0, "width": 0, "height": 0} if mode == "action-empty-frame" else FRAME
                        enabled_value, visible_value = True, True
                        include_visible = True
                        if mode == "target-changed":
                            id_value = "changed-id"
                        if mode == "target-frame-changed":
                            frame_value = {"x": 1, "y": 2, "width": 375, "height": 812}
                        if mode == "action-disabled":
                            enabled_value = False
                        if mode in ("action-hidden", "action-no-visible"):
                            visible_value = False
                        if mode == "action-visible-unknown":
                            include_visible = False
                        result = {}
                        if 25 in requested:
                            result[25] = id_value
                        if 21 in requested:
                            result[21] = frame_value
                        if 27 in requested:
                            result[27] = enabled_value
                        if 32 in requested and include_visible:
                            result[32] = visible_value
                    elif operation == "hit-test":
                        state["events"].append("hit-target-attributes")
                        result = {8: [], 21: FRAME, 33: "Actual hit element"}
                        if 33 not in requested:
                            result.pop(33)
                    elif token["objectID"] == 102 and mode in ("native-deep-state", "native-deep-known-false",
                                                                  "native-deep-visible-priority", "native-structural-duplicate"):
                        state["structural_state_requests"].append((token["objectID"], requested))
                        state["events"].append("structural-state")
                        if mode == "native-deep-known-false":
                            result = {key: False for key in (27, 28, 30, 32) if key in requested}
                        else:
                            result = {27: True, 28: False, 30: True,
                                      32: True if mode == "native-deep-visible-priority" else False,
                                      42: "placeholder", 45: 2, 46: "XCUIElementTypeButton",
                                      51: 1}
                            result = {key: value for key, value in result.items() if key in requested}
                    elif token["objectID"] == CHILD["objectID"] and 3 in requested and mode in ("description", "label-timeout"):
                        raise TimeoutError("fixture stalled Label")
                    elif token["objectID"] == TOKEN["objectID"]:
                        state["root_reads"] += 1
                        children = [CHILD]
                        if mode == "changed" and state["root_reads"] > 1:
                            children = []
                        if mode == "duplicate":
                            children = [CHILD, CHILD]
                        result = {8: children, 21: FRAME, 3: "Test app"}
                        if mode == "native-duplicate":
                            result[9] = [CHILD]
                        if mode in ("description", "description-changed"):
                            result[33] = "Test app"
                        if mode == "description-changed" and state["root_reads"] > 1:
                            result[33] = "Changed app description"
                        if mode == "label-changed" and state["root_reads"] > 2:
                            result[3] = "Changed app label"
                        if mode == "frame-changed" and state["root_reads"] > 1:
                            result[21] = {"x": 1, "y": 2, "width": 375, "height": 812}
                        if mode == "native-parent-duplicate":
                            result[41] = CHILD
                    else:
                        result = {8: [], 21: FRAME, 27: 0}
                        if mode == "missing":
                            del result[8]
                        if mode == "description":
                            result.update({33: "Example video title", 45: 14})
                        if mode == "label-only":
                            result.update({33: " ", 3: "Actual label"})
                    if operation != "press":
                        result = {key: val for key, val in result.items() if key in requested}
                else:
                    raise AssertionError(f"unexpected fixture request kind={kind}")
                if mode == "notification":
                    await self.conn._services[0].packet(archive({"associatedRequestType": 11, "resultData": None}))
                reply = {"associatedRequestType": req["requestType"], "resultData": result,
                         "attribute": 51 if mode == "wrong-attribute" else req["attributeType"],
                         "associatedTranslationObject": req["translation"]}
                if not (mode == "action-missing-error" and kind == 7):
                    reply["error"] = 9 if mode == "action-refused" and kind == 7 else 0
                await self.conn._services[0].packet(archive(reply))
        class Connection:
            def __init__(self, reader, writer):
                self._control_svc = Service({})
                self._services = {}
                self._ctrl_channel = Channel(self)
            async def connect(self):
                pass
            async def aclose(self):
                state["dtx_closed"] = True
        class Socket:
            reader = writer = None
            async def close(self):
                state["closed"] = True
        class Rsd:
            peer_info = {"Services": {ipb_ax.SERVICE: {"Port": "123"}}}
            udid = "fixture"
            async def create_service_connection(self, port):
                return Socket()
        class DeviceInfoService:
            def __init__(self, rsd):
                self.rsd = rsd
            async def __aenter__(self):
                state["events"].append("display-info")
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return False
            async def get_display_info(self):
                state["display_calls"] += 1
                height = 812 if not (mode == "display-changed" and state["display_calls"] > 1) else 800
                return {"displays": [{"primary": True, "bounds": [[0, 0], [375, height]],
                                      "nativeSize": [375, height], "pointScale": 1,
                                      "nativeOrientation": "rot0", "currentOrientation": "rot0"}]}
        mods = {name: types.ModuleType(name) for name in ("pymobiledevice3", "pymobiledevice3.dtx",
                "pymobiledevice3.dtx.service", "pymobiledevice3.exceptions",
                "pymobiledevice3.remote", "pymobiledevice3.remote.core_device",
                "pymobiledevice3.remote.core_device.device_info")}
        mods["pymobiledevice3.dtx"].DTXConnection = Connection
        mods["pymobiledevice3.dtx.service"].DTXControlService = Service
        mods["pymobiledevice3.dtx.service"].dtx_on_invoke = lambda name: lambda fn: fn
        mods["pymobiledevice3.exceptions"].ConnectionTerminatedError = Terminated
        mods["pymobiledevice3.remote"].__path__ = []
        mods["pymobiledevice3.remote.core_device"].__path__ = []
        mods["pymobiledevice3.remote.core_device.device_info"].DeviceInfoService = DeviceInfoService
        args = argparse.Namespace(pid=pid, point=(.5, .5), device_id="fixture", deep=deep, full_state=full_state,
                                  press_state="not-sent",
                                  operation=operation, identifier=identifier)
        with patch.dict(sys.modules, mods):
            try:
                result = await ipb_ax.capture(Rsd(), args)
                state["press_state"] = args.press_state
                return result, state, None
            except Exception as error:
                state["press_state"] = args.press_state
                return None, state, error

    async def test_notifications_are_not_assigned_to_nodes(self):
        result, state, error = await self.run_capture("notification")
        self.assertIsNone(error)
        self.assertEqual(result["nodeCount"], 2)
        self.assertGreater(result["unsolicitedCount"], 0)
        self.assertIs(result["nodes"][1]["enabled"], False)
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_default_keeps_ordinary_graph_without_snapshot_request(self):
        result, state, error = await self.run_capture("native-nil", deep=False)
        self.assertIsNone(error)
        self.assertEqual((result["nodeCount"], result["maxDepth"]), (2, 1))
        self.assertEqual(result["hierarchySource"], "AXChildren")
        self.assertEqual(result["attributePolicy"], "description-first")
        self.assertNotIn(2, state["requests"])
        self.assertIs(result["nodes"][1]["enabled"], False)

    async def test_native_geometry_precedence_does_not_emit_frame_and_unavailable(self):
        result, state, error = await self.run_capture("native-null-frame")
        self.assertIsNone(error)
        root = result["nodes"][0]
        self.assertEqual(root["frameUnavailable"], "CGRectNull")
        self.assertNotIn("frame", root)

    async def test_deep_structure_and_ordinary_state_use_same_transport(self):
        result, state, error = await self.run_capture("native-deep")
        self.assertIsNone(error)
        self.assertEqual((result["nodeCount"], result["maxDepth"], result["ordinaryAXNodeCount"]), (3, 2, 2))
        self.assertEqual(result["hierarchySource"], "AXUserTestingSnapshot")
        self.assertEqual(result["nodes"][1]["children"], ["n2"])
        self.assertEqual(result["nodes"][2]["parentId"], "n1")
        self.assertNotIn("enabled", result["nodes"][1])
        self.assertEqual(result["attributePolicy"], "native-snapshot+description-first")
        self.assertEqual(result["stateScope"], "native-visible+ordinary-state")
        self.assertIs(result["nodes"][1]["visible"], False)
        self.assertEqual(state["structural_state_requests"], [])
        self.assertIs(result["nodes"][2]["enabled"], False)
        self.assertEqual(state["requests"].count(2), 1)

    async def test_structural_state_preserves_true_and_false_without_label_read(self):
        result, state, error = await self.run_capture("native-deep-state", full_state=True)
        self.assertIsNone(error)
        structural = result["nodes"][1]
        self.assertIs(structural["enabled"], True)
        self.assertIs(structural["focused"], False)
        self.assertIs(structural["selected"], True)
        self.assertIs(structural["visible"], False)
        self.assertEqual(structural["placeholder"], "placeholder")
        self.assertEqual(structural["roleCode"], 2)
        self.assertEqual(structural["roleDescription"], "XCUIElementTypeButton")
        self.assertEqual(structural["subroleCode"], 1)
        self.assertEqual(structural["attributeSource"], "native-snapshot+AXAttributes")
        self.assertEqual(result["ordinaryAXNodeCount"], 2)
        self.assertEqual(state["structural_state_requests"], [(102, [27, 28, 30, 32, 42, 45, 46, 51])])
        self.assertTrue(all(3 not in requested for object_id, requested in state["attribute_requests"]
                            if object_id == 102))

    async def test_structural_known_false_does_not_synthesize_absent_semantics(self):
        result, state, error = await self.run_capture("native-deep-known-false", full_state=True)
        self.assertIsNone(error)
        structural = result["nodes"][1]
        for key in ("enabled", "focused", "selected", "visible"):
            self.assertIs(structural[key], False)
        for key in ("placeholder", "roleCode", "roleDescription", "subroleCode", "hint"):
            self.assertNotIn(key, structural)
        self.assertEqual(structural["attributeSource"], "native-snapshot+AXAttributes")
        self.assertEqual(result["ordinaryAXNodeCount"], 2)
        self.assertTrue(all(3 not in requested for object_id, requested in state["attribute_requests"]
                            if object_id == 102))

    async def test_repeated_structural_snapshot_handle_has_one_state_read_and_keeps_paths(self):
        result, state, error = await self.run_capture("native-structural-duplicate", full_state=True)
        self.assertIsNone(error)
        self.assertEqual(result["ordinaryAXNodeCount"], 2)
        structural = [node for node in result["nodes"] if node.get("identifier") == "container-id"]
        self.assertEqual(len(structural), 2)
        self.assertNotEqual(structural[0]["id"], structural[1]["id"])
        self.assertEqual(structural[0]["parentId"], structural[1]["parentId"])
        self.assertEqual([node["enabled"] for node in structural], [True, True])
        self.assertEqual([node["visible"] for node in structural], [False, False])
        self.assertEqual([node["attributeSource"] for node in structural],
                         ["native-snapshot+AXAttributes"] * 2)
        self.assertEqual(state["structural_state_requests"], [(102, [27, 28, 30, 32, 42, 45, 46, 51])])
        self.assertTrue(all(3 not in requested for object_id, requested in state["attribute_requests"]
                            if object_id == 102))

    async def test_full_state_is_opt_in_and_preserves_native_paths_and_frames(self):
        default, default_state, default_error = await self.run_capture("native-deep-state")
        full, full_state, full_error = await self.run_capture("native-deep-state", full_state=True)
        self.assertIsNone(default_error)
        self.assertIsNone(full_error)
        def structure(result):
            return [{key: node.get(key) for key in ("id", "parentId", "depth", "children", "frame", "frameUnavailable")}
                    for node in result["nodes"]]
        self.assertEqual(structure(default), structure(full))
        self.assertEqual(default["ordinaryAXNodeCount"], full["ordinaryAXNodeCount"])
        self.assertEqual(default["nodeCount"], full["nodeCount"])
        self.assertNotIn("enabled", default["nodes"][1])
        self.assertNotIn("focused", default["nodes"][1])
        self.assertIs(full["nodes"][1]["enabled"], True)
        self.assertIs(full["nodes"][1]["focused"], False)
        self.assertIs(default["nodes"][1]["visible"], False)
        self.assertIs(full["nodes"][1]["visible"], False)
        self.assertEqual(default["attributePolicy"], "native-snapshot+description-first")
        self.assertEqual(default["stateScope"], "native-visible+ordinary-state")
        self.assertEqual(full["attributePolicy"], "native-snapshot+description-first+structural-state")
        self.assertEqual(full["stateScope"], "all-native-handles")
        self.assertEqual(default_state["structural_state_requests"], [])
        self.assertEqual(full_state["structural_state_requests"], [(102, [27, 28, 30, 32, 42, 45, 46, 51])])

    async def test_full_state_does_not_override_native_snapshot_visibility(self):
        result, state, error = await self.run_capture("native-deep-visible-priority", full_state=True)
        self.assertIsNone(error)
        self.assertEqual(state["structural_state_requests"], [(102, [27, 28, 30, 32, 42, 45, 46, 51])])
        structural = result["nodes"][1]
        self.assertIs(structural["visible"], False)
        self.assertIs(structural["enabled"], True)
        self.assertEqual(structural["attributeSource"], "native-snapshot+AXAttributes")

    async def test_repeated_native_paths_share_one_state_read(self):
        result, state, error = await self.run_capture("native-duplicate")
        self.assertIsNone(error)
        self.assertEqual((result["nodeCount"], result["uniqueElementCount"]), (3, 2))
        self.assertEqual(result["nodes"][0]["children"], ["n1", "n2"])
        self.assertEqual(result["nodes"][0]["navigationUnavailable"], "ambiguous-snapshot-handle")
        self.assertNotIn("navigationOrder", result["nodes"][0])
        self.assertTrue(all(node["enabled"] is False for node in result["nodes"][1:]))
        self.assertEqual(sum(obj == CHILD["objectID"] and 8 in fields
                             for obj, fields in state["attribute_requests"]), 1)

    async def test_repeated_native_parent_handle_is_reported_ambiguous(self):
        result, state, error = await self.run_capture("native-parent-duplicate")
        self.assertIsNone(error)
        root = result["nodes"][0]
        self.assertEqual(root["reportedParentUnavailable"], "ambiguous-snapshot-handle")
        self.assertNotIn("reportedParentId", root)

    async def test_native_root_mismatch_reports_both_handles(self):
        result, state, error = await self.run_capture("native-root-mismatch")
        self.assertIsNone(result)
        self.assertRegex(str(error), r"snapshot root mismatch: expected=\(42, \d+\) actual=\(42, \d+\)")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_nil_native_snapshot_reports_device_unavailable(self):
        result, state, error = await self.run_capture("native-nil")
        self.assertIsNone(result)
        self.assertIn("AX snapshot unavailable: device returned nil", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_missing_ordinary_snapshot_handle_reports_identity_and_count(self):
        result, state, error = await self.run_capture("native-missing-element")
        self.assertIsNone(result)
        self.assertIn(f"AX ordinary element absent from native snapshot: pid=42 objectID={CHILD['objectID']} missing=1", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_frame_mismatch_reports_identity_and_coordinates(self):
        result, state, error = await self.run_capture("native-frame-mismatch")
        self.assertIsNone(result)
        self.assertIn("AX frame mismatch during collection: pid=42 objectID=", str(error))
        self.assertIn("ordinary={'x': 0, 'y': 0, 'width': 375, 'height': 812}", str(error))
        self.assertIn("native={'x': 1, 'y': 2, 'width': 31, 'height': 40}", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_snapshot_timeout_reports_attribute_and_cleans_up(self):
        result, state, error = await self.run_capture("snapshot-timeout")
        self.assertIsNone(result)
        self.assertIsInstance(error, TimeoutError)
        self.assertRegex(str(error), r"AX request type=2 pid=42 objectID=\d+ attribute=52 timed out")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_invalid_native_snapshot_never_falls_back(self):
        for mode in ("native-nil", "native-truncated", "native-missing-element", "wrong-attribute"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode)
                self.assertIsNone(result)
                self.assertIsInstance(error, ValueError)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_changed_root_does_not_emit_partial_tree(self):
        result, state, error = await self.run_capture("changed")
        self.assertIsNone(result)
        self.assertIn("root changed during collection: pid=42 objectID=", str(error))
        self.assertIn("changed=children", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_description_avoids_stalled_label_without_renaming_it(self):
        result, state, error = await self.run_capture("description")
        self.assertIsNone(error)
        self.assertEqual(result["nodeCount"], 2)
        self.assertEqual(result["attributePolicy"], "native-snapshot+description-first")
        title = result["nodes"][1]
        self.assertEqual(title["description"], "Example video title")
        self.assertEqual(title["frame"], FRAME)
        self.assertNotIn("label", title)
        self.assertTrue(all(3 not in fields for _, fields in state["attribute_requests"]))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_label_is_read_when_description_has_no_text(self):
        result, state, error = await self.run_capture("label-only")
        self.assertIsNone(error)
        self.assertEqual(result["nodes"][1]["label"], "Actual label")
        self.assertEqual(result["nodes"][1]["description"], " ")
        self.assertIn((CHILD["objectID"], [3]), state["attribute_requests"])

    async def test_stalled_label_still_fails_with_request_context(self):
        result, state, error = await self.run_capture("label-timeout")
        self.assertIsNone(result)
        self.assertIsInstance(error, TimeoutError)
        self.assertRegex(str(error), r"type=5 pid=42 objectID=101 attributes=\[3\] timed out")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_changed_root_description_does_not_emit_partial_tree(self):
        result, state, error = await self.run_capture("description-changed")
        self.assertIsNone(result)
        self.assertIn("changed=text", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_changed_root_label_without_description_still_fails(self):
        result, state, error = await self.run_capture("label-changed")
        self.assertIsNone(result)
        self.assertIn("changed=text", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_changed_root_frame_reports_frame_category(self):
        result, state, error = await self.run_capture("frame-changed")
        self.assertIsNone(result)
        self.assertIn("changed=frame", str(error))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_missing_child_list_fails_and_cleans_up(self):
        result, state, error = await self.run_capture("missing")
        self.assertIsNone(result)
        self.assertRegex(str(error), "children unavailable")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_duplicate_child_fails(self):
        result, state, error = await self.run_capture("duplicate")
        self.assertIsNone(result)
        self.assertRegex(str(error), "repeats an element")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_stop_failure_still_closes_transport(self):
        result, state, error = await self.run_capture("stop-error")
        self.assertIsNone(result)
        self.assertRegex(str(error), "stop refused")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_unique_identifier_submits_once_after_same_connection_preflight(self):
        for pid in (42, None):
            with self.subTest(pid=pid):
                result, state, error = await self.run_capture("action-repeat-same-handle", operation="press", pid=pid)
                self.assertIsNone(error)
                self.assertEqual(result["action"], {"name": "press", "identifier": "fixture-id",
                                                     "nativeAccepted": True, "effectVerified": False})
                self.assertEqual(state["requests"].count(7), 1)
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["requests"], [6, 1, 2, 5, 6, 6, 7])
                self.assertEqual(state["wire_requests"][3]["parameters"]["attributes"], [21, 25, 27, 32])
                self.assertEqual(state["wire_requests"][3]["translation"]["objectID"], 201)
                self.assertEqual(state["wire_requests"][-1]["actionType"], 5)
                self.assertEqual(state["wire_requests"][-1]["requestType"], 7)
                self.assertIsNone(state["wire_requests"][-1]["parameters"])
                self.assertEqual(state["wire_requests"][-1]["translation"]["objectID"], 201)
                self.assertEqual(state["events"], ["display-info", "hit", "application-root", "fresh-snapshot",
                                                    "target-recheck", "hit", "hit", "display-info", "action-submit"])
                self.assertEqual(state["requests"].count(6), 3)
                self.assertEqual(state["requests"].count(2), 1)
                self.assertLess(state["events"].index("display-info"), state["events"].index("hit"))
                self.assertLess(state["events"].index("target-recheck"), state["events"].index("action-submit"))
                self.assertEqual(state["display_calls"], 2)
                self.assertTrue(state["closed"] and state["dtx_closed"])
                self.assertTrue(result["cleanup"]["connectionClosed"])
                self.assertEqual(result["cleanup"]["subscriptionStop"], "acknowledged")
                self.assertEqual(state["press_state"], "accepted")

    async def test_press_rejects_missing_or_different_handle_matches_before_submission(self):
        for mode in ("action-no-match", "action-ambiguous"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_rejects_changed_target_before_submission(self):
        for mode in ("target-changed", "target-frame-changed"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_rechecks_foreground_and_display_before_submission(self):
        for mode in ("foreground-changed", "display-changed", "hit-pid-mismatch"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_requires_known_enabled_visible_and_frame_center_hit(self):
        for mode in ("action-disabled", "action-hidden", "action-no-visible", "action-visible-unknown", "action-empty-frame",
                     "center-hit-other"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                if mode == "center-hit-other":
                    self.assertEqual(state["requests"].count(6), 2)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_native_rejection_unknown_reply_and_refusal_fail_without_retry(self):
        for mode in ("action-false", "action-unknown", "action-refused", "action-missing-error"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["requests"].count(7), 1)
                self.assertEqual(state["press_state"], "refused" if mode == "action-false" else "submitted")
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_hit_test_returns_actual_non_root_target_and_no_reusable_token(self):
        result, state, error = await self.run_capture("hit-test", operation="hit-test", pid=None)
        self.assertIsNone(error)
        self.assertEqual(result["scope"], "point-hit-test")
        self.assertTrue(result["targetStable"])
        self.assertEqual(result["application"]["pid"], 42)
        self.assertEqual(result["target"]["description"], "Actual hit element")
        self.assertEqual(state["requests"], [6, 1, 5, 6])
        self.assertNotIn("token", result)
        self.assertNotIn("isHittable", result)
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_hit_test_rejects_changed_target_and_cleans_up(self):
        result, state, error = await self.run_capture("hit-target-changed", operation="hit-test", pid=None)
        self.assertIsNone(result)
        self.assertIn("hit target changed", str(error))
        self.assertEqual(state["requests"], [6, 1, 5, 6])
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_timeout_and_connection_error_never_replay_and_still_clean_up(self):
        for mode in ("action-timeout", "action-connection-error"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press")
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["requests"].count(7), 1)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_press_accepted_then_cleanup_timeout_keeps_accepted_failure_state(self):
        result, state, error = await self.run_capture("action-stop-timeout", operation="press")
        self.assertIsNone(result)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["press_state"], "accepted")
        self.assertTrue(state["closed"] and state["dtx_closed"])
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = ipb_ax.report_failure(argparse.Namespace(operation="press", press_state=state["press_state"]), error, 5)
        self.assertEqual(code, 6)
        self.assertIn("native press accepted", stderr.getvalue())
        self.assertIn("do not retry automatically", stderr.getvalue())

    def test_post_submission_timeout_and_cancellation_always_report_nonretryable_state(self):
        cases = (
            ("submitted", TimeoutError("tunnel close timeout after submission"), "outcome unknown"),
            ("submitted", asyncio.CancelledError(), "outcome unknown"),
            ("accepted", TimeoutError("outer timeout after native acceptance"), "native press accepted"),
            ("refused", RuntimeError("cleanup failed after native refusal"), "native press refused"),
        )
        for state, error, expected in cases:
            with self.subTest(state=state, error=type(error).__name__):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = ipb_ax.report_failure(argparse.Namespace(operation="press", press_state=state), error, 5)
                self.assertEqual(code, 6)
                self.assertIn(expected, stderr.getvalue())
                self.assertIn("do not retry automatically", stderr.getvalue())

    def test_empty_timeout_and_cancel_have_actionable_diagnostics(self):
        for error, expected in ((TimeoutError(), "timed out"), (asyncio.CancelledError(), "cancelled")):
            for state, expected_code in (("not-sent", 5), ("accepted", 6)):
                with self.subTest(error=type(error).__name__, state=state):
                    stderr = io.StringIO()
                    with redirect_stderr(stderr):
                        code = ipb_ax.report_failure(argparse.Namespace(operation="press", press_state=state), error, 5)
                    self.assertEqual(code, expected_code)
                    self.assertIn(expected, stderr.getvalue())
                    if state == "accepted":
                        self.assertIn("native press accepted", stderr.getvalue())
                        self.assertIn("do not retry automatically", stderr.getvalue())

    def test_pre_submission_failure_keeps_original_exit_code(self):
        for code in (1, 5):
            with self.subTest(code=code):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    actual = ipb_ax.report_failure(argparse.Namespace(operation="press", press_state="not-sent"),
                                                   TimeoutError("before submission"), code)
                self.assertEqual(actual, code)
                self.assertNotIn("do not retry", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
