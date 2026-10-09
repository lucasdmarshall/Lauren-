# Lauren — Edit Plan (v0.1)

> Status: Draft for the spike. Expect breaking changes until v1.

The edit plan is Lauren's core data model. The AI writes it, the timeline displays and edits it, and the render engine turns it into video.

- Schema: [`schema/edit-plan.schema.json`](../schema/edit-plan.schema.json) (JSON Schema 2020-12)
- Example: [`examples/tiktok-basic.json`](../examples/tiktok-basic.json)
- Library of effects, transitions and animations: [LIBRARY.md](LIBRARY.md)
- Validator: `python tools/validate_plan.py PLAN.json` (needs `pip install -r tools/requirements.txt`)

## Structure

```
plan
├── output      aspect ratio, resolution, fps, background
├── assets      media the plan may use (filled by the app)
├── clips       main video track, played back to back
│   └── reframe, transform (zoom/pan keyframes), effects*, transition_in*
├── overlays    stickers/images placed at timeline times, animation_in/out*
└── audio       music placed at timeline times

* reference a library item by id: { "ref": "whip", "duration": 0.24, "params": {...} }
```

## Design decisions

### 1. Times are seconds; the engine snaps to frames
LLMs reason about video in timestamps, not frame numbers, and phone footage is often variable frame rate. The plan stores seconds (decimals allowed). The render engine snaps every time to the output frame grid (`output.fps`), which is where frame precision comes from.

### 2. The main track is an ordered list
Clips have no stored timeline position; each starts when the previous one ends. The AI cannot create gaps or accidental overlaps, and reordering is just moving an array item. Clip duration on the timeline is `(out - in) / speed`.

Overlays and audio do use timeline times (`start`/`end`), because they are placed against the finished sequence.

### 3. Built for many short clips
The typical input is several short clips (a few seconds each) uploaded together. The AI combines them into one edit:

- It picks which clips to use, trims each one, and chooses the order. The order can differ from upload order, and an asset can be used more than once.
- `assets` carries what the AI needs to decide: duration, width/height (orientation for reframing), `has_audio`, and `recorded_at` when the file has it.
- Images can be clips too: `in` is 0 and `out` is how long the image is shown.

### 4. Effects, transitions and animations come from the library
The schema does not list any effect, transition or animation. Plans reference library items by id, and each item's manifest defines its parameters, duration range and behaviour. The AI picks from the catalog. See [LIBRARY.md](LIBRARY.md).

`transition_in` on clip N describes the change from clip N-1. A transition never uses media outside `in`/`out`, because short clips have no spare footage:

- **`overlap: true`** in the manifest (e.g. crossfade): both clips are visible at once, so they overlap by `duration` and the timeline gets shorter by that amount.
- **Otherwise** (e.g. whip, zoom, flash): applied to the last half of clip N-1 and the first half of clip N. The timeline length does not change.

### 5. Every item has an id and a note
Ids (`c2`, `o1`, `a1`) let follow-up prompts and the timeline target specific items ("make c2 shorter"). `note` records why the AI made the choice; the UI shows it and it goes back to the AI on the next prompt.

### 6. The AI never writes file paths
The app builds `assets` (id, kind, duration, label) and sends it to the AI. The AI references ids only. `src` is filled by the app.

### 7. Keep the schema simple for structured output
Flat objects with a `type` enum, no deep `oneOf` unions. This keeps the schema within what Gemini's structured output mode supports, and keeps invalid plans rare.

## Rules the schema cannot express

`tools/validate_plan.py` checks these after schema validation:

- Every `ref` exists in the library for the right kind, its `params` match the item's `params_schema`, and its duration is within the item's range.

- `out > in` for clips; `end > start` for overlays and audio.
- `in`/`out` fall within the asset's duration.
- Ids are unique, and every `asset` reference exists with a compatible `kind` (clips → video/image, audio → audio, overlays → image/sticker).
- Overlays and audio end before the end of the timeline.
- Keyframe and effect times fall within the clip's timeline duration.
- A transition is no longer than either neighbouring clip.
- Timeline duration accounts for overlapping transitions when checking overlay and audio end times.
- Audio does not need more of the track than the asset has.

## Not in v0.1

Text and captions, color grading, multiple video tracks (picture-in-picture), keyframed audio volume, custom fonts.

## Open questions

- **Follow-up prompts:** the AI returns a full new plan (simple) or a patch (cheaper, safer for large plans). Start with full plans in the spike.
- **Beat data:** `beat_sync` needs beat times from the music. Analyse locally, or ask the AI.
