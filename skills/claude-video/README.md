# Claude Video Skill

Vendored from [bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT), the `watch` skill.

## What it does

Gives Claude the ability to watch any video — a URL (YouTube, Vimeo, TikTok, etc.) or a local file. Downloads with `yt-dlp` when needed, extracts scene-aware or fast-keyframe frames with `ffmpeg`, pulls a timestamped transcript (native captions first, Whisper API as fallback), and hands frames + transcript to Claude to answer questions about what's on screen and what's said.

## Use cases inside video-use

- **Study a reference or competitor video** before proposing a cut/grade/animation strategy — "what hook did this open with?", "what's the pacing like?"
- **Diagnose a bug from a screen recording** a user drops in.
- **Summarize or fact-check** footage before deciding what to keep.

## Usage

```bash
python3 skills/claude-video/scripts/setup.py --json     # first-run preflight
python3 skills/claude-video/scripts/watch.py <url-or-path> [question]
```

See `SKILL.md` in this directory for the full workflow (frame extraction, transcript fallback, detail levels).

## Prerequisites

`yt-dlp` and `ffmpeg` (auto-installed on first run via `brew` on macOS; Linux/Windows get exact commands printed). A Whisper API key is only needed when a video has no captions.
