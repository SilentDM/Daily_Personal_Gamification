"""AI review tests with a fake Gemini client: no network, no real key, no keyring access."""
import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

from test_database import DbTestCase  # noqa: F401  (also sets up sys.path)

import ai_gemini  # noqa: E402
import ai_review  # noqa: E402
import database as db  # noqa: E402

needs_genai = unittest.skipUnless(ai_gemini.AVAILABLE, "google-genai not installed")


class RateLimit(Exception):
    code = 429


class BadKey(Exception):
    code = 400

    def __str__(self):
        return "400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key. API_KEY_INVALID"


def pack_json(**overrides):
    pack = {
        "summary": "Docker packages apps with their dependencies.",
        "key_concepts": [{"name": "Image", "explanation": "Read-only template."}],
        "gaps": [{"issue": "Said volumes are deleted with the container", "correction": "Named volumes persist."}],
        "questions": [{"stage": s, "kind": "recall", "question": f"Q stage {s}", "answer": f"A stage {s}"}
                      for s in (1, 1, 2, 3, 4)],
    }
    pack.update(overrides)
    return json.dumps(pack)


class FakeClient:
    """behaviour: {model_name: exception or response text}; models listed in that order."""

    def __init__(self, behaviour, listed=None):
        self.behaviour = behaviour
        self.calls = []
        names = listed or list(behaviour)
        self.models = SimpleNamespace(
            list=lambda: [SimpleNamespace(name=n, supported_actions=["generateContent"]) for n in names],
            generate_content=self._generate,
        )

    def _generate(self, model, contents, config):
        self.calls.append(model)
        result = self.behaviour[model]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)


class AiTestCase(DbTestCase):
    def setUp(self):
        super().setUp()
        key = mock.patch.object(ai_gemini, "get_api_key", return_value="test-key")
        key.start()
        self.addCleanup(key.stop)

    def use_client(self, client):
        patcher = mock.patch.object(ai_gemini, "_client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return client


class RankModelsTests(unittest.TestCase):
    def test_stable_flash_first_pro_last_and_non_text_models_dropped(self):
        models = [(n, ["generateContent"]) for n in (
            "models/gemini-2.5-pro", "models/gemini-2.5-flash", "models/gemini-2.5-flash-lite",
            "models/gemini-2.0-flash", "models/gemini-3.0-flash-preview", "models/gemini-2.5-flash-preview-tts",
            "models/gemma-3-27b-it", "models/gemini-2.0-flash-live")]
        models.append(("models/text-embedding-004", ["embedContent"]))
        self.assertEqual(ai_gemini.rank_models(models), [
            "models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro", "models/gemini-3.0-flash-preview"])


@needs_genai
class GenerateTests(AiTestCase):
    def test_falls_back_on_rate_limit_and_returns_parsed_schema(self):
        client = self.use_client(FakeClient({"models/gemini-2.5-flash": RateLimit("429 RESOURCE_EXHAUSTED"),
                                             "models/gemini-2.0-flash": pack_json()}))
        pack, model = ai_gemini.generate("prompt", "system", schema=ai_review.ReviewPack)
        self.assertEqual(model, "models/gemini-2.0-flash")
        self.assertEqual(pack.key_concepts[0].name, "Image")
        self.assertEqual(client.calls, ["models/gemini-2.5-flash", "models/gemini-2.0-flash"])

    def test_invalid_json_from_one_model_tries_the_next(self):
        self.use_client(FakeClient({"models/gemini-2.5-flash": "not json {",
                                    "models/gemini-2.0-flash": pack_json()}))
        _, model = ai_gemini.generate("prompt", "system", schema=ai_review.ReviewPack)
        self.assertEqual(model, "models/gemini-2.0-flash")

    def test_bad_key_stops_immediately(self):
        client = self.use_client(FakeClient({"models/gemini-2.5-flash": BadKey(),
                                             "models/gemini-2.0-flash": pack_json()}))
        with self.assertRaisesRegex(ai_gemini.AIError, "rejected the API key"):
            ai_gemini.generate("prompt", "system")
        self.assertEqual(client.calls, ["models/gemini-2.5-flash"])

    def test_all_models_rate_limited_gives_quota_message(self):
        self.use_client(FakeClient({"models/gemini-2.5-flash": RateLimit("429"),
                                    "models/gemini-2.0-flash": RateLimit("quota exceeded")}))
        with self.assertRaisesRegex(ai_gemini.AIError, "quota"):
            ai_gemini.generate("prompt", "system")

    def test_model_list_is_cached_and_preferred_model_goes_first(self):
        client = self.use_client(FakeClient({"models/gemini-2.5-flash": "a", "models/gemini-2.0-flash": "b"}))
        ai_gemini.generate("p", "s")
        self.assertIn("gemini-2.5-flash", db.get_hud_settings()[ai_gemini.SETTING_MODELS])
        client.models.list = lambda: self.fail("model list should come from the cache")
        db.set_hud_setting(ai_gemini.SETTING_PREFERRED, "gemini-2.0-flash")
        text, model = ai_gemini.generate("p", "s")
        self.assertEqual((text, model), ("b", "models/gemini-2.0-flash"))

    def test_no_key_raises_not_configured(self):
        with mock.patch.object(ai_gemini, "get_api_key", return_value=""):
            with self.assertRaises(ai_gemini.AINotConfigured):
                ai_gemini.generate("p", "s")


class PromptTests(DbTestCase):
    def test_prompt_has_journal_chronologically_and_only_filled_wrap_up(self):
        sid = db.add_study_session("Docker", "Alura")
        db.add_journal_entry(sid, "First: images vs containers", minutes=30, entry_date="2025-03-01")
        db.add_journal_entry(sid, "Second: volumes", next_step="compose", entry_date="2025-03-02")
        db.update_study_session(sid, eli5="Boxes for apps")
        prompt = ai_review.build_pack_prompt(db.get_study_session(sid), db.get_journal(sid))
        self.assertLess(prompt.index("First: images"), prompt.index("Second: volumes"))
        self.assertIn("30 min", prompt)
        self.assertIn("(next step: compose)", prompt)
        self.assertIn("Boxes for apps", prompt)
        self.assertNotIn("Toy Sandbox", prompt)  # template-only boxes are left out

    def test_long_journals_keep_the_newest_entries(self):
        sid = db.add_study_session("Long")
        db.add_journal_entry(sid, "OLD " + "x" * 50_000, entry_date="2025-01-01")
        db.add_journal_entry(sid, "NEW " + "y" * 20_000, entry_date="2025-02-01")
        prompt = ai_review.build_pack_prompt(db.get_study_session(sid), db.get_journal(sid))
        self.assertIn("NEW ", prompt)
        self.assertNotIn("OLD ", prompt)
        self.assertLessEqual(len(prompt), ai_review.MAX_PROMPT_CHARS + 500)

    def test_questions_for_stage(self):
        pack = json.loads(pack_json())
        self.assertEqual([q["question"] for q in ai_review.questions_for_stage(pack, 1)], ["Q stage 1", "Q stage 1"])
        self.assertEqual([q["question"] for q in ai_review.questions_for_stage(pack, 9)], ["Q stage 4"])
        self.assertEqual(len(ai_review.questions_for_stage(dict(pack, questions=[
            {"stage": 2, "question": "x", "answer": "y"}]), 1)), 1)  # empty stage -> all questions


@needs_genai
class PackTests(AiTestCase):
    def mastered(self, topic="Docker"):
        sid = db.add_study_session(topic)
        db.add_journal_entry(sid, "Images vs containers, port mapping with -p")
        db.set_study_status(sid, "Mastered", on=date(2025, 3, 10))
        return sid

    def test_generate_pack_stores_ready_content(self):
        sid = self.mastered()
        self.use_client(FakeClient({"models/gemini-2.5-flash": pack_json()}))
        self.assertTrue(ai_review.generate_pack(sid))
        pack = db.get_ai_pack(sid)
        self.assertEqual((pack["status"], pack["model"], pack["attempts"]), ("ready", "gemini-2.5-flash", 0))
        self.assertEqual(pack["content"]["gaps"][0]["correction"], "Named volumes persist.")

    def test_failure_is_retried_later_and_regeneration_failure_keeps_old_pack(self):
        sid = self.mastered()
        self.use_client(FakeClient({"models/gemini-2.5-flash": RateLimit("429")}))
        self.assertFalse(ai_review.generate_pack(sid))
        pack = db.get_ai_pack(sid)
        self.assertEqual((pack["status"], pack["attempts"]), ("failed", 1))
        self.assertIn("quota", pack["error"])
        self.assertEqual(db.get_ai_packs_to_generate(), [])  # not before the retry window
        self.assertEqual(db.get_ai_packs_to_generate(retry_after_minutes=0), [sid])

        self.use_client(FakeClient({"models/gemini-2.5-flash": pack_json()}))
        ai_review.generate_pack(sid)
        self.use_client(FakeClient({"models/gemini-2.5-flash": RateLimit("429")}))
        ai_review.generate_pack(sid)
        pack = db.get_ai_pack(sid)
        self.assertEqual(pack["status"], "failed")
        self.assertIsNotNone(pack["content"])  # the previous good pack is still usable

    def test_without_key_the_pack_waits_without_using_attempts(self):
        sid = self.mastered()
        with mock.patch.object(ai_gemini, "get_api_key", return_value=""):
            ai_review.generate_pack(sid)
        pack = db.get_ai_pack(sid)
        self.assertEqual((pack["status"], pack["attempts"]), ("pending", 0))
        self.assertEqual(db.get_ai_packs_to_generate(), [sid])

    def test_queue_on_mastery_respects_the_auto_setting(self):
        sid = self.mastered()
        with mock.patch.object(ai_review, "start_generation") as start:
            ai_review.set_auto_enabled(False)
            ai_review.queue_on_mastery(sid)
            start.assert_not_called()
            self.assertIsNone(db.get_ai_pack(sid))
            ai_review.set_auto_enabled(True)
            ai_review.queue_on_mastery(sid)
            start.assert_called_once()
        self.assertEqual(db.get_ai_pack(sid)["status"], "pending")

    def test_projects_and_unmastered_chapters_are_not_generated(self):
        sid = self.mastered()
        db.set_ai_pack(sid, "pending")
        db.set_study_needs_review(sid, False)
        self.assertEqual(db.get_ai_packs_to_generate(), [])
        self.assertEqual(db.get_chapters_missing_ai_pack(), [])

    def test_grade_answer(self):
        self.use_client(FakeClient({"models/gemini-2.5-flash": json.dumps(
            {"verdict": "partial", "feedback": "Good start", "missing": ["named volumes"]})}))
        grade = ai_review.grade_answer("Docker", "Do volumes persist?", "Named volumes do", "Yes")
        self.assertEqual((grade.verdict, grade.missing), ("partial", ["named volumes"]))


if __name__ == "__main__":
    unittest.main()
