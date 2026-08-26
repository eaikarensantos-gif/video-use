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

from fastapi import Body, FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from jobs import Job, get_job, start_render_job, start_thread_job  # noqa: E402
from mediainfo import generate_thumbnail, generate_waveform_peaks, probe_media  # noqa: E402
from project import AUDIO_EXTS, VIDEO_EXTS, Project  # noqa: E402


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
        return {"ok": True, "videos_dir": str(project.videos_dir)}

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
            result.append({
                "name": name,
                "filename": p.name,
                **info,
                "thumbnail_url": f"/api/media/{name}/thumbnail.jpg",
                "stream_url": f"/media/source/{p.name}",
                "transcribed": (project.edit_dir / "transcripts" / f"{name}.json").exists(),
            })
        return result

    @app.post("/api/media/upload")
    async def upload_media(file: UploadFile = File(...)):
        # .name strips any directory components the browser might send —
        # never trust a client-supplied path.
        safe_name = Path(file.filename or "upload").name
        ext = Path(safe_name).suffix.lower()
        if ext not in VIDEO_EXTS and ext not in AUDIO_EXTS:
            allowed = ", ".join(sorted(VIDEO_EXTS | AUDIO_EXTS))
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

        return {"name": dest.stem, "filename": dest.name, "kind": "video" if ext in VIDEO_EXTS else "audio"}

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
        if not STICKERS_DIR.exists():
            return []
        return [
            {"name": p.stem, "url": f"/static/stickers/{p.name}"}
            for p in sorted(STICKERS_DIR.glob("*.png"))
        ]

    # ---- Export ------------------------------------------------------------

    @app.post("/api/export")
    def export(mode: str = Body("preview", embed=True), build_subtitles: bool = Body(True, embed=True)):
        if mode not in ("preview", "final"):
            raise HTTPException(400, "mode must be 'preview' or 'final'")
        timeline = project.load_timeline()
        project.save_timeline(timeline)  # ensure edl.json reflects latest edits
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
