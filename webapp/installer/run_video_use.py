"""PyInstaller entry point for the installed video-use app.

Replaces the previous pythonw.exe + Video-Use.vbs pair with a single
process: starts the FastAPI/uvicorn backend on a background thread,
waits for it to actually answer, opens it in a dedicated Edge "app mode"
window (falls back to the default browser + a small dialog if Edge isn't
found), and exits cleanly — server included — the moment that window
closes. No orphan background process left behind.

Bundled layout (see video_use.spec) mirrors the source repo exactly, so
webapp/backend/main.py's own relative-path logic (REPO_ROOT, HELPERS_DIR,
FRONTEND_DIST, STICKERS_DIR — all computed from `Path(__file__)`) works
completely unmodified whether running from source or frozen:

    <bundle_root>/
        helpers/*.py
        webapp/backend/*.py
        webapp/frontend/dist/...
        static/stickers/*.png
        ffmpeg/ffmpeg.exe, ffprobe.exe

main.py and everything under helpers/ are bundled as loose data files
(not analyzed/frozen modules) specifically so `Path(__file__)` keeps
resolving to a real path on disk — third-party deps (fastapi, uvicorn,
anthropic, requests, numpy, multipart) are imported here first, at the
top level, so PyInstaller's analyzer bundles them properly and they're
already in sys.modules by the time main.py imports them itself.
"""

from __future__ import annotations

import ctypes
import importlib
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Force-import so PyInstaller's analyzer bundles these and their hidden
# deps properly (main.py imports them too, but by then they're cached).
import fastapi  # noqa: F401
import multipart  # noqa: F401  (python-multipart's actual import name)
import numpy  # noqa: F401
import requests  # noqa: F401
import uvicorn
import anthropic  # noqa: F401

HOST = "127.0.0.1"
PORT = 8756


def bundle_root() -> Path:
    # Always set when frozen (onedir or onefile alike); falls back to this
    # file's own parent's parent's parent for `python run_video_use.py`
    # during local testing, matching the source tree layout.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def load_create_app(root: Path):
    backend_dir = root / "webapp" / "backend"
    helpers_dir = root / "helpers"
    for p in (str(helpers_dir), str(backend_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)
    main_mod = importlib.import_module("main")
    return main_mod.create_app


def put_ffmpeg_on_path(root: Path) -> None:
    ffmpeg_dir = root / "ffmpeg"
    if ffmpeg_dir.exists():
        os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")


def wait_for_health(url: str, timeout_s: float = 60.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def find_edge() -> str | None:
    for env_var in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_var)
        if not base:
            continue
        candidate = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if candidate.exists():
            return str(candidate)
    return None


def message_box(text: str, title: str = "video-use") -> None:
    MB_OK = 0x0
    MB_ICONINFORMATION = 0x40
    ctypes.windll.user32.MessageBoxW(None, text, title, MB_OK | MB_ICONINFORMATION)


def crash_log_path() -> Path:
    # sys.executable is the real video-use.exe path when frozen (its
    # install dir, under %LOCALAPPDATA%, is always user-writable) — this
    # is the only place a windowed (console=False) build can surface an
    # exception, since stdout/stderr go nowhere for it.
    exe_dir = Path(sys.executable).resolve().parent
    return exe_dir / "video-use-crash.log"


def _run_server(server: "uvicorn.Server") -> None:
    try:
        server.run()
    except Exception:
        import traceback
        crash_log_path().write_text("server thread crashed:\n" + traceback.format_exc())


def main() -> None:
    root = bundle_root()
    put_ffmpeg_on_path(root)
    create_app = load_create_app(root)

    videos_dir = Path.home() / "Videos" / "video-use"
    videos_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(videos_dir)
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    thread.start()

    url = f"http://{HOST}:{PORT}"
    if not wait_for_health(url, timeout_s=60.0):
        message_box(
            "O video-use esta demorando mais que o esperado pra iniciar.\n"
            f"Tente abrir manualmente no navegador: {url}",
        )
        return

    if os.environ.get("VIDEO_USE_SMOKETEST"):
        # CI-only escape hatch (see build-windows-installer.yml): a headless
        # runner has no interactive desktop session, so launching a real
        # Edge window here isn't meaningful — the thing actually worth
        # verifying in CI is that the frozen bundle starts the server at
        # all, which the health check above already confirmed. Block
        # forever instead of returning — the server thread is a daemon,
        # so returning here would exit the whole process (and close the
        # port) before the CI step gets a chance to poll it externally;
        # the CI step kills this process once it's done checking.
        print(f"VIDEO_USE_SMOKETEST: server healthy at {url}")
        threading.Event().wait()
        return

    edge = find_edge()
    if edge:
        # A dedicated --user-data-dir forces a genuinely separate Edge
        # process instead of handing off to any Edge window the user
        # already has open — without this, Popen.wait() below could
        # return the instant that handoff happens, long before the user
        # actually closes the video-use window, shutting the server down
        # under them.
        profile_dir = Path(tempfile.gettempdir()) / "video-use-edge-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([
            edge,
            f"--app={url}",
            "--window-size=1440,900",
            f"--user-data-dir={profile_dir}",
        ])
        proc.wait()
    else:
        os.startfile(url)  # noqa: S606 — Windows-only entry point
        message_box(
            "O video-use esta rodando em segundo plano.\n"
            "Feche esta caixa para encerrar o programa."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        crash_log_path().write_text("main() crashed:\n" + traceback.format_exc())
        raise
