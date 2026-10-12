"""Bounded Foundation keyed archives for the captured DevicesApp AXP protocol.

Wire fields/IDs are documented in docs/protocol.md. No Apple class is instantiated.
"""
import math
import plistlib
import re
import secrets

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024


def decode(data):
    if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("invalid AX archive size")
    archive = plistlib.loads(data)
    if archive.get("$archiver") != "NSKeyedArchiver":
        raise ValueError("not an AX keyed archive")
    objects = archive["$objects"]
    if not isinstance(objects, list) or len(objects) > 50000:
        raise ValueError("invalid AX object table")
    memo, visiting = {0: None}, set()

    def value(obj, depth=0):
        if depth > 100:
            raise ValueError("AX archive nesting limit")
        if isinstance(obj, plistlib.UID):
            index = obj.data
            if index in memo:
                return memo[index]
            if index in visiting or not 0 <= index < len(objects):
                raise ValueError("cyclic or invalid AX reference")
            visiting.add(index)
            result = value(objects[index], depth + 1)
            visiting.remove(index)
            memo[index] = result
            return result
        if isinstance(obj, list):
            return [value(item, depth + 1) for item in obj]
        if not isinstance(obj, dict):
            return obj
        class_name = None
        if "$class" in obj:
            class_name = value(obj["$class"], depth + 1).get("$classname")
        if "NS.keys" in obj:
            keys = value(obj["NS.keys"], depth + 1)
            vals = value(obj["NS.objects"], depth + 1)
            if len(keys) != len(vals):
                raise ValueError("AX dictionary length mismatch")
            return dict(zip(keys, vals))
        if class_name in ("NSArray", "NSMutableArray"):
            return value(obj["NS.objects"], depth + 1)
        if class_name in ("NSString", "NSMutableString", "NSAttributedString", "NSMutableAttributedString"):
            for key in ("NSString", "NS.string"):
                if key in obj:
                    return value(obj[key], depth + 1)
        if class_name == "NSValue" and "NS.rectval" in obj:
            text = value(obj["NS.rectval"], depth + 1)
            nums = [float(n) for n in re.findall(r"[-+]?(?:\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|inf|nan)", text, re.I)]
            if len(nums) != 4:
                raise ValueError("invalid AX rectangle")
            if nums == [math.inf, math.inf, 0.0, 0.0]:
                return {"unavailable": "CGRectNull"}
            if not all(math.isfinite(n) for n in nums):
                raise ValueError("invalid AX rectangle")
            return {"x": nums[0], "y": nums[1], "width": nums[2], "height": nums[3]}
        return {key: value(val, depth + 1) for key, val in obj.items() if key != "$class"}

    return value(archive["$top"]["root"])


def request(kind, parameters, *, translation=None):
    """Encode only the proven read requests (application, attributes and hit test)."""
    objects = ["$null"]
    classes = {}

    def add(obj):
        objects.append(obj)
        return plistlib.UID(len(objects) - 1)

    def cls(name):
        if name not in classes:
            classes[name] = add({"$classname": name, "$classes": [name, "NSObject"]})
        return classes[name]

    def encode(obj):
        if obj is None:
            return plistlib.UID(0)
        if isinstance(obj, dict):
            return add({"NS.keys": [encode(k) for k in obj], "NS.objects": [encode(v) for v in obj.values()], "$class": cls("NSDictionary")})
        if isinstance(obj, list):
            return add({"NS.objects": [encode(v) for v in obj], "$class": cls("NSArray")})
        return add(obj)

    def handle(obj):
        return add({**{k: encode(obj.get(k)) for k in ("rawElementData", "bridgeDelegateToken")},
                    "objectID": encode(obj.get("objectID", 0)),
                    **{k: obj.get(k, False if k in ("isApplicationElement", "didPopuldateAppInfo") else 0)
                       for k in ("pid", "isApplicationElement", "didPopuldateAppInfo")},
                    "$class": cls("AXPTranslationObject")})

    if kind == 6:
        x, y = parameters["point"]
        point = add({"NS.pointval": encode(f"{{{x}, {y}}}"), "NS.special": 1, "$class": cls("NSValue")})
        params = add({"NS.keys": [encode("point"), encode("displayId")],
                      "NS.objects": [point, encode(0)], "$class": cls("NSDictionary")})
        token = handle({"objectID": secrets.randbits(64)})
    else:
        params = encode(parameters)
        token = handle(translation) if translation is not None else plistlib.UID(0)
    if kind not in (1, 5, 6):
        raise ValueError("unverified AX request type")
    root = add({"requestType": kind, "clientType": 0, "actionType": 0, "attributeType": 0,
                "translation": token, "parameters": params, "$class": cls("AXPTranslatorRequest")})
    return plistlib.dumps({"$version": 100000, "$archiver": "NSKeyedArchiver",
                          "$top": {"root": root}, "$objects": objects}, fmt=plistlib.FMT_BINARY)
