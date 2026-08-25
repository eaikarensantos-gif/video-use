"""Project = a `videos_dir` (raw footage folder) + its `edit/` output dir.

Mirrors the directory layout the video-use skill already uses (see
SKILL.md "Directory layout"), so the web UI and the Claude Code chat
flow operate on the exact same files.
"""

from __future__ import annotations

import json
from pathlib import Path

from bridge import edl_to_timeline, empty_timeline
from mediainfo import probe_media

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


class Project:
    def __init__(self, videos_dir: Path):
        self.videos_dir = videos_dir.resolve()
        self.edit_dir = self.videos_dir / "edit"
        self.edit_dir.mkdir(parents=True, exist_ok=True)

    @property
    def timeline_path(self) -> Path:
        return self.edit_dir / "timeline.json"

    @property
    def edl_path(self) -> Path:
        return self.edit_dir / "edl.json"

    def list_source_files(self) -> list[Path]:
        if not self.videos_dir.exists():
            return []
        return sorted(
            p for p in self.videos_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        )

    def find_source(self, name: str) -> Path | None:
        for p in self.list_source_files():
            if p.stem == name:
                return p
        return None

    def load_timeline(self) -> dict:
        if self.timeline_path.exists():
            timeline = json.loads(self.timeline_path.read_text())
            # Pick up any sources dropped into the folder since the timeline
            # was last saved (chat flow or the user adding footage by hand).
            self._merge_new_sources(timeline)
            return timeline

        if self.edl_path.exists():
            edl = json.loads(self.edl_path.read_text())
            media = {}
            for name, path in edl.get("sources", {}).items():
                try:
                    media[name] = probe_media(Path(path))
                except Exception:
                    media[name] = {}
            timeline = edl_to_timeline(edl, media)
            self._merge_new_sources(timeline)
            return timeline

        timeline = empty_timeline()
        self._merge_new_sources(timeline)
        return timeline

    def _merge_new_sources(self, timeline: dict) -> None:
        known = timeline.setdefault("sources", {})
        for p in self.list_source_files():
            if p.stem in known:
                continue
            try:
                info = probe_media(p)
            except Exception:
                info = {}
            known[p.stem] = {"path": str(p), **info}

    def save_timeline(self, timeline: dict) -> dict:
        from bridge import timeline_to_edl

        self.timeline_path.write_text(json.dumps(timeline, indent=2))
        edl = timeline_to_edl(timeline)
        self.edl_path.write_text(json.dumps(edl, indent=2))
        return timeline
