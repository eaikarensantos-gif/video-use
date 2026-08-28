export type Transition = { type: string; duration?: number } | null | undefined;

export interface ClipTransform {
  scale?: number;
  x?: number;
  y?: number;
  rotation?: number;
  opacity?: number;
  flip_h?: boolean;
  flip_v?: boolean;
}

export interface VideoClip {
  id: string;
  source: string;
  in: number;
  out: number;
  grade?: string;
  note?: string;
  transitionOut?: Transition;
  speed?: number;
  zoom?: { type: "in" | "out"; amount?: number } | null;
  transform?: ClipTransform;
}

export interface TextClip {
  id: string;
  start: number;
  duration: number;
  text: string;
  style?: {
    position?: "top" | "center" | "bottom";
    font_size?: number;
    color?: string;
    background?: boolean;
    background_color?: string;
    font?: string;
    animation?: "none" | "fade" | "slide_up";
  };
}

export interface OverlayClip {
  id: string;
  start: number;
  duration: number;
  file: string;
  kind?: "video" | "sticker";
  /** sticker only — center position as a fraction of frame size (0-1) */
  x?: number;
  y?: number;
  /** sticker only — width as a fraction of frame width (0-1) */
  scale?: number;
}

export interface Sticker {
  name: string;
  url: string;
}

export interface AudioClip {
  id: string;
  file: string;
  start: number;
  duration: number;
  trimIn?: number;
  volume?: number;
  fadeIn?: number;
  fadeOut?: number;
}

export type TrackType = "video" | "text" | "overlay" | "audio";

export interface Track {
  id: string;
  type: TrackType;
  name: string;
  clips: (VideoClip | TextClip | OverlayClip | AudioClip)[];
}

export interface SourceInfo {
  path: string;
  duration?: number;
  width?: number;
  height?: number;
  fps?: number;
  has_audio?: boolean;
}

export interface SubtitleStyle {
  font_size?: number;
  color?: string; // "#RRGGBB"
  position?: "bottom" | "top" | "middle";
  background?: boolean;
  uppercase?: boolean;
}

export interface Timeline {
  version: number;
  // width/height are null until the user picks an aspect ratio (Toolbar)
  // — until then, render.py fits each segment to its own source
  // orientation instead of a fixed frame, same as every project before
  // this existed.
  canvas: { width: number | null; height: number | null; fps: number };
  sources: Record<string, SourceInfo>;
  tracks: Track[];
  subtitles: { enabled: boolean; path: string };
}

export interface MediaItem {
  name: string;
  filename: string;
  duration?: number;
  width?: number;
  height?: number;
  fps?: number;
  has_audio?: boolean;
  thumbnail_url: string;
  stream_url: string;
  transcribed: boolean;
}

export interface AudioItem {
  name: string;
  filename: string;
  duration?: number;
  stream_url: string;
}

export interface GradePreset {
  id: string;
  label: string;
  description: string;
}

export interface ExportStatus {
  status: "queued" | "running" | "done" | "error";
  log: string[];
  error?: string | null;
  output_url?: string;
}

export interface AutoEditRange {
  source: string;
  start: number;
  end: number;
  beat: string;
  reason: string;
}

export interface CleanupSpan {
  start: number;
  end: number;
  kind: "silence" | "filler";
  label: string;
}

export interface CleanupResult {
  spans: CleanupSpan[];
  keep_ranges: { in: number; out: number }[];
}

export interface TranscriptWord {
  id: string;
  text: string;
  start: number;
  end: number;
  speaker?: string | null;
}

export interface Transcript {
  source: string;
  language?: string | null;
  text: string;
  words: TranscriptWord[];
}

export interface JobStatus<T = any> {
  status: "queued" | "running" | "done" | "error";
  log: string[];
  error?: string | null;
  result: T | null;
}

export interface UpdateInfo {
  current_version: string;
  latest_version?: string;
  available: boolean;
  release_name?: string;
  notes?: string;
  published_at?: string;
  download_url?: string;
  size?: number;
  digest?: string;
  error?: string;
}

export function isVideoClip(c: any, track: Track): c is VideoClip {
  return track.type === "video";
}
export function isTextClip(c: any, track: Track): c is TextClip {
  return track.type === "text";
}
export function isOverlayClip(c: any, track: Track): c is OverlayClip {
  return track.type === "overlay";
}
