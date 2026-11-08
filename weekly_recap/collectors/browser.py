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


def _wait_for_user(context, target: Path, message: str,
                   on_tick: Callable[[], None] | None = None) -> str:
    """Wait until the user presses Enter in the terminal OR closes the browser window.

    The session is saved every few seconds while the window is open, so closing
    the window instead of pressing Enter does not lose the login.
    Returns "enter" or "closed".
    """
    import select
    import time

    print(message, end="", flush=True)
    last_save = 0.0
    while True:
        if on_tick:
            on_tick()
        open_pages = [pg for pg in context.pages if not pg.is_closed()]
        if not open_pages:
            print("\n   (חלון הדפדפן נסגר)")
            return "closed"
        if time.time() - last_save > 3:
            try:
                context.storage_state(path=str(target))
                target.chmod(0o600)
                last_save = time.time()
            except Exception:
                pass
        if sys.stdin.isatty():
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if ready:
                sys.stdin.readline()
                break
        try:
            # Short wait on the page also lets Playwright process browser events.
            open_pages[0].wait_for_timeout(400)
        except Exception:
            continue  # the window was closed during the wait
    try:
        context.storage_state(path=str(target))
        target.chmod(0o600)
    except Exception:
        pass
    return "enter"


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
        _wait_for_user(context, target,
                       "   כשאתם רואים את המסך הראשי של האתר — חזרו לכאן והקישו Enter"
                       " (או סגרו את החלון)... ")
        try:
            browser.close()
        except Exception:
            pass
    print(f"✅ ההתחברות נשמרה מקומית ({target.name}).")
    return target


def capture_session(settings: Settings, source: str, start_url: str, display_name: str,
                    prompt: Callable[[str], str] = input, fresh: bool = True) -> Path:
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
    counter = {"n": 0}
    fh = out_file.open("w", encoding="utf-8")
    out_file.chmod(0o600)

    pending: list[Any] = []

    def on_response(resp):
        # Event handlers must not call blocking Playwright APIs: just queue.
        try:
            if "json" in resp.headers.get("content-type", "") and resp.request.method == "GET":
                pending.append(resp)
            elif resp.status >= 400 and resp.request.resource_type in ("xhr", "fetch"):
                failures.append({"meta": "http_error", "url": resp.url, "type": "fetch",
                                 "error": f"HTTP {resp.status}"})
        except Exception:
            pass

    def on_failed(req):
        # Diagnostics only: which requests failed (URL path + error), no bodies.
        try:
            if req.resource_type in ("xhr", "fetch", "document"):
                failures.append({"meta": "failed", "url": req.url, "type": req.resource_type,
                                 "error": req.failure})
        except Exception:
            pass

    failures: list[dict[str, Any]] = []

    def drain():
        while failures:
            rec = failures.pop(0)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            path = re.sub(r"https?://[^/]+", "", rec["url"]).split("?")[0]
            print(f"\n   ⚠️  בקשה נכשלה: {path} ({rec['error']})", end="", flush=True)
        # Written immediately, so nothing is lost if the window is closed.
        while pending:
            resp = pending.pop(0)
            try:
                rec = {"url": resp.url, "status": resp.status, "page": resp.frame.url,
                       "body": resp.json()}
            except Exception:
                continue
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            counter["n"] += 1
            # Live feedback: endpoint path + item count only (no personal values).
            path = re.sub(r"https?://[^/]+", "", resp.url).split("?")[0]
            path = re.sub(r"[0-9a-fA-F-]{20,}", "…", path)
            body = rec["body"]
            size = f"{len(body)} פריטים" if isinstance(body, (list, dict)) else ""
            print(f"\n   📥 [{counter['n']}] {path} {size}", end="", flush=True)

    with sync_playwright() as p:
        browser = _launch(p, headless=False)
        ctx_kw: dict[str, Any] = {"locale": "he-IL", "timezone_id": settings.timezone}
        # Fresh by default: some sites keep part of the login in per-tab memory that a saved
        # session cannot restore, so the user logs in and browses in the same window.
        if target.is_file() and not fresh:
            ctx_kw["storage_state"] = str(target)
        context = browser.new_context(**ctx_kw)
        context.on("response", on_response)
        context.on("requestfailed", on_failed)
        page = context.new_page()
        page.goto(start_url)
        print(f"\n🧭 מצב כיול ל-{display_name}.")
        print("   קודם התחברו בחלון שנפתח (גם אם כבר התחברתם קודם).")
        print("   היכנסו בתפריט של האתר לכל עמוד רלוונטי (למשל: התנהגות, הודעות, ציונים,")
        print("   שיעורי בית / משימות), וחכו בכל עמוד כמה שניות. לא ללחוץ על 'שלח' או 'הגש'.")
        print("   על כל נתון שנקלט תופיע כאן שורה עם 📥 — כך רואים שזה עובד.")
        _wait_for_user(context, target, "   בסיום הקישו Enter כאן (או סגרו את החלון)... ",
                       on_tick=drain)
        drain()
        try:
            browser.close()
        except Exception:
            pass
    fh.close()
    print(f"✅ נשמרו {counter['n']} תגובות JSON מקומית: {out_file}")
    return out_file


class HeadlessSession:
    """Context manager: headless browser with the saved session + JSON response capture."""

    def __init__(self, settings: Settings, source: str):
        self.settings = settings
        self.source = source
        self.responses: list[dict[str, Any]] = []
        self._pending: list[Any] = []
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
                self._pending.append(resp)
        except Exception:
            pass

    def _drain(self) -> None:
        while self._pending:
            resp = self._pending.pop(0)
            try:
                self.responses.append({"url": resp.url, "status": resp.status, "body": resp.json()})
            except Exception:
                pass

    def json_matching(self, pattern: str) -> list[Any]:
        """Bodies of JSON GET responses whose URL matches. Call while the browser is open."""
        self._drain()
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
