"""Bounded Foundation keyed archives for the captured DevicesApp AXP protocol.

Wire fields/IDs are documented in docs/protocol.md. No Apple class is instantiated.
"""
import math
import plistlib
import re
import secrets

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_NESTING = 512
MAX_DECODE_STEPS = 500000


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
    pending = [("value", archive["$top"]["root"], 0)]
    values = []
    steps = 0
    while pending:
        operation, obj, depth = pending.pop()
        steps += 1
        if steps > MAX_DECODE_STEPS:
            raise ValueError("AX archive work limit")
        if depth > MAX_ARCHIVE_NESTING:
            raise ValueError("AX archive nesting limit")
        if operation == "reference":
            visiting.remove(obj)
            memo[obj] = values[-1]
            continue
        if operation in ("list", "dict"):
            count = obj if operation == "list" else len(obj)
            decoded = values[-count:] if count else []
            if count:
                del values[-count:]
            if operation == "list":
                values.append(decoded)
                continue
            fields = dict(zip(obj, decoded))
            class_info = fields.pop("$class", {})
            if not isinstance(class_info, dict):
                raise ValueError("invalid AX class reference")
            class_name = class_info.get("$classname")
            if "NS.keys" in fields:
                keys, vals = fields["NS.keys"], fields.get("NS.objects")
                if not isinstance(keys, list) or not isinstance(vals, list) or len(keys) != len(vals):
                    raise ValueError("AX dictionary length mismatch")
                result = dict(zip(keys, vals))
            elif class_name in ("NSArray", "NSMutableArray"):
                result = fields["NS.objects"]
                if not isinstance(result, list):
                    raise ValueError("invalid AX array")
            elif class_name in ("NSString", "NSMutableString", "NSAttributedString", "NSMutableAttributedString"):
                result = fields.get("NSString", fields.get("NS.string", fields))
            elif class_name == "NSValue" and "NS.rectval" in fields:
                nums = [float(n) for n in re.findall(r"[-+]?(?:\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|inf|nan)", fields["NS.rectval"], re.I)]
                if len(nums) != 4 or (nums != [math.inf, math.inf, 0.0, 0.0] and not all(math.isfinite(n) for n in nums)):
                    raise ValueError("invalid AX rectangle")
                result = ({"unavailable": "CGRectNull"} if nums == [math.inf, math.inf, 0.0, 0.0]
                          else dict(zip(("x", "y", "width", "height"), nums)))
            else:
                result = fields
            values.append(result)
        elif isinstance(obj, plistlib.UID):
            index = obj.data
            if index in memo:
                values.append(memo[index])
                continue
            if index in visiting or not 0 <= index < len(objects):
                raise ValueError("cyclic or invalid AX reference")
            visiting.add(index)
            pending.extend([("reference", index, depth), ("value", objects[index], depth + 1)])
        elif isinstance(obj, (dict, list)):
            pending.append(("dict" if isinstance(obj, dict) else "list", list(obj) if isinstance(obj, dict) else len(obj), depth))
            pending.extend(("value", val, depth + 1) for val in reversed(list(obj.values()) if isinstance(obj, dict) else obj))
        else:
            values.append(obj)
    return values[0]


def request(kind, parameters, *, translation=None, action=0):
    """Encode proven reads and one native element press; never replay an action."""
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
    if kind not in (1, 2, 5, 6, 7):
        raise ValueError("unverified AX request type")
    if kind == 2 and translation is None:
        raise ValueError("AX snapshot requires an element")
    if kind == 7 and (translation is None or type(action) is not int or action != 5):
        raise ValueError("AX press requires an element and action 5")
    if kind != 7 and action != 0:
        raise ValueError("AX read cannot carry an action")
    root = add({"requestType": kind, "clientType": 0, "actionType": action, "attributeType": 52 if kind == 2 else 0,
                "translation": token, "parameters": params, "$class": cls("AXPTranslatorRequest")})
    return plistlib.dumps({"$version": 100000, "$archiver": "NSKeyedArchiver",
                          "$top": {"root": root}, "$objects": objects}, fmt=plistlib.FMT_BINARY)
