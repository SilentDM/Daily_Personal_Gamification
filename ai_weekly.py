"""Weekly summary for the Graphs tab: one short Gemini paragraph per ISO week (cached), describing the week
so far compared with the previous one. Same supportive, no-pressure tone as the insight of the day."""
import logging
import threading
from datetime import date, timedelta

from pydantic import BaseModel, Field

import ai_gemini
import ai_insight
import analytics
import database as db

log = logging.getLogger("gamification")

SETTING_TEXT = "weekly_summary_text"
SETTING_WEEK = "weekly_summary_week"
MAX_CHARS = 700

_lock = threading.Lock()
_running = False


class Summary(BaseModel):
    text: str = Field(description="One short paragraph (3-5 sentences, max ~550 characters)")


SYSTEM = """You are a supportive coach reviewing someone's week in a personal gamification app.
Write ONE short paragraph (3-5 sentences): what went well (be specific: habits, studies, quests),
one honest pattern worth noticing, and one small, concrete suggestion for the rest of the week.
Never guilt, never mention failure, deadlines or pressure. No emojis, no greetings, no lists.
Write in {language}."""


def week_key(today: date = None) -> str:
    iso = (today or date.today()).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def cached(today: date = None):
    settings = db.get_hud_settings()
    if settings.get(SETTING_WEEK) == week_key(today):
        return settings.get(SETTING_TEXT) or None
    return None


def build_context(today: date = None) -> str:
    today = today or date.today()
    this_start = analytics.monday(today)
    prev_start = this_start - timedelta(days=7)

    def summary(start, end):
        s = analytics._summary(start, end)
        avg = f"{s['avg_score']:.1f}/10" if s["avg_score"] is not None else "no entries"
        return (f"average habit score {avg}, {s['days_logged']}/{s['days_total']} days logged, "
                f"{s['xp']:.0f} XP, {s['study_minutes']} study minutes")

    lines = [f"THIS WEEK SO FAR ({this_start:%d/%m}–{today:%d/%m}): {summary(this_start, today)}",
             f"LAST WEEK: {summary(prev_start, this_start - timedelta(days=1))}"]
    per = {}
    for _, name, neg, _, _, score in analytics.habit_logs(this_start, today):
        per.setdefault((name, neg), []).append(score)
    rests = {}
    for _, name, _ in analytics.rest_logs(this_start, today):
        rests[name] = rests.get(name, 0) + 1
    if per:
        lines.append("HABITS THIS WEEK (average, days; rest days are planned breaks, not failures):")
        lines += [f"- {n}{' (vice to avoid)' if neg else ''}: {sum(v) / len(v):.1f} ({len(v)})" +
                  (f", {rests[n]} rest day(s)" if rests.get(n) else "")
                  for (n, neg), v in sorted(per.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))]
    week = analytics.weekly_series("7d", today)[-1]
    lines.append(f"QUESTS COMPLETED THIS WEEK: {week['quests']} • STUDY REVIEWS DONE: {week['reviews']}")
    active = [q for q in db.get_quests(statuses=("Active",)) if not q["done_this_period"]][:4]
    if active:
        lines.append("ACTIVE QUESTS: " + "; ".join(f"{q['title']} ({int(q['progress_pct'])}%)" for q in active))
    return "\n".join(lines)


def generate(today: date = None) -> str:
    summary, _ = ai_gemini.generate(build_context(today), SYSTEM.format(language=ai_insight.language()),
                                    schema=Summary, temperature=0.7, max_output_tokens=1024)
    text = " ".join(summary.text.split())[:MAX_CHARS]
    db.set_hud_setting(SETTING_TEXT, text)
    db.set_hud_setting(SETTING_WEEK, week_key(today))
    return text


def ensure(on_ready=None, force: bool = False) -> bool:
    """Generates this week's summary in the background if needed. Returns True if it started."""
    global _running
    if not ai_gemini.is_configured() or (cached() and not force):
        return False
    with _lock:
        if _running:
            return False
        _running = True

    def work():
        global _running
        error = None
        try:
            generate()
        except Exception as exc:
            log.exception("Weekly summary failed")
            error = str(exc)
        finally:
            with _lock:
                _running = False
        if on_ready:
            on_ready(error)

    threading.Thread(target=work, daemon=True, name="ai-weekly").start()
    return True


def is_generating() -> bool:
    with _lock:
        return _running
