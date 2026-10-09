"""Shared helpers for loading the schemas and the library (effects, transitions, animations, ramps, text styles)."""

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
LIBRARY_DIR = ROOT / "library"

# Library folder for each item kind.
KIND_DIRS = {
    "effect": "effects",
    "transition": "transitions",
    "animation": "animations",
    "ramp": "ramps",
    "text_style": "text_styles",
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_library(library_dir=LIBRARY_DIR):
    """Return {kind: {id: manifest}}, raising ValueError on an invalid manifest."""
    item_schema = load_json(SCHEMA_DIR / "library-item.schema.json")
    validator = jsonschema.Draft202012Validator(item_schema)
    library = {kind: {} for kind in KIND_DIRS}
    for kind, folder in KIND_DIRS.items():
        for path in sorted((Path(library_dir) / folder).glob("*.json")):
            item = load_json(path)
            errors = [e.message for e in validator.iter_errors(item)]
            if item.get("kind") != kind:
                errors.append(f"kind is {item.get('kind')!r} but file is in {folder}/")
            if item.get("id") != path.stem:
                errors.append(f"id {item.get('id')!r} does not match file name")
            jsonschema.Draft202012Validator.check_schema(item.get("params_schema", {}))
            for name, prop in item.get("params_schema", {}).get("properties", {}).items():
                for field in ("default", "description"):
                    if field not in prop:
                        errors.append(f"param {name!r} has no {field}")
            if kind == "ramp" and not errors:
                errors += check_ramp_points(item)
            if kind == "text_style" and not errors:
                style_keys = item_schema["properties"]["style"]["properties"]
                for name in item["params_schema"].get("properties", {}):
                    if name not in style_keys:
                        errors.append(f"param {name!r} is not a style key")
            if errors:
                raise ValueError(f"{path.relative_to(ROOT)}: " + "; ".join(errors))
            library[kind][item["id"]] = item
    return library


def check_ramp_points(item):
    """Expand a ramp preset with its defaults and check the result is a usable ramp."""
    from ramps import evaluate, preset_params

    params = preset_params(item, {})
    try:
        points = [(evaluate(p["offset"], params), evaluate(p["speed"], params)) for p in item["points"]]
    except (ValueError, SyntaxError) as e:
        return [str(e)]
    errors = []
    if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        errors.append("point offsets must increase with default params")
    if any(not 0.05 <= speed <= 16 for _, speed in points):
        errors.append("point speeds must be within 0.05-16x with default params")
    return errors
