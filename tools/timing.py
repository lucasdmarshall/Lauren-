"""Timeline maths for edit plans: speed ramps, freezes, and clip positions.

This is the reference implementation. The render engine must produce the
same numbers, so keep it small and deterministic.
"""

import math

SMOOTH_STEPS = 64  # Simpson's rule intervals for 'smooth' ramp segments (must be even).


def _smoothstep(u):
    return u * u * (3 - 2 * u)


def _speed_between(a, b, s):
    """Speed at source time s between ramp points a and b."""
    easing = a.get("easing", "smooth")
    if easing == "hold":
        return a["speed"]
    u = (s - a["at"]) / (b["at"] - a["at"])
    if easing == "smooth":
        u = _smoothstep(u)
    return a["speed"] + (b["speed"] - a["speed"]) * u


def _pieces(clip):
    """Yield (s0, s1, speed_fn, kind) covering the clip's source range [in, out]."""
    start, end = clip["in"], clip["out"]
    ramp = clip.get("speed_ramp")
    if not ramp:
        speed = clip.get("speed", 1)
        yield start, end, lambda s: speed, "hold"
        return
    first, last = ramp[0], ramp[-1]
    yield start, min(first["at"], end), lambda s: first["speed"], "hold"
    for a, b in zip(ramp, ramp[1:]):
        yield max(a["at"], start), min(b["at"], end), (lambda s, a=a, b=b: _speed_between(a, b, s)), a.get("easing", "smooth")
    yield max(last["at"], start), end, lambda s: last["speed"], "hold"


def _play_time(s0, s1, speed, kind):
    """Timeline seconds needed to play source range [s0, s1]: the integral of ds / speed(s)."""
    if s1 <= s0:
        return 0.0
    if kind == "hold":
        return (s1 - s0) / speed(s0)
    if kind == "linear":
        v0, v1 = speed(s0), speed(s1)
        if math.isclose(v0, v1):
            return (s1 - s0) / v0
        return (s1 - s0) * math.log(v1 / v0) / (v1 - v0)
    h = (s1 - s0) / SMOOTH_STEPS
    total = 1 / speed(s0) + 1 / speed(s1)
    for i in range(1, SMOOTH_STEPS):
        total += (4 if i % 2 else 2) / speed(s0 + i * h)
    return total * h / 3


def source_to_clip_time(clip, s):
    """Seconds from the clip's start on the timeline to where source time `s` is shown."""
    t = sum(_play_time(s0, min(s1, s), speed, kind) for s0, s1, speed, kind in _pieces(clip) if s0 < s)
    return t + sum(f["duration"] for f in clip.get("freezes", []) if f["at"] < s)


def clip_duration(clip):
    """Timeline length of a clip, including freezes."""
    t = sum(_play_time(s0, s1, speed, kind) for s0, s1, speed, kind in _pieces(clip))
    return t + sum(f["duration"] for f in clip.get("freezes", []))


def layout(plan, overlap_of):
    """Return ({clip_id: (start, length)}, timeline_length).

    `overlap_of(clip)` returns the seconds by which the clip's transition_in
    overlaps the previous clip (0 when it does not overlap).
    """
    positions = {}
    cursor = 0.0
    for i, clip in enumerate(plan["clips"]):
        if i > 0:
            cursor -= overlap_of(clip)
        length = clip_duration(clip)
        positions[clip["id"]] = (cursor, length)
        cursor += length
    return positions, cursor
