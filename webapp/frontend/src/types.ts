export type Transition = { type: string; duration?: number } | null | undefined;

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

export interface Timeline {
  version: number;
  canvas: { width: number; height: number; fps: number };
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

export function isVideoClip(c: any, track: Track): c is VideoClip {
  return track.type === "video";
}
export function isTextClip(c: any, track: Track): c is TextClip {
  return track.type === "text";
}
export function isOverlayClip(c: any, track: Track): c is OverlayClip {
  return track.type === "overlay";
}
