"""``mission check <source>``: snapshot a task *with the student's own answers* for checking.

Flow:
1. A visible browser opens on the site (persistent profile, so the user may already be
   logged in). The user opens the task and fills in their answers. Nothing is submitted.
2. Every few seconds, while the page changed, the tool saves locally a screenshot plus
   the text of every frame: questions, math (LaTeX / MathML), and the values the
   student typed or selected.
3. The user closes the window (or presses Enter). The snapshot folder is printed so the
   answers can be checked. The tool itself only reads: it never types, clicks or submits.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from .collectors import browser
from .config import load_settings
from .pipeline import make_collector

SOURCES = ("cet", "classit", "mashov")

# Runs inside every frame; read-only.
_EXTRACT_JS = r"""
() => {
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  const labelOf = el => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) return clean(l.innerText);
    }
    const l = el.closest("label");
    if (l) return clean(l.innerText);
    return clean(el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.title);
  };
  const fields = [];
  document.querySelectorAll("input, textarea, select, [contenteditable=''], [contenteditable='true']")
    .forEach((el, i) => {
      const t = (el.type || "").toLowerCase();
      if (["hidden", "submit", "button", "password", "file", "image", "reset"].includes(t)) return;
      const f = { i, tag: el.tagName.toLowerCase(), type: t, name: el.name || "", id: el.id || "",
                  label: labelOf(el).slice(0, 300) };
      if (t === "checkbox" || t === "radio") f.checked = el.checked;
      else if (el.tagName === "SELECT") f.value = el.selectedOptions[0] ? clean(el.selectedOptions[0].text) : "";
      else if (el.isContentEditable) f.value = clean(el.innerText);
      else f.value = el.value;
      fields.push(f);
    });
  const math = [];
  document.querySelectorAll('annotation[encoding="application/x-tex"], [data-latex], script[type^="math/tex"]')
    .forEach(el => math.push(clean(el.getAttribute("data-latex") || el.textContent)));
  document.querySelectorAll("math").forEach(el => {
    if (!el.querySelector("annotation")) math.push(clean(el.textContent));
  });
  return { url: location.href, title: document.title,
           text: (document.body ? document.body.innerText : "").slice(0, 40000),
           fields, math: math.slice(0, 500) };
}
"""


def _snapshot(page, out_dir: Path, state: dict) -> None:
    frames = []
    for fr in page.frames:
        try:
            frames.append(fr.evaluate(_EXTRACT_JS))
        except Exception:
            continue
    digest = hashlib.sha1(json.dumps(frames, ensure_ascii=False, sort_keys=True)
                          .encode()).hexdigest()
    if digest == state.get("digest"):
        return
    state["digest"] = digest
    state["n"] = state.get("n", 0) + 1
    (out_dir / "content.json").write_text(
        json.dumps({"saved_at": datetime.now().isoformat(timespec="seconds"),
                    "frames": frames}, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        page.screenshot(path=str(out_dir / "page.png"), full_page=True)
    except Exception:
        pass
    for p in out_dir.iterdir():
        p.chmod(0o600)


def check(source: str, profile: str | None = None) -> Path:
    from playwright.sync_api import sync_playwright

    settings = load_settings(profile)
    col = make_collector(settings, source)
    url = col.start_url
    if not url:
        raise SystemExit(f"חסרה כתובת האתר של {col.display_name} בקובץ ‎.env")
    settings.ensure_dirs()
    out_dir = settings.profile_dir / "missions" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.parent.chmod(0o700)
    out_dir.chmod(0o700)

    state: dict = {}
    with sync_playwright() as p:
        context = browser._launch_persistent(p, settings, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        print(f"\n📝 Mission check — {col.display_name}")
        print("   1. התחברו אם צריך, ופתחו את המשימה.")
        print("   2. ענו על השאלות כרגיל — אל תגישו.")
        print("   3. סגרו את החלון (או חזרו לכאן והקישו Enter). התשובות נשמרות אוטומטית.")
        last = 0.0
        while True:
            open_pages = [pg for pg in context.pages if not pg.is_closed()]
            if not open_pages:
                break
            if time.time() - last > 3:
                last = time.time()
                try:
                    _snapshot(open_pages[-1], out_dir, state)
                except Exception:
                    pass
            if sys.stdin.isatty():
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.readline()
                    try:
                        _snapshot(open_pages[-1], out_dir, state)
                    except Exception:
                        pass
                    break
            try:
                open_pages[0].wait_for_timeout(400)
            except Exception:
                continue
        try:
            context.close()
        except Exception:
            pass

    if not state.get("n"):
        print("⚠️ לא נשמר כלום (החלון נסגר מהר מדי?).")
    else:
        print(f"✅ נשמר: {out_dir}")
        print("   עכשיו כתבו ל-Claude: \"mission check\" — והוא יבדוק את התשובות.")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["check"]:
        argv = argv[1:]
    if not argv or argv[0] not in SOURCES:
        print(f"שימוש: mission check {{{'|'.join(SOURCES)}}}", file=sys.stderr)
        return 2
    check(argv[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
