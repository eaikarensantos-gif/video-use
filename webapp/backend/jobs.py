"""Background jobs — export (helpers/render.py as a subprocess) and
in-process work (transcription, AI auto-edit), both polled the same way
from the UI: a job id, a growing log, and a terminal status."""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    log: list[str] = field(default_factory=list)
    output_path: str | None = None
    error: str | None = None
    result: Any = None


JOBS: dict[str, Job] = {}
_lock = threading.Lock()


def start_thread_job(work: Callable[[Job], None]) -> str:
    """Run `work(job)` in a background thread. `work` should append progress
    strings to `job.log` and set `job.result` before returning; raising
    surfaces the exception message as `job.error` with status "error"."""
    job = Job(id=uuid.uuid4().hex[:12])
    with _lock:
        JOBS[job.id] = job

    def run() -> None:
        job.status = "running"
        try:
            work(job)
            if job.status == "running":
                job.status = "done"
        except SystemExit as exc:
            # helpers/*.py's load_api_key() reports missing keys via
            # sys.exit(msg) for the CLI — SystemExit is a BaseException, not
            # an Exception, so it needs its own handler here or it kills the
            # thread silently and leaves the job stuck at "running".
            job.status = "error"
            job.error = str(exc.code) if exc.code is not None else "exited"
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            job.status = "error"
            job.error = str(exc)

    threading.Thread(target=run, daemon=True).start()
    return job.id


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
