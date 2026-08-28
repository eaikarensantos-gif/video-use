import { useEffect, useState } from "react";
import { useEditor } from "../store";
import { api } from "../api";
import type { AudioClip, GradePreset, OverlayClip, TextClip, VideoClip } from "../types";
import { IconFlipH, IconFlipV } from "../icons";
import CleanupModal from "./CleanupModal";
import TranscriptModal from "./TranscriptModal";

export default function Inspector() {
  const timeline = useEditor((s) => s.timeline);
  const selection = useEditor((s) => s.selection);
  const updateVideoClip = useEditor((s) => s.updateVideoClip);
  const updateVideoTransform = useEditor((s) => s.updateVideoTransform);
  const updateTextClip = useEditor((s) => s.updateTextClip);
  const updateOverlayClip = useEditor((s) => s.updateOverlayClip);
  const updateAudioClip = useEditor((s) => s.updateAudioClip);
  const removeClip = useEditor((s) => s.removeClip);

  const [grades, setGrades] = useState<GradePreset[]>([]);
  const [transitions, setTransitions] = useState<string[]>([]);
  const [cleanupOpen, setCleanupOpen] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  useEffect(() => {
    api.gradePresets().then(setGrades).catch(() => {});
    api.transitionPresets().then(setTransitions).catch(() => {});
  }, []);

  if (!timeline || !selection) {
    return (
      <div className="inspector">
        <h3>Inspector</h3>
        <div className="empty-inspector">
          Select a clip on the timeline to edit its grade, transition, or text.
        </div>
      </div>
    );
  }

  const track = timeline.tracks.find((t) => t.id === selection.trackId);
  const clip = track?.clips.find((c) => c.id === selection.clipId);
  if (!track || !clip) return <div className="inspector"><h3>Inspector</h3></div>;

  if (track.type === "video") {
    const c = clip as VideoClip;
    const transType = c.transitionOut?.type ?? "cut";
    return (
      <div className="inspector">
        <h3>Video clip</h3>
        <div className="field">
          <label>Source</label>
          <input type="text" value={c.source} readOnly />
        </div>
        <div className="field-row">
          <div className="field">
            <label>In (s)</label>
            <input
              type="number" step={0.05} value={c.in.toFixed(2)}
              onChange={(e) => updateVideoClip(c.id, { in: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Out (s)</label>
            <input
              type="number" step={0.05} value={c.out.toFixed(2)}
              onChange={(e) => updateVideoClip(c.id, { out: Number(e.target.value) })}
            />
          </div>
        </div>
        <button className="ghost" style={{ width: "100%", marginBottom: 12 }} onClick={() => setCleanupOpen(true)}>
          ✂ Limpar (silêncios / gaguejo)
        </button>
        {cleanupOpen && <CleanupModal clip={c} onClose={() => setCleanupOpen(false)} />}
        <button className="ghost" style={{ width: "100%", marginBottom: 12 }} onClick={() => setTranscriptOpen(true)}>
          Editar pela transcrição
        </button>
        {transcriptOpen && <TranscriptModal clip={c} onClose={() => setTranscriptOpen(false)} />}
        <div className="field">
          <label>Grade</label>
          <select value={c.grade ?? "none"} onChange={(e) => updateVideoClip(c.id, { grade: e.target.value })}>
            {grades.map((g) => (
              <option key={g.id} value={g.id}>{g.label}</option>
            ))}
          </select>
          <div style={{ color: "var(--text-2)", fontSize: 11, marginTop: 4 }}>
            {grades.find((g) => g.id === (c.grade ?? "none"))?.description}
          </div>
        </div>
        <div className="field">
          <label>Transition out (to next clip)</label>
          <select
            value={transType}
            onChange={(e) => {
              const type = e.target.value;
              updateVideoClip(c.id, { transitionOut: type === "cut" ? { type: "cut" } : { type, duration: c.transitionOut?.duration ?? 0.4 } });
            }}
          >
            {transitions.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        {transType !== "cut" && (
          <div className="field">
            <label>Transition duration (s)</label>
            <input
              type="number" step={0.05} min={0.05} value={(c.transitionOut?.duration ?? 0.4).toFixed(2)}
              onChange={(e) => updateVideoClip(c.id, { transitionOut: { type: transType, duration: Number(e.target.value) } })}
            />
          </div>
        )}
        <div className="field">
          <label>Speed ({(c.speed ?? 1).toFixed(2)}x)</label>
          <select value={c.speed ?? 1} onChange={(e) => updateVideoClip(c.id, { speed: Number(e.target.value) })}>
            <option value={0.25}>0.25x</option>
            <option value={0.5}>0.5x</option>
            <option value={0.75}>0.75x</option>
            <option value={1}>1x (normal)</option>
            <option value={1.25}>1.25x</option>
            <option value={1.5}>1.5x</option>
            <option value={2}>2x</option>
            <option value={3}>3x</option>
            <option value={4}>4x</option>
          </select>
        </div>
        <div className="field">
          <label>Zoom / pan (Ken Burns)</label>
          <select
            value={c.zoom?.type ?? "none"}
            onChange={(e) => {
              const type = e.target.value;
              updateVideoClip(c.id, { zoom: type === "none" ? null : { type: type as "in" | "out", amount: c.zoom?.amount ?? 0.15 } });
            }}
          >
            <option value="none">None</option>
            <option value="in">Zoom in</option>
            <option value="out">Zoom out</option>
          </select>
        </div>
        {c.zoom && (
          <div className="field">
            <label>Zoom amount ({Math.round((c.zoom.amount ?? 0.15) * 100)}%)</label>
            <input
              type="range" min={0.05} max={0.6} step={0.01} value={c.zoom.amount ?? 0.15}
              onChange={(e) => updateVideoClip(c.id, { zoom: { type: c.zoom!.type, amount: Number(e.target.value) } })}
            />
          </div>
        )}
        <div className="field-row" style={{ alignItems: "center", justifyContent: "space-between" }}>
          <label style={{ margin: 0 }}>Transform</label>
          <button
            className="ghost"
            style={{ fontSize: 10, padding: "3px 6px" }}
            onClick={() => updateVideoClip(c.id, { transform: undefined })}
          >
            Reset
          </button>
        </div>
        <div className="field">
          <label>Scale ({Math.round((c.transform?.scale ?? 1) * 100)}%)</label>
          <input
            type="range" min={0.1} max={3} step={0.01} value={c.transform?.scale ?? 1}
            onChange={(e) => updateVideoTransform(c.id, { scale: Number(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <div className="field">
            <label>X ({Math.round((c.transform?.x ?? 0) * 100)}%)</label>
            <input
              type="range" min={-0.5} max={0.5} step={0.01} value={c.transform?.x ?? 0}
              onChange={(e) => updateVideoTransform(c.id, { x: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Y ({Math.round((c.transform?.y ?? 0) * 100)}%)</label>
            <input
              type="range" min={-0.5} max={0.5} step={0.01} value={c.transform?.y ?? 0}
              onChange={(e) => updateVideoTransform(c.id, { y: Number(e.target.value) })}
            />
          </div>
        </div>
        <div className="field">
          <label>Rotation ({Math.round(c.transform?.rotation ?? 0)}°)</label>
          <input
            type="range" min={-180} max={180} step={1} value={c.transform?.rotation ?? 0}
            onChange={(e) => updateVideoTransform(c.id, { rotation: Number(e.target.value) })}
          />
        </div>
        <div className="field">
          <label>Opacity ({Math.round((c.transform?.opacity ?? 1) * 100)}%)</label>
          <input
            type="range" min={0} max={1} step={0.01} value={c.transform?.opacity ?? 1}
            onChange={(e) => updateVideoTransform(c.id, { opacity: Number(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <button
            className={c.transform?.flip_h ? "primary" : "ghost"}
            style={{ flex: 1 }}
            onClick={() => updateVideoTransform(c.id, { flip_h: !c.transform?.flip_h })}
          >
            <IconFlipH size={13} /> Flip H
          </button>
          <button
            className={c.transform?.flip_v ? "primary" : "ghost"}
            style={{ flex: 1 }}
            onClick={() => updateVideoTransform(c.id, { flip_v: !c.transform?.flip_v })}
          >
            <IconFlipV size={13} /> Flip V
          </button>
        </div>
        <div className="field" style={{ marginTop: 12 }}>
          <label>Note / beat</label>
          <input type="text" value={c.note ?? ""} onChange={(e) => updateVideoClip(c.id, { note: e.target.value })} />
        </div>
        <button onClick={() => removeClip(track.id, c.id)}>Delete clip</button>
      </div>
    );
  }

  if (track.type === "text") {
    const c = clip as TextClip;
    return (
      <div className="inspector">
        <h3>Text card</h3>
        <div className="field">
          <label>Text</label>
          <input type="text" value={c.text} onChange={(e) => updateTextClip(c.id, { text: e.target.value })} />
        </div>
        <div className="field-row">
          <div className="field">
            <label>Start (s)</label>
            <input type="number" step={0.05} value={c.start.toFixed(2)} onChange={(e) => updateTextClip(c.id, { start: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Duration (s)</label>
            <input type="number" step={0.05} value={c.duration.toFixed(2)} onChange={(e) => updateTextClip(c.id, { duration: Number(e.target.value) })} />
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label>Position</label>
            <select
              value={c.style?.position ?? "bottom"}
              onChange={(e) => updateTextClip(c.id, { style: { position: e.target.value as any } })}
            >
              <option value="top">Top</option>
              <option value="center">Center</option>
              <option value="bottom">Bottom</option>
            </select>
          </div>
          <div className="field">
            <label>Animation</label>
            <select
              value={c.style?.animation ?? "none"}
              onChange={(e) => updateTextClip(c.id, { style: { animation: e.target.value as any } })}
            >
              <option value="none">None</option>
              <option value="fade">Fade in/out</option>
              <option value="slide_up">Slide up</option>
            </select>
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label>Font size</label>
            <input
              type="number" value={c.style?.font_size ?? 54}
              onChange={(e) => updateTextClip(c.id, { style: { font_size: Number(e.target.value) } })}
            />
          </div>
          <div className="field">
            <label>Color</label>
            <input
              type="text" value={c.style?.color ?? "white"}
              onChange={(e) => updateTextClip(c.id, { style: { color: e.target.value } })}
            />
          </div>
        </div>
        <div className="field checkbox-row">
          <input
            type="checkbox"
            checked={c.style?.background ?? true}
            onChange={(e) => updateTextClip(c.id, { style: { background: e.target.checked } })}
          />
          Background chip
        </div>
        <button onClick={() => removeClip(track.id, c.id)}>Delete text</button>
      </div>
    );
  }

  if (track.type === "audio") {
    const c = clip as AudioClip;
    return (
      <div className="inspector">
        <h3>Audio clip</h3>
        <div className="field">
          <label>File</label>
          <input type="text" value={c.file.split("/").pop()} readOnly />
        </div>
        <div className="field-row">
          <div className="field">
            <label>Start (s)</label>
            <input type="number" step={0.05} value={c.start.toFixed(2)} onChange={(e) => updateAudioClip(c.id, { start: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Duration (s)</label>
            <input type="number" step={0.05} value={c.duration.toFixed(2)} onChange={(e) => updateAudioClip(c.id, { duration: Number(e.target.value) })} />
          </div>
        </div>
        <div className="field">
          <label>Volume ({Math.round((c.volume ?? 1) * 100)}%)</label>
          <input type="range" min={0} max={2} step={0.01} value={c.volume ?? 1} onChange={(e) => updateAudioClip(c.id, { volume: Number(e.target.value) })} />
        </div>
        <div className="field-row">
          <div className="field">
            <label>Fade in (s)</label>
            <input type="number" step={0.05} min={0} value={(c.fadeIn ?? 0).toFixed(2)} onChange={(e) => updateAudioClip(c.id, { fadeIn: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Fade out (s)</label>
            <input type="number" step={0.05} min={0} value={(c.fadeOut ?? 0).toFixed(2)} onChange={(e) => updateAudioClip(c.id, { fadeOut: Number(e.target.value) })} />
          </div>
        </div>
        <button onClick={() => removeClip(track.id, c.id)}>Delete audio clip</button>
      </div>
    );
  }

  const c = clip as OverlayClip;
  const isSticker = c.kind === "sticker";
  return (
    <div className="inspector">
      <h3>{isSticker ? "Sticker" : "Overlay"}</h3>
      {isSticker && (
        <div className="field">
          <img src={c.file} alt="" style={{ width: 64, height: 64, objectFit: "contain", background: "var(--bg-2)", borderRadius: 6, padding: 6 }} />
        </div>
      )}
      <div className="field">
        <label>File</label>
        <input type="text" value={c.file} readOnly />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Start (s)</label>
          <input type="number" step={0.05} value={c.start.toFixed(2)} onChange={(e) => updateOverlayClip(c.id, { start: Number(e.target.value) })} />
        </div>
        <div className="field">
          <label>Duration (s)</label>
          <input type="number" step={0.05} value={c.duration.toFixed(2)} onChange={(e) => updateOverlayClip(c.id, { duration: Number(e.target.value) })} />
        </div>
      </div>
      {isSticker && (
        <>
          <div className="field-row">
            <div className="field">
              <label>X position ({Math.round((c.x ?? 0.5) * 100)}%)</label>
              <input type="range" min={0} max={1} step={0.01} value={c.x ?? 0.5} onChange={(e) => updateOverlayClip(c.id, { x: Number(e.target.value) })} />
            </div>
            <div className="field">
              <label>Y position ({Math.round((c.y ?? 0.5) * 100)}%)</label>
              <input type="range" min={0} max={1} step={0.01} value={c.y ?? 0.5} onChange={(e) => updateOverlayClip(c.id, { y: Number(e.target.value) })} />
            </div>
          </div>
          <div className="field">
            <label>Size ({Math.round((c.scale ?? 0.3) * 100)}% of frame width)</label>
            <input type="range" min={0.05} max={1} step={0.01} value={c.scale ?? 0.3} onChange={(e) => updateOverlayClip(c.id, { scale: Number(e.target.value) })} />
          </div>
        </>
      )}
      <button onClick={() => removeClip(track.id, c.id)}>Delete {isSticker ? "sticker" : "overlay"}</button>
    </div>
  );
}
