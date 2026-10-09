import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from apply_patch import PatchError, apply_ops, apply_response, merge_patch  # noqa: E402

PLAN = {
    "schema_version": "0.1",
    "output": {"aspect_ratio": "9:16", "resolution": "1080p", "fps": 30},
    "assets": [{"id": "v1", "kind": "video"}],
    "clips": [
        {"id": "c1", "asset": "v1", "in": 0, "out": 2, "transition_in": {"ref": "zoom", "params": {"x": 0.3}}},
        {"id": "c2", "asset": "v1", "in": 2, "out": 4},
        {"id": "c3", "asset": "v1", "in": 4, "out": 6},
    ],
}


def ids(plan, key="clips"):
    return [x["id"] for x in plan[key]]


class MergePatchTest(unittest.TestCase):
    def test_merges_objects_and_deletes_with_null(self):
        merged = merge_patch({"a": 1, "b": {"c": 2, "d": 3}}, {"a": None, "b": {"c": 5}})
        self.assertEqual(merged, {"b": {"c": 5, "d": 3}})

    def test_arrays_are_replaced(self):
        self.assertEqual(merge_patch({"a": [1, 2]}, {"a": [3]}), {"a": [3]})

    def test_new_library_ref_replaces_the_old_one(self):
        old = {"ref": "zoom", "params": {"x": 0.3}, "beat_sync": True}
        self.assertEqual(merge_patch(old, {"ref": "spin"}), {"ref": "spin"})
        # Same ref: params are merged as usual.
        self.assertEqual(merge_patch(old, {"ref": "zoom", "params": {"y": 0.1}})["params"], {"x": 0.3, "y": 0.1})


class OpsTest(unittest.TestCase):
    def test_add_positions(self):
        new = {"asset": "v1", "in": 0, "out": 1}
        plan = apply_ops(PLAN, [
            {"op": "add", "to": "clips", "item": {"id": "first", **new}, "after": None},
            {"op": "add", "to": "clips", "item": {"id": "mid", **new}, "after": "c1"},
            {"op": "add", "to": "clips", "item": {"id": "last", **new}},
        ])
        self.assertEqual(ids(plan), ["first", "c1", "mid", "c2", "c3", "last"])
        self.assertEqual(ids(PLAN), ["c1", "c2", "c3"], "input plan must not change")

    def test_update_move_remove(self):
        plan = apply_ops(PLAN, [
            {"op": "update", "id": "c2", "set": {"out": 3}},
            {"op": "move", "id": "c3", "after": None},
            {"op": "remove", "id": "c1"},
            {"op": "update", "id": "output", "set": {"aspect_ratio": "1:1"}},
        ])
        self.assertEqual(ids(plan), ["c3", "c2"])
        self.assertEqual(plan["clips"][1]["out"], 3)
        self.assertEqual(plan["output"]["aspect_ratio"], "1:1")

    def test_creates_missing_collection(self):
        text = {"id": "t1", "text": "hi", "start": 0, "duration": 1, "style": {"ref": "minimal"}}
        plan = apply_ops(PLAN, [{"op": "add", "to": "texts", "item": text}])
        self.assertEqual(ids(plan, "texts"), ["t1"])

    def test_errors(self):
        cases = [
            [{"op": "remove", "id": "nope"}],
            [{"op": "update", "id": "v1", "set": {"kind": "audio"}}],
            [{"op": "update", "id": "c1", "set": {"id": "c9"}}],
            [{"op": "add", "to": "clips", "item": {"id": "c2"}}],
            [{"op": "add", "to": "assets", "item": {"id": "v2"}}],
            [{"op": "move", "id": "c1", "after": "v1"}],
        ]
        for ops in cases:
            with self.assertRaises(PatchError, msg=ops):
                apply_ops(PLAN, ops)


class ResponseTest(unittest.TestCase):
    def test_patch_sets_summary(self):
        plan = apply_response(PLAN, {"mode": "patch", "summary": "Shorter.", "ops": [{"op": "remove", "id": "c3"}]})
        self.assertEqual(plan["summary"], "Shorter.")
        self.assertEqual(ids(plan), ["c1", "c2"])

    def test_full_replaces_plan(self):
        full = dict(PLAN, clips=[PLAN["clips"][0]])
        plan = apply_response(PLAN, {"mode": "full", "summary": "Rebuilt.", "plan": full})
        self.assertEqual(ids(plan), ["c1"])

    def test_mode_and_payload_must_match(self):
        import jsonschema
        with self.assertRaises(jsonschema.ValidationError):
            apply_response(PLAN, {"mode": "full", "summary": "x", "ops": []})


if __name__ == "__main__":
    unittest.main()
