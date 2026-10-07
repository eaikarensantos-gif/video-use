---
name: faceless-shorts
description: "Turn existing videos into short vertical clips for a faceless (no on-camera host) channel and export clean per-platform files for YouTube Shorts, TikTok, Kwai and Facebook Reels. Use when the user wants cortes, clips, shorts or reels from long videos they already have, a faceless/'canal fantasma'/'canal dark' channel, or the same short posted to several platforms. A sub-skill of video-use — inherits its Hard Rules."
version: 1.0.0
---

# Faceless Shorts

Existing long videos in, a batch of 9:16 shorts out, one clean file per platform.

This skill does not replace video-use. Transcription, cut selection, grading, subtitles and self-eval all follow the parent `SKILL.md` and its Hard Rules. What this skill adds is the clip-mining step at the start and the platform export step at the end.

## Pipeline

```
INVENTORY → RIGHTS CHECK → MINE CLIPS → CONFIRM → CUT (video-use) → EXPORT → REVIEW
```

1. **Inventory.** Same as video-use: `ffprobe`, `transcribe_batch.py`, `pack_transcripts.py`.
2. **Rights check.** Ask where each source came from before cutting anything (see *Source rights*). Write the answer into `edit/project.md`.
3. **Mine clips.** Read `takes_packed.md` and propose 5–15 candidate clips. Each candidate is a self-contained idea that makes sense with zero context.
4. **Confirm.** Show the list (table below). Wait for the user to pick. Never render the whole list unasked.
5. **Cut.** One EDL per clip, `edit/clips/<slug>/edl.json`. Render with `helpers/render.py` exactly as video-use does, output `edit/clips/<slug>/final.mp4`.
6. **Export.** `scripts/export_platforms.py edit/clips/<slug>/final.mp4 -o edit/clips/<slug>/export`.
7. **Review.** Run `--safe-zones` on at least one clip, look at the PNG, and confirm no caption or key text sits under platform UI. Then the parent skill's self-eval.

## Mining clips

A good short from a long video has: a hook in the first 2 seconds that is a claim, number or question; one idea only; a closing line that resolves it. Length 20–60s is the safe default for reach on all four platforms; longer only if the idea needs it.

Propose candidates as:

| # | slug | source | [start–end] | length | hook (first words) | why it stands alone |
|---|------|--------|-------------|--------|--------------------|---------------------|

Rules of thumb when reading the transcript:
- Start on the claim, not on the setup. Cut the "então, como eu ia dizendo".
- If the clip needs context, add it with a 1-line title card, not by extending the cut backwards.
- Never splice phrases from different moments to make someone say something they did not say. Reordering within one clip is fine only if meaning is unchanged.

## Faceless format

No host on camera means the frame must carry the attention. Options, pick per source:
- **Source already vertical or has a speaker** → center crop (`--fit crop`), check the face stays in frame with `timeline_view`.
- **Horizontal screen, slides, landscape footage** → `--fit pad` (blurred fill) plus big captions in the middle third.
- **Audio-only or weak visuals** → captions as the main visual; consider b-roll per video-use.

Captions: big, centered, between y≈600 and y≈1400 on a 1920 frame. Below 1500 they go under the platform UI on every app.

## Export

```bash
python scripts/export_platforms.py <clip.mp4> -o <export_dir>
python scripts/export_platforms.py <clip.mp4> -o <export_dir> --fit pad --handle @canal
python scripts/export_platforms.py <clip.mp4> --safe-zones zones.png
```

What it does per platform: 1080x1920, H.264 high, CRF 18, AAC 192k 48kHz, loudness to −14 LUFS, fps capped (Kwai at 30), source metadata stripped, `+faststart`. Output names `<clip>__<platform>.mp4` plus `manifest.json` with duration and warnings.

Duration caps in the script are defaults. Platforms change them without notice — if the user knows the current limit, pass `--max-seconds kwai=60`. Over-cap clips are warned, not cut, unless `--trim`.

Why one file per platform if they are almost identical: posting a file downloaded from TikTok to Kwai/Reels carries the other platform's watermark and those platforms reduce reach for it. Always upload from these clean exports.

## Source rights

"Existing videos" can mean three different things. Ask which:

1. **The user's own videos** → fine.
2. **Material released for free redistribution** (official campaign kits, Creative Commons, press material that says so) → fine; note the source in `project.md`.
3. **Someone else's videos without license** (TV, other creators) → tell the user plainly: platforms flag it as reused content (no monetization, strikes), and it can be copyright infringement. Do not mine clips from it unless the user confirms they have permission.

## Political and electoral content (Brazil)

If the channel's content is about elections, candidates or parties, these are legal constraints, not style. Raise them once at the start, in plain words, and record the user's answer in `project.md`.

- **Faceless is fine; anonymous is not.** During the campaign, electoral speech on the internet cannot be anonymous (Lei 9.504/97, art. 57-D). The channel can have no face on camera, but its bio must identify who is responsible (person or organization). Suggest `--handle` and a real name or entity in each profile bio.
- **AI-altered content must be labeled** (TSE Res. 23.610/2019 as amended in 2024). If any clip uses synthetic voice, generated images or altered footage, export with `--ai-label` and say so in the caption. Deepfakes of real people are prohibited outright — do not build them.
- **No paid boosting** of electoral content by anyone other than candidates, parties and coalitions, through their official accounts. Organic posting by individuals is allowed.
- **No out-of-context cuts.** A clip that changes what a candidate or opponent meant is the kind of content the TSE orders removed and can be treated as disinformation. The splice rule above is mandatory here.
- **Coordinated inauthentic behavior.** Running several fake-identity accounts to post the same content violates the rules of all four platforms and gets the whole network removed. One identified channel per platform.
- **Check the calendar.** Electoral propaganda has start and end dates set by the TSE, including a cut-off before voting day. Ask the user to confirm the current dates; do not assume.

These rules are summarized for the editing workflow, not legal advice. If the user is producing for a campaign or party, their legal team has the final word.

## Directory layout

```
<videos_dir>/edit/
├── project.md                 ← include source rights + electoral answers here
├── takes_packed.md
├── transcripts/
└── clips/<slug>/
    ├── edl.json
    ├── final.mp4
    └── export/
        ├── final__youtube.mp4
        ├── final__tiktok.mp4
        ├── final__kwai.mp4
        ├── final__facebook.mp4
        └── manifest.json
```
