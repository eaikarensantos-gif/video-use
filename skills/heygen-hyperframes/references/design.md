# HyperFrames Design Reference

## Frame.md design system

HyperFrames uses an inverted `DESIGN.md` format that translates web design tokens into video production constraints. When a project has a `DESIGN.md`, read it before authoring. It contains:

- Color tokens (primary, secondary, accent, background, surface)
- Typography scale (family, weights, sizes mapped to video roles)
- Spacing grid
- Logo/icon asset paths
- Tone and visual language description

If no `DESIGN.md` exists, propose a palette in the strategy phase and get confirmation before building.

## Typography for video

Video differs from web in three ways:
1. **No anti-aliasing at small sizes** — minimum 24px equivalent at 1080p.
2. **Background contrast must be explicit** — no browser default behaviors.
3. **Font loading must be synchronous** — async font loads miss frame 0.

### Safe font loading

```html
<style>
  /* Option 1: system font stack (zero latency) */
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

  /* Option 2: Google Fonts with display=swap disabled — preload instead */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=block');

  /* Option 3: self-hosted via data URI (zero network dependency) */
  @font-face {
    font-family: 'Brand';
    src: url('data:font/woff2;base64,<base64>') format('woff2');
  }
</style>
```

Never use `display=swap` — it can cause the frame capture to miss the loaded font. Use `display=block` or preload.

### Typography scale for 1920×1080

| Role | Font size | Line height | Use |
|------|-----------|-------------|-----|
| Hero headline | 96–120px | 1.1 | Single large statement |
| Section headline | 64–80px | 1.15 | Scene titles |
| Body copy | 36–48px | 1.4 | Supporting text |
| Label / caption | 24–32px | 1.3 | Annotations |
| Fine print | 20–24px | 1.3 | Minimum readable size |

Scale down proportionally for 1080×1920 (vertical): multiply by 0.56.

## Color palettes

### Dark tech / SaaS launch

```css
:root {
  --bg:      #0a0a0a;
  --surface: #141414;
  --primary: #ffffff;
  --accent:  #6366f1;  /* indigo */
  --muted:   #6b6b6b;
}
```

### Warm editorial / documentary

```css
:root {
  --bg:      #1a1410;
  --surface: #252018;
  --primary: #f5ede0;
  --accent:  #e8a44a;  /* amber */
  --muted:   #8a7d6a;
}
```

### Clean minimal / corporate

```css
:root {
  --bg:      #f8f8f8;
  --surface: #ffffff;
  --primary: #111111;
  --accent:  #0055ff;
  --muted:   #888888;
}
```

### Terminal / retro tech

```css
:root {
  --bg:      #0a0a0a;
  --surface: #111111;
  --primary: #33ff33;  /* green phosphor */
  --accent:  #ff5a00;
  --muted:   #6e6e6e;
}
```

Rules:
- ≤ 2 accent colors per composition.
- ~40% empty space. Crowded frames feel low-quality.
- Test text contrast: minimum 4.5:1 against background for readability.

## Layout templates

### Centered hero (product launch, announcement)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                     [HERO HEADLINE]                             │
│                     [SUBHEADLINE]                               │
│                                                                 │
│                       [CTA / LOGO]                              │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```css
.slide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
}
```

### Left-aligned editorial (interview overlay, lower third)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│  [HEADLINE]                                                     │
│  [Supporting text or metric]                                    │
│                                                                 │
│                             [Visual / illustration]            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Split (comparison, before/after)

```
┌──────────────────────────┬──────────────────────────────────────┐
│                          │                                      │
│  [Left panel]            │  [Right panel]                       │
│                          │                                      │
│  Label A                 │  Label B                             │
│                          │                                      │
└──────────────────────────┴──────────────────────────────────────┘
```

### Lower third (talking head overlay)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                                                                 │
│  ┌─────────────────────────────────────────┐                   │
│  │  NAME / TITLE                           │                   │
│  └─────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

Position at `bottom: 80px; left: 80px;` for standard broadcast safe area.

## Visual hierarchy rules

1. **One focal point per frame.** Everything else is context.
2. **Opacity layering:** primary elements 1.0, supporting 0.6, structural 0.2.
3. **Breathing room:** padding ≥ 80px from canvas edge at 1080p.
4. **Never center body text beyond 900px line width** — too wide to read comfortably.
5. **Avoid gradients that cross the video codec's banding threshold** — large subtle gradients band badly in h264. Use dithered noise or solid colors.

## CSS reset for video

```css
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  width: 1920px;
  height: 1080px;
  overflow: hidden;
  /* set background-color explicitly — no browser default */
  background: var(--bg);
}

.slide {
  width: 1920px;
  height: 1080px;
  position: relative;
  overflow: hidden;
}
```

## Transparent WebM overlays

When producing an overlay that composites over existing footage:
- Set `background: transparent` on body and `.slide`.
- Use `--format webm` in the render command.
- The EDL's `render.py` will blend using `overlay` filter.
- Avoid large transparent areas with subtle gradients — alpha channel compression can introduce artifacts. Prefer hard edges.

## Motion graphic principles (for <10s unnarrated clips)

- **One idea per composition.** Don't combine multiple messages.
- **Front-load the reveal.** Start motion within the first 0.5s.
- **Hold the final frame ≥ 1s.** Give the viewer time to read.
- **Loop-friendliness:** if the clip may loop, make the last frame visually close to the first.
- **No text smaller than 36px at 1080p** — social platforms may compress further.
