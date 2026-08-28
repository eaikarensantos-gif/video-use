"""Transcript-driven cleanup: detect silences and unambiguous filler-word
interjections in a source's transcript, and compute the sub-ranges of a
clip that remain after removing them.

Deliberately conservative on filler words — only standalone interjections
("um", "uh", "erm"...) are flagged. Words like "like", "so", "actually" are
too context-dependent to strip blindly (they're often not filler at all),
so they're left for the human to cut by hand if they want them gone —
matches this project's "never over-trust an automated destructive edit"
stance (see SKILL.md Hard Rule 11: propose, then confirm, then execute).
"""

from __future__ import annotations

import json
from pathlib import Path

FILLER_WORDS = {"um", "uh", "erm", "uhh", "umm", "hmm", "hm", "uhm"}


def detect_cleanup_spans(transcript_path: Path, silence_threshold: float = 0.6) -> list[dict]:
    """Return every removable span in a transcript, sorted by start time.

    Each entry: {"start": float, "end": float, "kind": "silence" | "filler", "label": str}.
    Scribe `words` entries have type 'word', 'spacing', or 'audio_event' —
    'spacing' entries carry the gap between spoken words via their own
    start/end, which is what a silence longer than `silence_threshold` is
    measured against.
    """
    data = json.loads(transcript_path.read_text())
    words = data.get("words", [])
    spans: list[dict] = []

    for w in words:
        t = w.get("type", "word")
        start = w.get("start")
        end = w.get("end")
        if start is None or end is None:
            continue

        if t == "spacing":
            if end - start >= silence_threshold:
                spans.append({
                    "start": start, "end": end, "kind": "silence",
                    "label": f"silêncio ({end - start:.1f}s)",
                })
        elif t == "word":
            text = (w.get("text") or "").strip().lower().strip(".,!?;:")
            if text in FILLER_WORDS:
                spans.append({
                    "start": start, "end": end, "kind": "filler",
                    "label": f"“{(w.get('text') or '').strip()}”",
                })

    spans.sort(key=lambda s: s["start"])
    return spans


def spans_to_keep_ranges(
    clip_in: float,
    clip_out: float,
    spans: list[dict],
    pad: float = 0.05,
    min_fragment: float = 0.15,
) -> list[tuple[float, float]]:
    """Subtract `spans` (already relevant to this clip) from [clip_in, clip_out].

    `pad` shrinks each removed span slightly so the cut lands just inside
    it rather than clipping the tail/head of adjacent speech. Fragments
    shorter than `min_fragment` after subtraction are dropped — not worth
    a cut. Returns the surviving sub-ranges in order.
    """
    shrunk: list[tuple[float, float]] = []
    for s in spans:
        a = max(clip_in, s["start"] + pad)
        b = min(clip_out, s["end"] - pad)
        if b > a:
            shrunk.append((a, b))
    shrunk.sort()

    merged: list[list[float]] = []
    for a, b in shrunk:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    keep: list[tuple[float, float]] = []
    cursor = clip_in
    for a, b in merged:
        if a > cursor:
            keep.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < clip_out:
        keep.append((cursor, clip_out))

    return [(a, b) for a, b in keep if b - a >= min_fragment]
