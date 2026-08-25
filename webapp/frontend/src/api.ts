import type { ExportStatus, GradePreset, MediaItem, Timeline } from "./types";

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
  startExport: (mode: "preview" | "final", buildSubtitles: boolean) =>
    fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, build_subtitles: buildSubtitles }),
    }).then((r) => json<{ job_id: string }>(r)),
  exportStatus: (jobId: string) => fetch(`/api/export/${jobId}`).then((r) => json<ExportStatus>(r)),
};
