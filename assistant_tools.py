"""Functions the Telegram assistant (Gemini) may call. Read tools + safe actions — nothing deletes data.

Rules for every tool:
- simple typed parameters and a clear docstring (Gemini reads them to decide what to call);
- dates are YYYY-MM-DD ("" = today), times HH:MM; names are matched loosely (difflib);
- actions are idempotent within one request (ActionLog), because a model fallback may replay calls;
- document numbers / notes are never exposed.
"""
import difflib
import threading
from datetime import date, datetime, timedelta

import analytics as an
import database as db
from constants import POSITIVE_SCORES, NEGATIVE_SCORES, REST_STATUS, DAY_NAMES

_local = threading.local()
_changed_callbacks = []


class ActionLog:
    """Remembers actions already done during one assistant request."""

    def __init__(self):
        self.done = {}
        self.changed = False

    def __enter__(self):
        _local.log = self
        return self

    def __exit__(self, *exc):
        _local.log = None
        if self.changed:
            for cb in list(_changed_callbacks):
                try:
                    cb()
                except Exception:
                    pass


def on_data_changed(callback):
    """main.py registers view refreshes here (tools run in the assistant's thread)."""
    _changed_callbacks.append(callback)


def _once(key, fn):
    log = getattr(_local, "log", None)
    if log is None:
        return fn()
    if key in log.done:
        return log.done[key]
    result = fn()
    log.done[key] = result
    if isinstance(result, dict) and result.get("ok"):
        log.changed = True
    return result


# ------------------------------------------------------------------ helpers
def _day(text: str) -> date:
    text = (text or "").strip().lower()
    if text in ("", "today", "hoje"):
        return date.today()
    if text in ("yesterday", "ontem"):
        return date.today() - timedelta(days=1)
    if text in ("tomorrow", "amanhã", "amanha"):
        return date.today() + timedelta(days=1)
    d = db.parse_flexible_date(text)
    if not d:
        raise ValueError(f"Could not understand the date '{text}'. Use YYYY-MM-DD.")
    return d


def _match(name: str, choices: dict, what: str):
    """choices: {display name: value}. Returns (value, display) or raises ValueError listing options."""
    if not choices:
        raise ValueError(f"There are no {what} yet.")
    lowered = {k.lower(): k for k in choices}
    key = (name or "").strip().lower()
    if key in lowered:
        return choices[lowered[key]], lowered[key]
    contains = [k for k in lowered if key and (key in k or k in key)]
    if len(contains) == 1:
        return choices[lowered[contains[0]]], lowered[contains[0]]
    close = difflib.get_close_matches(key, list(lowered), n=3, cutoff=0.5)
    if len(close) == 1 or (close and difflib.SequenceMatcher(None, key, close[0]).ratio() > 0.8):
        return choices[lowered[close[0]]], lowered[close[0]]
    options = ", ".join(sorted(choices))
    raise ValueError(f"Which {what}? I couldn't match '{name}'. Options: {options}")


def _err(exc) -> dict:
    return {"ok": False, "error": str(exc)}


def _habit_status(activity_id, d: date):
    iso = d.isocalendar()
    return db.get_current_week_logs(iso[0], iso[1]).get((activity_id, iso[2] - 1), ("-", None))


# ------------------------------------------------------------------ read tools
def get_today_overview() -> dict:
    """Today's snapshot: habits and answers, daily score, streak, level/XP, today's events, study reviews due,
    documents needing attention and the next step of active quests. Call this for "how is my day?"."""
    today = date.today()
    habits = []
    for aid, name, _, neg in db.get_activities():
        status, score = _habit_status(aid, today)
        habits.append({"habit": name, "vice": bool(neg), "answer": None if status == "-" else status,
                       "score": score})
    scored = [h["score"] for h in habits if h["score"] is not None]
    total_xp, level, xp_in_level, rank = db.get_user_xp_and_level()
    events = []
    done = db.get_completed_events(today.isoformat(), today.isoformat())
    for o in db.get_events_for_date(today):
        events.append({"title": o["title"], "time": "all day" if o["all_day"] else
                       f"{o['start_hour']:02d}:{o['start_minute']:02d}", "done": (o["id"], o["date"]) in done})
    return {
        "date": f"{DAY_NAMES[today.weekday()]} {today.isoformat()}",
        "habits": habits,
        "daily_score": round(sum(scored) / len(scored), 1) if scored else None,
        "unanswered": [h["habit"] for h in habits if h["answer"] is None],
        "streak_days": db.get_current_streak(),
        "level": level, "rank": rank, "total_xp": round(total_xp, 1),
        "events_today": events,
        "study_reviews_due": [r["topic"] for r in db.get_pending_reviews(until=today)],
        "documents_needing_attention": [{"title": t, "type": ty, "days_left": d}
                                        for t, ty, _, d in db.get_expiring_documents()],
        "active_quests": [{"title": q["title"], "progress_pct": int(q["progress_pct"]), "next_step": q["next_step"]}
                          for q in db.get_quests(statuses=("Active",)) if not q["done_this_period"]][:6],
    }


def get_agenda(days: int = 7) -> dict:
    """Upcoming calendar events, study reviews and document expirations for the next `days` days (max 60)."""
    days = max(1, min(int(days or 7), 60))
    start = date.today()
    end = start + timedelta(days=days - 1)
    events = []
    for d, occs in sorted(db.get_events_between(start, end).items()):
        for o in occs:
            events.append({"date": d.isoformat(), "weekday": DAY_NAMES[d.weekday()], "title": o["title"],
                           "time": "all day" if o["all_day"] else f"{o['start_hour']:02d}:{o['start_minute']:02d}",
                           "repeats": o["recurrence"]})
    reviews = [{"topic": r["topic"], "due": r["due_date"]} for r in db.get_pending_reviews(until=end)]
    docs = [{"title": d["title"], "type": d["doc_type"], "expires": d["expiration_date"], "status": d["status"]}
            for d in db.get_tracked_docs() if d["expiration_date"] <= end.isoformat() or d["status"] != "ok"]
    return {"from": start.isoformat(), "to": end.isoformat(), "events": events, "study_reviews": reviews,
            "documents": docs}


def get_habits(date_text: str = "") -> dict:
    """Habits and their answers for a day (YYYY-MM-DD, "" = today), plus the allowed answers per habit."""
    try:
        d = _day(date_text)
    except ValueError as exc:
        return _err(exc)
    out = []
    for aid, name, cat, neg in db.get_activities():
        status, score = _habit_status(aid, d)
        allowed = list(k for k in (NEGATIVE_SCORES if neg else POSITIVE_SCORES) if k != "-")
        if not neg:
            allowed.append(REST_STATUS)
        out.append({"habit": name, "category": cat, "vice": bool(neg), "answer": None if status == "-" else status,
                    "score": score, "allowed_answers": allowed})
    return {"date": d.isoformat(), "habits": out}


def get_quests() -> dict:
    """Active and on-hold quests with steps (done or not), progress, measurable target and next step."""
    quests = []
    for q in db.get_quests(statuses=("Active", "On hold")):
        quests.append({
            "title": q["title"], "status": q["status"], "type": q["quest_type"], "difficulty": q["difficulty"],
            "xp_reward": q["xp_reward"], "repeat": q["repeat"], "done_this_period": q["done_this_period"],
            "progress_pct": int(q["progress_pct"]), "next_step": q["next_step"],
            "steps": [{"step": s["title"], "done": s["done"]} for s in q["subquests"]],
            "target": {"unit": q["metric_unit"], "start": q["metric_start"], "current": q["metric_current"],
                       "target": q["metric_target"]} if q["has_metric"] else None,
        })
    return {"quests": quests}


def get_study() -> dict:
    """Study chapters (stage, next step, time studied) and the reviews that are due."""
    chapters = [{"topic": c["topic"], "stage": c["status"], "next_step": c["next_step"],
                 "sessions": c["sessions"], "minutes": c["minutes"], "reviews_due": c["reviews_due"]}
                for c in db.get_study_sessions()]
    return {"chapters": chapters,
            "reviews_due_today": [r["topic"] for r in db.get_pending_reviews(until=date.today())]}


def get_progress(period: str = "7d") -> dict:
    """Progress for a period: '7d', '30d', '12w' or '1y' — averages, days logged, XP, streak, study time
    (with the previous period for comparison) and the strongest / weakest habits."""
    key = period if period in an.PERIODS else "7d"
    k = an.kpis(key)
    ranking = an.habit_ranking(key)
    return {"period": an.PERIODS[key][0], "current": k["current"], "previous": k["previous"],
            "strongest_habits": [r[0] for r in ranking[:3]],
            "habits_needing_attention": [r[0] for r in ranking[-3:]] if len(ranking) > 3 else [],
            "current_streak": db.get_current_streak()}


def get_documents() -> dict:
    """Tracked documents with expiration dates and status (expired / soon / ok). Numbers are never shown."""
    return {"documents": [{"title": d["title"], "type": d["doc_type"], "expires": d["expiration_date"],
                           "status": d["status"], "days_left": d["days_left"]} for d in db.get_tracked_docs()]}


# ------------------------------------------------------------------ action tools (no deleting)
def mark_habit(habit: str, answer: str, date_text: str = "") -> dict:
    """Records a habit answer. answer: Excellent, Ok, A Little or Skipped (positive habits); Resisted, Slipped
    or Relapsed (vices); Rest (positive habits only, limited per week; no score impact). date_text: YYYY-MM-DD
    or "" for today (past days of this or earlier weeks allowed, never the future)."""
    def run():
        try:
            d = _day(date_text)
            if d > date.today():
                raise ValueError("Habits can't be marked for future days.")
            acts = {name: (aid, neg) for aid, name, _, neg in db.get_activities()}
            (aid, neg), name = _match(habit, acts, "habit")
            options = dict((k, v) for k, v in (NEGATIVE_SCORES if neg else POSITIVE_SCORES).items() if k != "-")
            wanted = {k.lower(): k for k in list(options) + [REST_STATUS]}
            key = (answer or "").strip().lower()
            if key not in wanted:
                close = difflib.get_close_matches(key, list(wanted), n=1, cutoff=0.6)
                if not close:
                    raise ValueError(f"'{answer}' isn't a valid answer for {name}. Use one of: "
                                     + ", ".join(list(options) + ([] if neg else [REST_STATUS])))
                key = close[0]
            status = wanted[key]
            iso = d.isocalendar()
            if status == REST_STATUS:
                if not db.can_rest(aid, iso[0], iso[1], iso[2] - 1):
                    raise ValueError("Rest isn't available: vices never rest and each habit has a weekly limit "
                                     f"of {db.rest_limit()} rest days.")
                db.save_log(aid, iso[0], iso[1], iso[2] - 1, REST_STATUS, None)
            else:
                db.save_log(aid, iso[0], iso[1], iso[2] - 1, status, options[status])
            return {"ok": True, "habit": name, "answer": status, "date": d.isoformat()}
        except ValueError as exc:
            return _err(exc)
    return _once(("mark_habit", habit.lower(), answer.lower(), date_text), run)


def add_calendar_event(title: str, date_text: str, time_text: str = "", duration_minutes: int = 60,
                       all_day: bool = False, repeat: str = "none", reminder_minutes: int = 15) -> dict:
    """Creates a calendar event. date_text YYYY-MM-DD; time_text HH:MM (ignored when all_day);
    repeat: none, daily, weekdays, weekly, monthly or yearly; reminder_minutes: minutes before (-1 = none)."""
    def run():
        try:
            d = _day(date_text)
            if not (title or "").strip():
                raise ValueError("The event needs a title.")
            hour = minute = 0
            if not all_day:
                try:
                    t = datetime.strptime((time_text or "").strip(), "%H:%M")
                except ValueError:
                    raise ValueError("Give a time as HH:MM (or make it an all-day event).")
                hour, minute = t.hour, t.minute
            rec = repeat if repeat in db.RECURRENCES else "none"
            event_id = db.add_calendar_event(title.strip(), d.isoformat(), hour, rec, start_minute=minute,
                                             duration_min=max(5, int(duration_minutes or 60)), all_day=bool(all_day),
                                             reminder_min=int(reminder_minutes))
            return {"ok": True, "event_id": event_id, "title": title.strip(), "date": d.isoformat(),
                    "time": "all day" if all_day else f"{hour:02d}:{minute:02d}", "repeat": rec}
        except ValueError as exc:
            return _err(exc)
    return _once(("add_event", title.lower(), date_text, time_text, all_day, repeat), run)


def mark_event_done(title: str, date_text: str = "") -> dict:
    """Marks a calendar event (or one occurrence of a repeating event) as done on a day (+XP)."""
    def run():
        try:
            d = _day(date_text)
            occs = {o["title"]: o for o in db.get_events_for_date(d)}
            occ, name = _match(title, occs, f"event on {d.isoformat()}")
            if db.is_event_completed(occ["id"], occ["date"]):
                return {"ok": True, "event": name, "already_done": True}
            db.toggle_event_completion(occ["id"], occ["date"])
            return {"ok": True, "event": name, "date": d.isoformat()}
        except ValueError as exc:
            return _err(exc)
    return _once(("event_done", title.lower(), date_text), run)


def log_study_session(chapter: str, notes: str, minutes: int = 0, next_step: str = "") -> dict:
    """Adds a study journal entry to a chapter (what was studied, minutes spent, next step)."""
    def run():
        try:
            chapters = {c["topic"]: c["id"] for c in db.get_study_sessions()}
            sid, name = _match(chapter, chapters, "study chapter")
            if not (notes or "").strip():
                raise ValueError("Tell me what you studied so I can write it in the journal.")
            xp = db.add_journal_entry(sid, notes.strip(), minutes=max(0, int(minutes or 0)),
                                      next_step=(next_step or "").strip())
            return {"ok": True, "chapter": name, "minutes": minutes, "xp_gained": xp}
        except ValueError as exc:
            return _err(exc)
    return _once(("study", chapter.lower(), notes[:40], minutes), run)


def check_quest_step(quest: str, step: str) -> dict:
    """Ticks a step (subquest) of a quest as done (+XP)."""
    def run():
        try:
            quests = {q["title"]: q for q in db.get_quests(statuses=("Active",))}
            q, qname = _match(quest, quests, "active quest")
            steps = {s["title"]: s for s in q["subquests"]}
            s, sname = _match(step, steps, f"step of '{qname}'")
            xp = db.set_subquest_done(s["id"], True)
            return {"ok": True, "quest": qname, "step": sname, "xp_gained": xp}
        except ValueError as exc:
            return _err(exc)
    return _once(("step", quest.lower(), step.lower()), run)


def add_quest_log(quest: str, text: str, value: str = "") -> dict:
    """Writes a progress note in a quest's log; value (optional, a number) updates its measurable target,
    e.g. weight in kg."""
    def run():
        try:
            quests = {q["title"]: q for q in db.get_quests(statuses=("Active", "On hold"))}
            q, qname = _match(quest, quests, "quest")
            number = None
            if (value or "").strip():
                try:
                    number = float(str(value).replace(",", "."))
                except ValueError:
                    raise ValueError(f"'{value}' isn't a number.")
            if not (text or "").strip() and number is None:
                raise ValueError("Tell me what to write in the quest log.")
            xp = db.add_quest_log(q["id"], (text or "").strip(), value=number)
            return {"ok": True, "quest": qname, "value": number, "xp_gained": xp}
        except ValueError as exc:
            return _err(exc)
    return _once(("quest_log", quest.lower(), (text or "")[:40], value), run)


def complete_quest(quest: str) -> dict:
    """Turns in a quest (one-time: Hall of Fame; repeatable: done for this week/month) and earns its XP."""
    def run():
        try:
            quests = {q["title"]: q for q in db.get_quests(statuses=("Active",))}
            q, qname = _match(quest, quests, "active quest")
            xp = db.complete_quest(q["id"])
            return {"ok": True, "quest": qname, "xp_gained": xp, "already_done": xp == 0}
        except ValueError as exc:
            return _err(exc)
    return _once(("complete_quest", quest.lower()), run)


def create_quest(title: str, steps: str = "", difficulty: str = "Normal") -> dict:
    """Creates a new quest. steps: optional, separated by ';'. difficulty: Easy, Normal, Hard or Epic."""
    def run():
        if not (title or "").strip():
            return _err("The quest needs a title.")
        diff = difficulty if difficulty in ("Easy", "Normal", "Hard", "Epic") else "Normal"
        quest_id = db.add_quest(title.strip(), difficulty=diff,
                                subquests=[s.strip() for s in (steps or "").split(";") if s.strip()])
        return {"ok": True, "quest_id": quest_id, "title": title.strip(), "difficulty": diff}
    return _once(("create_quest", title.lower()), run)


READ_TOOLS = [get_today_overview, get_agenda, get_habits, get_quests, get_study, get_progress, get_documents]
ACTION_TOOLS = [mark_habit, add_calendar_event, mark_event_done, log_study_session, check_quest_step,
                add_quest_log, complete_quest, create_quest]
ALL_TOOLS = READ_TOOLS + ACTION_TOOLS
