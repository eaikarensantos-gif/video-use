import { useEffect, useMemo, useState } from "react";
import { useEditor } from "../store";
import { computeVideoLayout } from "../layout";
import { api } from "../api";
import ClipBlock from "./ClipBlock";
import type { OverlayClip, TextClip, Track, VideoClip } from "../types";

function pickStep(zoom: number): number {
  const target = 80; // desired px between ticks
  const rawSeconds = target / zoom;
  const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
  return steps.find((s) => s >= rawSeconds) ?? 600;
}

function fmtTick(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

interface Layout {
  start: number;
  duration: number;
}

export default function Timeline() {
  const timeline = useEditor((s) => s.timeline);
  const media = useEditor((s) => s.media);
  const zoom = useEditor((s) => s.zoom);
  const playhead = useEditor((s) => s.playhead);
  const setPlayhead = useEditor((s) => s.setPlayhead);
  const selection = useEditor((s) => s.selection);
  const select = useEditor((s) => s.select);
  const totalDuration = useEditor((s) => s.totalDuration());

  const appendVideoClip = useEditor((s) => s.appendVideoClip);
  const updateVideoClip = useEditor((s) => s.updateVideoClip);
  const moveVideoClip = useEditor((s) => s.moveVideoClip);
  const removeClip = useEditor((s) => s.removeClip);
  const updateTextClip = useEditor((s) => s.updateTextClip);
  const updateOverlayClip = useEditor((s) => s.updateOverlayClip);
  const addTextClip = useEditor((s) => s.addTextClip);

  const [waveforms, setWaveforms] = useState<Record<string, number[]>>({});
  const [dragOffset, setDragOffset] = useState<{ clipId: string; deltaPx: number } | null>(null);
  const [resizeOffset, setResizeOffset] = useState<{ clipId: string; edge: "left" | "right"; deltaPx: number } | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const tracks = timeline?.tracks ?? [];
  const videoTrack = tracks.find((t) => t.type === "video");
  const videoClips = (videoTrack?.clips ?? []) as VideoClip[];
  const videoLayout = useMemo(() => computeVideoLayout(videoClips), [videoClips]);

  useEffect(() => {
    const sources = Array.from(new Set(videoClips.map((c) => c.source)));
    sources.forEach((name) => {
      if (waveforms[name] !== undefined) return;
      setWaveforms((w) => ({ ...w, [name]: [] })); // mark in-flight
      api.waveform(name).then((peaks) => setWaveforms((w) => ({ ...w, [name]: peaks }))).catch(() => {});
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoClips.map((c) => c.source).join(",")]);

  const laneWidth = Math.max(600, (totalDuration + 5) * zoom);
  const step = pickStep(zoom);
  const ticks: number[] = [];
  for (let t = 0; t <= totalDuration + step * 4; t += step) ticks.push(t);

  function timeFromClientX(clientX: number, laneEl: HTMLElement): number {
    const rect = laneEl.getBoundingClientRect();
    return Math.max(0, (clientX - rect.left) / zoom);
  }

  function peaksForRange(name: string, from: number, to: number): number[] | undefined {
    const peaks = waveforms[name];
    const src = media.find((m) => m.name === name);
    if (!peaks || !peaks.length || !src?.duration) return undefined;
    const startIdx = Math.floor((from / src.duration) * peaks.length);
    const endIdx = Math.ceil((to / src.duration) * peaks.length);
    return peaks.slice(Math.max(0, startIdx), Math.min(peaks.length, endIdx));
  }

  function renderTrack(track: Track) {
    const isVideo = track.type === "video";
    const layouts: Layout[] = isVideo
      ? videoLayout
      : (track.clips as (TextClip | OverlayClip)[]).map((c) => ({ start: c.start, duration: c.duration }));

    return (
      <div className="track-row" key={track.id}>
        <div className="track-label">{track.name}</div>
        <div
          className={`track-lane ${dragOver && isVideo ? "dragover" : ""}`}
          style={{ width: laneWidth }}
          onClick={(e) => {
            setPlayhead(timeFromClientX(e.clientX, e.currentTarget));
            select(null);
          }}
          onDragOver={(e) => {
            if (!isVideo) return;
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            if (!isVideo) return;
            e.preventDefault();
            setDragOver(false);
            const name = e.dataTransfer.getData("application/x-video-use-source");
            const src = media.find((m) => m.name === name);
            if (src) appendVideoClip(name, 0, src.duration ?? 3);
          }}
        >
          {track.clips.map((clip, i) => {
            const base = layouts[i];
            if (!base) return null;
            let left = base.start * zoom;
            let width = base.duration * zoom;
            if (dragOffset?.clipId === clip.id) left += dragOffset.deltaPx;
            if (resizeOffset?.clipId === clip.id) {
              const dt = resizeOffset.deltaPx / zoom;
              if (resizeOffset.edge === "left") {
                left += resizeOffset.deltaPx;
                width -= resizeOffset.deltaPx;
              } else {
                width += resizeOffset.deltaPx;
              }
            }
            const wf = isVideo ? peaksForRange((clip as VideoClip).source, (clip as VideoClip).in, (clip as VideoClip).out) : undefined;

            return (
              <ClipBlock
                key={clip.id}
                track={track}
                clip={clip}
                left={left}
                width={width}
                selected={selection?.clipId === clip.id}
                isLast={i === track.clips.length - 1}
                waveform={wf}
                onSelect={() => select({ trackId: track.id, clipId: clip.id })}
                onDelete={() => removeClip(track.id, clip.id)}
                onDragMove={(deltaPx, finished) => {
                  if (!finished) {
                    setDragOffset({ clipId: clip.id, deltaPx });
                    return;
                  }
                  setDragOffset(null);
                  const deltaTime = deltaPx / zoom;
                  if (Math.abs(deltaTime) < 0.05) return;
                  if (isVideo) {
                    const idx = videoClips.findIndex((c) => c.id === clip.id);
                    const targetCenter = base.start + base.duration / 2 + deltaTime;
                    let newIndex = 0;
                    videoLayout.forEach((l, li) => {
                      if (li === idx) return;
                      const center = l.start + l.duration / 2;
                      if (center < targetCenter) newIndex++;
                    });
                    if (newIndex !== idx) moveVideoClip(clip.id, newIndex);
                  } else {
                    const newStart = Math.max(0, base.start + deltaTime);
                    if (track.type === "text") updateTextClip(clip.id, { start: newStart });
                    else updateOverlayClip(clip.id, { start: newStart });
                  }
                }}
                onResize={(edge, deltaPx, finished) => {
                  if (!finished) {
                    setResizeOffset({ clipId: clip.id, edge, deltaPx });
                    return;
                  }
                  setResizeOffset(null);
                  const dt = deltaPx / zoom;
                  if (Math.abs(dt) < 0.02) return;
                  if (isVideo) {
                    const c = clip as VideoClip;
                    const src = media.find((m) => m.name === c.source);
                    const maxOut = src?.duration ?? c.out + 999;
                    if (edge === "left") {
                      const newIn = Math.min(Math.max(0, c.in + dt), c.out - 0.1);
                      updateVideoClip(clip.id, { in: newIn });
                    } else {
                      const newOut = Math.max(c.in + 0.1, Math.min(maxOut, c.out + dt));
                      updateVideoClip(clip.id, { out: newOut });
                    }
                  } else {
                    const c = clip as TextClip | OverlayClip;
                    if (edge === "left") {
                      const newStart = Math.max(0, c.start + dt);
                      const newDuration = Math.max(0.2, c.start + c.duration - newStart);
                      if (track.type === "text") updateTextClip(clip.id, { start: newStart, duration: newDuration });
                      else updateOverlayClip(clip.id, { start: newStart, duration: newDuration });
                    } else {
                      const newDuration = Math.max(0.2, c.duration + dt);
                      if (track.type === "text") updateTextClip(clip.id, { duration: newDuration });
                      else updateOverlayClip(clip.id, { duration: newDuration });
                    }
                  }
                }}
              />
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="timeline-wrap">
      <div className="timeline-toolbar">
        <button className="ghost" onClick={() => addTextClip(playhead, 2)}>+ Text at playhead</button>
        <div className="spacer" />
        <span style={{ color: "var(--text-2)", fontSize: 11 }}>
          {videoClips.length} clip{videoClips.length === 1 ? "" : "s"} · {totalDuration.toFixed(1)}s
        </span>
      </div>
      <div className="timeline-scroll">
        <div className="timeline-tracks" style={{ width: 90 + laneWidth }}>
          <div className="ruler">
            <div className="ruler-spacer" />
            <div
              className="ruler-ticks"
              style={{ width: laneWidth, cursor: "pointer" }}
              onClick={(e) => setPlayhead(timeFromClientX(e.clientX, e.currentTarget))}
              onMouseDown={(e) => {
                if (e.buttons !== 1) return;
                const lane = e.currentTarget;
                const onMove = (ev: MouseEvent) => setPlayhead(timeFromClientX(ev.clientX, lane));
                const onUp = () => window.removeEventListener("mousemove", onMove);
                window.addEventListener("mousemove", onMove);
                window.addEventListener("mouseup", onUp, { once: true });
              }}
            >
              {ticks.map((t) => (
                <div key={t} className="tick" style={{ left: t * zoom }}>{fmtTick(t)}</div>
              ))}
            </div>
          </div>
          {tracks.map(renderTrack)}
          <div className="playhead" style={{ left: 90 + playhead * zoom }} />
        </div>
      </div>
    </div>
  );
}
