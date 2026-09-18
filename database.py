import sqlite3
import os
import csv
from pathlib import Path
from datetime import datetime, date

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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Routine',
            is_negative INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("PRAGMA table_info(activities)")
    cols = [info[1] for info in cursor.fetchall()]
    if "category" not in cols:
        cursor.execute("ALTER TABLE activities ADD COLUMN category TEXT DEFAULT 'Routine'")
    if "is_negative" not in cols:
        cursor.execute("ALTER TABLE activities ADD COLUMN is_negative INTEGER DEFAULT 0")

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

    # New To-Do / Quests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'Planning',
            completed_year INTEGER,
            completed_week INTEGER,
            completed_at TIMESTAMP,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def get_current_week_info():
    today = date.today()
    iso = today.isocalendar()
    return iso[0], iso[1], today.weekday()

def get_activities():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, category, is_negative FROM activities WHERE active = 1 ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_activity(name: str, category: str = "Routine", is_negative: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activities (name, category, is_negative) VALUES (?, ?, ?)",
        (name, category, 1 if is_negative else 0)
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

def save_log(activity_id: int, year: int, week: int, day_idx: int, status: str, score: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM daily_logs 
        WHERE activity_id = ? AND year = ? AND week_number = ? AND day_of_week = ?
    """, (activity_id, year, week, day_idx))
    row = cursor.fetchone()
    
    if row:
        cursor.execute("""
            UPDATE daily_logs SET status = ?, score = ? WHERE id = ?
        """, (status, score, row[0]))
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

# Gamification calculations (Including Quest XP Bonus!)
def get_user_xp_and_level():
    conn = get_connection()
    cursor = conn.cursor()
    # Habit score points
    cursor.execute("SELECT SUM(score) FROM daily_logs WHERE score IS NOT NULL")
    res = cursor.fetchone()[0] or 0
    habit_xp = res * 10
    
    # Completed quests bonus (+50 XP each)
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Complete' AND active = 1")
    completed_tasks = cursor.fetchone()[0] or 0
    quest_xp = completed_tasks * 50

    conn.close()
    
    total_xp = habit_xp + quest_xp
    level = (total_xp // 100) + 1
    xp_in_level = total_xp % 100
    return total_xp, level, xp_in_level

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

# --- Tasks / To-Do Database Operations ---
def get_tasks():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, status, completed_year, completed_week 
        FROM tasks 
        WHERE active = 1 
        ORDER BY CASE WHEN status = 'Complete' THEN 1 ELSE 0 END ASC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_task(title: str, status: str = "Planning"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, status) VALUES (?, ?)", (title, status))
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