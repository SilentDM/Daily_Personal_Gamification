"""Translation checks: every text shown through tr()/trn() has a Portuguese version with the same placeholders,
and the data values shown on screen (answers, categories, options…) are translated too."""
import ast
import string
import unittest
from datetime import date
from pathlib import Path

from test_database import DbTestCase  # noqa: F401  (also sets up sys.path)

import database as db  # noqa: E402
import i18n  # noqa: E402
from i18n_pt import PT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# helpers that pass their first argument through tr()
INDIRECT = {"_hint", "_card", "_switch", "_dropdown", "_section_title", "scale_legend"}


def used_keys():
    """{text: 'file:line'} for every literal given to tr()/trn() (or to a helper that translates)."""
    keys = {}
    for path in sorted(ROOT.glob("*.py")):
        if path.name == "i18n_pt.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            n = 2 if name == "trn" else 1 if name == "tr" or name in INDIRECT else 0
            for arg in node.args[:n]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.setdefault(arg.value, f"{path.name}:{node.lineno}")
    return keys


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class TranslationCoverageTests(unittest.TestCase):
    def test_every_tr_text_has_a_portuguese_version(self):
        missing = {k: where for k, where in used_keys().items() if k not in PT}
        self.assertEqual(missing, {}, "add these to i18n_pt.py")

    def test_every_placeholder_gets_a_value(self):
        """tr("… {x} …") must be called with x=… (a missing one only crashes when that screen shows up)."""
        problems = []
        for path in sorted(ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ("tr", "trn")):
                    continue
                if any(kw.arg is None for kw in node.keywords):
                    continue  # **kwargs: can't check statically
                given = {kw.arg for kw in node.keywords} | ({"n"} if node.func.id == "trn" else set())
                texts = node.args[:2] if node.func.id == "trn" else node.args[:1]
                for arg in texts:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        needed = placeholders(arg.value)
                        if not needed <= given:
                            problems.append(f"{path.name}:{node.lineno} {arg.value!r} needs {needed - given}")
                        if given - needed and not (node.func.id == "trn" and given - needed == {"n"}):
                            problems.append(f"{path.name}:{node.lineno} {arg.value!r} gets unused {given - needed}")
        self.assertEqual(problems, [])

    def test_placeholders_match(self):
        bad = {k: v for k, v in PT.items() if placeholders(k) != placeholders(v)}
        self.assertEqual(bad, {})

    def test_data_values_shown_on_screen_are_translated(self):
        import calendar_view
        import constants
        import diary_view
        import settings
        import study_view
        import todo_view
        import wallpaper as wp
        values = set(constants.POSITIVE_SCORES) | set(constants.NEGATIVE_SCORES) | {constants.REST_STATUS}
        values -= {"-"}
        values |= set(constants.CATEGORIES) | set(constants.QUEST_TYPES) | set(constants.QUEST_DIFFICULTY_XP)
        values |= set(constants.QUEST_STATUSES) | set(constants.STUDY_STAGES)
        values |= {constants.get_rank_title(lv) for lv in range(1, 101)}
        values |= set(todo_view.REPEAT_LABELS.values()) | set(settings.OPTIONAL_TABS.values())
        values |= set(settings.REPLY_MODES.values()) | set(settings.VOICES.values())
        values |= set(wp.POSITIONS) | set(wp.COLOR_PALETTES) | set(wp.BG_MODES) | set(wp.SIZES) | set(wp.BLOCKS.values())
        values |= set(calendar_view.EVENT_COLORS) | {t for _, t in calendar_view.DURATION_OPTIONS}
        values |= {t for _, t in calendar_view.REMINDER_OPTIONS + calendar_view.ALL_DAY_REMINDER_OPTIONS}
        values |= {w for _, w in calendar_view.CalendarView.DOC_KIND_STYLE.values()}
        values |= set(db.DOC_TYPES)
        values |= set(study_view.FILTER_EMPTY.values()) | set(study_view.STAGE_FOCUS.values())
        values |= {v[0] for v in study_view.VERDICT_STYLE.values()}
        values |= {s for s in study_view.SOURCES if not s.isupper() and s not in ("Alura", "Nano Courses")}
        values |= {study_view.DEFAULT_ELI5, study_view.DEFAULT_CODE, study_view.DEFAULT_BREAK, study_view.DEFAULT_RECALL}
        values |= {label for _, label, _, _, _ in study_view.WRAP_UP_FIELDS}
        values |= {label for _, _, label in diary_view.MOODS} | {label for _, label in diary_view.ENERGY}
        for title, _, intro, spec in diary_view.EXERCISES.values():
            values |= {title, intro} | {x for _, label, hint, _ in spec for x in (label, hint) if x}
        missing = sorted(v for v in values if v not in PT)
        self.assertEqual(missing, [])

    def test_wrap_up_templates_keep_their_markers(self):
        """is_filled() and the flashcard parser rely on •, ->, Q1:/A1: and the code stub in both languages."""
        import study_view
        for template in (study_view.DEFAULT_ELI5, study_view.DEFAULT_BREAK, study_view.DEFAULT_CODE,
                         study_view.DEFAULT_RECALL):
            self.assertFalse(study_view.is_filled(PT[template], template))


class LanguageTests(DbTestCase):
    def tearDown(self):
        i18n.set_language("en")
        super().tearDown()

    def test_tr_and_plural(self):
        i18n.set_language("pt")
        self.assertEqual(i18n.tr("Save"), "Salvar")
        self.assertEqual(i18n.trn("{n} day", "{n} days", 1), "1 dia")
        self.assertEqual(i18n.trn("{n} day", "{n} days", 3), "3 dias")
        self.assertEqual(i18n.tr("A text nobody translated"), "A text nobody translated")  # falls back to English
        self.assertEqual(i18n.tr('Search: "{text}"', text="gym"), 'Busca: "gym"')  # any placeholder name works
        i18n.set_language("en")
        self.assertEqual(i18n.trn("{n} day", "{n} days", 3), "3 days")

    def test_dates(self):
        d = date(2026, 10, 12)
        i18n.set_language("pt")
        self.assertEqual(i18n.fmt_long(d), "Segunda-feira, 12 de outubro de 2026")
        self.assertEqual(i18n.fmt_month_year(d), "Outubro de 2026")
        self.assertEqual(i18n.fmt_short(d), "Seg 12/10/2026")
        i18n.set_language("en")
        self.assertEqual(i18n.fmt_long(d), "Monday, 12 October 2026")

    def test_saved_choice_and_old_setting(self):
        db.set_hud_setting("ai_language", "English")  # the old "AI & messages language"
        self.assertEqual(i18n.stored_language(), "en")
        db.set_hud_setting("ai_language", "Português (Brasil)")
        self.assertEqual(i18n.stored_language(), "pt")
        i18n.save_language("en")
        self.assertEqual(i18n.stored_language(), "en")
        self.assertEqual(i18n.language(), "en")  # the running app keeps its language until restarted

    def test_ai_and_assistant_follow_the_app_language(self):
        import ai_insight
        import messages
        i18n.set_language("pt")
        self.assertEqual((ai_insight.language(), messages.lang(), i18n.ai_language_name()),
                         ("Português (Brasil)", "pt", "Brazilian Portuguese"))
        i18n.set_language("en")
        self.assertEqual((ai_insight.language(), messages.lang()), ("English", "en"))

    def test_renewal_quests_are_created_in_the_app_language(self):
        i18n.set_language("pt")
        db.add_tracked_doc("CNH", "CNH", date.today().isoformat())
        db.sync_renewal_quests()
        quest = db.get_quests(statuses=("Active",))[0]
        self.assertEqual(quest["title"], "Renovar CNH")


if __name__ == "__main__":
    unittest.main()
