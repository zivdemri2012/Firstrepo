"""Background server management + opening Google Chrome (WSL-aware).

The server is started fully detached (new session, no terminal attached), so
closing the terminal or Claude Code does not stop the dashboard. It exits by
itself after ``WR_SERVER_IDLE_HOURS`` without requests, or via ``weekly recap --stop``.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .config import PROJECT_ROOT, Settings

WINDOWS_CHROME_CANDIDATES = [
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def dashboard_url(settings: Settings, profile: str | None = None) -> str:
    url = f"http://localhost:{settings.port}/"
    if profile and profile != "default":
        url += f"?profile={profile}"
    return url


def server_alive(settings: Settings, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{settings.port}/api/health",
                                    timeout=timeout) as r:
            return json.load(r).get("app") == "weekly-recap"
    except Exception:
        return False


def _pidfile(settings: Settings) -> Path:
    return settings.run_dir / "server.pid"


def ensure_server(settings: Settings) -> bool:
    if server_alive(settings):
        return True
    settings.ensure_dirs()
    log = (settings.run_dir / "server.log").open("ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "weekly_recap.server.app", "--port", str(settings.port)],
        cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True,  # detach from this terminal
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    _pidfile(settings).write_text(str(proc.pid))
    for _ in range(50):
        if server_alive(settings, timeout=0.5):
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    return False


def stop_server(settings: Settings) -> bool:
    pf = _pidfile(settings)
    if pf.is_file():
        try:
            os.kill(int(pf.read_text().strip()), signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        pf.unlink(missing_ok=True)
    for _ in range(20):
        if not server_alive(settings, timeout=0.3):
            return True
        time.sleep(0.2)
    return False


def find_chrome(settings: Settings | None = None) -> list[str] | None:
    if settings and settings.chrome_path:
        return [settings.chrome_path]
    if is_wsl():
        for c in WINDOWS_CHROME_CANDIDATES:
            if Path(c).is_file():
                return [c]
        # Per-user Chrome install: ask Windows to start it.
        if shutil.which("cmd.exe"):
            return ["cmd.exe", "/c", "start", "", "chrome"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if p := shutil.which(name):
            return [p]
    return None


def open_in_chrome(url: str, settings: Settings | None = None) -> bool:
    cmd = find_chrome(settings)
    if cmd is None:
        opener = shutil.which("wslview") or shutil.which("xdg-open")
        if not opener:
            print(f"פתחו בדפדפן: {url}")
            return False
        cmd = [opener]
    try:
        subprocess.Popen(cmd + [url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         cwd="/mnt/c" if is_wsl() and Path("/mnt/c").is_dir() else None)
        return True
    except OSError:
        print(f"פתחו בדפדפן: {url}")
        return False
