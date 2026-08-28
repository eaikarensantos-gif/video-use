import { useRef, useState } from "react";
import { api } from "../api";
import { useEditor } from "../store";
import { IconCheck, IconMusic, IconTrash, IconUpload, IconVideo } from "../icons";

/** Polls a transcription job until it's done/errored, then refreshes the
 * media list so `transcribed` badges update. Returns a per-name busy set
 * and any per-name error, plus a "busy all" flag for the bulk action. */
function useTranscribeJobs() {
  const refreshLibraries = useEditor((s) => s.refreshLibraries);
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busyAll, setBusyAll] = useState(false);
  const [allError, setAllError] = useState<string | null>(null);

  function poll(jobId: string, onDone: () => void, onError: (msg: string) => void) {
    const interval = setInterval(async () => {
      const s = await api.jobStatus(jobId).catch(() => null);
      if (!s) return;
      if (s.status === "done") {
        clearInterval(interval);
        onDone();
      } else if (s.status === "error") {
        clearInterval(interval);
        onError(s.error || "transcription failed");
      }
    }, 1000);
  }

  async function transcribeOne(name: string) {
    setErrors((e) => { const n = { ...e }; delete n[name]; return n; });
    setBusy((b) => new Set(b).add(name));
    try {
      const { job_id } = await api.transcribeMedia(name);
      poll(
        job_id,
        () => { setBusy((b) => { const n = new Set(b); n.delete(name); return n; }); refreshLibraries(); },
        (msg) => { setBusy((b) => { const n = new Set(b); n.delete(name); return n; }); setErrors((e) => ({ ...e, [name]: msg })); }
      );
    } catch (err: any) {
      setBusy((b) => { const n = new Set(b); n.delete(name); return n; });
      setErrors((e) => ({ ...e, [name]: String(err?.message || err) }));
    }
  }

  async function transcribeAll() {
    setBusyAll(true);
    setAllError(null);
    try {
      const { job_id } = await api.transcribeAll();
      poll(
        job_id,
        () => { setBusyAll(false); refreshLibraries(); },
        (msg) => { setBusyAll(false); setAllError(msg); refreshLibraries(); }
      );
    } catch (err: any) {
      setBusyAll(false);
      setAllError(String(err?.message || err));
    }
  }

  return { busy, errors, busyAll, allError, transcribeOne, transcribeAll };
}

function fmtDur(s?: number): string {
  if (!s && s !== 0) return "";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function MediaBin() {
  const media = useEditor((s) => s.media);
  const stickers = useEditor((s) => s.stickers);
  const audioFiles = useEditor((s) => s.audioFiles);
  const appendVideoClip = useEditor((s) => s.appendVideoClip);
  const addStickerClip = useEditor((s) => s.addStickerClip);
  const addAudioClip = useEditor((s) => s.addAudioClip);
  const playhead = useEditor((s) => s.playhead);
  const uploadFiles = useEditor((s) => s.uploadFiles);
  const uploading = useEditor((s) => s.uploading);
  const deleteMediaItem = useEditor((s) => s.deleteMediaItem);
  const deleteAudioItem = useEditor((s) => s.deleteAudioItem);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [deleting, setDeleting] = useState<Set<string>>(new Set());
  const { busy, errors, busyAll, allError, transcribeOne, transcribeAll } = useTranscribeJobs();

  async function handleDeleteMedia(name: string) {
    if (!confirm(`Apagar "${name}"? O arquivo original também será removido da pasta de vídeos.`)) return;
    setDeleting((d) => new Set(d).add(name));
    try {
      await deleteMediaItem(name);
    } finally {
      setDeleting((d) => { const n = new Set(d); n.delete(name); return n; });
    }
  }

  async function handleDeleteAudio(name: string) {
    if (!confirm(`Apagar "${name}"? O arquivo original também será removido.`)) return;
    setDeleting((d) => new Set(d).add(`audio:${name}`));
    try {
      await deleteAudioItem(name);
    } finally {
      setDeleting((d) => { const n = new Set(d); n.delete(`audio:${name}`); return n; });
    }
  }

  function handleFiles(fileList: FileList | null) {
    if (!fileList || !fileList.length) return;
    uploadFiles(Array.from(fileList));
  }

  return (
    <div
      className={`media-bin ${dragOver ? "dropzone-active" : ""}`}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div className="media-bin-header">
        <h3><IconVideo size={12} /> Media</h3>
        {media.length > 0 && (
          <button
            className="ghost"
            onClick={transcribeAll}
            disabled={busyAll}
            title="Transcribe every source with ElevenLabs (needed for AI auto-edit and auto-subtitles)"
          >
            {busyAll ? "Transcribing…" : "Transcribe all"}
          </button>
        )}
        <button className="ghost" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
          <IconUpload size={12} /> {uploading ? "Uploading…" : "Import"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*,audio/*"
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {allError && <div className="dur" style={{ color: "var(--danger)", marginBottom: 8 }}>{allError}</div>}
      {dragOver && <div className="dropzone-hint">Drop files to import</div>}

      {media.length === 0 && (
        <div className="media-empty">
          Drag video files here from your computer, or drop them into the videos folder this
          session points at and refresh — same as the chat-driven flow.
        </div>
      )}
      {media.map((m) => (
        <div
          key={m.name}
          className="media-item"
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData("application/x-video-use-source", m.name);
            e.dataTransfer.effectAllowed = "copy";
          }}
          onDoubleClick={() => appendVideoClip(m.name, 0, m.duration ?? 3)}
          title="Drag onto the video track, or double-click to append"
        >
          <img src={m.thumbnail_url} alt={m.name} loading="lazy" />
          <div className="meta">
            <div className="name">{m.name}</div>
            <div className="dur">{fmtDur(m.duration)}{m.width ? ` · ${m.width}×${m.height}` : ""}</div>
            {errors[m.name] && <div className="dur" style={{ color: "var(--danger)" }}>{errors[m.name]}</div>}
          </div>
          {m.transcribed ? (
            <span className="badge-ok" title="Transcript available"><IconCheck size={11} /> transcribed</span>
          ) : (
            <button
              className="ghost"
              style={{ fontSize: 10, padding: "3px 6px" }}
              onClick={(e) => { e.stopPropagation(); transcribeOne(m.name); }}
              disabled={busy.has(m.name)}
              title="Transcribe with ElevenLabs Scribe"
            >
              {busy.has(m.name) ? "…" : "Transcribe"}
            </button>
          )}
          <button
            className="ghost"
            style={{ padding: "3px 6px" }}
            onClick={(e) => { e.stopPropagation(); handleDeleteMedia(m.name); }}
            disabled={deleting.has(m.name)}
            title="Delete this file"
          >
            <IconTrash size={12} />
          </button>
        </div>
      ))}

      {stickers.length > 0 && (
        <>
          <h3 style={{ marginTop: 18 }}>Stickers</h3>
          <div className="sticker-grid">
            {stickers.map((s) => (
              <img
                key={s.name}
                src={s.url}
                alt={s.name}
                className="sticker-thumb"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("application/x-video-use-sticker", s.url);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                onDoubleClick={() => addStickerClip(s.url, playhead, 2)}
                title={`Drag onto the Overlays track, or double-click to add at the playhead (${s.name})`}
              />
            ))}
          </div>
        </>
      )}

      {audioFiles.length > 0 && (
        <>
          <h3 style={{ marginTop: 18 }}><IconMusic size={12} /> Music</h3>
          {audioFiles.map((a) => (
            <div
              key={a.name}
              className="media-item"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData("application/x-video-use-audio", a.stream_url);
                e.dataTransfer.effectAllowed = "copy";
              }}
              onDoubleClick={() => addAudioClip(a.stream_url, playhead, a.duration ?? 5)}
              title="Drag onto the Audio track, or double-click to add at the playhead"
            >
              <div className="audio-icon"><IconMusic size={16} /></div>
              <div className="meta">
                <div className="name">{a.name}</div>
                <div className="dur">{fmtDur(a.duration)}</div>
              </div>
              <button
                className="ghost"
                style={{ padding: "3px 6px" }}
                onClick={(e) => { e.stopPropagation(); handleDeleteAudio(a.name); }}
                disabled={deleting.has(`audio:${a.name}`)}
                title="Delete this file"
              >
                <IconTrash size={12} />
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
