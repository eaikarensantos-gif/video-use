"""video-use editor backend.

Serves the visual editor (React build) and a small REST API on top of the
existing video-use skill: the same `<videos_dir>/edit/` directory, the same
`edl.json`, the same `helpers/render.py` pipeline. The UI is a second way
to drive the same project the Claude Code chat flow already produces.

Run:
    python webapp/backend/main.py --videos-dir /path/to/footage [--port 8756]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent.parent
HELPERS_DIR = REPO_ROOT / "helpers"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
STICKERS_DIR = REPO_ROOT / "static" / "stickers"

# helpers/ uses same-directory imports (`from grade import ...`); make both
# it and this backend dir importable.
for p in (str(HELPERS_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import Body, FastAPI, File, Header, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from jobs import Job, get_job, start_render_job, start_thread_job  # noqa: E402
from mediainfo import (  # noqa: E402
    WEB_SAFE_VIDEO_CODECS,
    generate_preview_proxy,
    generate_thumbnail,
    generate_waveform_peaks,
    probe_media,
)
from project import AUDIO_EXTS, IMAGE_EXTS, VIDEO_EXTS, Project  # noqa: E402
from version import APP_VERSION  # noqa: E402


def create_app(videos_dir: Path) -> FastAPI:
    project = Project(videos_dir)

    app = FastAPI(title="video-use editor")
    # Local single-user tool — no auth, no untrusted origins to worry about.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"ok": True, "videos_dir": str(project.videos_dir), "version": APP_VERSION}

    # ---- Desktop application updates ----------------------------------

    @app.get("/api/update/check")
    def update_check():
        from updater import check_for_update

        return check_for_update()

    @app.post("/api/update/download")
    def update_download(payload: dict = Body(...), x_video_use_update_intent: str = Header("")):
        from updater import download_update

        if x_video_use_update_intent != "confirmed":
            raise HTTPException(403, "confirmacao de atualizacao ausente")

        download_url = str(payload.get("download_url", ""))
        expected_digest = payload.get("digest")

        def work(job: Job) -> None:
            last_percent = -1

            def progress(downloaded: int, total: int, percent: int) -> None:
                nonlocal last_percent
                job.result = {"downloaded": downloaded, "total": total, "percent": percent}
                if percent != last_percent and (percent % 5 == 0 or percent == 100):
                    job.log.append(f"download: {percent}%")
                    last_percent = percent

            path = download_update(download_url, expected_digest, progress)
            job.result = {**(job.result or {}), "ready": True, "path": path.name}

        return {"job_id": start_thread_job(work)}

    @app.post("/api/update/install")
    def update_install(x_video_use_update_intent: str = Header("")):
        from updater import install_and_restart

        if x_video_use_update_intent != "confirmed":
            raise HTTPException(403, "confirmacao de atualizacao ausente")

        try:
            install_and_restart()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True, "message": "O app sera fechado para concluir a atualizacao."}

    # ---- Media bin -----------------------------------------------------

    @app.get("/api/media")
    def list_media():
        result = []
        for p in project.list_source_files():
            name = p.stem
            try:
                info = probe_media(p)
            except Exception:
                info = {}
            vcodec = info.get("vcodec")
            web_safe = vcodec is None or vcodec in WEB_SAFE_VIDEO_CODECS
            result.append({
                "name": name,
                "filename": p.name,
                **info,
                "thumbnail_url": f"/api/media/{name}/thumbnail.jpg",
                # HEVC/h265 and other codecs browsers can't decode play
                # audio-only (black frame) via the raw file — route those
                # through a lazily-transcoded h264 proxy instead. Doesn't
                # affect export: render.py always re-encodes from the
                # original source regardless of this.
                "stream_url": f"/media/source/{p.name}" if web_safe else f"/api/media/{name}/proxy.mp4",
                "transcribed": (project.edit_dir / "transcripts" / f"{name}.json").exists(),
            })
        return result

    @app.get("/api/media/{name}/proxy.mp4")
    def media_proxy(name: str):
        src = project.find_source(name)
        if not src:
            raise HTTPException(404, f"unknown media '{name}'")
        cache = project.edit_dir / "proxies" / f"{name}.mp4"
        if not cache.exists():
            try:
                generate_preview_proxy(src, cache)
            except Exception as exc:
                raise HTTPException(500, f"preview conversion failed: {exc}") from exc
        return FileResponse(cache, media_type="video/mp4")

    @app.post("/api/media/upload")
    async def upload_media(file: UploadFile = File(...)):
        # .name strips any directory components the browser might send —
        # never trust a client-supplied path.
        safe_name = Path(file.filename or "upload").name
        ext = Path(safe_name).suffix.lower()
        if ext not in VIDEO_EXTS and ext not in AUDIO_EXTS and ext not in IMAGE_EXTS:
            allowed = ", ".join(sorted(VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS))
            raise HTTPException(400, f"unsupported file type '{ext}'. Allowed: {allowed}")

        dest = project.videos_dir / safe_name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            i = 1
            while dest.exists():
                dest = project.videos_dir / f"{stem}_{i}{suffix}"
                i += 1

        project.videos_dir.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)

        kind = "video" if ext in VIDEO_EXTS else "audio" if ext in AUDIO_EXTS else "image"
        return {"name": dest.stem, "filename": dest.name, "kind": kind}

    @app.delete("/api/media/{name}")
    def delete_media(name: str):
        src = project.find_source(name)
        if not src:
            raise HTTPException(404, f"unknown media '{name}'")
        trashed_path = project.trash_file(src)

        for thumb in (project.edit_dir / "thumbnails").glob(f"{name}_*.jpg"):
            thumb.unlink(missing_ok=True)
        (project.edit_dir / "waveforms" / f"{name}.json").unlink(missing_ok=True)
        (project.edit_dir / "transcripts" / f"{name}.json").unlink(missing_ok=True)
        (project.edit_dir / "proxies" / f"{name}.mp4").unlink(missing_ok=True)

        timeline = project.load_timeline()
        timeline.get("sources", {}).pop(name, None)
        removed_clips = 0
        for track in timeline.get("tracks", []):
            if track.get("type") != "video":
                continue
            before = len(track["clips"])
            track["clips"] = [c for c in track["clips"] if c.get("source") != name]
            removed_clips += before - len(track["clips"])
        project.save_timeline(timeline)

        return {"deleted": name, "removed_clips": removed_clips, "recoverable_at": str(trashed_path)}

    @app.get("/api/media/{name}/thumbnail.jpg")
    def media_thumbnail(name: str, t: float = 0.0):
        src = project.find_source(name)
        if not src:
            raise HTTPException(404, f"unknown source '{name}'")
        thumb_path = project.edit_dir / "thumbnails" / f"{name}_{int(t * 1000)}.jpg"
        if not thumb_path.exists():
            try:
                generate_thumbnail(src, thumb_path, at=t)
            except Exception as exc:
                raise HTTPException(500, f"thumbnail generation failed: {exc}") from exc
        return FileResponse(thumb_path, media_type="image/jpeg")

    @app.get("/api/media/{name}/waveform")
    def media_waveform(name: str):
        src = project.find_source(name)
        if not src:
            raise HTTPException(404, f"unknown source '{name}'")
        cache = project.edit_dir / "waveforms" / f"{name}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            peaks = generate_waveform_peaks(src)
        except Exception as exc:
            raise HTTPException(500, f"waveform generation failed: {exc}") from exc
        cache.write_text(json.dumps(peaks))
        return peaks

    # ---- Transcription (ElevenLabs Scribe — powers auto-captions + AI edit) --

    @app.post("/api/media/{name}/transcribe")
    def transcribe_media(name: str, language: str | None = Body(None, embed=True)):
        src = project.find_source(name)
        if not src:
            raise HTTPException(404, f"unknown source '{name}'")

        def work(job: Job) -> None:
            from transcribe import load_api_key, transcribe_one

            api_key = load_api_key()
            job.log.append(f"transcribing {src.name}…")
            path = transcribe_one(src, project.edit_dir, api_key, language=language, verbose=False)
            job.log.append(f"done: {path.name}")
            job.result = {"name": name, "path": str(path)}

        job_id = start_thread_job(work)
        return {"job_id": job_id}

    @app.post("/api/media/transcribe-all")
    def transcribe_all_media():
        def work(job: Job) -> None:
            from transcribe import load_api_key, transcribe_one

            api_key = load_api_key()
            sources = project.list_source_files()
            done = 0
            for src in sources:
                job.log.append(f"transcribing {src.name}…")
                try:
                    transcribe_one(src, project.edit_dir, api_key, verbose=False)
                    job.log.append(f"  done: {src.stem}")
                    done += 1
                except Exception as exc:  # noqa: BLE001 — keep going, report per-file
                    job.log.append(f"  failed: {src.stem}: {exc}")
            job.result = {"transcribed": done, "total": len(sources)}

        job_id = start_thread_job(work)
        return {"job_id": job_id}

    @app.get("/api/media/{name}/transcript")
    def get_transcript(name: str):
        if not project.find_source(name):
            raise HTTPException(404, f"unknown source '{name}'")
        tr_path = project.edit_dir / "transcripts" / f"{name}.json"
        if not tr_path.exists():
            raise HTTPException(404, f"no transcript for '{name}' — transcribe it first")
        try:
            payload = json.loads(tr_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(500, f"invalid transcript for '{name}': {exc}") from exc
        words = []
        for index, word in enumerate(payload.get("words", [])):
            if word.get("type", "word") != "word":
                continue
            start, end = word.get("start"), word.get("end")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
                continue
            words.append({
                "id": f"w{index}", "text": str(word.get("text", "")).strip(),
                "start": float(start), "end": float(end), "speaker": word.get("speaker_id"),
            })
        return {"source": name, "language": payload.get("language_code"), "text": payload.get("text", ""), "words": words}

    # ---- Cleanup (silence/filler-word detection from the transcript) ----

    @app.post("/api/media/{name}/detect-cleanup")
    def detect_cleanup(
        name: str,
        clip_in: float = Body(..., embed=True),
        clip_out: float = Body(..., embed=True),
        silence_threshold: float = Body(0.6, embed=True),
    ):
        from cleanup import detect_cleanup_spans, spans_to_keep_ranges

        tr_path = project.edit_dir / "transcripts" / f"{name}.json"
        if not tr_path.exists():
            raise HTTPException(404, f"no transcript for '{name}' — transcribe it first")
        spans = detect_cleanup_spans(tr_path, silence_threshold=silence_threshold)
        in_range = [s for s in spans if s["start"] < clip_out and s["end"] > clip_in]
        keep = spans_to_keep_ranges(clip_in, clip_out, in_range)
        return {
            "spans": in_range,
            "keep_ranges": [{"in": a, "out": b} for a, b in keep],
        }

    # ---- AI auto-edit (real Anthropic API call, proposes cuts for review) --

    @app.post("/api/ai/auto-edit")
    def ai_auto_edit(brief: str = Body(..., embed=True), target_duration: float | None = Body(None, embed=True)):
        def work(job: Job) -> None:
            from ai_editor import run_auto_edit

            ranges = run_auto_edit(project.edit_dir, brief, target_duration, log=job.log.append)
            job.result = {"ranges": ranges}

        job_id = start_thread_job(work)
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return {"status": job.status, "log": job.log[-300:], "error": job.error, "result": job.result}

    # ---- Music/ambience (background audio track) -------------------------

    @app.get("/api/audio")
    def list_audio():
        result = []
        for p in project.list_audio_files():
            name = p.stem
            try:
                info = probe_media(p)
            except Exception:
                info = {}
            result.append({
                "name": name,
                "filename": p.name,
                **info,
                "stream_url": f"/media/source/{p.name}",
            })
        return result

    @app.delete("/api/audio/{name}")
    def delete_audio(name: str):
        src = project.find_audio(name)
        if not src:
            raise HTTPException(404, f"unknown audio file '{name}'")
        stream_suffix = f"/media/source/{src.name}"
        trashed_path = project.trash_file(src)
        (project.edit_dir / "waveforms" / f"audio_{name}.json").unlink(missing_ok=True)

        timeline = project.load_timeline()
        removed_clips = 0
        for track in timeline.get("tracks", []):
            if track.get("type") != "audio":
                continue
            before = len(track["clips"])
            track["clips"] = [c for c in track["clips"] if c.get("file") != stream_suffix]
            removed_clips += before - len(track["clips"])
        project.save_timeline(timeline)

        return {"deleted": name, "removed_clips": removed_clips, "recoverable_at": str(trashed_path)}

    @app.get("/api/audio/{name}/waveform")
    def audio_waveform(name: str):
        src = project.find_audio(name)
        if not src:
            raise HTTPException(404, f"unknown audio file '{name}'")
        cache = project.edit_dir / "waveforms" / f"audio_{name}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            peaks = generate_waveform_peaks(src)
        except Exception as exc:
            raise HTTPException(500, f"waveform generation failed: {exc}") from exc
        cache.write_text(json.dumps(peaks))
        return peaks

    # ---- Timeline (multi-track, bridges to edl.json) --------------------

    @app.get("/api/timeline")
    def get_timeline():
        return project.load_timeline()

    @app.put("/api/timeline")
    def put_timeline(timeline: dict = Body(...)):
        return project.save_timeline(timeline)

    # ---- Presets ---------------------------------------------------------

    @app.get("/api/presets/grades")
    def presets_grades():
        from grade import PRESETS

        descriptions = {
            "none": "No grade — straight copy",
            "subtle": "Barely perceptible cleanup, no color shift",
            "neutral_punch": "Contrast + gentle S-curve, no hue shift",
            "warm_cinematic": "Teal/orange split, desaturated, cinematic",
            "auto": "Analyze the clip and auto-correct exposure/contrast",
        }
        names = [*PRESETS.keys(), "auto"]
        return [
            {"id": n, "label": n.replace("_", " ").title(), "description": descriptions.get(n, "")}
            for n in names
        ]

    @app.get("/api/presets/transitions")
    def presets_transitions():
        from render import XFADE_TRANSITIONS

        return ["cut", *sorted(XFADE_TRANSITIONS)]

    @app.get("/api/stickers")
    def list_stickers():
        builtins = [
            {"name": p.stem, "url": f"/static/stickers/{p.name}"}
            for p in sorted(STICKERS_DIR.glob("*.png"))
        ] if STICKERS_DIR.exists() else []
        imported = [{"name": p.stem, "url": f"/media/source/{p.name}"} for p in project.list_image_files()]
        return imported + builtins

    # ---- Export ------------------------------------------------------------

    def _ensure_translated_transcripts(edl: dict, language: str) -> None:
        """Translate every used source's transcript into `language`
        (Claude, cached to disk) before the render job starts — kept out
        of helpers/render.py since that script has no Anthropic
        dependency. Raises RuntimeError (surfaced as a 400) if there's no
        API key; sources with no transcript at all are silently skipped,
        same as they are for subtitles in the original language."""
        from ai_editor import load_anthropic_key
        from translate_captions import translate_transcript

        api_key = load_anthropic_key()
        transcripts_dir = project.edit_dir / "transcripts"
        used_sources = {r["source"] for r in edl.get("ranges", [])}
        for name in used_sources:
            original = transcripts_dir / f"{name}.json"
            if not original.exists():
                continue
            cache = transcripts_dir / f"{name}.{language}.json"
            translate_transcript(original, language, api_key, cache)

    @app.post("/api/export")
    def export(
        mode: str = Body("preview", embed=True),
        build_subtitles: bool = Body(True, embed=True),
        subtitle_style: dict | None = Body(None, embed=True),
        subtitle_language: str | None = Body(None, embed=True),
    ):
        if mode not in ("preview", "final"):
            raise HTTPException(400, "mode must be 'preview' or 'final'")
        timeline = project.load_timeline()
        project.save_timeline(timeline)  # ensure edl.json reflects latest edits

        # subtitle_style/subtitle_language are export-request settings, not
        # timeline state — written straight into this render's edl.json
        # rather than round-tripped through bridge.py.
        if build_subtitles and (subtitle_style or subtitle_language):
            edl = json.loads(project.edl_path.read_text())
            if subtitle_style:
                edl["subtitle_style"] = subtitle_style
            if subtitle_language and subtitle_language != "original":
                edl["subtitle_language"] = subtitle_language
                try:
                    _ensure_translated_transcripts(edl, subtitle_language)
                except RuntimeError as exc:
                    raise HTTPException(400, str(exc)) from exc
            project.edl_path.write_text(json.dumps(edl, indent=2))

        out_name = "preview.mp4" if mode == "preview" else "final.mp4"
        output_path = project.edit_dir / out_name
        job_id = start_render_job(
            edl_path=project.edl_path,
            output_path=output_path,
            helpers_dir=HELPERS_DIR,
            preview=(mode == "preview"),
            build_subtitles=build_subtitles,
            no_loudnorm=(mode == "preview"),
        )
        return {"job_id": job_id}

    @app.get("/api/export/{job_id}")
    def export_status(job_id: str):
        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        result = {"status": job.status, "log": job.log[-300:], "error": job.error}
        if job.output_path:
            rel = Path(job.output_path).relative_to(project.edit_dir)
            result["output_url"] = f"/media/edit/{rel.as_posix()}"
        return result

    @app.get("/api/export-edl")
    def export_edl():
        """CMX3600 EDL for DaVinci Resolve / Premiere Pro / Final Cut Pro —
        cuts only (source in/out + order). Grades, transitions, text/overlays,
        Ken Burns, speed, and music don't survive the format; see the
        `* NOTE:` comments the exporter writes for anything dropped."""
        from bridge import timeline_to_edl
        from export_edl import build_cmx_edl

        timeline = project.load_timeline()
        project.save_timeline(timeline)  # ensure edl.json reflects latest edits
        edl = timeline_to_edl(timeline, project.videos_dir)
        fps = timeline.get("canvas", {}).get("fps", 24)
        text = build_cmx_edl(edl, fps=fps, title=project.videos_dir.name)
        out_path = project.edit_dir / "export.edl"
        out_path.write_text(text)
        return FileResponse(out_path, media_type="text/plain", filename="video-use-export.edl")

    # ---- Static files: raw sources, edit dir outputs, frontend build -----

    if project.videos_dir.exists():
        app.mount("/media/source", StaticFiles(directory=str(project.videos_dir)), name="source")
    app.mount("/media/edit", StaticFiles(directory=str(project.edit_dir)), name="edit")
    if STICKERS_DIR.exists():
        app.mount("/static/stickers", StaticFiles(directory=str(STICKERS_DIR)), name="stickers")
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="video-use visual editor backend")
    ap.add_argument("--videos-dir", type=Path, default=Path.cwd(), help="Folder with raw footage")
    ap.add_argument("--port", type=int, default=8756)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    import uvicorn

    app = create_app(args.videos_dir)
    print(f"video-use editor — videos_dir={args.videos_dir.resolve()}")
    print(f"open http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
