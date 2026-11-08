#!/usr/bin/env bash
# One-time setup: venv, Python packages, Playwright Chromium, `weekly` command.
# Installs nothing globally except a symlink in ~/.local/bin.
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  if python3 -m venv .venv 2>/dev/null; then :; else
    # Ubuntu without python3-venv: create without pip and bootstrap pip from PyPA.
    rm -rf .venv
    python3 -m venv --without-pip .venv
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    .venv/bin/python /tmp/get-pip.py -q && rm -f /tmp/get-pip.py
  fi
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install chromium

[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; echo "נוצר קובץ .env — ערכו אותו לפי הצורך."; }
mkdir -p data && chmod 700 data

mkdir -p "$HOME/.local/bin"
ln -sf "$ROOT/scripts/weekly" "$HOME/.local/bin/weekly"
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"; echo "נוסף ~/.local/bin ל-PATH (פתחו טרמינל חדש)." ;;
esac

if ldd "$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux*/chrome | tail -1)" 2>/dev/null | grep -q "not found"; then
  echo
  echo "⚠️  ל-Chromium חסרות ספריות מערכת (נדרש רק לאיסוף ממשוב/גלים). הריצו פעם אחת:"
  echo "    sudo apt-get install -y libnss3 libnspr4"
fi
echo "✅ מוכן. הפעלה: weekly recap   (תצוגת דמה: weekly recap --demo)"
