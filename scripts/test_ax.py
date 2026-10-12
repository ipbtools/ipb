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


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def run_capture(self, mode):
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
                        if mode in ("description", "description-changed"):
                            result[33] = "Test app"
                        if mode == "description-changed" and state["root_reads"] > 1:
                            result[33] = "Changed app description"
                        if mode == "label-changed" and state["root_reads"] > 2:
                            result[3] = "Changed app label"
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
                await self.conn._services[0].packet(archive({"associatedRequestType": req["requestType"], "resultData": result, "error": 0}))
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
        args = argparse.Namespace(pid=42, point=(.5, .5), device_id="fixture")
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

    async def test_changed_root_does_not_emit_partial_tree(self):
        result, state, error = await self.run_capture("changed")
        self.assertIsNone(result)
        self.assertRegex(str(error), "root changed")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_description_avoids_stalled_label_without_renaming_it(self):
        result, state, error = await self.run_capture("description")
        self.assertIsNone(error)
        self.assertEqual(result["nodeCount"], 2)
        self.assertEqual(result["attributePolicy"], "description-first")
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
        self.assertRegex(str(error), "root changed")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_changed_root_label_without_description_still_fails(self):
        result, state, error = await self.run_capture("label-changed")
        self.assertIsNone(result)
        self.assertRegex(str(error), "root changed")
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
