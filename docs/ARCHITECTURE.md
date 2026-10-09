# Lauren — Architecture

> Status: Draft (Round 3 of discovery).

## Core principle: AI plans, the local engine edits

The AI never outputs video. It outputs an **edit plan** (structured JSON: clips, cuts, transitions, zooms, music, stickers). Lauren's engine on the user's machine turns that plan into a timeline, a preview and the final export.

```
footage ──► frames + audio ──► Gemini: clip analysis ──► text model + catalog ──► edit plan (JSON)
                                                                       │
                       user prompt / manual timeline edits ◄──────────┤
                                                                       ▼
                                                     timeline ──► live preview ──► export
```

Why:
- AI cost is limited to video understanding plus text output. This is what keeps Lauren cheaper than generation.
- The plan maps directly onto the timeline, so prompt edits and manual edits work on the same data.

## Two-stage AI pipeline

The AI work is split into two calls so the expensive part runs once per project, not once per prompt:

| Stage | Input | Output | Model | Runs |
|---|---|---|---|---|
| 1. Understand | Clip frames + audio (multimodal) | **Clip analysis**: per clip, what happens and when (subjects, motion, highlights, speech, best moments, orientation) | Gemini, video-capable | Once, when clips are added |
| 2. Edit | Clip analysis (text) + library catalog + user prompt (+ current plan for follow-ups) | Edit plan JSON | Text model, can be cheaper | Every prompt |

Why:
- **Follow-up prompts never resend video.** "Make c2 shorter" only reruns stage 2, on text.
- The library catalog only goes to the text-only stage, where tokens are cheapest.
- Stage 2's prompt starts with a fixed prefix (instructions + catalog) so provider prompt caching can bill it at a reduced rate on repeat requests.
- The clip analysis is cached locally with the project, so reopening a project costs nothing.

Risk: stage 2 can only use what stage 1 wrote down. Frame-precise decisions (exact cut points, zoom targets) need stage 1 to record timestamps and positions, not just descriptions. The clip analysis format is defined in the spike.

## Decisions

| Area | Decision |
|---|---|
| Desktop shell | Tauri: JS/TS UI + Rust core |
| AI access | OpenRouter |
| Video understanding | The AI looks at sampled frames (Gemini models) |
| AI billing | Lauren pays OpenRouter and charges users (subscription/credits) |
| Preview | Render first, then show: preview is a real render, so it always matches the export |
| Export | 720p / 1080p / 4K; 9:16, 16:9, 4:3, 1:1 |
| Upload | Footage is always uploaded for AI analysis. Users are told plainly it is used only for analysis, not collected |

## Hardware

The AI step needs no local GPU. Decoding, live preview and rendering (especially 4K) still run on the user's machine. They rely on hardware video decode/encode where available and fall back to CPU (slower). Minimum spec still to be defined.

## Open questions

- **Preview speed:** each edit needs a render before it is shown. Fast low-resolution preview renders keep iteration quick; full quality only on export.
- **Data handling:** pick OpenRouter providers with no training on / minimal retention of user data, and state this in the privacy policy.
- **Sending many clips to Gemini:** one request with every clip as a separate, id-labelled video part, or the clips joined into one contact video with markers. Measure accuracy and cost in the spike.
- **Frame sampling rate:** trade-off between AI cost and edit precision (relevant for frame-precise transitions).
- **Minimum hardware spec.**
