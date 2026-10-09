# Lauren — Effect, Transition & Animation Library

> Status: Draft for the spike.

Nothing about individual effects, transitions or animations is hardcoded in the edit plan schema or the app. Each one is a **library item**: a JSON manifest in `library/`. The AI is shown the catalog of available items and decides which to use, where, and with what parameters.

```
library/
├── transitions/   40 items
├── effects/       36 items
└── animations/    29 items (in, out and loop animations for overlays)
```

The full list is in [Catalog](#catalog) below.

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
| `slots` | Animations only: `in`, `out` and/or `loop`. An `out` animation plays the item in reverse; a `loop` animation repeats while the overlay is visible, with `duration` as one cycle. Default `["in", "out"]`. |
| `params_schema` | JSON Schema for the item's parameters. Every parameter needs a `default` and a `description`. |
| `render` | How the engine draws it. Format still open (below). |

## How the pieces connect

1. `tools/build_catalog.py` turns the manifests into a compact catalog.
2. The catalog goes into the edit-stage AI request alongside the clip analysis and the prompt (see [Catalog strategy](#catalog-strategy)).
3. The AI returns an edit plan that references items by id: `{ "ref": "whip", "duration": 0.24, "params": { "direction": "left" } }`.
4. `tools/validate_plan.py` checks the plan against the schema **and** the library: unknown ids, invalid params, durations out of range, timeline maths including overlapping transitions.
5. The render engine looks up each item's `render` definition and draws it.

## Catalog strategy

Sending the full catalog with every request is avoided in four layers. The first three apply now; the fourth is added when the library outgrows them.

1. **Only the edit stage sees the catalog.** Video understanding runs once per project and never receives the catalog. Follow-up prompts rerun only the text-only edit stage. See [ARCHITECTURE.md](ARCHITECTURE.md#two-stage-ai-pipeline).
2. **Compact text format.** One line per item instead of JSON: `whip [energetic,fast,trendy] 0.25s[0.1-0.6]: description | direction=left(left/right/up/down) blur=0.7(0-1)`. For the 105 current items: ~18 KB (about 4.5k tokens) versus ~40 KB as compact JSON.
3. **Stable, cacheable prefix.** The catalog sits at the start of the prompt with the fixed instructions, before anything that changes per request. Providers with prompt caching bill repeated prefixes at a reduced rate. The catalog text must be byte-identical between requests (sorted, deterministic), which `build_catalog.py` guarantees.
4. **Local shortlisting (later).** When the library grows to several hundred items, rank items locally before sending: match tags against the requested style and the clip analysis (and later, local text embeddings of descriptions), always keep a few safe defaults (cut, crossfade, pop, fade), and send the top items per kind. Costs nothing, since it runs on the user's machine.

Ruled out: letting the AI look items up through tool calls. Each round trip resends the whole conversation, so it costs more than sending the catalog once.

## Safety

Flashing items (strobe) are capped at 3 flashes per second, following the WCAG threshold for photosensitive viewers. New items that flash must stay within that limit.

## Open questions

- **Render format:** the same definition must drive the preview and the export. Candidate: GLSL shaders with parameters as uniforms, which can run in WebGL (preview) and in the Rust engine via wgpu (export). The open-source [gl-transitions](https://github.com/gl-transitions/gl-transitions) collection (MIT) uses this model and could seed the transition library. For the spike, items can map to FFmpeg filters instead.
- **Third-party items:** whether creators or partners can add library items later (a marketplace), and how they are sandboxed.
- **Salt:** placeholder manifest; parameters and render defined during development.

## Catalog

### Transitions

| id | Name | Tags | Overlap |
|---|---|---|---|
| `blinds` | Blinds | graphic, stylish | yes |
| `blur_dissolve` | Blur dissolve | smooth, dreamy, calm | yes |
| `circle_reveal` | Circle reveal | reveal, playful | yes |
| `clock_wipe` | Clock wipe | time, playful | yes |
| `crossfade` | Crossfade | smooth, calm, emotional | yes |
| `cube` | Cube | 3d, slick, tech | yes |
| `cut` | Cut | clean, neutral | |
| `dip` | Dip to color | calm, chapter, cinematic | |
| `film_burn` | Film burn | vintage, cinematic, warm | yes |
| `flash` | Flash | energetic, impact | |
| `flip` | Card flip | 3d, reveal, playful | yes |
| `glitch` | Glitch | edgy, tech, energetic | |
| `ink` | Ink bleed | artistic, smooth | yes |
| `kaleidoscope` | Kaleidoscope | trippy, music, wild | |
| `light_leak` | Light leak | dreamy, warm, vintage | yes |
| `luma_fade` | Luma fade | elegant, smooth | yes |
| `mosaic` | Mosaic | graphic, stylish | yes |
| `page_curl` | Page curl | classic, storytelling | yes |
| `pixelate` | Pixelate | retro, gaming, playful | |
| `push` | Push | clean, dynamic | yes |
| `rgb_split` | RGB split | edgy, impact | |
| `ripple` | Ripple | dreamy, liquid | yes |
| `roll` | Camera roll | energetic, playful | |
| `salt` | Salt | trendy, precise | |
| `shake_cut` | Impact cut | impact, energetic | |
| `shape_reveal` | Shape reveal | playful, reveal, cute | yes |
| `slide` | Slide | clean, modern | yes |
| `spin` | Spin | energetic, trendy, wild | |
| `split_slide` | Split slide | reveal, bold, stylish | yes |
| `stretch` | Stretch | playful, comedic, energetic | |
| `strobe` | Strobe | energetic, music, wild | |
| `stutter` | Stutter | trendy, music, rhythmic | |
| `swirl` | Swirl | trippy, surreal | |
| `tunnel` | Tunnel zoom | energetic, wild, reveal | |
| `vhs_rewind` | VHS rewind | retro, vintage, comedic | |
| `whip` | Whip pan | energetic, fast, trendy | |
| `whip_zoom` | Whip zoom | energetic, trendy, fast | |
| `wipe` | Wipe | clean, classic | yes |
| `zoom` | Zoom through | energetic, punchy, reveal | |
| `zoom_out` | Zoom out | reveal, energetic | |

### Effects

| id | Name | Tags |
|---|---|---|
| `black_white` | Black and white | dramatic, cinematic |
| `blur` | Blur | soft |
| `clone_grid` | Clone grid | graphic, music, bold |
| `color_pop` | Color pop | stylish, focus, color |
| `cool_tone` | Cool tone | cool, moody, color |
| `duotone` | Duotone | graphic, bold, color |
| `echo` | Echo trails | trippy, dreamy, dance |
| `exposure_flash` | Exposure flash | impact, energetic |
| `film_grain` | Film grain | cinematic, subtle |
| `freeze` | Freeze frame | comedic, emphasis |
| `glitch` | Glitch | edgy, tech |
| `glow` | Glow | dreamy, glam |
| `halftone` | Comic halftone | comedic, graphic, playful |
| `heartbeat` | Heartbeat | dramatic, emotional |
| `high_contrast` | High contrast | bold, color |
| `invert` | Invert | edgy, impact |
| `kaleidoscope` | Kaleidoscope | trippy, music |
| `lens_distortion` | Fisheye | comedic, skate, playful |
| `letterbox` | Cinematic bars | cinematic, dramatic |
| `light_leak` | Light leak | dreamy, vintage, warm |
| `mirror` | Mirror | trippy, stylish |
| `motion_blur` | Motion blur | dynamic, smooth |
| `neon` | Neon edges | futuristic, edgy, music |
| `pixelate` | Pixelate | retro, gaming |
| `radial_blur` | Zoom blur | energetic, focus |
| `rgb_split` | RGB split | edgy, music |
| `shake` | Camera shake | energetic, impact |
| `sharpen` | Sharpen | subtle, fix |
| `strobe` | Strobe | music, wild |
| `teal_orange` | Teal & orange | cinematic, color |
| `vhs` | VHS | retro, vintage, lo-fi |
| `vignette` | Vignette | cinematic, subtle, focus |
| `vintage` | Vintage | vintage, warm, color |
| `warm_tone` | Warm tone | warm, color, subtle |
| `wave` | Wave distortion | trippy, liquid |
| `zoom_pulse` | Zoom pulse | energetic, music, rhythmic |

### Animations

| id | Name | Tags | Slots |
|---|---|---|---|
| `blur_in` | Blur in | smooth, cinematic | in, out |
| `bounce` | Bounce | playful, energetic | in, out |
| `drop` | Drop | playful, comedic | in, out |
| `elastic` | Elastic | playful, cute | in, out |
| `fade` | Fade | smooth, subtle | in, out |
| `flicker` | Neon flicker | retro, night, stylish | in, out, loop |
| `flip` | Flip | 3d, playful | in, out |
| `float` | Float | subtle, calm | loop |
| `glitch_in` | Glitch in | edgy, tech | in, out |
| `grow` | Grow | clean, subtle | in, out |
| `heartbeat` | Heartbeat | cute, emotional | loop |
| `iris` | Iris | clean, reveal | in, out |
| `pixel_in` | Pixel in | retro, gaming | in, out |
| `pop` | Pop | playful, energetic | in, out |
| `pulse` | Pulse | rhythmic, music | loop |
| `rise` | Rise | subtle, elegant | in, out |
| `roll_in` | Roll in | playful | in, out |
| `rubber` | Squash & stretch | comedic, playful | in, out |
| `shimmer` | Shimmer | glam, premium | loop |
| `slide` | Slide | smooth | in, out |
| `spin_in` | Spin in | playful, energetic | in, out |
| `spin_loop` | Spin | playful | loop |
| `stamp` | Stamp | impact, bold, comedic | in, out |
| `sway` | Sway | playful, calm | loop |
| `swing` | Swing | playful | in, out |
| `whip_in` | Whip in | energetic, fast | in, out |
| `wiggle` | Wiggle | playful, comedic | loop |
| `wipe_in` | Wipe in | clean | in, out |
| `zoom_in` | Zoom in | dynamic, bold | in, out |
