"""Background export jobs — runs helpers/render.py as a subprocess and
streams its stdout into an in-memory log so the UI can poll progress."""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    log: list[str] = field(default_factory=list)
    output_path: str | None = None
    error: str | None = None


JOBS: dict[str, Job] = {}
_lock = threading.Lock()


def start_render_job(
    edl_path: Path,
    output_path: Path,
    helpers_dir: Path,
    preview: bool,
    build_subtitles: bool,
    no_loudnorm: bool = False,
) -> str:
    job = Job(id=uuid.uuid4().hex[:12])
    with _lock:
        JOBS[job.id] = job

    def run() -> None:
        job.status = "running"
        cmd = [sys.executable, str(helpers_dir / "render.py"), str(edl_path), "-o", str(output_path)]
        if preview:
            cmd.append("--preview")
        if build_subtitles:
            cmd.append("--build-subtitles")
        if no_loudnorm:
            cmd.append("--no-loudnorm")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(helpers_dir),
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                job.log.append(line.rstrip("\n"))
                if len(job.log) > 2000:
                    del job.log[:-2000]
            proc.wait()
            if proc.returncode == 0:
                job.status = "done"
                job.output_path = str(output_path)
            else:
                job.status = "error"
                job.error = f"render.py exited with code {proc.returncode}"
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            job.status = "error"
            job.error = str(exc)

    threading.Thread(target=run, daemon=True).start()
    return job.id


def get_job(job_id: str) -> Job | None:
    return JOBS.get(job_id)
