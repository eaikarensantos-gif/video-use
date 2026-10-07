"""Export one finished short into clean per-platform files.

Takes a single edited clip (usually `edit/final.mp4` from video-use) and writes
one file per platform into `<out_dir>/`, all 1080x1920 9:16, H.264 + AAC,
loudness-normalized, with no watermark from any other platform.

Per-platform differences are deliberately small: duration cap, frame-rate cap
and file naming. The platform limits below are defaults, not truths — every
platform changes them. Override with `--max-seconds platform=N` when needed.

Usage:
    python export_platforms.py <input> -o <out_dir>
    python export_platforms.py <input> -o <out_dir> --platforms youtube,tiktok
    python export_platforms.py <input> -o <out_dir> --fit pad          # blur-pad instead of crop
    python export_platforms.py <input> -o <out_dir> --handle @meucanal # small handle, top-left
    python export_platforms.py <input> -o <out_dir> --ai-label         # "Conteúdo feito com IA" tag
    python export_platforms.py <input> -o <out_dir> --trim             # cut to platform cap instead of warn
    python export_platforms.py <input> -o <out_dir> --max-seconds kwai=60
    python export_platforms.py <input> --safe-zones <png>              # one frame with UI zones drawn

Writes `<out_dir>/manifest.json` with every output, its duration and warnings.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


W, H = 1080, 1920

# Defaults checked in late 2026. Platforms move these often — treat as starting points.
PLATFORMS: dict[str, dict] = {
    "youtube":  {"label": "YouTube Shorts",  "max_seconds": 180, "max_fps": 60},
    "tiktok":   {"label": "TikTok",          "max_seconds": 600, "max_fps": 60},
    "kwai":     {"label": "Kwai",            "max_seconds": 600, "max_fps": 30},
    "facebook": {"label": "Facebook Reels",  "max_seconds": 180, "max_fps": 60},
}

# Approximate areas covered by platform UI on a 1080x1920 frame (x, y, w, h).
# Keep captions and key text out of these.
UI_ZONES: dict[str, list[tuple[int, int, int, int]]] = {
    "youtube":  [(0, 1500, W, 420), (940, 900, 140, 600)],
    "tiktok":   [(0, 1560, W, 360), (950, 760, 130, 800), (0, 0, W, 160)],
    "kwai":     [(0, 1540, W, 380), (940, 800, 140, 740)],
    "facebook": [(0, 1500, W, 420), (940, 900, 140, 600)],
}
ZONE_COLORS = {"youtube": "red", "tiktok": "cyan", "kwai": "orange", "facebook": "blue"}

TARGET_LUFS = -14.0
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        sys.exit(f"no video stream in {path}")
    num, den = (video.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "duration": float(data["format"]["duration"]),
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


def find_font() -> str | None:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def escape_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def video_filter(info: dict, fit: str, fps: float, handle: str | None, ai_label: bool) -> str:
    """Build the [0:v] -> [v] filtergraph."""
    is_vertical = abs(info["width"] / info["height"] - W / H) < 0.01
    if is_vertical:
        chain = f"[0:v]scale={W}:{H}:flags=lanczos,setsar=1[base]"
    elif fit == "crop":
        chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={W}:{H},setsar=1[base]")
    else:
        chain = (f"[0:v]split[a][b];"
                 f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"boxblur=40:2,eq=brightness=-0.08[bg];"
                 f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")

    last = "base"
    font = find_font()
    texts = []
    if handle:
        texts.append((handle, "x=48:y=200", 34, "white@0.85"))
    if ai_label:
        texts.append(("Conteúdo feito com IA", "x=48:y=250", 30, "white@0.95"))
    for i, (text, pos, size, color) in enumerate(texts):
        if font is None:
            print("warn: no font found, skipping text overlays", file=sys.stderr)
            break
        out = f"t{i}"
        chain += (f";[{last}]drawtext=fontfile='{font}':text='{escape_text(text)}':"
                  f"{pos}:fontsize={size}:fontcolor={color}:"
                  f"box=1:boxcolor=black@0.45:boxborderw=12[{out}]")
        last = out

    chain += f";[{last}]fps={fps:g},format=yuv420p[v]"
    return chain


def export_one(src: Path, dst: Path, info: dict, platform: str, cfg: dict,
               fit: str, handle: str | None, ai_label: bool, trim: bool) -> dict:
    warnings: list[str] = []
    duration = info["duration"]
    cap = cfg["max_seconds"]
    t_args: list[str] = []
    if duration > cap:
        if trim:
            t_args = ["-t", f"{cap:.3f}"]
            warnings.append(f"trimmed from {duration:.1f}s to platform cap {cap}s")
            duration = float(cap)
        else:
            warnings.append(f"{duration:.1f}s exceeds {cfg['label']} cap of {cap}s (use --trim)")

    fps = min(info["fps"], cfg["max_fps"])
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), *t_args,
           "-filter_complex", video_filter(info, fit, fps, handle, ai_label),
           "-map", "[v]"]
    if info["has_audio"]:
        cmd += ["-map", "0:a:0", "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.0:LRA=11",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        warnings.append("source has no audio track")
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-map_metadata", "-1",   # strip source metadata (GPS, device, editor tags)
            str(dst)]
    subprocess.run(cmd, check=True)
    return {"platform": platform, "file": dst.name, "duration": round(duration, 2),
            "fps": round(fps, 3), "warnings": warnings}


def safe_zone_frame(src: Path, png: Path, info: dict, fit: str) -> None:
    t = min(1.0, info["duration"] / 2)
    boxes = ",".join(
        f"drawbox=x={x}:y={y}:w={w}:h={h}:color={ZONE_COLORS[p]}@0.25:t=fill"
        for p, zones in UI_ZONES.items() for (x, y, w, h) in zones
    )
    chain = video_filter(info, fit, 30, None, False) + f";[v]{boxes}[zones]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(src),
                    "-filter_complex", chain, "-map", "[zones]",
                    "-frames:v", "1", str(png)], check=True)


def parse_overrides(items: list[str]) -> dict[str, int]:
    out = {}
    for item in items:
        name, _, value = item.partition("=")
        if name not in PLATFORMS or not value.isdigit():
            sys.exit(f"bad --max-seconds value: {item!r} (expected platform=N)")
        out[name] = int(value)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a short to per-platform 9:16 files")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--out-dir", type=Path)
    ap.add_argument("--platforms", default=",".join(PLATFORMS))
    ap.add_argument("--fit", choices=["crop", "pad"], default="crop",
                    help="non-vertical sources: center crop (default) or blurred pad")
    ap.add_argument("--handle", help="channel handle drawn small at top-left")
    ap.add_argument("--ai-label", action="store_true",
                    help="burn 'Conteúdo feito com IA' tag (required for AI-altered electoral content in BR)")
    ap.add_argument("--trim", action="store_true", help="cut to platform cap instead of warning")
    ap.add_argument("--max-seconds", action="append", default=[], metavar="PLATFORM=N")
    ap.add_argument("--safe-zones", type=Path, metavar="PNG",
                    help="write one frame with every platform's UI zones drawn, then exit")
    args = ap.parse_args()

    src = args.input.resolve()
    info = probe(src)

    if args.safe_zones:
        safe_zone_frame(src, args.safe_zones, info, args.fit)
        print(f"safe-zone frame -> {args.safe_zones}")
        return

    if args.out_dir is None:
        ap.error("-o/--out-dir is required unless --safe-zones is used")
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        sys.exit(f"unknown platform(s): {', '.join(unknown)}; known: {', '.join(PLATFORMS)}")
    overrides = parse_overrides(args.max_seconds)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for p in platforms:
        cfg = dict(PLATFORMS[p])
        if p in overrides:
            cfg["max_seconds"] = overrides[p]
        dst = args.out_dir / f"{src.stem}__{p}.mp4"
        r = export_one(src, dst, info, p, cfg, args.fit, args.handle, args.ai_label, args.trim)
        results.append(r)
        flag = f"  ! {'; '.join(r['warnings'])}" if r["warnings"] else ""
        print(f"{cfg['label']:<16} -> {dst.name} ({r['duration']}s){flag}")

    manifest = {"source": str(src), "source_info": info, "fit": args.fit,
                "handle": args.handle, "ai_label": args.ai_label, "outputs": results}
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
