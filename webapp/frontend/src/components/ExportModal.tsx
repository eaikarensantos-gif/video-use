import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ExportStatus } from "../types";
import { useEditor } from "../store";

export default function ExportModal({ onClose }: { onClose: () => void }) {
  const saveNow = useEditor((s) => s.saveNow);
  const [mode, setMode] = useState<"preview" | "final">("preview");
  const [buildSubtitles, setBuildSubtitles] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<ExportStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [status?.log.length]);

  async function start() {
    await saveNow();
    const { job_id } = await api.startExport(mode, buildSubtitles);
    setJobId(job_id);
    pollRef.current = setInterval(async () => {
      const s = await api.exportStatus(job_id);
      setStatus(s);
      if (s.status === "done" || s.status === "error") {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 800);
  }

  const running = status?.status === "running" || status?.status === "queued";

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget && !running) onClose(); }}>
      <div className="modal">
        <h2>Export</h2>
        {!jobId && (
          <>
            <div className="field">
              <label>Quality</label>
              <select value={mode} onChange={(e) => setMode(e.target.value as any)}>
                <option value="preview">Preview — fast, 720p, no loudness pass</option>
                <option value="final">Final — 1080p, loudness normalized</option>
              </select>
            </div>
            <div className="field checkbox-row">
              <input type="checkbox" checked={buildSubtitles} onChange={(e) => setBuildSubtitles(e.target.checked)} />
              Burn subtitles from source transcripts (if available)
            </div>
            <div className="actions">
              <button className="ghost" onClick={onClose}>Cancel</button>
              <button className="primary" onClick={start}>Start export</button>
            </div>
          </>
        )}
        {jobId && (
          <>
            <div style={{ fontSize: 12, color: "var(--text-1)", marginBottom: 8 }}>
              Status: <strong>{status?.status ?? "starting…"}</strong>
            </div>
            <div className="progress-bar">
              <div className="fill" style={{ width: status?.status === "done" ? "100%" : running ? "60%" : "0%" }} />
            </div>
            <div className="log" ref={logRef}>
              {(status?.log ?? []).join("\n") || "waiting for render output…"}
            </div>
            {status?.status === "error" && (
              <div style={{ color: "var(--danger)", fontSize: 12 }}>Error: {status.error}</div>
            )}
            <div className="actions">
              <button className="ghost" onClick={onClose} disabled={running}>Close</button>
              {status?.status === "done" && status.output_url && (
                <a className="primary" style={{ textDecoration: "none", padding: "6px 10px", borderRadius: 6 }} href={status.output_url} download>
                  Download
                </a>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
