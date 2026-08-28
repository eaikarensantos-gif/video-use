"""Export an `edl.json` (this project's cut list) as a CMX3600 Edit Decision
List — a plain-text format DaVinci Resolve, Premiere Pro, and Final Cut Pro
have all imported for decades, so it's the safest way to hand a cut off to
a real NLE without needing to guess at any single app's proprietary project
format.

Scope is deliberately narrow: only clip order and exact source in/out points
carry over (cuts only). Grades, transitions, text/overlays, Ken Burns, speed
changes, and music do NOT transfer — the target NLE has its own, better tools
for all of that, and baking approximations into the EDL would silently lose
fidelity. Anywhere the EDL would otherwise lie about that, we emit a
`* NOTE:` comment instead so the editor knows to redo it by hand in the NLE.

Usage:
    python helpers/export_edl.py <edl.json> -o export.edl
    python helpers/export_edl.py <edl.json> -o export.edl --fps 24 --title "My Project"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# CMX3600 convention: the record (output) timeline starts an hour in, so
# 00:00:00:00 is never seen as a record timecode (some older decks/NLEs treat
# it as "not set").
RECORD_START_SECONDS = 3600.0


def seconds_to_timecode(seconds: float, fps: float) -> str:
    """Non-drop-frame HH:MM:SS:FF. Safe here because the render pipeline
    always outputs at a fixed integer-ish fps (24 by default)."""
    seconds = max(0.0, seconds)
    total_frames = round(seconds * fps)
    frames = int(total_frames % round(fps))
    total_seconds = int(total_frames // round(fps))
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d}:{frames:02d}"


def sanitize_reel_name(source: str) -> str:
    """CMX3600 reel/tape names are traditionally <=8 uppercase alphanumeric
    chars. We also emit a `* FROM CLIP NAME:` comment with the full filename
    so NLEs that support it can auto-relink by name regardless."""
    stem = Path(source).stem
    cleaned = re.sub(r"[^A-Za-z0-9]", "", stem).upper()
    return cleaned[:8] if cleaned else "REEL"


def _describe_dropped_features(entry: dict) -> list[str]:
    notes = []
    if entry.get("grade") and entry["grade"] != "none":
        notes.append(f"grade '{entry['grade']}' not carried over — reapply in the NLE")
    if entry.get("speed") and float(entry["speed"]) != 1.0:
        notes.append(f"speed {entry['speed']}x not carried over — this event uses source in/out at 1x")
    if entry.get("zoom"):
        notes.append("Ken Burns zoom/pan not carried over")
    if entry.get("transform"):
        notes.append("transform (scale/position/rotation) not carried over")
    return notes


def build_cmx_edl(edl: dict, fps: float = 24.0, title: str = "video-use export") -> str:
    ranges = edl.get("ranges", [])
    transitions = edl.get("transitions") or []
    sources = edl.get("sources", {})

    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]

    record_cursor = RECORD_START_SECONDS
    for i, entry in enumerate(ranges):
        event_num = f"{i + 1:03d}"
        source = entry["source"]
        # `source` is the media's short name (no extension); resolve it to
        # the real filename via `sources` so `* FROM CLIP NAME:` matches
        # what's actually on disk (needed for NLE auto-relink by name).
        clip_filename = Path(sources[source]).name if source in sources else source
        reel = sanitize_reel_name(clip_filename)
        src_in = float(entry["start"])
        src_out = float(entry["end"])
        duration = max(0.0, src_out - src_in)

        rec_in = record_cursor
        rec_out = record_cursor + duration

        trans = transitions[i - 1] if 0 < i <= len(transitions) else None
        trans_type = (trans or {}).get("type", "cut")
        if trans_type in (None, "cut"):
            trans_code = "C"
        elif trans_type == "dissolve":
            dur_frames = round(float((trans or {}).get("duration", 0.4)) * fps)
            trans_code = f"D    {max(1, dur_frames):03d}"
        else:
            # Wipes/other named transitions: CMX wipe codes are numeric and
            # app-specific, so we fall back to a plain cut and flag it —
            # safer than emitting a wipe code the target app won't recognize.
            trans_code = "C"

        lines.append(
            f"{event_num}  {reel:<8} V     {trans_code:<5} "
            f"{seconds_to_timecode(src_in, fps)} {seconds_to_timecode(src_out, fps)} "
            f"{seconds_to_timecode(rec_in, fps)} {seconds_to_timecode(rec_out, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {clip_filename}")
        if trans_type not in (None, "cut", "dissolve"):
            lines.append(f"* NOTE: transition '{trans_type}' not supported by EDL — recreate manually")
        for note in _describe_dropped_features(entry):
            lines.append(f"* NOTE: {note}")
        lines.append("")

        record_cursor = rec_out

    if not ranges:
        lines.append("* NOTE: timeline is empty — nothing to export")

    if edl.get("overlays"):
        lines.append(f"* NOTE: {len(edl['overlays'])} text/sticker overlay(s) not carried over — video track only")
    if edl.get("audio_tracks"):
        lines.append(f"* NOTE: {len(edl['audio_tracks'])} music/audio clip(s) not carried over — video track only")
    if edl.get("subtitles"):
        lines.append("* NOTE: subtitles not carried over — video track only")

    unresolved_sources = {r["source"] for r in ranges if r["source"] not in sources}
    if unresolved_sources:
        lines.append(f"* NOTE: source path unknown for: {', '.join(sorted(unresolved_sources))}")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl", type=Path, help="path to edl.json")
    ap.add_argument("-o", "--output", type=Path, default=Path("export.edl"))
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--title", default="video-use export")
    args = ap.parse_args()

    edl = json.loads(args.edl.read_text())
    text = build_cmx_edl(edl, fps=args.fps, title=args.title)
    args.output.write_text(text)
    print(f"wrote {args.output} ({len(edl.get('ranges', []))} event(s))")


if __name__ == "__main__":
    main()
