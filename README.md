# Weekly Recap · הסיכום השבועי

כלי אישי שמרכז מידע מבית הספר (משוב, Google Classroom, לשון והבעה במט"ח, ClassIt במתמטיקה) ומציג דשבורד שבועי מקומי בעברית מלאה וב-RTL.

```bash
weekly recap
```

הפקודה אוספת נתונים, שומרת אותם ב-SQLite מקומי, מפעילה שרת דשבורד ברקע (מנותק מהטרמינל) ופותחת את Google Chrome.
היא עובדת גם כש-Claude Code סגור. אפשר לסגור את הטרמינל אחרי ההפעלה.

## התקנה

```bash
cd ~/school-tools
./scripts/install.sh            # venv, חבילות, Chromium של Playwright, פקודת weekly
sudo apt-get install -y libnss3 libnspr4   # פעם אחת, רק עבור איסוף ממשוב/גלים (WSL)
```

## פקודות

| פקודה | מה היא עושה |
|---|---|
| `weekly recap` | איסוף + פתיחת הדוח בכרום |
| `weekly recap --demo` | תצוגה עם **נתוני דמה** (פרופיל נפרד, מסומן בפס צהוב) |
| `weekly recap --no-collect` | פתיחת הדוח האחרון בלי לאסוף |
| `weekly recap --login mashov\|classroom\|cet\|classit` | התחברות ידנית ושמירת ה-session מקומית |
| `weekly recap --capture mashov\|cet\|classit` | מצב כיול: הקלטת מבנה הנתונים של האתר (מקומית בלבד) |
| `weekly recap --status` | מצב המקורות והשרת |
| `weekly recap --stop` | עצירת שרת הדשבורד |

## חיבור מקורות

* **Google Classroom**: דרך ה-API הרשמי, עם הרשאות קריאה בלבד וללא עלות.
  יוצרים OAuth client מסוג *Desktop app* ב-Google Cloud Console, מפעילים את Classroom API ושומרים את הקובץ כ-
  `data/profiles/default/secrets/classroom_client.json`. אחר כך מגדירים `CLASSROOM_ENABLED=true` ומריצים `weekly recap --login classroom`.
* **משוב / מט"ח (לשון והבעה) / ClassIt (מתמטיקה)**: מגדירים `MASHOV_URL` / `CET_URL` / `CLASSIT_URL` בקובץ `.env`. אחר כך:
  1. `weekly recap --login mashov`: נפתח חלון דפדפן ומתחברים **ידנית**. הכלי לא שומר סיסמאות ולא עוקף CAPTCHA או אימות דו-שלבי.
  2. `weekly recap --capture mashov`: נכנסים פעם אחת לעמודים הרלוונטיים כדי שהמפענח ייכתב לפי המבנה האמיתי של האתר, בלי ניחושים.

## ארכיטקטורה

```
weekly_recap/
  collectors/        איסוף (מודול לכל אתר; @register + WR_SOURCES)
    base.py          ממשק Collector + רישום
    browser.py       Playwright: התחברות ידנית, session שמור, מצב כיול
    mashov/ classroom/ cet/ classit/ galim/ demo/
  processing/        עיבוד: סיווג עברי, בניית הדוח והסיכום הטבעי
  database/db.py     SQLite: מניעת כפילויות, מעקב שינויים במשימות, היסטוריה שבועית
  server/app.py      FastAPI (127.0.0.1 בלבד)
  pipeline.py        איסוף → שמירה → תמונת מצב שבועית
  launcher.py        שרת ברקע + פתיחת Chrome (כולל Windows Chrome מתוך WSL)
  cli.py             weekly recap
frontend/            HTML/CSS/JS ללא שלב build
scripts/             weekly (launcher), install.sh
tests/               pytest
```

**הוספת מקור חדש:** יוצרים `weekly_recap/collectors/<name>/collector.py` עם מחלקה שיורשת מ-`Collector` (או מ-`BrowserSiteCollector`) ומחזירה `CollectorResult`. אחר כך מוסיפים את שם המקור ל-`WR_SOURCES`.

**משתמשים נוספים:** לכל פרופיל (`--profile` / `WR_PROFILE`) יש תיקייה ומסד נתונים משלו תחת `data/profiles/<name>/`, כך שהנתונים מופרדים לגמרי.

## כללי נתונים

* מספר מוצג רק אם המקור שמספק אותו הצליח לאסוף. אחרת מוצג "אין נתונים", ואף פעם לא אפס מומצא.
* הודעות וציונים מוצגים פעם אחת, בהפעלה שבה הופיעו לראשונה. אפשר גם לסמן אותם כנקראו בדשבורד.
* משימה פתוחה או באיחור ממשיכה להופיע עד שהיא מוגשת או מוסרת מהמקור.
* שינויים במועד הגשה או בסטטוס נרשמים ב-`task_changes`.
* בכל הפעלה נשמרת תמונת מצב שבועית (שבוע שמתחיל ביום ראשון) לצורך השוואה.

## אבטחה

`.env`, `data/` (מסד נתונים, sessions, tokens וקובצי כיול) ו-cookies מוחרגים ב-`.gitignore`.
השרת מאזין רק ל-127.0.0.1 ודוחה Host שאינו localhost.
כל המחברים קוראים מידע בלבד: הם לא מגישים, לא עורכים ולא שולחים.

## בדיקות

```bash
.venv/bin/python -m pytest
```
