"""Local dashboard server (FastAPI). Binds to 127.0.0.1 only.

Run directly: ``python -m weekly_recap.server.app`` (the launcher does this in
the background, detached from the terminal).
"""
from __future__ import annotations

import argparse
import os
import signal
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import FRONTEND_DIR, _PROFILE_RE, load_settings
from ..database.db import Database
from ..processing.report import build_report

APP_ID = "weekly-recap"
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def create_app(data_dir: Path | None = None, default_profile: str | None = None,
               idle_hours: float = 0) -> FastAPI:
    base = load_settings(default_profile)
    if data_dir:
        base.data_dir = Path(data_dir)
    app = FastAPI(title="Weekly Recap", docs_url=None, redoc_url=None, openapi_url=None)
    state = {"last": time.time()}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Defense against DNS-rebinding: only answer to localhost Host headers.
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "forbidden host"}, status_code=403)
        state["last"] = time.time()
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def settings_for(profile: str | None):
        name = (profile or base.profile).lower()
        if not _PROFILE_RE.match(name):
            raise HTTPException(400, "invalid profile")
        s = load_settings(name)
        s.data_dir = base.data_dir
        return s

    @app.get("/api/health")
    def health():
        return {"app": APP_ID, "pid": os.getpid()}

    @app.get("/api/report")
    def report(profile: str | None = None):
        s = settings_for(profile)
        if not s.db_path.is_file():
            return {"has_run": False, "profile": s.profile, "is_demo": s.is_demo}
        db = Database(s.db_path)
        try:
            return build_report(db, is_demo=s.is_demo, profile=s.profile)
        finally:
            db.close()

    @app.post("/api/messages/{message_id}/read")
    def mark_read(message_id: int, profile: str | None = None):
        s = settings_for(profile)
        if not s.db_path.is_file():
            raise HTTPException(404)
        db = Database(s.db_path)
        try:
            return {"ok": db.mark_message_read(message_id)}
        finally:
            db.close()

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    if idle_hours > 0:
        def watchdog():
            while True:
                time.sleep(60)
                if time.time() - state["last"] > idle_hours * 3600:
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
        threading.Thread(target=watchdog, daemon=True).start()
    return app


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--idle-hours", type=float, default=None)
    args = ap.parse_args()
    s = load_settings()
    if s.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("WR_HOST must stay 127.0.0.1 (the dashboard is not exposed to the network).")
    app = create_app(idle_hours=args.idle_hours if args.idle_hours is not None else s.server_idle_hours)
    uvicorn.run(app, host="127.0.0.1", port=args.port or s.port, log_level="warning")


if __name__ == "__main__":
    main()
