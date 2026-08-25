import { create } from "zustand";
import { api } from "./api";
import type { MediaItem, TextClip, Timeline, Track, VideoClip } from "./types";
import { totalVideoDuration } from "./layout";

let idCounter = 0;
function newId(prefix: string): string {
  idCounter += 1;
  return `${prefix}_${Date.now().toString(36)}_${idCounter}`;
}

interface Selection {
  trackId: string;
  clipId: string;
}

interface EditorState {
  timeline: Timeline | null;
  media: MediaItem[];
  loading: boolean;
  saving: boolean;
  dirty: boolean;
  selection: Selection | null;
  playhead: number;
  playing: boolean;
  zoom: number; // px per second
  history: Timeline[];
  future: Timeline[];

  load: () => Promise<void>;
  saveNow: () => Promise<void>;
  scheduleSave: () => void;

  setPlayhead: (t: number) => void;
  setPlaying: (p: boolean) => void;
  setZoom: (z: number) => void;
  select: (sel: Selection | null) => void;

  videoTrack: () => Track | undefined;
  totalDuration: () => number;

  appendVideoClip: (source: string, inPoint: number, outPoint: number) => void;
  updateVideoClip: (clipId: string, patch: Partial<VideoClip>) => void;
  removeClip: (trackId: string, clipId: string) => void;
  splitVideoClipAt: (time: number) => void;
  moveVideoClip: (clipId: string, toIndex: number) => void;

  addTextClip: (start: number, duration: number) => void;
  updateTextClip: (clipId: string, patch: Partial<TextClip>) => void;
  updateOverlayClip: (clipId: string, patch: Partial<import("./types").OverlayClip>) => void;

  undo: () => void;
  redo: () => void;
}

function withHistory(get: () => EditorState, set: (s: Partial<EditorState>) => void, mutate: (t: Timeline) => Timeline) {
  const cur = get().timeline;
  if (!cur) return;
  const next = mutate(structuredClone(cur));
  const history = [...get().history, cur].slice(-50);
  set({ timeline: next, history, future: [], dirty: true });
  get().scheduleSave();
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

export const useEditor = create<EditorState>((set, get) => ({
  timeline: null,
  media: [],
  loading: false,
  saving: false,
  dirty: false,
  selection: null,
  playhead: 0,
  playing: false,
  zoom: 80,
  history: [],
  future: [],

  load: async () => {
    set({ loading: true });
    const [timeline, media] = await Promise.all([api.timeline(), api.media()]);
    set({ timeline, media, loading: false, history: [], future: [], dirty: false });
  },

  saveNow: async () => {
    const { timeline } = get();
    if (!timeline) return;
    set({ saving: true });
    try {
      await api.saveTimeline(timeline);
      set({ dirty: false });
    } finally {
      set({ saving: false });
    }
  },

  scheduleSave: () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      get().saveNow();
    }, 600);
  },

  setPlayhead: (t) => set({ playhead: Math.max(0, t) }),
  setPlaying: (p) => set({ playing: p }),
  setZoom: (z) => set({ zoom: Math.min(400, Math.max(10, z)) }),
  select: (sel) => set({ selection: sel }),

  videoTrack: () => get().timeline?.tracks.find((t) => t.type === "video"),
  totalDuration: () => {
    const vt = get().videoTrack();
    return vt ? totalVideoDuration(vt.clips as VideoClip[]) : 0;
  },

  appendVideoClip: (source, inPoint, outPoint) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const clip: VideoClip = { id: newId("clip"), source, in: inPoint, out: outPoint, grade: "none" };
      track.clips.push(clip);
      return tl;
    });
  },

  updateVideoClip: (clipId, patch) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const clip = track.clips.find((c) => c.id === clipId) as VideoClip | undefined;
      if (clip) Object.assign(clip, patch);
      return tl;
    });
  },

  removeClip: (trackId, clipId) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.id === trackId);
      if (!track) return tl;
      track.clips = track.clips.filter((c) => c.id !== clipId);
      return tl;
    });
    if (get().selection?.clipId === clipId) set({ selection: null });
  },

  splitVideoClipAt: (time) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const clips = track.clips as VideoClip[];
      let cumulative = 0;
      for (let i = 0; i < clips.length; i++) {
        const c = clips[i];
        const dur = c.out - c.in;
        const overlapBefore = i > 0 ? overlapFor(clips[i - 1]) : 0;
        const start = cumulative - overlapBefore;
        const end = start + dur;
        if (time > start + 0.02 && time < end - 0.02) {
          const cutAtSource = c.in + (time - start);
          const left: VideoClip = { ...c, id: newId("clip"), out: cutAtSource, transitionOut: undefined };
          const right: VideoClip = { ...c, id: newId("clip"), in: cutAtSource };
          clips.splice(i, 1, left, right);
          break;
        }
        cumulative = end;
      }
      return tl;
    });
  },

  moveVideoClip: (clipId, toIndex) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const clips = track.clips as VideoClip[];
      const from = clips.findIndex((c) => c.id === clipId);
      if (from === -1) return tl;
      const [item] = clips.splice(from, 1);
      clips.splice(Math.max(0, Math.min(clips.length, toIndex)), 0, item);
      return tl;
    });
  },

  addTextClip: (start, duration) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "text");
      if (!track) return tl;
      const clip: TextClip = {
        id: newId("text"),
        start,
        duration,
        text: "Your text",
        style: { position: "bottom", font_size: 54, color: "white", background: true },
      };
      track.clips.push(clip);
      return tl;
    });
  },

  updateTextClip: (clipId, patch) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "text");
      if (!track) return tl;
      const clip = track.clips.find((c) => c.id === clipId) as TextClip | undefined;
      if (clip) Object.assign(clip, patch, { style: { ...clip.style, ...patch.style } });
      return tl;
    });
  },

  updateOverlayClip: (clipId, patch) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "overlay");
      if (!track) return tl;
      const clip = track.clips.find((c) => c.id === clipId) as any;
      if (clip) Object.assign(clip, patch);
      return tl;
    });
  },

  undo: () => {
    const { history, timeline } = get();
    if (!history.length || !timeline) return;
    const prev = history[history.length - 1];
    set({ timeline: prev, history: history.slice(0, -1), future: [timeline, ...get().future], dirty: true });
    get().scheduleSave();
  },

  redo: () => {
    const { future, timeline } = get();
    if (!future.length || !timeline) return;
    const next = future[0];
    set({ timeline: next, future: future.slice(1), history: [...get().history, timeline], dirty: true });
    get().scheduleSave();
  },
}));

function overlapFor(clip: VideoClip): number {
  const trans = clip.transitionOut;
  if (!trans || trans.type === "cut") return 0;
  return trans.duration ?? 0.4;
}
