"""
MediaBUDA Auto-Updater
Verifica atualizações no GitHub e baixa o instalador apropriado.
Repositório: TashiRabten/MidiaBUDA
"""

import sys
import os
import json
import urllib.request
import urllib.error
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict

APP_VERSION = "1.0.0"

GITHUB_REPO = "TashiRabten/MidiaBUDA"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"


class VersionUtils:
    """Funções utilitárias para comparação de versões."""

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        if not version_str:
            return (0, 0, 0)
        if version_str.startswith("v."):
            version_str = version_str[2:]
        elif version_str.startswith("v"):
            version_str = version_str[1:]
        try:
            return tuple(int(p.strip()) for p in version_str.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    @staticmethod
    def is_newer(latest: str, current: str) -> bool:
        lp = VersionUtils.parse_version(latest)
        cp = VersionUtils.parse_version(current)
        max_len = max(len(lp), len(cp))
        lp = lp + (0,) * (max_len - len(lp))
        cp = cp + (0,) * (max_len - len(cp))
        return lp > cp


class ReleaseParser:
    """Analisa respostas JSON da API de releases do GitHub."""

    @staticmethod
    def get_latest_release(json_text: str) -> Optional[Dict]:
        try:
            data = json.loads(json_text)
            releases = data if isinstance(data, list) else [data]
            for r in releases:
                if isinstance(r, dict) and not r.get("prerelease", False):
                    return r
            return releases[0] if releases and isinstance(releases[0], dict) else None
        except (json.JSONDecodeError, Exception):
            return None

    @staticmethod
    def extract_version(release: Dict) -> Optional[str]:
        tag = release.get("tag_name", "")
        if not tag:
            return None
        if tag.startswith("v."):
            return tag[2:]
        if tag.startswith("v"):
            return tag[1:]
        return tag

    @staticmethod
    def extract_download_url(release: Dict) -> Optional[str]:
        ext = ".exe" if sys.platform.startswith("win") else ".pkg"
        for asset in release.get("assets", []):
            if not isinstance(asset, dict):
                continue
            name = asset.get("name", "").lower()
            if name.endswith(ext):
                return asset.get("browser_download_url")
        return None

    @staticmethod
    def extract_release_notes(release: Dict) -> str:
        notes = release.get("body", "")
        return notes if notes else "Notas de versão não disponíveis."


class MediaBUDAUpdater:
    """Verificador de atualizações para o MediaBUDA."""

    def __init__(self, current_version: str = APP_VERSION):
        self.current_version = current_version
        self.api_url = GITHUB_RELEASES_API

    def check_for_updates(self) -> Tuple[bool, Optional[Dict]]:
        """Retorna (tem_atualização, info_dict_ou_None)."""
        try:
            req = urllib.request.Request(
                self.api_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "MediaBUDA-AutoUpdater/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.getcode() != 200:
                    return False, None
                body = resp.read().decode("utf-8")

            release = ReleaseParser.get_latest_release(body)
            if not release:
                return False, None

            latest = ReleaseParser.extract_version(release)
            if not latest:
                return False, None

            if VersionUtils.is_newer(latest, self.current_version):
                return True, {
                    "version": latest,
                    "download_url": ReleaseParser.extract_download_url(release),
                    "release_notes": ReleaseParser.extract_release_notes(release),
                }
            return False, None
        except Exception:
            return False, None

    def download_installer(
        self, download_url: str, progress_callback=None
    ) -> Optional[Path]:
        """Baixa o instalador para a pasta Downloads."""
        if not download_url:
            return None
        try:
            filename = download_url.split("/")[-1]
            if "?" in filename:
                filename = filename.split("?")[0]
            if not filename.endswith((".exe", ".pkg")):
                ext = ".exe" if sys.platform.startswith("win") else ".pkg"
                filename += ext

            temp_dir = Path(tempfile.mkdtemp(prefix="mediabuda-update-"))
            temp_file = temp_dir / filename

            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "MediaBUDA-AutoUpdater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                file_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(temp_file, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and file_size > 0:
                            progress_callback(int(downloaded * 100 / file_size))

            downloads_dir = Path.home() / "Downloads"
            downloads_dir.mkdir(exist_ok=True)
            final_path = downloads_dir / filename
            if final_path.exists():
                final_path.unlink()
            shutil.move(str(temp_file), str(final_path))
            temp_dir.rmdir()
            return final_path
        except Exception:
            return None

    @staticmethod
    def launch_installer(installer_path: Path) -> bool:
        """Abre o instalador baixado."""
        try:
            if not installer_path.exists():
                return False
            if sys.platform.startswith("win"):
                subprocess.Popen([str(installer_path)], shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(installer_path)])
            else:
                return False
            return True
        except Exception:
            return False
