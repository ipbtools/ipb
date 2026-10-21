#!/usr/bin/env python3
"""AX wire and failure-contract checks, without a phone or optional host packages."""
import argparse
import asyncio
import copy
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import plistlib
import signal
import sys
import tempfile
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

    def test_alert_press_cli_requires_explicit_pid_title_button_and_json(self):
        base = ["ipb ui", "alert-press"]
        cases = (
            (base + ["--alert-label", "title", "--label", "Allow Paste", "--json"], "requires --pid"),
            (base + ["--pid", "37", "--label", "Allow Paste", "--json"], "requires a non-empty --alert-label"),
            (base + ["--pid", "37", "--alert-label", "title", "--json"], "requires at least one"),
            (base + ["--pid", "37", "--alert-label", "title", "--label", "Allow Paste"], "requires --json"),
            (base + ["--pid", "37", "--alert-label", "title", "--identifier", "x",
                     "--label", "Allow Paste", "--json"], "accepts only --label"),
            (base + ["--pid", "37", "--alert-label", "title", "--value", "x",
                     "--label", "Allow Paste", "--json"], "accepts only --label"),
            (base + ["--pid", "37", "--alert-label", "title", "--class", "UIButton",
                     "--label", "Allow Paste", "--json"], "accepts only --label"),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv), patch("sys.argv", argv), redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    ipb_ax.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(expected, stderr.getvalue())

        captured = {}
        async def fake_run(args):
            captured.update(vars(args))
            return {"schemaVersion": 1, "scope": "test"}
        with patch("sys.argv", base + ["--pid", "37", "--alert-label", "Settings would like to paste",
                                       "--label", "Allow Paste", "--json"]), \
             patch.dict("os.environ", {"IPB_AX_DEVICE_ID": "fixture-device", "IPB_AX_UDID": "fixture-udid"}), \
             patch.object(ipb_ax, "version", return_value="11.10.2"), \
             patch.object(ipb_ax, "run", new=fake_run), redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(ipb_ax.main(), 0)
        self.assertEqual(captured["operation"], "alert-press")
        self.assertEqual(captured["pid"], 37)
        self.assertEqual(captured["alert_label"], "Settings would like to paste")
        self.assertEqual(captured["label"], "Allow Paste")
        self.assertIsNone(captured["identifier"])
        self.assertIsNone(captured["value"])
        self.assertIsNone(captured["class_name"])
        self.assertTrue(captured["json"])
        self.assertEqual(json.loads(stdout.getvalue())["scope"], "test")


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

    def test_kind_seven_accepts_supported_one_shot_actions_only_with_a_token(self):
        scroll = ax_archive.decode(ax_archive.request(7, None, translation=TOKEN, action=11))
        self.assertEqual((scroll["requestType"], scroll["actionType"]), (7, 11))
        self.assertEqual(scroll["translation"]["objectID"], TOKEN["objectID"])
        self.assertIsNone(scroll["parameters"])
        with self.assertRaises(ValueError):
            ax_archive.request(7, None, action=11)
        for action in (0, 1, 6, 12):
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

    def test_native_locator_selectors_are_exact_conjunctive_and_deduplicate_handles(self):
        first = {**CHILD, "objectID": 201}
        second = {**CHILD, "objectID": 202}
        first_attrs = {2001: "Save", 2003: FRAME, 2006: "Ready", 5019: "save-id"}
        second_attrs = {2001: "Save", 2003: FRAME, 2006: "Ready", 5019: "other-id"}
        tree = snapshot(TOKEN, [snapshot(first, attrs=first_attrs), snapshot(first, attrs=first_attrs),
                                snapshot(second, attrs=second_attrs)])

        _, matches = ipb_ax.native_matches(tree, TOKEN, {"label": "Save", "value": "Ready"})
        self.assertEqual(len(matches), 2)
        repeated = next(match for match in matches if match["token"]["objectID"] == 201)
        self.assertEqual(repeated["nodeIds"], ["n1", "n2"])

        _, matches = ipb_ax.native_matches(tree, TOKEN, {"identifier": "save-id", "label": "Save"})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["token"]["objectID"], 201)
        self.assertEqual(ipb_ax.native_matches(tree, TOKEN, {"label": "save"})[1], [])
        self.assertEqual(ipb_ax.native_matches(tree, TOKEN, {"value": "ready"})[1], [])

    def test_native_class_selector_uses_only_exact_native_class_metadata(self):
        button = {**CHILD, "objectID": 301}
        label = {**CHILD, "objectID": 302}
        tree = snapshot(TOKEN, [snapshot(button, attrs={2003: FRAME, 2001: "Search", 5003: "UIButton"}),
                                snapshot(label, attrs={2003: FRAME, 2001: "Search", 5003: "UILabel"}),
                                snapshot({**CHILD, "objectID": 303},
                                         attrs={2003: FRAME, 5003: "UISearchBarTextField"})])
        _, matches = ipb_ax.native_matches(tree, TOKEN, {"label": "Search", "className": "UIButton"})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["token"]["objectID"], 301)
        _, matches = ipb_ax.native_matches(tree, TOKEN, {"className": "UISearchBarTextField"})
        self.assertEqual(len(matches), 1)
        public = ipb_ax.public_matches(matches)[0]
        self.assertEqual(public["nativeAttributes"], {"5003": "UISearchBarTextField"})
        self.assertNotIn("identifier", public)
        self.assertNotIn("label", public)
        self.assertNotIn("value", public)

    def test_native_locator_public_results_never_expose_native_handles(self):
        tree = snapshot(TOKEN, [snapshot(CHILD, attrs={2003: FRAME, 5019: "fixture-id", 2001: "Fixture"})])
        _, matches = ipb_ax.native_matches(tree, TOKEN, {"identifier": "fixture-id"})
        public = ipb_ax.public_matches(matches)
        self.assertEqual(public, [{"id": "n1", "parentId": "n0", "depth": 1,
                                   "identifier": "fixture-id", "label": "Fixture", "frame": FRAME,
                                   "pathIds": ["n1"]}])
        encoded = json.dumps(public)
        self.assertNotIn("objectID", encoded)
        self.assertNotIn("pid", encoded)

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

    def test_foreign_ax_remote_proxy_leaves_are_explicit_without_changing_owned_nodes(self):
        own = {**CHILD, "objectID": 501}
        proxy1088 = {"pid": 1088, "objectID": 502, "isApplicationElement": False,
                     "didPopuldateAppInfo": True}
        proxy180 = {"pid": 180, "objectID": 503, "isApplicationElement": False,
                    "didPopuldateAppInfo": True}
        tree = snapshot(TOKEN, [snapshot(own, attrs={2003: FRAME, 5003: "AXRemoteElement"}),
                                snapshot(proxy1088, attrs={5003: "AXRemoteElement"}),
                                snapshot(proxy180, attrs={5003: "AXRemoteElement"})])
        nodes, _ = ipb_ax.snapshot_nodes(tree, TOKEN)
        self.assertEqual(nodes[0]["id"], "n0")
        self.assertNotIn("processIdentifier", nodes[0])
        self.assertNotIn("externalProcessReference", nodes[0])
        self.assertNotIn("processIdentifier", nodes[1])
        self.assertNotIn("externalProcessReference", nodes[1])
        self.assertEqual(nodes[2]["processIdentifier"], 1088)
        self.assertIs(nodes[2]["externalProcessReference"], True)
        self.assertEqual(nodes[3]["processIdentifier"], 180)
        self.assertIs(nodes[3]["externalProcessReference"], True)
        self.assertEqual(nodes[2]["children"], [])
        self.assertEqual(nodes[3]["children"], [])

    def test_foreign_nodes_must_be_ax_remote_terminal_proxies_with_consistent_children(self):
        foreign = {"pid": 1088, "objectID": 601, "isApplicationElement": False,
                   "didPopuldateAppInfo": True}
        leaf = snapshot(foreign, attrs={5003: "AXRemoteElement"})
        nonproxy = snapshot(foreign, attrs={5003: "UIButton"})
        container = snapshot(foreign, [snapshot({**foreign, "objectID": 602}, attrs={5003: "AXRemoteElement"})],
                             attrs={5003: "AXRemoteElement"})
        bad_count = copy.deepcopy(leaf)
        bad_count[ipb_ax.CHILD_COUNT] = 1
        inconsistent_children = copy.deepcopy(leaf)
        inconsistent_children[ipb_ax.CHILDREN] = [snapshot({**foreign, "objectID": 603},
                                                            attrs={5003: "AXRemoteElement"})]
        invalid_trees = (nonproxy, container, bad_count, inconsistent_children)
        for child in invalid_trees:
            with self.subTest(children=len(child[ipb_ax.CHILDREN]),
                              count=child[ipb_ax.CHILD_COUNT],
                              native_class=child[ipb_ax.NATIVE_ATTRS].get(5003)), self.assertRaises(ValueError):
                ipb_ax.snapshot_nodes(snapshot(TOKEN, [child]), TOKEN)

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
    async def run_capture(self, mode, *, deep=False, full_state=False, operation="capture", pid=42,
                          identifier="fixture-id", label=None, value=None, class_name=None,
                          wait_for="present", timeout=5.0, text="replacement", input_cli="/fixture/bin/ipb",
                          alert_label="Settings would like to paste from Safari"):
        state = {"requests": [], "attribute_requests": [], "structural_state_requests": [], "closed": False,
                 "dtx_closed": False, "root_reads": 0, "wire_requests": [],
                 "events": [], "display_calls": 0, "action_submissions": 0, "snapshot_reads": 0,
                 "action_types": [], "action_reply_errors": [],
                 "scroll_state": "not-sent"}
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
                    if not args[0] and mode in ("action-stop-timeout", "stop-timeout"):
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
                                     (mode in ("foreground-changed", "locate-pid-changed", "wait-pid-changed",
                                               "scroll-pid-changed", "input-pid-changed")
                                      and hit_number >= (2 if mode != "foreground-changed" else 3))) else 42
                    if operation == "press":
                        hit_object = (606 if mode == "center-hit-other" and hit_number == 2 else 201)
                    elif operation == "scroll-to-visible":
                        hit_object = (607 if mode == "scroll-post-hit-other" and state["action_submissions"] else
                                      201 if state["action_submissions"] else 606)
                    elif operation == "input":
                        hit_object = (201 if hit_number in (4, 7, 10) else 606)
                    else:
                        hit_object = 607 if mode == "hit-target-changed" and hit_number > 1 else 606
                    result = {"pid": hit_pid, "objectID": hit_object, "isApplicationElement": False, "didPopuldateAppInfo": True}
                elif kind == 7:
                    state["action_submissions"] += 1
                    state["action_types"].append(req["actionType"])
                    state["events"].append("action-submit")
                    if mode in ("action-timeout", "scroll-timeout", "alert-action-timeout"):
                        raise TimeoutError("fixture type-7 transport timeout")
                    if mode in ("action-connection-error", "alert-action-connection-error"):
                        raise ConnectionError("fixture type-7 connection error")
                    result = (mode not in ("action-false", "scroll-native-false", "alert-action-false",
                                           "scroll-native-false-post-timeout"))
                    if mode == "action-unknown":
                        result = {"unexpected": True}
                elif kind == 1:
                    state["events"].append("application-root")
                    selected_root = {**TOKEN, "pid": pid} if operation == "alert-press" else TOKEN
                    result = ({**selected_root, "objectID": selected_root["objectID"] + 1}
                              if mode == "root-identity-changed" and state["events"].count("application-root") > 1
                              else selected_root)
                elif kind == 2:
                    state["events"].append("fresh-snapshot")
                    state["snapshot_reads"] += 1
                    if mode == "snapshot-timeout":
                        raise TimeoutError("fixture type-2 transport timeout")
                    if (operation == "wait" and mode == "wait-deadline-during-snapshot" and
                            state["snapshot_reads"] > 1):
                        await asyncio.Event().wait()
                    if (operation == "scroll-to-visible" and mode in
                            ("scroll-post-snapshot-timeout", "scroll-native-false-post-timeout") and
                            state["action_submissions"]):
                        raise TimeoutError("fixture post-action type-2 timeout")
                    if operation == "alert-press":
                        root = {**TOKEN, "pid": pid}
                        modal_id = 701 if not (state["snapshot_reads"] == 2 and mode == "alert-modal-swap") else 711
                        button_id = 703 if not (state["snapshot_reads"] == 2 and mode == "alert-button-swap") else 713
                        after_action = state["action_submissions"] > 0
                        root_class = "UIView" if mode == "alert-root-wrong-class" else "SpringBoard"
                        bundle = "com.example.fake" if mode == "alert-root-wrong-bundle" else "com.apple.springboard"
                        root_attrs = {2003: FRAME, 5003: root_class, 3003: bundle}
                        if after_action and mode == "alert-post-timeout":
                            raise TimeoutError("fixture post-action type-2 timeout")
                        if (after_action and mode == "alert-post-modal-visible") or (
                                after_action and mode == "alert-visible-then-gone" and
                                state["snapshot_reads"] == 3):
                            result = snapshot(root, [snapshot(
                                {**CHILD, "pid": pid, "objectID": modal_id},
                                [snapshot({**CHILD, "pid": pid, "objectID": 702}, attrs={
                                    2001: alert_label, 2003: {"x": 20, "y": 20, "width": 300, "height": 40},
                                    5003: "UILabel", 2025: True}),
                                 snapshot({**CHILD, "pid": pid, "objectID": button_id}, attrs={
                                    2001: label, 2003: {"x": 20, "y": 100, "width": 120, "height": 50},
                                    5003: ipb_ax.ALERT_BUTTON_CLASS, 2025: True})],
                                attrs={2001: alert_label, 2003: FRAME,
                                       5003: ipb_ax.ALERT_CONTAINER_CLASS, 2025: True})], attrs=root_attrs)
                        elif after_action:
                            result = snapshot(root, attrs=root_attrs)
                        else:
                            modal = {**CHILD, "pid": pid, "objectID": modal_id}
                            title = {**CHILD, "pid": pid, "objectID": 702}
                            button = {**CHILD, "pid": pid, "objectID": button_id}
                            modal_class = "UIView" if mode == "alert-fake-modal-class" else ipb_ax.ALERT_CONTAINER_CLASS
                            button_class = ("UIButton" if mode == "alert-fake-button-class"
                                            else ipb_ax.ALERT_BUTTON_CLASS)
                            button_visible = mode != "alert-button-hidden"
                            modal_attrs = {2001: ("Different modal title" if mode == "alert-modal-wrong-title"
                                                else alert_label), 2003: FRAME,
                                           5003: modal_class, 2025: True}
                            title_attrs = {2001: ("Different title" if mode == "alert-wrong-title" else alert_label),
                                           2003: {"x": 20, "y": 20, "width": 300, "height": 40},
                                           5003: "UILabel", 2025: True}
                            button_attrs = {2001: label,
                                            2003: {"x": 20, "y": 100, "width": 120, "height": 50},
                                            5003: button_class, 2025: button_visible}
                            modal_children = [snapshot(title, attrs=title_attrs)]
                            if mode == "alert-button-outside-modal":
                                children = [snapshot(modal, modal_children, attrs=modal_attrs),
                                            snapshot(button, attrs=button_attrs)]
                            elif mode == "alert-foreign-target":
                                foreign = {"pid": 1088, "objectID": 703, "isApplicationElement": False,
                                           "didPopuldateAppInfo": True}
                                modal_children.append(snapshot(foreign, attrs={
                                    2001: label, 2003: button_attrs[2003], 5003: "AXRemoteElement", 2025: True}))
                                children = [snapshot(modal, modal_children, attrs=modal_attrs)]
                            else:
                                modal_children.append(snapshot(button, attrs=button_attrs))
                                children = [snapshot(modal, modal_children, attrs=modal_attrs)]
                            if mode == "alert-duplicate-modal":
                                other_modal = {**modal, "objectID": 712}
                                children.append(snapshot(other_modal, [snapshot({**title, "objectID": 722}, attrs=title_attrs),
                                                                      snapshot({**button, "objectID": 723}, attrs=button_attrs)],
                                                        attrs=modal_attrs))
                            if mode == "alert-duplicate-button":
                                children[0][ipb_ax.CHILDREN].append(snapshot({**button, "objectID": 733}, attrs=button_attrs))
                                children[0][ipb_ax.CHILD_COUNT] += 1
                            result = snapshot(root, children, attrs=root_attrs)
                    elif operation == "press":
                        target = {"pid": 1088 if mode == "foreign-target-press" else 42,
                                  "objectID": 201, "isApplicationElement": False, "didPopuldateAppInfo": True}
                        target_frame = {"x": 0, "y": 0, "width": 0, "height": 0} if mode == "action-empty-frame" else FRAME
                        target_identifier = ("implicit-id" if identifier is None and
                                             mode in ("label-only-press", "value-only-press", "qualified-id-changed")
                                             else identifier)
                        target_attrs = {2003: target_frame}
                        if not (mode == "class-only-press" and identifier is None):
                            target_attrs[5019] = target_identifier
                        if label is not None:
                            target_attrs[2001] = "Changed label" if mode == "qualified-target-changed" and state["snapshot_reads"] > 1 else label
                        if value is not None:
                            target_attrs[2006] = value
                        if class_name is not None:
                            target_attrs[5003] = ("UILabel" if mode == "qualified-class-changed" and
                                                  state["snapshot_reads"] > 1 else class_name)
                        if mode == "foreign-target-press":
                            target_attrs[5003] = "AXRemoteElement"
                        if mode == "action-no-match":
                            target_attrs[5019] = "other-id"
                        if mode == "action-ambiguous":
                            other = {"pid": 42, "objectID": 202, "isApplicationElement": False, "didPopuldateAppInfo": True}
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs), snapshot(other, attrs={2003: FRAME, 5019: identifier})])
                        elif mode == "action-repeat-same-handle":
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs), snapshot(target, attrs=target_attrs)])
                        else:
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs)])
                    elif operation == "input":
                        after_child = state.get("input_child_calls", 0) > 0
                        if after_child and mode == "input-post-missing":
                            result = snapshot(TOKEN)
                        else:
                            target = {**CHILD, "objectID": 201}
                            target_attrs = {2003: FRAME, 5019: identifier, 2004: ipb_ax.TEXT_ENTRY_TRAIT,
                                            2006: (text if after_child and mode not in
                                                   ("input-post-changed", "input-child-failed") else "before")}
                            if mode == "input-stale-value" and state["snapshot_reads"] > 1 and not after_child:
                                target_attrs[2006] = "changed before submission"
                            if label is not None:
                                target_attrs[2001] = label
                            if value is not None:
                                target_attrs[2006] = value
                            if class_name is not None:
                                target_attrs[5003] = class_name
                            responder = {ipb_ax.ELEMENT: target,
                                         ipb_ax.NATIVE_ATTRS: dict(target_attrs)}
                            if mode == "input-not-focused":
                                responder[ipb_ax.ELEMENT] = {**target, "objectID": 202}
                            if mode == "input-non-text-entry":
                                target_attrs[2004] = 1
                                responder[ipb_ax.NATIVE_ATTRS][2004] = 1
                            if mode == "input-foreign-target":
                                target = {**target, "pid": 1088}
                                target_attrs[5003] = "AXRemoteElement"
                                responder[ipb_ax.ELEMENT] = target
                                responder[ipb_ax.NATIVE_ATTRS] = dict(target_attrs)
                            root_attrs = {3002: responder}
                            if mode == "input-ambiguous":
                                other = {**CHILD, "objectID": 202}
                                result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs),
                                                          snapshot(other, attrs=target_attrs)], attrs=root_attrs)
                            elif after_child and mode == "input-post-target-changed":
                                other = {**target, "objectID": 202}
                                result = snapshot(TOKEN, [snapshot(other, attrs=target_attrs)], attrs=root_attrs)
                            else:
                                result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs)], attrs=root_attrs)
                    elif operation == "scroll-to-visible":
                        after_action = state["action_submissions"] > 0
                        if after_action and mode == "scroll-post-missing":
                            result = snapshot(TOKEN)
                        else:
                            target_id = 202 if after_action and mode == "scroll-post-target-changed" else 201
                            target = {"pid": 1088 if mode == "foreign-target-scroll" and not after_action else 42,
                                      "objectID": target_id, "isApplicationElement": False,
                                      "didPopuldateAppInfo": True}
                            offscreen = {"x": 450, "y": 900, "width": 60, "height": 30}
                            visible_frame = {"x": 100, "y": 100, "width": 60, "height": 30}
                            target_frame = (offscreen if not after_action or
                                            (after_action and mode == "scroll-post-offscreen") else visible_frame)
                            visible_native = bool(after_action and mode != "scroll-post-hidden")
                            target_attrs = {2003: target_frame, 2025: visible_native}
                            if identifier is not None:
                                target_attrs[5019] = identifier
                            if label is not None:
                                target_attrs[2001] = label
                            if value is not None:
                                target_attrs[2006] = value
                            if class_name is not None:
                                target_attrs[5003] = ("UILabel" if mode == "scroll-qualified-class-changed" and
                                                      state["snapshot_reads"] > 1 and
                                                      not after_action else class_name)
                            if mode == "foreign-target-scroll" and not after_action:
                                target_attrs[5003] = "AXRemoteElement"
                            if mode == "scroll-post-ambiguous" and after_action:
                                other = {**target, "objectID": 203}
                                result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs),
                                                          snapshot(other, attrs=target_attrs)])
                            else:
                                result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs)])
                    elif operation in ("locate", "wait"):
                        target = {**CHILD, "objectID": 201}
                        target_attrs = {2003: FRAME, 5019: identifier or "fixture-id",
                                        2001: label or "Fixture", 2006: value or "Ready"}
                        if class_name is not None:
                            target_attrs[5003] = class_name
                        if mode == "class-only-search":
                            target_attrs = {2003: FRAME, 5003: class_name}
                        present = True
                        if mode == "locator-missing":
                            present = False
                        if mode == "wait-present":
                            present = state["snapshot_reads"] > 1
                        if mode == "wait-absent":
                            present = state["snapshot_reads"] == 1
                        if mode == "wait-timeout":
                            present = False
                        if mode == "wait-deadline-during-snapshot":
                            present = False
                        if mode == "wait-snapshot-error":
                            raise RuntimeError("fixture native snapshot failed")
                        if mode == "locator-class-pair":
                            other = {**CHILD, "objectID": 202}
                            other_attrs = {**target_attrs, 5003: "UILabel"}
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs),
                                                      snapshot(other, attrs=other_attrs)])
                        elif mode in ("locator-ambiguous", "wait-ambiguous"):
                            other = {**CHILD, "objectID": 202}
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs),
                                                      snapshot(other, attrs=target_attrs)])
                        elif mode == "locator-repeat-path":
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs),
                                                      snapshot(target, attrs=target_attrs)])
                        else:
                            result = snapshot(TOKEN, [snapshot(target, attrs=target_attrs)] if present else [])
                    else:
                        result = snapshot(TOKEN, [snapshot(CHILD)])
                    if mode in ("native-duplicate", "native-parent-duplicate"):
                        result = snapshot(TOKEN, [snapshot(CHILD), snapshot(CHILD)])
                    if mode == "native-deep":
                        container = {**CHILD, "objectID": 102}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs={2003: FRAME, 2025: False})])
                    if mode in ("native-deep-state", "native-deep-known-false", "native-deep-visible-priority",
                                "supplement-refused", "supplement-timeout", "supplement-invalid",
                                "supplement-extra-fields"):
                        container = {**CHILD, "objectID": 102}
                        container_attrs = {2001: "Native title", 2003: FRAME, 5019: "container-id", 2025: False}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs=container_attrs)])
                    if mode == "native-structural-duplicate":
                        container = {**CHILD, "objectID": 102}
                        container_attrs = {2001: "Native title", 2003: FRAME, 5019: "container-id", 2025: False}
                        result = snapshot(TOKEN, [snapshot(container, [snapshot(CHILD)], attrs=container_attrs),
                                                  snapshot(container, [snapshot(CHILD)], attrs=container_attrs)])
                    if mode == "native-nil":
                        result = None
                    if mode == "native-child-pid-mismatch":
                        result = snapshot(TOKEN, [snapshot({**CHILD, "pid": CHILD["pid"] + 1})])
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
                        id_value = ("implicit-id" if identifier is None and
                                    mode in ("label-only-press", "value-only-press") else identifier)
                        if mode == "qualified-id-changed":
                            id_value = "changed-implicit-id"
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
                    elif operation == "scroll-to-visible":
                        after_action = state["action_submissions"] > 0
                        native_frame = ({"x": 450, "y": 900, "width": 60, "height": 30}
                                        if not after_action or mode == "scroll-post-offscreen" else
                                        {"x": 100, "y": 100, "width": 60, "height": 30})
                        id_value = identifier
                        if mode == "scroll-pre-id-changed" and not after_action:
                            id_value = "changed-id"
                        enabled_value = mode != "scroll-pre-disabled" if not after_action else True
                        visible_value = bool(after_action and mode != "scroll-post-hidden")
                        result = {21: native_frame, 25: id_value, 27: enabled_value, 32: visible_value}
                    elif operation == "input":
                        result = {21: FRAME, 25: identifier, 27: True, 32: True}
                    elif operation == "alert-press":
                        enabled = mode != "alert-live-disabled"
                        result = {21: {"x": 20, "y": 100, "width": 120, "height": 50},
                                  25: identifier, 27: enabled, 32: True}
                    elif operation == "hit-test":
                        state["events"].append("hit-target-attributes")
                        result = {8: [], 21: FRAME, 33: "Actual hit element"}
                        if 33 not in requested:
                            result.pop(33)
                    elif token["objectID"] == 102 and mode in ("native-deep-state", "native-deep-known-false",
                                                                  "native-deep-visible-priority", "native-structural-duplicate",
                                                                  "supplement-extra-fields"):
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
                    elif mode == "supplement-timeout":
                        raise TimeoutError("fixture supplemental timeout")
                    elif mode == "supplement-invalid":
                        result = ["invalid supplemental record"]
                    elif token["objectID"] == CHILD["objectID"] and 3 in requested and mode in ("description", "label-timeout"):
                        raise TimeoutError("fixture stalled Label")
                    elif token["objectID"] == TOKEN["objectID"]:
                        state["root_reads"] += 1
                        children = [CHILD]
                        if mode == "ordinary-foreign-child":
                            children = [{"pid": 1088, "objectID": 303,
                                         "isApplicationElement": False, "didPopuldateAppInfo": True}]
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
                    reply["error"] = (8 if mode == "supplement-refused" and kind == 5 else
                                       9 if mode in ("action-refused", "scroll-refused", "alert-native-error") and kind == 7 else 0)
                    if kind == 7:
                        state["action_reply_errors"].append(reply["error"])
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
                if mode == "dtx-close-error":
                    raise RuntimeError("fixture DTX close failed")
        class Socket:
            reader = writer = None
            async def close(self):
                state["closed"] = True
                if mode == "socket-close-error":
                    raise RuntimeError("fixture socket close failed")
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
                                  press_state="not-sent", scroll_state="not-sent",
                                  operation=operation, identifier=identifier,
                                  label=label, value=value, class_name=class_name,
                                  wait_for=wait_for, wait_state=wait_for, timeout=timeout,
                                  text=text, replace_all=True, input_cli=input_cli, input_state="not-sent",
                                  alert_label=alert_label, json=True)
        async def fake_input_child(cli, device_id, child_text):
            state["input_child_calls"] = state.get("input_child_calls", 0) + 1
            state["input_child_argv"] = [cli, "-s", device_id, "text", "--replace-all", child_text]
            if mode == "input-child-timeout":
                raise TimeoutError("fixture child timeout")
            return 7 if mode == "input-child-failed" else 0
        with patch.dict(sys.modules, mods):
            with patch.object(ipb_ax, "run_input_child", fake_input_child):
                try:
                    result = await ipb_ax.capture(Rsd(), args)
                    state["press_state"] = args.press_state
                    state["scroll_state"] = args.scroll_state
                    state["input_state"] = args.input_state
                    return result, state, None
                except Exception as error:
                    state["press_state"] = args.press_state
                    state["scroll_state"] = args.scroll_state
                    state["input_state"] = args.input_state
                    return None, state, error

    async def test_default_ordinary_schema_and_description_contract_are_unchanged(self):
        result, state, error = await self.run_capture("description")
        self.assertIsNone(error)
        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["hierarchySource"], "AXChildren")
        self.assertEqual(result["attributePolicy"], "description-first")
        self.assertEqual(result["ordinaryAXNodeCount"], 2)
        self.assertEqual(result["nodes"][1]["description"], "Example video title")
        for node in result["nodes"]:
            self.assertNotIn("processIdentifier", node)
            self.assertNotIn("externalProcessReference", node)
        self.assertNotIn(2, state["requests"])

    async def test_ordinary_axchildren_still_rejects_foreign_process_children(self):
        result, state, error = await self.run_capture("ordinary-foreign-child")
        self.assertIsNone(result)
        self.assertIn("AX child belongs to another process", str(error))
        self.assertNotIn(2, state["requests"])

    async def test_foreign_proxy_target_is_never_used_for_press_or_scroll(self):
        for operation, mode, action_kind, state_key in (
                ("press", "foreign-target-press", 7, "press_state"),
                ("scroll-to-visible", "foreign-target-scroll", 7, "scroll_state")):
            with self.subTest(operation=operation):
                result, state, error = await self.run_capture(
                    mode, operation=operation, identifier="fixture-id", pid=42)
                self.assertIsNone(result)
                self.assertIn("belongs to another process", str(error))
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(action_kind, state["action_types"])
                self.assertEqual(state[state_key], "not-sent")
                self.assertNotIn(5, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_input_requires_unique_current_text_responder_before_child_invocation(self):
        for mode, expected in (("input-ambiguous", "selector matches=2"),
                               ("input-not-focused", "not the current first responder"),
                               ("input-non-text-entry", "not a known text-entry element"),
                               ("input-foreign-target", "same-process"),
                               ("input-stale-value", "value changed before submission"),
                               ("input-pid-changed", "displayed AX process changed"),
                               ("display-changed", "AX display changed"),
                               ("root-identity-changed", "application root identity changed")):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(
                    mode, operation="input", pid=42, identifier="fixture-id", text="New value")
                self.assertIsNone(result)
                self.assertIn(expected, str(error))
                self.assertEqual(state.get("input_child_calls", 0), 0)
                self.assertEqual(state["input_state"], "not-sent")
                self.assertNotIn("input_child_argv", state)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_input_invokes_replace_all_child_once_and_requires_exact_same_handle_value(self):
        result, state, error = await self.run_capture(
            "input-success", operation="input", pid=42, identifier="fixture-id",
            text="literal $(touch /tmp/not-run) 中文", input_cli="/opt/ipb/bin/ipb")
        self.assertIsNone(error)
        self.assertTrue(result["postconditionVerified"])
        self.assertEqual(result["scope"], "native-first-responder-input")
        self.assertEqual(result["action"]["textLength"], len("literal $(touch /tmp/not-run) 中文"))
        self.assertEqual(state["input_child_calls"], 1)
        self.assertEqual(state["input_child_argv"], [
            "/opt/ipb/bin/ipb", "-s", "fixture", "text", "--replace-all",
            "literal $(touch /tmp/not-run) 中文"])
        self.assertEqual(state["input_state"], "child-exited-zero")
        self.assertNotIn("objectID", json.dumps(result))
        self.assertNotIn("literal $(touch /tmp/not-run) 中文", json.dumps(result))
        input_options = [request["parameters"]["parameter"]["attributes"]
                         for request in state["wire_requests"] if request["requestType"] == 2]
        self.assertTrue(input_options)
        self.assertTrue(all(3002 in attrs for attrs in input_options))

    async def test_input_postcondition_failures_and_child_failure_are_reported_without_replay(self):
        for mode, status in (("input-post-changed", "postcondition_failed"),
                             ("input-post-missing", "postcondition_failed"),
                             ("input-post-target-changed", "postcondition_failed"),
                             ("input-child-failed", "child_failed")):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(
                    mode, operation="input", pid=42, identifier="fixture-id", text="replace me")
                self.assertIsNone(error)
                self.assertEqual(result["status"], status)
                self.assertFalse(result["postconditionVerified"])
                self.assertEqual(state["input_child_calls"], 1)
                self.assertEqual(state["input_state"], "child-exited-nonzero" if mode == "input-child-failed"
                                 else "child-exited-zero")

    async def test_input_child_timeout_keeps_unknown_outcome_and_never_replays(self):
        result, state, error = await self.run_capture(
            "input-child-timeout", operation="input", pid=42, identifier="fixture-id", text="possibly partial")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "child_outcome_unknown")
        self.assertFalse(result["postconditionVerified"])
        self.assertIsNone(result["action"]["childExitCode"])
        self.assertEqual(state["input_child_calls"], 1)
        self.assertEqual(state["input_state"], "child-unknown")

    async def test_alert_press_preflight_requires_springboard_unique_visible_modal_button_without_hit_test(self):
        cases = (
            ("alert-root-wrong-class", "SpringBoard root"),
            ("alert-root-wrong-bundle", "SpringBoard root"),
            ("alert-fake-modal-class", "exactly one visible native alert container"),
            ("alert-fake-button-class", "exact-label native button"),
            ("alert-duplicate-modal", "exactly one visible native alert container"),
            ("alert-duplicate-button", "exact-label native button"),
            ("alert-button-outside-modal", "exact-label native button"),
            ("alert-foreign-target", "exact-label native button"),
            ("alert-modal-wrong-title", "exact title"),
            ("alert-button-hidden", "exact-label native button"),
            ("alert-live-disabled", "known enabled and visible"),
            ("alert-modal-swap", "modal identity/frame/class/label changed"),
            ("alert-button-swap", "button identity/frame/class/label changed"),
            ("root-identity-changed", "SpringBoard root identity changed"),
            ("display-changed", "display changed"),
        )
        for mode, expected in cases:
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(
                    mode, operation="alert-press", pid=37, identifier=None, value=None,
                    class_name=None, label="Allow Paste",
                    alert_label="Settings would like to paste from Safari")
                self.assertIsNone(result)
                self.assertIn(expected, str(error))
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                self.assertNotIn(6, state["requests"])
                self.assertEqual(state["press_state"], "not-sent")

    async def test_alert_press_uses_one_action_five_without_hit_test_and_verifies_modal_disappearance(self):
        result, state, error = await self.run_capture(
            "alert-success", operation="alert-press", pid=37, identifier=None, value=None,
            class_name=None, label="Allow Paste",
            alert_label="Settings would like to paste from Safari")
        self.assertIsNone(error)
        self.assertEqual(result["scope"], "springboard-modal-action")
        self.assertIs(result["hitTestVerified"], False)
        self.assertTrue(result["postconditionVerified"] and result["effectVerified"])
        self.assertEqual(result["postcondition"], {
            "originalModalNoLongerVisible": True, "originalButtonNoLongerVisible": True})
        self.assertEqual(state["requests"].count(6), 0)
        self.assertEqual(state["action_submissions"], 1)
        action_requests = [request for request in state["wire_requests"] if request["requestType"] == 7]
        self.assertEqual([request["actionType"] for request in action_requests], [5])
        self.assertEqual(action_requests[0]["translation"]["pid"], 37)
        self.assertEqual(action_requests[0]["translation"]["objectID"], 703)
        live_requests = [request for request in state["wire_requests"] if request["requestType"] == 5]
        self.assertEqual([request["parameters"]["attributes"] for request in live_requests], [[21, 25, 27, 32]])
        self.assertEqual(state["snapshot_reads"], 3)
        self.assertEqual(state["press_state"], "accepted")

    async def test_alert_press_false_result_is_refused_and_post_modal_visibility_is_not_success(self):
        refused, state, error = await self.run_capture(
            "alert-action-false", operation="alert-press", pid=37, identifier=None, value=None,
            class_name=None, label="Allow Paste", alert_label="Settings would like to paste from Safari")
        self.assertIsNone(error)
        self.assertEqual(refused["status"], "native_refused")
        self.assertFalse(refused["action"]["nativeAccepted"])
        self.assertFalse(refused["postconditionVerified"])
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["snapshot_reads"], 2)
        self.assertEqual(state["press_state"], "refused")

        with patch.object(ipb_ax, "ALERT_POSTCONDITION_SETTLE_S", 0.04), \
             patch.object(ipb_ax, "ALERT_POSTCONDITION_POLL_S", 0.002):
            visible, state, error = await self.run_capture(
                "alert-post-modal-visible", operation="alert-press", pid=37, identifier=None, value=None,
                class_name=None, label="Allow Paste", alert_label="Settings would like to paste from Safari")
        self.assertIsNone(error)
        self.assertEqual(visible["status"], "alert_postcondition_failed")
        self.assertFalse(visible["postconditionVerified"])
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["press_state"], "accepted")
        self.assertEqual(state["requests"].count(6), 0)

    async def test_alert_press_settles_after_first_visible_post_snapshot_then_gone(self):
        result, state, error = await self.run_capture(
            "alert-visible-then-gone", operation="alert-press", pid=37, identifier=None, value=None,
            class_name=None, label="Allow Paste", alert_label="Settings would like to paste from Safari")
        self.assertIsNone(error)
        self.assertTrue(result["postconditionVerified"] and result["effectVerified"])
        self.assertTrue(result["postcondition"]["originalModalNoLongerVisible"])
        self.assertTrue(result["postcondition"]["originalButtonNoLongerVisible"])
        self.assertGreaterEqual(result["postconditionObservations"], 2)
        self.assertEqual(state["snapshot_reads"], 4)
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["requests"].count(6), 0)

    async def test_alert_press_persistent_visibility_ends_at_bounded_deadline_without_replay(self):
        with patch.object(ipb_ax, "ALERT_POSTCONDITION_SETTLE_S", 0.08), \
             patch.object(ipb_ax, "ALERT_POSTCONDITION_POLL_S", 0.005):
            result, state, error = await self.run_capture(
                "alert-post-modal-visible", operation="alert-press", pid=37, identifier=None, value=None,
                class_name=None, label="Allow Paste", alert_label="Settings would like to paste from Safari")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "alert_postcondition_failed")
        self.assertFalse(result["postconditionVerified"])
        self.assertGreaterEqual(result["postconditionObservations"], 2)
        self.assertGreaterEqual(result["postconditionElapsedMs"], 70)
        self.assertLess(result["postconditionElapsedMs"], 500)
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["action_types"], [5])
        self.assertEqual(state["requests"].count(6), 0)

    async def test_alert_press_timeout_and_post_timeout_preserve_submitted_state_without_replay(self):
        for mode in ("alert-action-timeout", "alert-post-timeout"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(
                    mode, operation="alert-press", pid=37, identifier=None, value=None,
                    class_name=None, label="Allow Paste",
                    alert_label="Settings would like to paste from Safari")
                self.assertIsNone(result)
                self.assertIsInstance(error, TimeoutError)
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["press_state"], "submitted" if mode == "alert-action-timeout" else "accepted")
                self.assertEqual(state["requests"].count(6), 0)
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = ipb_ax.report_failure(argparse.Namespace(
                        operation="alert-press", press_state=state["press_state"]), error, 5)
                self.assertEqual(code, 6)
                self.assertIn("do not retry automatically", stderr.getvalue())

    async def test_alert_press_transport_and_cleanup_failures_keep_nonreplay_state(self):
        for mode, state_name, error_type in (
                ("alert-native-error", "submitted", ValueError),
                ("alert-action-connection-error", "submitted", RuntimeError),
                ("stop-error", "accepted", RuntimeError)):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(
                    mode, operation="alert-press", pid=37, identifier=None, value=None,
                    class_name=None, label="Allow Paste",
                    alert_label="Settings would like to paste from Safari")
                self.assertIsNone(result)
                self.assertIsInstance(error, error_type)
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["press_state"], state_name)
                self.assertEqual(state["requests"].count(6), 0)
                self.assertEqual(state["action_types"], [5])
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = ipb_ax.report_failure(argparse.Namespace(
                        operation="alert-press", press_state=state_name), error, 5)
                self.assertEqual(code, 6)
                self.assertIn("do not retry automatically", stderr.getvalue())

    async def test_unsolicited_notifications_are_not_assigned_to_ordinary_nodes(self):
        result, state, error = await self.run_capture("notification")
        self.assertIsNone(error)
        self.assertGreater(result["unsolicitedCount"], 0)
        self.assertEqual(result["schemaVersion"], 1)
        self.assertNotIn(2, state["requests"])
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_default_ordinary_root_signature_still_rejects_changed_children(self):
        result, state, error = await self.run_capture("changed")
        self.assertIsNone(result)
        self.assertIn("root changed during collection", str(error))
        self.assertIn("changed=children", str(error))
        self.assertNotIn(2, state["requests"])

    async def test_native_deep_avoids_all_ordinary_attribute_walk_failures(self):
        # These modes model the old ordinary walk's reachable missing children,
        # frame drift and root-child signature failures. Native deep must not ask
        # type 5 at all, so those unrelated failures cannot suppress its tree.
        for mode in ("missing", "frame-changed", "changed", "native-missing-element", "native-frame-mismatch"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True)
                self.assertIsNone(error)
                self.assertEqual(result["schemaVersion"], 2)
                self.assertEqual(result["attributePolicy"], "native-snapshot")
                self.assertEqual(result["stateScope"], "native-snapshot")
                self.assertEqual(result["rootStabilityScope"], "application-identity")
                self.assertIn("snapshotMs", result)
                self.assertNotIn("ordinaryAXNodeCount", result)
                self.assertEqual(state["requests"].count(2), 1)
                self.assertNotIn(5, state["requests"])
                snapshot_options = next(request["parameters"]["parameter"]
                                        for request in state["wire_requests"] if request["requestType"] == 2)
                self.assertNotIn(3002, snapshot_options["attributes"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_deep_revalidates_root_identity_and_pid(self):
        for mode in ("native-root-mismatch", "root-identity-changed", "native-child-pid-mismatch"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True)
                self.assertIsNone(result)
                self.assertIsInstance(error, ValueError)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_tree_geometry_null_and_repeated_paths(self):
        null_result, _, error = await self.run_capture("native-null-frame", deep=True)
        self.assertIsNone(error)
        self.assertEqual(null_result["nodes"][0]["frameUnavailable"], "CGRectNull")
        self.assertNotIn("frame", null_result["nodes"][0])
        result, state, error = await self.run_capture("native-duplicate", deep=True)
        self.assertIsNone(error)
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual((result["nodeCount"], result["uniqueElementCount"]), (3, 2))
        self.assertEqual(result["nodes"][0]["children"], ["n1", "n2"])
        self.assertEqual([node["attributeSource"] for node in result["nodes"]],
                         ["native-snapshot"] * 3)
        self.assertNotIn("navigationOrder", result["nodes"][0])
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_snapshot_limits_count_and_process_identity(self):
        for mode in ("native-truncated", "native-child-pid-mismatch"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True)
                self.assertIsNone(result)
                self.assertIsInstance(error, ValueError)
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_native_snapshot_nil_and_timeout_have_no_result(self):
        for mode, expected in (("native-nil", "snapshot unavailable"),
                               ("snapshot-timeout", "type=2")):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True)
                self.assertIsNone(result)
                self.assertIn(expected, str(error))
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_full_state_supplement_is_per_unique_handle_and_keeps_native_fields(self):
        result, state, error = await self.run_capture("native-deep-state", deep=True, full_state=True)
        self.assertIsNone(error)
        supplement = result["supplementalAX"]
        self.assertEqual((supplement["status"], supplement["scope"]), ("complete", "all-native-handles"))
        self.assertEqual(supplement["requestedElementCount"], 3)
        self.assertEqual(supplement["attemptedElementCount"], 3)
        self.assertEqual(supplement["completedElementCount"], 3)
        self.assertEqual(result["schemaVersion"], 2)
        container = next(node for node in result["nodes"] if node.get("identifier") == "container-id")
        self.assertEqual(container["attributeSource"], "native-snapshot")
        self.assertFalse(container["visible"])
        self.assertEqual(container["supplementalAX"]["enabled"], True)
        self.assertIs(container["supplementalAX"]["focused"], False)
        self.assertEqual(container["supplementalAX"]["placeholder"], "placeholder")
        self.assertEqual(container["frame"], FRAME)
        self.assertEqual(container["label"], "Native title")
        self.assertNotIn("enabled", container)
        self.assertNotIn("roleDescription", container)
        self.assertEqual(len(state["structural_state_requests"]), 1)
        self.assertEqual(state["structural_state_requests"][0][0], 102)
        self.assertEqual(state["requests"].count(5), 3)

    async def test_supplemental_extra_geometry_and_text_do_not_pollute_native_values(self):
        result, _, error = await self.run_capture("supplement-extra-fields", deep=True, full_state=True)
        self.assertIsNone(error)
        container = next(node for node in result["nodes"] if node.get("identifier") == "container-id")
        self.assertEqual(container["frame"], FRAME)
        self.assertEqual(container["label"], "Native title")
        self.assertNotIn("frame", container["supplementalAX"])
        self.assertNotIn("label", container["supplementalAX"])

    async def test_native_deep_rechecks_display_when_selected_by_point(self):
        result, state, error = await self.run_capture("display-changed", deep=True, pid=None)
        self.assertIsNone(result)
        self.assertIn("display changed during collection", str(error))
        self.assertEqual(state["requests"].count(2), 1)
        self.assertNotIn(5, state["requests"])
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_full_state_keeps_false_and_missing_attributes_distinct(self):
        result, _, error = await self.run_capture("native-deep-known-false", deep=True, full_state=True)
        self.assertIsNone(error)
        container = next(node for node in result["nodes"] if node.get("identifier") == "container-id")
        supplement = container["supplementalAX"]
        for key in ("enabled", "focused", "selected", "visible"):
            self.assertIs(supplement[key], False)
        for key in ("placeholder", "roleCode", "roleDescription", "subroleCode", "hint"):
            self.assertNotIn(key, supplement)
        self.assertEqual(container["attributeSource"], "native-snapshot")

    async def test_duplicate_native_handles_are_supplemented_once(self):
        result, state, error = await self.run_capture("native-structural-duplicate", deep=True, full_state=True)
        self.assertIsNone(error)
        matches = [node for node in result["nodes"] if node.get("identifier") == "container-id"]
        self.assertEqual(len(matches), 2)
        self.assertNotEqual(matches[0]["id"], matches[1]["id"])
        self.assertEqual(matches[0]["supplementalAX"], matches[1]["supplementalAX"])
        self.assertEqual(sum(object_id == 102 for object_id, _ in state["structural_state_requests"]), 1)

    async def test_supplement_failure_preserves_tree_and_stops_semantic_requests(self):
        expected_codes = {"supplement-refused": 1, "supplement-timeout": 5, "supplement-invalid": 1}
        for mode, code in expected_codes.items():
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True, full_state=True)
                self.assertIsNone(error)
                supplement = result["supplementalAX"]
                self.assertEqual(supplement["status"], "failed")
                self.assertEqual(supplement["exitCode"], code)
                self.assertGreater(supplement["attemptedElementCount"], supplement["completedElementCount"])
                self.assertEqual(result["nodeCount"], 3)
                self.assertEqual(len(result["nodes"]), 3)
                self.assertTrue(all(node["attributeSource"] == "native-snapshot" for node in result["nodes"]))
                self.assertEqual(state["requests"].count(5), supplement["attemptedElementCount"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_main_emits_complete_json_but_returns_supplement_failure_code(self):
        result, _, error = await self.run_capture("supplement-timeout", deep=True, full_state=True)
        self.assertIsNone(error)
        def fake_asyncio_run(coro):
            coro.close()
            return result
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ipb", "--deep", "--full-state", "--json"]), \
             patch.dict("os.environ", {"IPB_AX_DEVICE_ID": "fixture", "IPB_AX_UDID": "fixture"}), \
             patch.object(ipb_ax, "version", return_value="11.10.2"), \
             patch.object(ipb_ax.asyncio, "run", new=fake_asyncio_run), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = ipb_ax.main()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 5)
        self.assertEqual(payload["nodeCount"], 3)
        self.assertEqual(payload["supplementalAX"]["status"], "failed")
        self.assertIn("complete native snapshot emitted", stderr.getvalue())

    async def test_locate_is_read_only_reports_unique_public_matches_and_deduplicates_paths(self):
        for mode, expected_count, expected_unique in (("locate", 1, True),
                                                       ("locator-repeat-path", 1, True),
                                                       ("locator-missing", 0, False),
                                                       ("locator-ambiguous", 2, False)):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="locate", pid=42,
                                                              identifier="fixture-id", label="Fixture")
                self.assertIsNone(error)
                self.assertEqual(result["scope"], "native-locator")
                self.assertEqual((result["matchCount"], result["unique"]), (expected_count, expected_unique))
                self.assertEqual(result["atomic"], False)
                self.assertEqual(state["requests"], [1, 2, 1])
                self.assertNotIn(5, state["requests"])
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])
                for match in result["matches"]:
                    self.assertNotIn("objectID", json.dumps(match))
                    self.assertNotIn("pid", match)
                if mode == "locator-repeat-path":
                    self.assertEqual(result["matches"][0]["pathIds"], ["n1", "n2"])

    async def test_locate_class_disambiguates_native_controls_and_supports_class_only_search(self):
        result, state, error = await self.run_capture("locator-class-pair", operation="locate", pid=42,
                                                       identifier=None, label="Search", class_name="UIButton")
        self.assertIsNone(error)
        self.assertEqual(result["selectors"], {"label": "Search", "className": "UIButton"})
        self.assertEqual(result["matchCount"], 1)
        self.assertEqual(result["matches"][0]["nativeAttributes"], {"5003": "UIButton"})
        self.assertEqual(state["requests"], [1, 2, 1])

        result, state, error = await self.run_capture("class-only-search", operation="locate", pid=42,
                                                       identifier=None, class_name="UISearchBarTextField")
        self.assertIsNone(error)
        self.assertEqual(result["selectors"], {"className": "UISearchBarTextField"})
        self.assertEqual(result["matchCount"], 1)
        match = result["matches"][0]
        self.assertEqual(match["nativeAttributes"], {"5003": "UISearchBarTextField"})
        self.assertNotIn("identifier", match)
        self.assertNotIn("label", match)
        self.assertNotIn("value", match)
        self.assertNotIn(5, state["requests"])
        self.assertNotIn(7, state["requests"])

    async def test_class_only_press_revalidates_exact_class_and_rejects_a_class_change(self):
        result, state, error = await self.run_capture("class-only-press", operation="press", pid=42,
                                                       identifier=None, class_name="UISearchBarTextField")
        self.assertIsNone(error)
        self.assertEqual(result["action"]["selectors"], {"className": "UISearchBarTextField"})
        self.assertNotIn("identifier", result["action"])
        self.assertEqual(state["requests"], [6, 1, 2, 2, 5, 6, 6, 7])
        self.assertEqual(state["wire_requests"][-1]["actionType"], 5)
        self.assertEqual(state["action_submissions"], 1)

        result, state, error = await self.run_capture("qualified-class-changed", operation="press", pid=42,
                                                       identifier=None, class_name="UIButton")
        self.assertIsNone(result)
        self.assertIn("selector matches=0", str(error))
        self.assertEqual(state["requests"], [6, 1, 2, 2])
        self.assertEqual(state["action_submissions"], 0)
        self.assertNotIn(7, state["requests"])

    async def test_scroll_to_visible_submits_action_eleven_once_and_verifies_offscreen_target(self):
        result, state, error = await self.run_capture("scroll-success", operation="scroll-to-visible", pid=None,
                                                       identifier="fixture-id")
        self.assertIsNone(error)
        self.assertEqual(result["scope"], "native-scroll-to-visible")
        self.assertTrue(result["nativeResult"])
        self.assertTrue(result["postconditionVerified"])
        self.assertFalse(result["before"]["visible"])
        self.assertEqual(result["before"]["frame"], {"x": 450, "y": 900, "width": 60, "height": 30})
        self.assertTrue(result["after"]["visible"])
        self.assertEqual(result["after"]["frame"], {"x": 100, "y": 100, "width": 60, "height": 30})
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["action_types"], [11])
        action = next(req for req in state["wire_requests"]
                      if req["requestType"] == 7 and req["actionType"] == 11)
        self.assertEqual((action["requestType"], action["actionType"]), (7, 11))
        self.assertIsNone(action["parameters"])
        self.assertEqual(action["translation"]["objectID"], 201)
        self.assertEqual(state["snapshot_reads"], 2)
        self.assertEqual(sum(1 for _, attrs in state["attribute_requests"] if attrs == [21, 25, 27, 32]), 2)
        action_index = state["requests"].index(7)
        self.assertEqual(state["requests"][:action_index].count(6), 3)
        self.assertNotIn("objectID", json.dumps({"before": result["before"], "after": result["after"]}))
        self.assertNotIn("pid", json.dumps({"before": result["before"], "after": result["after"]}))
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_scroll_false_with_error_zero_can_still_verify_postcondition_and_class_only(self):
        result, state, error = await self.run_capture("scroll-native-false", operation="scroll-to-visible",
                                                       identifier="fixture-id")
        self.assertIsNone(error)
        self.assertIs(result["nativeResult"], False)
        self.assertTrue(result["postconditionVerified"])
        self.assertEqual(state["action_submissions"], 1)
        self.assertEqual(state["action_types"], [11])
        self.assertEqual(state["action_reply_errors"], [0])

        result, state, error = await self.run_capture("scroll-success", operation="scroll-to-visible", pid=42,
                                                       identifier=None, class_name="UISearchBarTextField")
        self.assertIsNone(error)
        self.assertTrue(result["postconditionVerified"])
        self.assertEqual(result["selectors"], {"className": "UISearchBarTextField"})
        self.assertEqual(result["before"]["nativeAttributes"], {"5003": "UISearchBarTextField"})
        self.assertEqual(state["snapshot_reads"], 3)
        self.assertEqual(state["action_types"], [11])
        self.assertEqual(state["action_submissions"], 1)

        result, state, error = await self.run_capture("scroll-qualified-class-changed",
            operation="scroll-to-visible", pid=42, identifier=None, class_name="UIButton")
        self.assertIsNone(result)
        self.assertIn("selector changed", str(error))
        self.assertEqual(state["snapshot_reads"], 2)
        self.assertEqual(state["action_submissions"], 0)
        self.assertNotIn(7, state["requests"])

    async def test_scroll_preflight_failures_are_unsent_and_validate_selection(self):
        cases = (("snapshot-timeout", 42, "type=2"),
                 ("scroll-pre-disabled", 42, "not known enabled"),
                 ("scroll-pre-id-changed", 42, "identifier changed"),
                 ("root-identity-changed", 42, "application root identity changed"),
                 ("scroll-pid-changed", None, "displayed AX process changed"),
                 ("display-changed", None, "display changed"))
        for mode, pid, message in cases:
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="scroll-to-visible", pid=pid,
                                                              identifier="fixture-id")
                self.assertIsNone(result)
                self.assertIn(message, str(error))
                self.assertEqual(state["scroll_state"], "not-sent")
                self.assertEqual(state["action_submissions"], 0)
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = ipb_ax.report_failure(argparse.Namespace(operation="scroll-to-visible",
                                                                       scroll_state=state["scroll_state"]), error, 5)
                self.assertEqual(code, 5)
                self.assertNotIn("do not retry automatically", stderr.getvalue())

    async def test_scroll_postcondition_failures_emit_public_result_with_nonzero_main_status(self):
        for mode in ("scroll-post-missing", "scroll-post-ambiguous", "scroll-post-target-changed",
                     "scroll-post-hidden", "scroll-post-offscreen", "scroll-post-hit-other"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="scroll-to-visible", pid=42,
                                                              identifier="fixture-id")
                self.assertIsNone(error)
                self.assertEqual(result["status"], "postcondition_failed")
                self.assertFalse(result["postconditionVerified"])
                self.assertEqual(state["action_submissions"], 1)
                self.assertEqual(state["action_types"], [11])
                self.assertNotIn("objectID", json.dumps(result["before"]))
                if result["after"] is not None:
                    self.assertNotIn("objectID", json.dumps(result["after"]))

        result, _, error = await self.run_capture("scroll-post-hidden", operation="scroll-to-visible", pid=42,
                                                   identifier="fixture-id")
        self.assertIsNone(error)
        def fake_asyncio_run(coro):
            coro.close()
            return result
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ipb", "scroll-to-visible", "--identifier", "fixture-id",
                                 "--pid", "42", "--json"]), \
             patch.dict("os.environ", {"IPB_AX_DEVICE_ID": "fixture", "IPB_AX_UDID": "fixture"}), \
             patch.object(ipb_ax, "version", return_value="11.10.2"), \
             patch.object(ipb_ax.asyncio, "run", new=fake_asyncio_run), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = ipb_ax.main()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 6)
        self.assertEqual(payload["status"], "postcondition_failed")
        self.assertIn("postcondition is not verified", stderr.getvalue())

    async def test_scroll_submission_failures_keep_known_or_unknown_state_without_replay(self):
        cases = (("scroll-refused", "unknown", "AX request refused"),
                 ("scroll-timeout", "unknown", "timed out"),
                 ("scroll-post-snapshot-timeout", "true", "type=2"),
                 ("scroll-native-false-post-timeout", "false", "type=2"))
        for mode, expected_native, message in cases:
            result, state, error = await self.run_capture(mode, operation="scroll-to-visible", pid=42,
                                                          identifier="fixture-id")
            self.assertIsNone(result)
            self.assertIn(message, str(error))
            expected_state = {"true": "native-true", "false": "native-false", "unknown": "submitted"}[expected_native]
            self.assertEqual(state["scroll_state"], expected_state)
            self.assertEqual(state["action_submissions"], 1)
            self.assertEqual(state["action_types"], [11])
            self.assertEqual(state["requests"].count(7), 1)
            if mode == "scroll-refused":
                self.assertEqual(state["action_reply_errors"], [9])
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = ipb_ax.report_failure(argparse.Namespace(operation="scroll-to-visible",
                                                                   scroll_state=state["scroll_state"]), error, 5)
            self.assertEqual(code, 6)
            self.assertIn(f"native result {expected_native}", stderr.getvalue())
            self.assertIn("do not retry automatically", stderr.getvalue())

    async def test_wait_present_and_absent_use_fresh_native_snapshots_only(self):
        for mode, wait_for, expected_count in (("wait-present", "present", 1),
                                                ("wait-absent", "absent", 0)):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="wait", pid=42,
                                                              identifier="fixture-id", wait_for=wait_for,
                                                              timeout=1.0)
                self.assertIsNone(error)
                self.assertEqual(result["status"], "satisfied")
                self.assertEqual(result["waitFor"], wait_for)
                self.assertEqual(result["matchCount"], expected_count)
                self.assertGreaterEqual(state["snapshot_reads"], 2)
                self.assertEqual(state["requests"], [1] + [kind for _ in range(state["snapshot_reads"])
                                                            for kind in (2, 1)])
                self.assertNotIn(5, state["requests"])
                self.assertNotIn(7, state["requests"])
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_wait_timeout_is_finite_and_snapshot_errors_are_not_absence(self):
        result, state, error = await self.run_capture("wait-timeout", operation="wait", pid=42,
                                                       identifier="fixture-id", wait_for="present", timeout=0.01)
        self.assertIsNone(error)
        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(result["matchCount"], 0)
        self.assertGreaterEqual(state["snapshot_reads"], 1)
        self.assertEqual(state["requests"], [1] + [kind for _ in range(state["snapshot_reads"])
                                                    for kind in (2, 1)])
        self.assertTrue(state["closed"] and state["dtx_closed"])

        result, state, error = await self.run_capture("wait-snapshot-error", operation="wait", pid=42,
                                                       identifier="fixture-id", wait_for="absent", timeout=1.0)
        self.assertIsNone(result)
        self.assertIn("fixture native snapshot failed", str(error))
        self.assertEqual(state["snapshot_reads"], 1)
        self.assertTrue(state["closed"] and state["dtx_closed"])

    def test_wait_deadline_during_snapshot_emits_timeout_json_and_keeps_last_result(self):
        async def fake_run(args):
            result, state, error = await SessionTests().run_capture(
                "wait-deadline-during-snapshot", operation="wait", pid=args.pid,
                identifier=args.identifier, wait_for=args.wait_for, timeout=args.timeout)
            self.state = state
            if error:
                raise error
            return result

        async def no_sleep(_delay):
            return None

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ipb ui", "wait", "--pid", "42", "--identifier", "fixture-id",
                                "--wait-for", "present", "--timeout", "0.05", "--json"]), \
             patch.dict("os.environ", {"IPB_AX_DEVICE_ID": "fixture-device", "IPB_AX_UDID": "fixture-udid"}), \
             patch.object(ipb_ax, "version", return_value="11.10.2"), \
             patch.object(ipb_ax, "run", new=fake_run), \
             patch.object(ipb_ax.asyncio, "sleep", new=no_sleep), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = ipb_ax.main()

        self.assertEqual(code, 5)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "timed_out")
        self.assertEqual(payload["matchCount"], 0)
        self.assertTrue(payload["snapshotId"])
        self.assertEqual(self.state["snapshot_reads"], 2)
        self.assertEqual(stderr.getvalue(), "")

    def test_wait_read_timeout_is_reported_as_failure_not_overall_wait_timeout(self):
        async def fake_run(args):
            result, _, error = await SessionTests().run_capture(
                "snapshot-timeout", operation="wait", pid=args.pid,
                identifier=args.identifier, wait_for=args.wait_for, timeout=args.timeout)
            if error:
                raise error
            return result

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ipb ui", "wait", "--pid", "42", "--identifier", "fixture-id",
                                "--wait-for", "present", "--timeout", "1", "--json"]), \
             patch.dict("os.environ", {"IPB_AX_DEVICE_ID": "fixture-device", "IPB_AX_UDID": "fixture-udid"}), \
             patch.object(ipb_ax, "version", return_value="11.10.2"), \
             patch.object(ipb_ax, "run", new=fake_run), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = ipb_ax.main()

        self.assertEqual(code, 5)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("attribute=52 timed out", stderr.getvalue())

    async def test_wait_rejects_ambiguity_instead_of_treating_it_as_presence(self):
        result, state, error = await self.run_capture("wait-ambiguous", operation="wait", pid=42,
                                                       identifier="fixture-id", wait_for="present", timeout=1.0)
        self.assertIsNone(result)
        self.assertIn("ambiguous", str(error))
        self.assertEqual(state["snapshot_reads"], 1)
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_locate_and_wait_reject_root_pid_and_display_changes_after_snapshot(self):
        cases = (("root-identity-changed", 42, "application root identity changed"),
                 ("locate-pid-changed", None, "displayed AX process changed"),
                 ("display-changed", None, "display changed"))
        for operation in ("locate", "wait"):
            for mode, pid, message in cases:
                with self.subTest(operation=operation, mode=mode):
                    result, state, error = await self.run_capture(
                        mode, operation=operation, pid=pid, identifier="fixture-id",
                        wait_for="absent", timeout=0.5)
                    self.assertIsNone(result)
                    self.assertIn(message, str(error))
                    self.assertGreaterEqual(state["snapshot_reads"], 1)
                    self.assertNotIn(5, state["requests"])
                    self.assertNotIn(7, state["requests"])
                    self.assertTrue(state["closed"] and state["dtx_closed"])
                    after_snapshot = state["requests"].index(2)
                    self.assertTrue(any(kind == 1 for kind in state["requests"][after_snapshot + 1:]))
                    if pid is None:
                        self.assertGreater(state["requests"].count(6), 1)
                    if mode == "display-changed":
                        self.assertGreaterEqual(state["display_calls"], 2)

    async def test_cleanup_failures_never_return_a_capture(self):
        for mode in ("stop-error", "stop-timeout", "dtx-close-error", "socket-close-error"):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=True)
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertTrue(state["closed"])
                if mode != "socket-close-error":
                    self.assertTrue(state["dtx_closed"])

    async def test_ordinary_label_and_description_semantics_remain_separate(self):
        result, state, error = await self.run_capture("label-only", deep=False)
        self.assertIsNone(error)
        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["nodes"][1]["label"], "Actual label")
        self.assertEqual(result["nodes"][1]["description"], " ")
        self.assertIn((CHILD["objectID"], [3]), state["attribute_requests"])

    async def test_ordinary_label_timeout_still_fails_with_request_context(self):
        result, state, error = await self.run_capture("label-timeout", deep=False)
        self.assertIsNone(result)
        self.assertIsInstance(error, TimeoutError)
        self.assertRegex(str(error), r"type=5 pid=42 objectID=101 attributes=\[3\] timed out")
        self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_ordinary_missing_children_and_duplicate_child_still_fail(self):
        for mode, message in (("missing", "children unavailable"), ("duplicate", "repeats an element")):
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, deep=False)
                self.assertIsNone(result)
                self.assertIn(message, str(error))
                self.assertTrue(state["closed"] and state["dtx_closed"])

    async def test_stop_failure_still_closes_transport(self):
        result, state, error = await self.run_capture("stop-error", deep=False)
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

    async def test_qualified_press_revalidates_native_selectors_in_a_second_snapshot(self):
        result, state, error = await self.run_capture("action-repeat-same-handle", operation="press",
                                                       label="Fixture", value="Ready")
        self.assertIsNone(error)
        self.assertTrue(result["action"]["nativeAccepted"])
        self.assertEqual(state["requests"], [6, 1, 2, 2, 5, 6, 6, 7])
        self.assertEqual(state["snapshot_reads"], 2)
        self.assertEqual(state["action_submissions"], 1)

        result, state, error = await self.run_capture("qualified-target-changed", operation="press",
                                                       label="Fixture")
        self.assertIsNone(result)
        self.assertIn("selector matches=0", str(error))
        self.assertEqual(state["requests"], [6, 1, 2, 2])
        self.assertEqual(state["action_submissions"], 0)
        self.assertNotIn(7, state["requests"])

    async def test_label_or_value_only_press_confirms_native_identifier_when_available(self):
        cases = (("label-only-press", {"label": "Fixture"}),
                 ("value-only-press", {"value": "Ready"}))
        for mode, selectors in cases:
            with self.subTest(mode=mode):
                result, state, error = await self.run_capture(mode, operation="press", identifier=None,
                                                              **selectors)
                self.assertIsNone(error)
                self.assertTrue(result["action"]["nativeAccepted"])
                self.assertNotIn("identifier", result["action"])
                self.assertEqual(result["action"]["selectors"], selectors)
                self.assertEqual(state["requests"], [6, 1, 2, 2, 5, 6, 6, 7])
                self.assertEqual(state["wire_requests"][4]["parameters"]["attributes"], [21, 25, 27, 32])
                self.assertEqual(state["action_submissions"], 1)

        result, state, error = await self.run_capture("qualified-id-changed", operation="press",
                                                       identifier=None, label="Fixture")
        self.assertIsNone(result)
        self.assertIn("identifier changed", str(error))
        self.assertEqual(state["requests"], [6, 1, 2, 2, 5])
        self.assertEqual(state["action_submissions"], 0)
        self.assertNotIn(7, state["requests"])

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


class InputChildLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def write_executable(self, directory, name, source):
        path = Path(directory) / name
        path.write_text(f"#!{sys.executable}\n" + source)
        path.chmod(0o700)
        return str(path)

    async def wait_for_pids(self, path):
        deadline = asyncio.get_running_loop().time() + 3
        while asyncio.get_running_loop().time() < deadline:
            try:
                values = Path(path).read_text().strip().split()
                if len(values) == 2:
                    return [int(value) for value in values]
            except FileNotFoundError:
                pass
            await asyncio.sleep(0.02)
        self.fail("temporary input child did not record its process IDs")

    async def wait_until_gone(self, pid):
        deadline = asyncio.get_running_loop().time() + 3
        while asyncio.get_running_loop().time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            await asyncio.sleep(0.03)
        self.fail(f"owned process {pid} remained after input child cleanup")

    async def test_real_input_child_returns_success_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory(prefix="ipb-ax-input-exit-") as directory:
            for name, code in (("success", 0), ("failure", 19)):
                with self.subTest(code=code):
                    executable = self.write_executable(
                        directory, name,
                        f"import sys\nprint('fixture stdout')\nsys.exit({code})\n")
                    result = await ipb_ax.run_input_child(executable, "fixture-device", "literal text")
                    self.assertEqual(result, code)

    async def test_cancelling_real_child_terminates_its_owned_process_group_and_reaps_leader(self):
        with tempfile.TemporaryDirectory(prefix="ipb-ax-input-cancel-") as directory:
            pids_file = Path(directory) / "pids"
            source = (
                "import os, signal, subprocess, sys, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "child = subprocess.Popen([sys.executable, '-c', "
                "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])\n"
                f"open({str(pids_file)!r}, 'w').write(str(os.getpid()) + ' ' + str(child.pid))\n"
                "while True: time.sleep(1)\n"
            )
            executable = self.write_executable(directory, "long-running", source)
            task = asyncio.create_task(ipb_ax.run_input_child(executable, "fixture-device", "literal text"))
            leader, descendant = await self.wait_for_pids(pids_file)
            started = asyncio.get_running_loop().time()
            try:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=3)
                self.assertLess(asyncio.get_running_loop().time() - started, 2.5)
                await self.wait_until_gone(leader)
                await self.wait_until_gone(descendant)
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=3)
                    except (asyncio.CancelledError, TimeoutError):
                        pass
                # The group ID is the PID of this helper's own fresh session.
                # This is only a safety net for the temporary processes created above.
                try:
                    os.killpg(leader, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
