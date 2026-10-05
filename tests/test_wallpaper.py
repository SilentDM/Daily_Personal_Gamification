"""Wallpaper HUD + insight tests. The desktop is never touched (_set/_current_wallpaper are faked)."""
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from PIL import Image

from test_database import DbTestCase  # noqa: F401  (sets up sys.path and a temp APPDATA)

import ai_gemini  # noqa: E402
import ai_insight  # noqa: E402
import database as db  # noqa: E402
import wallpaper as wp  # noqa: E402


class WallpaperTestCase(DbTestCase):
    def setUp(self):
        super().setUp()
        self.set_calls = []
        for name, fake in (("_set_wallpaper", lambda path: self.set_calls.append(path) or True),
                           ("_current_wallpaper", lambda: self.current)):
            patcher = mock.patch.object(wp, name, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.current = ""
        wp._BASE_CACHE.clear()

    def make_image(self, name, size, color):
        path = Path(self.tmp) / name
        Image.new("RGB", size, color).save(path)
        return path


class BlockTests(WallpaperTestCase):
    def test_old_show_flags_are_migrated_and_new_blocks_added(self):
        db.set_hud_setting("show_quests", "false")
        db.set_hud_setting("show_calendar", "false")
        blocks = {b["id"]: b["on"] for b in wp.get_blocks()}
        self.assertEqual(list(blocks), list(wp.BLOCKS))
        self.assertFalse(blocks["quests"])
        self.assertFalse(blocks["calendar"])
        self.assertTrue(blocks["status"] and blocks["documents"])
        self.assertFalse(blocks["insight"])  # needs a key: off until the user turns it on

    def test_saved_order_is_kept_unknown_dropped_missing_appended(self):
        db.set_hud_setting(wp.SETTING_BLOCKS, json.dumps([{"id": "quests", "on": True}, {"id": "nope", "on": True},
                                                          {"id": "status", "on": False}]))
        ids = [b["id"] for b in wp.get_blocks()]
        self.assertEqual(ids[:2], ["quests", "status"])
        self.assertEqual(sorted(ids), sorted(wp.BLOCKS))


class RenderTests(WallpaperTestCase):
    def test_renders_every_layout_and_size_at_several_resolutions(self):
        a = db.add_activity("Gym")
        year, week, day = db.get_current_week_info()
        db.save_log(a, year, week, day, "Ok", 7)
        db.add_quest("A rather long quest title that will certainly need to wrap across lines", subquests=["x"])
        db.add_tracked_doc("CNH", "CNH", (date.today() + timedelta(days=5)).isoformat())
        db.set_hud_setting(wp.SETTING_BLOCKS, json.dumps([{"id": b, "on": True} for b in wp.BLOCKS]))
        for columns in ("1", "2"):
            for size in wp.SIZES:
                for screen in ((1366, 768), (1920, 1080), (3840, 2160)):
                    db.set_hud_setting(wp.SETTING_COLUMNS, columns)
                    db.set_hud_setting(wp.SETTING_SIZE, size)
                    img = wp.build_hud_image(screen=screen)
                    self.assertEqual(img.size, screen)

    def test_card_scales_with_resolution_and_size(self):
        def card_width(screen, size):
            db.set_hud_setting(wp.SETTING_SIZE, size)
            db.set_hud_setting("bg_mode", wp.BG_BLACK)
            img = wp.build_hud_image(screen=screen)
            row = [img.getpixel((x, img.height // 12)) for x in range(img.width)]
            inside = [x for x, px in enumerate(row) if px != (12, 14, 18)]
            return max(inside) - min(inside)

        self.assertGreater(card_width((3840, 2160), "Normal"), 1.8 * card_width((1920, 1080), "Normal"))
        self.assertGreater(card_width((1920, 1080), "Large"), card_width((1920, 1080), "Compact"))

    def test_background_fills_the_screen_without_stretching(self):
        # a wide image: left half red, right half blue -> "cover" crops the sides, no squashing
        path = Path(self.tmp) / "wide.png"
        img = Image.new("RGB", (400, 100), (255, 0, 0))
        img.paste((0, 0, 255), (200, 0, 400, 100))
        img.save(path)
        db.set_hud_setting("bg_mode", wp.BG_FOLDER)
        db.set_hud_setting(wp.SETTING_FOLDER, self.tmp)
        base = wp.get_base_wallpaper(db.get_hud_settings(), 200, 200)
        self.assertEqual(base.size, (200, 200))
        self.assertEqual(base.getpixel((10, 100))[:3], (255, 0, 0))
        self.assertEqual(base.getpixel((190, 100))[:3], (0, 0, 255))


class FolderRotationTests(WallpaperTestCase):
    def test_one_image_per_day_and_skip_ahead(self):
        for i, color in enumerate(("red", "green", "blue")):
            self.make_image(f"{i}.png", (10, 10), color)
        (Path(self.tmp) / "notes.txt").write_text("not an image")
        db.set_hud_setting(wp.SETTING_FOLDER, self.tmp)
        self.assertEqual(len(wp.list_folder_images(self.tmp)), 3)
        d = date(2026, 10, 5)
        first = wp.current_folder_image(on=d)
        self.assertNotEqual(first, wp.current_folder_image(on=d + timedelta(days=1)))
        self.assertEqual(first, wp.current_folder_image(on=d + timedelta(days=3)))  # cycles
        db.set_hud_setting(wp.SETTING_ROTATION, "1")
        self.assertEqual(wp.current_folder_image(on=d), wp.current_folder_image(
            settings=dict(db.get_hud_settings(), **{wp.SETTING_ROTATION: "0"}), on=d + timedelta(days=1)))

    def test_missing_folder_falls_back_to_a_plain_background(self):
        db.set_hud_setting("bg_mode", wp.BG_FOLDER)
        db.set_hud_setting(wp.SETTING_FOLDER, str(Path(self.tmp) / "nope"))
        base = wp.get_base_wallpaper(db.get_hud_settings(), 50, 50)
        self.assertEqual(base.getpixel((5, 5))[:3], (12, 14, 18))


class PauseRestoreTests(WallpaperTestCase):
    def test_original_is_kept_once_and_restored_on_pause(self):
        self.current = str(self.make_image("my_photo.jpg", (20, 20), "purple"))
        wp.render_wallpaper()
        saved = db.get_hud_settings()[wp.SETTING_ORIGINAL]
        self.assertTrue(Path(saved).exists())
        self.assertEqual(self.set_calls[-1], str(wp.hud_path()))
        self.current = str(wp.hud_path())  # now the HUD is the wallpaper
        wp.render_wallpaper()
        self.assertEqual(db.get_hud_settings()[wp.SETTING_ORIGINAL], saved)  # not overwritten by the HUD
        self.assertTrue(wp.pause_hud())
        self.assertEqual(self.set_calls[-1], saved)
        calls = len(self.set_calls)
        wp.render_wallpaper()  # paused -> nothing happens
        self.assertEqual(len(self.set_calls), calls)
        with mock.patch.object(wp, "request_wallpaper_update") as req:
            wp.resume_hud()
            req.assert_called_once()
        self.assertFalse(wp.is_paused())

    def test_pause_without_a_saved_original(self):
        self.assertFalse(wp.pause_hud())
        self.assertTrue(wp.is_paused())

    def test_preview_never_touches_the_desktop(self):
        png = wp.render_preview(max_width=400)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertEqual(self.set_calls, [])


class InsightTests(WallpaperTestCase):
    def test_context_has_habits_quests_and_studies(self):
        a = db.add_activity("Meditation")
        year, week, day = db.get_current_week_info()
        db.save_log(a, year, week, day, "Excellent", 10)
        db.add_quest("Run a 5K", next_step="Buy shoes")
        sid = db.add_study_session("Docker")
        db.add_journal_entry(sid, "Images and containers basics")
        ctx = ai_insight.build_context()
        for text in ("Meditation: 10.0", "Run a 5K", "next step: Buy shoes", "Docker"):
            self.assertIn(text, ctx)

    def test_generate_caches_for_today_and_respects_language(self):
        captured = {}

        def fake_generate(prompt, system, schema=None, **kw):
            captured["system"] = system
            return schema(text="  Great streak!   Keep the walk after dinner.  "), "models/x"

        db.set_hud_setting(ai_insight.SETTING_LANGUAGE, "English")
        with mock.patch.object(ai_gemini, "generate", side_effect=fake_generate):
            self.assertEqual(ai_insight.generate(), "Great streak! Keep the walk after dinner.")
        self.assertIn("Write in English", captured["system"])
        self.assertEqual(ai_insight.cached_today(), "Great streak! Keep the walk after dinner.")
        db.set_hud_setting(ai_insight.SETTING_DATE, "2000-01-01")
        self.assertIsNone(ai_insight.cached_today())

    def test_no_key_no_generation(self):
        with mock.patch.object(ai_gemini, "get_api_key", return_value=""):
            self.assertFalse(ai_insight.ensure_today())

    def test_insight_shows_on_the_hud_when_cached(self):
        db.set_hud_setting(wp.SETTING_BLOCKS, json.dumps([{"id": "insight", "on": True}]))
        db.set_hud_setting("bg_mode", wp.BG_BLACK)
        empty = wp.build_hud_image(screen=(1280, 720))
        db.set_hud_setting(ai_insight.SETTING_TEXT, "You walked the dog 6 days this week. Lovely rhythm.")
        db.set_hud_setting(ai_insight.SETTING_DATE, date.today().isoformat())
        with_text = wp.build_hud_image(screen=(1280, 720))
        self.assertNotEqual(empty.tobytes(), with_text.tobytes())


if __name__ == "__main__":
    unittest.main()
