export type Transition = { type: string; duration?: number } | null | undefined;

export interface VideoClip {
  id: string;
  source: string;
  in: number;
  out: number;
  grade?: string;
  note?: string;
  transitionOut?: Transition;
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
  };
}

export interface OverlayClip {
  id: string;
  start: number;
  duration: number;
  file: string;
}

export type TrackType = "video" | "text" | "overlay";

export interface Track {
  id: string;
  type: TrackType;
  name: string;
  clips: (VideoClip | TextClip | OverlayClip)[];
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
