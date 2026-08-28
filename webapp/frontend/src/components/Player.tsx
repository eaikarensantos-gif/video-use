import { useEffect, useRef } from "react";
import { useEditor } from "../store";
import { computeVideoLayout } from "../layout";
import type { OverlayClip, TextClip, VideoClip } from "../types";
import { IconPause, IconPlay, IconSkipBack } from "../icons";

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

export default function Player() {
  const timeline = useEditor((s) => s.timeline);
  const media = useEditor((s) => s.media);
  const playhead = useEditor((s) => s.playhead);
  const setPlayhead = useEditor((s) => s.setPlayhead);
  const playing = useEditor((s) => s.playing);
  const setPlaying = useEditor((s) => s.setPlaying);
  const totalDuration = useEditor((s) => s.totalDuration());

  const videoRef = useRef<HTMLVideoElement>(null);
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);

  const videoTrack = timeline?.tracks.find((t) => t.type === "video");
  const clips = (videoTrack?.clips ?? []) as VideoClip[];
  const layout = computeVideoLayout(clips);

  let activeIdx = -1;
  for (let i = 0; i < layout.length; i++) {
    if (playhead >= layout[i].start && playhead < layout[i].end) {
      activeIdx = i;
      break;
    }
  }
  if (activeIdx === -1 && layout.length && playhead >= layout[layout.length - 1].end) {
    activeIdx = layout.length - 1;
  }
  const activeClip = activeIdx >= 0 ? clips[activeIdx] : null;
  const activeLayout = activeIdx >= 0 ? layout[activeIdx] : null;
  const sourceInfo = activeClip ? media.find((m) => m.name === activeClip.source) : null;

  // Point <video> at the active clip's source file.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !sourceInfo) return;
    if (!v.src.endsWith(sourceInfo.stream_url)) {
      v.src = sourceInfo.stream_url;
      v.load();
    }
  }, [sourceInfo?.stream_url]);

  // Keep <video> currentTime aligned to the playhead / play state. Metadata
  // may not be loaded yet right after swapping `src`, so defer the seek.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !activeClip || !activeLayout) return;
    const speed = activeClip.speed || 1;
    const sourceTime = activeClip.in + (playhead - activeLayout.start) * speed;
    const apply = () => {
      const tolerance = playing ? 0.35 * speed : 0.03;
      if (Math.abs(v.currentTime - sourceTime) > tolerance) v.currentTime = sourceTime;
      v.playbackRate = speed;
      if (playing) v.play().catch(() => {});
      else v.pause();
    };
    if (v.readyState >= 1) {
      apply();
    } else {
      v.addEventListener("loadedmetadata", apply, { once: true });
      return () => v.removeEventListener("loadedmetadata", apply);
    }
  }, [playhead, playing, activeClip?.id, sourceInfo?.stream_url]);

  // Drive the playhead clock while playing (reads live state via getState()
  // to avoid stale closures inside the rAF loop).
  useEffect(() => {
    if (!playing) {
      lastTsRef.current = null;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    const tick = (ts: number) => {
      if (lastTsRef.current == null) lastTsRef.current = ts;
      const dt = (ts - lastTsRef.current) / 1000;
      lastTsRef.current = ts;
      const state = useEditor.getState();
      const total = state.totalDuration();
      const next = state.playhead + dt;
      if (next >= total) {
        state.setPlayhead(total);
        state.setPlaying(false);
        return;
      }
      state.setPlayhead(next);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [playing]);

  // CSS approximation of the ffmpeg transform chain (Hard scope: the live
  // preview is a fast approximation, helpers/render.py is the source of
  // truth). Function order mirrors the backend's flip → rotate → zoom/pan:
  // rightmost (innermost) is applied first, so flip sits rightmost, the
  // zoom/pan scale sits leftmost (outermost, applied last).
  const tf = activeClip?.transform;
  // A chosen project aspect ratio (Toolbar) locks the frame to that shape
  // and crops every clip to fill it — object-fit: cover approximates the
  // real render's scale+crop-to-fill. With no aspect ratio chosen, the
  // frame just follows the active clip's own intrinsic size, as before.
  const canvas = timeline?.canvas;
  const hasFixedAspect = !!(canvas?.width && canvas?.height);
  const videoStyle: React.CSSProperties = {
    ...(hasFixedAspect ? { width: "100%", height: "100%", objectFit: "cover" as const } : {}),
    ...(tf
      ? {
          opacity: tf.opacity ?? 1,
          transform: [
            `scale(${tf.scale ?? 1})`,
            `translate(${-(tf.x ?? 0) * 100}%, ${-(tf.y ?? 0) * 100}%)`,
            `rotate(${tf.rotation ?? 0}deg)`,
            `scale(${tf.flip_h ? -1 : 1}, ${tf.flip_v ? -1 : 1})`,
          ].join(" "),
        }
      : {}),
  };

  const textTrack = timeline?.tracks.find((t) => t.type === "text");
  const activeTexts = ((textTrack?.clips ?? []) as TextClip[]).filter(
    (c) => playhead >= c.start && playhead < c.start + c.duration
  );
  const overlayTrack = timeline?.tracks.find((t) => t.type === "overlay");
  const activeOverlays = ((overlayTrack?.clips ?? []) as OverlayClip[]).filter(
    (c) => playhead >= c.start && playhead < c.start + c.duration
  );

  return (
    <div className="player-panel">
      <div
        className="player-frame"
        style={hasFixedAspect ? { aspectRatio: `${canvas!.width} / ${canvas!.height}`, width: "auto", height: "100%" } : undefined}
      >
        {activeClip ? (
          <video ref={videoRef} playsInline muted={false} style={videoStyle} />
        ) : (
          <div className="no-clip">
            Drag a clip from Media onto the video track to start editing.
          </div>
        )}
        {activeTexts.map((t) => (
          <div
            key={t.id}
            className="text-overlay-preview"
            style={{
              top: t.style?.position === "top" ? "8%" : t.style?.position === "center" ? "45%" : undefined,
              bottom: (!t.style?.position || t.style.position === "bottom") ? "10%" : undefined,
              color: t.style?.color ?? "white",
              fontSize: Math.max(12, (t.style?.font_size ?? 54) / 2.6),
              background: t.style?.background === false ? "transparent" : "rgba(0,0,0,0.5)",
            }}
          >
            {t.text}
          </div>
        ))}
        {activeOverlays.filter((o) => o.kind === "sticker").map((o) => (
          <img
            key={o.id}
            src={o.file}
            alt=""
            style={{
              position: "absolute",
              left: `${(o.x ?? 0.5) * 100}%`,
              top: `${(o.y ?? 0.5) * 100}%`,
              width: `${(o.scale ?? 0.3) * 100}%`,
              transform: "translate(-50%, -50%)",
              pointerEvents: "none",
            }}
          />
        ))}
        {activeOverlays.some((o) => o.kind !== "sticker") && (
          <div style={{ position: "absolute", top: 8, right: 8, background: "rgba(0,0,0,0.6)", padding: "2px 8px", borderRadius: 4, fontSize: 10 }}>
            overlay: {activeOverlays.filter((o) => o.kind !== "sticker").map((o) => o.file.split("/").pop()).join(", ")}
          </div>
        )}
      </div>
      <div className="transport">
        <button className="ghost" onClick={() => setPlayhead(0)} title="Jump to start">
          <IconSkipBack size={14} />
        </button>
        <button onClick={() => setPlaying(!playing)} title="Play/Pause (space)">
          {playing ? <IconPause size={14} /> : <IconPlay size={14} />}
        </button>
        <div className="time">{fmt(playhead)} / {fmt(totalDuration)}</div>
        <input
          style={{ flex: 1 }}
          type="range"
          min={0}
          max={Math.max(0.01, totalDuration)}
          step={0.01}
          value={Math.min(playhead, totalDuration)}
          onChange={(e) => setPlayhead(Number(e.target.value))}
        />
      </div>
    </div>
  );
}
