# PyInstaller spec for the video-use Windows installer build.
# Run from webapp/installer/: pyinstaller video_use.spec
#
# Builds a onedir bundle (faster startup than onefile — no per-launch
# extraction of a large numpy/fastapi payload to a temp dir). The Inno
# Setup script (installer.iss) packages dist/video-use/ into a single
# setup.exe.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent.parent
INSTALLER_DIR = SPEC_DIR

# webapp/backend/main.py and its siblings are bundled as loose data files
# (see the Tree() calls below), specifically so their own Path(__file__)
# logic keeps working unmodified — but that also means PyInstaller's
# static analyzer never actually reads their source, so it can't see
# imports like `from fastapi.middleware.cors import CORSMiddleware` on
# its own (confirmed by a real CI failure: ModuleNotFoundError for
# exactly that submodule). Pull in every fastapi/starlette submodule
# unconditionally instead of hand-listing each one main.py happens to
# use today — cheap insurance against the next one.
hidden = collect_submodules("fastapi") + collect_submodules("starlette")
hidden += [
    # Starlette's multipart form parsing (needed for file upload) imports
    # this lazily, only when a multipart request actually arrives.
    "multipart",
]

a = Analysis(
    [str(SPEC_DIR / "run_video_use.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Never referenced by the webapp backend (see requirements-freeze.txt) —
        # excluding them keeps numba/librosa's build-heavy native extensions
        # (and matplotlib/manim) out even if something transitively suggests
        # them.
        "librosa",
        "numba",
        "matplotlib",
        "manim",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="video-use",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(REPO_ROOT / "Video-Use.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    Tree(str(REPO_ROOT / "helpers"), prefix="helpers"),
    Tree(str(REPO_ROOT / "webapp" / "backend"), prefix="webapp/backend"),
    Tree(str(REPO_ROOT / "webapp" / "frontend" / "dist"), prefix="webapp/frontend/dist"),
    Tree(str(REPO_ROOT / "static" / "stickers"), prefix="static/stickers"),
    Tree(str(INSTALLER_DIR / "ffmpeg"), prefix="ffmpeg"),
    strip=False,
    upx=False,
    name="video-use",
)
