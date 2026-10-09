"""Validate an edit plan against the schema, the library, and the rules the schema cannot express.

Usage: python tools/validate_plan.py PLAN.json [PLAN.json ...]

Exits non-zero if any plan has errors. Warnings are printed but do not fail.
"""

import sys

import jsonschema

from lauren_lib import SCHEMA_DIR, load_json, load_library
from ramps import expand_preset
from timing import layout, source_to_clip_time

EPSILON = 1e-6
SPEED_RANGE = (0.05, 16)
ITEM_COLLECTIONS = ("assets", "clips", "overlays", "texts", "captions", "audio")
CLIP_KINDS = {"video", "image"}
OVERLAY_KINDS = {"image", "sticker"}


def check_library_ref(item, kind, where, library, errors):
    """Check a {ref, duration, params} object against its library manifest."""
    manifest = library[kind].get(item["ref"])
    if manifest is None:
        errors.append(f"{where}: unknown {kind} {item['ref']!r}")
        return None
    params_validator = jsonschema.Draft202012Validator(manifest["params_schema"])
    for e in params_validator.iter_errors(item.get("params", {})):
        errors.append(f"{where}: params: {e.message}")
    limits = manifest.get("duration", {})
    duration = item.get("duration", limits.get("default"))
    if duration is not None:
        if "min" in limits and duration < limits["min"] - EPSILON:
            errors.append(f"{where}: duration {duration} below minimum {limits['min']}")
        if "max" in limits and duration > limits["max"] + EPSILON:
            errors.append(f"{where}: duration {duration} above maximum {limits['max']}")
    return manifest


def in_source(clip, s, where, errors):
    if not clip["in"] - EPSILON <= s <= clip["out"] + EPSILON:
        errors.append(f"{where}: source time {s} is outside the clip ({clip['in']}-{clip['out']})")
        return False
    return True


def validate(plan, library):
    errors, warnings = [], []

    ids = [x["id"] for key in ITEM_COLLECTIONS for x in plan.get(key, [])]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate id {dup!r}")

    assets = {a["id"]: a for a in plan["assets"]}
    clips = {c["id"]: c for c in plan["clips"]}

    def asset_for(item, allowed, where):
        asset = assets.get(item["asset"])
        if asset is None:
            errors.append(f"{where}: unknown asset {item['asset']!r}")
        elif asset["kind"] not in allowed:
            errors.append(f"{where}: asset {asset['id']!r} is {asset['kind']}, expected {sorted(allowed)}")
            asset = None
        return asset

    # Clips: source ranges and speed data. Timing can only be computed once these are sound.
    # `resolved` holds the clips with any speed_preset expanded into speed_ramp points.
    resolved = []
    timing_ok = True
    for clip in plan["clips"]:
        where = f"clip {clip['id']}"
        asset = asset_for(clip, CLIP_KINDS, where)
        if clip["out"] <= clip["in"]:
            errors.append(f"{where}: out must be greater than in")
            timing_ok = False
            resolved.append(clip)
            continue
        if asset and asset["kind"] == "video" and "duration" in asset and clip["out"] > asset["duration"] + EPSILON:
            errors.append(f"{where}: out {clip['out']} is past the end of asset {asset['id']} ({asset['duration']})")
        modes = [k for k in ("speed", "speed_ramp", "speed_preset") if k in clip]
        if len(modes) > 1:
            errors.append(f"{where}: use only one of {', '.join(modes)}")
        preset = clip.get("speed_preset")
        if preset:
            pwhere = f"{where} speed_preset"
            manifest = check_library_ref(preset, "ramp", pwhere, library, errors)
            if not manifest or not in_source(clip, preset["at"], pwhere, errors):
                timing_ok = False
                continue
            ramp = expand_preset(preset, manifest)
            if any(not clip["in"] <= p["at"] <= clip["out"] for p in ramp):
                warnings.append(f"{pwhere}: {preset['ref']!r} at {preset['at']} extends past the clip's in/out; the ramp is cut off there")
            if any(not SPEED_RANGE[0] <= p["speed"] <= SPEED_RANGE[1] for p in ramp):
                errors.append(f"{pwhere}: params give a speed outside {SPEED_RANGE[0]}-{SPEED_RANGE[1]}x")
                timing_ok = False
            clip = {k: v for k, v in clip.items() if k != "speed_preset"} | {"speed_ramp": ramp}
        else:
            ramp = clip.get("speed_ramp", [])
            for point in ramp:
                in_source(clip, point["at"], f"{where} speed_ramp", errors)
        for a, b in zip(ramp, ramp[1:]):
            if b["at"] <= a["at"]:
                errors.append(f"{where}: speed_ramp points must be in increasing source time")
                timing_ok = False
        resolved.append(clip)
        for freeze in clip.get("freezes", []):
            in_source(clip, freeze["at"], f"{where} freeze", errors)
        for kf in clip.get("transform", []):
            in_source(clip, kf["at"], f"{where} transform", errors)

    # Transitions decide how much clips overlap on the timeline.
    overlaps = {}
    for i, clip in enumerate(plan["clips"]):
        transition = clip.get("transition_in")
        if not transition or i == 0:
            continue
        manifest = check_library_ref(transition, "transition", f"clip {clip['id']} transition_in", library, errors)
        duration = transition.get("duration", (manifest or {}).get("duration", {}).get("default", 0))
        overlaps[clip["id"]] = (duration, bool(manifest and manifest.get("overlap")))

    if not timing_ok:
        return errors, warnings, None

    overlap_by = {clip_id: duration for clip_id, (duration, overlap) in overlaps.items() if overlap}
    clips = {c["id"]: c for c in resolved}
    positions, timeline = layout({"clips": resolved}, lambda clip: overlap_by.get(clip["id"], 0))

    prev = None
    for clip in resolved:
        where = f"clip {clip['id']}"
        _, length = positions[clip["id"]]
        if clip["id"] in overlaps and prev is not None:
            duration = overlaps[clip["id"]][0]
            if duration > min(length, positions[prev][1]) + EPSILON:
                errors.append(f"{where} transition_in: duration {duration} is longer than a neighbouring clip")
        for j, effect in enumerate(clip.get("effects", [])):
            ewhere = f"{where} effect {j}"
            manifest = check_library_ref(effect, "effect", ewhere, library, errors)
            at = effect.get("at", clip["in"])
            if not in_source(clip, at, ewhere, errors):
                continue
            duration = effect.get("duration", (manifest or {}).get("duration", {}).get("default"))
            if duration is not None and source_to_clip_time(clip, at) + duration > length + EPSILON:
                errors.append(f"{ewhere}: runs past the clip's end ({length:.3f}s)")
        prev = clip["id"]

    def placement(item, where):
        """Timeline start of an overlay or audio item, or None if its anchor is invalid."""
        if ("start" in item) == ("anchor" in item):
            if "anchor" in item or where.startswith("overlay"):
                errors.append(f"{where}: use exactly one of start or anchor")
                return None
            return 0.0
        if "start" in item:
            return item["start"]
        clip = clips.get(item["anchor"]["clip"])
        if clip is None:
            errors.append(f"{where}: anchor refers to unknown clip {item['anchor']['clip']!r}")
            return None
        if not in_source(clip, item["anchor"]["at"], f"{where} anchor", errors):
            return None
        return positions[clip["id"]][0] + source_to_clip_time(clip, item["anchor"]["at"])

    def check_animations(item, where, target):
        for slot in ("in", "out", "loop"):
            animation = item.get(f"animation_{slot}")
            if not animation:
                continue
            awhere = f"{where} animation_{slot}"
            manifest = check_library_ref(animation, "animation", awhere, library, errors)
            if not manifest:
                continue
            if slot not in manifest.get("slots", ["in", "out"]):
                errors.append(f"{awhere}: {animation['ref']!r} cannot be used as a {slot} animation")
            if target not in manifest.get("applies_to", ["image", "text"]):
                errors.append(f"{awhere}: {animation['ref']!r} does not apply to {target}")

    for key, target in (("overlays", "image"), ("texts", "text")):
        for item in plan.get(key, []):
            where = f"{key[:-1]} {item['id']}"
            if key == "overlays":
                asset_for(item, OVERLAY_KINDS, where)
            else:
                check_library_ref(item["style"], "text_style", f"{where} style", library, errors)
            check_animations(item, where, target)
            start = placement(item, where)
            if start is not None and start + item["duration"] > timeline + EPSILON:
                errors.append(f"{where}: ends at {start + item['duration']:.3f}s after the timeline ends ({timeline:.3f}s)")

    for item in plan.get("captions", []):
        where = f"caption {item['id']}"
        check_library_ref(item["style"], "text_style", f"{where} style", library, errors)
        check_animations(item, where, "text")
        clip = clips.get(item["clip"])
        if clip is None:
            errors.append(f"{where}: unknown clip {item['clip']!r}")
            continue
        if clip.get("reverse"):
            errors.append(f"{where}: clip {clip['id']} plays in reverse and cannot be captioned")
        words = item["words"]
        for w in words:
            if w["end"] <= w["at"]:
                errors.append(f"{where}: word {w['text']!r} ends before it starts")
        if any(b["at"] < a["at"] for a, b in zip(words, words[1:])):
            errors.append(f"{where}: words must be in spoken order")
        hidden = [w["text"] for w in words if w["at"] < clip["in"] - EPSILON or w["end"] > clip["out"] + EPSILON]
        if len(hidden) == len(words):
            errors.append(f"{where}: no words fall inside clip {clip['id']} ({clip['in']}-{clip['out']})")
        elif hidden:
            warnings.append(f"{where}: {len(hidden)} word(s) fall outside clip {clip['id']} and are not shown")

    for item in plan.get("audio", []):
        where = f"audio {item['id']}"
        asset = asset_for(item, {"audio"}, where)
        start = placement(item, where)
        if start is None:
            continue
        duration = item.get("duration", timeline - start)
        if start + duration > timeline + EPSILON:
            errors.append(f"{where}: ends at {start + duration:.3f}s after the timeline ends ({timeline:.3f}s)")
        if asset and "duration" in asset and not item.get("loop"):
            available = asset["duration"] - item.get("source_in", 0)
            if duration > available + EPSILON:
                warnings.append(f"{where}: track ends {duration - available:.2f}s before its slot does (set loop to repeat it)")

    return errors, warnings, timeline


def main(paths):
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_DIR / "edit-plan.schema.json"))
    library = load_library()
    failed = False
    for path in paths:
        plan = load_json(path)
        schema_errors = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in validator.iter_errors(plan)]
        if schema_errors:
            errors, warnings, timeline = schema_errors, [], None
        else:
            errors, warnings, timeline = validate(plan, library)
        if errors:
            failed = True
            print(f"{path}: INVALID")
        else:
            print(f"{path}: valid ({timeline:.2f}s)")
        for e in errors:
            print(f"  - error: {e}")
        for w in warnings:
            print(f"  - warning: {w}")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip())
    sys.exit(main(sys.argv[1:]))
