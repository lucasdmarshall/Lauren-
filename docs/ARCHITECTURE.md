# Lauren — Architecture

> Status: Draft (Round 3 of discovery).

## Core principle: AI plans, the local engine edits

The AI never outputs video. It outputs an **edit plan** (structured JSON: clips, cuts, transitions, zooms, music, stickers). Lauren's engine on the user's machine turns that plan into a timeline, a preview and the final export.

```
footage ──► sample frames + audio ──► Gemini (via OpenRouter) ──► edit plan (JSON)
                                                                       │
                       user prompt / manual timeline edits ◄──────────┤
                                                                       ▼
                                                     timeline ──► live preview ──► export
```

Why:
- AI cost is limited to video understanding plus text output. This is what keeps Lauren cheaper than generation.
- The plan maps directly onto the timeline, so prompt edits and manual edits work on the same data.

## Decisions

| Area | Decision |
|---|---|
| Desktop shell | Tauri: JS/TS UI + Rust core |
| AI access | OpenRouter |
| Video understanding | The AI looks at sampled frames (Gemini models) |
| AI billing | Lauren pays OpenRouter and charges users (subscription/credits) |
| Preview | Live: edits show immediately in the preview |
| Export | 720p / 1080p / 4K; 9:16, 16:9, 4:3, 1:1 |
| Privacy | User chooses whether footage is uploaded. A future web version requires upload |

## Hardware

The AI step needs no local GPU. Decoding, live preview and rendering (especially 4K) still run on the user's machine. They rely on hardware video decode/encode where available and fall back to CPU (slower). Minimum spec still to be defined.

## Open questions

- **Preview engine:** compositing in the webview (WebCodecs + WebGL) or in Rust. Preview and export must render the same result.
- **Privacy vs. AI:** frame analysis sends sampled frames to the AI provider. A "local only" mode can avoid uploading the full video but not the frames.
- **Frame sampling rate:** trade-off between AI cost and edit precision (relevant for frame-precise transitions).
- **Minimum hardware spec.**
