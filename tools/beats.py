"""Local beat analysis, and snapping beat_sync cuts onto music beats.

Usage:
  python tools/beats.py analyze AUDIO_FILE        # prints {bpm, beats, downbeats}
  python tools/beats.py snap PLAN.json [-o OUT]   # moves beat_sync cuts onto beats

Analysis needs librosa (pip install librosa). Snapping does not.

Snapping runs when a plan is saved, not during rendering: it rewrites clip
'in'/'out' so cuts land on beats, which keeps timing.py free of music
logic and makes the saved plan the exact edit that gets rendered.
"""

import argparse
import copy
import json
import sys

from lauren_lib import load_json, load_library
from ramps import resolve_speed
from timing import layout, source_to_clip_time

DEFAULT_TOLERANCE = 0.25  # seconds a cut may move to reach a beat
MIN_CLIP = 0.05           # shortest source range a snap may leave


def analyze(path):
    """Return {bpm, beats, downbeats} for an audio file, in seconds."""
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=22050, mono=True)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    beats = librosa.frames_to_time(frames, sr=sr)
    # Downbeats, assuming 4/4: the phase whose beats carry the most onset energy.
    downbeats = []
    if len(frames) >= 4:
        strength = [onset_env[frames[phase::4]].sum() for phase in range(4)]
        downbeats = beats[int(np.argmax(strength))::4]
    return {
        "bpm": round(float(np.atleast_1d(tempo)[0]), 2),
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": [round(float(b), 3) for b in downbeats],
    }


def _music_beats(plan, positions):
    """Timeline times of the beats of the first audio item whose asset has beats."""
    assets = {a["id"]: a for a in plan["assets"]}
    for item in plan.get("audio", []):
        asset = assets.get(item["asset"], {})
        if not asset.get("beats"):
            continue
        if "anchor" in item:
            clip_id = item["anchor"]["clip"]
            clip = next(c for c in plan["clips"] if c["id"] == clip_id)
            start = positions[clip_id][0] + source_to_clip_time(clip, item["anchor"]["at"])
        else:
            start = item.get("start", 0)
        source_in = item.get("source_in", 0)
        return [start + b - source_in for b in asset["beats"] if b >= source_in]
    return []


def _end_speed(clip):
    """Speed at the last frame the clip plays."""
    ramp = clip.get("speed_ramp")
    if not ramp:
        return clip.get("speed", 1)
    return (ramp[0] if clip.get("reverse") else ramp[-1])["speed"]


def snap_to_beats(plan, library, tolerance=DEFAULT_TOLERANCE):
    """Return a copy of the plan with every beat_sync cut moved onto the nearest beat.

    A cut moves only if a beat is within `tolerance` seconds. The previous
    clip is trimmed or extended to make the move, within its asset.
    """
    plan = copy.deepcopy(plan)
    assets = {a["id"]: a for a in plan["assets"]}

    def overlap_of(clip):
        t = clip.get("transition_in")
        if not t:
            return 0
        manifest = library["transition"].get(t["ref"], {})
        return t.get("duration", manifest.get("duration", {}).get("default", 0)) if manifest.get("overlap") else 0

    for i in range(1, len(plan["clips"])):
        clip = plan["clips"][i]
        if not (clip.get("transition_in") or {}).get("beat_sync"):
            continue
        resolved = {"clips": [resolve_speed(c, library) for c in plan["clips"]]}
        positions, _ = layout(resolved, overlap_of)
        beats = _music_beats(dict(plan, clips=resolved["clips"]), positions)
        if not beats:
            break
        cut = positions[clip["id"]][0] + overlap_of(clip) / 2
        beat = min(beats, key=lambda b: abs(b - cut))
        delta = beat - cut
        if abs(delta) > tolerance or abs(delta) < 1e-4:
            continue
        prev = plan["clips"][i - 1]
        source_delta = delta * _end_speed(resolved["clips"][i - 1])
        if prev.get("reverse"):
            prev["in"] = max(0.0, min(prev["in"] - source_delta, prev["out"] - MIN_CLIP))
        else:
            limit = assets.get(prev["asset"], {}).get("duration", float("inf"))
            prev["out"] = min(limit, max(prev["out"] + source_delta, prev["in"] + MIN_CLIP))
        for key in ("in", "out"):
            prev[key] = round(prev[key], 4)
    return plan


def main():
    parser = argparse.ArgumentParser(description="Beat analysis and beat snapping.")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("audio")
    s = sub.add_parser("snap")
    s.add_argument("plan")
    s.add_argument("-o", "--output")
    s.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = parser.parse_args()

    if args.command == "analyze":
        print(json.dumps(analyze(args.audio)))
        return 0
    snapped = snap_to_beats(load_json(args.plan), load_library(), args.tolerance)
    text = json.dumps(snapped, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
