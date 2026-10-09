"""Options + Telegram assistant tests: fake bot, fake Gemini, temp database. No network, no keyring."""
import time
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from test_database import DbTestCase  # noqa: F401  (also sets up sys.path)

import ai_gemini  # noqa: E402
import assistant as assistant_mod  # noqa: E402
import assistant_tools as tools  # noqa: E402
import database as db  # noqa: E402
import notifier as notifier_mod  # noqa: E402
import settings  # noqa: E402

CHAT = "4242"


class FakeBot:
    token = "fake-token"

    def __init__(self, *a, **kw):
        self.sent, self.voices, self.edits, self.answers, self.actions = [], [], [], [], []

    def get_me(self):
        return {"username": "test_bot"}

    def get_updates(self, offset=None, timeout=50):
        time.sleep(0.05)
        return []

    def send_message(self, chat_id, text, buttons=None, reply_to=None):
        self.sent.append((str(chat_id), text, buttons))
        return {"message_id": len(self.sent)}

    def send_voice(self, chat_id, mp3, caption=None):
        self.voices.append((str(chat_id), mp3, caption))

    def edit_text(self, chat_id, message_id, text, buttons=None):
        self.edits.append((message_id, text, buttons))

    def answer_callback(self, callback_id, text=None):
        self.answers.append((callback_id, text))

    def send_chat_action(self, chat_id, action="typing"):
        self.actions.append(action)

    def download_file(self, file_id):
        return b"OGG-AUDIO"


def text_update(text, chat=CHAT, age=0):
    return {"update_id": 1, "message": {"chat": {"id": int(chat)}, "text": text, "date": int(time.time()) - age}}


class AssistantTestCase(DbTestCase):
    def setUp(self):
        super().setUp()
        self.replies = []
        self.calls = []

        def fake_generate(prompt, system, **kw):
            self.calls.append((prompt, system, kw))
            return (self.replies.pop(0) if self.replies else "Tudo certo!"), "models/fake"

        self.bot = FakeBot()
        self.a = assistant_mod.Assistant(bot_factory=lambda: self.bot, generate=fake_generate,
                                         synthesize=lambda text, lang, gender: b"MP3")
        self.a.bot = self.bot
        settings.set("tg_enabled", True)

    def pair(self):
        settings.set("tg_chat_id", CHAT)


# ---------------------------------------------------------------------- settings
class SettingsTests(DbTestCase):
    def test_defaults_and_empty_values(self):
        self.assertEqual(settings.get("passing_score"), "7.0")
        settings.set("passing_score", "")
        self.assertEqual(settings.get("passing_score"), "7.0")  # "" means default here
        settings.set("tg_briefing", "")
        self.assertEqual(settings.get("tg_briefing"), "")        # but "" is "off" for the briefing
        settings.set("close_to_tray", False)
        self.assertFalse(settings.flag("close_to_tray"))

    def test_tabs(self):
        self.assertTrue(settings.tab_enabled("schedule"))
        settings.set_tab_enabled("graphs", False)
        self.assertNotIn("graphs", settings.enabled_tabs())
        settings.set_tab_enabled("graphs", True)
        self.assertEqual(settings.enabled_tabs(), list(settings.OPTIONAL_TABS))  # canonical order kept

    def test_quiet_hours_cross_midnight(self):
        settings.set("quiet_start", "22:30")
        settings.set("quiet_end", "07:00")
        day = date(2026, 10, 9)
        self.assertTrue(settings.in_quiet_hours(datetime.combine(day, datetime.strptime("23:00", "%H:%M").time())))
        self.assertTrue(settings.in_quiet_hours(datetime.combine(day, datetime.strptime("06:59", "%H:%M").time())))
        self.assertFalse(settings.in_quiet_hours(datetime.combine(day, datetime.strptime("07:00", "%H:%M").time())))
        settings.set("quiet_enabled", False)
        self.assertFalse(settings.in_quiet_hours(datetime.combine(day, datetime.strptime("23:00", "%H:%M").time())))

    def test_scoring_rules_are_configurable(self):
        aid = db.add_activity("Gym")
        self.log_today(aid, "Ok", 7)
        self.assertEqual(db.get_current_streak(), 1)
        settings.set("passing_score", "8.0")
        self.assertEqual(db.get_current_streak(), 0)
        settings.set("rest_limit", "0")
        year, week, day_idx = db.get_current_week_info()
        self.assertFalse(db.can_rest(aid, year, week, day_idx))

    def test_sent_keys_persist(self):
        self.assertFalse(db.was_sent("x"))
        db.mark_sent("x")
        db.mark_sent("x")
        self.assertTrue(db.was_sent("x"))


# ---------------------------------------------------------------------- tools
class ToolTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.gym = db.add_activity("Workout / Gym")
        self.smoke = db.add_activity("Smoking", is_negative=True)

    def test_mark_habit_loose_name_and_answer(self):
        r = tools.mark_habit("gym", "ok")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["habit"], r["answer"]), ("Workout / Gym", "Ok"))
        self.assertEqual(db.count_unmarked_today(), 1)

    def test_vices_never_rest_and_no_future(self):
        self.assertFalse(tools.mark_habit("smoking", "Rest")["ok"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(tools.mark_habit("gym", "Ok", tomorrow)["ok"])
        self.assertIn("Options", tools.mark_habit("zzz", "Ok")["error"])

    def test_actions_are_idempotent_within_a_request(self):
        changed = []
        tools.on_data_changed(lambda: changed.append(1))
        self.addCleanup(tools._changed_callbacks.clear)
        with tools.ActionLog():
            first = tools.add_calendar_event("Dentist", date.today().isoformat(), "14:30")
            again = tools.add_calendar_event("Dentist", date.today().isoformat(), "14:30")  # model fallback replay
        self.assertEqual(first["event_id"], again["event_id"])
        self.assertEqual(len(db.get_events_for_date(date.today())), 1)
        self.assertEqual(changed, [1])

    def test_documents_never_expose_numbers(self):
        db.add_tracked_doc("Passport", "Passport", (date.today() + timedelta(days=20)).isoformat())
        doc = tools.get_documents()["documents"][0]
        self.assertNotIn("number", doc)
        self.assertNotIn("notes", doc)

    def test_no_delete_tools(self):
        self.assertFalse([f for f in tools.ALL_TOOLS if "delete" in f.__name__ or "remove" in f.__name__])


# ---------------------------------------------------------------------- bot
class PairingTests(AssistantTestCase):
    def test_wrong_code_is_refused(self):
        self.a.handle_update(text_update("/start 000000" if self.a.pairing_code != "000000" else "/start 1"))
        self.assertEqual(settings.get("tg_chat_id"), "")
        self.assertIn("privado", self.bot.sent[-1][1])

    def test_right_code_pairs(self):
        self.a.handle_update(text_update(f"/start {self.a.pairing_code}"))
        self.assertEqual(settings.get("tg_chat_id"), CHAT)

    def test_unpaired_chat_text_is_not_answered_by_ai(self):
        self.a.handle_update(text_update("hello"))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.bot.sent, [])

    def test_strangers_are_ignored_after_pairing(self):
        self.pair()
        self.a.handle_update(text_update("como está meu dia?", chat="999"))
        self.assertEqual((self.calls, self.bot.sent), ([], []))

    def test_old_messages_are_skipped(self):
        self.pair()
        self.a.handle_update(text_update("oi", age=3600))
        self.assertEqual(self.calls, [])


class ChatTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.pair()

    def test_text_reply_uses_tools_and_memory(self):
        self.replies = ["Seu dia está ótimo."]
        self.a.handle_update(text_update("como está meu dia?"))
        prompt, system, kw = self.calls[0]
        self.assertIs(kw["tools"], tools.ALL_TOOLS)
        self.assertIn("Brazilian Portuguese", system)
        self.assertEqual(self.bot.sent[-1][1], "Seu dia está ótimo.")
        self.a.handle_update(text_update("e amanhã?"))
        self.assertIn("Seu dia está ótimo.", self.calls[1][0])  # short-term memory

    def test_voice_reply_mode(self):
        settings.set("tg_reply_mode", "voice")
        self.a.handle_update(text_update("oi"))
        self.assertEqual(len(self.bot.voices), 1)
        self.assertEqual(self.bot.sent, [])
        settings.set("tg_reply_mode", "both")
        self.a.handle_update(text_update("oi"))
        self.assertEqual(self.bot.voices[-1][2], "Tudo certo!")  # caption carries the text

    def test_voice_falls_back_to_text(self):
        settings.set("tg_reply_mode", "voice")
        self.a._synthesize = lambda *a: b""
        self.a.handle_update(text_update("oi"))
        self.assertEqual(self.bot.sent[-1][1], "Tudo certo!")

    @unittest.skipUnless(ai_gemini.AVAILABLE, "google-genai not installed")
    def test_voice_message_goes_to_gemini_as_audio(self):
        update = {"update_id": 2, "message": {"chat": {"id": int(CHAT)}, "date": int(time.time()),
                                              "voice": {"file_id": "f1", "mime_type": "audio/ogg"}}}
        self.a.handle_update(update)
        prompt = self.calls[0][0]
        self.assertIsInstance(prompt, list)
        self.assertEqual(prompt[1].inline_data.data, b"OGG-AUDIO")

    def test_ai_not_configured(self):
        def no_key(*a, **kw):
            raise ai_gemini.AINotConfigured("no key")
        self.a._generate = no_key
        self.a.handle_update(text_update("oi"))
        self.assertIn("Gemini", self.bot.sent[-1][1])


class CheckinTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.pair()
        self.gym = db.add_activity("Gym")
        self.smoke = db.add_activity("Smoking", is_negative=True)

    def test_keyboard_lists_unanswered_habits(self):
        text, rows = assistant_mod.checkin_keyboard()
        self.assertIn("2", text)
        answers = [b["text"] for b in rows[1]]
        self.assertIn("Rest", answers)
        self.assertNotIn("Rest", [b["text"] for b in rows[3]])  # vices can't rest

    def test_button_press_marks_and_updates_the_message(self):
        self.a.send_checkin()
        today = date.today().isoformat()
        cq = {"id": "cb1", "data": f"h|{self.gym}|{today}|Excellent",
              "message": {"message_id": 7, "chat": {"id": int(CHAT)}}}
        self.a.handle_update({"update_id": 3, "callback_query": cq})
        self.assertEqual(db.count_unmarked_today(), 1)
        self.assertEqual(self.bot.edits[-1][0], 7)
        self.assertIsNotNone(self.bot.edits[-1][2])  # Smoking still asked
        cq["data"] = f"h|{self.smoke}|{today}|Resisted"
        self.a.handle_update({"update_id": 4, "callback_query": cq})
        self.assertIsNone(self.bot.edits[-1][2])
        self.assertIn("10.0", self.bot.edits[-1][1])

    def test_buttons_from_strangers_do_nothing(self):
        cq = {"id": "cb1", "data": f"h|{self.gym}|{date.today().isoformat()}|Ok",
              "message": {"message_id": 7, "chat": {"id": 999}}}
        self.a.handle_update({"update_id": 5, "callback_query": cq})
        self.assertEqual(db.count_unmarked_today(), 2)


# ---------------------------------------------------------------------- notifier
class SyncThread:
    def __init__(self, target, **kw):
        self.target = target

    def start(self):
        self.target()


class NotifierTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.pair()
        settings.set("quiet_enabled", False)
        settings.set("tg_briefing", "")  # tested on its own (it would start a thread)
        self.n = notifier_mod.Notifier(self.a, checkin_time=lambda: "21:30")

    def at(self, hhmm):
        return datetime.combine(date.today(), datetime.strptime(hhmm, "%H:%M").time())

    def texts(self):
        return [t for _, t, _ in self.bot.sent]

    def test_nothing_when_off_or_unpaired(self):
        settings.set("tg_chat_id", "")
        self.n.tick(self.at("10:00"))
        self.assertEqual(self.bot.sent, [])

    def test_calendar_reminder_sent_once_even_after_restart(self):
        db.add_calendar_event("Dentist", date.today().isoformat(), 10, "none", start_minute=30, reminder_min=15)
        self.n.tick(self.at("10:00"))
        self.assertEqual(self.bot.sent, [])
        self.n.tick(self.at("10:16"))
        notifier_mod.Notifier(self.a).tick(self.at("10:20"))  # a new instance = app restarted
        self.assertEqual(len([t for t in self.texts() if "Dentist" in t]), 1)
        self.assertIn("10:30", self.texts()[0])

    def test_quiet_hours_hold_documents(self):
        settings.set("quiet_enabled", True)
        db.add_tracked_doc("Passport", "Passport", (date.today() + timedelta(days=5)).isoformat())
        self.n.tick(self.at("23:00"))
        self.assertEqual(self.bot.sent, [])
        self.n.tick(self.at("10:00"))
        self.assertIn("Passport", self.texts()[0])

    def test_checkin_has_buttons_and_skips_when_all_answered(self):
        aid = db.add_activity("Gym")
        self.n.tick(self.at("21:00"))
        self.assertEqual(self.bot.sent, [])
        self.n.tick(self.at("21:31"))
        self.assertIsNotNone(self.bot.sent[-1][2])
        self.n.tick(self.at("21:40"))
        self.assertEqual(len(self.bot.sent), 1)  # once a day
        self.log_today(aid, "Ok", 7)
        tomorrow = notifier_mod.Notifier(self.a, checkin_time=lambda: "21:30")
        with mock.patch.object(notifier_mod.db, "count_unmarked_today", return_value=0):
            tomorrow._checkin(self.at("21:31") + timedelta(days=1))
        self.assertEqual(len(self.bot.sent), 1)  # nothing left to ask: no message

    def test_briefing_once_with_fallback(self):
        def down(*a, **kw):
            raise ai_gemini.AIError("quota")
        self.a._generate = down
        settings.set("tg_briefing", "07:30")
        db.add_calendar_event("Standup", date.today().isoformat(), 9, "none")
        with mock.patch.object(notifier_mod.threading, "Thread", SyncThread):
            self.n.tick(self.at("07:00"))
            self.n.tick(self.at("07:31"))
            self.n.tick(self.at("08:00"))
        briefings = [t for t in self.texts() if "Standup" in t]
        self.assertEqual(len(briefings), 1)
        self.assertIn("09:00", briefings[0])

    def test_achievements(self):
        self.n.tick(self.at("10:00"))  # first run: baseline, no backlog
        self.assertEqual(self.bot.sent, [])
        qid = db.add_quest("Run 5k", difficulty="Hard")
        db.complete_quest(qid)
        self.n.tick(self.at("10:01"))
        texts = self.texts()
        self.assertTrue(any("Run 5k" in t for t in texts), texts)
        self.assertTrue(any("nível" in t for t in texts), texts)
        self.n.tick(self.at("10:02"))
        self.assertEqual(len(self.bot.sent), len(texts))

    def test_streak_milestone_key_is_stable(self):
        aid = db.add_activity("Gym")
        today = date.today()
        for back in range(1, 4):  # three passing days before today
            d = today - timedelta(days=back)
            iso = d.isocalendar()
            db.save_log(aid, iso[0], iso[1], iso[2] - 1, "Ok", 7)
        self.n.tick(self.at("10:00"))  # baseline run
        self.n.tick(self.at("10:01"))
        self.assertTrue(any("3" in t for t in self.texts()))
        sent = len(self.bot.sent)
        self.n.tick(self.at("10:05"))
        self.assertEqual(len(self.bot.sent), sent)


if __name__ == "__main__":
    unittest.main()
