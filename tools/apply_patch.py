"""Apply an edit response (patch or full plan) to an edit plan.

Usage: python tools/apply_patch.py PLAN.json RESPONSE.json [-o NEW_PLAN.json]

The result is validated like any plan; the exit status is non-zero if the
response is malformed or the resulting plan is invalid.
"""

import argparse
import copy
import json
import sys

import jsonschema

from lauren_lib import SCHEMA_DIR, load_json, load_library
from validate_plan import validate

# Collections the AI may change. Assets belong to the app.
EDITABLE = ("clips", "overlays", "texts", "captions", "audio")


class PatchError(ValueError):
    pass


def merge_patch(target, patch):
    """RFC 7396 JSON merge patch: merge objects, replace everything else, null deletes.

    One exception: a library reference ({"ref": ...}) that names a different
    item replaces the old one instead of merging, so the previous item's
    params do not leak into the new one.
    """
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    if isinstance(target, dict) and "ref" in patch and patch["ref"] != target.get("ref"):
        target = None
    result = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def _find(plan, item_id):
    """Return (collection name, index) of the item with this id."""
    for name in EDITABLE:
        for i, item in enumerate(plan.get(name, [])):
            if item["id"] == item_id:
                return name, i
    if any(a["id"] == item_id for a in plan.get("assets", [])):
        raise PatchError(f"{item_id!r} is an asset; assets cannot be changed by the AI")
    raise PatchError(f"no item with id {item_id!r}")


def _insert(items, item, op):
    if "after" not in op:
        items.append(item)
    elif op["after"] is None:
        items.insert(0, item)
    else:
        index = next((i for i, x in enumerate(items) if x["id"] == op["after"]), None)
        if index is None:
            raise PatchError(f"'after' refers to {op['after']!r}, which is not in the same collection")
        items.insert(index + 1, item)


def apply_ops(plan, ops):
    plan = copy.deepcopy(plan)
    for n, op in enumerate(ops):
        try:
            kind = op["op"]
            if kind == "add":
                if op.get("to") not in EDITABLE or "item" not in op:
                    raise PatchError("add needs 'to' (an editable collection) and 'item'")
                new_id = op["item"].get("id")
                if new_id is None:
                    raise PatchError("added item has no id")
                existing = {x["id"] for key in EDITABLE + ("assets",) for x in plan.get(key, [])}
                if new_id in existing:
                    raise PatchError(f"id {new_id!r} already exists")
                _insert(plan.setdefault(op["to"], []), copy.deepcopy(op["item"]), op)
            elif kind == "update":
                if "set" not in op:
                    raise PatchError("update needs 'set'")
                if op.get("id") == "output":
                    plan["output"] = merge_patch(plan["output"], op["set"])
                    continue
                if "id" in op["set"]:
                    raise PatchError("update cannot change an item's id")
                name, i = _find(plan, op["id"])
                plan[name][i] = merge_patch(plan[name][i], op["set"])
            elif kind == "remove":
                name, i = _find(plan, op["id"])
                del plan[name][i]
            elif kind == "move":
                name, i = _find(plan, op["id"])
                item = plan[name].pop(i)
                _insert(plan[name], item, op)
            else:
                raise PatchError(f"unknown op {kind!r}")
        except PatchError as e:
            raise PatchError(f"op {n} ({op.get('op')} {op.get('id') or op.get('to', '')}): {e}") from None
    return plan


def apply_response(plan, response):
    """Return the new plan for an edit response. Raises PatchError or jsonschema.ValidationError."""
    jsonschema.validate(response, load_json(SCHEMA_DIR / "edit-response.schema.json"))
    if response["mode"] == "full":
        new_plan = copy.deepcopy(response["plan"])
    else:
        new_plan = apply_ops(plan, response["ops"])
    new_plan["summary"] = response["summary"]
    return new_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan")
    parser.add_argument("response")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    try:
        new_plan = apply_response(load_json(args.plan), load_json(args.response))
    except (PatchError, jsonschema.ValidationError) as e:
        print(f"cannot apply response: {getattr(e, 'message', e)}", file=sys.stderr)
        return 1

    plan_validator = jsonschema.Draft202012Validator(load_json(SCHEMA_DIR / "edit-plan.schema.json"))
    schema_errors = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in plan_validator.iter_errors(new_plan)]
    errors, warnings, timeline = (schema_errors, [], None) if schema_errors else validate(new_plan, load_library())
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    text = json.dumps(new_plan, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"applied: {timeline:.2f}s -> {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
