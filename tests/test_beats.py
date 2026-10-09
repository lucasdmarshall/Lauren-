import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from beats import snap_to_beats  # noqa: E402
from lauren_lib import load_library  # noqa: E402
from timing import layout  # noqa: E402

try:
    import librosa  # noqa: F401
    import numpy as np
    import soundfile as sf
except ImportError:
    librosa = None


def plan_with(clips, beats, audio=None):
    return {
        "assets": [
            {"id": "v1", "kind": "video", "duration": 10},
            {"id": "m1", "kind": "audio", "duration": 60, "beats": beats},
        ],
        "clips": clips,
        "audio": [audio or {"id": "a1", "asset": "m1"}],
    }


def clip(id, start, end, sync=True, **kw):
    c = {"id": id, "asset": "v1", "in": start, "out": end, **kw}
    if sync:
        c["transition_in"] = {"ref": "flash", "beat_sync": True}
    return c


class SnapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()

    def cuts(self, plan):
        positions, _ = layout(plan, lambda c: 0)
        return [round(positions[c["id"]][0], 4) for c in plan["clips"][1:]]

    def test_moves_cuts_onto_nearby_beats(self):
        plan = plan_with([clip("c1", 0, 1, sync=False), clip("c2", 2, 3), clip("c3", 4, 5)], beats=[1.1, 2.2, 3.3])
        snapped = snap_to_beats(plan, self.library)
        self.assertEqual(self.cuts(snapped), [1.1, 2.2])
        self.assertEqual(snapped["clips"][0]["out"], 1.1)

    def test_leaves_cuts_far_from_beats_and_without_sync(self):
        plan = plan_with([clip("c1", 0, 1, sync=False), clip("c2", 2, 3, sync=False), clip("c3", 4, 5)], beats=[1.4, 2.6])
        snapped = snap_to_beats(plan, self.library)
        self.assertEqual(self.cuts(snapped), [1.0, 2.0])

    def test_accounts_for_speed_and_music_offset(self):
        plan = plan_with(
            [clip("c1", 0, 2, sync=False, speed=2), clip("c2", 2, 3)],
            beats=[5.2],
            audio={"id": "a1", "asset": "m1", "source_in": 4},
        )
        # Beat 5.2 in the track plays at 1.2s; c1 at 2x must gain 0.4s of source.
        snapped = snap_to_beats(plan, self.library)
        self.assertAlmostEqual(snapped["clips"][0]["out"], 2.4)

    def test_reverse_clip_extends_from_its_in(self):
        plan = plan_with([clip("c1", 3, 4, sync=False, reverse=True), clip("c2", 5, 6)], beats=[1.2])
        snapped = snap_to_beats(plan, self.library)
        self.assertAlmostEqual(snapped["clips"][0]["in"], 2.8)


@unittest.skipIf(librosa is None, "librosa not installed")
class AnalyzeTest(unittest.TestCase):
    def test_click_track_at_120_bpm(self):
        import tempfile

        from beats import analyze

        sr = 22050
        times = np.arange(0.5, 12, 0.5)
        y = librosa.clicks(times=times, sr=sr, length=sr * 12)
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            sf.write(f.name, y, sr)
            result = analyze(f.name)
        self.assertAlmostEqual(result["bpm"], 120, delta=3)
        gaps = np.diff(result["beats"])
        self.assertAlmostEqual(float(np.median(gaps)), 0.5, delta=0.03)
        self.assertTrue(set(result["downbeats"]) <= set(result["beats"]))


if __name__ == "__main__":
    unittest.main()
