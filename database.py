import sqlite3, os, csv, json, shutil
import calendar as _calendar
import secure
from pathlib import Path
from datetime import datetime, date
from constants import get_rank_title, XP_QUEST, XP_STUDY, XP_EVENT, XP_NOTE_PROGRESS, SCORE_PASSING

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

def delete_activity(activity_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE activities SET active = 0 WHERE id = ?", (activity_id,))
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

# --- Tasks / Quests Operations ---
# --- Subquest Definitions and Operations ---
SUBQUEST_WEIGHTS = {
    "Planning": 0.0,
    "Started": 25.0,
    "In Progress": 50.0,
    "Almost There": 75.0,
    "Complete": 100.0
}

def get_subtasks(task_id: int):
    """Fetches all active subquests for a given parent quest."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, status, sort_order 
        FROM subtasks 
        WHERE task_id = ? AND active = 1 
        ORDER BY sort_order ASC, id ASC
    """, (task_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_subtask(task_id: int, title: str, status: str = "Planning"):
    """Adds a new subquest to a main quest."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM subtasks WHERE task_id = ? AND active = 1", (task_id,))
    next_order = cursor.fetchone()[0]
    cursor.execute("""
        INSERT INTO subtasks (task_id, title, status, sort_order) 
        VALUES (?, ?, ?, ?)
    """, (task_id, title, status, next_order))
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()

    year, week, _ = get_current_week_info()
    recalculate_task_progress(task_id, year, week)
    return sub_id

def update_subtask_status(subtask_id: int, status: str):
    """Updates the status of a subquest and auto-recalculates parent progress."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id FROM subtasks WHERE id = ?", (subtask_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    task_id = row[0]
    cursor.execute("UPDATE subtasks SET status = ? WHERE id = ?", (status, subtask_id))
    conn.commit()
    conn.close()

    year, week, _ = get_current_week_info()
    recalculate_task_progress(task_id, year, week)

def delete_subtask(subtask_id: int):
    """Deactivates a subquest and updates parent progress."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id FROM subtasks WHERE id = ?", (subtask_id,))
    row = cursor.fetchone()
    if row:
        task_id = row[0]
        cursor.execute("UPDATE subtasks SET active = 0 WHERE id = ?", (subtask_id,))
        conn.commit()
        year, week, _ = get_current_week_info()
        recalculate_task_progress(task_id, year, week)
    conn.close()

def move_subtask(subtask_id: int, direction: str):
    """Moves a subquest up or down inside its parent quest."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id FROM subtasks WHERE id = ?", (subtask_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    task_id = row[0]
    cursor.execute("""
        SELECT id, sort_order 
        FROM subtasks 
        WHERE task_id = ? AND active = 1 
        ORDER BY sort_order ASC, id ASC
    """, (task_id,))
    rows = cursor.fetchall()

    idx = next((i for i, r in enumerate(rows) if r[0] == subtask_id), None)
    if idx is not None:
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap_idx < len(rows):
            curr_id, curr_order = rows[idx]
            target_id, target_order = rows[swap_idx]

            if curr_order == target_order:
                for i, r in enumerate(rows):
                    cursor.execute("UPDATE subtasks SET sort_order = ? WHERE id = ?", (i, r[0]))
                curr_order = idx
                target_order = swap_idx

            cursor.execute("UPDATE subtasks SET sort_order = ? WHERE id = ?", (target_order, curr_id))
            cursor.execute("UPDATE subtasks SET sort_order = ? WHERE id = ?", (curr_order, target_id))
            conn.commit()
    conn.close()

def recalculate_task_progress(task_id: int, year: int, week: int):
    """Automatically marks parent quest complete if all subquests are complete."""
    subtasks = get_subtasks(task_id)
    if not subtasks:
        update_task_status(task_id, "Planning", year, week)
        return

    total_weight = sum(SUBQUEST_WEIGHTS.get(s[2], 0.0) for s in subtasks)
    progress_pct = total_weight / len(subtasks)

    if progress_pct >= 99.9:
        update_task_status(task_id, "Complete", year, week)
    else:
        update_task_status(task_id, "In Progress" if progress_pct > 0 else "Planning", year, week)
def get_tasks():
    """
    Returns tasks with their subquests and calculated progress percentage.
    Format: (id, title, status, completed_year, completed_week, notes, subtasks, progress_pct)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, status, completed_year, completed_week, COALESCE(notes, '') 
        FROM tasks 
        WHERE active = 1 
        ORDER BY CASE WHEN status = 'Complete' THEN 1 ELSE 0 END ASC, sort_order ASC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        task_id = r[0]
        status = r[2]
        subtasks = get_subtasks(task_id)

        if subtasks:
            total_weight = sum(SUBQUEST_WEIGHTS.get(s[2], 0.0) for s in subtasks)
            progress_pct = total_weight / len(subtasks)
        else:
            progress_pct = 100.0 if status == "Complete" else 0.0

        result.append((r[0], r[1], r[2], r[3], r[4], r[5], subtasks, progress_pct))

    return result

def add_task(title: str, status: str = "Planning"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM tasks WHERE active = 1")
    next_order = cursor.fetchone()[0]
    cursor.execute("INSERT INTO tasks (title, status, sort_order) VALUES (?, ?, ?)", (title, status, next_order))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id: int, status: str, year: int, week: int):
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

def delete_task(task_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def move_task(task_id: int, direction: str):
    """Moves a quest up or down among non-completed tasks (or among completed)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sort_order, status 
        FROM tasks 
        WHERE active = 1 
        ORDER BY CASE WHEN status = 'Complete' THEN 1 ELSE 0 END ASC, sort_order ASC, id DESC
    """)
    rows = cursor.fetchall()
    
    idx = next((i for i, r in enumerate(rows) if r[0] == task_id), None)
    if idx is not None:
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap_idx < len(rows):
            curr_is_complete = (rows[idx][2] == "Complete")
            swap_is_complete = (rows[swap_idx][2] == "Complete")

            # Allows swapping between any active quests regardless of 'Started' vs 'Planning'
            if curr_is_complete == swap_is_complete:
                curr_id, curr_order, _ = rows[idx]
                target_id, target_order, _ = rows[swap_idx]

                if curr_order == target_order:
                    for i, r in enumerate(rows):
                        cursor.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (i, r[0]))
                    curr_order = idx
                    target_order = swap_idx

                cursor.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (target_order, curr_id))
                cursor.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (curr_order, target_id))
                conn.commit()
    conn.close()

def save_task_notes_with_progress(task_id: int, new_notes: str) -> float:
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

def get_weekly_completed_tasks_count(year: int, week: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE active = 1 AND status = 'Complete' AND completed_year = ? AND completed_week = ?
    """, (year, week))
    count = cursor.fetchone()[0] or 0
    conn.close()
    return count

# --- Study Sessions Operations ---
def get_study_sessions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, topic, source, eli5, code_sandbox, break_test, recall_questions, status, created_at 
        FROM study_sessions 
        WHERE active = 1 
        ORDER BY CASE WHEN status = 'In Progress' THEN 0 ELSE 1 END ASC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_study_session(topic: str, source: str = "FIAP"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO study_sessions (topic, source) VALUES (?, ?)", (topic, source))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def update_study_session(session_id: int, topic: str, source: str, eli5: str, code_sandbox: str, break_test: str, recall_questions: str, status: str):
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

def delete_study_session(session_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE study_sessions SET active = 0 WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

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
def add_calendar_event(title: str, event_date_str: str, start_hour: int, recurrence: str = "none"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO calendar_events (title, event_date, start_hour, recurrence)
        VALUES (?, ?, ?, ?)
    """, (title, event_date_str, start_hour, recurrence))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def delete_calendar_event(event_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE calendar_events SET active = 0 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def get_events_for_date(target_date: date):
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

def get_upcoming_events(limit=3):
    now = datetime.now()
    today = now.date()
    current_hour = now.hour
    upcoming = []

    for i in range(14):
        check_date = date.fromordinal(today.toordinal() + i)
        day_events = get_events_for_date(check_date)
        date_str = check_date.strftime("%Y-%m-%d")

        for ev in day_events:
            eid, title, _, start_hour, rec = ev
            if check_date == today and start_hour < current_hour:
                continue
            if is_event_completed(eid, date_str):
                continue
            upcoming.append((check_date, title, start_hour, rec))
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

def get_documents(category_filter: str = "All"):
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

def add_document(category: str, doc_type: str, title: str, doc_number: str, secondary_info: str = "", issue_date: str = "", expiration_date: str = "", notes: str = "", extra_fields: str = "[]"):
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

def update_document(doc_id: int, category: str, doc_type: str, title: str, doc_number: str, issue_date: str, expiration_date: str, notes: str, extra_fields: str = "[]", secondary_info=None):
    """secondary_info=None keeps the stored value (the editor does not show that field)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE personal_documents
        SET category = ?, doc_type = ?, title = ?, doc_number = ?,
            issue_date = ?, expiration_date = ?, notes = ?, extra_fields = ?
        WHERE id = ?
    """, (category, doc_type, title, secure.encrypt(doc_number),
          issue_date, expiration_date, secure.encrypt(notes), secure.encrypt(extra_fields), doc_id))
    if secondary_info is not None:
        cursor.execute("UPDATE personal_documents SET secondary_info = ? WHERE id = ?",
                       (secure.encrypt(secondary_info), doc_id))
    conn.commit()
    conn.close()

def delete_document(doc_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE personal_documents SET active = 0 WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

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

def get_expiring_documents(days_ahead: int = 60):
    """Returns active documents expiring within `days_ahead` days or already expired."""
    docs = get_documents("All")
    today = date.today()
    expiring = []

    for d in docs:
        doc_type = d[2]
        title = d[3]
        exp = d[7] if len(d) > 7 else ""

        if exp and exp.strip():
            exp_date = parse_flexible_date(exp)
            if exp_date:
                delta = (exp_date - today).days
                limit = 180 if ("passaporte" in doc_type.lower() or "passport" in doc_type.lower()) else days_ahead

                if delta <= limit:
                    expiring.append((title, doc_type, exp_date, delta))

    expiring.sort(key=lambda x: x[3])
    return expiring

# --- Manual quest status (quests without subquests) ---
def set_task_manual_status(task_id: int, complete: bool):
    """Completes / reopens a quest that has no subquests."""
    if get_subtasks(task_id):
        return  # progress is driven by the subquests
    year, week, _ = get_current_week_info()
    update_task_status(task_id, "Complete" if complete else "Planning", year, week)

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
