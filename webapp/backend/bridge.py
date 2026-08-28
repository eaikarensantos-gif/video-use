"""Convert between the visual editor's `timeline.json` (multi-track, per-clip
grade/transitions/text) and the renderer's `edl.json` (the format the video-use
skill's chat flow and helpers/render.py already speak).

This is what lets the UI and Claude Code's conversational flow "convive"
(coexist) on the same project: whichever one last saved, the other reads
compatible state.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_STICKERS_DIR = _REPO_ROOT / "static" / "stickers"


def _resolve_overlay_file(file: str) -> str:
    """Stickers are served to the browser at `/static/stickers/<name>.png`;
    the renderer needs a real filesystem path. Everything else (animation
    clips the chat flow rendered into `edit/animations/...`) is already a
    path and passes through unchanged."""
    if file.startswith("/static/stickers/"):
        return str(_STICKERS_DIR / file.removeprefix("/static/stickers/"))
    return file


def _resolve_audio_file(file: str, videos_dir: Path | None) -> str:
    """Music files are served to the browser at `/media/source/<name>`;
    the renderer needs a real filesystem path."""
    if videos_dir and file.startswith("/media/source/"):
        return str(videos_dir / file.removeprefix("/media/source/"))
    return file


def _is_nondefault_transform(t: dict) -> bool:
    """Skip writing a transform block to the EDL when every field is still
    at its identity default — keeps existing chat-authored EDLs untouched
    for clips the user never opened the Transform panel on."""
    return bool(
        (t.get("scale") not in (None, 1) and t.get("scale") != 1.0)
        or (t.get("x") not in (None, 0) and t.get("x") != 0.0)
        or (t.get("y") not in (None, 0) and t.get("y") != 0.0)
        or (t.get("rotation") not in (None, 0) and t.get("rotation") != 0.0)
        or (t.get("opacity") not in (None, 1) and t.get("opacity") != 1.0)
        or t.get("flip_h")
        or t.get("flip_v")
    )


def _audio_file_to_url(file: str, videos_dir: Path | None) -> str:
    """Reverse of `_resolve_audio_file`, for opening a chat-authored EDL."""
    if videos_dir:
        p = Path(file)
        if p.is_absolute() and p.parent == videos_dir:
            return f"/media/source/{p.name}"
    return file


def timeline_to_edl(timeline: dict, videos_dir: Path | None = None) -> dict:
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
            if c.get("speed") and c["speed"] != 1:
                entry["speed"] = float(c["speed"])
            if c.get("zoom") and c["zoom"].get("type") in ("in", "out"):
                entry["zoom"] = {"type": c["zoom"]["type"], "amount": float(c["zoom"].get("amount", 0.15))}
            if c.get("transform") and _is_nondefault_transform(c["transform"]):
                entry["transform"] = c["transform"]
            ranges.append(entry)
            if i < len(clips) - 1:
                transitions.append(c.get("transitionOut") or {"type": "cut"})

    overlays: list[dict] = []
    for track in timeline.get("tracks", []):
        ttype = track.get("type")
        if ttype == "overlay":
            for c in track.get("clips", []):
                if c.get("kind") == "sticker":
                    overlays.append({
                        "type": "sticker",
                        "file": _resolve_overlay_file(c["file"]),
                        "start_in_output": float(c["start"]),
                        "duration": float(c["duration"]),
                        "x": float(c.get("x", 0.5)),
                        "y": float(c.get("y", 0.5)),
                        "scale": float(c.get("scale", 0.3)),
                    })
                else:
                    overlays.append({
                        "file": _resolve_overlay_file(c["file"]),
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

    audio_tracks: list[dict] = []
    for track in timeline.get("tracks", []):
        if track.get("type") != "audio":
            continue
        for c in track.get("clips", []):
            audio_tracks.append({
                "file": _resolve_audio_file(c["file"], videos_dir),
                "start_in_output": float(c["start"]),
                "duration": float(c["duration"]),
                "trim_in": float(c.get("trimIn", 0.0)),
                "volume": float(c.get("volume", 1.0)),
                "fade_in": float(c.get("fadeIn", 0.0)),
                "fade_out": float(c.get("fadeOut", 0.0)),
            })

    subs = timeline.get("subtitles") or {}

    return {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "transitions": transitions,
        "grade": "none",  # per-range grade always set explicitly by the UI
        "overlays": overlays,
        "audio_tracks": audio_tracks,
        "subtitles": subs.get("path") if subs.get("enabled") and subs.get("path") else None,
        "canvas": timeline.get("canvas"),
    }


def edl_to_timeline(edl: dict, media_info: dict[str, dict], videos_dir: Path | None = None) -> dict:
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
            "speed": float(r.get("speed", 1.0)) or 1.0,
        }
        if r.get("zoom") and r["zoom"].get("type") in ("in", "out"):
            clip["zoom"] = {"type": r["zoom"]["type"], "amount": float(r["zoom"].get("amount", 0.15))}
        if r.get("transform"):
            clip["transform"] = r["transform"]
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
        elif ov.get("type") == "sticker":
            file = ov["file"]
            if file.startswith(str(_STICKERS_DIR)):
                file = "/static/stickers/" + Path(file).name
            overlay_clips.append({
                "id": f"ov_{i}",
                "kind": "sticker",
                "start": float(ov["start_in_output"]),
                "duration": float(ov["duration"]),
                "file": file,
                "x": float(ov.get("x", 0.5)),
                "y": float(ov.get("y", 0.5)),
                "scale": float(ov.get("scale", 0.3)),
            })
        else:
            overlay_clips.append({
                "id": f"ov_{i}",
                "kind": "video",
                "start": float(ov["start_in_output"]),
                "duration": float(ov["duration"]),
                "file": ov["file"],
            })
    audio_clips = []
    for i, a in enumerate(edl.get("audio_tracks") or []):
        audio_clips.append({
            "id": f"audio_{i}",
            "file": _audio_file_to_url(a["file"], videos_dir),
            "start": float(a["start_in_output"]),
            "duration": float(a["duration"]),
            "trimIn": float(a.get("trim_in", 0.0)),
            "volume": float(a.get("volume", 1.0)),
            "fadeIn": float(a.get("fade_in", 0.0)),
            "fadeOut": float(a.get("fade_out", 0.0)),
        })

    # Always include text/overlay/audio tracks (even empty) so "+ Text",
    # sticker drag-drop, and music drag-drop have somewhere to land on a
    # project that doesn't have any yet — matches empty_timeline()'s shape.
    tracks.append({"id": "t1", "type": "text", "name": "Text", "clips": text_clips})
    tracks.append({"id": "ov1", "type": "overlay", "name": "Overlays", "clips": overlay_clips})
    tracks.append({"id": "a1", "type": "audio", "name": "Audio", "clips": audio_clips})

    subs_path = edl.get("subtitles")
    # width/height stay null until the user explicitly picks an aspect
    # ratio (Toolbar → Aspect ratio) — with no canvas locked in, render.py
    # keeps scaling each segment to fit its own source orientation, same
    # as every project before this feature existed. Defaulting this to
    # 1920x1080 would silently crop portrait phone footage in every new
    # project to fill a landscape frame — exactly the kind of regression
    # this project can't afford another round of "meu video sumiu" over.
    canvas = edl.get("canvas") or {"width": None, "height": None, "fps": 24}
    return {
        "version": 1,
        "canvas": canvas,
        "sources": sources,
        "tracks": tracks,
        "subtitles": {"enabled": bool(subs_path), "path": subs_path or ""},
    }


def empty_timeline() -> dict:
    return {
        "version": 1,
        "canvas": {"width": None, "height": None, "fps": 24},
        "sources": {},
        "tracks": [
            {"id": "v1", "type": "video", "name": "Video", "clips": []},
            {"id": "t1", "type": "text", "name": "Text", "clips": []},
            {"id": "ov1", "type": "overlay", "name": "Overlays", "clips": []},
            {"id": "a1", "type": "audio", "name": "Audio", "clips": []},
        ],
        "subtitles": {"enabled": False, "path": ""},
    }
