"""Give each static carousel slide a small, looping motion and export one video per slide.

Only the elements listed in the spec move; everything else stays still:
  - "star":  sparkle. Slow wobble plus a short glint (scale pop + soft glow).
  - "sway":  gentle balance. Tiny rotation and vertical drift around the centre.

The original element is removed from the base plate (filled with the slide's
background colour on flat slides, inpainted on photos) and redrawn as a moving
sprite, so nothing is duplicated when it rotates. Every period divides the
duration, so the video loops without a jump.

Spec (JSON):
{
  "duration": 6, "fps": 30,
  "slides": [
    {"file": "slide-01.png", "out": "slide-01.mp4", "elements": [
      {"type": "star", "box": [x0, y0, x1, y1], "phase": 0.0},
      {"type": "sway", "box": [x0, y0, x1, y1], "mask": "mint"}
    ]}
  ]
}

`mask` picks which pixels belong to the element when the slide is a photo:
"mint" (highlight boxes), "dark" (dark pills) or "color" (saturated stars).
On flat slides anything that differs from the background colour is used.

Usage:
    python helpers/slide_micro_motion.py spec.json --src slides/ --out out/
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def flat_bg(a: np.ndarray) -> tuple[int, int, int] | None:
    border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
                             a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)]).astype(int)
    return tuple(int(v) for v in border[0]) if np.abs(border - border[0]).max() < 6 else None


def element_mask(a: np.ndarray, box, bg, kind: str) -> np.ndarray:
    """Boolean mask (full slide size) of the element's pixels inside its box."""
    x0, y0, x1, y1 = box
    pad = 16
    crop = np.pad(a[y0:y1, x0:x1].astype(int), ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    r, g, b = crop[..., 0], crop[..., 1], crop[..., 2]
    if bg is not None:
        # loose threshold + 1px grow keeps anti-aliased edges inside the sprite
        m = ndimage.binary_dilation(np.abs(crop - np.array(bg)).sum(-1) > 4)
    elif kind == "mint":
        m = (g > 200) & (b > 180) & (r > 150) & (g - r > 20)
        m = ndimage.binary_closing(m, iterations=12)
    elif kind == "dark":
        m = (r < 70) & (g < 70) & (b < 70)
        m = ndimage.binary_closing(m, iterations=6)
    else:  # saturated colour
        m = (crop.max(-1) - crop.min(-1)) > 80
    m = ndimage.binary_fill_holes(m)
    if bg is None:  # photos: drop specks, keep the solid shapes
        m = ndimage.binary_opening(m, iterations=2)
        m = ndimage.binary_dilation(m, iterations=2)
    full = np.zeros(a.shape[:2], bool)
    full[y0:y1, x0:x1] = m[pad:-pad, pad:-pad]
    return full


class Sprite:
    def __init__(self, a: np.ndarray, mask: np.ndarray, box, el: dict):
        x0, y0, x1, y1 = box
        alpha = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8))
        alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))
        self.img = Image.fromarray(a[y0:y1, x0:x1]).convert("RGBA")
        self.img.putalpha(alpha)
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.el = el
        if el["type"] == "star":
            glow = Image.new("RGBA", self.img.size, (255, 244, 214, 0))
            glow.putalpha(alpha.filter(ImageFilter.GaussianBlur(9)))
            self.glow = glow

    def transform(self, img: Image.Image, size, scale: float, angle_deg: float, dx: float, dy: float):
        a = math.radians(angle_deg)
        cos, sin = math.cos(a) / scale, math.sin(a) / scale
        w, h = img.size
        ox, oy = self.cx + dx, self.cy + dy
        # output (X, Y) -> input: rotate/scale about the element centre
        coeffs = (cos, sin, w / 2 - cos * ox - sin * oy,
                  -sin, cos, h / 2 + sin * ox - cos * oy)
        return img.transform(size, Image.AFFINE, coeffs, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))

    def draw(self, frame: Image.Image, t: float, dur: float):
        el = self.el
        ph = el.get("phase", 0.0)
        if el["type"] == "star":
            period = el.get("period", dur / 2)
            u = ((t / period) + ph) % 1.0
            wobble = 5 * math.sin(2 * math.pi * (t / dur * 2 + ph))
            pop = math.sin(math.pi * ease(u / 0.3)) if u < 0.3 else 0.0  # glint in the first 30% of each period
            scale = 1 + 0.03 * math.sin(2 * math.pi * (t / dur * 2 + ph)) + 0.16 * pop
            frame.alpha_composite(self.transform(self.img, frame.size, scale, wobble, 0, 0))
            if pop > 0.01:
                g = self.transform(self.glow, frame.size, scale * 1.15, wobble, 0, 0)
                g.putalpha(g.getchannel("A").point(lambda v: int(v * 0.75 * pop)))
                frame.alpha_composite(g)
        else:
            cycles = el.get("cycles", 2)
            s = math.sin(2 * math.pi * (t / dur * cycles + ph))
            c = math.sin(2 * math.pi * (t / dur * cycles + ph + 0.25))
            angle = el.get("angle", 0.7) * s
            dy = el.get("drift", 3.0) * c
            frame.alpha_composite(self.transform(self.img, frame.size, 1.0, angle, 0, dy))


def render(src: Path, out: Path, elements: list[dict], dur: float, fps: int):
    a = np.asarray(Image.open(src).convert("RGB"))
    bg = flat_bg(a)
    base = a.copy()
    sprites = []
    hole = np.zeros(a.shape[:2], bool)
    for el in elements:
        box = el["box"]
        mask = element_mask(a, box, bg, el.get("mask", "color"))
        sprites.append(Sprite(a, mask, box, el))
        hole |= ndimage.binary_dilation(mask, iterations=4)
    if bg is not None:
        base[hole] = bg
    else:
        base = cv2.inpaint(base, hole.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
    plate = Image.fromarray(base).convert("RGBA")

    h, w = a.shape[:2]
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for f in range(round(dur * fps)):
        frame = plate.copy()
        for s in sprites:
            s.draw(frame, f / fps, dur)
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"ffmpeg failed on {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    spec = json.loads(args.spec.read_text())
    for s in spec["slides"]:
        out = args.out / s.get("out", Path(s["file"]).with_suffix(".mp4").name)
        render(args.src / s["file"], out, s["elements"], spec.get("duration", 6), spec.get("fps", 30))
        print(out)


if __name__ == "__main__":
    main()
