import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useEditor } from "../store";
import type { Transcript, TranscriptWord, VideoClip } from "../types";

function remainingRanges(clip: VideoClip, removedWords: TranscriptWord[]) {
  const ordered = [...removedWords].sort((a, b) => a.start - b.start);
  const removed: { start: number; end: number }[] = [];
  for (const word of ordered) {
    const start = Math.max(clip.in, word.start - 0.03);
    const end = Math.min(clip.out, word.end + 0.03);
    const last = removed[removed.length - 1];
    if (last && start - last.end <= 0.18) last.end = Math.max(last.end, end);
    else if (end > start) removed.push({ start, end });
  }
  const keep: { in: number; out: number }[] = [];
  let cursor = clip.in;
  for (const range of removed) {
    if (range.start > cursor + 0.08) keep.push({ in: cursor, out: range.start });
    cursor = Math.max(cursor, range.end);
  }
  if (cursor < clip.out - 0.08) keep.push({ in: cursor, out: clip.out });
  return keep;
}

export default function TranscriptModal({ clip, onClose }: { clip: VideoClip; onClose: () => void }) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const setPlayhead = useEditor((s) => s.setPlayhead);
  const setPlaying = useEditor((s) => s.setPlaying);
  const applyCleanup = useEditor((s) => s.applyCleanup);
  const timeline = useEditor((s) => s.timeline);

  useEffect(() => {
    api.transcript(clip.source).then(setTranscript).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [clip.source]);

  const words = useMemo(() => transcript?.words.filter((w) => w.start < clip.out && w.end > clip.in) || [], [transcript, clip]);

  function seek(word: TranscriptWord) {
    const clips = (timeline?.tracks.find((t) => t.type === "video")?.clips || []) as VideoClip[];
    let timelineStart = 0;
    for (const item of clips) {
      if (item.id === clip.id) break;
      timelineStart += (item.out - item.in) / (item.speed || 1);
    }
    setPlayhead(timelineStart + (word.start - clip.in) / (clip.speed || 1));
    setPlaying(false);
  }

  function toggle(word: TranscriptWord) {
    seek(word);
    setRemoved((current) => {
      const next = new Set(current);
      if (next.has(word.id)) next.delete(word.id); else next.add(word.id);
      return next;
    });
  }

  function apply() {
    if (!transcript || !removed.size) return;
    const keep = remainingRanges(clip, words.filter((word) => removed.has(word.id)));
    if (!keep.length) {
      setError("A seleção removeria o clipe inteiro. Deixe pelo menos um trecho.");
      return;
    }
    applyCleanup(clip.id, keep);
    onClose();
  }

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal transcript-modal">
        <h2>Editar pela transcrição</h2>
        <p className="transcript-help">Clique nas palavras que deseja cortar. A alteração só será aplicada após sua confirmação e poderá ser desfeita.</p>
        {error && <p className="update-error">{error}</p>}
        {!transcript && !error && <div className="transcript-loading">Carregando transcrição…</div>}
        {transcript && !words.length && <div className="transcript-loading">Não há palavras transcritas neste trecho.</div>}
        <div className="transcript-words">
          {words.map((word) => (
            <button key={word.id} className={removed.has(word.id) ? "transcript-word removed" : "transcript-word"}
              onClick={() => toggle(word)} title={`${word.start.toFixed(2)}s`}>
              {word.text}
            </button>
          ))}
        </div>
        <div className="actions">
          <span className="transcript-count">{removed.size} palavra(s) selecionada(s)</span>
          <button className="ghost" onClick={onClose}>Cancelar</button>
          <button className="primary" disabled={!removed.size} onClick={apply}>Aplicar cortes</button>
        </div>
      </div>
    </div>
  );
}
