# HyperFrames CLI Reference

All commands run via `npx --yes hyperframes <command>`. Use `--yes` to auto-confirm installation.

## Core dev commands

### `init`

Scaffold a new composition project.

```bash
npx --yes hyperframes init . --example blank --non-interactive --skip-skills
npx --yes hyperframes init . --example product-launch --non-interactive --skip-skills
```

| Flag | Purpose |
|------|---------|
| `--example <name>` | Starting template (`blank`, `product-launch`, `website-to-video`, etc.) |
| `--non-interactive` | Skip all prompts (required for sub-agents) |
| `--skip-skills` | Don't download agent skills into the slot directory |

Always run inside the slot directory. Never at repo root.

### `preview`

Launch a live-reload browser preview.

```bash
npx --yes hyperframes preview .
npx --yes hyperframes preview . --port 3333
```

Use this interactively to inspect timing and layout. Not used in automated sub-agent flows.

### `lint`

Validate composition syntax: missing required attributes, malformed meta tags, unsupported elements.

```bash
npx --yes hyperframes lint .
```

Always run before `render`. Fix all errors before proceeding.

### `validate`

Check composition integrity: timing overlaps, seekability of animation adapters, media file references.

```bash
npx --yes hyperframes validate .
```

Run after `lint`. Reports non-seekable animation patterns that would produce wrong frames.

### `inspect`

Print composition metadata (duration, FPS, canvas size, slide count).

```bash
npx --yes hyperframes inspect .
```

Useful to verify meta tags were parsed correctly before rendering.

### `doctor`

Diagnose environment: Node version, FFmpeg presence, Chrome/Chromium path, network access.

```bash
npx --yes hyperframes doctor
```

Run on first use in a new environment.

### `render`

Render the composition to video.

```bash
# MP4 (default)
npx --yes hyperframes render . -o render.mp4

# WebM with alpha channel (for transparent overlays)
npx --yes hyperframes render . --format webm -o render.webm

# Draft quality (faster, lower resolution)
npx --yes hyperframes render . -o render_draft.mp4 --quality draft

# Specific resolution override
npx --yes hyperframes render . -o render.mp4 --width 1920 --height 1080

# Specific FPS override
npx --yes hyperframes render . -o render.mp4 --fps 24

# Render subset of slides
npx --yes hyperframes render . -o render.mp4 --slides 1,3-5
```

| Flag | Purpose |
|------|---------|
| `-o <path>` | Output file path (required) |
| `--format mp4\|webm` | Output container (default: mp4) |
| `--quality draft\|medium\|high` | Quality preset (default: high) |
| `--width <px>` | Override canvas width |
| `--height <px>` | Override canvas height |
| `--fps <n>` | Override frame rate |
| `--slides <spec>` | Slide subset, e.g. `1,3-5` |

After rendering, always verify with ffprobe:

```bash
ffprobe -v error -show_entries format=duration,size -of csv render.mp4
```

## Registry commands

### `add`

Install catalog blocks into the current slot.

```bash
npx --yes hyperframes add flash-through-white
npx --yes hyperframes add instagram-follow
npx --yes hyperframes add data-chart
npx --yes hyperframes add --all          # entire catalog
npx --yes hyperframes add --list         # print available blocks
npx --yes hyperframes add --skill <name> # install agent skill
```

### `publish`

Deploy a composition to HyperFrames cloud (requires auth).

```bash
npx --yes hyperframes publish .
```

## Lambda (cloud rendering)

For long compositions or when local rendering is slow.

```bash
# Set up distributed render stack on AWS
npx --yes hyperframes lambda deploy

# Render on Lambda
npx --yes hyperframes lambda render . -o render.mp4

# Check render progress
npx --yes hyperframes lambda progress <job-id>
```

Lambda rendering produces the same output as local rendering (deterministic guarantee).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `HF_CHROME_PATH` | Override Chromium executable path |
| `HF_FFMPEG_PATH` | Override FFmpeg executable path |
| `HF_CONCURRENCY` | Parallel render workers (default: CPU count) |
| `HF_API_KEY` | API key for cloud/Lambda rendering |

## Typical sub-agent command sequence

```bash
cd <slot_dir>
npx --yes hyperframes init . --example blank --non-interactive --skip-skills
# ... author composition.html ...
npx --yes hyperframes lint .
npx --yes hyperframes validate .
npx --yes hyperframes render . -o render.mp4
ffprobe -v error -show_entries format=duration -of csv render.mp4
```
