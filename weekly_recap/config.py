"""Settings loaded from `.env` (never committed) plus per-profile paths.

Every piece of personal state (database, browser sessions, OAuth tokens,
raw captures) lives under ``data/profiles/<profile>/`` so that adding more
users later means adding more profiles — data is never shared between them.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
DEMO_PROFILE = "demo"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    profile: str = "default"
    host: str = "127.0.0.1"
    port: int = 8765
    timezone: str = "Asia/Jerusalem"
    data_dir: Path = PROJECT_ROOT / "data"
    server_idle_hours: float = 6.0
    chrome_path: str = ""
    headless: bool = True
    # Per-source raw settings (e.g. MASHOV_URL); collectors read what they need.
    env: dict[str, str] = field(default_factory=dict)

    # ---- derived paths -------------------------------------------------
    @property
    def profile_dir(self) -> Path:
        return self.data_dir / "profiles" / self.profile

    @property
    def db_path(self) -> Path:
        return self.profile_dir / "weekly_recap.sqlite3"

    @property
    def sessions_dir(self) -> Path:
        return self.profile_dir / "sessions"

    @property
    def secrets_dir(self) -> Path:
        return self.profile_dir / "secrets"

    @property
    def captures_dir(self) -> Path:
        return self.profile_dir / "captures"

    @property
    def run_dir(self) -> Path:
        return self.data_dir / "run"

    @property
    def is_demo(self) -> bool:
        return self.profile == DEMO_PROFILE

    def get(self, key: str, default: str = "") -> str:
        return self.env.get(key, default).strip()

    def ensure_dirs(self) -> None:
        for d in (self.profile_dir, self.sessions_dir, self.secrets_dir,
                  self.captures_dir, self.run_dir):
            d.mkdir(parents=True, exist_ok=True)
        # Personal data: owner-only permissions.
        for d in (self.data_dir, self.profile_dir, self.sessions_dir,
                  self.secrets_dir, self.captures_dir):
            try:
                d.chmod(0o700)
            except OSError:
                pass


def load_settings(profile: str | None = None, env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    env = dict(os.environ)
    chosen = (profile or env.get("WR_PROFILE") or "default").strip().lower()
    if not _PROFILE_RE.match(chosen):
        raise ValueError(f"Invalid profile name: {chosen!r}")
    host = env.get("WR_HOST", "127.0.0.1").strip() or "127.0.0.1"
    data_dir = Path(env.get("WR_DATA_DIR", "").strip() or PROJECT_ROOT / "data")
    return Settings(
        profile=chosen,
        host=host,
        port=int(env.get("WR_PORT", "8765") or 8765),
        timezone=env.get("WR_TIMEZONE", "Asia/Jerusalem") or "Asia/Jerusalem",
        data_dir=data_dir,
        server_idle_hours=float(env.get("WR_SERVER_IDLE_HOURS", "6") or 6),
        chrome_path=env.get("WR_CHROME_PATH", "").strip(),
        headless=_bool(env.get("WR_HEADLESS"), True),
        env=env,
    )
