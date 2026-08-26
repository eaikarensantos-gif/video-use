import { useRef, useState } from "react";
import { useEditor } from "../store";

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

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

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
        <h3>Media</h3>
        <button className="ghost" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
          {uploading ? "Uploading…" : "+ Import"}
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
          </div>
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
          <h3 style={{ marginTop: 18 }}>Music</h3>
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
              <div className="audio-icon">♪</div>
              <div className="meta">
                <div className="name">{a.name}</div>
                <div className="dur">{fmtDur(a.duration)}</div>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
