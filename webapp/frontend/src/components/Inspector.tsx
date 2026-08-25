import { useEffect, useState } from "react";
import { useEditor } from "../store";
import { api } from "../api";
import type { GradePreset, OverlayClip, TextClip, VideoClip } from "../types";

export default function Inspector() {
  const timeline = useEditor((s) => s.timeline);
  const selection = useEditor((s) => s.selection);
  const updateVideoClip = useEditor((s) => s.updateVideoClip);
  const updateTextClip = useEditor((s) => s.updateTextClip);
  const updateOverlayClip = useEditor((s) => s.updateOverlayClip);
  const removeClip = useEditor((s) => s.removeClip);

  const [grades, setGrades] = useState<GradePreset[]>([]);
  const [transitions, setTransitions] = useState<string[]>([]);

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

  const c = clip as OverlayClip;
  return (
    <div className="inspector">
      <h3>Overlay</h3>
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
      <button onClick={() => removeClip(track.id, c.id)}>Delete overlay</button>
    </div>
  );
}
