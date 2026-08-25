"""Convert between the visual editor's `timeline.json` (multi-track, per-clip
grade/transitions/text) and the renderer's `edl.json` (the format the video-use
skill's chat flow and helpers/render.py already speak).

This is what lets the UI and Claude Code's conversational flow "convive"
(coexist) on the same project: whichever one last saved, the other reads
compatible state.
"""

from __future__ import annotations


def timeline_to_edl(timeline: dict) -> dict:
    sources = {name: info["path"] for name, info in timeline.get("sources", {}).items()}

    video_track = next(
        (t for t in timeline.get("tracks", []) if t.get("type") == "video"), None
    )
    ranges: list[dict] = []
    transitions: list[dict] = []
    if video_track:
        clips = video_track.get("clips", [])
        for i, c in enumerate(clips):
            entry: dict = {
                "source": c["source"],
                "start": float(c["in"]),
                "end": float(c["out"]),
            }
            if c.get("grade"):
                entry["grade"] = c["grade"]
            if c.get("note"):
                entry["beat"] = c["note"]
            ranges.append(entry)
            if i < len(clips) - 1:
                transitions.append(c.get("transitionOut") or {"type": "cut"})

    overlays: list[dict] = []
    for track in timeline.get("tracks", []):
        ttype = track.get("type")
        if ttype == "overlay":
            for c in track.get("clips", []):
                overlays.append({
                    "file": c["file"],
                    "start_in_output": float(c["start"]),
                    "duration": float(c["duration"]),
                })
        elif ttype == "text":
            for c in track.get("clips", []):
                overlays.append({
                    "type": "text",
                    "text": c.get("text", ""),
                    "start_in_output": float(c["start"]),
                    "duration": float(c["duration"]),
                    "style": c.get("style", {}),
                })

    subs = timeline.get("subtitles") or {}

    return {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "transitions": transitions,
        "grade": "none",  # per-range grade always set explicitly by the UI
        "overlays": overlays,
        "subtitles": subs.get("path") if subs.get("enabled") and subs.get("path") else None,
    }


def edl_to_timeline(edl: dict, media_info: dict[str, dict]) -> dict:
    """Best-effort reverse conversion, for opening a project the chat flow
    (or a previous `render.py` run) already produced an `edl.json` for.
    """
    sources = {}
    for name, path in edl.get("sources", {}).items():
        info = media_info.get(name, {})
        sources[name] = {"path": path, **info}

    transitions = edl.get("transitions") or []
    clips = []
    for i, r in enumerate(edl.get("ranges", [])):
        clip = {
            "id": f"clip_{i}",
            "source": r["source"],
            "in": float(r["start"]),
            "out": float(r["end"]),
            "grade": r.get("grade") or edl.get("grade") or "none",
            "note": r.get("beat") or r.get("note") or "",
        }
        if i < len(transitions):
            clip["transitionOut"] = transitions[i]
        clips.append(clip)

    tracks = [{"id": "v1", "type": "video", "name": "Video", "clips": clips}]

    text_clips, overlay_clips = [], []
    for i, ov in enumerate(edl.get("overlays") or []):
        if ov.get("type") == "text":
            text_clips.append({
                "id": f"text_{i}",
                "start": float(ov["start_in_output"]),
                "duration": float(ov["duration"]),
                "text": ov.get("text", ""),
                "style": ov.get("style", {}),
            })
        else:
            overlay_clips.append({
                "id": f"ov_{i}",
                "start": float(ov["start_in_output"]),
                "duration": float(ov["duration"]),
                "file": ov["file"],
            })
    if text_clips:
        tracks.append({"id": "t1", "type": "text", "name": "Text", "clips": text_clips})
    if overlay_clips:
        tracks.append({"id": "ov1", "type": "overlay", "name": "Overlays", "clips": overlay_clips})

    subs_path = edl.get("subtitles")
    return {
        "version": 1,
        "canvas": {"width": 1920, "height": 1080, "fps": 24},
        "sources": sources,
        "tracks": tracks,
        "subtitles": {"enabled": bool(subs_path), "path": subs_path or ""},
    }


def empty_timeline() -> dict:
    return {
        "version": 1,
        "canvas": {"width": 1920, "height": 1080, "fps": 24},
        "sources": {},
        "tracks": [
            {"id": "v1", "type": "video", "name": "Video", "clips": []},
            {"id": "t1", "type": "text", "name": "Text", "clips": []},
            {"id": "ov1", "type": "overlay", "name": "Overlays", "clips": []},
        ],
        "subtitles": {"enabled": False, "path": ""},
    }
