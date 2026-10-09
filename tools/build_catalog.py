"""Print the library catalog that is sent to the AI with each request.

Usage: python tools/build_catalog.py [--json] > catalog.txt

The default output is a compact text index, one line per item, which uses
roughly a third of the tokens of the JSON form. --json prints the full form.
"""

import json
import sys

from lauren_lib import load_library


def build_catalog(library):
    catalog = {}
    for kind, items in library.items():
        entries = []
        for item in items.values():
            entry = {"id": item["id"], "description": item["description"]}
            if item.get("tags"):
                entry["tags"] = item["tags"]
            if "duration" in item:
                entry["duration"] = item["duration"]
            if item.get("overlap"):
                entry["overlap"] = True
            if kind == "animation":
                entry["slots"] = item.get("slots", ["in", "out"])
            params = item["params_schema"].get("properties", {})
            if params:
                entry["params"] = params
            entries.append(entry)
        catalog[kind + "s"] = entries
    return catalog


def format_param(name, prop):
    """Render one parameter as name=default(range or options)."""
    if "enum" in prop:
        domain = "/".join(map(str, prop["enum"]))
    elif "minimum" in prop and "maximum" in prop:
        domain = f"{prop['minimum']:g}-{prop['maximum']:g}"
    elif "pattern" in prop and prop["pattern"].startswith("^#"):
        domain = "#rrggbb"
    else:
        domain = prop.get("type", "")
    default = prop["default"]
    if isinstance(default, bool):
        default = str(default).lower()
    elif isinstance(default, float):
        default = f"{default:g}"
    return f"{name}={default}({domain})"


def format_duration(duration):
    if not duration:
        return ""
    lo, hi = duration.get("min"), duration.get("max")
    if lo is not None and hi is not None:
        return f" {duration['default']:g}s[{lo:g}-{hi:g}]"
    return f" {duration['default']:g}s"


def build_compact_catalog(library):
    """One line per item: id [tags] duration flags: description | params."""
    sections = []
    for kind, items in library.items():
        lines = [f"## {kind}s"]
        for item in items.values():
            flags = ""
            if item.get("overlap"):
                flags = " overlap"
            if kind == "animation":
                flags = " " + "/".join(item.get("slots", ["in", "out"]))
            line = f"{item['id']} [{','.join(item.get('tags', []))}]{format_duration(item.get('duration'))}{flags}: {item['description']}"
            params = item["params_schema"].get("properties", {})
            if params:
                line += " | " + " ".join(format_param(n, p) for n, p in params.items())
            lines.append(line)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


if __name__ == "__main__":
    library = load_library()
    if "--json" in sys.argv[1:]:
        print(json.dumps(build_catalog(library), indent=2))
    else:
        print(build_compact_catalog(library))
