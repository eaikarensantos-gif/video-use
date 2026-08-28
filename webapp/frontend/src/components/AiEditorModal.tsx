import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AiProviderStatus, AiTextOverlay, AutoEditRange, JobStatus } from "../types";
import { useEditor } from "../store";

/** Real AI auto-edit: sends a brief + the transcribed footage to the configured provider and
 * proposes a cut list. Nothing is written to the timeline until the user
 * reviews the proposal and explicitly clicks "Apply" — this mirrors the
 * chat flow's "propose a strategy, then wait for confirmation" rule. */
export default function AiEditorModal({ onClose }: { onClose: () => void }) {
  const media = useEditor((s) => s.media);
  const applyAutoEditRanges = useEditor((s) => s.applyAutoEditRanges);
  const applyAiTextOverlays = useEditor((s) => s.applyAiTextOverlays);
  const playhead = useEditor((s) => s.playhead);
  const totalDuration = useEditor((s) => s.totalDuration);

  const [brief, setBrief] = useState("");
  const [targetDuration, setTargetDuration] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus<{ ranges: AutoEditRange[]; text_overlays: AiTextOverlay[] }> | null>(null);
  const [ranges, setRanges] = useState<AutoEditRange[] | null>(null);
  const [textOverlays, setTextOverlays] = useState<AiTextOverlay[]>([]);
  const [included, setIncluded] = useState<Set<number>>(new Set());
  const [includedText, setIncludedText] = useState<Set<number>>(new Set());
  const [provider, setProvider] = useState<AiProviderStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const untranscribed = media.filter((m) => !m.transcribed);

  useEffect(() => {
    api.aiStatus().then(setProvider).catch(() => setProvider({ provider: null, model: null, configured: false }));
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [status?.log.length]);

  async function generate() {
    const dur = targetDuration.trim() ? Number(targetDuration) : undefined;
    const { job_id } = await api.autoEdit(brief, dur, playhead, totalDuration());
    setJobId(job_id);
    pollRef.current = setInterval(async () => {
      const s = await api.jobStatus<{ ranges: AutoEditRange[]; text_overlays: AiTextOverlay[] }>(job_id);
      setStatus(s);
      if (s.status === "done") {
        if (pollRef.current) clearInterval(pollRef.current);
        const r = s.result?.ranges ?? [];
        const texts = s.result?.text_overlays ?? [];
        setRanges(r);
        setTextOverlays(texts);
        setIncluded(new Set(r.map((_, i) => i)));
        setIncludedText(new Set(texts.map((_, i) => i)));
      } else if (s.status === "error") {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 1000);
  }

  function toggle(i: number) {
    setIncluded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }

  function toggleText(i: number) {
    setIncludedText((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }

  function apply() {
    if (!ranges) return;
    const chosen = ranges.filter((_, i) => included.has(i));
    const chosenText = textOverlays.filter((_, i) => includedText.has(i));
    if (chosen.length) applyAutoEditRanges(chosen);
    if (chosenText.length) applyAiTextOverlays(chosenText);
    onClose();
  }

  const running = status?.status === "running" || status?.status === "queued";
  const fmt = (s: number) => `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget && !running) onClose(); }}>
      <div className="modal wide">
        <h2>AI auto-edit</h2>
        <div className={provider?.configured ? "ai-provider-status ok" : "ai-provider-status"}>
          {provider?.configured
            ? `IA: ${provider.provider === "openai" ? "OpenAI" : "Anthropic"} · ${provider.model}`
            : "Nenhuma API configurada. Adicione OPENAI_API_KEY ao arquivo .env e reinicie o app."}
        </div>

        {!jobId && (
          <>
            {untranscribed.length > 0 && (
              <div className="dur" style={{ color: "var(--danger)", marginBottom: 10 }}>
                {untranscribed.length} clipe(s) sem transcrição. Isso não impede textos e elementos visuais,
                mas cortes baseados na fala exigem transcrição.
              </div>
            )}
            <div className="field">
              <label>Brief — describe the edit you want</label>
              <textarea
                rows={5}
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="e.g. Build a 60s highlight reel focused on the product demo, upbeat tone, cut the intro small talk."
              />
            </div>
            <div className="field">
              <label>Target duration (seconds, optional)</label>
              <input
                type="number"
                min={1}
                value={targetDuration}
                onChange={(e) => setTargetDuration(e.target.value)}
                placeholder="e.g. 60"
              />
            </div>
            <div className="actions">
              <button className="ghost" onClick={onClose}>Cancel</button>
              <button className="primary" onClick={generate} disabled={!brief.trim() || !provider?.configured}>
                Propor edição
              </button>
            </div>
          </>
        )}

        {jobId && !ranges && (
          <>
            <div style={{ fontSize: 12, color: "var(--text-1)", marginBottom: 8 }}>
              Status: <strong>{status?.status ?? "starting…"}</strong>
            </div>
            <div className="progress-bar">
              <div className="fill" style={{ width: running ? "60%" : status?.status === "done" ? "100%" : "0%" }} />
            </div>
            <div className="log" ref={logRef}>
              {(status?.log ?? []).join("\n") || "pedindo à IA para analisar as transcrições…"}
            </div>
            {status?.status === "error" && (
              <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>Error: {status.error}</div>
            )}
            <div className="actions">
              <button className="ghost" onClick={onClose} disabled={running}>Close</button>
            </div>
          </>
        )}

        {ranges && (
          <>
            <div className="dur" style={{ marginBottom: 6 }}>
              {ranges.length + textOverlays.length} operação(ões) proposta(s) — revise antes de aplicar.
            </div>
            <div className="cut-list">
              {ranges.map((r, i) => (
                <label key={i} className="cut-row">
                  <input type="checkbox" checked={included.has(i)} onChange={() => toggle(i)} />
                  <div className="cut-row-body">
                    <div className="cut-beat">{r.beat || r.source}</div>
                    <div className="cut-meta">
                      {r.source} · {fmt(r.start)}–{fmt(r.end)}
                    </div>
                    {r.reason && <div className="cut-reason">{r.reason}</div>}
                  </div>
                </label>
              ))}
              {textOverlays.map((item, i) => (
                <label key={`text-${i}`} className="cut-row">
                  <input type="checkbox" checked={includedText.has(i)} onChange={() => toggleText(i)} />
                  <div className="cut-row-body">
                    <div className="cut-beat">Texto na tela: “{item.text}”</div>
                    <div className="cut-meta">
                      {fmt(item.start)} · {item.duration.toFixed(1)}s · {item.position}
                    </div>
                    {item.reason && <div className="cut-reason">{item.reason}</div>}
                  </div>
                </label>
              ))}
            </div>
            <div className="actions">
              <button className="ghost" onClick={onClose}>Discard</button>
              <button className="primary" onClick={apply} disabled={included.size + includedText.size === 0}>
                Aplicar {included.size + includedText.size} operação(ões)
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
