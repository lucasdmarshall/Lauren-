# Lauren — Edit Plan (v0.1)

> Status: Draft for the spike. Expect breaking changes until v1.

The edit plan is Lauren's core data model. The AI writes it, the timeline displays and edits it, and the render engine turns it into video.

- Schema: [`schema/edit-plan.schema.json`](../schema/edit-plan.schema.json) (JSON Schema 2020-12)
- Examples: [`examples/tiktok-basic.json`](../examples/tiktok-basic.json) (four clips, ramp preset), [`examples/run-it-back.json`](../examples/run-it-back.json) (reverse)
- Library of effects, transitions and animations: [LIBRARY.md](LIBRARY.md)
- Validator: `python tools/validate_plan.py PLAN.json` (needs `pip install -r tools/requirements.txt`)
- Timing reference implementation: [`tools/timing.py`](../tools/timing.py), tests in `tests/` (`python -m unittest discover -s tests`)

## Structure

```
plan
├── output      aspect ratio, resolution, fps, background
├── assets      media the plan may use (filled by the app)
├── clips       main video track, played back to back
│   └── reverse, speed / speed_ramp / speed_preset*, freezes, reframe, transform (zoom/pan keyframes), effects*, transition_in*
├── overlays    stickers/images, placed at a timeline time or anchored to a clip moment; animation_in/out/loop*
└── audio       music, placed like overlays; runs to the end of the edit by default

* reference a library item by id: { "ref": "whip", "duration": 0.24, "params": {...} }
```

## Design decisions

### 1. Times are seconds; the engine snaps to frames
LLMs reason about video in timestamps, not frame numbers, and phone footage is often variable frame rate. The plan stores seconds (decimals allowed). The render engine snaps every time to the output frame grid (`output.fps`), which is where frame precision comes from.

### 2. The main track is an ordered list
Clips have no stored timeline position; each starts when the previous one ends. The AI cannot create gaps or accidental overlaps, and reordering is just moving an array item.

### 3. Length is derived, and things stick to content
Editing changes the length constantly: trims, speed ramps, freezes and transitions all move everything after them. The plan never stores a clip's length or position. They are computed from the clip data by [`tools/timing.py`](../tools/timing.py), which the render engine must match.

To keep edits from drifting when timing changes, **times inside a clip are source times** (`at`): ramp points, freezes, zoom keyframes and effect starts all point at a moment in the footage. A shake at the landing (`"at": 4.2`) stays on the landing however the speed around it changes. This also matches how the AI thinks: the clip analysis says "landing at 4.2s in v1", and the plan can use that number directly.

Durations that describe how long something is *seen* (an effect, a freeze, an overlay) are timeline seconds.

Overlays and audio are placed either at a fixed timeline `start` or with an `anchor` (`{ "clip": "c3", "at": 4.2 }`), which follows that moment in the clip. Audio without a `duration` runs to the end of the edit, so music adapts when the edit gets longer or shorter.

### 4. Speed ramps
A clip has either a constant `speed` or a `speed_ramp`: points in source time, each with a speed (0.05x to 16x) and an easing for the change to the next point:

```json
"speed_ramp": [
  { "at": 2.3, "speed": 1.5, "easing": "hold" },
  { "at": 3.7, "speed": 1.5 },
  { "at": 4.0, "speed": 0.3, "easing": "hold" },
  { "at": 4.6, "speed": 0.3 },
  { "at": 5.0, "speed": 1.5 }
]
```

That is: fast run-up, smooth drop into 0.3x slow motion through the landing, smooth return to 1.5x.

- `hold` keeps the speed until the next point; `linear` changes it at a constant rate; `smooth` (default) eases in and out, which is what makes ramps look professional.
- Before the first point the first speed applies; after the last point, the last speed.
- Points are in source time, so the timeline length of the clip is the integral of `1 / speed` over the source range. `timing.py` computes it exactly for `hold`/`linear` and numerically for `smooth`.
- `preserve_pitch` (default true) keeps the clip's own audio at natural pitch.
- `freezes` hold a single frame for a number of timeline seconds and add that time to the clip.

Most ramps follow a few well-known shapes, so the AI usually places a **ramp preset** from the library instead of writing points:

```json
"speed_preset": { "ref": "hero_slowmo", "at": 4.2, "params": { "slow": 0.3 } }
```

`at` is the moment the shape is built around (the landing). The preset expands into `speed_ramp` points before timing is computed (`tools/ramps.py`). A clip uses exactly one of `speed`, `speed_ramp` and `speed_preset`. See [LIBRARY.md](LIBRARY.md#ramp-presets).

### 5. Reverse
`"reverse": true` plays a clip backward, from `out` to `in`. Everything inside the clip still uses source times, so a speed ramp, freeze, zoom keyframe or anchored sticker stays on the same frame whichever way the clip plays. The clip's own audio plays backward too; set `volume` to 0 to mute it.

Reverse applies to a whole clip. Effects that change direction mid-shot are built from several clips of the same asset, which keeps every source time unambiguous (a moment shown twice belongs to two different clips):

| Pattern | Clips |
|---|---|
| **Run it back** (rewind and replay) | forward to the moment → same range `reverse` at 2–4x, muted, often with `vhs_rewind` → forward again, usually with a slow-mo ramp. See [`examples/run-it-back.json`](../examples/run-it-back.json). |
| **Boomerang** | a short range forward → the same range `reverse` → repeat 2–3 times, cut transitions. |
| **Reverse reveal** | a single `reverse` clip, e.g. a cup un-spilling or a jump in reverse, as a hook in the first second. |

These patterns go into the edit-stage AI prompt as recipes.

### 6. Built for many short clips
The typical input is several short clips (a few seconds each) uploaded together. The AI combines them into one edit:

- It picks which clips to use, trims each one, and chooses the order. The order can differ from upload order, and an asset can be used more than once.
- `assets` carries what the AI needs to decide: duration, width/height (orientation for reframing), `has_audio`, and `recorded_at` when the file has it.
- Images can be clips too: `in` is 0 and `out` is how long the image is shown.

### 7. Effects, transitions and animations come from the library
The schema does not list any effect, transition or animation. Plans reference library items by id, and each item's manifest defines its parameters, duration range and behaviour. The AI picks from the catalog. See [LIBRARY.md](LIBRARY.md).

`transition_in` on clip N describes the change from clip N-1. A transition never uses media outside `in`/`out`, because short clips have no spare footage:

- **`overlap: true`** in the manifest (e.g. crossfade): both clips are visible at once, so they overlap by `duration` and the timeline gets shorter by that amount.
- **Otherwise** (e.g. whip, zoom, flash): applied to the last half of clip N-1 and the first half of clip N. The timeline length does not change.

### 8. Every item has an id and a note
Ids (`c2`, `o1`, `a1`) let follow-up prompts and the timeline target specific items ("make c2 shorter"). `note` records why the AI made the choice; the UI shows it and it goes back to the AI on the next prompt.

### 9. The AI never writes file paths
The app builds `assets` (id, kind, duration, label) and sends it to the AI. The AI references ids only. `src` is filled by the app.

### 10. Keep the schema simple for structured output
Flat objects with a `type` enum, no deep `oneOf` unions. This keeps the schema within what Gemini's structured output mode supports, and keeps invalid plans rare.

## Rules the schema cannot express

`tools/validate_plan.py` checks these after schema validation:

- Every `ref` exists in the library for the right kind, its `params` match the item's `params_schema`, and its duration is within the item's range.
- `out > in` for clips, and `out` is within the asset's duration.
- Ids are unique, and every `asset` reference exists with a compatible `kind` (clips → video/image, audio → audio, overlays → image/sticker).
- A clip has at most one of `speed`, `speed_ramp`, `speed_preset`; ramp points are in increasing order; a preset's params keep speeds within 0.05–16x.
- Warning: a preset whose shape extends past the clip's `in`/`out` (it is cut off there).
- Every source time (`at` in ramps, freezes, keyframes, effects, anchors) is within the clip's `in`–`out`.
- Overlays use exactly one of `start` or `anchor`; anchors point to an existing clip.
- Effects end before their clip ends; overlays and audio end before the timeline ends (all computed with speed ramps, freezes and overlapping transitions).
- A transition is no longer than either neighbouring clip.
- Warning (not an error): a music track shorter than its slot, unless `loop` is set.

## Not in v0.1

Text and captions, color grading, multiple video tracks (picture-in-picture), keyframed audio volume, custom fonts.

## Open questions

- **Follow-up prompts:** the AI returns a full new plan (simple) or a patch (cheaper, safer for large plans). Start with full plans in the spike.
- **Pattern presets:** if the AI gets multi-clip patterns (run it back, boomerang) wrong, they can become a library kind that expands one clip into several, like ramp presets do for speed.
- **Beat data:** `beat_sync` needs beat times from the music. Analyse locally, or ask the AI.
