# Lauren — Product (MVP)

> Status: Draft (Round 2 of discovery).

## Example prompts

These describe the kind of edits Lauren must handle:

1. "Find music that fits this video and add it."
2. "Adjust this TikTok video with transitions, effects and cuts where needed."
3. "Make a salt transition between these clips." (A TikTok-style transition with master-level, frame-precise timing. The exact spec will be worked out during development.)

## Input footage

The typical input is **several short clips** uploaded together (phone recordings of a few seconds each). The AI selects, trims, orders and combines them into one video. Any genre of footage is allowed.

## Editing model: prompt + timeline

The user can refine an AI edit in two ways:

- **Prompt:** follow-up instructions such as "make this part shorter".
- **Timeline:** the AI's edit is shown on a timeline the user can adjust by hand.

The AI's output is an editable project, not a flattened video.

## Effects, transitions and animations

Nothing is hardcoded. Lauren ships libraries of effects, transitions and in/out animations, and the AI decides which to use for each edit. See [LIBRARY.md](LIBRARY.md).

## MVP features

| Feature | Notes |
|---|---|
| Cut / trim | Core of every edit |
| Music | User brings their own music; the AI picks and fits tracks to the video. If Lauren searches for music, it uses royalty-free sources only |
| Transitions | Between clips |
| Zoom / reframe | Including vertical (9:16) output for TikTok/Reels |
| Stickers | Overlays |

## AI provider

**OpenRouter**, with a Gemini model for video understanding. Lauren pays for AI usage and charges users (see [ARCHITECTURE.md](ARCHITECTURE.md)).

## Language

**English first.** Other languages (including Burmese) come later.

## Export

- Resolutions: 720p, 1080p, 4K
- Aspect ratios: 9:16, 16:9, 4:3, 1:1

## Non-goals

- Video generation (see [VISION.md](VISION.md))

## Founder skills

JavaScript, Python, C++. These shape the tech stack (Round 3).

## Open questions

- **Salt transition spec:** emerges during development.
