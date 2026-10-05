import sqlite3, os, csv, json, shutil, logging
import calendar as _calendar
import secure
from pathlib import Path
from datetime import datetime, date, timedelta
from constants import (get_rank_title, XP_QUEST, XP_STUDY, XP_EVENT, SCORE_PASSING,
                       XP_STUDY_LOG, XP_REVIEW, STUDY_STAGES, REVIEW_DAYS,
                       XP_SUBQUEST, XP_QUEST_LOG, QUEST_DIFFICULTY_XP)

def get_db_path():
    app_data = os.getenv("APPDATA")
    if app_data:
        base_dir = Path(app_data) / "Daily_Personal_Gamification"
    else:
        base_dir = Path.home() / ".daily_personal_gamification"
        
    base_dir.mkdir(parents=True, exist_ok=True)
    return str(base_dir / "gamification.db")

def get_connection():
    return sqlite3.connect(get_db_path(), timeout=10)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    conn.execute("PRAGMA journal_mode=WAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Routine',
            is_negative INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    # 1. Base Tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            source TEXT DEFAULT 'FIAP / Alura',
            eli5 TEXT DEFAULT '',
            code_sandbox TEXT DEFAULT '',
            break_test TEXT DEFAULT '',
            recall_questions TEXT DEFAULT '',
            status TEXT DEFAULT 'In Progress',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hud_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_hour INTEGER NOT NULL,
            recurrence TEXT DEFAULT 'none',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            completion_date TEXT,
            completed INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_id, completion_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quest_progress_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            xp_awarded REAL DEFAULT 2.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            year INTEGER,
            week_number INTEGER,
            day_of_week INTEGER,
            status TEXT,
            score INTEGER,
            FOREIGN KEY (activity_id) REFERENCES activities (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'Planning',
            notes TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            completed_year INTEGER,
            completed_week INTEGER,
            completed_at TIMESTAMP,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'Planning',
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,       -- 'Identity', 'Vehicle', 'Housing', 'Other'
            doc_type TEXT NOT NULL,       -- 'CPF', 'RG / CIN', 'CNH', 'Passport', 'CRLV', 'IPTU', etc.
            title TEXT NOT NULL,          -- e.g. "Minha CNH", "Carro Honda", "Passaporte"
            doc_number TEXT NOT NULL,
            secondary_info TEXT DEFAULT '', -- Órgão emissor, Renavam, Placa, etc.
            issue_date TEXT DEFAULT '',    -- YYYY-MM-DD
            expiration_date TEXT DEFAULT '', -- YYYY-MM-DD
            notes TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Migrations for Activities table
    cursor.execute("PRAGMA table_info(activities)")
    cols = [info[1] for info in cursor.fetchall()]
    if "category" not in cols:
        cursor.execute("ALTER TABLE activities ADD COLUMN category TEXT DEFAULT 'Routine'")
    if "is_negative" not in cols:
        cursor.execute("ALTER TABLE activities ADD COLUMN is_negative INTEGER DEFAULT 0")
    if "sort_order" not in cols:
        cursor.execute("ALTER TABLE activities ADD COLUMN sort_order INTEGER DEFAULT 0")
        cursor.execute("UPDATE activities SET sort_order = id WHERE sort_order = 0 OR sort_order IS NULL")

    # 3. Migrations for Tasks table
    cursor.execute("PRAGMA table_info(tasks)")
    task_cols = [info[1] for info in cursor.fetchall()]
    if "notes" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN notes TEXT DEFAULT ''")
    if "sort_order" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")
        cursor.execute("UPDATE tasks SET sort_order = id WHERE sort_order = 0 OR sort_order IS NULL")
    
    # 4. Migrations for Documents table (must run before v2: it encrypts extra_fields)
    cursor.execute("PRAGMA table_info(personal_documents)")
    doc_cols = [info[1] for info in cursor.fetchall()]
    if "extra_fields" not in doc_cols:
        cursor.execute("ALTER TABLE personal_documents ADD COLUMN extra_fields TEXT DEFAULT '[]'")

    _run_v2_migrations(conn)
    _run_calendar_migrations(conn)
    _run_study_migrations(conn)
    _run_quest_migrations(conn)
    _run_document_migrations(conn)

    conn.commit()
    conn.close()

def get_current_week_info():
    today = date.today()
    iso = today.isocalendar()
    return iso[0], iso[1], today.weekday()

# --- Activities (Daily Habits) Operations ---
def get_activities():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, category, is_negative FROM activities WHERE active = 1 ORDER BY sort_order ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_activity(name: str, category: str = "Routine", is_negative: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM activities WHERE active = 1")
    next_order = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO activities (name, category, is_negative, sort_order) VALUES (?, ?, ?, ?)",
        (name, category, 1 if is_negative else 0, next_order)
    )
    activity_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return activity_id

def update_activity(activity_id: int, name: str = None, category: str = None):
    """Renames / re-categorizes a habit (the positive/vice flag stays: past answers depend on it)."""
    fields = {k: v for k, v in (("name", name), ("category", category)) if v is not None}
    if not fields:
        return
    conn = get_connection()
    conn.execute(f"UPDATE activities SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                 (*fields.values(), activity_id))
    conn.commit()
    conn.close()


def count_unmarked_today() -> int:
    """Active habits with no answer today (used by the nightly check-in reminder)."""
    year, week, day_idx = get_current_week_info()
    conn = get_connection()
    n = conn.execute("""
        SELECT COUNT(*) FROM activities a
        WHERE a.active = 1 AND NOT EXISTS (
            SELECT 1 FROM daily_logs l WHERE l.activity_id = a.id AND l.year = ? AND l.week_number = ?
              AND l.day_of_week = ? AND l.score IS NOT NULL)
    """, (year, week, day_idx)).fetchone()[0]
    conn.close()
    return n


def delete_activity(activity_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE activities SET active = 0 WHERE id = ?", (activity_id,))
    # the daily averages (and their XP) only count active habits
    days = cursor.execute(
        "SELECT DISTINCT year, week_number, day_of_week FROM daily_logs WHERE activity_id = ?",
        (activity_id,),
    ).fetchall()
    for year, week, day_idx in days:
        _refresh_habit_day(cursor, year, week, day_idx)
    conn.commit()
    conn.close()

def move_activity(activity_id: int, direction: str):
    """Moves an activity up or down in the display order."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, sort_order FROM activities WHERE active = 1 ORDER BY sort_order ASC, id ASC")
    rows = cursor.fetchall()
    
    idx = next((i for i, r in enumerate(rows) if r[0] == activity_id), None)
    if idx is not None:
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap_idx < len(rows):
            curr_id, curr_order = rows[idx]
            target_id, target_order = rows[swap_idx]

            if curr_order == target_order:
                for i, r in enumerate(rows):
                    cursor.execute("UPDATE activities SET sort_order = ? WHERE id = ?", (i, r[0]))
                curr_order = idx
                target_order = swap_idx

            cursor.execute("UPDATE activities SET sort_order = ? WHERE id = ?", (target_order, curr_id))
            cursor.execute("UPDATE activities SET sort_order = ? WHERE id = ?", (curr_order, target_id))
            conn.commit()
    conn.close()

# --- Daily Logs Operations ---
def save_log(activity_id: int, year: int, week: int, day_idx: int, status: str, score: int):
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

def get_current_week_logs(year: int, week: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT activity_id, day_of_week, status, score 
        FROM daily_logs 
        WHERE year = ? AND week_number = ?
    """, (year, week))
    rows = cursor.fetchall()
    conn.close()
    
    logs = {}
    for r in rows:
        logs[(r[0], r[1])] = (r[2], r[3])
    return logs

# --- Gamification Calculations (All 5 Discipline Sources) ---
def get_user_xp_and_level():
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

def get_current_streak():
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

def get_past_weeks_scores(num_weeks=6):
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

def get_weekly_insights(year: int, week: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.name, a.category, a.is_negative, l.status, l.score
        FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.year = ? AND l.week_number = ? AND l.score IS NOT NULL
    """, (year, week))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "completion_rate": 0.0,
            "vice_rate": None,
            "category_scores": {},
            "strongest_habit": None,
            "nemesis_habit": None
        }

    total_logs = len(rows)
    completed_logs = sum(1 for r in rows if r[4] > 0)
    completion_rate = (completed_logs / total_logs) * 100.0 if total_logs else 0.0

    vice_rows = [r for r in rows if r[2] == 1]
    vice_rate = None
    if vice_rows:
        resisted = sum(1 for r in vice_rows if r[3] == "Resisted")
        vice_rate = (resisted / len(vice_rows)) * 100.0

    cat_points = {}
    for r in rows:
        cat = r[1]
        score = r[4]
        cat_points.setdefault(cat, []).append(score)

    category_scores = {
        cat: (sum(scores) / (len(scores) * 10.0)) * 100.0
        for cat, scores in cat_points.items()
    }

    habit_scores = {}
    for r in rows:
        name = r[0]
        score = r[4]
        habit_scores.setdefault(name, []).append(score)

    habit_avgs = {name: sum(sc) / len(sc) for name, sc in habit_scores.items()}
    strongest = max(habit_avgs.items(), key=lambda x: x[1]) if habit_avgs else None
    nemesis = min(habit_avgs.items(), key=lambda x: x[1]) if habit_avgs and len(habit_avgs) > 1 else None

    return {
        "completion_rate": completion_rate,
        "vice_rate": vice_rate,
        "category_scores": category_scores,
        "strongest_habit": strongest,
        "nemesis_habit": nemesis
    }

# --- Quests: types, difficulty XP, checkbox subquests, quest log, measurable targets, repeats ---
# No deadlines on purpose: nothing can be "late". Quests can be put on hold instead.
QUEST_FIELDS = ("id", "title", "status", "notes", "quest_type", "difficulty", "repeat", "metric_unit",
                "metric_start", "metric_target", "next_step", "completed_at", "sort_order", "created_at")
_EDITABLE_QUEST_FIELDS = {"title", "notes", "quest_type", "difficulty", "repeat", "metric_unit",
                          "metric_start", "metric_target", "next_step"}
QUEST_LOG_MIN_CHARS = 15  # a log entry this long (or any entry with a value) earns the daily log XP


def quest_period_key(repeat: str, on: date = None) -> str:
    """Completion period of a quest: 'done' (one-off), 'YYYY-Www' (weekly) or 'YYYY-MM' (monthly)."""
    on = on or date.today()
    if repeat == "weekly":
        iso = on.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if repeat == "monthly":
        return f"{on.year}-{on.month:02d}"
    return "done"


def next_period_start(repeat: str, on: date = None) -> date:
    """When a repeatable quest becomes available again."""
    on = on or date.today()
    if repeat == "weekly":
        return on + timedelta(days=7 - on.weekday())
    if repeat == "monthly":
        return date(on.year + (on.month == 12), on.month % 12 + 1, 1)
    return on


def quest_xp(difficulty: str) -> int:
    return QUEST_DIFFICULTY_XP.get(difficulty, XP_QUEST)


def _metric_progress(start, target, current):
    if start is None or target is None or current is None:
        return None
    if target == start:
        return 100.0 if current == target else 0.0
    return max(0.0, min(100.0, (current - start) / (target - start) * 100.0))


def get_quests(statuses=None, on: date = None):
    """Quests as dicts (QUEST_FIELDS + computed progress), in display order.

    Computed: subquests [{id, title, done, sort_order}], sub_done, sub_total, metric_current, metric_pct,
    progress_pct, period_key, done_this_period, times_completed, xp_reward, log_count, last_log.
    """
    on = on or date.today()
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT {', '.join(QUEST_FIELDS)} FROM tasks WHERE active = 1
        ORDER BY CASE status WHEN 'Active' THEN 0 WHEN 'On hold' THEN 1 ELSE 2 END,
                 CASE WHEN status = 'Complete' THEN completed_at END DESC, sort_order ASC, id ASC
    """).fetchall()
    subs = {}
    for task_id, sid, title, done_key, order in conn.execute("""
        SELECT task_id, id, title, COALESCE(done_key, ''), sort_order FROM subtasks
        WHERE active = 1 ORDER BY sort_order ASC, id ASC
    """):
        subs.setdefault(task_id, []).append((sid, title, done_key, order))
    logs = {r[0]: r[1:] for r in conn.execute("""
        SELECT task_id, COUNT(*), MAX(entry_date) FROM quest_log GROUP BY task_id
    """)}
    values = {}
    for task_id, value in conn.execute("""
        SELECT task_id, value FROM quest_log WHERE value IS NOT NULL ORDER BY entry_date ASC, id ASC
    """):
        values[task_id] = value  # last one wins = latest value
    completions = {}
    for task_id, period in conn.execute("SELECT task_id, period_key FROM quest_completions"):
        completions.setdefault(task_id, set()).add(period)
    conn.close()

    quests = []
    for r in rows:
        q = dict(zip(QUEST_FIELDS, r))
        q["notes"] = q["notes"] or ""
        q["next_step"] = q["next_step"] or ""
        q["metric_unit"] = q["metric_unit"] or ""
        q["repeat"] = q["repeat"] or "none"
        q["quest_type"] = q["quest_type"] or "Main"
        q["difficulty"] = q["difficulty"] or "Normal"
        if statuses and q["status"] not in statuses:
            continue
        key = quest_period_key(q["repeat"], on)
        q["period_key"] = key
        q["subquests"] = [{"id": sid, "title": title, "done": done_key == key, "sort_order": order}
                          for sid, title, done_key, order in subs.get(q["id"], [])]
        q["sub_total"] = len(q["subquests"])
        q["sub_done"] = sum(1 for s in q["subquests"] if s["done"])
        q["has_metric"] = q["metric_target"] is not None and q["repeat"] == "none"
        q["metric_current"] = values.get(q["id"], q["metric_start"]) if q["has_metric"] else None
        q["metric_pct"] = _metric_progress(q["metric_start"], q["metric_target"], q["metric_current"]) \
            if q["has_metric"] else None
        q["times_completed"] = len(completions.get(q["id"], ())) if q["repeat"] != "none" else \
            (1 if q["status"] == "Complete" else 0)
        q["done_this_period"] = key in completions.get(q["id"], ()) if q["repeat"] != "none" else \
            q["status"] == "Complete"
        q["xp_reward"] = quest_xp(q["difficulty"])
        q["log_count"], q["last_log"] = logs.get(q["id"], (0, ""))
        parts = []
        if q["sub_total"]:
            parts.append(q["sub_done"] / q["sub_total"] * 100.0)
        if q["metric_pct"] is not None:
            parts.append(q["metric_pct"])
        if q["done_this_period"]:
            q["progress_pct"] = 100.0
        else:
            q["progress_pct"] = sum(parts) / len(parts) if parts else 0.0
        quests.append(q)
    return quests


def get_quest(quest_id: int, on: date = None):
    return next((q for q in get_quests(on=on) if q["id"] == quest_id), None)


def add_quest(title: str, quest_type: str = "Main", difficulty: str = "Normal", repeat: str = "none",
              notes: str = "", metric_unit: str = "", metric_start=None, metric_target=None,
              next_step: str = "", subquests=()) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    next_order = cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM tasks WHERE active = 1").fetchone()[0]
    cursor.execute("""
        INSERT INTO tasks (title, status, notes, quest_type, difficulty, repeat, metric_unit, metric_start,
                           metric_target, next_step, sort_order)
        VALUES (?, 'Active', ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, notes, quest_type, difficulty, repeat, metric_unit, metric_start, metric_target, next_step,
          next_order))
    quest_id = cursor.lastrowid
    for i, sub in enumerate(s for s in subquests if s and s.strip()):
        cursor.execute("INSERT INTO subtasks (task_id, title, status, sort_order) VALUES (?, ?, 'Planning', ?)",
                       (quest_id, sub.strip(), i + 1))
    conn.commit()
    conn.close()
    return quest_id


def update_quest(quest_id: int, **fields):
    """Edits quest fields (see _EDITABLE_QUEST_FIELDS). Completion/status: use the functions below."""
    unknown = set(fields) - _EDITABLE_QUEST_FIELDS
    if unknown:
        raise ValueError(f"Unknown quest fields: {sorted(unknown)}")
    if not fields:
        return
    conn = get_connection()
    conn.execute(f"UPDATE tasks SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                 (*fields.values(), quest_id))
    conn.commit()
    conn.close()


def set_quest_status(quest_id: int, status: str):
    """Active <-> On hold, or reopen a completed one-off quest (removes its completion XP)."""
    if status not in ("Active", "On hold"):
        raise ValueError("Use complete_quest() to complete a quest")
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT status FROM tasks WHERE id = ?", (quest_id,)).fetchone()
    if row and row[0] == "Complete":
        cursor.execute("UPDATE tasks SET completed_at = NULL, completed_year = NULL, completed_week = NULL "
                       "WHERE id = ?", (quest_id,))
        _ledger_clear(cursor, "quest", str(quest_id))
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, quest_id))
    conn.commit()
    conn.close()


def complete_quest(quest_id: int, on: date = None) -> float:
    """Turns in a quest. One-off: Complete (Hall of Fame). Repeatable: done for this period.

    Returns the XP awarded (0 if it was already done).
    """
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT status, difficulty, COALESCE(repeat, 'none') FROM tasks WHERE id = ?",
                         (quest_id,)).fetchone()
    if not row:
        conn.close()
        return 0.0
    status, difficulty, repeat = row
    xp = float(quest_xp(difficulty))
    if repeat == "none":
        if status == "Complete":
            conn.close()
            return 0.0
        iso = on.isocalendar()
        cursor.execute("""
            UPDATE tasks SET status = 'Complete', completed_at = ?, completed_year = ?, completed_week = ?
            WHERE id = ?
        """, (f"{on.isoformat()} {datetime.now():%H:%M:%S}", iso[0], iso[1], quest_id))
        _ledger_set(cursor, "quest", str(quest_id), on.isoformat(), xp, replace=False)
    else:
        key = quest_period_key(repeat, on)
        cursor.execute("INSERT OR IGNORE INTO quest_completions (task_id, period_key, completed_on, xp) "
                       "VALUES (?, ?, ?, ?)", (quest_id, key, on.isoformat(), xp))
        if cursor.rowcount == 0:
            conn.close()
            return 0.0
        _ledger_set(cursor, "quest", f"{quest_id}:{key}", on.isoformat(), xp, replace=False)
    conn.commit()
    conn.close()
    return xp


def undo_quest_completion(quest_id: int, on: date = None):
    """Repeatable: un-does this period's completion. One-off: reopens the quest."""
    on = on or date.today()
    quest = get_quest(quest_id, on=on)
    if not quest:
        return
    if quest["repeat"] == "none":
        set_quest_status(quest_id, "Active")
        return
    key = quest_period_key(quest["repeat"], on)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quest_completions WHERE task_id = ? AND period_key = ?", (quest_id, key))
    _ledger_clear(cursor, "quest", f"{quest_id}:{key}")
    conn.commit()
    conn.close()


def delete_quest(quest_id: int):
    conn = get_connection()
    conn.execute("UPDATE tasks SET active = 0 WHERE id = ?", (quest_id,))
    conn.commit()
    conn.close()


def _swap_sort_order(cursor, table: str, rows, item_id: int, direction: str) -> bool:
    """Swaps item_id with its neighbour in `rows` [(id, sort_order)]; renumbers when orders collide."""
    idx = next((i for i, r in enumerate(rows) if r[0] == item_id), None)
    if idx is None:
        return False
    swap = idx - 1 if direction == "up" else idx + 1
    if not 0 <= swap < len(rows):
        return False
    (a_id, a_order), (b_id, b_order) = rows[idx], rows[swap]
    if a_order == b_order:
        for i, (rid, _) in enumerate(rows):
            cursor.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (i, rid))
        a_order, b_order = idx, swap
    cursor.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (b_order, a_id))
    cursor.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (a_order, b_id))
    return True


def move_quest(quest_id: int, direction: str):
    """Moves a quest up/down among the quests with the same status."""
    conn = get_connection()
    cursor = conn.cursor()
    status = cursor.execute("SELECT status FROM tasks WHERE id = ?", (quest_id,)).fetchone()
    if status:
        rows = cursor.execute("SELECT id, sort_order FROM tasks WHERE active = 1 AND status = ? "
                              "ORDER BY sort_order ASC, id ASC", (status[0],)).fetchall()
        if _swap_sort_order(cursor, "tasks", rows, quest_id, direction):
            conn.commit()
    conn.close()


def add_subquest(quest_id: int, title: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    next_order = cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM subtasks "
                                "WHERE task_id = ? AND active = 1", (quest_id,)).fetchone()[0]
    cursor.execute("INSERT INTO subtasks (task_id, title, status, sort_order) VALUES (?, ?, 'Planning', ?)",
                   (quest_id, title, next_order))
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sub_id


def set_subquest_done(subquest_id: int, done: bool, on: date = None) -> float:
    """Checks / unchecks a subquest (+XP_SUBQUEST; repeatable quests reset every period)."""
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT COALESCE(t.repeat, 'none'), COALESCE(s.done_key, '') FROM subtasks s
        JOIN tasks t ON t.id = s.task_id WHERE s.id = ?
    """, (subquest_id,)).fetchone()
    if not row:
        conn.close()
        return 0.0
    key = quest_period_key(row[0], on)
    ref = f"{subquest_id}:{key}"
    gained = 0.0
    if done:
        cursor.execute("UPDATE subtasks SET done_key = ?, status = 'Complete' WHERE id = ?", (key, subquest_id))
        if row[1] != key:
            _ledger_set(cursor, "subquest", ref, on.isoformat(), XP_SUBQUEST, replace=False)
            gained = float(XP_SUBQUEST)
    else:
        cursor.execute("UPDATE subtasks SET done_key = '', status = 'Planning' WHERE id = ?", (subquest_id,))
        _ledger_clear(cursor, "subquest", ref)
    conn.commit()
    conn.close()
    return gained


def rename_subquest(subquest_id: int, title: str):
    conn = get_connection()
    conn.execute("UPDATE subtasks SET title = ? WHERE id = ?", (title, subquest_id))
    conn.commit()
    conn.close()


def delete_subquest(subquest_id: int):
    conn = get_connection()
    conn.execute("UPDATE subtasks SET active = 0 WHERE id = ?", (subquest_id,))
    conn.commit()
    conn.close()


def move_subquest(subquest_id: int, direction: str):
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT task_id FROM subtasks WHERE id = ?", (subquest_id,)).fetchone()
    if row:
        rows = cursor.execute("SELECT id, sort_order FROM subtasks WHERE task_id = ? AND active = 1 "
                              "ORDER BY sort_order ASC, id ASC", (row[0],)).fetchall()
        if _swap_sort_order(cursor, "subtasks", rows, subquest_id, direction):
            conn.commit()
    conn.close()


def _refresh_quest_log_xp(cursor, quest_id: int, entry_date: str):
    """One XP_QUEST_LOG per quest per day while a real entry exists that day."""
    ref = f"{quest_id}:{entry_date}"
    qualifies = cursor.execute("""
        SELECT 1 FROM quest_log WHERE task_id = ? AND entry_date = ?
          AND (value IS NOT NULL OR LENGTH(TRIM(text)) >= ?)
    """, (quest_id, entry_date, QUEST_LOG_MIN_CHARS)).fetchone()
    if qualifies:
        _ledger_set(cursor, "quest_log", ref, entry_date, XP_QUEST_LOG, replace=False)
    else:
        _ledger_clear(cursor, "quest_log", ref)


def get_quest_log(quest_id: int):
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, entry_date, text, value FROM quest_log WHERE task_id = ?
        ORDER BY entry_date DESC, id DESC
    """, (quest_id,)).fetchall()
    conn.close()
    return [{"id": r[0], "entry_date": r[1], "text": r[2] or "", "value": r[3]} for r in rows]


def add_quest_log(quest_id: int, text: str = "", value=None, next_step: str = "", entry_date: str = None) -> float:
    """Adds a progress entry (optionally a new target value). Returns the XP gained."""
    entry_date = entry_date or date.today().isoformat()
    ref = f"{quest_id}:{entry_date}"
    conn = get_connection()
    cursor = conn.cursor()
    had = cursor.execute("SELECT 1 FROM xp_ledger WHERE source = 'quest_log' AND ref_key = ?", (ref,)).fetchone()
    cursor.execute("INSERT INTO quest_log (task_id, entry_date, text, value) VALUES (?, ?, ?, ?)",
                   (quest_id, entry_date, text, value))
    if next_step.strip():
        cursor.execute("UPDATE tasks SET next_step = ? WHERE id = ?", (next_step.strip(), quest_id))
    _refresh_quest_log_xp(cursor, quest_id, entry_date)
    has = cursor.execute("SELECT 1 FROM xp_ledger WHERE source = 'quest_log' AND ref_key = ?", (ref,)).fetchone()
    conn.commit()
    conn.close()
    return float(XP_QUEST_LOG) if has and not had else 0.0


def update_quest_log(entry_id: int, text: str, value, entry_date: str):
    conn = get_connection()
    cursor = conn.cursor()
    old = cursor.execute("SELECT task_id, entry_date FROM quest_log WHERE id = ?", (entry_id,)).fetchone()
    if old:
        cursor.execute("UPDATE quest_log SET text = ?, value = ?, entry_date = ? WHERE id = ?",
                       (text, value, entry_date, entry_id))
        for d in {old[1], entry_date}:
            _refresh_quest_log_xp(cursor, old[0], d)
    conn.commit()
    conn.close()


def delete_quest_log(entry_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    old = cursor.execute("SELECT task_id, entry_date FROM quest_log WHERE id = ?", (entry_id,)).fetchone()
    if old:
        cursor.execute("DELETE FROM quest_log WHERE id = ?", (entry_id,))
        _refresh_quest_log_xp(cursor, old[0], old[1])
    conn.commit()
    conn.close()


def get_quest_week_stats(year: int, week: int):
    """(quests completed that ISO week, XP earned from quests that week)."""
    try:
        start = date.fromisocalendar(year, week, 1)
    except ValueError:
        return 0, 0.0
    end = start + timedelta(days=6)
    conn = get_connection()
    one_off = conn.execute("""
        SELECT COUNT(*) FROM tasks WHERE active = 1 AND status = 'Complete'
          AND completed_year = ? AND completed_week = ?
    """, (year, week)).fetchone()[0]
    repeats = conn.execute("""
        SELECT COUNT(*) FROM quest_completions c JOIN tasks t ON t.id = c.task_id
        WHERE t.active = 1 AND c.completed_on BETWEEN ? AND ?
    """, (start.isoformat(), end.isoformat())).fetchone()[0]
    xp = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM xp_ledger
        WHERE source IN ('quest', 'subquest', 'quest_log') AND event_date BETWEEN ? AND ?
    """, (start.isoformat(), end.isoformat())).fetchone()[0]
    conn.close()
    return one_off + repeats, float(xp)

# --- Study Chapters: journal, stages and spaced-repetition reviews ---
STUDY_FIELDS = ("id", "topic", "source", "eli5", "code_sandbox", "break_test", "recall_questions",
                "status", "created_at", "needs_review", "next_step", "mastered_at")
_EDITABLE_STUDY_FIELDS = {"topic", "source", "eli5", "code_sandbox", "break_test", "recall_questions", "next_step"}
JOURNAL_FIELDS = ("id", "session_id", "entry_date", "minutes", "notes", "next_step")
STUDY_LOG_MIN_CHARS = 20  # a journal entry this long earns the daily study XP


def get_study_sessions():
    """Active chapters as dicts (STUDY_FIELDS + journal / review stats), active stages first."""
    today = date.today().isoformat()
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT {', '.join('s.' + f for f in STUDY_FIELDS)},
               (SELECT COUNT(*) FROM study_journal j WHERE j.session_id = s.id),
               (SELECT COALESCE(SUM(minutes), 0) FROM study_journal j WHERE j.session_id = s.id),
               (SELECT MAX(entry_date) FROM study_journal j WHERE j.session_id = s.id),
               (SELECT COUNT(*) FROM study_reviews r WHERE r.session_id = s.id
                    AND r.done_date = '' AND r.due_date <= ?),
               (SELECT MIN(due_date) FROM study_reviews r WHERE r.session_id = s.id AND r.done_date = '')
        FROM study_sessions s
        WHERE s.active = 1
    """, (today,)).fetchall()
    conn.close()

    chapters = []
    for r in rows:
        ch = dict(zip(STUDY_FIELDS, r[:len(STUDY_FIELDS)]))
        ch["sessions"], ch["minutes"], ch["last_studied"], ch["reviews_due"], ch["next_review"] = r[len(STUDY_FIELDS):]
        ch["needs_review"] = bool(ch["needs_review"])
        for k in ("eli5", "code_sandbox", "break_test", "recall_questions", "next_step", "mastered_at", "source"):
            ch[k] = ch[k] or ""
        ch["last_studied"] = ch["last_studied"] or ""
        ch["next_review"] = ch["next_review"] or ""
        chapters.append(ch)

    # most recent activity first, then (stable) group: reviews due, active stages, mastered
    order = {"Studying": 0, "Reviewing": 1, "Not started": 2, "Mastered": 3}
    chapters.sort(key=lambda c: (c["last_studied"] or (c["created_at"] or "")[:10], c["id"]), reverse=True)
    chapters.sort(key=lambda c: (c["reviews_due"] == 0, order.get(c["status"], 9)))
    return chapters


def get_study_session(session_id: int):
    return next((c for c in get_study_sessions() if c["id"] == session_id), None)


def add_study_session(topic: str, source: str = "FIAP"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO study_sessions (topic, source, status) VALUES (?, ?, 'Not started')",
                   (topic, source))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def update_study_session(session_id: int, **fields):
    """Updates text fields (topic, source, wrap-up boxes, next_step). Status: use set_study_status."""
    unknown = set(fields) - _EDITABLE_STUDY_FIELDS
    if unknown:
        raise ValueError(f"Unknown study fields: {sorted(unknown)}")
    if not fields:
        return
    conn = get_connection()
    conn.execute(
        f"UPDATE study_sessions SET {', '.join(f'{k} = ?' for k in fields)}, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?", (*fields.values(), session_id))
    conn.commit()
    conn.close()


def delete_study_session(session_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE study_sessions SET active = 0 WHERE id = ?", (session_id,))
    cursor.execute("DELETE FROM study_reviews WHERE session_id = ? AND done_date = ''", (session_id,))
    conn.commit()
    conn.close()


def _schedule_review(cursor, session_id: int, review_no: int, due: date):
    cursor.execute("INSERT INTO study_reviews (session_id, review_no, due_date) VALUES (?, ?, ?)",
                   (session_id, review_no, due.isoformat()))


def _review_series_finished(cursor, session_id: int) -> bool:
    return cursor.execute(
        "SELECT 1 FROM study_reviews WHERE session_id = ? AND review_no = ? AND remembered = 1",
        (session_id, len(REVIEW_DAYS))).fetchone() is not None


def _start_reviews(cursor, session_id: int, start: date):
    """(Re)starts the review series: review 1 is due REVIEW_DAYS[0] days after `start`."""
    cursor.execute("DELETE FROM study_reviews WHERE session_id = ? AND done_date = ''", (session_id,))
    _schedule_review(cursor, session_id, 1, start + timedelta(days=REVIEW_DAYS[0]))


def set_study_status(session_id: int, status: str, on: date = None):
    """Moves a chapter between STUDY_STAGES. Mastering awards XP_STUDY and starts the reviews."""
    if status not in STUDY_STAGES:
        raise ValueError(f"Unknown study status: {status}")
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT status, needs_review FROM study_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row or row[0] == status:
        conn.close()
        return
    if status == "Mastered":
        cursor.execute("UPDATE study_sessions SET status = ?, mastered_at = ?, updated_at = CURRENT_TIMESTAMP "
                       "WHERE id = ?", (status, on.isoformat(), session_id))
        _ledger_set(cursor, "study", str(session_id), on.isoformat(), XP_STUDY, replace=False)
        if row[1]:
            _start_reviews(cursor, session_id, on)
    else:
        cursor.execute("UPDATE study_sessions SET status = ?, mastered_at = '', updated_at = CURRENT_TIMESTAMP "
                       "WHERE id = ?", (status, session_id))
        _ledger_clear(cursor, "study", str(session_id))
        cursor.execute("DELETE FROM study_reviews WHERE session_id = ? AND done_date = ''", (session_id,))
    conn.commit()
    conn.close()


def set_study_needs_review(session_id: int, needs_review: bool, on: date = None):
    """Turns spaced repetition on/off for a chapter (off for projects that need no review)."""
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE study_sessions SET needs_review = ? WHERE id = ?", (1 if needs_review else 0, session_id))
    if not needs_review:
        cursor.execute("DELETE FROM study_reviews WHERE session_id = ? AND done_date = ''", (session_id,))
    else:
        status = cursor.execute("SELECT status FROM study_sessions WHERE id = ?", (session_id,)).fetchone()
        pending = cursor.execute("SELECT 1 FROM study_reviews WHERE session_id = ? AND done_date = ''",
                                 (session_id,)).fetchone()
        if status and status[0] == "Mastered" and not pending and not _review_series_finished(cursor, session_id):
            _start_reviews(cursor, session_id, on)
    conn.commit()
    conn.close()


def get_study_reviews(session_id: int):
    """All reviews of a chapter (done and pending), oldest first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, review_no, due_date, done_date, remembered FROM study_reviews
        WHERE session_id = ? ORDER BY due_date ASC, id ASC
    """, (session_id,)).fetchall()
    conn.close()
    return [{"id": r[0], "review_no": r[1], "due_date": r[2], "done_date": r[3] or "",
             "remembered": None if r[4] is None else bool(r[4])} for r in rows]


def get_pending_reviews(until: date = None):
    """Pending reviews due on or before `until` (default: all), with the chapter topic."""
    conn = get_connection()
    query = """
        SELECT r.id, r.session_id, s.topic, r.review_no, r.due_date
        FROM study_reviews r JOIN study_sessions s ON s.id = r.session_id
        WHERE r.done_date = '' AND s.active = 1
    """
    params = ()
    if until is not None:
        query += " AND r.due_date <= ?"
        params = (until.isoformat(),)
    rows = conn.execute(query + " ORDER BY r.due_date ASC, s.topic ASC", params).fetchall()
    conn.close()
    return [{"id": r[0], "session_id": r[1], "topic": r[2], "review_no": r[3], "due_date": r[4]} for r in rows]


def complete_review(review_id: int, remembered: bool = True, on: date = None) -> float:
    """Marks a review done (+XP_REVIEW) and schedules the next one.

    remembered=False repeats the same review tomorrow instead of moving on.
    """
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT session_id, review_no, done_date FROM study_reviews WHERE id = ?",
                         (review_id,)).fetchone()
    if not row or row[2]:
        conn.close()
        return 0.0
    session_id, review_no, _ = row
    cursor.execute("UPDATE study_reviews SET done_date = ?, remembered = ? WHERE id = ?",
                   (on.isoformat(), 1 if remembered else 0, review_id))
    _ledger_set(cursor, "study_review", str(review_id), on.isoformat(), XP_REVIEW, replace=False)
    if not remembered:
        _schedule_review(cursor, session_id, review_no, on + timedelta(days=1))
    elif review_no < len(REVIEW_DAYS):
        gap = REVIEW_DAYS[review_no] - REVIEW_DAYS[review_no - 1]
        _schedule_review(cursor, session_id, review_no + 1, on + timedelta(days=gap))
    conn.commit()
    conn.close()
    return float(XP_REVIEW)


def _refresh_study_log_xp(cursor, session_id: int, entry_date: str):
    """One XP_STUDY_LOG per chapter per day, while a long-enough entry exists that day."""
    ref = f"{session_id}:{entry_date}"
    qualifies = cursor.execute(
        "SELECT 1 FROM study_journal WHERE session_id = ? AND entry_date = ? AND LENGTH(TRIM(notes)) >= ?",
        (session_id, entry_date, STUDY_LOG_MIN_CHARS)).fetchone()
    if qualifies:
        _ledger_set(cursor, "study_log", ref, entry_date, XP_STUDY_LOG, replace=False)
    else:
        _ledger_clear(cursor, "study_log", ref)


def get_journal(session_id: int):
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT {', '.join(JOURNAL_FIELDS)} FROM study_journal
        WHERE session_id = ? ORDER BY entry_date DESC, id DESC
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(zip(JOURNAL_FIELDS, r)) for r in rows]


def add_journal_entry(session_id: int, notes: str, minutes: int = 0, next_step: str = "",
                      entry_date: str = None) -> float:
    """Logs a study session. Returns the XP gained (first qualifying entry of the day)."""
    entry_date = entry_date or date.today().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    had_xp = cursor.execute("SELECT 1 FROM xp_ledger WHERE source = 'study_log' AND ref_key = ?",
                            (f"{session_id}:{entry_date}",)).fetchone()
    cursor.execute("""
        INSERT INTO study_journal (session_id, entry_date, minutes, notes, next_step)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, entry_date, minutes or 0, notes, next_step))
    if next_step.strip():
        cursor.execute("UPDATE study_sessions SET next_step = ? WHERE id = ?", (next_step.strip(), session_id))
    cursor.execute("UPDATE study_sessions SET status = 'Studying' WHERE id = ? AND status = 'Not started'",
                   (session_id,))
    _refresh_study_log_xp(cursor, session_id, entry_date)
    has_xp = cursor.execute("SELECT 1 FROM xp_ledger WHERE source = 'study_log' AND ref_key = ?",
                            (f"{session_id}:{entry_date}",)).fetchone()
    conn.commit()
    conn.close()
    return float(XP_STUDY_LOG) if has_xp and not had_xp else 0.0


def update_journal_entry(entry_id: int, notes: str, minutes: int, next_step: str, entry_date: str):
    conn = get_connection()
    cursor = conn.cursor()
    old = cursor.execute("SELECT session_id, entry_date FROM study_journal WHERE id = ?", (entry_id,)).fetchone()
    if not old:
        conn.close()
        return
    cursor.execute("UPDATE study_journal SET notes = ?, minutes = ?, next_step = ?, entry_date = ? WHERE id = ?",
                   (notes, minutes or 0, next_step, entry_date, entry_id))
    for d in {old[1], entry_date}:
        _refresh_study_log_xp(cursor, old[0], d)
    conn.commit()
    conn.close()


def delete_journal_entry(entry_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    old = cursor.execute("SELECT session_id, entry_date FROM study_journal WHERE id = ?", (entry_id,)).fetchone()
    if old:
        cursor.execute("DELETE FROM study_journal WHERE id = ?", (entry_id,))
        _refresh_study_log_xp(cursor, old[0], old[1])
    conn.commit()
    conn.close()

# --- AI review packs (generated by ai_review.py, one per mastered chapter) ---
AI_PACK_MAX_ATTEMPTS = 5


def get_ai_pack(session_id: int):
    """{"status", "content" (dict or None), "model", "error", "attempts", "updated_at"} or None."""
    conn = get_connection()
    row = conn.execute("SELECT status, content, model, error, attempts, updated_at FROM study_ai_packs "
                       "WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    try:
        content = json.loads(row[1]) if row[1] else None
    except ValueError:
        content = None
    return {"status": row[0], "content": content, "model": row[2] or "", "error": row[3] or "",
            "attempts": row[4] or 0, "updated_at": row[5] or ""}


def set_ai_pack(session_id: int, status: str, content: dict = None, model: str = None, error: str = None,
                count_attempt: bool = False, reset_attempts: bool = False):
    """Upserts a pack's state. Content/model are kept unless given (a failed regenerate keeps the old pack)."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO study_ai_packs (session_id, status, updated_at) VALUES (?, ?, ?)",
                 (session_id, status, now))
    sets, params = ["status = ?", "updated_at = ?", "error = ?"], [status, now, error or ""]
    if content is not None:
        sets.append("content = ?")
        params.append(json.dumps(content, ensure_ascii=False))
    if model is not None:
        sets.append("model = ?")
        params.append(model)
    if reset_attempts:
        sets.append("attempts = 0")
    elif count_attempt:
        sets.append("attempts = attempts + 1")
    conn.execute(f"UPDATE study_ai_packs SET {', '.join(sets)} WHERE session_id = ?", (*params, session_id))
    conn.commit()
    conn.close()


def get_ai_packs_to_generate(retry_after_minutes: int = 30):
    """Mastered chapters (with reviews on) whose pack is pending, or failed long enough ago to retry."""
    cutoff = (datetime.now() - timedelta(minutes=retry_after_minutes)).isoformat(timespec="seconds")
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.session_id FROM study_ai_packs p
        JOIN study_sessions s ON s.id = p.session_id
        WHERE s.active = 1 AND s.status = 'Mastered' AND s.needs_review = 1
          AND p.attempts < ?
          AND (p.status = 'pending' OR (p.status = 'failed' AND p.updated_at <= ?))
        ORDER BY p.updated_at ASC
    """, (AI_PACK_MAX_ATTEMPTS, cutoff)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_chapters_missing_ai_pack():
    """Mastered chapters with reviews on that have no ready pack (for "generate missing packs")."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.id FROM study_sessions s
        LEFT JOIN study_ai_packs p ON p.session_id = s.id
        WHERE s.active = 1 AND s.status = 'Mastered' AND s.needs_review = 1
          AND (p.session_id IS NULL OR p.status != 'ready')
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


# --- HUD Settings Operations ---
def get_hud_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM hud_settings")
    rows = cursor.fetchall()
    conn.close()
    
    defaults = {
        "position": "Top-Right",
        "bg_mode": "Custom Image (base_wallpaper.jpg)",
        "accent_color": "Amber / Gold",
        "show_quests": "true",
        "show_studies": "true",
        "show_score": "true",
        "show_xp_bar": "true",
        "show_calendar": "true"
    }
    defaults.update(dict(rows))
    return defaults

def set_hud_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO hud_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

# --- Calendar Events & Reminders Operations ---
RECURRENCES = ("none", "daily", "weekdays", "weekly", "monthly", "yearly")
EVENT_FIELDS = ("id", "title", "event_date", "start_hour", "start_minute", "duration_min", "all_day",
                "recurrence", "recurrence_end", "color", "notes", "reminder_min")
_EDITABLE_EVENT_FIELDS = set(EVENT_FIELDS) - {"id"}
NO_REMINDER = -1
ALL_DAY_REMINDER_HOUR = 9  # all-day events remind at 09:00 (the day before for reminders >= 1 day)


def _event_from_row(row) -> dict:
    ev = dict(zip(EVENT_FIELDS, row))
    ev["all_day"] = bool(ev["all_day"])
    ev["start_minute"] = ev["start_minute"] or 0
    ev["duration_min"] = 60 if ev["duration_min"] is None else ev["duration_min"]
    ev["reminder_min"] = 15 if ev["reminder_min"] is None else ev["reminder_min"]
    ev["notes"] = ev["notes"] or ""
    ev["recurrence_end"] = ev["recurrence_end"] or ""
    ev["color"] = ev["color"] or "Cyan"
    return ev


def add_calendar_event(title: str, event_date_str: str, start_hour: int = 9, recurrence: str = "none",
                       start_minute: int = 0, duration_min: int = 60, all_day: bool = False,
                       color: str = "Cyan", notes: str = "", reminder_min: int = 15,
                       recurrence_end: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO calendar_events (title, event_date, start_hour, recurrence, start_minute, duration_min,
                                     all_day, color, notes, reminder_min, recurrence_end)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, event_date_str, start_hour, recurrence, start_minute, duration_min,
          1 if all_day else 0, color, notes, reminder_min, recurrence_end))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_event(event_id: int):
    conn = get_connection()
    row = conn.execute(f"SELECT {', '.join(EVENT_FIELDS)} FROM calendar_events WHERE id = ?",
                       (event_id,)).fetchone()
    conn.close()
    return _event_from_row(row) if row else None


def update_calendar_event(event_id: int, **fields):
    """Updates the whole series. Accepts any of EVENT_FIELDS except id."""
    unknown = set(fields) - _EDITABLE_EVENT_FIELDS
    if unknown:
        raise ValueError(f"Unknown event fields: {sorted(unknown)}")
    if not fields:
        return
    if "all_day" in fields:
        fields["all_day"] = 1 if fields["all_day"] else 0
    conn = get_connection()
    conn.execute(
        f"UPDATE calendar_events SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
        (*fields.values(), event_id),
    )
    conn.commit()
    conn.close()


def delete_calendar_event(event_id: int):
    """Deletes the whole series."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE calendar_events SET active = 0 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def skip_event_occurrence(event_id: int, date_str: str):
    """Deletes a single occurrence of a repeating event."""
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO event_exceptions (event_id, exception_date) VALUES (?, ?)",
                 (event_id, date_str))
    conn.commit()
    conn.close()


def end_event_series(event_id: int, date_str: str):
    """Deletes this occurrence and all following ones (the earlier ones are kept)."""
    ev = get_event(event_id)
    if not ev:
        return
    if date_str <= ev["event_date"]:
        delete_calendar_event(event_id)
    else:
        day_before = date.fromisoformat(date_str) - timedelta(days=1)
        update_calendar_event(event_id, recurrence_end=day_before.isoformat())


def _move_completion(cursor, old_id: int, new_id: int, date_str: str):
    """Keeps a completed occurrence (and its XP) attached to the event that replaces it."""
    cursor.execute("UPDATE event_completions SET event_id = ? WHERE event_id = ? AND completion_date = ?",
                   (new_id, old_id, date_str))
    cursor.execute("UPDATE xp_ledger SET ref_key = ? WHERE source = 'event' AND ref_key = ?",
                   (f"{new_id}:{date_str}", f"{old_id}:{date_str}"))


def _clone_event(ev: dict, **overrides) -> int:
    new = {k: v for k, v in ev.items() if k not in ("id", "date")}
    new.update(overrides)
    return add_calendar_event(new.pop("title"), new.pop("event_date"), **new)


def edit_event_occurrence(event_id: int, date_str: str, **fields) -> int:
    """Changes only one occurrence: it is skipped in the series and replaced by a one-time event."""
    ev = get_event(event_id)
    if not ev:
        return None
    fields = {"event_date": date_str, **fields, "recurrence": "none", "recurrence_end": ""}
    skip_event_occurrence(event_id, date_str)
    new_id = _clone_event(ev, **fields)
    conn = get_connection()
    _move_completion(conn.cursor(), event_id, new_id, date_str)
    conn.commit()
    conn.close()
    return new_id


def edit_event_following(event_id: int, date_str: str, **fields) -> int:
    """Changes this occurrence and all following ones by splitting the series at date_str."""
    ev = get_event(event_id)
    if not ev:
        return None
    if date_str <= ev["event_date"]:
        update_calendar_event(event_id, **fields)
        return event_id
    fields = {"event_date": date_str, **fields}
    end_event_series(event_id, date_str)
    new_id = _clone_event(ev, **fields)
    conn = get_connection()
    cursor = conn.cursor()
    later = cursor.execute(
        "SELECT completion_date FROM event_completions WHERE event_id = ? AND completion_date >= ?",
        (event_id, date_str)).fetchall()
    for (d,) in later:
        _move_completion(cursor, event_id, new_id, d)
    conn.commit()
    conn.close()
    return new_id


def _event_occurs_on(ev: dict, target_date: date) -> bool:
    try:
        start_d = date.fromisoformat(ev["event_date"])
    except ValueError:
        return False
    if target_date < start_d:
        return False
    if ev["recurrence_end"] and target_date.isoformat() > ev["recurrence_end"]:
        return False
    rec = ev["recurrence"]
    if rec == "none":
        return start_d == target_date
    if rec == "daily":
        return True
    if rec == "weekdays":
        return target_date.weekday() < 5
    if rec == "weekly":
        return start_d.weekday() == target_date.weekday()
    # an event on the 31st falls on the last day of shorter months
    last_day = _calendar.monthrange(target_date.year, target_date.month)[1]
    if rec == "monthly":
        return target_date.day == min(start_d.day, last_day)
    if rec == "yearly":
        return target_date.month == start_d.month and target_date.day == min(start_d.day, last_day)
    return False


def _occurrence_sort_key(ev: dict):
    return (not ev["all_day"], ev["start_hour"], ev["start_minute"], ev["title"].lower())


def get_events_between(start_date: date, end_date: date):
    """{date: [occurrence, ...]} for every day in the range (all-day first, then by start time).

    Each occurrence is an event dict (see EVENT_FIELDS) plus "date" (YYYY-MM-DD of that occurrence).
    """
    start_str, end_str = start_date.isoformat(), end_date.isoformat()
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT {', '.join(EVENT_FIELDS)} FROM calendar_events
        WHERE active = 1 AND event_date <= ?
          AND (COALESCE(recurrence_end, '') = '' OR recurrence_end >= ?)
    """, (end_str, start_str)).fetchall()
    skipped = set(conn.execute(
        "SELECT event_id, exception_date FROM event_exceptions WHERE exception_date BETWEEN ? AND ?",
        (start_str, end_str)).fetchall())
    conn.close()

    events = [_event_from_row(r) for r in rows]
    result = {}
    for ordinal in range(start_date.toordinal(), end_date.toordinal() + 1):
        day = date.fromordinal(ordinal)
        day_str = day.isoformat()
        result[day] = sorted(
            (dict(ev, date=day_str) for ev in events
             if (ev["id"], day_str) not in skipped and _event_occurs_on(ev, day)),
            key=_occurrence_sort_key,
        )
    return result


def get_events_for_date(target_date: date):
    return get_events_between(target_date, target_date)[target_date]


def occurrence_start(occ: dict) -> datetime:
    d = date.fromisoformat(occ["date"])
    if occ["all_day"]:
        return datetime(d.year, d.month, d.day)
    return datetime(d.year, d.month, d.day, occ["start_hour"], occ["start_minute"])


def occurrence_end(occ: dict) -> datetime:
    if occ["all_day"]:
        return occurrence_start(occ) + timedelta(days=1)
    return occurrence_start(occ) + timedelta(minutes=max(occ["duration_min"], 0))


def reminder_time(occ: dict):
    """When the reminder for this occurrence should fire, or None."""
    minutes = occ["reminder_min"]
    if minutes < 0:
        return None
    if occ["all_day"]:
        base = occurrence_start(occ) + timedelta(hours=ALL_DAY_REMINDER_HOUR)
        return base - timedelta(days=minutes // 1440)
    return occurrence_start(occ) - timedelta(minutes=minutes)


def get_completed_events(start_str: str, end_str: str):
    """Set of (event_id, 'YYYY-MM-DD') completed within the date range."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT event_id, completion_date FROM event_completions WHERE completion_date BETWEEN ? AND ?",
        (start_str, end_str),
    ).fetchall()
    conn.close()
    return set(rows)


def toggle_event_completion(event_id: int, date_str: str):
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


def is_event_completed(event_id: int, date_str: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM event_completions WHERE event_id = ? AND completion_date = ?", (event_id, date_str))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_upcoming_events(limit=3, days=14, now=None):
    """Next not-completed occurrences that have not started yet (today's all-day events included)."""
    now = now or datetime.now()
    today = now.date()
    last = today + timedelta(days=days - 1)
    events_by_day = get_events_between(today, last)
    completed = get_completed_events(today.isoformat(), last.isoformat())

    upcoming = []
    for day in sorted(events_by_day):
        for occ in events_by_day[day]:
            if (occ["id"], occ["date"]) in completed:
                continue
            if not occ["all_day"] and occurrence_start(occ) < now:
                continue
            upcoming.append(occ)
            if len(upcoming) >= limit:
                return upcoming
    return upcoming

def export_to_csv():
    desktop_dir = _desktop_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = desktop_dir / f"gamification_export_{timestamp}.csv"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.name, a.category, a.is_negative, l.year, l.week_number, l.day_of_week, l.status, l.score
        FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        ORDER BY l.year DESC, l.week_number DESC, l.day_of_week ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Activity", "Category", "Is_Bad_Habit", "Year", "Week", "Day", "Status", "Score"])
        for r in rows:
            day_str = day_labels[r[5]] if 0 <= r[5] < 7 else str(r[5])
            writer.writerow([r[0], r[1], "Yes" if r[2] else "No", r[3], r[4], day_str, r[6], r[7]])

    return str(file_path)

def parse_flexible_date(date_str: str):
    if not date_str or not date_str.strip():
        return None
    clean = date_str.strip().replace("/", "-")
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


# --- Documents: a lean expiration tracker (number/notes optional and encrypted) ---
# category -> [(doc_type, default warn days, renews every year)]
DOC_TYPES = {
    "Identity": [("RG / CIN", 60, False), ("CNH", 60, False), ("Passaporte", 180, False),
                 ("Título de Eleitor", 30, False)],
    "Vehicle": [("CRLV / Licenciamento", 30, True), ("IPVA", 30, True), ("Seguro auto", 30, True)],
    "Home": [("IPTU", 30, True), ("Seguro residencial", 30, True), ("Contrato de aluguel", 60, False)],
    "Health": [("Plano de saúde", 30, True), ("Exame / Vacina", 30, False)],
    "Other": [("Outro", 30, False)],
}
DOC_FIELDS = ("id", "title", "doc_type", "category", "expiration_date", "warn_days", "annual",
              "number", "notes", "quest_id", "quest_for", "notified_stage", "created_at")
_EDITABLE_DOC_FIELDS = {"title", "doc_type", "category", "expiration_date", "warn_days", "annual", "number", "notes"}
SETTING_DOC_PIN = "doc_pin_hash"
SETTING_DOC_QUESTS = "doc_renewal_quests"  # "true" / "false"


def doc_type_defaults(doc_type: str):
    """(category, warn_days, annual) for a preset type; sensible defaults otherwise."""
    for category, types in DOC_TYPES.items():
        for name, warn, annual in types:
            if name == doc_type:
                return category, warn, annual
    return "Other", 30, False


def doc_status(doc: dict, today: date = None):
    """('expired' | 'soon' | 'ok', days_left, warn_start date)."""
    today = today or date.today()
    exp = date.fromisoformat(doc["expiration_date"])
    days = (exp - today).days
    warn_start = exp - timedelta(days=max(0, doc["warn_days"] or 0))
    if days < 0:
        return "expired", days, warn_start
    if today >= warn_start:
        return "soon", days, warn_start
    return "ok", days, warn_start


def _doc_from_row(row, today=None):
    d = dict(zip(DOC_FIELDS, row))
    d["annual"] = bool(d["annual"])
    d["warn_days"] = d["warn_days"] or 0
    d["has_number"] = bool(d["number"])
    d["has_notes"] = bool(d["notes"])
    del d["number"], d["notes"]  # secrets only via get_doc_secrets()
    d["status"], d["days_left"], warn_start = doc_status(d, today)
    d["warn_start"] = warn_start.isoformat()
    return d


def get_tracked_docs(today: date = None):
    """Documents sorted by urgency (expired, soon, ok; then by date). Secrets are not included."""
    conn = get_connection()
    rows = conn.execute(f"SELECT {', '.join(DOC_FIELDS)} FROM tracked_documents").fetchall()
    conn.close()
    docs = [_doc_from_row(r, today) for r in rows]
    order = {"expired": 0, "soon": 1, "ok": 2}
    docs.sort(key=lambda d: (order[d["status"]], d["expiration_date"], d["title"].lower()))
    return docs


def get_tracked_doc(doc_id: int, today: date = None):
    return next((d for d in get_tracked_docs(today) if d["id"] == doc_id), None)


def get_doc_secrets(doc_id: int):
    """Decrypted (number, notes) — the UI only calls this when the documents are unlocked."""
    conn = get_connection()
    row = conn.execute("SELECT number, notes FROM tracked_documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        return "", ""
    return secure.decrypt(row[0] or ""), secure.decrypt(row[1] or "")


def add_tracked_doc(title: str, doc_type: str, expiration_date: str, category: str = None, warn_days: int = None,
                    annual: bool = None, number: str = "", notes: str = "") -> int:
    cat, warn, ann = doc_type_defaults(doc_type)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tracked_documents (title, doc_type, category, expiration_date, warn_days, annual, number, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, doc_type, category or cat, expiration_date, warn if warn_days is None else warn_days,
          int(ann if annual is None else annual), secure.encrypt(number.strip()), secure.encrypt(notes.strip())))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def update_tracked_doc(doc_id: int, **fields):
    unknown = set(fields) - _EDITABLE_DOC_FIELDS
    if unknown:
        raise ValueError(f"Unknown document fields: {sorted(unknown)}")
    if not fields:
        return
    for key in ("number", "notes"):
        if key in fields:
            fields[key] = secure.encrypt((fields[key] or "").strip())
    if "annual" in fields:
        fields["annual"] = int(bool(fields["annual"]))
    if "expiration_date" in fields:
        fields["notified_stage"] = ""  # a new date restarts the reminders (fields were validated above)
    conn = get_connection()
    conn.execute(f"UPDATE tracked_documents SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                 (*fields.values(), doc_id))
    conn.commit()
    conn.close()


def delete_tracked_doc(doc_id: int):
    """Removes the document and its history for good (nothing sensitive is left behind)."""
    conn = get_connection()
    conn.execute("DELETE FROM tracked_documents WHERE id = ?", (doc_id,))
    conn.execute("DELETE FROM doc_renewals WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()


def get_doc_renewals(doc_id: int):
    conn = get_connection()
    rows = conn.execute("SELECT renewed_on, old_expiration, new_expiration FROM doc_renewals "
                        "WHERE doc_id = ? ORDER BY renewed_on DESC, id DESC", (doc_id,)).fetchall()
    conn.close()
    return [{"renewed_on": r[0], "old_expiration": r[1], "new_expiration": r[2]} for r in rows]


def suggested_renewal_date(doc: dict) -> date:
    """Annual items move one year ahead; others keep the old date as a starting point for editing."""
    exp = date.fromisoformat(doc["expiration_date"])
    if doc["annual"]:
        try:
            return exp.replace(year=exp.year + 1)
        except ValueError:  # 29 Feb
            return exp.replace(year=exp.year + 1, day=28)
    return exp


def renew_doc(doc_id: int, new_expiration: str, on: date = None) -> float:
    """Records a renewal, moves the expiration date and completes the linked renewal quest (its XP)."""
    on = on or date.today()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT expiration_date, quest_id FROM tracked_documents WHERE id = ?",
                         (doc_id,)).fetchone()
    if not row:
        conn.close()
        return 0.0
    cursor.execute("INSERT INTO doc_renewals (doc_id, renewed_on, old_expiration, new_expiration) VALUES (?, ?, ?, ?)",
                   (doc_id, on.isoformat(), row[0], new_expiration))
    cursor.execute("UPDATE tracked_documents SET expiration_date = ?, notified_stage = '', quest_id = NULL "
                   "WHERE id = ?", (new_expiration, doc_id))
    conn.commit()
    conn.close()
    xp = 0.0
    if row[1]:
        quest = get_quest(row[1], on=on)
        if quest and quest["status"] != "Complete":
            xp = complete_quest(row[1], on=on)
    return xp


def renewal_quests_enabled() -> bool:
    return get_hud_settings().get(SETTING_DOC_QUESTS, "true") == "true"


def sync_renewal_quests(today: date = None):
    """Creates one renewal quest per document entering its warning window (once per expiration date)."""
    if not renewal_quests_enabled():
        return []
    today = today or date.today()
    created = []
    for doc in get_tracked_docs(today):
        if doc["status"] == "ok" or doc["quest_for"] == doc["expiration_date"]:
            continue
        exp = date.fromisoformat(doc["expiration_date"])
        quest_id = add_quest(
            f"Renew {doc['title']}", quest_type="Side", difficulty="Normal",
            notes=f"Created automatically: {doc['title']} ({doc['doc_type']}) expires on {exp:%d/%m/%Y}.",
            next_step=f"Check what's needed to renew {doc['doc_type']}",
            subquests=[f"Check what's needed to renew {doc['doc_type']}", f"Renew {doc['doc_type']}",
                       "Press 'Renewed' in Documents with the new date"])
        conn = get_connection()
        conn.execute("UPDATE tracked_documents SET quest_id = ?, quest_for = ? WHERE id = ?",
                     (quest_id, doc["expiration_date"], doc["id"]))
        conn.commit()
        conn.close()
        created.append(quest_id)
    return created


def doc_notification_stage(doc: dict):
    """Reminder milestones: 'window' (warning starts), 'week' (7 days left), 'due' (expires today/expired)."""
    if doc["status"] == "ok":
        return None
    if doc["days_left"] <= 0:
        return "due"
    if doc["days_left"] <= 7:
        return "week"
    return "window"


def get_doc_notifications(today: date = None):
    """[(doc, stage)] whose milestone has not been notified yet (at most 3 reminders per cycle)."""
    return [(d, s) for d in get_tracked_docs(today)
            for s in [doc_notification_stage(d)] if s and s != (d["notified_stage"] or "")]


def mark_doc_notified(doc_id: int, stage: str):
    conn = get_connection()
    conn.execute("UPDATE tracked_documents SET notified_stage = ? WHERE id = ?", (stage, doc_id))
    conn.commit()
    conn.close()


def get_docs_for_calendar(start: date, end: date, today: date = None):
    """{date: [doc + "kind"]}: 'due' on the expiration date, 'warn' when the warning starts;
    expired documents also show on today."""
    today = today or date.today()
    out = {}
    for doc in get_tracked_docs(today):
        exp = date.fromisoformat(doc["expiration_date"])
        warn = date.fromisoformat(doc["warn_start"])
        if start <= exp <= end:
            out.setdefault(exp, []).append(dict(doc, kind="due"))
        if warn != exp and start <= warn <= end:
            out.setdefault(warn, []).append(dict(doc, kind="warn"))
        if doc["status"] == "expired" and start <= today <= end and exp != today:
            out.setdefault(today, []).append(dict(doc, kind="expired"))
    return out


def get_expiring_documents(days_ahead: int = None, today: date = None):
    """Documents needing attention (warning window or expired): [(title, doc_type, exp_date, days_left)]."""
    return [(d["title"], d["doc_type"], date.fromisoformat(d["expiration_date"]), d["days_left"])
            for d in get_tracked_docs(today) if d["status"] != "ok"]


# --- Documents PIN (an app-level privacy screen; the data itself is encrypted by secure.py) ---
def _hash_pin(pin: str, salt: bytes) -> str:
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000).hex()


def has_doc_pin() -> bool:
    return bool(get_hud_settings().get(SETTING_DOC_PIN))


def set_doc_pin(pin: str):
    salt = os.urandom(16)
    set_hud_setting(SETTING_DOC_PIN, f"{salt.hex()}${_hash_pin(pin, salt)}")


def check_doc_pin(pin: str) -> bool:
    import hmac
    stored = get_hud_settings().get(SETTING_DOC_PIN) or ""
    if "$" not in stored:
        return not stored
    salt_hex, digest = stored.split("$", 1)
    return hmac.compare_digest(_hash_pin(pin or "", bytes.fromhex(salt_hex)), digest)


def remove_doc_pin():
    set_hud_setting(SETTING_DOC_PIN, "")


def reset_doc_pin_and_wipe_secrets():
    """Forgotten PIN: removes the PIN *and* every saved number/note (dates and names stay)."""
    conn = get_connection()
    conn.execute("UPDATE tracked_documents SET number = '', notes = ''")
    conn.commit()
    conn.close()
    remove_doc_pin()


# --- Old-format documents (personal_documents): import the safe fields, then delete for good ---
_LEGACY_CATEGORY = {"Identity": "Identity", "Vehicles": "Vehicle", "Housing & Finance": "Home", "Other": "Other"}


def count_legacy_documents() -> int:
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM personal_documents").fetchone()[0]
    conn.close()
    return n


def remove_legacy_documents(import_safe_fields: bool) -> int:
    """Optionally imports title/type/category/expiration (never numbers or notes), then deletes every
    old-format row permanently. Returns how many documents were imported."""
    conn = get_connection()
    rows = conn.execute("SELECT title, doc_type, category, expiration_date FROM personal_documents "
                        "WHERE active = 1").fetchall()
    conn.close()
    imported = 0
    if import_safe_fields:
        for title, doc_type, category, exp in rows:
            exp_d = parse_flexible_date(exp or "")
            if not exp_d:
                continue  # nothing to track without an expiration date
            _, warn, annual = doc_type_defaults(doc_type)
            add_tracked_doc(title, doc_type, exp_d.isoformat(), category=_LEGACY_CATEGORY.get(category, "Other"),
                            warn_days=180 if "passap" in (doc_type or "").lower() else warn, annual=annual)
            imported += 1
    conn = get_connection()
    conn.execute("DELETE FROM personal_documents")
    conn.commit()
    conn.execute("VACUUM")  # so the deleted encrypted values don't linger in free pages
    conn.close()
    return imported

# --- Automatic daily backup with rotation ---
def backup_db(keep: int = 14):
    """Creates one consistent backup per day. Set GAMIFICATION_BACKUP_DIR to also
    copy it to another folder (e.g. OneDrive / Google Drive)."""
    src = Path(get_db_path())
    if not src.exists():
        return None

    dst_dir = src.parent / "backups"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"gamification_{date.today():%Y%m%d}.db"
    if dst.exists():
        return str(dst)

    tmp = dst.with_suffix(".tmp")
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(tmp))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    tmp.replace(dst)

    for old in sorted(dst_dir.glob("gamification_*.db"))[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass

    extra = os.getenv("GAMIFICATION_BACKUP_DIR")
    if extra and Path(extra).is_dir():
        try:
            shutil.copy2(dst, Path(extra) / dst.name)
        except OSError:
            pass
    return str(dst)

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
    #    (skipped, not fatal, if the key is unavailable: retried on the next start)
    if secure.AVAILABLE:
        try:
            for doc_id, num, sec, notes, extra in conn.execute(
                "SELECT id, doc_number, secondary_info, notes, extra_fields FROM personal_documents"
            ).fetchall():
                new = [secure.encrypt(v) for v in (num, sec, notes, extra)]
                if new != [num, sec, notes, extra]:
                    conn.execute(
                        "UPDATE personal_documents SET doc_number = ?, secondary_info = ?, notes = ?, "
                        "extra_fields = ? WHERE id = ?", (*new, doc_id))
        except RuntimeError:
            logging.getLogger("gamification").exception("Document encryption migration skipped")


def _run_calendar_migrations(conn):
    """Calendar overhaul: minutes, duration, all-day, colors, notes, reminders, series end, exceptions."""
    cols = {info[1] for info in conn.execute("PRAGMA table_info(calendar_events)")}
    for name, ddl in (
        ("start_minute", "INTEGER DEFAULT 0"),
        ("duration_min", "INTEGER DEFAULT 60"),
        ("all_day", "INTEGER DEFAULT 0"),
        ("color", "TEXT DEFAULT 'Cyan'"),
        ("notes", "TEXT DEFAULT ''"),
        ("reminder_min", "INTEGER DEFAULT 15"),
        ("recurrence_end", "TEXT DEFAULT ''"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE calendar_events ADD COLUMN {name} {ddl}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            exception_date TEXT NOT NULL,
            UNIQUE(event_id, exception_date)
        )
    """)


def _run_study_migrations(conn):
    """Study overhaul: stages, journal, next step and spaced-repetition reviews."""
    cols = {info[1] for info in conn.execute("PRAGMA table_info(study_sessions)")}
    for name, ddl in (
        ("needs_review", "INTEGER DEFAULT 1"),
        ("next_step", "TEXT DEFAULT ''"),
        ("mastered_at", "TEXT DEFAULT ''"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE study_sessions ADD COLUMN {name} {ddl}")
    conn.execute("UPDATE study_sessions SET status = 'Studying' WHERE status = 'In Progress'")
    conn.execute("""
        UPDATE study_sessions SET mastered_at = COALESCE(date(updated_at), date('now', 'localtime'))
        WHERE status = 'Mastered' AND COALESCE(mastered_at, '') = ''
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            minutes INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            next_step TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_ai_packs (
            session_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            content TEXT,
            model TEXT DEFAULT '',
            error TEXT DEFAULT '',
            attempts INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            review_no INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            done_date TEXT DEFAULT '',
            remembered INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _run_quest_migrations(conn):
    """Quest overhaul: types, difficulty, repeats, measurable targets, checkbox subquests, log."""
    cols = {info[1] for info in conn.execute("PRAGMA table_info(tasks)")}
    for name, ddl in (
        ("quest_type", "TEXT DEFAULT 'Main'"),
        ("difficulty", "TEXT DEFAULT 'Normal'"),
        ("repeat", "TEXT DEFAULT 'none'"),
        ("metric_unit", "TEXT DEFAULT ''"),
        ("metric_start", "REAL"),
        ("metric_target", "REAL"),
        ("next_step", "TEXT DEFAULT ''"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {ddl}")
    # the old 5-step stages collapse to Active; completed quests stay in the Hall of Fame
    conn.execute("UPDATE tasks SET status = 'Active' WHERE status NOT IN ('Active', 'On hold', 'Complete')")
    sub_cols = {info[1] for info in conn.execute("PRAGMA table_info(subtasks)")}
    if "done_key" not in sub_cols:
        conn.execute("ALTER TABLE subtasks ADD COLUMN done_key TEXT DEFAULT ''")
        conn.execute("UPDATE subtasks SET done_key = 'done' WHERE status = 'Complete'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            text TEXT DEFAULT '',
            value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quest_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            period_key TEXT NOT NULL,
            completed_on TEXT NOT NULL,
            xp REAL DEFAULT 0,
            UNIQUE(task_id, period_key)
        )
    """)


def _run_document_migrations(conn):
    """Documents overhaul: a lean tracker table + renewal history (old rows are removed from the UI)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracked_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            category TEXT DEFAULT 'Other',
            expiration_date TEXT NOT NULL,
            warn_days INTEGER DEFAULT 30,
            annual INTEGER DEFAULT 0,
            number TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            quest_id INTEGER,
            quest_for TEXT DEFAULT '',
            notified_stage TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_renewals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            renewed_on TEXT NOT NULL,
            old_expiration TEXT,
            new_expiration TEXT
        )
    """)


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
