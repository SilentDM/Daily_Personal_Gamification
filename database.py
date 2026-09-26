import sqlite3
import os
import csv
from pathlib import Path
from datetime import datetime, date
from constants import get_rank_title

def get_db_path():
    app_data = os.getenv("APPDATA")
    if app_data:
        base_dir = Path(app_data) / "Daily_Personal_Gamification"
    else:
        base_dir = Path.home() / ".daily_personal_gamification"
        
    base_dir.mkdir(parents=True, exist_ok=True)
    return str(base_dir / "gamification.db")

def get_connection():
    return sqlite3.connect(get_db_path())

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
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
        SELECT id FROM daily_logs 
        WHERE activity_id = ? AND year = ? AND week_number = ? AND day_of_week = ?
    """, (activity_id, year, week, day_idx))
    row = cursor.fetchone()
    
    if row:
        cursor.execute("UPDATE daily_logs SET status = ?, score = ? WHERE id = ?", (status, score, row[0]))
    else:
        cursor.execute("""
            INSERT INTO daily_logs (activity_id, year, week_number, day_of_week, status, score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (activity_id, year, week, day_idx, status, score))
        
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
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Daily habit averages net XP: (Daily_Avg - 5.0) * 2.0
    cursor.execute("""
        SELECT l.year, l.week_number, l.day_of_week, AVG(l.score)
        FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.score IS NOT NULL
        GROUP BY l.year, l.week_number, l.day_of_week
    """)
    day_rows = cursor.fetchall()
    
    net_habit_xp = 0.0
    for y, w, d, avg in day_rows:
        daily_delta = (avg - 5.0) * 2.0
        net_habit_xp += daily_delta

    # 2. Completed Quests (+15 XP each)
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Complete' AND active = 1")
    quest_xp = (cursor.fetchone()[0] or 0) * 15.0

    # 3. Mastered Studies (+15 XP each)
    cursor.execute("SELECT COUNT(*) FROM study_sessions WHERE status = 'Mastered' AND active = 1")
    study_xp = (cursor.fetchone()[0] or 0) * 15.0
    
    # 4. Completed Calendar Events (+10 XP each)
    cursor.execute("SELECT COUNT(*) FROM event_completions WHERE completed = 1")
    event_xp = (cursor.fetchone()[0] or 0) * 10.0

    # 5. Incremental Quest Note Progress (+2 XP per working session)
    cursor.execute("SELECT SUM(xp_awarded) FROM quest_progress_logs")
    note_progress_xp = (cursor.fetchone()[0] or 0.0)

    # Total discipline XP (0.0 to 1,000.0)
    total_xp = max(0.0, min(1000.0, net_habit_xp + quest_xp + study_xp + event_xp + note_progress_xp))

    if total_xp >= 1000.0:
        level = 100
        xp_in_level = 10.0
    else:
        level = max(1, int(total_xp // 10) + 1)
        xp_in_level = total_xp % 10.0

    rank_title = get_rank_title(level)
    conn.close()
    
    return total_xp, level, xp_in_level, rank_title

def get_current_streak():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.year, l.week_number, l.day_of_week, AVG(l.score)
        FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.score IS NOT NULL
        GROUP BY l.year, l.week_number, l.day_of_week
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return 0

    date_scores = {}
    for y, w, d, avg in rows:
        try:
            day_date = date.fromisocalendar(y, w, d + 1)
            date_scores[day_date] = avg
        except ValueError:
            continue

    today = date.today()
    streak = 0
    current_check = today

    if date_scores.get(today, 0) < 7.0:
        current_check = date.fromordinal(today.toordinal() - 1)

    while True:
        avg = date_scores.get(current_check, 0)
        if avg >= 7.0:
            streak += 1
            current_check = date.fromordinal(current_check.toordinal() - 1)
        else:
            break

    return streak

def get_past_weeks_scores(num_weeks=6):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.year, l.week_number, AVG(l.score)
        FROM daily_logs l
        JOIN activities a ON l.activity_id = a.id
        WHERE a.active = 1 AND l.score IS NOT NULL
        GROUP BY l.year, l.week_number
        ORDER BY l.year ASC, l.week_number ASC
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
        return

    total_weight = sum(SUBQUEST_WEIGHTS.get(s[2], 0.0) for s in subtasks)
    progress_pct = total_weight / len(subtasks)

    if progress_pct >= 99.9:
        update_task_status(task_id, "Complete", year, week)
    else:
        update_task_status(task_id, "In Progress", year, week)
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
    if status == "Complete":
        cursor.execute("""
            UPDATE tasks 
            SET status = ?, completed_year = ?, completed_week = ?, completed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (status, year, week, task_id))
    else:
        cursor.execute("""
            UPDATE tasks 
            SET status = ?, completed_year = NULL, completed_week = NULL, completed_at = NULL 
            WHERE id = ?
        """, (status, task_id))
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
    """Saves notes and awards +2.0 XP if content grew by at least 10 characters."""
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
        cursor.execute("""
            SELECT created_at FROM quest_progress_logs 
            WHERE task_id = ? 
            ORDER BY id DESC LIMIT 1
        """, (task_id,))
        last_log = cursor.fetchone()

        can_award = True
        if last_log and last_log[0]:
            try:
                last_time = datetime.strptime(last_log[0].split(".")[0], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_time).total_seconds() < 900:  # 15 min cooldown
                    can_award = False
            except Exception:
                can_award = True

        if can_award:
            xp_gained = 2.0
            cursor.execute("INSERT INTO quest_progress_logs (task_id, xp_awarded) VALUES (?, ?)", (task_id, xp_gained))

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
        SET topic = ?, source = ?, eli5 = ?, code_sandbox = ?, break_test = ?, recall_questions = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (topic, source, eli5, code_sandbox, break_test, recall_questions, status, session_id))
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

    matching_events = []
    for r in rows:
        eid, title, start_date_str, hour, rec = r
        start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        if rec == "none" and start_d == target_date:
            matching_events.append(r)
        elif rec == "weekly" and start_d.weekday() == target_date.weekday():
            matching_events.append(r)
        elif rec == "monthly" and start_d.day == target_date.day:
            matching_events.append(r)

    return matching_events

def toggle_event_completion(event_id: int, date_str: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM event_completions WHERE event_id = ? AND completion_date = ?", (event_id, date_str))
    row = cursor.fetchone()

    if row:
        cursor.execute("DELETE FROM event_completions WHERE id = ?", (row[0],))
        is_done = False
    else:
        cursor.execute("INSERT INTO event_completions (event_id, completion_date) VALUES (?, ?)", (event_id, date_str))
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
    desktop_dir = Path.home() / "Desktop"
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