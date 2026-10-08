"""Analytics for the Graphs tab (fixed dates, throwaway database)."""
import unittest
from datetime import date, timedelta
from unittest import mock

from test_database import DbTestCase  # noqa: F401  (sets up sys.path and a temp APPDATA)

import ai_gemini  # noqa: E402
import ai_weekly  # noqa: E402
import analytics as an  # noqa: E402
import database as db  # noqa: E402

TODAY = date(2026, 10, 7)  # a Wednesday


def log(activity_id, day, status, score):
    iso = day.isocalendar()
    db.save_log(activity_id, iso[0], iso[1], iso[2] - 1, status, score)


class AnalyticsTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.gym = db.add_activity("Gym", "Health")
        self.read = db.add_activity("Read", "Study")
        self.smoke = db.add_activity("Smoking", "Vice / Avoid", is_negative=True)

    def test_period_bounds(self):
        self.assertEqual(an.period_bounds("7d", TODAY),
                         (date(2026, 10, 1), TODAY, date(2026, 9, 24), date(2026, 9, 30)))
        start, end, ps, pe = an.period_bounds("1y", TODAY)
        self.assertEqual(((end - start).days + 1, (pe - ps).days + 1, pe + timedelta(days=1)), (365, 365, start))

    def test_daily_scores_ignore_deleted_habits_and_other_periods(self):
        log(self.gym, TODAY, "Excellent", 10)
        log(self.read, TODAY, "A Little", 4)
        log(self.gym, TODAY - timedelta(days=30), "Ok", 7)  # outside 7d
        old = db.add_activity("Old")
        log(old, TODAY, "Skipped", 0)
        db.delete_activity(old)
        self.assertEqual(an.daily_scores(*an.period_bounds("7d", TODAY)[:2]), {TODAY: 7.0})

    def test_score_series_daily_then_weekly(self):
        log(self.gym, TODAY, "Excellent", 10)
        daily = an.score_series("7d", TODAY)
        self.assertEqual(len(daily), 7)
        self.assertEqual(daily[-1][2], 10.0)
        self.assertIsNone(daily[0][2])
        weekly = an.score_series("12w", TODAY)
        self.assertTrue(12 <= len(weekly) <= 13)
        self.assertEqual(weekly[-1][2], 10.0)

    def test_habit_matrix_days_and_weeks(self):
        log(self.gym, TODAY, "Ok", 7)
        log(self.gym, TODAY - timedelta(days=1), "Excellent", 10)
        cols, rows = an.habit_matrix("7d", TODAY)
        self.assertEqual(len(cols), 7)
        gym = rows[0]
        self.assertEqual((gym[0], gym[2][-1], gym[2][-2], gym[3][-1]), ("Gym", 7, 10, "Ok"))
        self.assertIsNone(rows[1][2][-1])
        cols, rows = an.habit_matrix("12w", TODAY)
        self.assertEqual(rows[0][2][-1], 8.5)  # both days fall in this week
        self.assertEqual(rows[0][3][-1], "2 days")

    def test_ranking_strongest_first(self):
        for i in range(3):
            log(self.gym, TODAY - timedelta(days=i), "Excellent", 10)
            log(self.read, TODAY - timedelta(days=i), "A Little", 4)
        log(self.smoke, TODAY, "Resisted", 10)
        ranking = an.habit_ranking("7d", TODAY)
        self.assertEqual([r[0] for r in ranking], ["Gym", "Smoking", "Read"])  # ties: more days logged first
        self.assertEqual(ranking[0][2:], (10.0, 3, 7, 0))

    def test_weekday_pattern(self):
        log(self.gym, date(2026, 10, 5), "Excellent", 10)  # Monday
        log(self.gym, date(2026, 9, 28), "Ok", 7)          # Monday
        log(self.gym, date(2026, 10, 6), "Skipped", 0)     # Tuesday
        pattern = dict((d, (avg, n)) for d, avg, n in an.weekday_pattern("30d", TODAY))
        self.assertEqual(pattern["Mon"], (8.5, 2))
        self.assertEqual(pattern["Tue"], (0.0, 1))
        self.assertEqual(pattern["Sun"], (None, 0))

    def test_year_map_shape(self):
        log(self.gym, TODAY, "Ok", 7)
        weeks = an.year_map(TODAY)
        self.assertEqual((len(weeks), {len(w) for w in weeks}), (53, {7}))
        last = weeks[-1]
        self.assertEqual(last[2][:2], (TODAY, 7.0))
        self.assertTrue(last[3][2] and not last[2][2])  # Thursday is in the future

    def test_kpis_compare_with_previous_period(self):
        for i in range(3):
            log(self.gym, TODAY - timedelta(days=i), "Excellent", 10)
        log(self.gym, TODAY - timedelta(days=8), "A Little", 4)
        sid = db.add_study_session("Docker")
        db.add_journal_entry(sid, "Images and containers", minutes=45, entry_date=TODAY.isoformat())
        k = an.kpis("7d", TODAY)
        cur, prev = k["current"], k["previous"]
        self.assertEqual((cur["avg_score"], cur["days_logged"], cur["best_streak"], cur["study_minutes"]),
                         (10.0, 3, 3, 45))
        self.assertEqual((prev["avg_score"], prev["days_logged"], prev["best_streak"]), (4.0, 1, 0))
        self.assertGreater(cur["xp"], prev["xp"])

    def test_weekly_series_counts(self):
        sid = db.add_study_session("SQL")
        db.add_journal_entry(sid, "Joins and indexes", minutes=30, entry_date=TODAY.isoformat())
        db.set_study_status(sid, "Mastered", on=TODAY - timedelta(days=2))
        review = db.get_study_reviews(sid)[0]
        db.complete_review(review["id"], on=TODAY)
        q = db.add_quest("Taxes")
        db.complete_quest(q, on=TODAY)
        w = db.add_quest("Weekly review", repeat="weekly")
        db.complete_quest(w, on=TODAY)
        this_week = an.weekly_series("7d", TODAY)[-1]
        self.assertEqual(this_week["week"], date(2026, 10, 5))
        self.assertEqual((this_week["study_minutes"], this_week["reviews"], this_week["quests"]), (30, 1, 2))
        self.assertGreater(this_week["xp"], 0)


    def test_rest_is_visible_but_never_scored(self):
        log(self.gym, TODAY, "Excellent", 10)
        log(self.read, TODAY, "Rest", None)
        log(self.read, TODAY - timedelta(days=1), "Rest", None)  # a rest-only day
        start, end = an.period_bounds("7d", TODAY)[:2]
        self.assertEqual(an.daily_scores(start, end), {TODAY: 10.0})
        self.assertEqual(an.rest_only_days(start, end), {TODAY - timedelta(days=1)})
        cols, rows = an.habit_matrix("7d", TODAY)
        read = rows[1]
        self.assertEqual((read[2][-1], read[3][-1], read[4][-1]), (None, "Rest", 1))
        ranking = {r[0]: r for r in an.habit_ranking("7d", TODAY)}
        self.assertNotIn("Read", ranking)  # no scored answers -> not ranked
        log(self.read, TODAY - timedelta(days=2), "Ok", 7)
        ranking = {r[0]: r for r in an.habit_ranking("7d", TODAY)}
        self.assertEqual(ranking["Read"][2:], (7.0, 1, 7, 2))
        k = an.kpis("7d", TODAY)["current"]
        self.assertEqual((k["days_logged"], k["rest_days"], k["avg_score"]), (3, 2, 8.5))
        year = an.year_map(TODAY)
        flags = {d: r for wk in year for d, v, f, r in wk}
        self.assertTrue(flags[TODAY - timedelta(days=1)])
        self.assertFalse(flags[TODAY])

    def test_best_streak_counts_rest_only_days(self):
        log(self.gym, TODAY - timedelta(days=2), "Excellent", 10)
        log(self.gym, TODAY - timedelta(days=1), "Rest", None)
        log(self.gym, TODAY, "Ok", 7)
        self.assertEqual(an.kpis("7d", TODAY)["current"]["best_streak"], 3)


class WeeklySummaryTests(DbTestCase):
    def test_context_and_cache_per_week(self):
        a = db.add_activity("Meditation")
        log(a, date.today(), "Excellent", 10)
        ctx = ai_weekly.build_context()
        self.assertIn("Meditation: 10.0", ctx)
        self.assertIn("THIS WEEK SO FAR", ctx)

        def fake(prompt, system, schema=None, **kw):
            return schema(text="  A calm, steady week.  "), "models/x"

        with mock.patch.object(ai_gemini, "generate", side_effect=fake):
            self.assertEqual(ai_weekly.generate(), "A calm, steady week.")
        self.assertEqual(ai_weekly.cached(), "A calm, steady week.")
        self.assertIsNone(ai_weekly.cached(date.today() + timedelta(days=7)))

    def test_no_key_no_call(self):
        with mock.patch.object(ai_gemini, "get_api_key", return_value=""):
            self.assertFalse(ai_weekly.ensure())


if __name__ == "__main__":
    unittest.main()
