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

# helpers/ uses same-directory imports (`from grade import ...`); make both
# it and this backend dir importable.
for p in (str(HELPERS_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import Body, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from jobs import get_job, start_render_job  # noqa: E402
from mediainfo import generate_thumbnail, generate_waveform_peaks, probe_media  # noqa: E402
from project import Project  # noqa: E402


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
            })
        return result

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
