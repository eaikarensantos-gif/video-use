"""ffprobe/thumbnail/waveform helpers for the editor backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np


def ffprobe_json(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def probe_media(path: Path) -> dict:
    """Return duration/width/height/fps/has_audio for a media file."""
    data = ffprobe_json(path)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = fmt.get("duration") or (vstream or {}).get("duration") or 0.0
    duration = float(duration)

    fps = None
    if vstream and vstream.get("r_frame_rate"):
        num, _, den = vstream["r_frame_rate"].partition("/")
        den_f = float(den) if den and float(den) else 1.0
        try:
            fps = round(float(num) / den_f, 3)
        except ValueError:
            fps = None

    return {
        "duration": duration,
        "width": int(vstream["width"]) if vstream and vstream.get("width") else None,
        "height": int(vstream["height"]) if vstream and vstream.get("height") else None,
        "fps": fps,
        "has_audio": astream is not None,
    }


def generate_thumbnail(path: Path, out_path: Path, at: float = 0.0, width: int = 320) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{at:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale={width}:-2", str(out_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def generate_waveform_peaks(path: Path, num_points: int = 800) -> list[float]:
    """Downmix to mono 8kHz PCM float32 and return `num_points` peak (abs max) samples."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-f", "f32le", "-ac", "1", "-ar", "8000", "-"]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    samples = np.frombuffer(proc.stdout, dtype=np.float32)
    if samples.size == 0:
        return []
    chunk = max(1, samples.size // num_points)
    peaks: list[float] = []
    for i in range(0, samples.size, chunk):
        window = samples[i:i + chunk]
        if window.size:
            peaks.append(float(np.abs(window).max()))
    return peaks
