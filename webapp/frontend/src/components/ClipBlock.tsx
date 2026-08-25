import { useRef } from "react";
import type { OverlayClip, TextClip, Track, VideoClip } from "../types";

interface Props {
  track: Track;
  clip: VideoClip | TextClip | OverlayClip;
  left: number;
  width: number;
  selected: boolean;
  isLast: boolean;
  waveform?: number[];
  onSelect: () => void;
  onDelete: () => void;
  onDragMove: (deltaPx: number, finished: boolean) => void;
  onResize: (edge: "left" | "right", deltaPx: number, finished: boolean) => void;
}

export default function ClipBlock({ track, clip, left, width, selected, waveform, onSelect, onDelete, onDragMove, onResize }: Props) {
  const startX = useRef(0);
  const dragging = useRef(false);

  function beginDrag(e: React.MouseEvent) {
    e.stopPropagation();
    onSelect();
    startX.current = e.clientX;
    dragging.current = true;
    const onMove = (ev: MouseEvent) => {
      onDragMove(ev.clientX - startX.current, false);
    };
    const onUp = (ev: MouseEvent) => {
      onDragMove(ev.clientX - startX.current, true);
      dragging.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function beginResize(edge: "left" | "right", e: React.MouseEvent) {
    e.stopPropagation();
    onSelect();
    const startXLocal = e.clientX;
    const onMove = (ev: MouseEvent) => onResize(edge, ev.clientX - startXLocal, false);
    const onUp = (ev: MouseEvent) => {
      onResize(edge, ev.clientX - startXLocal, true);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  const label =
    track.type === "video"
      ? (clip as VideoClip).source
      : track.type === "text"
      ? (clip as TextClip).text || "(empty text)"
      : (clip as OverlayClip).file.split("/").pop();

  const transitionOut = track.type === "video" ? (clip as VideoClip).transitionOut : null;
  const hasTransition = transitionOut && transitionOut.type && transitionOut.type !== "cut";

  return (
    <div
      className={`clip ${track.type} ${selected ? "selected" : ""}`}
      style={{ left, width: Math.max(4, width) }}
      onMouseDown={beginDrag}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (confirm(`Delete this ${track.type} clip?`)) onDelete();
      }}
      title={`${label} — drag to move, edges to trim, double-click to delete`}
    >
      {waveform && waveform.length > 1 && (
        <svg
          className="clip-waveform"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, opacity: 0.35, width: "100%", height: "100%" }}
        >
          <polyline
            fill="none"
            stroke="white"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            points={waveform
              .map((v, i) => `${(i / (waveform.length - 1)) * 100},${50 - v * 45}`)
              .concat(waveform.map((v, i) => `${(1 - i / (waveform.length - 1)) * 100},${50 + v * 45}`).reverse())
              .join(" ")}
          />
        </svg>
      )}
      <span className="label">{label}</span>
      {hasTransition && <div className="transition-badge">⇄</div>}
      <div className="handle left" onMouseDown={(e) => beginResize("left", e)} />
      <div className="handle right" onMouseDown={(e) => beginResize("right", e)} />
    </div>
  );
}
