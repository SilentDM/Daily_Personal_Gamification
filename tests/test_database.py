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
from constants import XP_QUEST, XP_STUDY, XP_STUDY_LOG, XP_REVIEW, REVIEW_DAYS  # noqa: E402


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


class QuestTests(DbTestCase):
    def test_quest_xp_awarded_once_and_removed_on_reopen(self):
        t = db.add_task("Taxes")
        db.set_task_manual_status(t, True)
        db.set_task_manual_status(t, True)
        self.assertAlmostEqual(self.xp(), XP_QUEST)
        db.set_task_manual_status(t, False)
        self.assertAlmostEqual(self.xp(), 0.0)

    def test_progress_comes_from_subquests(self):
        t = db.add_task("Trip")
        s1 = db.add_subtask(t, "Book flight")
        db.add_subtask(t, "Book hotel")
        db.update_subtask_status(s1, "Complete")
        task = next(r for r in db.get_tasks() if r[0] == t)
        self.assertEqual(task[2], "In Progress")
        self.assertEqual(len(task[6]), 2)
        self.assertAlmostEqual(task[7], 50.0)


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
    def test_update_keeps_secondary_info(self):
        d = db.add_document("Vehicles", "CRLV / Carro", "Car", "123", "Renavam 999")
        db.update_document(d, "Vehicles", "CRLV / Carro", "Car", "456", "", "2030-01-01", "")
        doc = db.get_documents()[0]
        self.assertEqual((doc[4], doc[5], doc[7]), ("456", "Renavam 999", "2030-01-01"))

    @unittest.skipUnless(secure.AVAILABLE, "cryptography not installed")
    def test_sensitive_fields_are_encrypted_at_rest(self):
        db.add_document("Identity", "CPF", "Me", "111.222.333-44")
        conn = db.get_connection()
        raw = conn.execute("SELECT doc_number FROM personal_documents").fetchone()[0]
        conn.close()
        self.assertTrue(raw.startswith(secure.PREFIX))
        self.assertEqual(db.get_documents()[0][4], "111.222.333-44")


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
