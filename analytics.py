"""Read-only analytics for the Graphs tab: everything is computed for a period (and the previous one)."""
from datetime import date, timedelta

import database as db
from constants import SCORE_PASSING, DAY_NAMES

# key -> (label, number of days)
PERIODS = {
    "7d": ("Last 7 days", 7),
    "30d": ("Last 30 days", 30),
    "12w": ("Last 12 weeks", 84),
    "1y": ("Last 12 months", 365),
}


def period_bounds(key: str, today: date = None):
    """(start, end, prev_start, prev_end) — the period ends today; the previous one is right before it."""
    today = today or date.today()
    n = PERIODS[key][1]
    start = today - timedelta(days=n - 1)
    prev_end = start - timedelta(days=1)
    return start, today, prev_end - timedelta(days=n - 1), prev_end


def uses_weeks(key: str) -> bool:
    """Long periods are drawn per week (84 / 365 columns would be unreadable)."""
    return key in ("12w", "1y")


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _days(start: date, end: date):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


# ------------------------------------------------------------------ habit logs
def habit_logs(start: date, end: date):
    """[(activity_id, name, is_negative, date, status, score)] for active habits with a score."""
    years = sorted({start.isocalendar()[0], end.isocalendar()[0], start.year, end.year})
    conn = db.get_connection()
    rows = conn.execute(f"""
        SELECT l.activity_id, a.name, a.is_negative, l.year, l.week_number, l.day_of_week, l.status, l.score
        FROM daily_logs l JOIN activities a ON a.id = l.activity_id
        WHERE a.active = 1 AND l.score IS NOT NULL AND l.year BETWEEN ? AND ?
    """, (years[0], years[-1])).fetchall()
    conn.close()
    out = []
    for aid, name, neg, y, w, d, status, score in rows:
        try:
            day = date.fromisocalendar(y, w, d + 1)
        except ValueError:
            continue
        if start <= day <= end:
            out.append((aid, name, bool(neg), day, status, score))
    return out


def daily_scores(start: date, end: date):
    """{date: average score} for days with at least one answer."""
    per_day = {}
    for _, _, _, day, _, score in habit_logs(start, end):
        per_day.setdefault(day, []).append(score)
    return {d: sum(v) / len(v) for d, v in per_day.items()}


def score_series(key: str, today: date = None):
    """[(label, date, value or None)] — daily for short periods, weekly averages for long ones."""
    start, end, _, _ = period_bounds(key, today)
    scores = daily_scores(start, end)
    if not uses_weeks(key):
        return [(f"{d:%d/%m}", d, scores.get(d)) for d in _days(start, end)]
    series = []
    wk = monday(start)
    while wk <= end:
        vals = [v for d, v in scores.items() if wk <= d <= wk + timedelta(days=6)]
        series.append((f"{wk:%d/%m}", wk, sum(vals) / len(vals) if vals else None))
        wk += timedelta(days=7)
    return series


def habit_matrix(key: str, today: date = None):
    """(columns, rows) for the habit heatmap.

    columns: [(label, first_day, last_day)] — days (7d/30d) or weeks (12w/1y)
    rows:    [(name, is_negative, [value or None per column], [status or None per column])]
    """
    start, end, _, _ = period_bounds(key, today)
    if uses_weeks(key):
        columns, wk = [], monday(start)
        while wk <= end:
            columns.append((f"{wk:%d/%m}", max(wk, start), min(wk + timedelta(days=6), end)))
            wk += timedelta(days=7)
    else:
        columns = [(DAY_NAMES[d.weekday()][0] if key == "7d" else f"{d.day}", d, d) for d in _days(start, end)]
    logs = habit_logs(start, end)
    rows = []
    for aid, name, _, neg in db.get_activities():
        values, statuses = [], []
        for _, first, last in columns:
            cell = [(score, status) for a, _, _, d, status, score in logs if a == aid and first <= d <= last]
            values.append(sum(s for s, _ in cell) / len(cell) if cell else None)
            statuses.append(cell[0][1] if len(cell) == 1 else (f"{len(cell)} days" if cell else None))
        rows.append((name, bool(neg), values, statuses))
    return columns, rows


def habit_ranking(key: str, today: date = None):
    """[(name, is_negative, average, days_logged, days_in_period)], strongest first."""
    start, end, _, _ = period_bounds(key, today)
    total = (end - start).days + 1
    per = {}
    for aid, name, neg, _, _, score in habit_logs(start, end):
        per.setdefault((aid, name, neg), []).append(score)
    ranking = [(name, neg, sum(v) / len(v), len(v), total) for (aid, name, neg), v in per.items()]
    ranking.sort(key=lambda r: (-r[2], -r[3], r[0].lower()))
    return ranking


def weekday_pattern(key: str, today: date = None):
    """[(day name, average or None, days counted)] Monday..Sunday."""
    start, end, _, _ = period_bounds(key, today)
    per = {i: [] for i in range(7)}
    for d, v in daily_scores(start, end).items():
        per[d.weekday()].append(v)
    return [(DAY_NAMES[i], sum(v) / len(v) if v else None, len(v)) for i, v in per.items()]


def year_map(today: date = None):
    """53 weeks × 7 days ending this week: [[(date, average or None, in_future)] per week]."""
    today = today or date.today()
    first = monday(today) - timedelta(weeks=52)
    scores = daily_scores(first, today)
    weeks = []
    for w in range(53):
        wk = first + timedelta(weeks=w)
        weeks.append([(wk + timedelta(days=i), scores.get(wk + timedelta(days=i)), wk + timedelta(days=i) > today)
                      for i in range(7)])
    return weeks


# ------------------------------------------------------------------ headline numbers
def _best_streak(scores: dict, start: date, end: date) -> int:
    best = run = 0
    for d in _days(start, end):
        if scores.get(d, 0) >= SCORE_PASSING:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def _sum_ledger(start: date, end: date) -> float:
    conn = db.get_connection()
    xp = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE event_date BETWEEN ? AND ?",
                      (start.isoformat(), end.isoformat())).fetchone()[0]
    conn.close()
    return float(xp)


def _study_minutes(start: date, end: date) -> int:
    conn = db.get_connection()
    m = conn.execute("""
        SELECT COALESCE(SUM(j.minutes), 0) FROM study_journal j JOIN study_sessions s ON s.id = j.session_id
        WHERE s.active = 1 AND j.entry_date BETWEEN ? AND ?
    """, (start.isoformat(), end.isoformat())).fetchone()[0]
    conn.close()
    return int(m)


def _summary(start: date, end: date):
    scores = daily_scores(start, end)
    return {
        "avg_score": sum(scores.values()) / len(scores) if scores else None,
        "days_logged": len(scores),
        "days_total": (end - start).days + 1,
        "xp": _sum_ledger(start, end),
        "best_streak": _best_streak(scores, start, end),
        "study_minutes": _study_minutes(start, end),
    }


def kpis(key: str, today: date = None):
    """{"current": {...}, "previous": {...}} with avg_score, days_logged, days_total, xp, best_streak,
    study_minutes."""
    start, end, prev_start, prev_end = period_bounds(key, today)
    return {"current": _summary(start, end), "previous": _summary(prev_start, prev_end)}


# ------------------------------------------------------------------ weekly series
def weekly_series(key: str, today: date = None):
    """Per week overlapping the period: [{"week": monday, "label", "xp", "study_minutes", "reviews", "quests"}]."""
    start, end, _, _ = period_bounds(key, today)
    first = monday(start)
    weeks = []
    wk = first
    while wk <= end:
        weeks.append({"week": wk, "label": f"{wk:%d/%m}", "xp": 0.0, "study_minutes": 0, "reviews": 0, "quests": 0})
        wk += timedelta(days=7)
    index = {w["week"]: w for w in weeks}

    def add(day_iso, field, amount):
        try:
            d = date.fromisoformat((day_iso or "")[:10])
        except ValueError:
            return
        w = index.get(monday(d))
        if w is not None and first <= d <= end:
            w[field] += amount

    conn = db.get_connection()
    lo, hi = first.isoformat(), end.isoformat()
    for d, amount in conn.execute("SELECT event_date, amount FROM xp_ledger WHERE event_date BETWEEN ? AND ?", (lo, hi)):
        add(d, "xp", amount)
    for d, m in conn.execute("""SELECT j.entry_date, j.minutes FROM study_journal j
                                JOIN study_sessions s ON s.id = j.session_id
                                WHERE s.active = 1 AND j.entry_date BETWEEN ? AND ?""", (lo, hi)):
        add(d, "study_minutes", m or 0)
    for (d,) in conn.execute("SELECT done_date FROM study_reviews WHERE done_date != '' AND done_date BETWEEN ? AND ?",
                             (lo, hi)):
        add(d, "reviews", 1)
    for (d,) in conn.execute("""SELECT substr(completed_at, 1, 10) FROM tasks
                                WHERE active = 1 AND status = 'Complete' AND completed_at IS NOT NULL
                                  AND substr(completed_at, 1, 10) BETWEEN ? AND ?""", (lo, hi)):
        add(d, "quests", 1)
    for (d,) in conn.execute("""SELECT c.completed_on FROM quest_completions c JOIN tasks t ON t.id = c.task_id
                                WHERE t.active = 1 AND c.completed_on BETWEEN ? AND ?""", (lo, hi)):
        add(d, "quests", 1)
    conn.close()
    return weeks
