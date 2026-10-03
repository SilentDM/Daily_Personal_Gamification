"""Database layer tests. Run with:  python -m unittest discover tests

Every test gets a throwaway %APPDATA%, so the real database is never touched.
"""
import os
import sys
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db  # noqa: E402
import secure  # noqa: E402
from constants import XP_QUEST  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
