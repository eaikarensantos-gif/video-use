"""Safe, opt-in updater backed by this project's GitHub Releases."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from version import APP_VERSION

RELEASE_API = "https://api.github.com/repos/eaikarensantos-gif/video-use/releases/latest"
ASSET_NAME = "video-use-setup.exe"
_downloaded_installer: Path | None = None


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lstrip("vV").split("-", 1)[0]
    try:
        return tuple(int(part) for part in clean.split("."))
    except ValueError:
        return (0,)


def check_for_update() -> dict:
    request = urllib.request.Request(
        RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"video-use/{APP_VERSION}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            release = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "current_version": APP_VERSION,
            "available": False,
            "error": f"Nao foi possivel verificar atualizacoes: {exc}",
        }

    latest = str(release.get("tag_name", "")).lstrip("vV")
    asset = next((item for item in release.get("assets", []) if item.get("name") == ASSET_NAME), None)
    available = bool(asset and _version_tuple(latest) > _version_tuple(APP_VERSION))
    return {
        "current_version": APP_VERSION,
        "latest_version": latest or APP_VERSION,
        "available": available,
        "release_name": release.get("name") or release.get("tag_name") or latest,
        "notes": release.get("body") or "",
        "published_at": release.get("published_at"),
        "download_url": asset.get("browser_download_url") if available else None,
        "size": asset.get("size") if available else None,
        "digest": asset.get("digest") if available else None,
    }


def download_update(download_url: str, expected_digest: str | None, progress) -> Path:
    global _downloaded_installer
    if not download_url.startswith("https://github.com/eaikarensantos-gif/video-use/releases/download/"):
        raise RuntimeError("endereco de atualizacao nao autorizado")

    target_dir = Path(tempfile.gettempdir()) / "video-use-updates"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / ASSET_NAME
    partial = target.with_suffix(".download")
    partial.unlink(missing_ok=True)

    request = urllib.request.Request(download_url, headers={"User-Agent": f"video-use/{APP_VERSION}"})
    with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as output:
        total = int(response.headers.get("Content-Length", "0"))
        downloaded = 0
        digest = hashlib.sha256()
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            percent = round(downloaded * 100 / total) if total else 0
            progress(downloaded, total, percent)

    actual_digest = digest.hexdigest()
    if expected_digest and expected_digest.startswith("sha256:"):
        expected = expected_digest.split(":", 1)[1].lower()
        if actual_digest.lower() != expected:
            partial.unlink(missing_ok=True)
            raise RuntimeError("a verificacao de seguranca do instalador falhou")
    if partial.stat().st_size < 1024 * 1024:
        partial.unlink(missing_ok=True)
        raise RuntimeError("o arquivo de atualizacao parece incompleto")

    partial.replace(target)
    _downloaded_installer = target
    return target


def installer_is_ready() -> bool:
    return bool(_downloaded_installer and _downloaded_installer.is_file())


def install_and_restart() -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError("a instalacao automatica so esta disponivel no aplicativo instalado")
    if not installer_is_ready():
        raise RuntimeError("baixe a atualizacao antes de instalar")

    installer = str(_downloaded_installer)

    def launch() -> None:
        time.sleep(1.0)
        subprocess.Popen(
            [installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=launch, daemon=False).start()

