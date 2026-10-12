"""Diary tests: encryption, exercises XP rules, habit notes, search, PIN, AI reflection (fake Gemini)."""
import json
import unittest
from datetime import date, timedelta
from unittest import mock

from test_database import DbTestCase  # noqa: F401  (also sets up sys.path)

import ai_diary  # noqa: E402
import ai_gemini  # noqa: E402
import analytics as an  # noqa: E402
import assistant_tools as tools  # noqa: E402
import database as db  # noqa: E402
import secure  # noqa: E402
import settings  # noqa: E402
from constants import XP_DIARY_EXERCISE, DIARY_XP_EXERCISES_PER_DAY  # noqa: E402

TODAY = date.today()
LONG = "Today I finally touched my toes while stretching and it felt amazing."


class DiaryPageTests(DbTestCase):
    def test_empty_page(self):
        entry = db.get_diary_entry(TODAY)
        self.assertEqual((entry["body"], entry["mood"]), ("", None))

    def test_partial_saves_and_encryption(self):
        db.save_diary_entry(TODAY, body="Dear diary, secret stuff")
        db.save_diary_entry(TODAY, mood=4)
        db.save_diary_entry(TODAY, energy=9)  # clamped to 5
        entry = db.get_diary_entry(TODAY)
        self.assertEqual((entry["body"], entry["mood"], entry["energy"]), ("Dear diary, secret stuff", 4, 5))
        db.save_diary_entry(TODAY, mood=None)
        self.assertIsNone(db.get_diary_entry(TODAY)["mood"])
        if secure.AVAILABLE:
            conn = db.get_connection()
            raw = conn.execute("SELECT body FROM diary_entries").fetchone()[0]
            conn.close()
            self.assertTrue(raw.startswith(secure.PREFIX))
            self.assertNotIn("secret", raw)

    def test_append_keeps_existing_text(self):
        db.save_diary_entry(TODAY, body="Morning thoughts.")
        db.append_diary(TODAY, "Evening run was great", source="Telegram")
        body = db.get_diary_entry(TODAY)["body"]
        self.assertTrue(body.startswith("Morning thoughts.\n\n["))
        self.assertIn("Telegram] Evening run was great", body)
        with self.assertRaises(ValueError):
            db.append_diary(TODAY, "   ")


class ExerciseTests(DbTestCase):
    def test_xp_needs_real_writing_and_once_per_kind(self):
        self.assertEqual(db.add_diary_exercise(TODAY, "win", {"win": "ok"}), 0)  # too short
        self.assertEqual(db.add_diary_exercise(TODAY, "win", {"win": LONG}), XP_DIARY_EXERCISE)
        self.assertEqual(db.add_diary_exercise(TODAY, "win", {"win": LONG}), 0)  # same kind, same day
        self.assertAlmostEqual(self.xp(), XP_DIARY_EXERCISE)
        with self.assertRaises(ValueError):
            db.add_diary_exercise(TODAY, "win", {"win": "  "})

    def test_daily_cap(self):
        kinds = ["win", "gratitude", "expressive", "thought", "worry"]
        earned = [db.add_diary_exercise(TODAY, k, {"text": LONG}) for k in kinds]
        self.assertEqual(sum(1 for x in earned if x), DIARY_XP_EXERCISES_PER_DAY)

    def test_fields_roundtrip_and_delete_removes_xp(self):
        db.add_diary_exercise(TODAY, "thought", {"situation": "Meeting", "balanced": LONG})
        ex = db.get_diary_exercises(TODAY)[0]
        self.assertEqual(ex["fields"]["situation"], "Meeting")
        db.update_diary_exercise(ex["id"], {"situation": "Big meeting", "balanced": LONG})
        self.assertEqual(db.get_diary_exercises(TODAY)[0]["fields"]["situation"], "Big meeting")
        db.delete_diary_exercise(ex["id"])
        self.assertEqual(db.get_diary_exercises(TODAY), [])
        self.assertAlmostEqual(self.xp(), 0)


class HabitNoteTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.aid = db.add_activity("Stretching", "Health")
        self.log_today(self.aid, "Excellent", 10)

    def test_note_flags_highlights_and_delete(self):
        db.set_habit_note(self.aid, TODAY, "Touched my toes!", highlight=True)
        self.assertEqual(db.habit_note_flags(TODAY, TODAY), {(self.aid, TODAY.isoformat()): True})
        notes = db.get_habit_notes(TODAY)
        self.assertEqual((notes[0]["habit"], notes[0]["status"], notes[0]["note"]),
                         ("Stretching", "Excellent", "Touched my toes!"))
        self.assertEqual(len(db.get_habit_notes(highlights_only=True)), 1)
        db.set_habit_note(self.aid, TODAY, "")
        self.assertEqual(db.habit_note_flags(TODAY, TODAY), {})

    def test_month_and_search(self):
        db.set_habit_note(self.aid, TODAY, "Best stretching session ever", highlight=True)
        db.save_diary_entry(TODAY - timedelta(days=1), body="A calm day at the beach", mood=5)
        db.add_diary_exercise(TODAY, "gratitude", {"one": "Coffee with my sister"})
        month = db.diary_month(TODAY - timedelta(days=1), TODAY)
        self.assertTrue(month[TODAY.isoformat()]["highlight"])
        self.assertEqual(month[(TODAY - timedelta(days=1)).isoformat()]["mood"], 5)
        self.assertEqual([h["where"] for h in db.search_diary("BEACH")], ["page"])
        self.assertEqual([h["where"] for h in db.search_diary("sister")], ["gratitude"])
        self.assertEqual([h["where"] for h in db.search_diary("stretching")], ["Stretching"])
        self.assertEqual(db.search_diary("x"), [])  # too short


class PinTests(DbTestCase):
    def test_pin_and_forgotten_pin_wipes_text_only(self):
        self.assertFalse(db.has_diary_pin())
        db.set_diary_pin("2468")
        self.assertTrue(db.check_diary_pin("2468"))
        self.assertFalse(db.check_diary_pin("1111"))
        self.assertFalse(db.has_doc_pin())  # independent from the Documents PIN
        aid = db.add_activity("Gym")
        db.save_diary_entry(TODAY, body="private", mood=3)
        db.add_diary_exercise(TODAY, "win", {"win": LONG})
        db.set_habit_note(aid, TODAY, "note")
        xp = self.xp()
        db.reset_diary_pin_and_wipe_text()
        entry = db.get_diary_entry(TODAY)
        self.assertEqual((entry["body"], entry["mood"]), ("", 3))
        self.assertEqual((db.get_diary_exercises(TODAY), db.get_habit_notes()), ([], []))
        self.assertFalse(db.has_diary_pin())
        self.assertAlmostEqual(self.xp(), xp)


class TabSettingTests(DbTestCase):
    def test_new_tabs_start_enabled_for_old_settings(self):
        db.set_hud_setting("enabled_tabs", json.dumps(["graphs", "study"]))  # older format, no "diary"
        self.assertEqual(settings.enabled_tabs(), ["graphs", "study", "diary"])
        settings.set_tab_enabled("diary", False)
        self.assertEqual(settings.enabled_tabs(), ["graphs", "study"])
        settings.set_tab_enabled("quests", True)
        self.assertEqual(settings.enabled_tabs(), ["graphs", "quests", "study"])


class AssistantDiaryTests(DbTestCase):
    def test_write_only_tool(self):
        r = tools.write_diary("Hoje alonguei como nunca")
        self.assertTrue(r["ok"], r)
        self.assertIn("alonguei", db.get_diary_entry(TODAY)["body"])
        self.assertNotIn("alonguei", json.dumps(r))  # the tool never echoes diary content
        self.assertFalse([f for f in tools.READ_TOOLS if "diary" in f.__name__])
        settings.set_tab_enabled("diary", False)
        self.assertFalse(tools.write_diary("x")["ok"])


class ReflectionTests(DbTestCase):
    def test_prompt_contains_only_that_day(self):
        aid = db.add_activity("Stretching")
        db.save_diary_entry(TODAY, body="Felt proud today", mood=4)
        db.save_diary_entry(TODAY - timedelta(days=1), body="yesterday secret")
        db.add_diary_exercise(TODAY, "win", {"win": LONG})
        db.set_habit_note(aid, TODAY, "toes!", highlight=True)
        prompt = ai_diary.build_prompt(TODAY, {"win": "Win of the day"})
        for part in ("Felt proud today", "MOOD: 4/5", "Win of the day", "toes!", "[highlight]"):
            self.assertIn(part, prompt)
        self.assertNotIn("yesterday secret", prompt)

    def test_needs_consent_and_content(self):
        with self.assertRaises(ai_gemini.AIError):
            ai_diary.reflect(TODAY)  # no consent
        ai_diary.give_consent()
        with self.assertRaises(ai_gemini.AIError):
            ai_diary.reflect(TODAY)  # nothing written
        db.save_diary_entry(TODAY, body="A hard day, but I went for a walk.")
        with mock.patch.object(ai_gemini, "generate", return_value=("You showed up for yourself.", "m")) as gen:
            self.assertEqual(ai_diary.reflect(TODAY), "You showed up for yourself.")
        self.assertIn("went for a walk", gen.call_args[0][0])
        self.assertEqual(db.get_diary_entry(TODAY)["reflection"], "You showed up for yourself.")


class MoodAnalyticsTests(DbTestCase):
    def test_mood_vs_passing_days(self):
        aid = db.add_activity("Gym")
        self.log_today(aid, "Excellent", 10)
        db.save_diary_entry(TODAY, mood=5)
        good, other = an.mood_vs_habits("7d")
        self.assertEqual(good, (5, 1))
        self.assertIsNone(other)
        self.assertEqual(an.mood_series("7d")[-1][2], 5)


if __name__ == "__main__":
    unittest.main()
