import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from timing import clip_duration, layout, source_to_clip_time  # noqa: E402


def clip(**kw):
    return {"id": "c", "asset": "v", "in": 0, "out": 4, **kw}


class TimingTest(unittest.TestCase):
    def test_constant_speed(self):
        self.assertAlmostEqual(clip_duration(clip()), 4)
        self.assertAlmostEqual(clip_duration(clip(speed=2)), 2)
        self.assertAlmostEqual(source_to_clip_time(clip(speed=0.5), 1), 2)

    def test_hold_ramp(self):
        # 2s at 1x, then 2s at 0.5x.
        ramp = [{"at": 0, "speed": 1, "easing": "hold"}, {"at": 2, "speed": 0.5}]
        self.assertAlmostEqual(clip_duration(clip(speed_ramp=ramp)), 2 + 4)

    def test_linear_ramp_matches_closed_form(self):
        ramp = [{"at": 0, "speed": 1, "easing": "linear"}, {"at": 4, "speed": 2}]
        self.assertAlmostEqual(clip_duration(clip(speed_ramp=ramp)), 4 * math.log(2))

    def test_smooth_ramp_is_between_its_speeds(self):
        ramp = [{"at": 0, "speed": 1}, {"at": 4, "speed": 0.25}]
        d = clip_duration(clip(speed_ramp=ramp))
        self.assertGreater(d, 4)
        self.assertLess(d, 16)
        # Symmetry: smoothstep 1 -> 0.25 takes as long as 0.25 -> 1.
        back = [{"at": 0, "speed": 0.25}, {"at": 4, "speed": 1}]
        self.assertAlmostEqual(d, clip_duration(clip(speed_ramp=back)), places=6)

    def test_speed_outside_ramp_points_holds(self):
        ramp = [{"at": 1, "speed": 2, "easing": "hold"}, {"at": 3, "speed": 0.5}]
        # 1s at 2x, 2s at 2x, 1s at 0.5x.
        self.assertAlmostEqual(clip_duration(clip(speed_ramp=ramp)), 0.5 + 1 + 2)

    def test_source_to_clip_time_is_monotonic_and_ends_at_duration(self):
        c = clip(speed_ramp=[{"at": 0.5, "speed": 1.5}, {"at": 2, "speed": 0.3}, {"at": 3, "speed": 1.5}])
        times = [source_to_clip_time(c, s / 10) for s in range(0, 41)]
        self.assertTrue(all(b > a for a, b in zip(times, times[1:])))
        self.assertAlmostEqual(times[-1], clip_duration(c))

    def test_freezes_add_time_after_their_frame(self):
        c = clip(freezes=[{"at": 2, "duration": 0.5}])
        self.assertAlmostEqual(clip_duration(c), 4.5)
        self.assertAlmostEqual(source_to_clip_time(c, 2), 2)
        self.assertAlmostEqual(source_to_clip_time(c, 3), 3.5)

    def test_reverse_plays_from_out_to_in(self):
        c = clip(reverse=True, speed=2)
        self.assertAlmostEqual(clip_duration(c), 2)
        self.assertAlmostEqual(source_to_clip_time(c, 4), 0)
        self.assertAlmostEqual(source_to_clip_time(c, 3), 0.5)
        self.assertAlmostEqual(source_to_clip_time(c, 0), 2)

    def test_reverse_with_ramp_and_freeze(self):
        ramp = [{"at": 0, "speed": 1, "easing": "hold"}, {"at": 2, "speed": 0.5}]
        c = clip(reverse=True, speed_ramp=ramp, freezes=[{"at": 3, "duration": 1}])
        # Backward: source 4 -> 2 at 0.5x takes 4s (with a 1s freeze at 3), then 2 -> 0 at 1x takes 2s.
        self.assertAlmostEqual(clip_duration(c), 7)
        self.assertAlmostEqual(source_to_clip_time(c, 3.5), 1)
        self.assertAlmostEqual(source_to_clip_time(c, 2), 5)
        forward = dict(c, reverse=False)
        self.assertAlmostEqual(clip_duration(forward), clip_duration(c))

    def test_layout_with_overlap(self):
        plan = {"clips": [clip(id="a"), clip(id="b"), clip(id="c")]}
        positions, total = layout(plan, lambda c: 1 if c["id"] == "b" else 0)
        self.assertEqual(positions["b"], (3, 4))
        self.assertAlmostEqual(total, 11)


if __name__ == "__main__":
    unittest.main()
