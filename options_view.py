"""Options tab: general behaviour, which tabs load, scoring rules, quiet hours, data, AI and the Telegram assistant."""
import os
import threading
from pathlib import Path

import flet as ft

import ai_gemini
import ai_insight
import database as db
import settings
import telegram_api
import tts
from schedule_view import reminder_time as checkin_reminder_time

HALF_HOURS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
BRIEFING_TIMES = [t for t in HALF_HOURS if "05:00" <= t <= "11:30"]
PASSING_SCORES = [f"{x / 2:.1f}" for x in range(10, 19)]  # 5.0 … 9.0


class OptionsView(ft.Column):
    def __init__(self, page: ft.Page, assistant=None, on_restart=None, loaded_tabs=None):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, visible=False)
        self.app_page = page
        self.assistant = assistant
        self.restart_app = on_restart
        self.loaded_tabs = set(loaded_tabs if loaded_tabs is not None else settings.enabled_tabs())
        self.message = ""
        self.tg_message = ""
        self.left_col = ft.Column(spacing=14, width=540)
        self.right_col = ft.Column(spacing=14, width=600)
        self.controls = [ft.Container(
            content=ft.Row([self.left_col, self.right_col], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=ft.Padding.only(left=20, right=20, top=15, bottom=20))]
        self.render()

    # ------------------------------------------------------------ helpers
    def _update(self):
        if self.app_page:
            try:
                self.app_page.update()
            except Exception:
                pass

    @staticmethod
    def _card(title, controls, icon=None):
        head = ft.Row([ft.Icon(icon, size=18), ft.Text(title, size=15, weight=ft.FontWeight.BOLD)], spacing=8) \
            if icon else ft.Text(title, size=15, weight=ft.FontWeight.BOLD)
        return ft.Container(content=ft.Column([head, *controls], spacing=10,
                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=16)

    @staticmethod
    def _hint(text):
        return ft.Text(text, size=11, color=ft.Colors.GREY_400)

    def _set(self, key, value, rerender=False):
        settings.set(key, value)
        if rerender:
            self.render()

    def _switch(self, label, key, rerender=False):
        return ft.Switch(label=label, value=settings.flag(key),
                         on_change=lambda e: self._set(key, bool(e.control.value), rerender))

    def _dropdown(self, label, key, options, width=150, on_change=None):
        return ft.Dropdown(label=label, value=settings.get(key), width=width, dense=True,
                           options=[ft.DropdownOption(key=k, text=v) for k, v in options],
                           on_select=on_change or (lambda e: self._set(key, e.control.value)))

    # ------------------------------------------------------------ actions
    def _toggle_tab(self, tab, on):
        settings.set_tab_enabled(tab, on)
        self.render()

    def _toggle_startup(self, on):
        error = settings.set_start_with_windows(on)
        self.message = f"Could not change it: {error}" if error else \
            ("The tracker will open when you sign in to Windows." if on else "It won't open with Windows anymore.")
        self.render()

    def _set_score_rule(self, key, value):
        settings.set(key, value)
        self.message = "Saved. Streaks, colors and the wallpaper use the new rule."
        self.render()

    def _save_backup_dir(self, value):
        value = (value or "").strip()
        if value and not Path(value).is_dir():
            self.message = "That folder doesn't exist."
        else:
            settings.set("backup_dir", value)
            self.message = "Each daily backup is also copied to that folder." if value else \
                "Extra backup folder removed (backups stay in the data folder)."
        self.render()

    def _open_data_folder(self, e=None):
        try:
            os.startfile(str(Path(db.get_db_path()).parent))
        except Exception as exc:
            self.message = f"Could not open it: {exc}"
            self.render()

    def _export(self, e=None):
        try:
            path = db.export_to_csv()
            self.message = f"Exported to {path}" if path else "Exported to your Desktop."
        except Exception as exc:
            self.message = f"Export failed: {exc}"
        self.render()

    def _ai_settings(self, e=None):
        from study_view import open_ai_settings
        open_ai_settings(self.app_page, on_change=lambda *_: self.render())

    # Telegram ---------------------------------------------------
    def _run_bg(self, work):
        def run():
            try:
                self.tg_message = work() or ""
            except Exception as exc:
                self.tg_message = str(exc)
            self.render()
        threading.Thread(target=run, daemon=True, name="options-telegram").start()

    def _save_token(self, token):
        token = (token or "").strip()
        if not token:
            self.tg_message = "Paste the token from @BotFather first."
            self.render()
            return
        self.tg_message = "Checking the token…"
        self.render()

        def work():
            me = telegram_api.Bot(token).get_me()
            telegram_api.set_token(token)
            if self.assistant:
                self.assistant.unpair()  # a new bot means a new pairing
                self.assistant.start()
            return f"Saved — connected to @{me.get('username', '?')}."
        self._run_bg(work)

    def _remove_token(self, e=None):
        telegram_api.set_token("")
        settings.set("tg_enabled", False)
        if self.assistant:
            self.assistant.stop()
            self.assistant.unpair()
        self.tg_message = "Token removed and assistant turned off."
        self.render()

    def _toggle_assistant(self, on):
        settings.set("tg_enabled", on)
        if self.assistant:
            if on:
                if not self.assistant.start():
                    self.tg_message = self.assistant.last_error or "Save a bot token first."
            else:
                self.assistant.stop()
        self.render()
        if on:  # the status changes once the bot has answered getMe
            threading.Timer(3, self.render).start()

    def _unpair(self, e=None):
        if self.assistant:
            self.assistant.unpair()
        self.tg_message = "Unpaired. Send the new code to pair again."
        self.render()

    def _test_message(self, e=None):
        def work():
            if not (self.assistant and self.assistant.send("👋 Test message from your tracker.", speak=True)):
                return self.assistant.last_error if self.assistant else "Assistant unavailable."
            return "Test message sent."
        self._run_bg(work)

    def _send_checkin(self, e=None):
        def work():
            if self.assistant and self.assistant.send_checkin():
                return "Check-in sent."
            return "Nothing to ask: every habit is answered today." if self.assistant and self.assistant.chat_id \
                else "Pair your Telegram first."
        self._run_bg(work)

    # ------------------------------------------------------------ render
    def render(self):
        self.left_col.controls = [self._general_card(), self._tabs_card(), self._scoring_card(), self._data_card()]
        self.right_col.controls = [self._ai_card(), self._telegram_card(), self._messages_card()]
        self._update()

    def _general_card(self):
        lang_dd = ft.Dropdown(label="AI & messages language", value=ai_insight.language(), width=240, dense=True,
                              options=[ft.DropdownOption(lang) for lang in ai_insight.LANGUAGES],
                              on_select=lambda e: db.set_hud_setting(ai_insight.SETTING_LANGUAGE, e.control.value))
        controls = [
            lang_dd,
            self._hint("Used by Gemini (reviews, insights, quest planner) and the Telegram assistant. "
                       "The app itself stays in English."),
            ft.Switch(label="Start with Windows", value=settings.starts_with_windows(),
                      on_change=lambda e: self._toggle_startup(bool(e.control.value))),
            self._switch("Closing the window keeps it running in the tray", "close_to_tray"),
            self._hint("Off: the X button quits the app (reminders and the assistant stop with it)."),
            self._switch("Check for updates when the app starts", "auto_update"),
        ]
        if self.message:
            controls.append(ft.Text(self.message, size=12, color=ft.Colors.AMBER_ACCENT))
        return self._card("General", controls, ft.Icons.TUNE)

    def _tabs_card(self):
        enabled = settings.enabled_tabs()
        checks = [ft.Checkbox(label="Schedule (always on)", value=True, disabled=True)]
        checks += [ft.Checkbox(label=label, value=tab in enabled,
                               on_change=lambda e, t=tab: self._toggle_tab(t, bool(e.control.value)))
                   for tab, label in settings.OPTIONAL_TABS.items()]
        controls = [
            self._hint("A turned-off tab isn't loaded at all, and its background work stops "
                       "(e.g. Calendar off = no event alarms; Wallpaper off = the HUD stops updating)."),
            ft.Row([ft.Column(checks[:4], spacing=0, width=220), ft.Column(checks[4:], spacing=0, width=220)],
                   vertical_alignment=ft.CrossAxisAlignment.START),
        ]
        if set(enabled) != self.loaded_tabs:
            controls.append(ft.Row([
                ft.Icon(ft.Icons.RESTART_ALT, color=ft.Colors.AMBER_ACCENT, size=18),
                ft.Text("Restart the app to apply.", size=13, color=ft.Colors.AMBER_ACCENT, expand=True),
                ft.Button("Restart now", icon=ft.Icons.RESTART_ALT, disabled=self.restart_app is None,
                          on_click=lambda e: self.restart_app()),
            ], spacing=8))
        return self._card("Tabs", controls, ft.Icons.TAB)

    def _scoring_card(self):
        quiet_on = settings.flag("quiet_enabled")
        return self._card("Habits & scoring", [
            ft.Row([
                self._dropdown("Passing score", "passing_score", [(s, s) for s in PASSING_SCORES], width=150,
                               on_change=lambda e: self._set_score_rule("passing_score", e.control.value)),
                self._dropdown("Rest days / habit / week", "rest_limit", [(str(n), str(n)) for n in range(0, 8)],
                               width=210, on_change=lambda e: self._set_score_rule("rest_limit", e.control.value)),
            ], spacing=12),
            self._hint("Passing score: the daily average that keeps the streak (and turns the day green). "
                       "Rest days: how many times per week each habit may take a Rest answer."),
            ft.Divider(height=1),
            self._switch("Quiet hours", "quiet_enabled", rerender=True),
            ft.Row([
                self._dropdown("From", "quiet_start", [(t, t) for t in HALF_HOURS], width=120),
                self._dropdown("To", "quiet_end", [(t, t) for t in HALF_HOURS], width=120),
            ], spacing=12, visible=quiet_on),
            self._hint("No Telegram messages about documents, reviews or achievements in this window "
                       "(they arrive afterwards). Times you set yourself — briefing, event reminders, "
                       "the check-in — are always sent."),
        ], ft.Icons.SCOREBOARD_OUTLINED)

    def _data_card(self):
        folder = ft.TextField(label="Extra backup folder (e.g. OneDrive)", value=settings.get("backup_dir"),
                              dense=True, expand=True, hint_text="Empty = only the data folder")
        return self._card("Data", [
            ft.Row([folder, ft.IconButton(ft.Icons.SAVE, tooltip="Save backup folder",
                                          on_click=lambda e: self._save_backup_dir(folder.value))]),
            self._hint("A copy of the database is made every day before the app starts."),
            ft.Row([
                ft.OutlinedButton("Open data folder", icon=ft.Icons.FOLDER_OPEN, on_click=self._open_data_folder),
                ft.OutlinedButton("Export habits (CSV)", icon=ft.Icons.DOWNLOAD, on_click=self._export),
            ], spacing=10, wrap=True),
        ], ft.Icons.STORAGE)

    def _ai_card(self):
        ok = ai_gemini.is_configured()
        return self._card("AI (Gemini)", [
            ft.Text(ai_gemini.status_text(), size=13,
                    color=ft.Colors.GREEN_ACCENT if ok else ft.Colors.AMBER_ACCENT),
            self._hint("One key powers study reviews, the wallpaper insight, the quest planner and the "
                       "Telegram assistant (free tier is enough)."),
            ft.Row([ft.OutlinedButton("Gemini settings…", icon=ft.Icons.AUTO_AWESOME, on_click=self._ai_settings)]),
        ], ft.Icons.AUTO_AWESOME)

    def _telegram_card(self):
        a = self.assistant
        has_token = bool(telegram_api.get_token())
        enabled = settings.flag("tg_enabled")
        status = a.status_text() if a else "Unavailable."
        running = bool(a and a.running)
        token_f = ft.TextField(label="Bot token", password=True, can_reveal_password=True, dense=True, expand=True,
                               hint_text="Saved ✓ (paste a new one to replace)" if has_token else
                               "Paste the token from @BotFather")
        controls = [
            self._hint("1) In Telegram, talk to @BotFather → /newbot → copy the token.  "
                       "2) Paste it here and save.  3) Turn the assistant on and send the pairing code to your bot."),
            ft.Row([token_f,
                    ft.IconButton(ft.Icons.SAVE, tooltip="Check and save the token",
                                  on_click=lambda e: self._save_token(token_f.value)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Remove the saved token", disabled=not has_token,
                                  on_click=self._remove_token)]),
            ft.Switch(label="Assistant on", value=enabled, disabled=not has_token,
                      on_change=lambda e: self._toggle_assistant(bool(e.control.value))),
            ft.Text(status, size=13, selectable=True,
                    color=ft.Colors.GREEN_ACCENT if running and a.chat_id else ft.Colors.AMBER_ACCENT),
        ]
        if a and enabled and not a.chat_id:
            controls.append(ft.Container(
                content=ft.Row([ft.Text("Pairing code", size=13),
                                ft.Text(a.pairing_code, size=22, weight=ft.FontWeight.BOLD, selectable=True,
                                        font_family="Consolas")], spacing=12),
                padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH))
        if a and a.chat_id:
            controls.append(ft.Row([
                ft.OutlinedButton("Send test message", icon=ft.Icons.SEND, on_click=self._test_message,
                                  disabled=not running),
                ft.OutlinedButton("Send check-in now", icon=ft.Icons.CHECKLIST, on_click=self._send_checkin,
                                  disabled=not running),
                ft.TextButton("Unpair", icon=ft.Icons.LINK_OFF, on_click=self._unpair),
            ], spacing=8, wrap=True))

        mode = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(v)) for k, v in settings.REPLY_MODES.items()],
            selected=[settings.get("tg_reply_mode")], show_selected_icon=False,
            on_change=lambda e: self._set("tg_reply_mode", e.control.selected[0], True) if e.control.selected else None)
        voice = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(v)) for k, v in settings.VOICES.items()],
            selected=[settings.get("tg_voice")], show_selected_icon=False,
            disabled=settings.get("tg_reply_mode") == "text",
            on_change=lambda e: self._set("tg_voice", e.control.selected[0]) if e.control.selected else None)
        controls += [
            ft.Divider(height=1),
            ft.Row([ft.Text("Replies", width=70), mode], spacing=10),
            ft.Row([ft.Text("Voice", width=70), voice], spacing=10),
            self._hint("You can always talk to it by text or by voice message. Voice replies use Microsoft's "
                       "neural voices (Brazilian Portuguese or English, following the language above)."
                       + ("" if tts.AVAILABLE else "  ⚠ edge-tts isn't installed, so replies fall back to text.")),
            self._hint("It can read everything and mark habits, add events, log studies and update quests — it "
                       "never deletes anything. It only works while this app is running."),
        ]
        if self.tg_message:
            controls.append(ft.Text(self.tg_message, size=12, color=ft.Colors.AMBER_ACCENT))
        return self._card("Telegram assistant", controls, ft.Icons.SMART_TOY_OUTLINED)

    def _messages_card(self):
        briefing = [("", "Off")] + [(t, t) for t in BRIEFING_TIMES]
        checkin_at = checkin_reminder_time()
        return self._card("Messages it sends", [
            ft.Row([
                self._dropdown("Morning briefing", "tg_briefing", briefing, width=170),
                ft.Container(self._hint("Your wake-up message: today's events, reviews, documents and next quest "
                                        "steps, written by Gemini."), expand=True),
            ], spacing=12),
            self._switch("Calendar reminders (each event's own reminder time)", "tg_calendar"),
            self._switch("Documents expiring (window, 7 days, due)", "tg_documents"),
            self._switch("Study reviews due (after 09:00)", "tg_reviews"),
            self._switch("Evening check-in with answer buttons", "tg_checkin"),
            self._hint(f"Sent at the Schedule's nightly reminder time ({checkin_at})." if checkin_at else
                       "Turn on the nightly reminder in the Schedule tab (🔔) to pick its time."),
            self._switch("Achievements (level up, streaks, quests, mastered chapters)", "tg_achievements"),
        ], ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED)
