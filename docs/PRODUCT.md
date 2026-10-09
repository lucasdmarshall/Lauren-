# Lauren — Product (MVP)

> Status: Draft (Round 2 of discovery).

## Example prompts

These describe the kind of edits Lauren must handle:

1. "Find music that fits this video and add it."
2. "Adjust this TikTok video with transitions, effects and cuts where needed."
3. "Make a salt transition between these clips." (A TikTok-style transition cut with master-level, frame-precise timing. Exact spec still to be written.)

## Input footage

**Any kind** (talking-head, vlog, gaming, tutorial, etc.). Lauren is not limited to one genre of footage.

## Editing model: prompt + timeline

The user can refine an AI edit in two ways:

- **Prompt:** follow-up instructions such as "make this part shorter".
- **Timeline:** the AI's edit is shown on a timeline the user can adjust by hand.

The AI's output is an editable project, not a flattened video.

## MVP features

| Feature | Notes |
|---|---|
| Cut / trim | Core of every edit |
| Music | Pick and add music that fits the video (see open question on licensing) |
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

- **Music licensing:** "royalty-free not required" is a legal risk. If Lauren supplies copyrighted music, creators' videos get muted or claimed, and Lauren itself could be liable. Options: the user supplies their own music, or Lauren searches a free/licensed library.
- **Salt transition spec:** define it precisely enough to implement (cut timing, motion, effects).
