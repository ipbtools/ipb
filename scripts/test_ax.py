#!/usr/bin/env python3
"""AX wire and failure-contract checks, without a phone or optional host packages."""
import argparse
import asyncio
import copy
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
    async def run_capture(self, mode, *, deep=True):
        state = {"requests": [], "attribute_requests": [], "closed": False,
                 "dtx_closed": False, "root_reads": 0}
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
                    return None
                req = ax_archive.decode(args[0])
                state["requests"].append(req["requestType"])
                if req["requestType"] == 1:
                    result = TOKEN
                elif req["requestType"] == 2:
                    if mode == "snapshot-timeout":
                        raise TimeoutError("fixture type-2 transport timeout")
                    result = snapshot(TOKEN, [snapshot(CHILD)])
                    if mode in ("native-duplicate", "native-parent-duplicate"):
                        result = snapshot(TOKEN, [snapshot(CHILD), snapshot(CHILD)])
                    if mode == "native-deep":
                        container = {**CHILD, "objectID": 102}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)])])
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
                else:
                    token = req["translation"]
                    requested = req["parameters"]["attributes"]
                    state["attribute_requests"].append((token["objectID"], requested))
                    if token["objectID"] == CHILD["objectID"] and 3 in requested and mode in ("description", "label-timeout"):
                        raise TimeoutError("fixture stalled Label")
                    if token["objectID"] == TOKEN["objectID"]:
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
                    result = {key: val for key, val in result.items() if key in requested}
                if mode == "notification":
                    await self.conn._services[0].packet(archive({"associatedRequestType": 11, "resultData": None}))
                await self.conn._services[0].packet(archive({"associatedRequestType": req["requestType"], "resultData": result,
                    "error": 0, "attribute": 51 if mode == "wrong-attribute" else req["attributeType"],
                    "associatedTranslationObject": req["translation"]}))
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
        mods = {name: types.ModuleType(name) for name in ("pymobiledevice3", "pymobiledevice3.dtx",
                "pymobiledevice3.dtx.service", "pymobiledevice3.exceptions")}
        mods["pymobiledevice3.dtx"].DTXConnection = Connection
        mods["pymobiledevice3.dtx.service"].DTXControlService = Service
        mods["pymobiledevice3.dtx.service"].dtx_on_invoke = lambda name: lambda fn: fn
        mods["pymobiledevice3.exceptions"].ConnectionTerminatedError = Terminated
        args = argparse.Namespace(pid=42, point=(.5, .5), device_id="fixture", deep=deep)
        with patch.dict(sys.modules, mods):
            try:
                result = await ipb_ax.capture(Rsd(), args)
                return result, state, None
            except Exception as error:
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
        self.assertIs(result["nodes"][2]["enabled"], False)
        self.assertEqual(state["requests"].count(2), 1)

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


if __name__ == "__main__":
    unittest.main()
