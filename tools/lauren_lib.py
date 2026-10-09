"""Shared helpers for loading the schemas and the effect/transition/animation library."""

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
LIBRARY_DIR = ROOT / "library"

# Library folder for each item kind.
KIND_DIRS = {"effect": "effects", "transition": "transitions", "animation": "animations"}


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
            if errors:
                raise ValueError(f"{path.relative_to(ROOT)}: " + "; ".join(errors))
            library[kind][item["id"]] = item
    return library
