"""Print the library catalog that is sent to the AI with each request.

Usage: python tools/build_catalog.py > catalog.json
"""

import json

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
            params = item["params_schema"].get("properties", {})
            if params:
                entry["params"] = params
            entries.append(entry)
        catalog[kind + "s"] = entries
    return catalog


if __name__ == "__main__":
    print(json.dumps(build_catalog(load_library()), indent=2))
