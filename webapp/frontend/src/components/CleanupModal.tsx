import { useState } from "react";
import { api } from "../api";
import type { CleanupResult, VideoClip } from "../types";
import { useEditor } from "../store";

/** Detects silences and unambiguous filler words ("um", "uh"...) inside the
 * selected clip's current range, via the transcript, and proposes the
 * clip split into the sub-ranges left over after removing them. Nothing
 * is applied until the user reviews the list and clicks Apply — same
 * "propose, then confirm" shape as the AI editor. */
export default function CleanupModal({ clip, onClose }: { clip: VideoClip; onClose: () => void }) {
  const applyCleanup = useEditor((s) => s.applyCleanup);

  const [silenceThreshold, setSilenceThreshold] = useState(0.6);
  const [result, setResult] = useState<CleanupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function detect() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.detectCleanup(clip.source, clip.in, clip.out, silenceThreshold);
      setResult(r);
    } catch (err: any) {
      setError(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }

  function apply() {
    if (!result || !result.keep_ranges.length) return;
    applyCleanup(clip.id, result.keep_ranges);
    onClose();
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
  const removedCount = result?.spans.length ?? 0;
  const silenceCount = result?.spans.filter((s) => s.kind === "silence").length ?? 0;
  const fillerCount = result?.spans.filter((s) => s.kind === "filler").length ?? 0;
  const removedSeconds = result ? result.spans.reduce((sum, s) => sum + (s.end - s.start), 0) : 0;

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal wide">
        <h2>Limpar clipe (silêncios + gaguejo)</h2>

        {!result && (
          <>
            <div className="dur" style={{ marginBottom: 10 }}>
              Procura silêncios e interjeições isoladas ("um", "uh"...) na transcrição de
              <strong> {clip.source}</strong>, dentro do trecho usado por este clipe
              ({fmt(clip.in)}–{fmt(clip.out)}). Nada é aplicado até você revisar e clicar em Aplicar.
            </div>
            <div className="field">
              <label>Sensibilidade de silêncio ({silenceThreshold.toFixed(1)}s ou mais)</label>
              <input
                type="range" min={0.2} max={2} step={0.1} value={silenceThreshold}
                onChange={(e) => setSilenceThreshold(Number(e.target.value))}
              />
            </div>
            {error && <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>Erro: {error}</div>}
            <div className="actions">
              <button className="ghost" onClick={onClose}>Cancelar</button>
              <button className="primary" onClick={detect} disabled={loading}>
                {loading ? "Procurando…" : "Detectar"}
              </button>
            </div>
          </>
        )}

        {result && (
          <>
            <div className="dur" style={{ marginBottom: 6 }}>
              {removedCount === 0
                ? "Nada encontrado para remover neste trecho."
                : `${removedCount} corte(s) — ${silenceCount} silêncio(s), ${fillerCount} gaguejo(s) — ${removedSeconds.toFixed(1)}s no total.`}
            </div>
            {removedCount > 0 && (
              <div className="cut-list">
                {result.spans.map((s, i) => (
                  <div key={i} className="cut-row">
                    <div className="cut-row-body">
                      <div className="cut-beat">{s.kind === "silence" ? "Silêncio" : "Gaguejo"}</div>
                      <div className="cut-meta">
                        {fmt(s.start)}–{fmt(s.end)} · {s.label}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="actions">
              <button className="ghost" onClick={() => setResult(null)}>Voltar</button>
              <button className="ghost" onClick={onClose}>Cancelar</button>
              <button className="primary" onClick={apply} disabled={removedCount === 0}>
                Aplicar ({result.keep_ranges.length} pedaço(s))
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
