import type { VideoClip } from "./types";

export interface ClipLayout {
  start: number;
  duration: number;
  end: number;
}

/** Mirrors helpers/render.py's build_base_with_transitions offset math:
 * a crossfade transition after a clip pulls the next clip's start earlier
 * by the transition duration (capped to 90% of either clip's length). */
export function computeVideoLayout(clips: VideoClip[]): ClipLayout[] {
  const layout: ClipLayout[] = [];
  let cumulative = 0;
  clips.forEach((c, i) => {
    const duration = Math.max(0, c.out - c.in) / (c.speed || 1);
    if (i === 0) {
      layout.push({ start: 0, duration, end: duration });
      cumulative = duration;
      return;
    }
    const prev = clips[i - 1];
    const trans = prev.transitionOut;
    const raw = trans && trans.type && trans.type !== "cut" ? trans.duration ?? 0.4 : 0;
    const overlap = Math.min(raw, duration * 0.9, (layout[i - 1]?.duration ?? duration) * 0.9);
    const start = Math.max(0, cumulative - overlap);
    layout.push({ start, duration, end: start + duration });
    cumulative = start + duration;
  });
  return layout;
}

export function totalVideoDuration(clips: VideoClip[]): number {
  const layout = computeVideoLayout(clips);
  return layout.length ? layout[layout.length - 1].end : 0;
}
