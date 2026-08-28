import { create } from "zustand";
import { api } from "./api";
import type { AudioClip, AudioItem, AutoEditRange, ClipTransform, MediaItem, OverlayClip, Sticker, TextClip, Timeline, Track, VideoClip } from "./types";
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
  stickers: Sticker[];
  audioFiles: AudioItem[];
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
  refreshLibraries: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
  uploading: boolean;
  deleteMediaItem: (name: string) => Promise<void>;
  deleteAudioItem: (name: string) => Promise<void>;
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
  updateVideoTransform: (clipId: string, patch: Partial<ClipTransform>) => void;
  applyCleanup: (clipId: string, keepRanges: { in: number; out: number }[]) => void;
  removeClip: (trackId: string, clipId: string) => void;
  splitVideoClipAt: (time: number) => void;
  moveVideoClip: (clipId: string, toIndex: number) => void;

  addTextClip: (start: number, duration: number) => void;
  updateTextClip: (clipId: string, patch: Partial<TextClip>) => void;
  updateOverlayClip: (clipId: string, patch: Partial<OverlayClip>) => void;
  addStickerClip: (file: string, start: number, duration: number) => void;
  addAudioClip: (file: string, start: number, duration: number) => void;
  updateAudioClip: (clipId: string, patch: Partial<AudioClip>) => void;

  applyAutoEditRanges: (ranges: AutoEditRange[]) => void;

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
  stickers: [],
  audioFiles: [],
  loading: false,
  uploading: false,
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
    const [timeline, media, stickers, audioFiles] = await Promise.all([
      api.timeline(), api.media(), api.stickers(), api.audioFiles(),
    ]);
    set({ timeline, media, stickers, audioFiles, loading: false, history: [], future: [], dirty: false });
  },

  refreshLibraries: async () => {
    const [media, audioFiles] = await Promise.all([api.media(), api.audioFiles()]);
    set({ media, audioFiles });
  },

  uploadFiles: async (files) => {
    set({ uploading: true });
    try {
      for (const file of files) {
        await api.uploadMedia(file).catch((err) => console.error("upload failed", file.name, err));
      }
      await get().refreshLibraries();
    } finally {
      set({ uploading: false });
    }
  },

  // Deletion happens server-side (file removed, timeline clips referencing
  // it stripped, edl.json resaved), so pull the fresh timeline back down
  // rather than trying to replay that mutation through withHistory — the
  // deleted source can't be un-deleted, so there's nothing meaningful to
  // undo back to.
  deleteMediaItem: async (name) => {
    await api.deleteMedia(name);
    const [timeline, media] = await Promise.all([api.timeline(), api.media()]);
    set({ timeline, media, history: [], future: [], dirty: false, selection: null });
  },

  deleteAudioItem: async (name) => {
    await api.deleteAudio(name);
    const [timeline, audioFiles] = await Promise.all([api.timeline(), api.audioFiles()]);
    set({ timeline, audioFiles, history: [], future: [], dirty: false, selection: null });
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

  updateVideoTransform: (clipId, patch) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const clip = track.clips.find((c) => c.id === clipId) as VideoClip | undefined;
      if (clip) clip.transform = { ...clip.transform, ...patch };
      return tl;
    });
  },

  applyCleanup: (clipId, keepRanges) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      const idx = track.clips.findIndex((c) => c.id === clipId);
      if (idx === -1 || !keepRanges.length) return tl;
      const original = track.clips[idx] as VideoClip;
      const fragments: VideoClip[] = keepRanges.map((r, i) => ({
        ...original,
        id: newId("clip"),
        in: r.in,
        out: r.out,
        transitionOut: i === keepRanges.length - 1 ? original.transitionOut : undefined,
      }));
      track.clips.splice(idx, 1, ...fragments);
      return tl;
    });
    if (get().selection?.clipId === clipId) set({ selection: null });
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
        const speed = c.speed || 1;
        const dur = (c.out - c.in) / speed;
        const overlapBefore = i > 0 ? overlapFor(clips[i - 1]) : 0;
        const start = cumulative - overlapBefore;
        const end = start + dur;
        if (time > start + 0.02 && time < end - 0.02) {
          const cutAtSource = c.in + (time - start) * speed;
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

  addStickerClip: (file, start, duration) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "overlay");
      if (!track) return tl;
      const clip: OverlayClip = {
        id: newId("sticker"),
        kind: "sticker",
        file,
        start,
        duration,
        x: 0.5,
        y: 0.5,
        scale: 0.3,
      };
      track.clips.push(clip);
      return tl;
    });
  },

  addAudioClip: (file, start, duration) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "audio");
      if (!track) return tl;
      const clip: AudioClip = { id: newId("audio"), file, start, duration, trimIn: 0, volume: 1, fadeIn: 0, fadeOut: 0 };
      track.clips.push(clip);
      return tl;
    });
  },

  updateAudioClip: (clipId, patch) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "audio");
      if (!track) return tl;
      const clip = track.clips.find((c) => c.id === clipId) as any;
      if (clip) Object.assign(clip, patch);
      return tl;
    });
  },

  applyAutoEditRanges: (ranges) => {
    withHistory(get, set, (tl) => {
      const track = tl.tracks.find((t) => t.type === "video");
      if (!track) return tl;
      track.clips = ranges.map(
        (r): VideoClip => ({
          id: newId("clip"),
          source: r.source,
          in: r.start,
          out: r.end,
          grade: "none",
          note: r.beat || undefined,
        })
      );
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
