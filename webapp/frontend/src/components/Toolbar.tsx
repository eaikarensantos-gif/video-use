import { useEditor } from "../store";

export default function Toolbar({ onExport, onAiEdit }: { onExport: () => void; onAiEdit: () => void }) {
  const dirty = useEditor((s) => s.dirty);
  const saving = useEditor((s) => s.saving);
  const undo = useEditor((s) => s.undo);
  const redo = useEditor((s) => s.redo);
  const history = useEditor((s) => s.history);
  const future = useEditor((s) => s.future);
  const zoom = useEditor((s) => s.zoom);
  const setZoom = useEditor((s) => s.setZoom);
  const playhead = useEditor((s) => s.playhead);
  const splitVideoClipAt = useEditor((s) => s.splitVideoClipAt);

  const statusText = saving ? "saving…" : dirty ? "unsaved changes" : "saved";

  return (
    <div className="toolbar">
      <div className="title">video-use editor</div>
      <button className="ghost" disabled={!history.length} onClick={undo} title="Undo">
        ↶ Undo
      </button>
      <button className="ghost" disabled={!future.length} onClick={redo} title="Redo">
        ↷ Redo
      </button>
      <button className="ghost" onClick={() => splitVideoClipAt(playhead)} title="Split at playhead (S)">
        ✂ Split
      </button>
      <div className="spacer" />
      <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-1)", fontSize: 11 }}>
        Zoom
        <input
          type="range"
          min={20}
          max={300}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
        />
      </label>
      <div className="status">{statusText}</div>
      <button className="ghost" onClick={onAiEdit} title="Propose a cut with the real AI editor, review, then apply">
        ✨ AI Edit
      </button>
      <button className="primary" onClick={onExport}>
        Export
      </button>
    </div>
  );
}
