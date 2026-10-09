"""Proactive Telegram messages: morning briefing, calendar, documents, reviews, evening check-in, achievements.

`Notifier.tick()` runs from the app's reminder loop (every ~20 s). Every message has a key saved in the
assistant_sent table, so nothing is sent twice, even after a restart.
Quiet hours hold back documents, reviews and achievements; times the user picked (briefing, event
reminders, check-in) are always delivered.
"""
import logging
import threading
from datetime import datetime, timedelta

import database as db
import messages
import settings

log = logging.getLogger("gamification")

REVIEWS_HOUR = 9                   # review warning: first tick after 09:00 (outside quiet hours)
BRIEFING_LATEST_HOUR = 12          # app opened in the afternoon: skip that day's briefing
STREAK_MILESTONES = (3, 7, 14, 21, 30, 50, 75, 100, 150, 200, 250, 300, 365, 500, 730, 1000)
SETTING_LEDGER_SEEN = "tg_ledger_seen"
SETTING_LEVEL_SEEN = "tg_level_seen"


def _hhmm(text: str):
    try:
        return datetime.strptime(text, "%H:%M").time()
    except (TypeError, ValueError):
        return None


class Notifier:
    def __init__(self, assistant, checkin_time=None):
        """checkin_time: callable returning the Schedule's nightly reminder 'HH:MM' (or '' when off)."""
        self.assistant = assistant
        self.checkin_time = checkin_time or (lambda: "")

    def _send_once(self, key: str, text: str, **kw) -> bool:
        if db.was_sent(key):
            return False
        if self.assistant.send(text, **kw):
            db.mark_sent(key)
            return True
        return False

    def tick(self, now: datetime = None):
        if not (settings.flag("tg_enabled") and self.assistant.chat_id):
            return
        now = now or datetime.now()
        quiet = settings.in_quiet_hours(now)
        for step in (self._briefing, self._calendar, self._checkin):
            try:
                step(now)
            except Exception:
                log.exception("Telegram %s failed", step.__name__)
        if quiet:
            return
        for step in (self._documents, self._reviews, self._achievements):
            try:
                step(now)
            except Exception:
                log.exception("Telegram %s failed", step.__name__)

    # ---------------------------------------------------------- morning briefing (the wake-up message)
    def briefing_text(self, now: datetime) -> str:
        today = now.date()
        events = [f"{o['title']} ({'dia todo' if messages.lang() == 'pt' else 'all day'})" if o["all_day"]
                  else f"{o['title']} {o['start_hour']:02d}:{o['start_minute']:02d}"
                  for o in db.get_events_for_date(today)] if settings.tab_enabled("calendar") else []
        reviews = [r["topic"] for r in db.get_pending_reviews(until=today)] if settings.tab_enabled("study") else []
        steps = [q["next_step"] for q in db.get_quests(statuses=("Active",))
                 if q["next_step"] and not q["done_this_period"]][:3] if settings.tab_enabled("quests") else []
        nothing = messages.t("nothing")
        fallback = messages.t("briefing_fallback", events=", ".join(events) or nothing,
                              reviews=", ".join(reviews) or "0", steps=", ".join(steps) or "-")
        instruction = (
            "Write my good-morning message for today (it is the first message of my day). Call get_today_overview "
            "and get_agenda(2). Mention today's events with times, study reviews due, documents needing attention "
            "and one next step of a quest. End with one short, genuine line of encouragement based on my streak or "
            "recent progress. Maximum 8 short lines, no greeting longer than 3 words."
        )
        return self.assistant.compose(instruction, fallback)

    def _briefing(self, now: datetime):
        at = _hhmm(settings.get("tg_briefing"))
        if not at or now.time() < at or now.hour >= BRIEFING_LATEST_HOUR:
            return
        key = f"briefing:{now.date().isoformat()}"
        if db.was_sent(key):
            return
        db.mark_sent(key)  # before the (slow) AI call, so the next tick doesn't start another one

        def run():
            self.assistant.send(self.briefing_text(now), speak=True)
        threading.Thread(target=run, daemon=True, name="telegram-briefing").start()

    # ---------------------------------------------------------- calendar
    def _calendar(self, now: datetime):
        if not (settings.flag("tg_calendar") and settings.tab_enabled("calendar")):
            return
        today = now.date()
        tomorrow = today + timedelta(days=1)
        done = db.get_completed_events(today.isoformat(), tomorrow.isoformat())
        for occs in db.get_events_between(today, tomorrow).values():
            for occ in occs:
                if (occ["id"], occ["date"]) in done:
                    continue
                remind_at = db.reminder_time(occ)
                if remind_at is None:
                    continue
                start = db.occurrence_start(occ)
                window_end = remind_at + timedelta(hours=2) if occ["all_day"] else start
                if not (remind_at <= now < window_end):
                    continue
                is_today = start.date() == today
                if occ["all_day"]:
                    when = messages.t("event_allday_today" if is_today else "event_allday_tomorrow")
                else:
                    when = messages.t("event_today" if is_today else "event_tomorrow", time=f"{start:%H:%M}")
                self._send_once(f"cal:{occ['id']}:{occ['date']}", messages.t("event_soon", title=occ["title"],
                                                                             when=when))

    # ---------------------------------------------------------- evening check-in (buttons)
    def _checkin(self, now: datetime):
        if not settings.flag("tg_checkin"):
            return
        at = _hhmm(self.checkin_time())
        if not at or now.time() < at:
            return
        key = f"checkin:{now.date().isoformat()}"
        if db.was_sent(key):
            return
        if db.count_unmarked_today() == 0:
            db.mark_sent(key)  # all answered: nothing to ask today
            return
        if self.assistant.send_checkin(now.date()):
            db.mark_sent(key)

    # ---------------------------------------------------------- documents
    def _documents(self, now: datetime):
        if not (settings.flag("tg_documents") and settings.tab_enabled("documents")) or not 8 <= now.hour < 22:
            return
        for doc in db.get_tracked_docs(now.date()):
            stage = db.doc_notification_stage(doc)
            if not stage:
                continue
            exp = datetime.fromisoformat(doc["expiration_date"]).strftime("%d/%m/%Y")
            text = messages.t("doc_" + stage, title=doc["title"], date=exp, days=doc["days_left"])
            self._send_once(f"doc:{doc['id']}:{stage}:{doc['expiration_date']}", text)

    # ---------------------------------------------------------- study reviews
    def _reviews(self, now: datetime):
        if not (settings.flag("tg_reviews") and settings.tab_enabled("study")) or now.hour < REVIEWS_HOUR:
            return
        key = f"reviews:{now.date().isoformat()}"
        if db.was_sent(key):
            return
        due = db.get_pending_reviews(until=now.date())
        if not due:
            return  # checked again later: a review may become due after a chapter is mastered today
        topics = ", ".join(sorted({r["topic"] for r in due}))
        self._send_once(key, messages.t("reviews", n=len(due), topics=topics))

    # ---------------------------------------------------------- achievements
    def _achievements(self, now: datetime):
        if not settings.flag("tg_achievements"):
            return
        stored = db.get_hud_settings().get(SETTING_LEDGER_SEEN)
        if not stored:  # first run: start from now, no backlog of old achievements
            db.set_hud_setting(SETTING_LEDGER_SEEN, str(db.max_ledger_id()))
            db.set_hud_setting(SETTING_LEVEL_SEEN, str(db.get_user_xp_and_level()[1]))
            return
        seen = int(stored)
        for row_id, source, ref, amount in db.ledger_since(seen):
            text = None
            if source == "quest":
                quest = db.get_quest(int(ref.split(":")[0]))
                if quest:
                    text = messages.t("quest_done", title=quest["title"], xp=amount)
            elif source == "study":
                chapter = db.get_study_session(int(ref))
                if chapter:
                    text = messages.t("mastered", title=chapter["topic"])
            if text and not self._send_once(f"ach:{source}:{ref}", text) and not db.was_sent(f"ach:{source}:{ref}"):
                break  # sending failed: try again next tick from here
            seen = row_id
        db.set_hud_setting(SETTING_LEDGER_SEEN, str(seen))

        _, level, _, rank = db.get_user_xp_and_level()
        level_seen = int(db.get_hud_settings().get(SETTING_LEVEL_SEEN) or level)
        if level > level_seen:
            if self.assistant.send(messages.t("level_up", level=level, rank=rank)):
                db.set_hud_setting(SETTING_LEVEL_SEEN, str(level))
        elif level < level_seen:
            db.set_hud_setting(SETTING_LEVEL_SEEN, str(level))  # XP undone: celebrate again when regained

        streak = db.get_current_streak()
        if streak in STREAK_MILESTONES:
            last = now.date() if db.streak_days().get(now.date()) else now.date() - timedelta(days=1)
            began = (last - timedelta(days=streak - 1)).isoformat()  # same key whether today counts yet or not
            self._send_once(f"streak:{streak}:{began}", messages.t("streak", n=streak))
