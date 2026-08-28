import type { AiProviderStatus, AudioItem, CleanupResult, ExportStatus, GradePreset, JobStatus, MediaItem, Sticker, SubtitleStyle, Timeline, Transcript, UpdateInfo } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  checkUpdate: () => fetch("/api/update/check").then((r) => json<UpdateInfo>(r)),
  downloadUpdate: (downloadUrl: string, digest?: string) =>
    fetch("/api/update/download", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Video-Use-Update-Intent": "confirmed" },
      body: JSON.stringify({ download_url: downloadUrl, digest: digest || null }),
    }).then((r) => json<{ job_id: string }>(r)),
  installUpdate: () =>
    fetch("/api/update/install", { method: "POST", headers: { "X-Video-Use-Update-Intent": "confirmed" } }).then((r) => json<{ ok: boolean; message: string }>(r)),
  media: () => fetch("/api/media").then((r) => json<MediaItem[]>(r)),
  waveform: (name: string) => fetch(`/api/media/${encodeURIComponent(name)}/waveform`).then((r) => json<number[]>(r)),
  timeline: () => fetch("/api/timeline").then((r) => json<Timeline>(r)),
  saveTimeline: (timeline: Timeline) =>
    fetch("/api/timeline", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(timeline),
    }).then((r) => json<Timeline>(r)),
  gradePresets: () => fetch("/api/presets/grades").then((r) => json<GradePreset[]>(r)),
  transitionPresets: () => fetch("/api/presets/transitions").then((r) => json<string[]>(r)),
  stickers: () => fetch("/api/stickers").then((r) => json<Sticker[]>(r)),
  audioFiles: () => fetch("/api/audio").then((r) => json<AudioItem[]>(r)),
  audioWaveform: (name: string) => fetch(`/api/audio/${encodeURIComponent(name)}/waveform`).then((r) => json<number[]>(r)),
  deleteMedia: (name: string) =>
    fetch(`/api/media/${encodeURIComponent(name)}`, { method: "DELETE" }).then((r) =>
      json<{ deleted: string; removed_clips: number }>(r)
    ),
  deleteAudio: (name: string) =>
    fetch(`/api/audio/${encodeURIComponent(name)}`, { method: "DELETE" }).then((r) =>
      json<{ deleted: string; removed_clips: number }>(r)
    ),
  uploadMedia: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return fetch("/api/media/upload", { method: "POST", body }).then((r) =>
      json<{ name: string; filename: string; kind: "video" | "audio" | "image" }>(r)
    );
  },
  startExport: (
    mode: "preview" | "final",
    buildSubtitles: boolean,
    subtitleStyle?: SubtitleStyle,
    subtitleLanguage?: string
  ) =>
    fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        build_subtitles: buildSubtitles,
        subtitle_style: subtitleStyle ?? null,
        subtitle_language: subtitleLanguage ?? null,
      }),
    }).then((r) => json<{ job_id: string }>(r)),
  exportStatus: (jobId: string) => fetch(`/api/export/${jobId}`).then((r) => json<ExportStatus>(r)),
  transcribeMedia: (name: string, language?: string) =>
    fetch(`/api/media/${encodeURIComponent(name)}/transcribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: language || null }),
    }).then((r) => json<{ job_id: string }>(r)),
  transcribeAll: () =>
    fetch("/api/media/transcribe-all", { method: "POST" }).then((r) => json<{ job_id: string }>(r)),
  transcript: (name: string) =>
    fetch(`/api/media/${encodeURIComponent(name)}/transcript`).then((r) => json<Transcript>(r)),
  autoEdit: (brief: string, targetDuration?: number) =>
    fetch("/api/ai/auto-edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, target_duration: targetDuration ?? null }),
    }).then((r) => json<{ job_id: string }>(r)),
  aiStatus: () => fetch("/api/ai/status").then((r) => json<AiProviderStatus>(r)),
  jobStatus: <T = any>(jobId: string) => fetch(`/api/jobs/${jobId}`).then((r) => json<JobStatus<T>>(r)),
  detectCleanup: (name: string, clipIn: number, clipOut: number, silenceThreshold = 0.6) =>
    fetch(`/api/media/${encodeURIComponent(name)}/detect-cleanup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clip_in: clipIn, clip_out: clipOut, silence_threshold: silenceThreshold }),
    }).then((r) => json<CleanupResult>(r)),
};
