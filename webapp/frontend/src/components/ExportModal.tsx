import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ExportStatus, SubtitleStyle } from "../types";
import { useEditor } from "../store";

const SUBTITLE_LANGUAGES: { code: string; label: string }[] = [
  { code: "original", label: "Original (no translation)" },
  { code: "Portuguese", label: "Português" },
  { code: "English", label: "English" },
  { code: "Spanish", label: "Español" },
  { code: "French", label: "Français" },
  { code: "Italian", label: "Italiano" },
  { code: "German", label: "Deutsch" },
  { code: "Japanese", label: "日本語" },
];

export default function ExportModal({ onClose }: { onClose: () => void }) {
  const saveNow = useEditor((s) => s.saveNow);
  const [mode, setMode] = useState<"preview" | "final">("preview");
  const [buildSubtitles, setBuildSubtitles] = useState(true);
  const [subStyle, setSubStyle] = useState<SubtitleStyle>({
    font_size: 18, color: "#FFFFFF", position: "bottom", background: false, uppercase: true,
  });
  const [subLanguage, setSubLanguage] = useState("original");
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
    const { job_id } = await api.startExport(mode, buildSubtitles, subStyle, subLanguage);
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
  const [edlBusy, setEdlBusy] = useState(false);

  async function exportEdl() {
    setEdlBusy(true);
    try {
      await saveNow();
      window.location.href = "/api/export-edl";
    } finally {
      setEdlBusy(false);
    }
  }

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
            {buildSubtitles && (
              <div style={{ background: "var(--bg-2)", borderRadius: 8, padding: 12, marginBottom: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="field">
                  <label>Subtitle language</label>
                  <select value={subLanguage} onChange={(e) => setSubLanguage(e.target.value)}>
                    {SUBTITLE_LANGUAGES.map((l) => (
                      <option key={l.code} value={l.code}>{l.label}</option>
                    ))}
                  </select>
                  {subLanguage !== "original" && (
                    <div className="dur" style={{ marginTop: 4 }}>
                      Translated with Claude — timing follows sentence boundaries, not
                      exact per-word sync (translation changes word count/order).
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <div className="field" style={{ flex: 1 }}>
                    <label>Size ({subStyle.font_size}px)</label>
                    <input
                      type="range" min={12} max={36} step={1}
                      value={subStyle.font_size}
                      onChange={(e) => setSubStyle((s) => ({ ...s, font_size: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="field">
                    <label>Color</label>
                    <input
                      type="color"
                      value={subStyle.color}
                      onChange={(e) => setSubStyle((s) => ({ ...s, color: e.target.value }))}
                    />
                  </div>
                </div>
                <div className="field">
                  <label>Position</label>
                  <select
                    value={subStyle.position}
                    onChange={(e) => setSubStyle((s) => ({ ...s, position: e.target.value as SubtitleStyle["position"] }))}
                  >
                    <option value="bottom">Bottom (safe zone for Reels/Shorts UI)</option>
                    <option value="middle">Middle</option>
                    <option value="top">Top</option>
                  </select>
                </div>
                <div className="field checkbox-row">
                  <input
                    type="checkbox" checked={!!subStyle.background}
                    onChange={(e) => setSubStyle((s) => ({ ...s, background: e.target.checked }))}
                  />
                  Background box behind text
                </div>
                <div className="field checkbox-row">
                  <input
                    type="checkbox" checked={subStyle.uppercase !== false}
                    onChange={(e) => setSubStyle((s) => ({ ...s, uppercase: e.target.checked }))}
                  />
                  UPPERCASE
                </div>
              </div>
            )}
            <div className="actions">
              <button className="ghost" onClick={onClose}>Cancel</button>
              <button className="primary" onClick={start}>Start export</button>
            </div>
            <div className="dur" style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              Editing in DaVinci Resolve, Premiere Pro, or Final Cut instead? Export a CMX3600 EDL
              with the cut order and exact in/out points — grades, transitions, text, Ken Burns,
              speed and music don't carry over (the exported file notes what to redo in the NLE).
            </div>
            <div className="actions">
              <button className="ghost" onClick={exportEdl} disabled={edlBusy}>
                {edlBusy ? "Exportando…" : "Export EDL (DaVinci / Premiere / FCP)"}
              </button>
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
