#!/usr/bin/env python3
"""
Passos 6 e 7 da revisão. Rode DEPOIS do apply_patches.py (passos 1-5).

Antes:   pip install cryptography keyring pytest
Uso:     python apply_patches_v2.py      (na pasta do projeto, venv ativada)

Igual ao anterior: idempotente, cria .bak, preserva CRLF e não grava um arquivo
se algum trecho-âncora não for encontrado.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class P:
    def __init__(self, old, new, count=1, regex=False, done=None, desc=""):
        self.old, self.new, self.count = old, new, count
        self.regex, self.done, self.desc = regex, done, desc

    def is_done(self, text):
        if self.done is not None:
            return self.done in text
        if self.regex:
            return False
        if self.old in self.new:
            return self.new in text
        return self.old not in text

    def apply(self, text):
        if self.regex:
            return re.subn(self.old, self.new, text, flags=re.S)
        return text.replace(self.old, self.new), text.count(self.old)


class F:
    """Replaces a whole function/method (found by name) with new source."""

    count = 1

    def __init__(self, name, new_src, indent="", desc=""):
        self.old = f"def {name}(...)"
        self.name, self.new_src, self.indent, self.desc = name, new_src, indent, desc
        self.done = f"# v2 {name}"
        n = len(indent)
        self.pattern = re.compile(
            rf"^{indent}def {name}\(.*?(?=^ {{0,{n}}}\S|\Z)", re.M | re.S
        )

    def is_done(self, text):
        return self.done in text

    def apply(self, text):
        return self.pattern.subn(lambda m: self.new_src.rstrip() + "\n\n", text, count=1)


class Append:
    count = 1

    def __init__(self, marker, block, desc=""):
        self.marker, self.block, self.desc = marker, block, desc
        self.old = marker

    def is_done(self, text):
        return self.marker in text

    def apply(self, text):
        return text.rstrip("\n") + "\n" + self.block, 1


# ==========================================================================
# database.py
# ==========================================================================
DB_SAVE_LOG = r'''def save_log(activity_id: int, year: int, week: int, day_idx: int, status: str, score: int):
    # v2 save_log
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO daily_logs (activity_id, year, week_number, day_of_week, status, score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id, year, week_number, day_of_week)
        DO UPDATE SET status = excluded.status, score = excluded.score
    """, (activity_id, year, week, day_idx, status, score))
    _refresh_habit_day(cursor, year, week, day_idx)
    conn.commit()
    conn.close()
'''

DB_XP = r'''def get_user_xp_and_level():
    # v2 get_user_xp_and_level
    """Total XP is the sum of the XP ledger (history is immutable), capped at 1000."""
    conn = get_connection()
    total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_ledger").fetchone()[0] or 0.0
    conn.close()

    total_xp = max(0.0, min(1000.0, float(total)))
    if total_xp >= 1000.0:
        level = 100
        xp_in_level = 10.0
    else:
        level = max(1, int(total_xp // 10) + 1)
        xp_in_level = total_xp % 10.0

    return total_xp, level, xp_in_level, get_rank_title(level)
'''

DB_STREAK = r'''def get_current_streak():
    # v2 get_current_streak
    conn = get_connection()
    rows = conn.execute(
        "SELECT event_date, meta FROM xp_ledger WHERE source = 'habit_day' AND meta IS NOT NULL"
    ).fetchall()
    conn.close()

    date_scores = {}
    for d, avg in rows:
        try:
            date_scores[date.fromisoformat(d)] = avg
        except ValueError:
            continue
    if not date_scores:
        return 0

    today = date.today()
    streak = 0
    current_check = today
    if date_scores.get(today, 0) < SCORE_PASSING:
        current_check = date.fromordinal(today.toordinal() - 1)

    while date_scores.get(current_check, 0) >= SCORE_PASSING:
        streak += 1
        current_check = date.fromordinal(current_check.toordinal() - 1)
    return streak
'''

DB_PAST_WEEKS = r'''def get_past_weeks_scores(num_weeks=6):
    # v2 get_past_weeks_scores
    """Weekly score = average of the daily averages (same rule as the KPI card)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT year, week_number, AVG(day_avg) FROM (
            SELECT l.year AS year, l.week_number AS week_number, l.day_of_week,
                   AVG(l.score) AS day_avg
            FROM daily_logs l
            JOIN activities a ON l.activity_id = a.id
            WHERE a.active = 1 AND l.score IS NOT NULL
            GROUP BY l.year, l.week_number, l.day_of_week
        )
        GROUP BY year, week_number
        ORDER BY year ASC, week_number ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows[-num_weeks:] if rows else []
'''

DB_UPDATE_TASK = r'''def update_task_status(task_id: int, status: str, year: int, week: int):
    # v2 update_task_status
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row and row[0] == status:
        conn.close()
        return  # nothing changed: keeps completed_week and never double-awards XP

    if status == "Complete":
        cursor.execute("""
            UPDATE tasks
            SET status = ?, completed_year = ?, completed_week = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, year, week, task_id))
        _ledger_set(cursor, "quest", str(task_id), date.today().isoformat(), XP_QUEST, replace=False)
    else:
        cursor.execute("""
            UPDATE tasks
            SET status = ?, completed_year = NULL, completed_week = NULL, completed_at = NULL
            WHERE id = ?
        """, (status, task_id))
        _ledger_clear(cursor, "quest", str(task_id))
    conn.commit()
    conn.close()
'''

DB_NOTES = r'''def save_task_notes_with_progress(task_id: int, new_notes: str) -> float:
    # v2 save_task_notes_with_progress
    """Saves notes and awards XP if content grew by at least 10 characters (15 min cooldown)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(notes, '') FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    old_notes = row[0] if row else ""
    cursor.execute("UPDATE tasks SET notes = ? WHERE id = ?", (new_notes, task_id))

    xp_gained = 0.0
    new_clean = new_notes.strip()
    old_clean = old_notes.strip()

    if len(new_clean) >= len(old_clean) + 10 and new_clean != old_clean:
        cursor.execute(
            "SELECT created_at FROM quest_progress_logs WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        )
        last_log = cursor.fetchone()

        can_award = True
        if last_log and last_log[0]:
            try:
                last_time = datetime.strptime(last_log[0].split(".")[0], "%Y-%m-%d %H:%M:%S")
                # created_at is CURRENT_TIMESTAMP (UTC), so compare against utcnow
                if (datetime.utcnow() - last_time).total_seconds() < 900:
                    can_award = False
            except Exception:
                can_award = True

        if can_award:
            xp_gained = XP_NOTE_PROGRESS
            cursor.execute(
                "INSERT INTO quest_progress_logs (task_id, xp_awarded) VALUES (?, ?)",
                (task_id, xp_gained),
            )
            _ledger_set(cursor, "note", str(cursor.lastrowid), date.today().isoformat(),
                        xp_gained, replace=False)

    conn.commit()
    conn.close()
    return xp_gained
'''

DB_STUDY = r'''def update_study_session(session_id: int, topic: str, source: str, eli5: str, code_sandbox: str, break_test: str, recall_questions: str, status: str):
    # v2 update_study_session
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE study_sessions
        SET topic = ?, source = ?, eli5 = ?, code_sandbox = ?, break_test = ?, recall_questions = ?,
            status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (topic, source, eli5, code_sandbox, break_test, recall_questions, status, session_id))
    if status == "Mastered":
        _ledger_set(cursor, "study", str(session_id), date.today().isoformat(), XP_STUDY, replace=False)
    else:
        _ledger_clear(cursor, "study", str(session_id))
    conn.commit()
    conn.close()
'''

DB_TOGGLE_EVENT = r'''def toggle_event_completion(event_id: int, date_str: str):
    # v2 toggle_event_completion
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM event_completions WHERE event_id = ? AND completion_date = ?", (event_id, date_str))
    row = cursor.fetchone()
    ref = f"{event_id}:{date_str}"

    if row:
        cursor.execute("DELETE FROM event_completions WHERE id = ?", (row[0],))
        _ledger_clear(cursor, "event", ref)
        is_done = False
    else:
        cursor.execute("INSERT INTO event_completions (event_id, completion_date) VALUES (?, ?)", (event_id, date_str))
        _ledger_set(cursor, "event", ref, date_str, XP_EVENT, replace=False)
        is_done = True

    conn.commit()
    conn.close()
    return is_done
'''

DB_EVENTS = r'''def get_events_for_date(target_date: date):
    # v2 get_events_for_date
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, event_date, start_hour, recurrence
        FROM calendar_events
        WHERE active = 1 AND event_date <= ?
        ORDER BY start_hour ASC
    """, (target_date.strftime("%Y-%m-%d"),))
    rows = cursor.fetchall()
    conn.close()

    last_day = _calendar.monthrange(target_date.year, target_date.month)[1]
    matching_events = []
    for r in rows:
        _, _, start_date_str, _, rec = r
        start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        if rec == "none":
            match = start_d == target_date
        elif rec == "weekly":
            match = start_d.weekday() == target_date.weekday()
        elif rec == "monthly":
            # an event on the 31st falls on the last day of shorter months
            match = target_date.day == min(start_d.day, last_day)
        elif rec == "yearly":
            match = (target_date.month == start_d.month
                     and target_date.day == min(start_d.day, last_day))
        else:
            match = False

        if match:
            matching_events.append(r)
    return matching_events
'''

DB_GET_DOCS = r'''def get_documents(category_filter: str = "All"):
    # v2 get_documents
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT id, category, doc_type, title, doc_number, secondary_info, issue_date,
               expiration_date, notes, COALESCE(extra_fields, '[]')
        FROM personal_documents
        WHERE active = 1
    """
    if category_filter != "All":
        cursor.execute(query + " AND category = ? ORDER BY id DESC", (category_filter,))
    else:
        cursor.execute(query + " ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    out = []
    for r in rows:
        r = list(r)
        for i in (4, 5, 8, 9):  # doc_number, secondary_info, notes, extra_fields
            r[i] = secure.decrypt(r[i])
        out.append(tuple(r))
    return out
'''

DB_ADD_DOC = r'''def add_document(category: str, doc_type: str, title: str, doc_number: str, secondary_info: str = "", issue_date: str = "", expiration_date: str = "", notes: str = "", extra_fields: str = "[]"):
    # v2 add_document
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO personal_documents (category, doc_type, title, doc_number, secondary_info, issue_date, expiration_date, notes, extra_fields)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (category, doc_type, title, secure.encrypt(doc_number), secure.encrypt(secondary_info),
          issue_date, expiration_date, secure.encrypt(notes), secure.encrypt(extra_fields)))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id
'''

DB_UPDATE_DOC = r'''def update_document(doc_id: int, category: str, doc_type: str, title: str, doc_number: str, secondary_info: str, issue_date: str, expiration_date: str, notes: str, extra_fields: str = "[]"):
    # v2 update_document
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE personal_documents
        SET category = ?, doc_type = ?, title = ?, doc_number = ?, secondary_info = ?,
            issue_date = ?, expiration_date = ?, notes = ?, extra_fields = ?
        WHERE id = ?
    """, (category, doc_type, title, secure.encrypt(doc_number), secure.encrypt(secondary_info),
          issue_date, expiration_date, secure.encrypt(notes), secure.encrypt(extra_fields), doc_id))
    conn.commit()
    conn.close()
'''

DB_APPEND = r'''
# ==========================================================================
# v2: XP ledger, schema migrations, helpers
# ==========================================================================
def _ledger_set(cursor, source: str, ref_key: str, event_date: str, amount: float,
                meta=None, replace: bool = True):
    """Records an XP entry. replace=False keeps the original entry (and date) if it exists."""
    if replace:
        cursor.execute("""
            INSERT INTO xp_ledger (event_date, source, ref_key, amount, meta)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, ref_key) DO UPDATE SET
                event_date = excluded.event_date, amount = excluded.amount, meta = excluded.meta
        """, (event_date, source, ref_key, amount, meta))
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO xp_ledger (event_date, source, ref_key, amount, meta)
            VALUES (?, ?, ?, ?, ?)
        """, (event_date, source, ref_key, amount, meta))


def _ledger_clear(cursor, source: str, ref_key: str):
    cursor.execute("DELETE FROM xp_ledger WHERE source = ? AND ref_key = ?", (source, ref_key))


def _refresh_habit_day(cursor, year: int, week: int, day_idx: int):
    """Recomputes the net habit XP of one day: (daily average - 5) * 2."""
    try:
        day = date.fromisocalendar(year, week, day_idx + 1).isoformat()
    except ValueError:
        return
    avg = cursor.execute("""
        SELECT AVG(l.score) FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.score IS NOT NULL
          AND l.year = ? AND l.week_number = ? AND l.day_of_week = ?
    """, (year, week, day_idx)).fetchone()[0]

    if avg is None:
        _ledger_clear(cursor, "habit_day", day)
    else:
        _ledger_set(cursor, "habit_day", day, day, (avg - 5.0) * 2.0, meta=avg)


def get_weekly_xp(num_weeks: int = 8):
    """Net XP earned per ISO week, from the ledger: [(year, week, xp), ...]."""
    conn = get_connection()
    rows = conn.execute("SELECT event_date, amount FROM xp_ledger").fetchall()
    conn.close()
    weeks = {}
    for d, amount in rows:
        try:
            iso = date.fromisoformat(d).isocalendar()
        except ValueError:
            continue
        key = (iso[0], iso[1])
        weeks[key] = weeks.get(key, 0.0) + amount
    return [(y, w, xp) for (y, w), xp in sorted(weeks.items())][-num_weeks:]


def _backfill_xp_ledger(conn):
    """One-time import of the history that used to be recalculated on the fly."""
    ins = ("INSERT OR IGNORE INTO xp_ledger (event_date, source, ref_key, amount, meta) "
           "VALUES (?, ?, ?, ?, ?)")
    fallback = "date('now', 'localtime')"

    rows = conn.execute("""
        SELECT l.year, l.week_number, l.day_of_week, AVG(l.score)
        FROM daily_logs l JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.score IS NOT NULL
        GROUP BY l.year, l.week_number, l.day_of_week
    """).fetchall()
    for y, w, d, avg in rows:
        try:
            day = date.fromisocalendar(y, w, d + 1).isoformat()
        except ValueError:
            continue
        conn.execute(ins, (day, "habit_day", day, (avg - 5.0) * 2.0, avg))

    for tid, day in conn.execute(
        f"SELECT id, COALESCE(date(completed_at), {fallback}) FROM tasks "
        "WHERE status = 'Complete' AND active = 1"
    ).fetchall():
        conn.execute(ins, (day, "quest", str(tid), XP_QUEST, None))

    for sid, day in conn.execute(
        f"SELECT id, COALESCE(date(updated_at), {fallback}) FROM study_sessions "
        "WHERE status = 'Mastered' AND active = 1"
    ).fetchall():
        conn.execute(ins, (day, "study", str(sid), XP_STUDY, None))

    for eid, day in conn.execute(
        "SELECT event_id, completion_date FROM event_completions WHERE completed = 1"
    ).fetchall():
        conn.execute(ins, (day, "event", f"{eid}:{day}", XP_EVENT, None))

    for lid, day, xp in conn.execute(
        f"SELECT id, COALESCE(date(created_at), {fallback}), xp_awarded FROM quest_progress_logs"
    ).fetchall():
        conn.execute(ins, (day, "note", str(lid), xp, None))


def _to_iso(date_str: str) -> str:
    d = parse_flexible_date(date_str)
    return d.isoformat() if d else (date_str or "")


def _run_v2_migrations(conn):
    # 1. daily_logs: one row per (activity, day) -> allows a real upsert
    conn.execute("""
        DELETE FROM daily_logs WHERE id NOT IN (
            SELECT MAX(id) FROM daily_logs GROUP BY activity_id, year, week_number, day_of_week
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_logs_day
        ON daily_logs (activity_id, year, week_number, day_of_week)
    """)

    # 2. XP ledger (+ one-time backfill so the current level does not change)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xp_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            source TEXT NOT NULL,
            ref_key TEXT NOT NULL,
            amount REAL NOT NULL,
            meta REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, ref_key)
        )
    """)
    flag = conn.execute("SELECT value FROM hud_settings WHERE key = 'xp_ledger_backfilled'").fetchone()
    if not flag:
        _backfill_xp_ledger(conn)
        conn.execute("INSERT OR REPLACE INTO hud_settings (key, value) VALUES ('xp_ledger_backfilled', '1')")

    # 3. Document dates -> ISO (YYYY-MM-DD); the UI shows them as DD-MM-YY
    for doc_id, issue, exp in conn.execute(
        "SELECT id, issue_date, expiration_date FROM personal_documents"
    ).fetchall():
        new_issue, new_exp = _to_iso(issue), _to_iso(exp)
        if (new_issue, new_exp) != (issue, exp):
            conn.execute("UPDATE personal_documents SET issue_date = ?, expiration_date = ? WHERE id = ?",
                         (new_issue, new_exp, doc_id))

    # 4. Encrypt sensitive document fields that are still plain text
    if secure.AVAILABLE:
        for doc_id, num, sec, notes, extra in conn.execute(
            "SELECT id, doc_number, secondary_info, notes, extra_fields FROM personal_documents"
        ).fetchall():
            new = [secure.encrypt(v) for v in (num, sec, notes, extra)]
            if new != [num, sec, notes, extra]:
                conn.execute(
                    "UPDATE personal_documents SET doc_number = ?, secondary_info = ?, notes = ?, "
                    "extra_fields = ? WHERE id = ?", (*new, doc_id))


def _desktop_dir() -> Path:
    """Real Desktop folder (handles OneDrive redirection); falls back to AppData."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            p = Path(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
            if p.is_dir():
                return p
    except Exception:
        pass
    for cand in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop",
                 Path.home() / "OneDrive" / "Área de Trabalho"):
        if cand.is_dir():
            return cand
    return Path(get_db_path()).parent
'''

DATABASE = [
    P("import sqlite3, os, csv, json, shutil\n",
      "import sqlite3, os, csv, json, shutil\nimport calendar as _calendar\nimport secure\n",
      done="import secure\n"),
    P('cursor.execute("PRAGMA table_info(personal_documents)")',
      '_run_v2_migrations(conn)\n    cursor.execute("PRAGMA table_info(personal_documents)")',
      done="_run_v2_migrations(conn)", desc="migracoes v2 dentro do init_db"),
    F("save_log", DB_SAVE_LOG),
    F("get_user_xp_and_level", DB_XP),
    F("get_current_streak", DB_STREAK),
    F("get_past_weeks_scores", DB_PAST_WEEKS),
    F("update_task_status", DB_UPDATE_TASK),
    F("save_task_notes_with_progress", DB_NOTES),
    F("update_study_session", DB_STUDY),
    F("toggle_event_completion", DB_TOGGLE_EVENT),
    F("get_events_for_date", DB_EVENTS),
    F("get_documents", DB_GET_DOCS),
    F("add_document", DB_ADD_DOC),
    F("update_document", DB_UPDATE_DOC),
    P('desktop_dir = Path.home() / "Desktop"', "desktop_dir = _desktop_dir()"),
    Append("def _run_v2_migrations", DB_APPEND),
]

# ==========================================================================
# schedule_view.py  -  week navigation
# ==========================================================================
SCHEDULE_METHODS = '''    def _sync_week(self):
        """Keeps the displayed week; follows the real week while viewing the current one."""
        cur_year, cur_week, real_today = db.get_current_week_info()
        if self.viewing_current:
            self.year, self.week = cur_year, cur_week
        # highlight "today" only when the displayed week is the current one
        self.today_idx = real_today if self.viewing_current else -1

    def _shift_week(self, delta: int):
        monday = date.fromisocalendar(self.year, self.week, 1) + timedelta(weeks=delta)
        y, w, _ = monday.isocalendar()
        cur_year, cur_week, _ = db.get_current_week_info()
        if (y, w) > (cur_year, cur_week):
            return  # no logging in the future
        self.year, self.week = y, w
        self.viewing_current = ((y, w) == (cur_year, cur_week))
        self.render()
        self.calculate_daily_scores()

    def _go_current_week(self):
        self.viewing_current = True
        self.render()
        self.calculate_daily_scores()

    def _week_range_label(self):
        start = date.fromisocalendar(self.year, self.week, 1)
        end = start + timedelta(days=6)
        return f"{start:%d/%m} - {end:%d/%m}"

    def render(self):'''

SCHEDULE = [
    P("import database as db\n", "import database as db\nfrom datetime import date, timedelta\n",
      done="from datetime import date, timedelta"),
    P("self.daily_score_texts = {}", "self.daily_score_texts = {}\n        self.viewing_current = True",
      done="self.viewing_current = True"),
    P("self.year, self.week, self.today_idx = db.get_current_week_info()", "self._sync_week()",
      count=3, done="self._sync_week()\n"),
    P("    def render(self):", SCHEDULE_METHODS, done="def _shift_week"),
    P(
        r'ft\.Text\(f"Week \{self\.week\} \(\{self\.year\}\)", size=22, weight=ft\.FontWeight\.BOLD\),\s+'
        r'ft\.Text\(f"• Today is \{DAY_NAMES\[self\.today_idx\]\}", size=15, color=ft\.Colors\.CYAN_ACCENT\)',
        '''ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=ft.Colors.CYAN_ACCENT, tooltip="Previous week",
                                  on_click=lambda e: self._shift_week(-1)),
                    ft.Text(f"Week {self.week} ({self.year})", size=22, weight=ft.FontWeight.BOLD),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=ft.Colors.CYAN_ACCENT, tooltip="Next week",
                                  disabled=self.viewing_current, on_click=lambda e: self._shift_week(1)),
                    ft.Text(self._week_range_label(), size=14, color=ft.Colors.GREY_400),
                    ft.Text(
                        f"• Today is {DAY_NAMES[date.today().weekday()]}" if self.viewing_current
                        else "• Editing a past week (XP updates accordingly)",
                        size=15, color=ft.Colors.CYAN_ACCENT
                    ),
                    ft.Button(content="This week", icon=ft.Icons.TODAY, disabled=self.viewing_current,
                              on_click=lambda e: self._go_current_week())''',
        regex=True, done="self._go_current_week())", desc="2.2 navegacao entre semanas",
    ),
    P(r"def quick_fill_today\(self, e\):",
      "def quick_fill_today(self, e):\n        if not self.viewing_current:\n            return  # Quick-Fill only makes sense for today",
      regex=True, done="if not self.viewing_current:\n            return  # Quick-Fill"),
]

# ==========================================================================
# graphs_view.py  -  XP per week chart (from the ledger)
# ==========================================================================
GRAPHS_XP = '''# 5b. XP earned per week (from the XP ledger)
        weekly_xp = db.get_weekly_xp(num_weeks=8)
        if weekly_xp:
            import math
            xp_groups, xp_labels = [], []
            for idx, (yr, wk, xp) in enumerate(weekly_xp):
                xp_color = ft.Colors.GREEN_ACCENT if xp >= 0 else ft.Colors.RED_ACCENT
                xp_groups.append(
                    fch.BarChartGroup(
                        x=idx,
                        rods=[fch.BarChartRod(from_y=0, to_y=xp, width=28, color=xp_color, border_radius=ft.BorderRadius.all(4))]
                    )
                )
                xp_labels.append(fch.ChartAxisLabel(value=idx, label=ft.Text(f"W{wk}")))

            hi = max(10.0, max(x for _, _, x in weekly_xp))
            lo = min(0.0, min(x for _, _, x in weekly_xp))
            step = max(5, int(math.ceil((hi - lo) / 5 / 5.0) * 5))
            y_max = int(math.ceil(hi / step) * step)
            y_min = int(math.floor(lo / step) * step)

            xp_chart = fch.BarChart(
                groups=xp_groups,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                left_axis=fch.ChartAxis(
                    labels=[fch.ChartAxisLabel(value=v, label=ft.Text(str(v))) for v in range(y_min, y_max + 1, step)],
                    label_size=36
                ),
                bottom_axis=fch.ChartAxis(labels=xp_labels, label_size=30),
                horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.GREY_800, interval=step),
                min_y=y_min,
                max_y=y_max,
                interactive=True,
                expand=True
            )

            self.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("XP Earned per Week", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Net XP: habits + quests + studies + events", size=12, color=ft.Colors.GREY_400)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(content=xp_chart, height=200, padding=10)
                    ]),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=10,
                    padding=15,
                    margin=ft.Margin.symmetric(horizontal=20, vertical=5)
                )
            )

        # 6. Section 3: Category Breakdown & Habit Insights'''

GRAPHS = [
    P("# 6. Section 3: Category Breakdown & Habit Insights", GRAPHS_XP, done="# 5b. XP earned per week"),
]

# ==========================================================================
# calendar_view.py  -  yearly recurrence
# ==========================================================================
CALENDAR = [
    P('ft.DropdownOption("Monthly")', 'ft.DropdownOption("Monthly"),\n                    ft.DropdownOption("Yearly")',
      done='ft.DropdownOption("Yearly")'),
    P('rec = "monthly"', 'rec = "monthly"\n                elif rec_dropdown.value == "Yearly":\n                    rec = "yearly"',
      done='rec = "yearly"'),
]

# ==========================================================================
# documents_view.py  -  ISO dates, validation, single date parser, clipboard
# ==========================================================================
DOCS_HANDLE_COPY = '''    def handle_copy(self, val: str, btn: ft.IconButton):
        # v2 handle_copy
        copy_to_windows_clipboard(val)
        restore_icon = ft.Icons.COPY_ALL_ROUNDED if btn.icon_size == 18 else ft.Icons.COPY
        btn.icon = ft.Icons.CHECK
        btn.icon_color = ft.Colors.GREEN_ACCENT
        if self.app_page:
            self.app_page.update()

        def _restore():
            try:
                btn.icon = restore_icon
                btn.icon_color = ft.Colors.CYAN_ACCENT
                if self.app_page:
                    self.app_page.update()
            except Exception:
                pass

        for delay, fn, args in ((2.0, _restore, ()), (30.0, clear_clipboard_if_unchanged, (val,))):
            t = threading.Timer(delay, fn, args=args)
            t.daemon = True
            t.start()
'''

DOCS_CLEAR_CLIP = '''def clear_clipboard_if_unchanged(text: str):
    """Wipes the clipboard 30s after copying a document number (only if still ours)."""
    try:
        cur = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=10, creationflags=0x08000000
        ).stdout.strip()
        if cur == text.strip():
            subprocess.run("clip", input=b"", creationflags=0x08000000)
    except Exception:
        pass

def mask_number(val: str) -> str:'''

DOCS_PARSE = '''def parse_flexible_date(date_str: str):
    # v2 parse_flexible_date
    return db.parse_flexible_date(date_str)  # single implementation lives in database.py
'''

DOCS = [
    ALIAS_DOCS := P("import subprocess\n", "import subprocess\nimport threading\n", done="import threading\n"),
    P("def mask_number(val: str) -> str:", DOCS_CLEAR_CLIP, done="def clear_clipboard_if_unchanged"),
    F("parse_flexible_date", DOCS_PARSE),
    F("handle_copy", DOCS_HANDLE_COPY, indent="    "),
    P(
        r'issue_clean = format_to_dd_mm_yy\(self\.issue_input\.value\) if self\.issue_input\.value\.strip\(\) else ""\s+'
        r'exp_clean = format_to_dd_mm_yy\(self\.expiration_input\.value\) if self\.expiration_input\.value\.strip\(\) else ""',
        '''issue_raw = self.issue_input.value.strip()
        exp_raw = self.expiration_input.value.strip()
        issue_d = parse_flexible_date(issue_raw) if issue_raw else None
        exp_d = parse_flexible_date(exp_raw) if exp_raw else None
        self.issue_input.error_text = "Invalid date (use DD-MM-YY)" if issue_raw and not issue_d else None
        self.expiration_input.error_text = "Invalid date (use DD-MM-YY)" if exp_raw and not exp_d else None
        if self.issue_input.error_text or self.expiration_input.error_text:
            if self.app_page:
                self.app_page.update()
            return
        # stored as ISO (YYYY-MM-DD); displayed as DD-MM-YY
        issue_clean = issue_d.isoformat() if issue_d else ""
        exp_clean = exp_d.isoformat() if exp_d else ""''',
        regex=True, done="# stored as ISO (YYYY-MM-DD)", desc="2.6 validacao + ISO",
    ),
]

# ==========================================================================
# wallpaper.py / main.py
# ==========================================================================
WALLPAPER = [
    P('print(f"Wallpaper update error: {ex}")',
      'logging.getLogger("gamification").exception("Wallpaper update error")',
      done='"Wallpaper update error")'),
    P("import textwrap\n", "import logging\nimport textwrap\n", done="import logging\n"),
]

REMINDER_BLOCK = '''# 3. Calendar Event Reminders (robust to sleep/resume, skips completed events)
                for ev in db.get_events_for_date(today):
                    eid, title, _, hour, _ = ev
                    if db.is_event_completed(eid, today_str):
                        continue
                    event_dt = datetime(today.year, today.month, today.day, hour, 0, 0)
                    delta_min = (event_dt - now).total_seconds() / 60.0

                    if 0.0 < delta_min <= 15.0:
                        key = (eid, today_str, "15m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                            try:  # unobtrusive: tray notification, no focus stealing
                                tray_icon_instance.notify(
                                    f"'{title}' starts at {hour:02d}:00 (in {int(delta_min) + 1} min)",
                                    "Upcoming appointment"
                                )
                            except Exception:
                                log.exception("tray notification failed")

                    elif -30.0 <= delta_min <= 0.0:
                        key = (eid, today_str, "0m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            NOTIFIED_ALARMS.add((eid, today_str, "15m"))
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                            restore_window_from_tray(page)
                            show_alarm_dialog(
                                "🚨 Event Starting NOW!",
                                f"'{title}' starts now ({hour:02d}:00)!",
                                eid, today_str
                            )
            except Exception:
                log.exception("reminder loop failed")'''

MAIN = [
    P("from wallpaper import request_wallpaper_update as update_desktop_wallpaper, flush_wallpaper_update\n",
      "from wallpaper import request_wallpaper_update as update_desktop_wallpaper, flush_wallpaper_update\n"
      "from applog import setup_logging\n", done="from applog import setup_logging"),
    P('APP_TITLE = "Personal Gamification Tracker"\n',
      'APP_TITLE = "Personal Gamification Tracker"\nlog = setup_logging()\n', done="log = setup_logging()"),
    P("        pass  # a failed backup must never stop the app from starting",
      '        log.exception("Daily backup failed")  # never stop the app from starting',
      done='log.exception("Daily backup failed")'),
    P(r"# 3\. Calendar Event Reminders.*?except Exception:\s+pass(?=\s+threading\.Thread\(target=reminder_loop)",
      REMINDER_BLOCK, regex=True, done="# 3. Calendar Event Reminders (robust",
      desc="4 alarmes: sem duplicar concluidos, suspensao, notificacao de bandeja"),
]

FILES = {
    "database.py": DATABASE,
    "schedule_view.py": SCHEDULE,
    "graphs_view.py": GRAPHS,
    "calendar_view.py": CALENDAR,
    "documents_view.py": DOCS,
    "wallpaper.py": WALLPAPER,
    "main.py": MAIN,
}


def patch_file(name, patches):
    path = ROOT / name
    if not path.exists():
        print(f"[FALTA] {name}: arquivo nao encontrado em {ROOT}")
        return False

    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")

    problems, applied, skipped = [], 0, 0
    for i, p in enumerate(patches, 1):
        if p.is_done(text):
            skipped += 1
            continue
        new_text, n = p.apply(text)
        if n != p.count:
            snippet = str(p.old)[:70].replace("\n", "\\n")
            problems.append(f"patch #{i} (achou {n}x, esperado {p.count}x): {snippet}")
            continue
        text = new_text
        applied += 1

    if problems:
        print(f"[ERRO ] {name}: nada foi gravado.")
        for pr in problems:
            print("        -", pr)
        return False

    if applied:
        bak = path.with_name(path.name + ".v2.bak")
        if not bak.exists():
            bak.write_bytes(raw.encode("utf-8"))
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        print(f"[ OK  ] {name}: {applied} alteracao(oes), {skipped} ja existente(s)")
    else:
        print(f"[ --  ] {name}: ja estava atualizado")
    return True


def update_requirements():
    path = ROOT / "requirements.txt"
    if not path.exists():
        return
    from importlib import metadata

    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    names = {re.split(r"[=<>]", l)[0].lower() for l in lines}
    for pkg in ("cryptography", "keyring"):
        if pkg not in names:
            try:
                lines.append(f"{pkg}=={metadata.version(pkg)}")
            except metadata.PackageNotFoundError:
                print(f"        ! {pkg} nao esta instalado: rode `pip install {pkg}` e este script de novo")
                lines.append(pkg)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[ OK  ] requirements.txt:", ", ".join(lines))


def main():
    for needed in ("secure.py", "applog.py"):
        if not (ROOT / needed).exists():
            print(f"[FALTA] copie {needed} para a pasta do projeto antes de rodar este script.")
            return 1
    ok = True
    for name, patches in FILES.items():
        ok &= patch_file(name, patches)
    update_requirements()
    print("\nConcluido." if ok else "\nConcluido COM PENDENCIAS (veja [ERRO ]/[FALTA]).")
    print("Guarde sua chave de criptografia:  python secure.py show-key")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
