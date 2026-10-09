# Lauren — Effect, Transition & Animation Library

> Status: Draft for the spike.

Nothing about individual effects, transitions or animations is hardcoded in the edit plan schema or the app. Each one is a **library item**: a JSON manifest in `library/`. The AI is shown the catalog of available items and decides which to use, where, and with what parameters.

```
library/
├── transitions/   cut, crossfade, whip, zoom, flash, salt (placeholder)
├── effects/       shake, blur, black_white
└── animations/    pop, fade, slide   (in/out animations for overlays)
```

Adding a new item means adding a manifest (and, later, its render code). No schema, prompt or app change is needed.

## Manifest

Schema: [`schema/library-item.schema.json`](../schema/library-item.schema.json)

```json
{
  "id": "whip",
  "kind": "transition",
  "name": "Whip pan",
  "description": "Fast motion-blurred pan ... High energy; works best on a beat.",
  "tags": ["energetic", "fast", "trendy"],
  "duration": { "default": 0.25, "min": 0.1, "max": 0.6 },
  "params_schema": {
    "type": "object",
    "properties": {
      "direction": { "enum": ["left", "right", "up", "down"], "default": "left", "description": "..." }
    }
  }
}
```

| Field | Purpose |
|---|---|
| `id` | What the edit plan references (`"ref": "whip"`). Must match the file name. |
| `kind` | `effect`, `transition` or `animation`. Must match the folder. |
| `description`, `tags` | Written for the AI. This is how it chooses between items, so describe the look **and when to use it**. |
| `duration` | Default and allowed range. |
| `overlap` | Transitions only: whether both clips are visible at once (the timeline gets shorter by the duration). |
| `params_schema` | JSON Schema for the item's parameters. Every parameter needs a `default` and a `description`. |
| `render` | How the engine draws it. Format still open (below). |

## How the pieces connect

1. `tools/build_catalog.py` turns the manifests into a compact catalog.
2. The catalog goes into the AI request alongside the clips and the prompt.
3. The AI returns an edit plan that references items by id: `{ "ref": "whip", "duration": 0.24, "params": { "direction": "left" } }`.
4. `tools/validate_plan.py` checks the plan against the schema **and** the library: unknown ids, invalid params, durations out of range, timeline maths including overlapping transitions.
5. The render engine looks up each item's `render` definition and draws it.

## Open questions

- **Render format:** the same definition must drive the preview and the export. Candidate: GLSL shaders with parameters as uniforms, which can run in WebGL (preview) and in the Rust engine via wgpu (export). The open-source [gl-transitions](https://github.com/gl-transitions/gl-transitions) collection (MIT) uses this model and could seed the transition library. For the spike, items can map to FFmpeg filters instead.
- **Catalog size:** with hundreds of items the catalog becomes expensive to send every time. Options: send only items matching the requested style, or a two-step request (pick categories, then items).
- **Third-party items:** whether creators or partners can add library items later (a marketplace), and how they are sandboxed.
- **Salt:** placeholder manifest; parameters and render defined during development.
