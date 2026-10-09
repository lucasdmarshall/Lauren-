"""Expand speed ramp presets (library/ramps) into explicit speed_ramp points.

Preset points use small arithmetic expressions over the preset's parameters,
e.g. "-(before + ease)". Only numbers, parameter names, + - * / and
parentheses are allowed.
"""

import ast
import operator

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def evaluate(expr, params):
    """Evaluate a number or an arithmetic expression string over `params`."""
    if isinstance(expr, (int, float)):
        return float(expr)

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in params:
                raise ValueError(f"unknown parameter {node.id!r} in {expr!r}")
            return float(params[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](walk(node.operand))
        raise ValueError(f"unsupported expression {expr!r}")

    return walk(ast.parse(expr, mode="eval"))


def preset_params(manifest, given):
    """Parameter values for a preset: manifest defaults overridden by `given`."""
    props = manifest["params_schema"].get("properties", {})
    return {name: given.get(name, prop["default"]) for name, prop in props.items()}


def expand_preset(preset, manifest):
    """Return speed_ramp points for a {ref, at, params} preset placed in a clip."""
    params = preset_params(manifest, preset.get("params", {}))
    points = []
    for point in manifest["points"]:
        expanded = {"at": preset["at"] + evaluate(point["offset"], params), "speed": evaluate(point["speed"], params)}
        if "easing" in point:
            expanded["easing"] = point["easing"]
        points.append(expanded)
    return points


def resolve_speed(clip, library):
    """Return the clip with any speed_preset replaced by explicit speed_ramp points."""
    preset = clip.get("speed_preset")
    if not preset:
        return clip
    resolved = {k: v for k, v in clip.items() if k != "speed_preset"}
    resolved["speed_ramp"] = expand_preset(preset, library["ramp"][preset["ref"]])
    return resolved
