# HyperFrames Registry Reference

The HyperFrames registry provides pre-built catalog blocks — transitions, overlays, and data visualizations — installable into any slot.

## Installing blocks

```bash
# Single block
npx --yes hyperframes add <block-name>

# Entire catalog
npx --yes hyperframes add --all

# List available blocks
npx --yes hyperframes add --list

# Agent skill (installs into ~/.claude/skills/ or ~/.codex/skills/)
npx --yes hyperframes add --skill <name>
```

Always install inside the slot directory, not the repo root. Blocks are copied into the slot so each slot is self-contained.

## Known catalog blocks

### Transitions

| Block | Effect | Duration |
|-------|--------|----------|
| `flash-through-white` | Quick white flash between scenes | 0.3s |
| `crossfade` | Opacity crossfade between slides | 0.5–1.0s |
| `slide-left` | New slide enters from right, old exits left | 0.6s |
| `zoom-through` | Push zoom into next scene | 0.5s |
| `dip-to-black` | Fade to black then fade up | 0.8s |

### Overlay cards

| Block | Use case |
|-------|---------|
| `instagram-follow` | Social follow call-to-action |
| `lower-third` | Speaker name + title bar |
| `badge` | Award / feature highlight badge |
| `countdown` | Animated countdown timer |
| `progress-bar` | Horizontal progress indicator |

### Data visualizations

| Block | Use case |
|-------|---------|
| `data-chart` | Animated bar/line chart from JSON data |
| `stat-counter` | Animated numeric counter with label |
| `comparison-table` | Animated side-by-side comparison |
| `pie-reveal` | Animated pie/donut chart |

## Using an installed block

After installing, a block adds HTML snippets and/or JS modules to the slot directory. The install command prints usage instructions. General pattern:

```html
<!-- After installing flash-through-white -->
<link rel="stylesheet" href="./blocks/flash-through-white/style.css">
<script src="./blocks/flash-through-white/index.js"></script>

<!-- In your GSAP timeline -->
<script>
  import { flashThroughWhite } from './blocks/flash-through-white/index.js';

  const tl = gsap.timeline({ paused: true });
  tl.add(flashThroughWhite('#slide-1', '#slide-2'), 3.0);

  if (window.__hf_play) window.__hf_play(tl);
  else tl.play();
</script>
```

Exact API varies per block — check the block's `README.md` after installation.

## Agent skills via registry

HyperFrames ships domain-specific agent skills installable via the registry:

| Skill | Description |
|-------|-------------|
| `hyperframes-core` | Composition contract and timing rules |
| `hyperframes-animation` | Motion rules and adapter patterns |
| `hyperframes-creative` | Design direction and narration |
| `hyperframes-media` | TTS, music, transcription, effects |
| `hyperframes-cli` | Dev loop tooling |
| `hyperframes-registry` | Component installation and authoring |

These are already covered by the `heygen-hyperframes` skill in `video-use`. Do not install them into slot directories — they would be redundant.

## Authoring a custom block

If you need a reusable component across multiple slots, author it as a block:

```
my-block/
  index.js      ← exported functions/classes
  style.css     ← scoped styles
  README.md     ← usage instructions
  preview.mp4   ← optional demo
```

Keep blocks self-contained. No imports from outside the block directory.
