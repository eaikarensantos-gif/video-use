"""Render a video from an EDL.

Implements the HEURISTICS render pipeline in the correct order:

  1. Per-segment extract with color grade + 30ms audio fades baked in
  2. Lossless -c copy concat into base.mp4
  3. If overlays or subtitles: single filter graph that overlays animations
     (with PTS shift so frame 0 lands at the overlay window start)
     and applies `subtitles` filter LAST → final.mp4

Optionally builds a master SRT from the per-source transcripts + EDL
output-timeline offsets, applies the proven force_style (2-word
UPPERCASE chunks, Helvetica 18 Bold, MarginV=35).

Usage:
    python helpers/render.py <edl.json> -o final.mp4
    python helpers/render.py <edl.json> -o preview.mp4 --preview
    python helpers/render.py <edl.json> -o final.mp4 --build-subtitles
    python helpers/render.py <edl.json> -o final.mp4 --no-subtitles
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from grade import get_preset, auto_grade_for_clip  # same directory
except Exception:
    def get_preset(name: str) -> str:
        return ""

    def auto_grade_for_clip(video, start=0.0, duration=None, verbose=False):  # type: ignore
        return "eq=contrast=1.03:saturation=0.98", {}


# -------- Subtitle style (bold-overlay, proven at 1920×1080 and 1080×1920) --
#
# MarginV is NOT taste — it is a platform safe-zone rule.
# TikTok / IG Reels / Shorts UI (caption, username, music, right-rail actions)
# covers roughly the bottom ~25–30% of a 1080×1920 frame. Captions placed near
# the bottom edge get clipped or obscured by the UI. libass auto-scales the
# render canvas relative to PlayResY=288, so MarginV=90 lands the caption
# baseline roughly 30% up from the bottom on any aspect — clear of the UI on
# every major vertical-video platform. Do not drop this below ~75 without a
# specific reason.
SUB_FORCE_STYLE = (
    "FontName=Helvetica,FontSize=18,Bold=1,"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=90"
)

# -------- Helpers ------------------------------------------------------------


def run(cmd: list[str], quiet: bool = False) -> None:
    if not quiet:
        print(f"  $ {' '.join(str(c) for c in cmd[:6])}{' …' if len(cmd) > 6 else ''}")
    subprocess.run(cmd, check=True)


def run_ffmpeg(cmd: list[str]) -> None:
    """Run an ffmpeg/ffprobe command, echoing stderr on failure.

    The plain `subprocess.run(..., check=True, stderr=PIPE)` pattern used
    throughout this file swallows ffmpeg's actual error message inside the
    CalledProcessError — which is unhelpful both on the CLI and in the web
    editor's export log, where it's the only diagnostic the user sees.
    """
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode(errors="replace"))
        raise subprocess.CalledProcessError(proc.returncode, cmd)


def resolve_grade_filter(grade_field: str | None) -> str:
    """The EDL's 'grade' field can be a preset name, a raw ffmpeg filter, or 'auto'.

    Returns the filter string to embed into the per-segment -vf chain.
    For 'auto', returns the sentinel "__AUTO__" which is resolved per-segment.
    """
    if not grade_field:
        return ""
    if grade_field == "auto":
        return "__AUTO__"
    # Preset names are short identifiers, filter strings contain '=' or ','.
    if re.fullmatch(r"[a-zA-Z0-9_\-]+", grade_field):
        try:
            return get_preset(grade_field)
        except KeyError:
            print(f"warning: unknown preset '{grade_field}', using as raw filter")
            return grade_field
    return grade_field


def resolve_path(maybe_path: str, base: Path) -> Path:
    """Resolve a path that may be absolute or relative to `base`."""
    p = Path(maybe_path)
    if p.is_absolute():
        return p
    return (base / p).resolve()


# -------- HDR → SDR tone mapping (HLG / PQ sources) --------------------------
#
# iPhone defaults to HLG HDR in Rec.2020 (and many mirrorless cameras ship PQ).
# If the source is HDR and we only downconvert bit depth (yuv420p10le → yuv420p)
# without tone-mapping, the output is 8-bit but still carries HLG/PQ transfer
# metadata. Players that honor the metadata (screen recorders, most social
# upload re-encodes) interpret 8-bit values in an HDR container and the result
# looks oversaturated / blown out. QuickTime on macOS can hide this locally —
# screen recording and uploaded renders cannot.
#
# Fix: detect HDR via color_transfer and prepend a zscale+tonemap chain to the
# vf graph so the output is clean Rec.709 SDR.

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ (HDR10) and HLG

TONEMAP_CHAIN = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)


def is_hdr_source(video: Path) -> bool:
    """Return True if the source uses a PQ or HLG transfer function."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=color_transfer",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() in HDR_TRANSFERS
    except subprocess.CalledProcessError:
        return False


def is_portrait_source(video: Path) -> bool:
    """Return True if the video's height > width (portrait / vertical)."""
    try:
        w, h = probe_dimensions(video)
        return h > w
    except Exception:
        return False


def probe_dimensions(video: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    w, h = map(int, out.stdout.strip().split(","))
    return w, h


# -------- Ken Burns (zoom/pan) -----------------------------------------------


def build_zoompan_filter(zoom_cfg: dict, duration: float, width: int, height: int, fps: int = 24) -> str:
    """Build a `zoompan=...` filter for a slow zoom-in or zoom-out over the
    clip's duration — the practical stand-in for full keyframe animation in
    an ffmpeg-filter-graph renderer: one motion, not an arbitrary property
    curve, but genuinely smooth and centered on the frame.

    `zoom_cfg`: {"type": "in" | "out", "amount": 0.15} — amount is the total
    zoom delta over the clip (0.15 = ends/starts 15% zoomed in).

    Applied at the source's native resolution (`width`/`height`) as the
    first step in the filter chain, before the scale/grade/setpts that
    follow — `zoompan`'s `s=` option needs literal dimensions, not an
    expression, so it can't reference the later scale target directly.
    """
    amount = max(0.01, float(zoom_cfg.get("amount", 0.15)))
    total_frames = max(1, round(duration * fps))
    step = amount / total_frames
    if zoom_cfg.get("type") == "out":
        z_expr = f"if(eq(on,0),{1 + amount:.4f},max(zoom-{step:.6f},1.0))"
    else:  # "in" (default)
        z_expr = f"min(zoom+{step:.6f},{1 + amount:.4f})"
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"
    return f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d=1:s={width}x{height}:fps={fps}"


# -------- Per-clip transform (scale/rotate/position/opacity/flip) -----------


def build_transform_filter(transform: dict) -> str:
    """Build the -vf chain for a clip's manual transform, operating on the
    frame at whatever size it already is (iw×ih) and leaving it that same
    size afterward — so it can be inserted into the existing per-segment
    chain without disturbing concat's fixed-frame-size assumption.

    `transform`: {"scale": 1.0, "rotation": 0, "x": 0.0, "y": 0.0,
                  "opacity": 1.0, "flip_h": false, "flip_v": false}
    - scale: 1.0 = no zoom. >1 crops in (digital zoom); <1 shrinks with
      black bars (letterbox), both centered then offset by x/y.
    - x/y: recenter offset as a fraction of frame width/height (0.1 = shift
      10% right/down). Only meaningful together with scale != 1, since at
      scale=1 the frame already fills the canvas with nothing to pan into.
    - rotation: degrees, clockwise. Frame size is preserved (rotate=...
      ow=iw:oh=ih), exposed corners filled black.
    - opacity: 1.0 = fully opaque. Since the video track is a single
      sequential layer (nothing beneath a clip to blend with), this is
      approximated as a dissolve toward black rather than true alpha.
    """
    parts: list[str] = []
    scale = float(transform.get("scale", 1.0)) or 1.0
    x = float(transform.get("x", 0.0))
    y = float(transform.get("y", 0.0))
    rotation = float(transform.get("rotation", 0.0))
    opacity = float(transform.get("opacity", 1.0))
    flip_h = bool(transform.get("flip_h"))
    flip_v = bool(transform.get("flip_v"))

    if flip_h:
        parts.append("hflip")
    if flip_v:
        parts.append("vflip")
    if rotation:
        parts.append(f"rotate={rotation:.4f}*PI/180:ow=iw:oh=ih:c=black")
    if abs(scale - 1.0) > 1e-6 or x or y:
        scale = max(0.1, scale)
        parts.append(f"scale=iw*{scale:.4f}:ih*{scale:.4f}")
        if scale >= 1.0:
            parts.append(
                f"crop=iw/{scale:.4f}:ih/{scale:.4f}:"
                f"(iw-iw/{scale:.4f})/2-({x:.4f})*iw/{scale:.4f}:"
                f"(ih-ih/{scale:.4f})/2-({y:.4f})*ih/{scale:.4f}"
            )
        else:
            parts.append(
                f"pad=iw/{scale:.4f}:ih/{scale:.4f}:"
                f"(ow-iw)/2+({x:.4f})*iw/{scale:.4f}:"
                f"(oh-ih)/2+({y:.4f})*ih/{scale:.4f}:color=black"
            )
    if abs(opacity - 1.0) > 1e-6:
        opacity = max(0.0, min(1.0, opacity))
        parts.append(f"colorchannelmixer=rr={opacity:.4f}:gg={opacity:.4f}:bb={opacity:.4f}")

    return ",".join(parts)


# -------- Per-segment extraction (Rule 2 + Rule 3) --------------------------


def atempo_chain(speed: float) -> str:
    """`atempo` only accepts 0.5-2.0 per instance; chain instances to cover
    more extreme speed changes (e.g. 4x = two `atempo=2.0` in a row)."""
    if 0.5 <= speed <= 2.0:
        return f"atempo={speed:.4f}"
    parts: list[str] = []
    remaining = speed
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def extract_segment(
    source: Path,
    seg_start: float,
    duration: float,
    grade_filter: str,
    out_path: Path,
    preview: bool = False,
    draft: bool = False,
    speed: float = 1.0,
    zoom: dict | None = None,
    transform: dict | None = None,
) -> None:
    """Extract a cut range as its own MP4 with grade + 30ms audio fades baked in.

    `-ss` before `-i` for fast accurate seeking. Scale to 1080p from 4K.
    Portrait sources (height > width) are scaled by height to preserve orientation.

    Quality ladder:
      - final (default): 1080p libx264 fast CRF 20
      - preview:         1080p libx264 medium CRF 22 (evaluable for QC)
      - draft:           720p libx264 ultrafast CRF 28 (cut-point check only)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    portrait = is_portrait_source(source)
    if draft:
        scale = "scale=-2:1280" if portrait else "scale=1280:-2"
    else:
        scale = "scale=-2:1920" if portrait else "scale=1920:-2"

    vf_parts: list[str] = []
    if is_hdr_source(source):
        vf_parts.append(TONEMAP_CHAIN)
    if zoom and zoom.get("type") in ("in", "out"):
        native_w, native_h = probe_dimensions(source)
        vf_parts.append(build_zoompan_filter(zoom, duration, native_w, native_h))
    vf_parts.append(scale)
    if transform:
        transform_filter = build_transform_filter(transform)
        if transform_filter:
            vf_parts.append(transform_filter)
    if grade_filter:
        vf_parts.append(grade_filter)
    if speed != 1.0:
        vf_parts.append(f"setpts=PTS/{speed:.4f}")
    vf = ",".join(vf_parts)

    # Speed changes the segment's actual output duration — fades (Rule 3)
    # are timed against that, not the source-timeline duration, since they
    # need to land exactly at the sped-up clip's edges.
    output_duration = duration / speed if speed else duration
    af_parts: list[str] = []
    if speed != 1.0:
        af_parts.append(atempo_chain(speed))
    fade_out_start = max(0.0, output_duration - 0.03)
    af_parts.append(f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03")
    af = ",".join(af_parts)

    if draft:
        preset, crf = "ultrafast", "28"
    elif preview:
        preset, crf = "medium", "22"
    else:
        preset, crf = "fast", "20"

    cmd = [
        "ffmpeg", "-y",
        # -t as an INPUT option (before -i) bounds how much of the SOURCE is
        # read — the correct semantics whether or not a speed filter is about
        # to retime that footage on the output side. -t placed after -i would
        # instead bound the (already-retimed) output timeline, which for
        # speed != 1.0 silently reads the wrong amount of source content.
        "-ss", f"{seg_start:.3f}",
        "-t", f"{duration:.3f}",
        "-i", str(source),
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run_ffmpeg(cmd)


def extract_all_segments(
    edl: dict,
    edit_dir: Path,
    preview: bool,
    draft: bool = False,
) -> list[Path]:
    """Extract every EDL range into edit_dir/clips_graded/seg_NN.mp4.
    Returns the ordered list of segment paths.

    Grade resolution per segment: a range may set its own `grade` field
    (preset name, raw filter, or "auto") which overrides the EDL's global
    `grade`. This lets the visual editor apply a different look per clip —
    the CLI/chat flow keeps working unchanged since `grade` on a range is
    optional and falls back to the global value.
    """
    global_resolved = resolve_grade_filter(edl.get("grade"))
    clips_dir = edit_dir / (
        "clips_draft" if draft else ("clips_preview" if preview else "clips_graded")
    )
    clips_dir.mkdir(parents=True, exist_ok=True)

    ranges = edl["ranges"]
    sources = edl["sources"]

    seg_paths: list[Path] = []
    print(f"extracting {len(ranges)} segment(s) → {clips_dir.name}/")
    for i, r in enumerate(ranges):
        src_name = r["source"]
        src_path = resolve_path(sources[src_name], edit_dir)
        start = float(r["start"])
        end = float(r["end"])
        duration = end - start
        out_path = clips_dir / f"seg_{i:02d}_{src_name}.mp4"

        range_grade = r.get("grade")
        resolved = resolve_grade_filter(range_grade) if range_grade else global_resolved
        is_auto = resolved == "__AUTO__"

        if is_auto:
            seg_filter, _stats = auto_grade_for_clip(src_path, start=start, duration=duration, verbose=False)
        else:
            seg_filter = resolved

        speed = float(r.get("speed", 1.0)) or 1.0
        zoom = r.get("zoom")
        transform = r.get("transform")
        note = r.get("beat") or r.get("note") or ""
        speed_note = f"  speed={speed:g}x" if speed != 1.0 else ""
        zoom_note = f"  zoom={zoom['type']}" if zoom and zoom.get("type") in ("in", "out") else ""
        transform_note = "  transform" if transform else ""
        print(f"  [{i:02d}] {src_name}  {start:7.2f}-{end:7.2f}  ({duration:5.2f}s)  {note}{speed_note}{zoom_note}{transform_note}")
        if is_auto:
            print(f"        grade: {seg_filter or '(none)'}")
        extract_segment(
            src_path, start, duration, seg_filter, out_path,
            preview=preview, draft=draft, speed=speed, zoom=zoom, transform=transform,
        )
        seg_paths.append(out_path)

    return seg_paths


# -------- Lossless concat ----------------------------------------------------


def concat_segments(segment_paths: list[Path], out_path: Path, edit_dir: Path) -> None:
    """Lossless concat via the concat demuxer. No re-encode."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list = edit_dir / "_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths))

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"concat → {out_path.name}")
    run_ffmpeg(cmd)
    concat_list.unlink(missing_ok=True)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


# xfade transition names ffmpeg supports natively (subset exposed to the UI).
XFADE_TRANSITIONS = {
    "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "circleopen", "circleclose", "dissolve", "fadeblack", "fadewhite",
}


def has_real_transitions(transitions: list[dict] | None) -> bool:
    if not transitions:
        return False
    return any((t or {}).get("type", "cut") not in (None, "cut") for t in transitions)


def build_base_with_transitions(
    segment_paths: list[Path],
    transitions: list[dict] | None,
    out_path: Path,
) -> None:
    """Concat segments with per-boundary transitions via ffmpeg xfade/acrossfade.

    `transitions[i]` describes the boundary between segment i and i+1:
    `{"type": "cut"}` (or missing) is a hard cut, everything else is an
    xfade transition name (see XFADE_TRANSITIONS) with a `duration` in
    seconds. Re-encodes (transitions can't be done with lossless concat),
    so this path is only used when at least one real transition is present —
    pure-cut EDLs keep using the fast lossless `concat_segments` path.
    """
    n = len(segment_paths)
    durations = [probe_duration(p) for p in segment_paths]
    inputs: list[str] = []
    for p in segment_paths:
        inputs += ["-i", str(p)]

    vparts: list[str] = []
    aparts: list[str] = []
    cumulative = durations[0]
    prev_v, prev_a = "0:v", "0:a"

    for i in range(1, n):
        t = (transitions[i - 1] if transitions and i - 1 < len(transitions) else None) or {}
        ttype = t.get("type", "cut")
        vlabel, alabel = f"v{i}", f"a{i}"

        if ttype == "cut" or ttype is None:
            vparts.append(f"[{prev_v}][{i}:v]concat=n=2:v=1:a=0[{vlabel}]")
            aparts.append(f"[{prev_a}][{i}:a]concat=n=2:v=0:a=1[{alabel}]")
            cumulative = cumulative + durations[i]
        else:
            xtype = ttype if ttype in XFADE_TRANSITIONS else "fade"
            dur = float(t.get("duration", 0.4))
            dur = max(0.05, min(dur, durations[i - 1] * 0.9, durations[i] * 0.9))
            offset = max(0.0, cumulative - dur)
            vparts.append(
                f"[{prev_v}][{i}:v]xfade=transition={xtype}:duration={dur:.3f}:offset={offset:.3f}[{vlabel}]"
            )
            aparts.append(f"[{prev_a}][{i}:a]acrossfade=d={dur:.3f}[{alabel}]")
            cumulative = cumulative + durations[i] - dur

        prev_v, prev_a = vlabel, alabel

    filter_complex = ";".join(vparts + aparts)
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"concat with transitions → {out_path.name}")
    run_ffmpeg(cmd)


# -------- Master SRT (Rule 5) ------------------------------------------------


PUNCT_BREAK = set(".,!?;:")


def _srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _words_in_range(transcript: dict, t_start: float, t_end: float) -> list[dict]:
    out: list[dict] = []
    for w in transcript.get("words", []):
        if w.get("type") != "word":
            continue
        ws = w.get("start")
        we = w.get("end")
        if ws is None or we is None:
            continue
        if we <= t_start or ws >= t_end:
            continue
        out.append(w)
    return out


def build_master_srt(edl: dict, edit_dir: Path, out_path: Path) -> None:
    """Build an output-timeline SRT from per-source transcripts.

    - 2-word chunks (break on any punctuation in between)
    - UPPERCASE text
    - Output times computed as word.start - segment_start + segment_offset
    """
    transcripts_dir = edit_dir / "transcripts"
    sources = edl["sources"]

    entries: list[tuple[float, float, str]] = []
    seg_offset = 0.0

    for r in edl["ranges"]:
        src_name = r["source"]
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        speed = float(r.get("speed", 1.0)) or 1.0
        seg_duration = (seg_end - seg_start) / speed

        tr_path = transcripts_dir / f"{src_name}.json"
        if not tr_path.exists():
            print(f"  no transcript for {src_name}, skipping captions for this segment")
            seg_offset += seg_duration
            continue

        transcript = json.loads(tr_path.read_text())
        words_in_seg = _words_in_range(transcript, seg_start, seg_end)

        # Group into 2-word chunks, break on punctuation
        chunks: list[list[dict]] = []
        current: list[dict] = []
        for w in words_in_seg:
            text = (w.get("text") or "").strip()
            if not text:
                continue
            current.append(w)
            # Break if the current text ends in punctuation or we hit 2 words
            ends_in_punct = bool(text) and text[-1] in PUNCT_BREAK
            if len(current) >= 2 or ends_in_punct:
                chunks.append(current)
                current = []
        if current:
            chunks.append(current)

        for chunk in chunks:
            local_start = max(seg_start, chunk[0].get("start", seg_start))
            local_end = min(seg_end, chunk[-1].get("end", seg_end))
            out_start = max(0.0, local_start - seg_start) / speed + seg_offset
            out_end = max(0.0, local_end - seg_start) / speed + seg_offset
            if out_end <= out_start:
                out_end = out_start + 0.4
            text = " ".join((w.get("text") or "").strip() for w in chunk)
            text = re.sub(r"\s+", " ", text).strip()
            # Strip trailing punctuation for cleaner uppercase look
            text = text.rstrip(",;:")
            text = text.upper()
            entries.append((out_start, out_end, text))

        seg_offset += seg_duration

    # Sort and write as SRT
    entries.sort(key=lambda e: e[0])
    lines: list[str] = []
    for i, (a, b, t) in enumerate(entries, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(a)} --> {_srt_timestamp(b)}")
        lines.append(t)
        lines.append("")
    out_path.write_text("\n".join(lines))
    print(f"master SRT → {out_path.name} ({len(entries)} cues)")


# -------- Loudness normalization (social-ready audio) -----------------------


# Social-media standard: -14 LUFS integrated, -1 dBTP peak, LRA 11 LU.
# Matches YouTube / Instagram / TikTok / X / LinkedIn normalization targets.
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0


def measure_loudness(video_path: Path) -> dict[str, str] | None:
    """Run ffmpeg loudnorm first pass and parse the JSON measurement.

    Returns a dict with measured_i, measured_tp, measured_lra, measured_thresh,
    target_offset, or None if measurement failed.
    """
    filter_str = (
        f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(video_path),
        "-af", filter_str,
        "-vn", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # loudnorm prints the JSON to stderr at the end of the run
    stderr = proc.stderr

    # Find the JSON block — loudnorm output contains a `{ ... }` block
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None
    needed = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    if not needed.issubset(data.keys()):
        return None
    return data


def apply_loudnorm_two_pass(
    input_path: Path,
    output_path: Path,
    preview: bool = False,
) -> bool:
    """Run two-pass loudnorm on input_path, write normalized copy to output_path.

    Returns True on success, False if measurement failed (caller should fall
    back to copying the input unchanged).

    In preview mode, skips the measurement pass and uses a one-pass approximation
    for speed. Final mode always does the proper two-pass.
    """
    if preview:
        # One-pass approximation — faster, slightly less accurate.
        filter_str = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats",
            "-i", str(input_path),
            "-c:v", "copy",
            "-af", filter_str,
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            str(output_path),
        ]
        print(f"  loudnorm (1-pass preview) → {output_path.name}")
        run_ffmpeg(cmd)
        return True

    # Full two-pass
    print(f"  loudnorm pass 1: measuring {input_path.name}")
    measurement = measure_loudness(input_path)
    if measurement is None:
        print("  loudnorm measurement failed — falling back to 1-pass")
        return apply_loudnorm_two_pass(input_path, output_path, preview=True)

    print(f"    measured: I={measurement['input_i']} LUFS  "
          f"TP={measurement['input_tp']}  LRA={measurement['input_lra']}")

    filter_str = (
        f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        f":measured_I={measurement['input_i']}"
        f":measured_TP={measurement['input_tp']}"
        f":measured_LRA={measurement['input_lra']}"
        f":measured_thresh={measurement['input_thresh']}"
        f":offset={measurement['target_offset']}"
        f":linear=true"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(input_path),
        "-c:v", "copy",
        "-af", filter_str,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ]
    print(f"  loudnorm pass 2: normalizing → {output_path.name}")
    run_ffmpeg(cmd)
    return True


# -------- Text overlay cards (drawtext, composited like video overlays) -----

TEXT_X = "(w-text_w)/2"
TEXT_Y = {
    "top": "h*0.08",
    "center": "(h-text_h)/2",
    "bottom": "h*0.85",
}
TEXT_ANIMATIONS = {"none", "fade", "slide_up"}


def escape_drawtext(text: str) -> str:
    """Escape text for ffmpeg's drawtext filter syntax (not shell syntax —
    args are passed as a list, so only ffmpeg's own filter escaping applies).
    Straight apostrophes are swapped for a typographic quote to sidestep
    drawtext's fiddly nested single-quote escaping.
    """
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("%", "\\%")
    text = text.replace("'", "’")
    return text


def build_drawtext_filter(overlay: dict) -> str:
    """Build a `drawtext=...` filter string for a text-type overlay entry.

    Expected shape:
        {"type": "text", "text": "...", "start_in_output": 0.0, "duration": 2.0,
         "style": {"position": "bottom", "font_size": 54, "color": "white",
                   "background": true, "font": "Helvetica",
                   "animation": "none" | "fade" | "slide_up"}}

    `animation` is an entrance effect over the first ~0.3s of the window
    (capped at a third of the card's duration for very short cards):
    "fade" ramps opacity in (and back out in the closing 0.3s), "slide_up"
    animates the y position in from 40px below its resting spot.
    """
    style = overlay.get("style") or {}
    text = escape_drawtext(str(overlay.get("text", "")))
    t = float(overlay["start_in_output"])
    dur = float(overlay["duration"])
    end = t + dur
    ramp = min(0.3, dur / 3)

    font_size = int(style.get("font_size", 54))
    color = style.get("color", "white")
    font = style.get("font", "Helvetica")
    y_expr = TEXT_Y.get(style.get("position", "bottom"), TEXT_Y["bottom"])
    animation = style.get("animation", "none")
    if animation not in TEXT_ANIMATIONS:
        animation = "none"

    if animation == "slide_up":
        progress = f"min(1,max(0,(t-{t:.3f})/{ramp:.3f}))"
        y_expr = f"({y_expr})+40*(1-{progress})"

    parts = [
        f"text='{text}'",
        f"font='{font}'",
        f"fontsize={font_size}",
        f"fontcolor={color}",
        f"x={TEXT_X}",
        f"y='{y_expr}'",
        f"enable='between(t,{t:.3f},{end:.3f})'",
    ]
    if animation == "fade":
        alpha_expr = (
            f"if(lt(t,{t:.3f}+{ramp:.3f}),(t-{t:.3f})/{ramp:.3f},"
            f"if(lt(t,{end:.3f}-{ramp:.3f}),1,({end:.3f}-t)/{ramp:.3f}))"
        )
        parts.append(f"alpha='{alpha_expr}'")
    if style.get("background", True):
        box_color = style.get("background_color", "black@0.5")
        parts.append(f"box=1:boxcolor={box_color}:boxborderw=16")
    return "drawtext=" + ":".join(parts)


# -------- Sticker overlays (static image, positioned/scaled) ----------------


def build_sticker_filters(overlay: dict, input_idx: int, current_label: str, out_label: str) -> list[str]:
    """Build the scale+overlay filter pair for a sticker-type overlay entry.

    Expected shape:
        {"type": "sticker", "file": "...", "start_in_output": 0.0, "duration": 2.0,
         "x": 0.5, "y": 0.5, "scale": 0.3}
    `x`/`y` are the sticker's center as a fraction of frame width/height
    (0.5, 0.5 = centered). `scale` is the sticker's width as a fraction of
    frame width, height keeps aspect ratio.
    """
    t = float(overlay["start_in_output"])
    dur = float(overlay["duration"])
    end = t + dur
    x = float(overlay.get("x", 0.5))
    y = float(overlay.get("y", 0.5))
    scale = float(overlay.get("scale", 0.3))
    scaled_label = f"[stk{input_idx}]"
    return [
        f"[{input_idx}:v]scale=iw*{scale}:-1{scaled_label}",
        f"{current_label}{scaled_label}overlay="
        f"x=(W*{x})-w/2:y=(H*{y})-h/2:enable='between(t,{t:.3f},{end:.3f})'{out_label}",
    ]


# -------- Background audio mixing (music, ambience) -------------------------


def mix_audio_tracks(video_path: Path, audio_tracks: list[dict], out_path: Path, edit_dir: Path) -> None:
    """Mix background audio tracks (music, ambience) into `video_path`'s
    existing audio, keeping the video stream untouched (`-c:v copy`).

    Each entry:
        {"file": "...", "start_in_output": 0.0, "duration": 5.0,
         "trim_in": 0.0, "volume": 1.0, "fade_in": 0.0, "fade_out": 0.0}
    `trim_in`/`duration` select the slice of the source file to use;
    `start_in_output` positions that slice on the output timeline.
    """
    inputs: list[str] = ["-i", str(video_path)]
    filter_parts: list[str] = []
    mix_labels = ["[0:a]"]

    for i, track in enumerate(audio_tracks, start=1):
        src = resolve_path(track["file"], edit_dir)
        trim_in = float(track.get("trim_in", 0.0))
        dur = float(track["duration"])
        inputs += ["-ss", f"{trim_in:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]

        vol = float(track.get("volume", 1.0))
        fade_in = float(track.get("fade_in", 0.0))
        fade_out = float(track.get("fade_out", 0.0))
        start = float(track.get("start_in_output", 0.0))

        chain = [f"volume={vol:.3f}"]
        if fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            chain.append(f"afade=t=out:st={max(0.0, dur - fade_out):.3f}:d={fade_out:.3f}")
        # `all=1` applies the delay across every channel regardless of layout
        # (mono vs stereo source), avoiding a channel-count mismatch.
        chain.append(f"adelay=delays={int(start * 1000)}:all=1")

        label = f"[bg{i}]"
        filter_parts.append(f"[{i}:a]{','.join(chain)}{label}")
        mix_labels.append(label)

    # duration=first keeps the mix locked to the base video's audio length,
    # regardless of how long the background tracks run.
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[aout]"
    )
    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"mixing {len(audio_tracks)} background audio track(s) → {out_path.name}")
    run_ffmpeg(cmd)


# -------- Final compositing (Rule 1 + Rule 4) -------------------------------


def build_final_composite(
    base_path: Path,
    overlays: list[dict],
    subtitles_path: Path | None,
    out_path: Path,
    edit_dir: Path,
) -> None:
    """Final pass: base → video overlays (PTS-shifted) → stickers → text cards
    → subtitles LAST → out.

    `overlays` entries default to video-file overlays (`{"file": ...}`) and
    may also be text cards (`{"type": "text", ...}`, drawtext) or stickers
    (`{"type": "sticker", "file": <image>, "x":.., "y":.., "scale":..}`,
    a positioned/scaled static image). Composited in that order, still
    before subtitles (Rule 1).

    If there is nothing to composite, just copy base to out.
    """
    video_overlays = [ov for ov in overlays if ov.get("type") not in ("text", "sticker")]
    sticker_overlays = [ov for ov in overlays if ov.get("type") == "sticker"]
    text_overlays = [ov for ov in overlays if ov.get("type") == "text"]
    has_overlays = bool(video_overlays)
    has_stickers = bool(sticker_overlays)
    has_text = bool(text_overlays)
    # A zero-byte SRT (e.g. no transcript was available for any source) makes
    # libass fail with "Unable to open" — treat it the same as "no subtitles".
    has_subs = (
        subtitles_path is not None
        and subtitles_path.exists()
        and subtitles_path.stat().st_size > 0
    )

    if not has_overlays and not has_stickers and not has_text and not has_subs:
        # Nothing to do — just rename/copy base to final name
        run(["ffmpeg", "-y", "-i", str(base_path), "-c", "copy", str(out_path)], quiet=True)
        return

    inputs: list[str] = ["-i", str(base_path)]
    for ov in video_overlays:
        ov_path = resolve_path(ov["file"], edit_dir)
        inputs += ["-i", str(ov_path)]
    sticker_start_idx = 1 + len(video_overlays)
    for ov in sticker_overlays:
        ov_path = resolve_path(ov["file"], edit_dir)
        inputs += ["-loop", "1", "-t", f"{float(ov['duration']):.3f}", "-i", str(ov_path)]

    filter_parts: list[str] = []
    # PTS-shift every video overlay so its frame 0 lands at start_in_output
    for idx, ov in enumerate(video_overlays, start=1):
        t = float(ov["start_in_output"])
        filter_parts.append(f"[{idx}:v]setpts=PTS-STARTPTS+{t}/TB[a{idx}]")

    # Chain video overlays on top of base
    current = "[0:v]"
    for idx, ov in enumerate(video_overlays, start=1):
        t = float(ov["start_in_output"])
        dur = float(ov["duration"])
        end = t + dur
        next_label = f"[v{idx}]"
        filter_parts.append(
            f"{current}[a{idx}]overlay=enable='between(t,{t:.3f},{end:.3f})'{next_label}"
        )
        current = next_label

    # Stickers — scaled + positioned image overlays, chained next
    for i, ov in enumerate(sticker_overlays):
        input_idx = sticker_start_idx + i
        next_label = f"[s{input_idx}]"
        filter_parts.extend(build_sticker_filters(ov, input_idx, current, next_label))
        current = next_label

    # Text cards — drawtext, chained after overlays/stickers
    for idx, ov in enumerate(text_overlays, start=1):
        next_label = f"[txt{idx}]"
        filter_parts.append(f"{current}{build_drawtext_filter(ov)}{next_label}")
        current = next_label

    # Subtitles LAST — Rule 1
    if has_subs:
        subs_abs = str(subtitles_path.resolve()).replace(":", r"\:").replace("'", r"\'")
        filter_parts.append(
            f"{current}subtitles='{subs_abs}':force_style='{SUB_FORCE_STYLE}'[outv]"
        )
        out_label = "[outv]"
    else:
        # Rename the last stage's output to [outv] for consistency
        if has_overlays or has_stickers or has_text:
            filter_parts.append(f"{current}null[outv]")
            out_label = "[outv]"
        else:
            out_label = "[0:v]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", out_label,
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"compositing → {out_path.name}")
    print(f"  overlays: {len(video_overlays)}, stickers: {len(sticker_overlays)}, "
          f"text: {len(text_overlays)}, subtitles: {'yes' if has_subs else 'no'}")
    run_ffmpeg(cmd)


# -------- Main ---------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a video from an EDL")
    ap.add_argument("edl", type=Path, help="Path to edl.json")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output video path")
    ap.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: 1080p, medium, CRF 22 — evaluable for QC, faster than final.",
    )
    ap.add_argument(
        "--draft",
        action="store_true",
        help="Draft mode: 720p, ultrafast, CRF 28 — cut-point verification only.",
    )
    ap.add_argument(
        "--build-subtitles",
        action="store_true",
        help="Build master.srt from transcripts + EDL offsets before compositing",
    )
    ap.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Skip subtitles even if the EDL references one",
    )
    ap.add_argument(
        "--no-loudnorm",
        action="store_true",
        help="Skip audio loudness normalization. Default is on (-14 LUFS, -1 dBTP, LRA 11).",
    )
    args = ap.parse_args()

    edl_path = args.edl.resolve()
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")

    edl = json.loads(edl_path.read_text())
    edit_dir = edl_path.parent
    out_path = args.output.resolve()

    # 1. Extract per-segment (auto-grade per range if EDL grade is "auto")
    segment_paths = extract_all_segments(
        edl, edit_dir, preview=args.preview, draft=args.draft
    )

    # 2. Concat → base
    if args.draft:
        base_name = "base_draft.mp4"
    elif args.preview:
        base_name = "base_preview.mp4"
    else:
        base_name = "base.mp4"
    base_path = edit_dir / base_name
    transitions = edl.get("transitions")
    if has_real_transitions(transitions):
        build_base_with_transitions(segment_paths, transitions, base_path)
    else:
        concat_segments(segment_paths, base_path, edit_dir)

    # 3. Subtitles: build if requested, resolve final path
    subs_path: Path | None = None
    if not args.no_subtitles:
        if args.build_subtitles:
            subs_path = edit_dir / "master.srt"
            build_master_srt(edl, edit_dir, subs_path)
        elif edl.get("subtitles"):
            subs_path = resolve_path(edl["subtitles"], edit_dir)
            if not subs_path.exists():
                print(f"warning: subtitles path in EDL does not exist: {subs_path}")
                subs_path = None

    # 4. Composite (overlays + subtitles LAST) → intermediate (pre-loudnorm) path
    overlays = edl.get("overlays") or []
    composite_path = out_path if args.no_loudnorm else out_path.with_suffix(".prenorm.mp4")
    build_final_composite(base_path, overlays, subs_path, composite_path, edit_dir)

    # 5. Mix in background audio tracks (music, ambience), if any
    audio_tracks = edl.get("audio_tracks") or []
    if audio_tracks:
        mixed_path = composite_path.with_suffix(".withmusic.mp4")
        mix_audio_tracks(composite_path, audio_tracks, mixed_path, edit_dir)
        composite_path.unlink(missing_ok=True)
        mixed_path.rename(composite_path)

    if not args.no_loudnorm:
        print("loudness normalization → social-ready (-14 LUFS / -1 dBTP / LRA 11)")
        apply_loudnorm_two_pass(composite_path, out_path, preview=args.draft)
        composite_path.unlink(missing_ok=True)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
