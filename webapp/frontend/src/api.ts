import type { AudioItem, ExportStatus, GradePreset, JobStatus, MediaItem, Sticker, Timeline } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
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
  uploadMedia: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return fetch("/api/media/upload", { method: "POST", body }).then((r) =>
      json<{ name: string; filename: string; kind: "video" | "audio" }>(r)
    );
  },
  startExport: (mode: "preview" | "final", buildSubtitles: boolean) =>
    fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, build_subtitles: buildSubtitles }),
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
  autoEdit: (brief: string, targetDuration?: number) =>
    fetch("/api/ai/auto-edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, target_duration: targetDuration ?? null }),
    }).then((r) => json<{ job_id: string }>(r)),
  jobStatus: <T = any>(jobId: string) => fetch(`/api/jobs/${jobId}`).then((r) => json<JobStatus<T>>(r)),
};
