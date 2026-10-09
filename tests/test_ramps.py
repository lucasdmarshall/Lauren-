import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from lauren_lib import load_library  # noqa: E402
from ramps import evaluate, expand_preset, resolve_speed  # noqa: E402
from timing import clip_duration  # noqa: E402


class EvaluateTest(unittest.TestCase):
    def test_numbers_and_expressions(self):
        self.assertEqual(evaluate(2, {}), 2.0)
        self.assertEqual(evaluate("-(before + ease)", {"before": 0.4, "ease": 0.3}), -0.7)
        self.assertEqual(evaluate("2 * fast / 4", {"fast": 3}), 1.5)

    def test_rejects_anything_else(self):
        for expr in ("__import__('os')", "fast ** 2", "missing + 1", "[1]"):
            with self.assertRaises(ValueError):
                evaluate(expr, {"fast": 1})


class PresetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()

    def test_hero_slowmo_expands_around_the_moment(self):
        manifest = self.library["ramp"]["hero_slowmo"]
        points = expand_preset({"ref": "hero_slowmo", "at": 4.2, "params": {"before": 0.2}}, manifest)
        self.assertEqual([round(p["at"], 6) for p in points], [3.7, 4.0, 4.7, 5.0])
        self.assertEqual([p["speed"] for p in points], [1.5, 0.3, 0.3, 1.5])

    def test_every_preset_expands_and_lengthens_or_shortens_a_clip(self):
        for ref in self.library["ramp"]:
            clip = {"id": "c", "asset": "v", "in": 0, "out": 10, "speed_preset": {"ref": ref, "at": 5}}
            resolved = resolve_speed(clip, self.library)
            self.assertNotIn("speed_preset", resolved)
            self.assertGreater(clip_duration(resolved), 0, ref)


if __name__ == "__main__":
    unittest.main()
