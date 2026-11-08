"""Playwright helpers shared by browser-based collectors.

Design rules:
* Login is always done **manually by the user** in a visible browser window
  (no CAPTCHA / 2FA bypassing, passwords are never stored by this tool).
* After login, the browser's storage state (cookies) is saved locally under
  ``data/profiles/<profile>/sessions/<source>.json`` with 0600 permissions.
* Collection runs headless re-using that saved session, and only *reads*.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..config import Settings

CHROMIUM_DEPS_HINT = (
    "Chromium של Playwright חסר ספריות מערכת. הריצו פעם אחת:\n"
    "  sudo apt-get install -y libnss3 libnspr4\n"
    "(או: sudo ~/school-tools/.venv/bin/playwright install-deps chromium)"
)


def session_path(settings: Settings, source: str) -> Path:
    return settings.sessions_dir / f"{source}.json"


def has_session(settings: Settings, source: str) -> bool:
    return session_path(settings, source).is_file()


def _launch(p, headless: bool):
    try:
        return p.chromium.launch(headless=headless)
    except Exception as e:  # missing libnss3 etc.
        msg = str(e)
        if "shared libraries" in msg or "libnss3" in msg or "Host system is missing" in msg:
            raise RuntimeError(CHROMIUM_DEPS_HINT) from e
        raise


def manual_login(settings: Settings, source: str, start_url: str,
                 display_name: str, prompt: Callable[[str], str] = input) -> Path:
    """Open a visible browser at ``start_url``; the user logs in; we save the session."""
    from playwright.sync_api import sync_playwright

    settings.ensure_dirs()
    target = session_path(settings, source)
    with sync_playwright() as p:
        browser = _launch(p, headless=False)
        ctx_kw: dict[str, Any] = {"locale": "he-IL", "timezone_id": settings.timezone}
        if target.is_file():
            ctx_kw["storage_state"] = str(target)
        context = browser.new_context(**ctx_kw)
        page = context.new_page()
        page.goto(start_url)
        print(f"\n🔐 נפתח חלון דפדפן של {display_name}.")
        print("   התחברו ידנית (כולל אימות דו-שלבי אם נדרש).")
        prompt("   כשאתם רואים את המסך הראשי של האתר — חזרו לכאן והקישו Enter... ")
        context.storage_state(path=str(target))
        target.chmod(0o600)
        browser.close()
    print(f"✅ ההתחברות נשמרה מקומית ({target.name}).")
    return target


def capture_session(settings: Settings, source: str, start_url: str, display_name: str,
                    prompt: Callable[[str], str] = input) -> Path:
    """Calibration mode: user browses the relevant pages; we record the JSON the site loads.

    The capture is saved only locally (gitignored) and is used to build the
    parser from the site's *real* structure instead of guessing it.
    """
    from playwright.sync_api import sync_playwright

    settings.ensure_dirs()
    target = session_path(settings, source)
    out_dir = settings.captures_dir / source
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o700)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = out_dir / f"capture-{stamp}.jsonl"
    records: list[dict[str, Any]] = []

    def on_response(resp):
        try:
            ctype = resp.headers.get("content-type", "")
            if "json" not in ctype or resp.request.method != "GET":
                return
            records.append({"url": resp.url, "status": resp.status, "page": resp.frame.url,
                            "body": resp.json()})
        except Exception:
            pass

    with sync_playwright() as p:
        browser = _launch(p, headless=False)
        ctx_kw: dict[str, Any] = {"locale": "he-IL", "timezone_id": settings.timezone}
        if target.is_file():
            ctx_kw["storage_state"] = str(target)
        context = browser.new_context(**ctx_kw)
        context.on("response", on_response)
        page = context.new_page()
        page.goto(start_url)
        print(f"\n🧭 מצב כיול ל-{display_name}: היכנסו לעמודים הרלוונטיים (התנהגות, הודעות,")
        print("   ציונים, שיעורי בית / משימות). לא ללחוץ על 'שלח' או 'הגש'.")
        prompt("   בסיום הקישו Enter... ")
        context.storage_state(path=str(target))
        target.chmod(0o600)
        browser.close()
    with out_file.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out_file.chmod(0o600)
    print(f"✅ נשמרו {len(records)} תגובות JSON מקומית: {out_file}")
    return out_file


class HeadlessSession:
    """Context manager: headless browser with the saved session + JSON response capture."""

    def __init__(self, settings: Settings, source: str):
        self.settings = settings
        self.source = source
        self.responses: list[dict[str, Any]] = []
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self) -> "HeadlessSession":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self.browser = _launch(self._pw, headless=self.settings.headless)
        self.context = self.browser.new_context(
            storage_state=str(session_path(self.settings, self.source)),
            locale="he-IL", timezone_id=self.settings.timezone,
        )
        self.context.on("response", self._on_response)
        self.page = self.context.new_page()
        return self

    def _on_response(self, resp) -> None:
        try:
            if "json" in resp.headers.get("content-type", "") and resp.request.method == "GET":
                self.responses.append({"url": resp.url, "status": resp.status, "body": resp.json()})
        except Exception:
            pass

    def json_matching(self, pattern: str) -> list[Any]:
        rx = re.compile(pattern)
        return [r["body"] for r in self.responses if rx.search(r["url"]) and r["status"] == 200]

    def __exit__(self, *exc) -> None:
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
