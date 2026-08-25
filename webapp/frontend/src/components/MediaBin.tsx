import { useEditor } from "../store";

function fmtDur(s?: number): string {
  if (!s && s !== 0) return "";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function MediaBin() {
  const media = useEditor((s) => s.media);
  const appendVideoClip = useEditor((s) => s.appendVideoClip);

  return (
    <div className="media-bin">
      <h3>Media</h3>
      {media.length === 0 && (
        <div className="media-empty">
          Drop raw footage into the videos folder this session points at, then refresh —
          it shows up here automatically, same as the chat-driven flow.
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
    </div>
  );
}
