import { useEditor } from "../store";
import { IconExport, IconLogo, IconRedo, IconScissors, IconSparkle, IconUndo } from "../icons";

const ASPECT_PRESETS: { label: string; width: number | null; height: number | null }[] = [
  { label: "Original (per clip)", width: null, height: null },
  { label: "16:9 Landscape", width: 1920, height: 1080 },
  { label: "9:16 Vertical (Reels/Shorts)", width: 1080, height: 1920 },
  { label: "1:1 Square", width: 1080, height: 1080 },
  { label: "4:5 Portrait", width: 1080, height: 1350 },
];

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
  const canvas = useEditor((s) => s.timeline?.canvas);
  const setCanvasAspect = useEditor((s) => s.setCanvasAspect);

  const statusText = saving ? "saving…" : dirty ? "unsaved changes" : "saved";
  const aspectIndex = ASPECT_PRESETS.findIndex(
    (p) => p.width === (canvas?.width ?? null) && p.height === (canvas?.height ?? null)
  );

  return (
    <div className="toolbar">
      <div className="brand">
        <IconLogo size={28} />
        <div className="brand-copy">
          <div className="title">Video Use</div>
          <div className="project-name">Untitled project</div>
        </div>
      </div>
      <div className="divider" />
      <div className="toolbar-group edit-actions">
        <button className="ghost icon-action" disabled={!history.length} onClick={undo} title="Undo">
          <IconUndo size={15} /><span>Undo</span>
        </button>
        <button className="ghost icon-action" disabled={!future.length} onClick={redo} title="Redo">
          <IconRedo size={15} /><span>Redo</span>
        </button>
        <button className="ghost icon-action" onClick={() => splitVideoClipAt(playhead)} title="Split at playhead (S)">
          <IconScissors size={15} /><span>Split</span>
        </button>
      </div>
      <div className="spacer" />
      <label className="toolbar-control">
        <span>Canvas</span>
        <select
          value={aspectIndex === -1 ? 0 : aspectIndex}
          onChange={(e) => {
            const preset = ASPECT_PRESETS[Number(e.target.value)];
            setCanvasAspect(preset.width && preset.height ? { width: preset.width, height: preset.height } : null);
          }}
          title="Reframe the whole project — every clip is scaled/cropped to fill this shape. Original leaves each clip at its own orientation."
        >
          {ASPECT_PRESETS.map((p, i) => (
            <option key={p.label} value={i}>{p.label}</option>
          ))}
        </select>
      </label>
      <label className="toolbar-control zoom-control">
        <span>Zoom</span>
        <input
          type="range"
          min={20}
          max={300}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
        />
      </label>
      <div className={`status ${dirty ? "is-dirty" : ""}`}><span className="status-dot" />{statusText}</div>
      <button className="ai-action" onClick={onAiEdit} title="Propose a cut with the real AI editor, review, then apply">
        <IconSparkle size={15} /> AI Studio <span className="beta-badge">BETA</span>
      </button>
      <button className="primary export-action" onClick={onExport}>
        <IconExport size={14} /> Export
      </button>
    </div>
  );
}
