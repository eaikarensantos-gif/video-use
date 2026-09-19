# Remotion Motion Graphics Skill

Vendored from [haidrrrry/claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill) (MIT).

## What it does

Production rules and reference material for building React/Remotion video compositions that don't look like "generic AI video" — mandatory easing curves, multi-property entrances, staggering, a five-layer scene stack, Ken Burns on stills, breathing idle elements, and a render-inspect-fix verification loop.

## Use when

Building a Remotion animation overlay slot for `video-use` (see the "Animations" section of the root `SKILL.md`) — React composition with component state, reusable primitives, or when the user specifically asks for React/Remotion.

## Contents

- `SKILL.md` — non-negotiable rules + workflow
- `references/design-rules.md`, `references/motion-patterns.md` — deeper patterns
- `assets/theme.ts` — starting theme object (colors, easings, spring presets, fonts)

## Prerequisites

Node.js, a Remotion project scaffolded inside the animation slot directory (`npx create-video@latest` or local install) — see the root `SKILL.md`'s Remotion slot instructions.
