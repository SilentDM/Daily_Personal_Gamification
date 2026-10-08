"""Database layer tests. Run with:  python -m unittest discover tests

Every test gets a throwaway %APPDATA%, so the real database is never touched.
"""
import os
import sys
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db  # noqa: E402
import secure  # noqa: E402
from constants import (XP_QUEST, XP_STUDY, XP_STUDY_LOG, XP_REVIEW, REVIEW_DAYS, XP_SUBQUEST,  # noqa: E402
                       XP_QUEST_LOG, QUEST_DIFFICULTY_XP)


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {"APPDATA": self.tmp})
        env.start()
        self.addCleanup(env.stop)
        # never read/write the real Windows Credential Manager
        if secure.AVAILABLE:
            key = secure.Fernet.generate_key()
            patcher = mock.patch.object(secure, "_load_key", return_value=key)
            patcher.start()
            self.addCleanup(patcher.stop)
        secure._reset()
        self.addCleanup(secure._reset)
        db.init_db()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def xp(self):
        return db.get_user_xp_and_level()[0]

    def log_today(self, activity_id, status, score):
        year, week, day_idx = db.get_current_week_info()
        db.save_log(activity_id, year, week, day_idx, status, score)


class InitTests(DbTestCase):
    def test_init_is_idempotent(self):
        db.init_db()
        db.init_db()

    def test_fresh_install_with_encryption_enabled(self):
        # regression: the encryption migration read extra_fields before it existed
        fresh = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, fresh, True)
        with mock.patch.dict(os.environ, {"APPDATA": fresh}), \
                mock.patch.object(secure, "AVAILABLE", True), \
                mock.patch.object(secure, "encrypt", lambda v: v):
            db.init_db()


class HabitXpTests(DbTestCase):
    def test_perfect_day_gives_10_xp_and_a_streak(self):
        a = db.add_activity("Gym")
        self.log_today(a, "Excellent", 10)
        self.assertAlmostEqual(self.xp(), 10.0)
        self.assertEqual(db.get_current_streak(), 1)

    def test_relogging_a_day_replaces_its_xp(self):
        a = db.add_activity("Gym")
        self.log_today(a, "Excellent", 10)
        self.log_today(a, "Ok", 7)
        self.assertAlmostEqual(self.xp(), 4.0)  # (7 - 5) * 2

    def test_deleting_a_habit_recomputes_daily_xp(self):
        good = db.add_activity("Gym")
        bad = db.add_activity("Smoking", "Vice / Avoid", is_negative=True)
        self.log_today(good, "Excellent", 10)
        self.log_today(bad, "Relapsed", 0)
        self.assertAlmostEqual(self.xp(), 0.0)  # avg 5 -> 0 XP
        db.delete_activity(bad)
        self.assertAlmostEqual(self.xp(), 10.0)  # avg 10 -> +10 XP


class RestDayTests(DbTestCase):
    def log_on(self, activity_id, day, status, score):
        iso = day.isocalendar()
        db.save_log(activity_id, iso[0], iso[1], iso[2] - 1, status, score)

    def test_rest_is_answered_but_never_scored(self):
        gym, read = db.add_activity("Gym"), db.add_activity("Read")
        self.log_today(read, "Excellent", 10)
        xp_before = self.xp()
        self.log_today(gym, "Rest", 7)  # any score passed in is ignored
        year, week, day = db.get_current_week_info()
        self.assertEqual(db.get_current_week_logs(year, week)[(gym, day)], ("Rest", None))
        self.assertAlmostEqual(self.xp(), xp_before)  # the day is still worth exactly Read's 10
        self.assertEqual(db.count_unmarked_today(), 0)

    def test_vices_cannot_rest(self):
        smoke = db.add_activity("Smoking", "Vice / Avoid", is_negative=True)
        year, week, day = db.get_current_week_info()
        self.assertFalse(db.can_rest(smoke, year, week, day))
        with self.assertRaises(ValueError):
            self.log_today(smoke, "Rest", None)

    def test_three_rest_days_per_habit_per_week(self):
        gym, read = db.add_activity("Gym"), db.add_activity("Read")
        monday = date(2026, 10, 5)
        for i in range(3):
            self.log_on(gym, monday + timedelta(days=i), "Rest", None)
        with self.assertRaises(ValueError):
            self.log_on(gym, monday + timedelta(days=3), "Rest", None)
        self.log_on(gym, monday + timedelta(days=2), "Rest", None)  # re-saving the same day is fine
        self.log_on(read, monday + timedelta(days=3), "Rest", None)  # other habits have their own 3
        self.log_on(gym, monday + timedelta(days=7), "Rest", None)  # a new week resets the allowance
        self.assertEqual(db.rest_days_used(gym, 2026, 41), 3)

    def test_streak_counts_rest_only_days(self):
        gym = db.add_activity("Gym")
        today = date.today()
        self.log_on(gym, today - timedelta(days=2), "Excellent", 10)
        self.log_on(gym, today - timedelta(days=1), "Rest", None)
        self.log_on(gym, today, "Ok", 7)
        self.assertEqual(db.get_current_streak(), 3)

    def test_streak_partial_rest_uses_the_other_habits(self):
        gym, read = db.add_activity("Gym"), db.add_activity("Read")
        today = date.today()
        self.log_on(gym, today, "Rest", None)
        self.log_on(read, today, "A Little", 4)  # the day is only Read's 4 -> below 7
        self.assertEqual(db.get_current_streak(), 0)
        self.log_on(read, today, "Excellent", 10)
        self.assertEqual(db.get_current_streak(), 1)


class HabitManagementTests(DbTestCase):
    def test_rename_and_recategorize_keep_history(self):
        a = db.add_activity("Gym")
        self.log_today(a, "Excellent", 10)
        db.update_activity(a, name="Gym / Workout", category="Health")
        self.assertEqual(db.get_activities()[0][1:3], ("Gym / Workout", "Health"))
        year, week, day = db.get_current_week_info()
        self.assertEqual(db.get_current_week_logs(year, week)[(a, day)], ("Excellent", 10))

    def test_count_unmarked_today(self):
        a, b = db.add_activity("Gym"), db.add_activity("Read")
        db.add_activity("Archived")
        db.delete_activity(db.get_activities()[-1][0])
        self.assertEqual(db.count_unmarked_today(), 2)
        self.log_today(a, "Ok", 7)
        self.log_today(b, "-", None)  # cleared answers still count as unmarked
        self.assertEqual(db.count_unmarked_today(), 1)


class QuestTests(DbTestCase):
    MON = date(2025, 6, 2)  # a Monday

    def test_quest_xp_depends_on_difficulty_awarded_once_and_removed_on_reopen(self):
        q = db.add_quest("Taxes", difficulty="Hard")
        self.assertEqual(db.complete_quest(q), QUEST_DIFFICULTY_XP["Hard"])
        self.assertEqual(db.complete_quest(q), 0.0)
        self.assertAlmostEqual(self.xp(), QUEST_DIFFICULTY_XP["Hard"])
        self.assertEqual(db.get_quest(q)["status"], "Complete")
        db.set_quest_status(q, "Active")  # reopen
        self.assertAlmostEqual(self.xp(), 0.0)

    def test_checkbox_subquests_give_xp_and_drive_progress(self):
        q = db.add_quest("Trip", subquests=["Book flight", "Book hotel", ""])
        subs = db.get_quest(q)["subquests"]
        self.assertEqual([s["title"] for s in subs], ["Book flight", "Book hotel"])
        self.assertEqual(db.set_subquest_done(subs[0]["id"], True), XP_SUBQUEST)
        self.assertEqual(db.set_subquest_done(subs[0]["id"], True), 0.0)  # already checked
        quest = db.get_quest(q)
        self.assertEqual((quest["sub_done"], quest["sub_total"], quest["progress_pct"]), (1, 2, 50.0))
        self.assertEqual(quest["status"], "Active")  # turning in is explicit
        db.set_subquest_done(subs[0]["id"], False)
        self.assertAlmostEqual(self.xp(), 0.0)

    def test_measurable_target_works_for_decreasing_goals(self):
        q = db.add_quest("Lose weight", metric_unit="kg", metric_start=82, metric_target=77)
        self.assertEqual(db.get_quest(q)["progress_pct"], 0.0)
        db.add_quest_log(q, "weekly weigh-in", value=80, entry_date="2025-06-01")
        db.add_quest_log(q, value=79.5, entry_date="2025-06-08")
        quest = db.get_quest(q)
        self.assertEqual(quest["metric_current"], 79.5)
        self.assertAlmostEqual(quest["metric_pct"], 50.0)
        db.add_quest_log(q, value=76, entry_date="2025-06-20")  # past the target -> capped
        self.assertEqual(db.get_quest(q)["metric_pct"], 100.0)

    def test_progress_mixes_subquests_and_target(self):
        q = db.add_quest("Read", metric_unit="books", metric_start=0, metric_target=10, subquests=["List", "Buy"])
        db.set_subquest_done(db.get_quest(q)["subquests"][0]["id"], True)
        db.add_quest_log(q, value=5)
        self.assertAlmostEqual(db.get_quest(q)["progress_pct"], 50.0)  # mean of 50% and 50%

    def test_repeatable_quest_once_per_period_and_subquests_reset(self):
        q = db.add_quest("Weekly review", repeat="weekly", subquests=["Inbox zero"])
        sub = db.get_quest(q, on=self.MON)["subquests"][0]["id"]
        db.set_subquest_done(sub, True, on=self.MON)
        self.assertEqual(db.complete_quest(q, on=self.MON + timedelta(days=2)), XP_QUEST)
        self.assertEqual(db.complete_quest(q, on=self.MON + timedelta(days=3)), 0.0)  # same week
        quest = db.get_quest(q, on=self.MON + timedelta(days=3))
        self.assertTrue(quest["done_this_period"])
        self.assertEqual(quest["status"], "Active")
        next_week = db.get_quest(q, on=self.MON + timedelta(days=7))
        self.assertFalse(next_week["done_this_period"])
        self.assertFalse(next_week["subquests"][0]["done"])  # reset for the new week
        self.assertEqual(db.complete_quest(q, on=self.MON + timedelta(days=8)), XP_QUEST)
        self.assertEqual(db.get_quest(q, on=self.MON + timedelta(days=8))["times_completed"], 2)
        self.assertAlmostEqual(self.xp(), XP_SUBQUEST + 2 * XP_QUEST)

    def test_undo_repeatable_completion_only_this_period(self):
        q = db.add_quest("Pay bills", repeat="monthly")
        db.complete_quest(q, on=date(2025, 5, 3))
        db.complete_quest(q, on=date(2025, 6, 3))
        db.undo_quest_completion(q, on=date(2025, 6, 10))
        self.assertEqual(db.get_quest(q, on=date(2025, 6, 10))["times_completed"], 1)
        self.assertAlmostEqual(self.xp(), XP_QUEST)

    def test_periods_and_next_availability(self):
        self.assertEqual(db.quest_period_key("weekly", date(2025, 12, 31)), "2026-W01")
        self.assertEqual(db.quest_period_key("monthly", date(2025, 12, 31)), "2025-12")
        self.assertEqual(db.next_period_start("weekly", date(2025, 6, 4)), date(2025, 6, 9))
        self.assertEqual(db.next_period_start("monthly", date(2025, 12, 15)), date(2026, 1, 1))

    def test_quest_log_xp_once_per_day_for_real_entries(self):
        q = db.add_quest("Taxes")
        self.assertEqual(db.add_quest_log(q, "ok", entry_date="2025-06-02"), 0.0)
        self.assertEqual(db.add_quest_log(q, "Collected all receipts", next_step="Fill the form",
                                          entry_date="2025-06-02"), XP_QUEST_LOG)
        self.assertEqual(db.add_quest_log(q, "Started filling the form", entry_date="2025-06-02"), 0.0)
        self.assertEqual(db.get_quest(q)["next_step"], "Fill the form")
        entry = [e for e in db.get_quest_log(q) if e["text"] == "Collected all receipts"][0]
        db.delete_quest_log(entry["id"])
        self.assertAlmostEqual(self.xp(), XP_QUEST_LOG)  # "Started filling..." still qualifies

    def test_on_hold_and_order(self):
        a, b, c = (db.add_quest(t) for t in ("A", "B", "C"))
        db.set_quest_status(b, "On hold")
        db.move_quest(c, "up")
        self.assertEqual([q["title"] for q in db.get_quests()], ["C", "A", "B"])
        self.assertEqual([q["title"] for q in db.get_quests(statuses=("On hold",))], ["B"])

    def test_week_stats_count_one_off_and_repeatable(self):
        a = db.add_quest("One-off", difficulty="Easy")
        r = db.add_quest("Weekly", repeat="weekly")
        db.complete_quest(a, on=self.MON)
        db.complete_quest(r, on=self.MON + timedelta(days=1))
        count, xp = db.get_quest_week_stats(2025, 23)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(xp, QUEST_DIFFICULTY_XP["Easy"] + XP_QUEST)

    def test_update_rejects_unknown_fields(self):
        q = db.add_quest("X")
        with self.assertRaises(ValueError):
            db.update_quest(q, status="Complete")
        with self.assertRaises(ValueError):
            db.set_quest_status(q, "Complete")

    def test_old_quests_are_migrated(self):
        old = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, old, True)
        with mock.patch.dict(os.environ, {"APPDATA": old}):
            conn = db.get_connection()
            conn.execute("""CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                status TEXT DEFAULT 'Planning', notes TEXT DEFAULT '', sort_order INTEGER DEFAULT 0,
                completed_year INTEGER, completed_week INTEGER, completed_at TIMESTAMP, active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("""CREATE TABLE subtasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
                title TEXT NOT NULL, status TEXT DEFAULT 'Planning', sort_order INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("INSERT INTO tasks (title, status, notes) VALUES ('Old quest', 'Almost There', 'my notes')")
            conn.execute("INSERT INTO tasks (title, status, completed_at) VALUES ('Done quest', 'Complete', "
                         "'2025-01-05 10:00:00')")
            conn.execute("INSERT INTO subtasks (task_id, title, status) VALUES (1, 'Step done', 'Complete')")
            conn.execute("INSERT INTO subtasks (task_id, title, status) VALUES (1, 'Step half', 'In Progress')")
            conn.commit()
            conn.close()
            db.init_db()
            by_title = {q["title"]: q for q in db.get_quests()}
            old_q = by_title["Old quest"]
            self.assertEqual((old_q["status"], old_q["notes"], old_q["difficulty"], old_q["quest_type"],
                              old_q["repeat"], old_q["sub_done"], old_q["sub_total"]),
                             ("Active", "my notes", "Normal", "Main", "none", 1, 2))
            self.assertEqual(by_title["Done quest"]["status"], "Complete")


class CalendarTests(DbTestCase):
    def test_monthly_event_on_31st_falls_on_last_day_of_short_months(self):
        db.add_calendar_event("Rent", "2025-01-31", 9, "monthly")
        self.assertEqual(len(db.get_events_for_date(date(2025, 2, 28))), 1)
        self.assertEqual(len(db.get_events_for_date(date(2025, 2, 27))), 0)
        self.assertEqual(len(db.get_events_for_date(date(2024, 12, 31))), 0)  # before start

    def test_range_matches_single_day_lookup(self):
        db.add_calendar_event("Gym", "2025-03-03", 7, "weekly")
        db.add_calendar_event("Dentist", "2025-03-12", 15, "none")
        db.add_calendar_event("Birthday", "2024-03-20", 0, "yearly")
        start, end = date(2025, 3, 1), date(2025, 3, 31)
        by_day = db.get_events_between(start, end)
        self.assertEqual(len(by_day), 31)
        for d, events in by_day.items():
            self.assertEqual(events, db.get_events_for_date(d))
        self.assertEqual(sum(len(v) for v in by_day.values()), 5 + 1 + 1)  # 5 Mondays from the 3rd

    def test_upcoming_skips_completed_occurrences(self):
        tomorrow = date.today() + timedelta(days=1)
        eid = db.add_calendar_event("Call", tomorrow.isoformat(), 10, "none")
        self.assertEqual(len(db.get_upcoming_events()), 1)
        db.toggle_event_completion(eid, tomorrow.isoformat())
        self.assertEqual(db.get_upcoming_events(), [])

    def test_upcoming_uses_minutes_and_keeps_todays_all_day_events(self):
        db.add_calendar_event("Standup", "2025-05-05", 9, start_minute=30)
        db.add_calendar_event("Holiday", "2025-05-05", all_day=True)
        titles = [o["title"] for o in db.get_upcoming_events(now=datetime(2025, 5, 5, 9, 20))]
        self.assertEqual(titles, ["Holiday", "Standup"])
        titles = [o["title"] for o in db.get_upcoming_events(now=datetime(2025, 5, 5, 9, 31))]
        self.assertEqual(titles, ["Holiday"])

    def test_day_is_sorted_all_day_first_then_by_time(self):
        db.add_calendar_event("Late", "2025-05-05", 18)
        db.add_calendar_event("Early", "2025-05-05", 8, start_minute=45)
        db.add_calendar_event("Trip", "2025-05-05", all_day=True)
        db.add_calendar_event("Earlier", "2025-05-05", 8, start_minute=15)
        self.assertEqual([o["title"] for o in db.get_events_for_date(date(2025, 5, 5))],
                         ["Trip", "Earlier", "Early", "Late"])

    def test_daily_and_weekdays_with_series_end(self):
        db.add_calendar_event("Meds", "2025-06-01", 8, "daily", recurrence_end="2025-06-10")
        db.add_calendar_event("Work", "2025-06-02", 9, "weekdays")  # Monday
        june = db.get_events_between(date(2025, 6, 1), date(2025, 6, 30))
        meds = [d.day for d, occ in june.items() if any(o["title"] == "Meds" for o in occ)]
        work = [d.day for d, occ in june.items() if any(o["title"] == "Work" for o in occ)]
        self.assertEqual(meds, list(range(1, 11)))
        self.assertEqual(len(work), 21)
        self.assertNotIn(7, work)  # Saturday

    def test_skip_single_occurrence(self):
        eid = db.add_calendar_event("Gym", "2025-06-02", 7, "weekly")
        db.skip_event_occurrence(eid, "2025-06-09")
        self.assertEqual(db.get_events_for_date(date(2025, 6, 9)), [])
        self.assertEqual(len(db.get_events_for_date(date(2025, 6, 16))), 1)

    def test_end_series_keeps_earlier_occurrences(self):
        eid = db.add_calendar_event("Class", "2025-06-02", 19, "weekly")
        db.end_event_series(eid, "2025-06-16")
        self.assertEqual(len(db.get_events_for_date(date(2025, 6, 9))), 1)
        self.assertEqual(db.get_events_for_date(date(2025, 6, 16)), [])
        db.end_event_series(eid, "2025-06-02")  # from the first one -> whole series
        self.assertEqual(db.get_events_for_date(date(2025, 6, 9)), [])

    def test_edit_one_occurrence_moves_its_completion(self):
        eid = db.add_calendar_event("Gym", "2025-06-02", 7, "weekly")
        db.toggle_event_completion(eid, "2025-06-09")
        xp_before = self.xp()
        new_id = db.edit_event_occurrence(eid, "2025-06-09", start_hour=18, title="Gym (evening)")
        occ = db.get_events_for_date(date(2025, 6, 9))
        self.assertEqual([(o["id"], o["title"], o["start_hour"], o["recurrence"]) for o in occ],
                         [(new_id, "Gym (evening)", 18, "none")])
        self.assertTrue(db.is_event_completed(new_id, "2025-06-09"))
        self.assertAlmostEqual(self.xp(), xp_before)
        self.assertEqual(db.get_events_for_date(date(2025, 6, 16))[0]["start_hour"], 7)

    def test_edit_following_splits_the_series(self):
        eid = db.add_calendar_event("Class", "2025-06-02", 19, "weekly", recurrence_end="2025-12-31")
        new_id = db.edit_event_following(eid, "2025-06-16", start_hour=20)
        self.assertEqual(db.get_events_for_date(date(2025, 6, 9))[0]["start_hour"], 19)
        later = db.get_events_for_date(date(2025, 6, 23))[0]
        self.assertEqual((later["id"], later["start_hour"], later["recurrence_end"]), (new_id, 20, "2025-12-31"))
        self.assertEqual(sum(len(v) for v in db.get_events_between(date(2025, 6, 1), date(2025, 6, 30)).values()), 5)

    def test_update_rejects_unknown_fields(self):
        eid = db.add_calendar_event("X", "2025-06-02")
        with self.assertRaises(ValueError):
            db.update_calendar_event(eid, active=0)

    def test_reminder_times(self):
        timed = {"date": "2025-06-02", "all_day": False, "start_hour": 10, "start_minute": 30, "reminder_min": 15}
        self.assertEqual(db.reminder_time(timed), datetime(2025, 6, 2, 10, 15))
        self.assertIsNone(db.reminder_time(dict(timed, reminder_min=db.NO_REMINDER)))
        all_day = dict(timed, all_day=True, reminder_min=0)
        self.assertEqual(db.reminder_time(all_day), datetime(2025, 6, 2, 9, 0))
        self.assertEqual(db.reminder_time(dict(all_day, reminder_min=1440)), datetime(2025, 6, 1, 9, 0))

    def test_old_calendar_schema_is_migrated(self):
        old = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, old, True)
        with mock.patch.dict(os.environ, {"APPDATA": old}):
            conn = db.get_connection()
            conn.execute("""CREATE TABLE calendar_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, event_date TEXT NOT NULL, start_hour INTEGER NOT NULL,
                recurrence TEXT DEFAULT 'none', active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("INSERT INTO calendar_events (title, event_date, start_hour) VALUES ('Old', '2025-01-01', 14)")
            conn.commit()
            conn.close()
            db.init_db()
            occ = db.get_events_for_date(date(2025, 1, 1))[0]
            self.assertEqual((occ["title"], occ["start_hour"], occ["start_minute"], occ["duration_min"],
                              occ["all_day"], occ["reminder_min"], occ["color"]),
                             ("Old", 14, 0, 60, False, 15, "Cyan"))


class DocumentTests(DbTestCase):
    TODAY = date(2026, 10, 5)

    def add(self, title, doc_type, days_from_today, **kw):
        return db.add_tracked_doc(title, doc_type, (self.TODAY + timedelta(days=days_from_today)).isoformat(), **kw)

    def test_type_presets_and_status(self):
        cnh = self.add("My CNH", "CNH", 90)
        passport = self.add("Passport", "Passaporte", 120)
        ipva = self.add("IPVA Honda", "IPVA", -3)
        by_id = {d["id"]: d for d in db.get_tracked_docs(self.TODAY)}
        self.assertEqual((by_id[cnh]["category"], by_id[cnh]["warn_days"], by_id[cnh]["status"]), ("Identity", 60, "ok"))
        self.assertEqual((by_id[passport]["warn_days"], by_id[passport]["status"]), (180, "soon"))
        self.assertEqual((by_id[ipva]["annual"], by_id[ipva]["status"], by_id[ipva]["days_left"]), (True, "expired", -3))
        self.assertEqual([d["id"] for d in db.get_tracked_docs(self.TODAY)], [ipva, passport, cnh])  # by urgency

    def test_number_is_optional_encrypted_and_never_listed(self):
        bare = self.add("RG", "RG / CIN", 400)
        full = self.add("CNH", "CNH", 400, number="123456789", notes="Category B")
        listed = {d["id"]: d for d in db.get_tracked_docs(self.TODAY)}
        self.assertNotIn("number", listed[full])
        self.assertEqual((listed[bare]["has_number"], listed[full]["has_number"]), (False, True))
        self.assertEqual(db.get_doc_secrets(full), ("123456789", "Category B"))
        if secure.AVAILABLE:
            conn = db.get_connection()
            raw = conn.execute("SELECT number FROM tracked_documents WHERE id = ?", (full,)).fetchone()[0]
            conn.close()
            self.assertTrue(raw.startswith(secure.PREFIX))

    def test_renew_records_history_and_annual_suggestion(self):
        ipva = self.add("IPVA", "IPVA", 10)
        doc = db.get_tracked_doc(ipva, self.TODAY)
        nxt = db.suggested_renewal_date(doc)
        self.assertEqual(nxt, (self.TODAY + timedelta(days=10)).replace(year=2027))
        db.renew_doc(ipva, nxt.isoformat(), on=self.TODAY)
        doc = db.get_tracked_doc(ipva, self.TODAY)
        self.assertEqual((doc["expiration_date"], doc["status"]), (nxt.isoformat(), "ok"))
        self.assertEqual(db.get_doc_renewals(ipva)[0]["new_expiration"], nxt.isoformat())

    def test_renewal_quest_created_once_and_completed_by_renewing(self):
        cnh = self.add("CNH", "CNH", 30)
        self.add("RG", "RG / CIN", 300)  # not in its window yet
        created = db.sync_renewal_quests(self.TODAY)
        self.assertEqual(len(created), 1)
        self.assertEqual(db.sync_renewal_quests(self.TODAY), [])  # no duplicates
        quest = db.get_quest(created[0])
        self.assertEqual((quest["title"], quest["sub_total"]), ("Renew CNH", 3))
        xp = db.renew_doc(cnh, "2036-10-05", on=self.TODAY)
        self.assertEqual(xp, XP_QUEST)
        self.assertEqual(db.get_quest(created[0])["status"], "Complete")

    def test_renewal_quest_not_recreated_after_manual_completion_and_can_be_disabled(self):
        self.add("Seguro", "Seguro auto", 5)
        quest_id = db.sync_renewal_quests(self.TODAY)[0]
        db.complete_quest(quest_id)
        self.assertEqual(db.sync_renewal_quests(self.TODAY), [])
        db.set_hud_setting(db.SETTING_DOC_QUESTS, "false")
        self.add("IPTU", "IPTU", 5)
        self.assertEqual(db.sync_renewal_quests(self.TODAY), [])

    def test_notification_milestones_fire_once_each(self):
        doc_id = self.add("CNH", "CNH", 30)
        self.assertEqual([s for _, s in db.get_doc_notifications(self.TODAY)], ["window"])
        db.mark_doc_notified(doc_id, "window")
        self.assertEqual(db.get_doc_notifications(self.TODAY), [])
        self.assertEqual([s for _, s in db.get_doc_notifications(self.TODAY + timedelta(days=25))], ["week"])
        self.assertEqual([s for _, s in db.get_doc_notifications(self.TODAY + timedelta(days=30))], ["due"])
        db.update_tracked_doc(doc_id, expiration_date="2030-01-01")  # new date restarts reminders
        self.assertEqual(db.get_tracked_doc(doc_id)["notified_stage"], "")

    def test_calendar_items(self):
        cnh = self.add("CNH", "CNH", 30)            # warn started 30 days ago, due in 30
        old = self.add("Old", "Outro", -2)          # expired -> also shown today
        items = db.get_docs_for_calendar(self.TODAY - timedelta(days=40), self.TODAY + timedelta(days=40), self.TODAY)
        kinds = sorted((d["id"], d["kind"], day) for day, docs in items.items() for d in docs)
        self.assertIn((cnh, "due", self.TODAY + timedelta(days=30)), kinds)
        self.assertIn((cnh, "warn", self.TODAY - timedelta(days=30)), kinds)
        self.assertIn((old, "expired", self.TODAY), kinds)

    def test_pin(self):
        self.assertFalse(db.has_doc_pin())
        db.set_doc_pin("4321")
        self.assertTrue(db.has_doc_pin())
        self.assertTrue(db.check_doc_pin("4321"))
        self.assertFalse(db.check_doc_pin("1234"))
        self.assertNotIn("4321", db.get_hud_settings()[db.SETTING_DOC_PIN])

    def test_forgotten_pin_wipes_only_secrets(self):
        doc_id = self.add("CNH", "CNH", 400, number="999", notes="x")
        db.set_doc_pin("1111")
        db.reset_doc_pin_and_wipe_secrets()
        self.assertFalse(db.has_doc_pin())
        self.assertEqual(db.get_doc_secrets(doc_id), ("", ""))
        self.assertEqual(db.get_tracked_doc(doc_id)["title"], "CNH")

    def test_update_rejects_unknown_fields(self):
        doc_id = self.add("X", "Outro", 10)
        with self.assertRaises(ValueError):
            db.update_tracked_doc(doc_id, quest_id=5)

    def test_legacy_documents_import_safe_fields_then_delete(self):
        conn = db.get_connection()
        conn.execute("INSERT INTO personal_documents (category, doc_type, title, doc_number, expiration_date) "
                     "VALUES ('Vehicles', 'CRLV / Carro', 'Honda', '123', '2027-03-01')")
        conn.execute("INSERT INTO personal_documents (category, doc_type, title, doc_number) "
                     "VALUES ('Identity', 'CPF', 'Me', '111.222.333-44')")  # no date -> not imported
        conn.commit()
        conn.close()
        self.assertEqual(db.count_legacy_documents(), 2)
        self.assertEqual(db.remove_legacy_documents(import_safe_fields=True), 1)
        self.assertEqual(db.count_legacy_documents(), 0)
        doc = db.get_tracked_docs()[0]
        self.assertEqual((doc["title"], doc["category"], doc["expiration_date"], doc["has_number"]),
                         ("Honda", "Vehicle", "2027-03-01", False))


class StudyTests(DbTestCase):
    D0 = date(2025, 3, 10)

    def chapter(self, sid):
        return db.get_study_session(sid)

    def test_new_chapter_starts_not_started_and_first_entry_moves_to_studying(self):
        sid = db.add_study_session("Docker")
        self.assertEqual(self.chapter(sid)["status"], "Not started")
        db.add_journal_entry(sid, "Installed docker, ran hello-world container", minutes=30,
                             next_step="Volumes chapter")
        ch = self.chapter(sid)
        self.assertEqual((ch["status"], ch["sessions"], ch["minutes"], ch["next_step"]),
                         ("Studying", 1, 30, "Volumes chapter"))

    def test_journal_xp_once_per_chapter_per_day_and_only_for_real_notes(self):
        sid = db.add_study_session("SQL")
        self.assertEqual(db.add_journal_entry(sid, "short", entry_date="2025-03-10"), 0.0)
        self.assertEqual(db.add_journal_entry(sid, "Joins: inner, left, right and full outer", entry_date="2025-03-10"),
                         XP_STUDY_LOG)
        self.assertEqual(db.add_journal_entry(sid, "Window functions: ROW_NUMBER, RANK", entry_date="2025-03-10"), 0.0)
        self.assertEqual(db.add_journal_entry(sid, "Indexes and query plans, EXPLAIN", entry_date="2025-03-11"),
                         XP_STUDY_LOG)
        self.assertAlmostEqual(self.xp(), 2 * XP_STUDY_LOG)

    def test_deleting_the_only_qualifying_entry_removes_its_xp(self):
        sid = db.add_study_session("SQL")
        db.add_journal_entry(sid, "Joins: inner, left, right and full outer", entry_date="2025-03-10")
        entry = db.get_journal(sid)[0]
        db.delete_journal_entry(entry["id"])
        self.assertAlmostEqual(self.xp(), 0.0)

    def test_mastering_awards_xp_and_schedules_first_review(self):
        sid = db.add_study_session("Git")
        db.set_study_status(sid, "Mastered", on=self.D0)
        self.assertAlmostEqual(self.xp(), XP_STUDY)
        reviews = db.get_study_reviews(sid)
        self.assertEqual([(r["review_no"], r["due_date"]) for r in reviews], [(1, "2025-03-11")])

    def test_review_series_follows_review_days_when_on_time(self):
        sid = db.add_study_session("Git")
        db.set_study_status(sid, "Mastered", on=self.D0)
        for _ in REVIEW_DAYS:
            pending = [r for r in db.get_study_reviews(sid) if not r["done_date"]][0]
            db.complete_review(pending["id"], on=date.fromisoformat(pending["due_date"]))
        reviews = db.get_study_reviews(sid)
        due_offsets = [(date.fromisoformat(r["due_date"]) - self.D0).days for r in reviews]
        self.assertEqual(tuple(due_offsets), REVIEW_DAYS)
        self.assertTrue(all(r["done_date"] for r in reviews))
        self.assertAlmostEqual(self.xp(), XP_STUDY + XP_REVIEW * len(REVIEW_DAYS))

    def test_struggled_review_repeats_tomorrow(self):
        sid = db.add_study_session("Regex")
        db.set_study_status(sid, "Mastered", on=self.D0)
        first = db.get_study_reviews(sid)[0]
        db.complete_review(first["id"], remembered=False, on=date(2025, 3, 11))
        pending = [r for r in db.get_study_reviews(sid) if not r["done_date"]]
        self.assertEqual([(r["review_no"], r["due_date"]) for r in pending], [(1, "2025-03-12")])

    def test_projects_can_skip_reviews(self):
        sid = db.add_study_session("Portfolio project")
        db.set_study_needs_review(sid, False)
        db.set_study_status(sid, "Mastered", on=self.D0)
        self.assertEqual(db.get_study_reviews(sid), [])
        db.set_study_needs_review(sid, True, on=self.D0)  # turning it back on starts the series
        self.assertEqual(len(db.get_study_reviews(sid)), 1)
        db.set_study_needs_review(sid, False)
        self.assertEqual(db.get_study_reviews(sid), [])

    def test_reopening_a_chapter_removes_xp_and_pending_reviews(self):
        sid = db.add_study_session("Git")
        db.set_study_status(sid, "Mastered", on=self.D0)
        db.set_study_status(sid, "Reviewing")
        self.assertAlmostEqual(self.xp(), 0.0)
        self.assertEqual(db.get_study_reviews(sid), [])
        self.assertEqual(self.chapter(sid)["mastered_at"], "")

    def test_due_reviews_listing_and_chapter_order(self):
        a = db.add_study_session("Old mastered")
        b = db.add_study_session("Active one")
        db.set_study_status(a, "Mastered", on=date.today() - timedelta(days=5))
        db.add_journal_entry(b, "Working through exercises 1 to 10")
        due = db.get_pending_reviews(until=date.today())
        self.assertEqual([(r["topic"], r["review_no"]) for r in due], [("Old mastered", 1)])
        # a chapter with a review due is listed first
        self.assertEqual([c["topic"] for c in db.get_study_sessions()], ["Old mastered", "Active one"])
        self.assertEqual(db.get_study_sessions()[0]["reviews_due"], 1)

    def test_old_study_rows_are_migrated(self):
        old = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, old, True)
        with mock.patch.dict(os.environ, {"APPDATA": old}):
            conn = db.get_connection()
            conn.execute("""CREATE TABLE study_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
                source TEXT DEFAULT 'FIAP / Alura', eli5 TEXT DEFAULT '', code_sandbox TEXT DEFAULT '',
                break_test TEXT DEFAULT '', recall_questions TEXT DEFAULT '', status TEXT DEFAULT 'In Progress',
                active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("INSERT INTO study_sessions (topic) VALUES ('Old in progress')")
            conn.execute("INSERT INTO study_sessions (topic, status, updated_at) "
                         "VALUES ('Old mastered', 'Mastered', '2025-01-02 10:00:00')")
            conn.commit()
            conn.close()
            db.init_db()
            by_topic = {c["topic"]: c for c in db.get_study_sessions()}
            self.assertEqual(by_topic["Old in progress"]["status"], "Studying")
            self.assertEqual(by_topic["Old mastered"]["mastered_at"], "2025-01-02")
            self.assertTrue(by_topic["Old mastered"]["needs_review"])
            self.assertEqual(db.get_pending_reviews(), [])  # no surprise backlog of old reviews

    def test_update_rejects_status_and_unknown_fields(self):
        sid = db.add_study_session("X")
        with self.assertRaises(ValueError):
            db.update_study_session(sid, status="Mastered")


if __name__ == "__main__":
    unittest.main()
