"""Insight of the day: one short, supportive Gemini sentence based on recent habits, quests and studies.

One call per day at most (cached in hud_settings); generated in the background and shown on the HUD.
"""
import logging
import threading
from datetime import date, timedelta

from pydantic import BaseModel, Field

import ai_gemini
import database as db

log = logging.getLogger("gamification")

SETTING_TEXT = "insight_text"
SETTING_DATE = "insight_date"
SETTING_LANGUAGE = "ai_language"
OLD_SETTING_LANGUAGE = "insight_language"
LANGUAGES = ["Português (Brasil)", "English"]
MAX_CHARS = 220

_lock = threading.Lock()
_running = False


class Insight(BaseModel):
    text: str = Field(description="One or two short sentences (max ~180 characters): specific, kind, actionable")


SYSTEM = """You are a warm, perceptive coach for someone using a personal gamification app.
From their recent data, write ONE short insight for today (max ~180 characters):
- be specific (name a habit, quest or study topic), kind and encouraging; suggest one small next action;
- never guilt, never mention failure, deadlines or pressure; celebrate progress when there is some;
- no emojis, no greetings, no quotes from famous people.
Write in {language}."""


def language() -> str:
    settings = db.get_hud_settings()
    lang = settings.get(SETTING_LANGUAGE) or settings.get(OLD_SETTING_LANGUAGE) or LANGUAGES[0]
    return lang if lang in LANGUAGES else LANGUAGES[0]


def cached_today():
    """Today's insight text, or None."""
    settings = db.get_hud_settings()
    if settings.get(SETTING_DATE) == date.today().isoformat():
        return settings.get(SETTING_TEXT) or None
    return None


def build_context(today: date = None) -> str:
    today = today or date.today()
    lines = [f"TODAY: {today:%A %d/%m/%Y}", f"HABIT STREAK: {db.get_current_streak()} day(s)"]

    # habit averages over the last 7 days (most recent ISO weeks)
    conn = db.get_connection()
    start = today - timedelta(days=6)
    rows = conn.execute("""
        SELECT a.name, a.is_negative, l.year, l.week_number, l.day_of_week, l.score
        FROM daily_logs l JOIN activities a ON a.id = l.activity_id
        WHERE a.active = 1 AND l.score IS NOT NULL
    """).fetchall()
    conn.close()
    per_habit = {}
    for name, neg, y, w, d, score in rows:
        try:
            day = date.fromisocalendar(y, w, d + 1)
        except ValueError:
            continue
        if start <= day <= today:
            per_habit.setdefault((name, bool(neg)), []).append(score)
    if per_habit:
        lines.append("HABITS (last 7 days, average 0-10, number of days logged):")
        for (name, neg), scores in sorted(per_habit.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
            lines.append(f"- {name}{' (vice to avoid)' if neg else ''}: {sum(scores) / len(scores):.1f} "
                         f"({len(scores)} days)")

    quests = [q for q in db.get_quests(statuses=("Active",)) if not q["done_this_period"]][:5]
    if quests:
        lines.append("ACTIVE QUESTS:")
        for q in quests:
            extra = f", next step: {q['next_step']}" if q["next_step"] else ""
            lines.append(f"- {q['title']} ({int(q['progress_pct'])}%{extra})")
    studies = [s for s in db.get_study_sessions() if s["status"] in ("Studying", "Reviewing")][:3]
    if studies:
        lines.append("STUDYING:")
        lines += [f"- {s['topic']}" + (f" (next: {s['next_step']})" if s["next_step"] else "") for s in studies]
    due = db.get_pending_reviews(until=today)
    if due:
        lines.append(f"STUDY REVIEWS DUE: {len(due)}")
    return "\n".join(lines)


def generate(today: date = None) -> str:
    today = today or date.today()
    insight, _ = ai_gemini.generate(build_context(today), SYSTEM.format(language=language()), schema=Insight,
                                    temperature=0.8, max_output_tokens=512)
    text = " ".join(insight.text.split())[:MAX_CHARS]
    db.set_hud_setting(SETTING_TEXT, text)
    db.set_hud_setting(SETTING_DATE, today.isoformat())
    return text


def ensure_today(on_ready=None, force: bool = False) -> bool:
    """Generates today's insight in the background if needed. Returns True if a generation started."""
    global _running
    if not ai_gemini.is_configured() or (cached_today() and not force):
        return False
    with _lock:
        if _running:
            return False
        _running = True

    def work():
        global _running
        try:
            generate()
            if on_ready:
                on_ready()
        except Exception:
            log.exception("Insight of the day failed")
        finally:
            with _lock:
                _running = False

    threading.Thread(target=work, daemon=True, name="ai-insight").start()
    return True


def is_generating() -> bool:
    with _lock:
        return _running
