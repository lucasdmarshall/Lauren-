"""Validate an edit plan against the schema, the library, and the rules the schema cannot express.

Usage: python tools/validate_plan.py PLAN.json [PLAN.json ...]
"""

import sys

import jsonschema

from lauren_lib import SCHEMA_DIR, load_json, load_library

EPSILON = 1e-6
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


def validate(plan, library):
    errors = []

    ids = [x["id"] for key in ("assets", "clips", "overlays", "audio") for x in plan.get(key, [])]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate id {dup!r}")

    assets = {a["id"]: a for a in plan["assets"]}

    def asset_for(item, allowed, where):
        asset = assets.get(item["asset"])
        if asset is None:
            errors.append(f"{where}: unknown asset {item['asset']!r}")
        elif asset["kind"] not in allowed:
            errors.append(f"{where}: asset {asset['id']!r} is {asset['kind']}, expected {sorted(allowed)}")
            asset = None
        return asset

    # Main track: compute timeline length, accounting for overlapping transitions.
    timeline = 0.0
    prev_length = None
    for i, clip in enumerate(plan["clips"]):
        where = f"clip {clip['id']}"
        asset = asset_for(clip, CLIP_KINDS, where)
        if clip["out"] <= clip["in"]:
            errors.append(f"{where}: out must be greater than in")
        if asset and asset["kind"] == "video" and "duration" in asset and clip["out"] > asset["duration"] + EPSILON:
            errors.append(f"{where}: out {clip['out']} is past the end of asset {asset['id']} ({asset['duration']})")
        length = (clip["out"] - clip["in"]) / clip.get("speed", 1)

        for kf in clip.get("transform", []):
            if kf["t"] > length + EPSILON:
                errors.append(f"{where}: keyframe at {kf['t']} is past the clip's end ({length:.3f})")
        for j, effect in enumerate(clip.get("effects", [])):
            ewhere = f"{where} effect {j}"
            check_library_ref(effect, "effect", ewhere, library, errors)
            if effect.get("start", 0) + effect.get("duration", 0) > length + EPSILON:
                errors.append(f"{ewhere}: runs past the clip's end ({length:.3f})")

        transition = clip.get("transition_in")
        if transition and i > 0:
            twhere = f"{where} transition_in"
            manifest = check_library_ref(transition, "transition", twhere, library, errors)
            if manifest:
                duration = transition.get("duration", manifest.get("duration", {}).get("default", 0))
                if duration > min(length, prev_length) + EPSILON:
                    errors.append(f"{twhere}: duration {duration} is longer than a neighbouring clip")
                if manifest.get("overlap"):
                    timeline -= duration
        timeline += length
        prev_length = length

    for item in plan.get("overlays", []):
        where = f"overlay {item['id']}"
        asset_for(item, OVERLAY_KINDS, where)
        for slot in ("in", "out", "loop"):
            animation = item.get(f"animation_{slot}")
            if animation:
                awhere = f"{where} animation_{slot}"
                manifest = check_library_ref(animation, "animation", awhere, library, errors)
                if manifest and slot not in manifest.get("slots", ["in", "out"]):
                    errors.append(f"{awhere}: {animation['ref']!r} cannot be used as a {slot} animation")

    for item in plan.get("audio", []):
        where = f"audio {item['id']}"
        asset = asset_for(item, {"audio"}, where)
        if asset and "duration" in asset:
            needed = item.get("source_in", 0) + item["end"] - item["start"]
            if needed > asset["duration"] + EPSILON:
                errors.append(f"{where}: needs {needed:.3f}s of audio but asset has {asset['duration']}")

    for key in ("overlays", "audio"):
        for item in plan.get(key, []):
            where = f"{key[:-1] if key == 'overlays' else key} {item['id']}"
            if item["end"] <= item["start"]:
                errors.append(f"{where}: end must be greater than start")
            if item["end"] > timeline + EPSILON:
                errors.append(f"{where}: ends at {item['end']} after the timeline ends ({timeline:.3f})")

    return errors, timeline


def main(paths):
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_DIR / "edit-plan.schema.json"))
    library = load_library()
    failed = False
    for path in paths:
        plan = load_json(path)
        schema_errors = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in validator.iter_errors(plan)]
        if schema_errors:
            errors, timeline = schema_errors, None
        else:
            errors, timeline = validate(plan, library)
        if errors:
            failed = True
            print(f"{path}: INVALID")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"{path}: valid ({timeline:.2f}s)")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip())
    sys.exit(main(sys.argv[1:]))
