/* Weekly Recap dashboard — vanilla JS, no build step. All text is inserted as text (no innerHTML). */
(() => {
  "use strict";

  const TZ = "Asia/Jerusalem";
  const params = new URLSearchParams(location.search);
  const profile = params.get("profile") || "";
  const q = profile ? `?profile=${encodeURIComponent(profile)}` : "";

  // ---------------------------------------------------------------- utils
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  function safeUrl(u) {
    try {
      const url = new URL(u);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch { return null; }
  }

  // Dates arrive as local Israel time without offset ("2026-11-10T23:59") or as dates ("2026-11-10").
  function parseLocal(s) {
    if (!s) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(s);
    if (!m) return null;
    return { y: +m[1], mo: +m[2], d: +m[3], hh: m[4] ? +m[4] : null, mm: m[5] ? +m[5] : null,
             date: new Date(+m[1], +m[2] - 1, +m[3], m[4] ? +m[4] : 23, m[5] ? +m[5] : 59) };
  }
  const WEEKDAYS = ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳"];
  const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט",
                  "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
  const pad = (n) => String(n).padStart(2, "0");

  function fmtDate(s, { weekday = true, time = true, year = false } = {}) {
    const p = parseLocal(s);
    if (!p) return "";
    let out = `${p.d}.${p.mo}${year ? "." + p.y : ""}`;
    if (weekday) out = `יום ${WEEKDAYS[p.date.getDay()]}, ${out}`;
    if (time && p.hh !== null) out += ` · ${pad(p.hh)}:${pad(p.mm)}`;
    return out;
  }

  function fmtWeek(start, end) {
    const a = parseLocal(start), b = parseLocal(end);
    if (!a || !b) return "";
    if (a.mo === b.mo) return `שבוע ${a.d}–${b.d} ב${MONTHS[b.mo - 1]} ${b.y}`;
    return `שבוע ${a.d} ב${MONTHS[a.mo - 1]} – ${b.d} ב${MONTHS[b.mo - 1]} ${b.y}`;
  }

  function relDue(hoursLeft) {
    if (hoursLeft === null || hoursLeft === undefined) return "";
    const abs = Math.abs(hoursLeft);
    const days = Math.round(abs / 24);
    let span;
    if (abs < 1) span = "פחות משעה";
    else if (abs < 24) span = Math.round(abs) === 1 ? "שעה" : Math.round(abs) === 2 ? "שעתיים" : `${Math.round(abs)} שעות`;
    else span = days === 1 ? "יום" : days === 2 ? "יומיים" : `${days} ימים`;
    return hoursLeft >= 0 ? `בעוד ${span}` : `לפני ${span}`;
  }

  function fmtUpdated(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return "עודכן " + new Intl.DateTimeFormat("he-IL", {
      timeZone: TZ, day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit",
    }).format(d);
  }

  // ---------------------------------------------------------------- theme
  const root = document.documentElement;
  try {
    const saved = localStorage.getItem("wr-theme");
    if (saved) root.dataset.theme = saved;
  } catch { /* storage unavailable */ }
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const dark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("wr-theme", root.dataset.theme); } catch { /* ignore */ }
  });

  // ---------------------------------------------------------------- sections
  function sectionHead(num, title, note) {
    return h("div", { class: "section-head" },
      h("h2", {}, h("span", { class: "section-num" }, num), title),
      note ? h("span", { class: "section-note" }, note) : null);
  }

  function unavailable(text) { return h("div", { class: "unavailable" }, text); }

  const STAT_DEFS = [
    { key: "absences", label: "היעדרויות", ico: "⌀", tone: "danger", higherIsBad: true },
    { key: "lates", label: "איחורים", ico: "⏱", tone: "warn", higherIsBad: true },
    { key: "positives", label: "חיזוקים חיוביים", ico: "★", tone: "ok", higherIsBad: false },
    { key: "notes", label: "אירועים והערות", ico: "✎", tone: "info", higherIsBad: true },
  ];
  const KIND_LABEL = { absence: ["היעדרות", "danger"], late: ["איחור", "warn"],
                       positive: ["חיזוק חיובי", "ok"], note: ["אירוע / הערה", "info"] };

  function renderBehavior(b) {
    const wrap = h("section", { "aria-labelledby": "behavior-h" });
    const note = b.available
      ? (b.stale ? `נתונים מ־${fmtUpdated(b.as_of).replace("עודכן ", "")} — המקור לא עודכן בהפעלה האחרונה` : "")
      : "";
    wrap.append(sectionHead("1", "סיכום התנהגות שבועי", note));
    const stats = h("div", { class: "stats" });
    for (const def of STAT_DEFS) {
      const value = b.available ? b.counts[def.key] : null;
      let deltaEl = null;
      if (b.available && b.previous && b.previous[def.key] !== null && b.previous[def.key] !== undefined) {
        const d = b.delta[def.key];
        if (d === 0) deltaEl = h("div", { class: "delta" }, `ללא שינוי משבוע שעבר (${b.previous[def.key]})`);
        else {
          const good = def.higherIsBad ? d < 0 : d > 0;
          deltaEl = h("div", { class: "delta" },
            h("span", { class: good ? "good" : "bad" }, `${d > 0 ? "▲" : "▼"} ${Math.abs(d)}`),
            ` לעומת שבוע שעבר (${b.previous[def.key]})`);
        }
      } else if (b.available) {
        deltaEl = h("div", { class: "delta" }, "אין נתוני שבוע קודם להשוואה");
      }
      stats.append(h("div", { class: `stat tone-${def.tone}` },
        h("div", { class: "label" }, h("span", { class: "ico", "aria-hidden": "true" }, def.ico), def.label),
        value === null
          ? h("div", { class: "value na" }, "אין נתונים")
          : h("div", { class: "value" }, value),
        deltaEl));
    }
    wrap.append(stats);
    if (!b.available) {
      wrap.append(h("div", { style: "margin-top:12px" },
        unavailable("נתוני התנהגות ונוכחות יופיעו כאן אחרי חיבור משוב. לא מוצגים מספרים שלא נאספו בפועל.")));
    } else if (b.events.length) {
      const list = h("ul", { class: "event-list" });
      for (const e of b.events) {
        const [label, tone] = KIND_LABEL[e.kind] || [e.title, "neutral"];
        list.append(h("li", {},
          h("span", { class: "when" }, fmtDate(e.date, { time: false })),
          h("span", {}, h("span", { class: `badge tone-${tone}` }, label)),
          h("span", {}, [e.title !== label ? e.title : null, e.subject, e.teacher, e.details]
            .filter(Boolean).join(" · "),
            e.justified === 1 ? h("span", { class: "badge tone-neutral", style: "margin-inline-start:8px" }, "מוצדק") : null)));
      }
      wrap.append(h("details", { class: "card events", open: true },
        h("summary", {}, `פירוט האירועים השבוע (${b.events.length})`), list));
    }
    return wrap;
  }

  const STATUS_BADGE = { open: ["פתוחה", "info"], late: ["באיחור", "danger"],
                         submitted: ["הוגשה", "ok"], cancelled: ["בוטלה", "neutral"] };

  function taskItem(t) {
    const st = t.effective_status;
    const [label, tone] = STATUS_BADGE[st] || [st, "neutral"];
    const url = safeUrl(t.url);
    const dueChanged = t.changes.some((c) => c.field === "due_at");
    return h("li", { class: `task urgency-${t.urgency} status-${st}` },
      h("div", { class: "task-top" },
        h("span", { class: "subject" }, [t.subject || "ללא מקצוע", t.teacher].filter(Boolean).join(" · ")),
        h("span", { class: `badge tone-${tone}` }, label)),
      h("div", { class: "task-title" }, t.title),
      h("div", { class: "task-meta" },
        t.due_at
          ? h("span", { class: "due" }, "הגשה: ", h("strong", {}, fmtDate(t.due_at)),
              st !== "submitted" && t.hours_left !== null ? ` (${relDue(t.hours_left)})` : "")
          : h("span", {}, "ללא מועד הגשה"),
        h("span", {}, t.source_name)),
      h("div", { class: "task-flags" },
        t.is_new ? h("span", { class: "badge tone-info" }, "חדשה") : null,
        t.carried_over ? h("span", { class: "badge tone-warn" }, "הועברה משבוע קודם") : null,
        dueChanged ? h("span", { class: "badge tone-warn" }, "מועד ההגשה השתנה") : null,
        t.submitted_late === 1 ? h("span", { class: "badge tone-warn" }, "הוגשה באיחור") : null,
        url ? h("a", { class: "task-link", href: url, target: "_blank", rel: "noopener noreferrer" }, "פתיחת המשימה ↗") : null));
  }

  function taskColumn(title, tone, items, emptyText, extra) {
    const list = h("ul", { class: "task-list" });
    items.forEach((t) => list.append(taskItem(t)));
    if (!items.length) list.append(h("li", { class: "empty-col" }, emptyText));
    if (extra) list.append(h("li", { class: "empty-col" }, extra));
    return h("div", { class: `task-col tone-${tone}` },
      h("div", { class: "task-col-head" }, h("span", { class: "title" }, title),
        h("span", { class: "count" }, items.length)),
      list);
  }

  function describeChange(c) {
    if (c.field === "due_at") {
      return `${c.title}: מועד ההגשה השתנה מ־${fmtDate(c.old_value) || "ללא מועד"} ל־${fmtDate(c.new_value) || "ללא מועד"}`;
    }
    const lbl = (s) => (STATUS_BADGE[s] || [s])[0];
    return `${c.title}: הסטטוס השתנה מ"${lbl(c.old_value)}" ל"${lbl(c.new_value)}"`;
  }

  function renderTasks(t) {
    const wrap = h("section", {});
    wrap.append(sectionHead("2", "משימות", t.available ? "ממוינות לפי מועד הגשה" : ""));
    if (!t.available) {
      wrap.append(unavailable("משימות יופיעו כאן אחרי חיבור Google Classroom, לשון והבעה (מט״ח) או ClassIt (מתמטיקה)."));
      return wrap;
    }
    wrap.append(h("div", { class: "task-cols" },
      taskColumn("באיחור", "danger", t.late, "אין משימות באיחור 🎉",
        t.old_late_count ? `ועוד ${t.old_late_count} משימות ישנות (מעל 30 יום) שלא סומנו כהוגשו` : null),
      taskColumn("פתוחות", "info", t.open, "אין משימות פתוחות"),
      taskColumn("הוגשו השבוע", "ok", t.submitted, "עוד לא הוגשו משימות השבוע")));
    const changes = t.changes.map(describeChange);
    t.cancelled.forEach((c) => changes.push(`${c.title}: המשימה הוסרה מהמקור או בוטלה`));
    if (changes.length) {
      wrap.append(h("div", { class: "card changes" },
        h("strong", {}, "שינויים מאז ההפעלה הקודמת"),
        h("ul", {}, [...new Set(changes)].map((c) => h("li", {}, c)))));
    }
    return wrap;
  }

  const MSG_CATS = [
    { key: "grade", label: "ציונים חדשים", ico: "✓", tone: "ok" },
    { key: "homework", label: "שיעורי בית", ico: "✎", tone: "info" },
    { key: "trip", label: "טיולים", ico: "⛰", tone: "warn" },
    { key: "activity", label: "פעילויות ואירועים", ico: "✦", tone: "info" },
    { key: "teacher", label: "הודעות מורים", ico: "✉", tone: "neutral" },
  ];

  function renderMessages(m, prevRunAt) {
    const wrap = h("section", {});
    wrap.append(sectionHead("3", "הודעות חשובות",
      m.available ? (prevRunAt ? `חדשות מאז ${fmtUpdated(prevRunAt).replace("עודכן ", "")}` : "") : ""));
    if (!m.available) {
      wrap.append(unavailable("הודעות, שיעורי בית, טיולים וציונים חדשים ממשוב יופיעו כאן אחרי החיבור."));
      return wrap;
    }
    if (!m.count) {
      wrap.append(unavailable("אין הודעות חדשות מאז ההפעלה הקודמת. הודעות שכבר הוצגו לא מוצגות שוב."));
      return wrap;
    }
    const grid = h("div", { class: "msg-grid" });
    for (const cat of MSG_CATS) {
      const items = m.by_category[cat.key] || [];
      if (!items.length) continue;
      const list = h("ul", { class: "msg-list" });
      for (const msg of items) {
        const url = safeUrl(msg.url);
        const li = h("li", { class: "msg" },
          h("div", { class: "msg-title" },
            h("span", {}, url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, msg.title) : msg.title),
            msg.grade ? h("span", { class: "grade-pill" }, msg.grade) : null),
          h("div", { class: "msg-meta" }, [msg.subject, msg.sender, fmtDate(msg.date)].filter(Boolean).join(" · ")),
          msg.body ? h("div", { class: "msg-body" }, msg.body) : null,
          h("button", { class: "read-btn", type: "button", onclick: async (ev) => {
            ev.currentTarget.disabled = true;
            try {
              await fetch(`/api/messages/${msg.id}/read${q}`, { method: "POST" });
              li.remove();
              if (!list.children.length) list.closest(".msg-group").remove();
            } catch { ev.currentTarget.disabled = false; }
          } }, "סימון כנקרא"));
        list.append(li);
      }
      grid.append(h("div", { class: `msg-group tone-${cat.tone}` },
        h("h3", {}, h("span", { class: "ico", "aria-hidden": "true" }, cat.ico), cat.label,
          h("span", { class: "count" }, items.length)),
        list));
    }
    wrap.append(grid);
    return wrap;
  }

  function renderSummary(s) {
    const blocks = [
      ["מה קרה השבוע?", s.happened, "info"],
      ["מה צריך להשלים?", s.todo, "danger"],
      ["מה חשוב בשבוע הבא?", s.next_week, "warn"],
      ["שינויים בהתנהגות", s.behavior_change, "ok"],
    ];
    return h("section", {}, sectionHead("4", "סיכום כללי"),
      h("div", { class: "summary-grid" }, blocks.map(([title, items, tone]) =>
        h("div", { class: `summary-block tone-${tone}` }, h("h3", {}, title),
          h("ul", {}, items.map((x) => h("li", {}, x)))))));
  }

  function renderHistory(history, currentWeek) {
    if (!history || history.length < 1) return null;
    const val = (v, avail) => (avail && v !== null && v !== undefined ? v : "—");
    const rows = history.map((r) => h("tr", { class: r.week_start === currentWeek ? "current" : "" },
      h("td", {}, fmtDate(r.week_start, { weekday: false, time: false, year: true })),
      h("td", { class: "num" }, val(r.absences, r.behavior_available)),
      h("td", { class: "num" }, val(r.lates, r.behavior_available)),
      h("td", { class: "num" }, val(r.positives, r.behavior_available)),
      h("td", { class: "num" }, val(r.open_tasks, r.tasks_available)),
      h("td", { class: "num" }, val(r.late_tasks, r.tasks_available)),
      h("td", { class: "num" }, val(r.carried_over, r.tasks_available))));
    return h("section", {}, sectionHead("", "היסטוריה שבועית", "— = לא נאספו נתונים באותו שבוע"),
      h("div", { class: "card", style: "overflow-x:auto" },
        h("table", { class: "history-table" },
          h("thead", {}, h("tr", {}, ["שבוע שמתחיל ב־", "היעדרויות", "איחורים", "חיזוקים",
            "משימות פתוחות", "באיחור", "הועברו"].map((x) => h("th", {}, x)))),
          h("tbody", {}, rows))));
  }

  function renderSources(sources) {
    const box = document.getElementById("sources");
    box.replaceChildren(...(sources || []).map((s) =>
      h("span", { class: `src ${s.status}`, title: s.message || "" },
        h("bdi", {}, s.display_name), `: ${s.status_label}`)));
  }

  // ---------------------------------------------------------------- main
  async function load() {
    const app = document.getElementById("app");
    let r;
    try {
      const res = await fetch(`/api/report${q}`, { cache: "no-store" });
      r = await res.json();
    } catch {
      app.replaceChildren(unavailable("לא ניתן להתחבר לשרת המקומי. הריצו שוב: weekly recap"));
      return;
    }
    document.getElementById("demo-banner").hidden = !r.is_demo;
    if (r.is_demo) document.title = "[דמה] " + document.title;
    if (!r.has_run) {
      document.getElementById("week-range").textContent = "";
      app.replaceChildren(document.getElementById("tpl-empty").content.cloneNode(true));
      return;
    }
    document.getElementById("week-range").textContent = fmtWeek(r.week.start, r.week.end);
    document.getElementById("updated").textContent = fmtUpdated(r.run && r.run.finished_at);
    renderSources(r.sources);
    app.replaceChildren(
      renderBehavior(r.behavior),
      renderTasks(r.tasks),
      renderMessages(r.messages, r.previous_run_at),
      renderSummary(r.summary),
      renderHistory(r.history, r.week.start) || "");
  }

  load();
})();
