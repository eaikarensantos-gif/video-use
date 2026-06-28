---
name: heygen-hyperframes
description: "Production pipeline for browser-native HTML/CSS/GSAP video compositions using HeyGen HyperFrames. Creates product launch videos, website-to-video captures, kinetic typography, transparent WebM overlays, motion graphics, and any composition that benefits from deterministic frame capture from web technology. Use when: the animation is authored like a web composition (HTML/CSS/GSAP/Lottie/Three.js), the output needs precise timing control, the slot requires a transparent WebM overlay, or the user asks for HyperFrames specifically."
version: 1.0.0
requires:
  - node: ">=22"
  - ffmpeg: "*"
---

# HeyGen HyperFrames Production Pipeline

## When to use HyperFrames (vs. other engines)

| Signal | Use HyperFrames |
|--------|-----------------|
| Product UI motion, website/mockup captures | Yes |
| Kinetic typography, landing-page promos | Yes |
| Transparent WebM overlay needed | Yes |
| Data-driven UI states | Yes |
| Deterministic frame capture required (CI/regression) | Yes |
| Author prefers HTML/CSS/GSAP over React | Yes |
| Already have a Remotion brand system | No → use Remotion |
| Formal math diagrams, equation derivations | No → use Manim |
| Simple text card, single counter | No → use PIL+ffmpeg |

## Prerequisites

```bash
node --version   # must be 22+
ffmpeg -version  # must be on PATH
npx hyperframes doctor  # diagnose environment
```

HyperFrames itself is installed on demand via `npx --yes hyperframes`.

## Slot setup (one per animation)

Always scaffold inside the slot directory, never at repo root.

```bash
mkdir -p <edit>/animations/slot_<id>
cd <edit>/animations/slot_<id>
npx --yes hyperframes init . --example blank --non-interactive --skip-skills
```

`--skip-skills` prevents the init from downloading agent skills into the slot (they live in the video-use repo instead).

## Composition structure

A HyperFrames composition is a plain HTML file. No build step required.

```html
<!DOCTYPE html>
<html>
<head>
  <meta name="hz:canvas-width"  content="1920">
  <meta name="hz:canvas-height" content="1080">
  <meta name="hz:fps"           content="30">
  <meta name="hz:duration"      content="6">   <!-- seconds -->
  <meta name="hz:slide-selector" content=".slide">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 1920px; height: 1080px; overflow: hidden; background: #0a0a0a; }
    .slide { width: 1920px; height: 1080px; position: relative; }
  </style>
</head>
<body>
  <div class="slide">
    <!-- composition content here -->
  </div>

  <!-- GSAP via CDN — always publicly reachable -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script>
    // HyperFrames calls window.__hf_ready() when rendering begins.
    // Animations that need seek-control must register via HF adapter (see references/animation.md).
    // Simple GSAP timelines auto-adapt when paused at t=0 before render starts.
    document.addEventListener('DOMContentLoaded', () => {
      const tl = gsap.timeline({ paused: true });
      // build timeline...
      if (window.__hf_play) window.__hf_play(tl);
      else tl.play();
    });
  </script>
</body>
</html>
```

### Key metadata

| Meta tag | Purpose | Default |
|----------|---------|---------|
| `hz:canvas-width` | Output pixel width | 1920 |
| `hz:canvas-height` | Output pixel height | 1080 |
| `hz:fps` | Capture frame rate | 30 |
| `hz:duration` | Total composition duration (s) | required |
| `hz:slide-selector` | CSS selector for slides | `.slide` |

### Clip elements (media timing)

```html
<video class="clip" data-start="0" data-duration="6" src="file.mp4"></video>
<audio          data-start="0" data-duration="6" src="music.wav"></audio>
<img   class="clip" data-start="1" data-duration="4" src="logo.png">
```

`data-start` and `data-duration` are in seconds relative to composition start.

## Dev loop

```bash
# 1. Live preview with hot reload
npx --yes hyperframes preview .

# 2. Lint composition syntax
npx --yes hyperframes lint .

# 3. Validate timing/integrity
npx --yes hyperframes validate .

# 4. Draft render (fast check)
npx --yes hyperframes render . -o render_draft.mp4 --quality draft

# 5. Final render
npx --yes hyperframes render . -o render.mp4

# 6. Transparent WebM (when overlay needs alpha)
npx --yes hyperframes render . --format webm -o render.webm

# 7. Verify output
ffprobe -v error -show_entries format=duration,size -of csv render.mp4
```

Always run `lint` and `validate` before the final render. Fix any issues they report before handing the output to the EDL.

## Catalog blocks (registry)

Pre-built components installable into a slot:

```bash
npx --yes hyperframes add flash-through-white   # transition
npx --yes hyperframes add instagram-follow       # overlay card
npx --yes hyperframes add data-chart             # data visualization
npx --yes hyperframes add --all                  # entire catalog
```

Inspect what's available with `npx --yes hyperframes add --list` (or check `references/registry.md`).

## Animation adapters

HyperFrames requires animations to be **seekable** for deterministic frame capture. Different libraries integrate differently:

- **GSAP timelines** — pass the timeline to `window.__hf_play(tl)` (see composition template above).
- **CSS animations** — HyperFrames pauses and seeks `document.timeline` automatically.
- **Lottie** — use `lottie.loadAnimation({...})` and expose via `window.__hf_lottie = anim`.
- **Three.js / custom** — implement the `HFAdapter` interface (see `references/animation.md`).

See `references/animation.md` for full adapter patterns.

## Output spec

Match the source video's resolution and framerate unless the user asks otherwise. Common targets:

| Format | Resolution | FPS | Flag |
|--------|-----------|-----|------|
| 1080p landscape | 1920×1080 | 30 | default |
| Vertical social | 1080×1920 | 30 | set meta tags |
| Square | 1080×1080 | 30 | set meta tags |
| 4K | 3840×2160 | 24 | set meta tags |
| Transparent overlay | any | 30 | `--format webm` |

## Multi-slide compositions

For longer compositions with distinct sections, use multiple `.slide` divs. HyperFrames treats each as a page:

```html
<div class="slide" data-canvas-height="1080"><!-- slide 1 --></div>
<div class="slide" data-canvas-height="1080"><!-- slide 2 --></div>
```

Or use a single slide with GSAP timeline controlling a full narrative arc.

## Connecting to the EDL

After rendering, point the EDL overlay at the rendered file:

```json
{
  "overlays": [
    {
      "file": "<edit>/animations/slot_1/render.mp4",
      "start_in_output": 12.4,
      "duration": 6.0
    }
  ]
}
```

For WebM overlays with alpha, `render.py` handles the blend automatically.

## Sub-agent brief template

When spawning an animation sub-agent for a HyperFrames slot, include all of the following. Sub-agents have no parent context — the brief must be self-contained.

```
Build ONE HyperFrames animation slot. Nothing else.

GOAL: [one sentence describing what the animation shows]

SLOT DIR: <absolute path to slot_<id> dir>
OUTPUT:   <slot_dir>/render.mp4  (or render.webm if alpha needed)

TECHNICAL SPEC:
  Resolution: 1920×1080
  FPS: 30
  Duration: <N>s
  Format: mp4 (or webm)
  Codec: h264/yuv420p (or vp9/yuva420p for webm)

SETUP:
  cd <slot_dir>
  npx --yes hyperframes init . --example blank --non-interactive --skip-skills

VISUAL STYLE:
  Background: <color>
  Primary color: <color>
  Accent: <color>
  Font: <family, size, weight>
  Feel: <e.g. "clean SaaS launch", "retro terminal", "warm editorial">

FRAME-BY-FRAME TIMELINE:
  0.0s  — [what appears]
  0.5s  — [motion or transition]
  ...
  <N-1>s — hold final frame

ANIMATION RULES:
  - Use GSAP timelines; pass to window.__hf_play(tl)
  - Easing: power2.out for reveals, power2.inOut for continuous motion — never Linear
  - One element appears at a time — no parallel reveals

CHECKS (in order):
  1. npx --yes hyperframes lint .
  2. npx --yes hyperframes validate .
  3. npx --yes hyperframes render . -o render.mp4
  4. ffprobe -v error -show_entries format=duration -of csv render.mp4  ← must match spec

DELIVERABLE: render.mp4 at the output path. Report ffprobe duration.
Do not ask questions. If anything is ambiguous, pick the most obvious interpretation.
```

## Anti-patterns

- **Importing across slot directories.** Each slot is self-contained. Copy any shared helpers inline.
- **Non-seekable animations.** Linear `setTimeout`/`setInterval` animations won't render correctly — always use GSAP timelines or CSS keyframes.
- **Missing `hz:duration` meta.** Render will fail or produce wrong length.
- **Skipping lint/validate.** They catch timing overlap and attribute errors before the expensive render.
- **Running `npx hyperframes` at repo root.** Always inside the slot directory.
- **Parallel reveals.** One new element per beat — the eye can't track two simultaneous entrances.
- **Linear easing.** Always cubic or power easing. `gsap.defaults({ ease: "power2.out" })`.

## References

| File | Contents |
|------|----------|
| `references/animation.md` | GSAP patterns, CSS keyframes, Lottie adapter, HFAdapter interface, seekability rules |
| `references/registry.md` | Catalog block list, install commands, usage examples |
| `references/cli.md` | Full CLI reference — all commands, flags, render options, Lambda commands |
| `references/design.md` | Frame.md design system, typography for video, color palettes, layout templates |
