"""Diary: a page per day with mood & energy, guided writing exercises, notes from the Schedule,
a look back (calendar, search, on this day, highlights) and an optional honest AI reflection.

Everything written is encrypted (secure.py); with a PIN the tab stays locked until unlocked.
"""
import calendar
import threading
import time
from datetime import date, datetime, timedelta

import flet as ft

import ai_diary
import ai_gemini
import database as db
from constants import XP_DIARY_EXERCISE, DIARY_XP_EXERCISES_PER_DAY, DIARY_EXERCISE_MIN_CHARS
from ui_helpers import confirm_action, update_ui
from i18n import tr, trn, day_short, fmt_long, fmt_month_year, fmt_short

UNLOCK_MINUTES = 15          # stays open while you use it (every action extends it)
ACCENT = ft.Colors.PINK_ACCENT_100
MOODS = [(1, "😞", "Very low"), (2, "😕", "Low"), (3, "😐", "Okay"), (4, "🙂", "Good"), (5, "😄", "Great")]
ENERGY = [(1, "Drained"), (2, "Low"), (3, "Steady"), (4, "Good"), (5, "Charged")]
MOOD_EMOJI = {m: e for m, e, _ in MOODS}

# kind -> (title, icon, intro, [(field, label, hint, lines)])
EXERCISES = {
    "win": ("Win of the day", ft.Icons.EMOJI_EVENTS_OUTLINED,
            "Big or small: write down something that went well and own your part in it.",
            [("win", "What went well?", "e.g. Stretching felt amazing — I touched my toes for the first time", 3),
             ("how", "What made it possible?", "Your effort, a choice you made, someone who helped…", 2),
             ("feel", "How does it feel?", "", 2)]),
    "gratitude": ("Three good things", ft.Icons.VOLUNTEER_ACTIVISM_OUTLINED,
                  "Three things that went well today, and why. Small things count — that's the point.",
                  [("one", "1. Something good", "", 2), ("two", "2. Something good", "", 2),
                   ("three", "3. Something good", "", 2), ("why", "Why did they happen?", "", 2)]),
    "expressive": ("Expressive writing", ft.Icons.EDIT_NOTE,
                   "Write freely about something that's on your mind for about 15 minutes: what happened, how you "
                   "feel and why. Don't worry about grammar or order — this is only for you.",
                   [("text", "Write freely", "", 12)]),
    "thought": ("Thought record", ft.Icons.PSYCHOLOGY_OUTLINED,
                "When a feeling hits hard, slow it down: separate what happened from the story your mind told.",
                [("situation", "Situation", "Where were you? What happened?", 2),
                 ("thought", "Automatic thought", "What went through your mind?", 2),
                 ("feeling", "Feeling (and how strong, 0-100)", "e.g. anxious 70", 1),
                 ("for", "Evidence that supports the thought", "", 2),
                 ("against", "Evidence that doesn't", "", 2),
                 ("balanced", "A more balanced thought", "What would you tell a friend?", 2),
                 ("after", "Feeling now (0-100)", "", 1)]),
    "worry": ("Worry dump", ft.Icons.NIGHTS_STAY_OUTLINED,
              "Before sleep, empty your head onto the page so it doesn't have to hold everything tonight.",
              [("worries", "Everything on my mind", "", 6),
               ("control", "What can I actually act on?", "", 2),
               ("next", "One small next step (for tomorrow)", "", 1),
               ("let_go", "What I can let go of for tonight", "", 2)]),
    "compassion": ("Self-compassion letter", ft.Icons.FAVORITE_BORDER,
                   "Write to yourself the way a kind friend who knows you well would: about something hard, "
                   "with understanding instead of criticism.",
                   [("letter", "Dear me,", "", 10)]),
}
EXERCISE_TITLES = {k: v[0] for k, v in EXERCISES.items()}


class _Lock:
    def __init__(self):
        self.until = 0.0

    def unlocked(self) -> bool:
        return not db.has_diary_pin() or time.monotonic() < self.until

    def unlock(self):
        self.until = time.monotonic() + UNLOCK_MINUTES * 60

    def touch(self):
        """Any activity in the diary keeps it open."""
        if db.has_diary_pin() and self.unlocked():
            self.unlock()

    def lock(self):
        self.until = 0.0


LOCK = _Lock()


def ask_pin(page: ft.Page, on_ok, title=None):
    if LOCK.unlocked():
        on_ok()
        return
    pin_f = ft.TextField(label=tr("PIN"), password=True, can_reveal_password=True, autofocus=True, dense=True,
                         keyboard_type=ft.KeyboardType.NUMBER)
    error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

    def submit(e=None):
        if db.check_diary_pin(pin_f.value or ""):
            LOCK.unlock()
            page.pop_dialog()
            on_ok()
        else:
            error.value = tr("Wrong PIN.")
            pin_f.value = ""
            page.update()

    pin_f.on_submit = submit
    page.show_dialog(ft.AlertDialog(
        modal=True, title=ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE),
                                  ft.Text(title or tr("Unlock your diary"), weight=ft.FontWeight.BOLD)]),
        content=ft.Container(width=320, content=ft.Column(
            [ft.Text(tr("It stays open while you use it (locks after {n} quiet minutes).", n=UNLOCK_MINUTES), size=12,
                     color=ft.Colors.GREY_400), pin_f, error], spacing=10, tight=True)),
        actions=[ft.TextButton(tr("Cancel"), on_click=lambda e: page.pop_dialog()),
                 ft.Button(tr("Unlock"), icon=ft.Icons.LOCK_OPEN, on_click=submit)]))


def open_habit_note(page: ft.Page, activity_id: int, habit: str, day: date, status: str = "-",
                    on_saved=None, on_close=None):
    """Note on a Schedule cell. Writing a new note never needs the PIN; reading an existing one does."""
    existing = db.get_habit_note(activity_id, day) if LOCK.unlocked() else None
    if existing is None and db.habit_note_flags(day, day).get((activity_id, day.isoformat())) is not None:
        ask_pin(page, lambda: open_habit_note(page, activity_id, habit, day, status, on_saved, on_close),
                title=tr("Unlock to read this note"))
        return
    existing = existing or {"note": "", "highlight": False}
    note_f = ft.TextField(value=existing["note"], multiline=True, min_lines=4, max_lines=10, autofocus=True,
                          hint_text=tr("What made it special? How did it feel?"), text_size=14)
    star = ft.Checkbox(label=tr("⭐ Highlight — show it in the Diary's highlights"), value=existing["highlight"]
                       or (not existing["note"] and status == "Excellent"))

    def close(e=None):
        page.pop_dialog()
        if on_close:
            on_close()

    def save(e=None):
        db.set_habit_note(activity_id, day, note_f.value, bool(star.value))
        LOCK.touch()
        close()
        if on_saved:
            on_saved()

    def remove(e=None):
        db.set_habit_note(activity_id, day, "")
        close()
        if on_saved:
            on_saved()

    label = f"{habit} · {DAY_LABEL(day)}" + (f" · {tr(status)}" if status not in ("-", None) else "")
    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, color=ACCENT), ft.Text(label, weight=ft.FontWeight.BOLD,
                                                                          size=16, expand=True)]),
        content=ft.Container(width=520, content=ft.Column([
            note_f, star,
            ft.Text(tr("It also appears on that day's Diary page. Encrypted like the rest of the diary."),
                    size=11, color=ft.Colors.GREY_500)], tight=True, spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
        actions=[ft.TextButton(tr("Delete note"), icon=ft.Icons.DELETE_OUTLINE, on_click=remove,
                               visible=bool(existing["note"])),
                 ft.TextButton(tr("Cancel"), on_click=close),
                 ft.Button(tr("Save"), icon=ft.Icons.SAVE, on_click=save)]))


def DAY_LABEL(d: date) -> str:  # noqa: N802 - small formatting helper used like a constant
    if d == date.today():
        return tr("today")
    if d == date.today() - timedelta(days=1):
        return tr("yesterday")
    return fmt_short(d)


class DiaryView(ft.Row):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0, visible=False, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.app_page = page
        self.selected_day = date.today()
        self.month_start = date.today().replace(day=1)
        self.search_text = ""
        self.body_dirty = False
        self.save_status = ""
        self.ai_busy = False
        self.ai_error = ""
        self.message = ""
        self.body_field = None
        self.sidebar = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO,
                                 horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.workspace = ft.Column(spacing=14, expand=True, scroll=ft.ScrollMode.AUTO,
                                   horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls = [
            ft.Container(content=self.sidebar, width=330, padding=15, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
            ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
            ft.Container(content=self.workspace, expand=True,
                         padding=ft.Padding.only(left=20, right=30, top=15, bottom=30)),
        ]

    # ------------------------------------------------------------ helpers
    def _update(self):
        if self.app_page:
            update_ui(self.app_page)

    def _card(self, title, controls, icon=None, trailing=None):
        head = [ft.Icon(icon, size=18, color=ACCENT)] if icon else []
        head.append(ft.Text(tr(title), size=15, weight=ft.FontWeight.BOLD, expand=True))
        if trailing:
            head.append(trailing)
        return ft.Container(content=ft.Column([ft.Row(head, spacing=8), *controls], spacing=10,
                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=16)

    def save_draft(self):
        """Saves the page text if it changed (switching days, locking, leaving the tab)."""
        if self.body_dirty and self.body_field is not None:
            db.save_diary_entry(self.selected_day, body=self.body_field.value or "")
            self.body_dirty = False
            self.save_status = tr("Saved {time}", time=f"{datetime.now():%H:%M}")

    # ------------------------------------------------------------ actions
    def go_to(self, day: date):
        if day > date.today():
            return
        self.save_draft()
        LOCK.touch()
        self.selected_day = day
        self.month_start = day.replace(day=1)
        self.save_status = self.ai_error = self.message = ""
        self.render()

    def _shift_month(self, delta):
        y, m = self.month_start.year, self.month_start.month + delta
        y, m = (y - 1, 12) if m < 1 else ((y + 1, 1) if m > 12 else (y, m))
        if date(y, m, 1) > date.today():
            return
        self.month_start = date(y, m, 1)
        self.render()

    def _set_mood(self, value):
        LOCK.touch()
        entry = db.get_diary_entry(self.selected_day)
        db.save_diary_entry(self.selected_day, mood=None if entry["mood"] == value else value)
        self.render()

    def _set_energy(self, value):
        LOCK.touch()
        entry = db.get_diary_entry(self.selected_day)
        db.save_diary_entry(self.selected_day, energy=None if entry["energy"] == value else value)
        self.render()

    def _body_changed(self, e):
        self.body_dirty = True
        LOCK.touch()

    def _save_body(self, e=None):
        self.save_draft()
        if e is not None and getattr(e.control, "data", None) == "button":
            self.render()

    def _lock_now(self, e=None):
        self.save_draft()
        LOCK.lock()
        self.render()

    def _unlock(self, e=None):
        ask_pin(self.app_page, self._unlocked)

    def _unlocked(self):
        self.render()
        threading.Timer(UNLOCK_MINUTES * 60 + 1, self._relock_if_expired).start()

    def _relock_if_expired(self):
        if not db.has_diary_pin():
            return
        if LOCK.unlocked():  # still in use: check again later
            threading.Timer(60, self._relock_if_expired).start()
            return
        self.save_draft()
        if self.visible:
            self.render()

    def _search(self, value):
        self.search_text = (value or "").strip()
        LOCK.touch()
        self.render()

    # exercises ----------------------------------------------------
    def open_exercise(self, kind, existing=None):
        title, icon, intro, spec = EXERCISES[kind]
        title = tr(title)
        values = (existing or {}).get("fields", {})
        inputs = {}
        controls = [ft.Text(tr(intro), size=13, color=ft.Colors.GREY_300)]
        for name, label, hint, lines in spec:
            inputs[name] = ft.TextField(label=tr(label), hint_text=tr(hint) if hint else None, value=values.get(name, ""),
                                        multiline=lines > 1, min_lines=lines, max_lines=max(lines, 3) * 3,
                                        text_size=14)
            controls.append(inputs[name])
        rewarded = existing is None
        if rewarded:
            controls.append(ft.Text(tr("+{xp} XP when you write at least {n} characters (each kind once a day, up to "
                                       "{max} a day).", xp=f"{XP_DIARY_EXERCISE:g}", n=DIARY_EXERCISE_MIN_CHARS,
                                       max=DIARY_XP_EXERCISES_PER_DAY),
                                    size=11, color=ft.Colors.GREY_500))
        page = self.app_page

        def save(e=None):
            fields = {n: f.value or "" for n, f in inputs.items()}
            if not any(v.strip() for v in fields.values()):
                page.pop_dialog()
                return
            LOCK.touch()
            if existing:
                db.update_diary_exercise(existing["id"], fields)
                self.message = tr("{title} updated.", title=title)
            else:
                xp = db.add_diary_exercise(self.selected_day, kind, fields)
                self.message = tr("{title} saved", title=title) + (f" · +{xp:g} XP 🌱" if xp else ".")
            page.pop_dialog()
            self.render()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(icon, color=ACCENT), ft.Text(title, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(width=640, content=ft.Column(
                controls, tight=True, spacing=12, scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=[ft.TextButton(tr("Cancel"), on_click=lambda e: page.pop_dialog()),
                     ft.Button(tr("Save"), icon=ft.Icons.SAVE, on_click=save)]))

    def _delete_exercise(self, ex):
        def done():
            db.delete_diary_exercise(ex["id"])
            self.render()
        confirm_action(self.app_page, tr("Delete exercise?"),
                       tr("'{title}' of {day} will be deleted for good.",
                          title=tr(EXERCISE_TITLES.get(ex["kind"], ex["kind"])), day=DAY_LABEL(self.selected_day)), done)

    # reflection ---------------------------------------------------
    def _ask_reflection(self, e=None):
        self.save_draft()
        if not ai_diary.has_consent():
            self._consent_dialog()
            return
        self.ai_busy, self.ai_error = True, ""
        self.render()
        day = self.selected_day

        def work():
            try:
                ai_diary.reflect(day, EXERCISE_TITLES)
            except ai_gemini.AIError as exc:
                self.ai_error = str(exc)
            except Exception as exc:  # never leave the spinner running
                self.ai_error = tr("Something went wrong: {error}", error=exc)
            self.ai_busy = False
            if self.visible and self.selected_day == day:
                self.render()

        threading.Thread(target=work, daemon=True, name="ai-diary").start()

    def _consent_dialog(self):
        page = self.app_page

        def agree(e):
            ai_diary.give_consent()
            page.pop_dialog()
            self._ask_reflection()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=ACCENT),
                          ft.Text(tr("Before the first reflection"), weight=ft.FontWeight.BOLD)]),
            content=ft.Container(width=520, content=ft.Column([
                ft.Text(tr("Only when you click, the selected day's page, exercises, habit notes, habit answers and "
                        "mood are sent to Google's Gemini for an honest, impartial reflection — it will point out "
                        "patterns and your own part in things, not just comfort you. Nothing is sent automatically."),
                        size=13),
                ft.Text(tr("On Gemini's free tier, Google may use that text to improve its products. Skip this for "
                        "anything you wouldn't want to leave your computer."), size=13, color=ft.Colors.AMBER_200),
                ft.Text(tr("The reflection is not therapy or medical advice. If you're struggling, talking to someone "
                        "you trust or a professional helps — in Brazil, CVV answers 24h at 188 (free)."),
                        size=12, color=ft.Colors.GREY_400),
            ], tight=True, spacing=10)),
            actions=[ft.TextButton(tr("Not now"), on_click=lambda e: page.pop_dialog()),
                     ft.Button(tr("I understand, continue"), icon=ft.Icons.AUTO_AWESOME, on_click=agree)]))

    def _clear_reflection(self, e=None):
        db.set_diary_reflection(self.selected_day, "")
        self.render()

    # settings -----------------------------------------------------
    def open_settings(self, e=None):
        page = self.app_page
        has_pin = db.has_diary_pin()
        pin1 = ft.TextField(label=tr("New PIN (4+ digits)"), password=True, can_reveal_password=True, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER)
        pin2 = ft.TextField(label=tr("Repeat the PIN"), password=True, can_reveal_password=True, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER)
        current = ft.TextField(label=tr("Current PIN"), password=True, can_reveal_password=True, dense=True,
                               keyboard_type=ft.KeyboardType.NUMBER, visible=has_pin)
        error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

        def save(e=None):
            if has_pin and not db.check_diary_pin(current.value or ""):
                error.value = tr("The current PIN is wrong.")
            elif len(pin1.value or "") < 4 or not (pin1.value or "").isdigit():
                error.value = tr("Use at least 4 digits.")
            elif pin1.value != pin2.value:
                error.value = tr("The PINs don't match.")
            else:
                self.save_draft()
                db.set_diary_pin(pin1.value)
                LOCK.unlock()
                page.pop_dialog()
                self.message = tr("PIN saved. Your diary locks after 15 quiet minutes (or with the lock button).")
                self.render()
                return
            page.update()

        def remove(e=None):
            if not db.check_diary_pin(current.value or ""):
                error.value = tr("Type the current PIN to remove it.")
                page.update()
                return
            db.remove_diary_pin()
            page.pop_dialog()
            self.message = tr("PIN removed.")
            self.render()

        def forgot(e=None):
            page.pop_dialog()

            def wipe():
                db.reset_diary_pin_and_wipe_text()
                LOCK.lock()
                self.message = tr("PIN removed and the diary's texts erased. Moods were kept.")
                self.render()
            confirm_action(page, tr("Forgot the PIN?"),
                           tr("Without the PIN the diary can't be opened. Removing it ERASES every text in the diary "
                           "(pages, exercises, habit notes and reflections); moods and earned XP stay. "
                           "This can't be undone."), wipe, confirm_label=tr("Erase texts and remove PIN"))

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE), ft.Text(tr("Diary privacy"), weight=ft.FontWeight.BOLD)]),
            content=ft.Container(width=420, content=ft.Column([
                ft.Text(tr("Everything you write is encrypted on this computer. A PIN also hides the diary until "
                        "you unlock it."), size=12, color=ft.Colors.GREY_400),
                current, pin1, pin2, error,
                ft.Text(tr("There is no way to recover a forgotten PIN without erasing the diary's texts."),
                        size=11, color=ft.Colors.AMBER_200),
            ], tight=True, spacing=10)),
            actions=[ft.TextButton(tr("Forgot PIN"), on_click=forgot, visible=has_pin),
                     ft.TextButton(tr("Remove PIN"), on_click=remove, visible=has_pin),
                     ft.TextButton(tr("Cancel"), on_click=lambda e: page.pop_dialog()),
                     ft.Button(tr("Save PIN"), icon=ft.Icons.SAVE, on_click=save)]))

    # ------------------------------------------------------------ render
    def render(self):
        if not LOCK.unlocked():
            self.body_field = None
            self.sidebar.controls = [ft.Row([ft.Icon(ft.Icons.MENU_BOOK, color=ACCENT, size=24),
                                             ft.Text(tr("Diary"), size=18, weight=ft.FontWeight.BOLD)])]
            self.workspace.controls = [ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.LOCK_OUTLINE, size=56, color=ACCENT),
                    ft.Text(tr("Your diary is locked"), size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(tr("Notes from the Schedule can still be written without unlocking."), size=12,
                            color=ft.Colors.GREY_400),
                    ft.Button(tr("Unlock"), icon=ft.Icons.LOCK_OPEN, on_click=self._unlock),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                alignment=ft.Alignment.CENTER, padding=80)]
            self._update()
            return
        self._render_sidebar()
        self._render_workspace()
        self._update()

    def _render_sidebar(self):
        has_pin = db.has_diary_pin()
        controls = [
            ft.Row([ft.Icon(ft.Icons.MENU_BOOK, color=ACCENT, size=24),
                    ft.Text(tr("Diary"), size=18, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.LOCK_OUTLINE, tooltip=tr("Lock now"), visible=has_pin,
                                  on_click=self._lock_now),
                    ft.IconButton(ft.Icons.SETTINGS_OUTLINED, tooltip=tr("Privacy & PIN"), on_click=self.open_settings)]),
            self._calendar(),
            ft.TextField(value=self.search_text, hint_text=tr("Search the diary…"), dense=True, text_size=13,
                         prefix_icon=ft.Icons.SEARCH, on_submit=lambda e: self._search(e.control.value),
                         suffix=ft.IconButton(ft.Icons.CLOSE, icon_size=16, tooltip=tr("Clear search"),
                                              on_click=lambda e: self._search(""),
                                              visible=bool(self.search_text))),
        ]
        if self.search_text:
            controls += self._search_results()
        else:
            controls += self._look_back()
        self.sidebar.controls = controls

    def _calendar(self):
        first = self.month_start
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        info = db.diary_month(first, last)
        today = date.today()
        header = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_size=18, tooltip=tr("Previous month"),
                          on_click=lambda e: self._shift_month(-1)),
            ft.Text(fmt_month_year(first), weight=ft.FontWeight.BOLD, expand=True, text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=18, tooltip=tr("Next month"),
                          disabled=last >= today, on_click=lambda e: self._shift_month(1)),
            ft.TextButton(tr("Today"), on_click=lambda e: self.go_to(date.today())),
        ], spacing=0)
        week = ft.Row([ft.Container(ft.Text(n, size=10, color=ft.Colors.GREY_500), width=38,
                                    alignment=ft.Alignment.CENTER) for n in (day_short(i)[0] for i in range(7))],
                      spacing=4)
        rows = [header, week]
        cells = [ft.Container(width=38, height=40) for _ in range(first.weekday())]
        d = first
        while d <= last:
            i = info.get(d.isoformat())
            future = d > today
            selected = d == self.selected_day
            mark = ""
            if i:
                mark = MOOD_EMOJI.get(i["mood"], "") or ("⭐" if i["highlight"] else "•")
            tip = None
            if i:
                bits = [tr("mood {emoji}", emoji=MOOD_EMOJI[i["mood"]]) if i["mood"] else "",
                        tr("page") if i["written"] else "",
                        tr("{n} exercise(s)", n=i["exercises"]) if i["exercises"] else "",
                        tr("{n} habit note(s)", n=i["notes"]) if i["notes"] else ""]
                tip = f"{fmt_short(d, year=False)}: " + ", ".join(b for b in bits if b)
            cells.append(ft.Container(
                content=ft.Column([
                    ft.Text(str(d.day), size=12, weight=ft.FontWeight.BOLD if d == today else None,
                            color=ft.Colors.GREY_700 if future else (ft.Colors.CYAN_ACCENT if d == today else None)),
                    ft.Text(mark, size=10, height=13),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                width=38, height=40, border_radius=8, alignment=ft.Alignment.CENTER, tooltip=tip,
                bgcolor=ft.Colors.with_opacity(0.10, ACCENT) if i and (i["written"] or i["exercises"]) else None,
                border=ft.Border.all(2, ACCENT) if selected else None,
                ink=not future, on_click=None if future else (lambda e, day=d: self.go_to(day))))
            d += timedelta(days=1)
        for start in range(0, len(cells), 7):
            rows.append(ft.Row(cells[start:start + 7], spacing=4))
        return ft.Column(rows, spacing=2)

    def _look_back(self):
        out = []
        day = self.selected_day
        candidates = []
        for label, delta in (("A week ago", 7), ("A month ago", None), ("A year ago", "year")):
            if delta == "year":
                try:
                    past = day.replace(year=day.year - 1)
                except ValueError:  # 29 Feb
                    past = day.replace(year=day.year - 1, day=28)
            elif delta is None:  # same day last month (clipped to its length)
                prev_last = day.replace(day=1) - timedelta(days=1)
                past = prev_last.replace(day=min(day.day, prev_last.day))
            else:
                past = day - timedelta(days=delta)
            candidates.append((label, past))
        for label, past in candidates:
            entry = db.get_diary_entry(past)
            notes = db.get_habit_notes(past)
            text = entry["body"].strip() or (notes[0]["note"] if notes else "")
            if not (text or entry["mood"]):
                continue
            preview = (MOOD_EMOJI.get(entry["mood"], "") + " " + text.replace("\n", " ")).strip()
            out.append(ft.Container(
                content=ft.Column([ft.Text(f"{tr(label)} · {past:%d/%m/%Y}", size=11, color=ACCENT),
                                   ft.Text(preview[:140] + ("…" if len(preview) > 140 else ""), size=12,
                                           color=ft.Colors.GREY_300)], spacing=2),
                padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, ink=True,
                on_click=lambda e, d=past: self.go_to(d)))
        if out:
            out.insert(0, ft.Text(tr("On this day"), size=13, weight=ft.FontWeight.BOLD))

        highlights = db.get_habit_notes(highlights_only=True, limit=12)
        if highlights:
            out.append(ft.Text(tr("⭐ Highlights"), size=13, weight=ft.FontWeight.BOLD))
            for h in highlights:
                d = date.fromisoformat(h["date"])
                out.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"{h['habit']} · {d:%d/%m/%Y}" + (f" · {tr(h['status'])}" if h["status"] != "-" else ""),
                                size=11, color=ft.Colors.AMBER_200),
                        ft.Text(h["note"][:120] + ("…" if len(h["note"]) > 120 else ""), size=12)], spacing=2),
                    padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, ink=True,
                    on_click=lambda e, d=d: self.go_to(d)))
        if not out:
            out.append(ft.Text(tr("Highlights and memories from past days will show up here."), size=12,
                               color=ft.Colors.GREY_500))
        return out

    def _search_results(self):
        hits = db.search_diary(self.search_text)
        out = [ft.Text(trn("{n} result for “{text}”", "{n} results for “{text}”", len(hits), text=self.search_text),
                       size=12,
                       color=ft.Colors.GREY_400)]
        for h in hits:
            d = date.fromisoformat(h["date"])
            where = tr("Page") if h["where"] == "page" else tr(EXERCISE_TITLES.get(h["where"], h["where"]))
            out.append(ft.Container(
                content=ft.Column([ft.Text(f"{d:%d/%m/%Y} · {where}", size=11, color=ACCENT),
                                   ft.Text(h["snippet"], size=12)], spacing=2),
                padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, ink=True,
                on_click=lambda e, d=d: self.go_to(d)))
        return out

    def _render_workspace(self):
        day = self.selected_day
        entry = db.get_diary_entry(day)
        title = fmt_long(day)
        controls = [ft.Row([
            ft.Text(title, size=22, weight=ft.FontWeight.BOLD, expand=True),
            ft.Container(ft.Text(tr("Today"), size=11, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                         bgcolor=ft.Colors.CYAN_ACCENT, border_radius=10,
                         padding=ft.Padding.symmetric(horizontal=8, vertical=2), visible=day == date.today()),
        ])]
        if self.message:
            controls.append(ft.Text(self.message, size=12, color=ft.Colors.GREEN_ACCENT))

        mood_row = ft.Row([ft.Text(tr("Mood"), width=60, color=ft.Colors.GREY_400)] + [
            ft.Container(ft.Text(emoji, size=22), padding=6, border_radius=10, tooltip=tr(label), ink=True,
                         bgcolor=ft.Colors.with_opacity(0.25, ACCENT) if entry["mood"] == m else None,
                         border=ft.Border.all(1, ACCENT if entry["mood"] == m else ft.Colors.GREY_800),
                         on_click=lambda e, m=m: self._set_mood(m)) for m, emoji, label in MOODS], spacing=6)
        energy_row = ft.Row([ft.Text(tr("Energy"), width=60, color=ft.Colors.GREY_400)] + [
            ft.Container(ft.Text(f"{n} · {tr(label)}", size=11), padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                         border_radius=10, ink=True,
                         bgcolor=ft.Colors.with_opacity(0.25, ACCENT) if entry["energy"] == n else None,
                         border=ft.Border.all(1, ACCENT if entry["energy"] == n else ft.Colors.GREY_800),
                         on_click=lambda e, n=n: self._set_energy(n)) for n, label in ENERGY], spacing=6, wrap=True)

        self.body_field = ft.TextField(
            value=entry["body"], multiline=True, min_lines=8, max_lines=30, text_size=15,
            hint_text=tr("What happened today? What's on your mind? Anything goes — it's encrypted and only yours."),
            on_change=self._body_changed, on_blur=self._save_body)
        self.body_dirty = False
        save_row = ft.Row([
            ft.Text(self.save_status or (tr("Last saved {time}", time=entry["updated_at"][11:16])
                                         if entry["updated_at"] else ""),
                    size=11, color=ft.Colors.GREY_500, expand=True),
            ft.Button(tr("Save"), icon=ft.Icons.SAVE, data="button", on_click=self._save_body),
        ])
        controls.append(self._card("Today's page" if day == date.today() else "Page",
                                   [mood_row, energy_row, self.body_field, save_row], ft.Icons.AUTO_STORIES))

        notes = db.get_habit_notes(day)
        note_controls = [ft.Container(
            content=ft.Column([
                ft.Text(("⭐ " if n["highlight"] else "") + n["habit"] +
                        (f" · {tr(n['status'])}" if n["status"] != "-" else ""), size=12, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_200 if n["highlight"] else ft.Colors.GREY_300),
                ft.Text(n["note"], size=13, selectable=True)], spacing=2),
            padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, ink=True, tooltip=tr("Edit note"),
            on_click=lambda e, n=n: open_habit_note(self.app_page, n["activity_id"], n["habit"], day, n["status"],
                                                    on_saved=self.render)) for n in notes]
        if not note_controls:
            note_controls = [ft.Text(tr("No habit notes this day. In the Schedule, use ✎ on a habit (or press N) to "
                                     "write why it mattered."), size=12, color=ft.Colors.GREY_500)]
        controls.append(self._card("From the Schedule", note_controls, ft.Icons.CHECKLIST))

        exercises = db.get_diary_exercises(day)
        buttons = ft.Row([ft.OutlinedButton(tr(t), icon=icon, on_click=lambda e, k=k: self.open_exercise(k))
                          for k, (t, icon, _, _) in EXERCISES.items()], wrap=True, spacing=8, run_spacing=8)
        ex_controls = [buttons]
        for ex in exercises:
            title, icon, _, spec = EXERCISES.get(ex["kind"], (ex["kind"], ft.Icons.NOTES, "", []))
            labels = {n: tr(lbl) for n, lbl, _, _ in spec}
            lines = [ft.Column([ft.Text(labels.get(k, k), size=11, color=ft.Colors.GREY_400),
                                ft.Text(v, size=13, selectable=True)], spacing=1)
                     for k, v in ex["fields"].items() if v]
            ex_controls.append(ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(icon, size=16, color=ACCENT),
                            ft.Text(f"{tr(title)} · {ex['created_at'][11:16]}", weight=ft.FontWeight.BOLD, size=13,
                                    expand=True),
                            ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=16, tooltip=tr("Edit exercise"),
                                          on_click=lambda e, ex=ex: self.open_exercise(ex["kind"], ex)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, tooltip=tr("Delete exercise"),
                                          on_click=lambda e, ex=ex: self._delete_exercise(ex))], spacing=4),
                    *lines], spacing=6),
                padding=12, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH))
        controls.append(self._card("Guided exercises", ex_controls, ft.Icons.SELF_IMPROVEMENT,
                                   trailing=ft.Text(tr("+{xp} XP each", xp=f"{XP_DIARY_EXERCISE:g}"), size=11,
                                                    color=ft.Colors.GREY_500)))

        controls.append(self._reflection_card(entry))
        self.workspace.controls = controls

    def _reflection_card(self, entry):
        configured = ai_gemini.is_configured()
        body = []
        if entry["reflection"]:
            body.append(ft.Text(entry["reflection"], size=14, selectable=True, italic=True))
            body.append(ft.Text(f"Gemini · {entry['reflection_at'][:16].replace('T', ' ')}", size=11,
                                color=ft.Colors.GREY_500))
        if self.ai_busy:
            body.append(ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2),
                                ft.Text(tr("Reading your day…"), size=12, color=ft.Colors.GREY_400)]))
        if self.ai_error:
            body.append(ft.Text(self.ai_error, size=12, color=ft.Colors.RED_ACCENT))
        if not configured:
            body.append(ft.Text(tr("Optional: add a Gemini key (Options → AI) to ask for an honest reflection on a day."),
                                size=12, color=ft.Colors.GREY_500))
        else:
            body.append(ft.Row([
                ft.OutlinedButton(tr("Ask for a reflection") if not entry["reflection"] else tr("Reflect again"),
                                  icon=ft.Icons.AUTO_AWESOME, disabled=self.ai_busy, on_click=self._ask_reflection),
                ft.TextButton(tr("Remove"), icon=ft.Icons.DELETE_OUTLINE, visible=bool(entry["reflection"]),
                              on_click=self._clear_reflection),
                ft.Text(tr("Sent only when you click."), size=11, color=ft.Colors.GREY_500),
            ], wrap=True))
        return self._card("Reflection", body, ft.Icons.AUTO_AWESOME)
