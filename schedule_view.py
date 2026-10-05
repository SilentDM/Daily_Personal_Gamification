import flet as ft
import database as db
from datetime import date, timedelta
from ui_helpers import confirm_action
from wallpaper import request_wallpaper_update as update_desktop_wallpaper
from constants import (
    SCORE_GREEN,
    SCORE_ORANGE,
    POSITIVE_SCORES,
    NEGATIVE_SCORES,
    CATEGORIES,
    DAY_NAMES,
)

CATEGORY_COLORS = {
    "Health": ft.Colors.GREEN_400,
    "Study": ft.Colors.BLUE_400,
    "Routine": ft.Colors.PURPLE_300,
    "Vice / Avoid": ft.Colors.RED_400,
}
SHORT_LABELS = {"Excellent": "Exc", "Ok": "Ok", "A Little": "Little", "Skipped": "Skip",
                "Resisted": "Resisted", "Slipped": "Slipped", "Relapsed": "Relapsed"}
TITLE_W, TODAY_W, DAY_W, ACTIONS_W = 250, 260, 92, 150
SETTING_REMINDER = "checkin_reminder_time"   # "HH:MM" or "" (off)
SETTING_REMINDED = "checkin_reminded_on"     # ISO date of the last reminder
DEFAULT_REMINDER = "21:30"


def options_for(is_negative: bool):
    """[(status, score)] in keyboard order (1, 2, 3, 4)."""
    scores = NEGATIVE_SCORES if is_negative else POSITIVE_SCORES
    return [(status, score) for status, score in scores.items() if score is not None]


def score_color(score):
    if score is None:
        return ft.Colors.GREY_700
    if score >= SCORE_GREEN:
        return ft.Colors.GREEN_ACCENT_700
    if score >= SCORE_ORANGE:
        return ft.Colors.ORANGE_ACCENT_700
    if score > 0:
        return ft.Colors.DEEP_ORANGE_700
    return ft.Colors.RED_700


def reminder_time() -> str:
    return db.get_hud_settings().get(SETTING_REMINDER, DEFAULT_REMINDER)


class ScheduleView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True)
        self.app_page = page
        self.daily_score_texts = {}
        self.viewing_current = True
        self.cursor = None          # (row index, day index) for keyboard input
        self.typing = False         # a text field has focus -> shortcuts off
        self.modal = False          # one of our dialogs is open -> shortcuts off
        self._sync_week()

        # Gamification banner elements
        self.streak_text = ft.Text("0 Days Streak", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_ACCENT)
        self.level_text = ft.Text("Level 1 • Novice", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT)
        self.xp_bar = ft.ProgressBar(value=0.0, width=180, color=ft.Colors.CYAN_ACCENT, bgcolor=ft.Colors.GREY_800)
        self.xp_fraction_text = ft.Text("0 / 10 XP", size=12, color=ft.Colors.GREY_400)

        self.render()

    # ------------------------------------------------------------ stats (also used by main.py)
    def update_gamification_stats(self):
        """Updates the Streak, Level (1-100), and XP progress."""
        streak = db.get_current_streak()
        total_xp, level, xp_in_level, rank_title = db.get_user_xp_and_level()

        self.streak_text.value = f"{streak} Day{'s' if streak != 1 else ''} Streak"
        self.level_text.value = f"Level {level} / 100 • {rank_title}"
        self.xp_bar.value = min(xp_in_level / 10.0, 1.0)
        if level >= 100:
            self.xp_fraction_text.value = "MAX LEVEL REACHED! (1,000 XP)"
        else:
            self.xp_fraction_text.value = f"{xp_in_level:.1f} / 10 XP to Lvl {level + 1} (Total: {total_xp:.1f} / 1000)"

    def calculate_daily_scores(self):
        self._sync_week()
        logs = db.get_current_week_logs(self.year, self.week)
        active_ids = {a[0] for a in db.get_activities()}
        for d in range(7):
            day_scores = [score for (act_id, day), (status, score) in logs.items()
                          if day == d and score is not None and act_id in active_ids]
            text = self.daily_score_texts.get(d)
            if text is None:
                continue
            if day_scores:
                avg = sum(day_scores) / len(day_scores)
                text.value = f"{avg:.1f} / 10"
                text.color = ft.Colors.GREEN_ACCENT if avg >= SCORE_GREEN else (
                    ft.Colors.ORANGE_ACCENT if avg >= SCORE_ORANGE else ft.Colors.RED_ACCENT)
            else:
                text.value, text.color = "- / 10", ft.Colors.GREY_500
        self.update_gamification_stats()
        if self.app_page:
            self.app_page.update()

    # ------------------------------------------------------------ week navigation
    def _sync_week(self):
        """Keeps the displayed week; follows the real week while viewing the current one."""
        cur_year, cur_week, real_today = db.get_current_week_info()
        if self.viewing_current:
            self.year, self.week = cur_year, cur_week
        # highlight "today" only when the displayed week is the current one
        self.today_idx = real_today if self.viewing_current else -1

    def _last_editable_day(self) -> int:
        return self.today_idx if self.viewing_current else 6

    def _shift_week(self, delta: int):
        monday = date.fromisocalendar(self.year, self.week, 1) + timedelta(weeks=delta)
        y, w, _ = monday.isocalendar()
        cur_year, cur_week, _ = db.get_current_week_info()
        if (y, w) > (cur_year, cur_week):
            return  # no logging in the future
        self.year, self.week = y, w
        self.viewing_current = ((y, w) == (cur_year, cur_week))
        self.cursor = None
        self.render()

    def _go_current_week(self):
        self.viewing_current = True
        self.cursor = None
        self.render()

    def _week_range_label(self):
        start = date.fromisocalendar(self.year, self.week, 1)
        return f"{start:%d/%m} - {start + timedelta(days=6):%d/%m}"

    # ------------------------------------------------------------ logging
    def set_status(self, activity_id: int, day_idx: int, is_negative: bool, status: str):
        """Saves one answer ("-" clears it). Future days can't be logged."""
        if day_idx > self._last_editable_day():
            return
        score = dict(options_for(is_negative)).get(status)
        db.save_log(activity_id, self.year, self.week, day_idx, status if score is not None else "-", score)
        update_desktop_wallpaper()

    def _click_today(self, row, act, status, current):
        act_id, _, _, is_neg = act
        self.set_status(act_id, self.today_idx, is_neg, "-" if status == current else status)
        self.cursor = (self._next_row(row, self.today_idx), self.today_idx)
        self.render()

    def _pick_past(self, row, act, day_idx, status):
        act_id, _, _, is_neg = act
        self.set_status(act_id, day_idx, is_neg, status)
        self.cursor = (row, day_idx)
        self.render()

    def _next_row(self, row: int, day_idx: int) -> int:
        """Next habit without an answer on that day (wrapping), or the next row."""
        acts = self._activities
        logs = self._logs
        n = len(acts)
        for step in range(1, n + 1):
            r = (row + step) % n
            if logs.get((acts[r][0], day_idx), ("-", None))[1] is None:
                return r
        return min(row + 1, n - 1) if n else 0

    def quick_fill_today(self, e):
        if not self.viewing_current:
            return  # Quick-Fill only makes sense for today
        for act_id, _, _, is_neg in db.get_activities():
            if self._logs.get((act_id, self.today_idx), ("-", None))[1] is None:
                status = "Resisted" if is_neg else "Ok"
                db.save_log(act_id, self.year, self.week, self.today_idx, status, dict(options_for(is_neg))[status])
        self.render()
        update_desktop_wallpaper()

    def export_csv_clicked(self, e):
        db.export_to_csv()
        e.control.content = "Exported to Desktop!"
        e.control.icon = ft.Icons.CHECK
        self.app_page.update()

    # ------------------------------------------------------------ keyboard (wired in main.py)
    def handle_key(self, e) -> bool:
        """1-4 answer the highlighted cell (and jump to the next open habit), 0/Backspace clear,
        arrows move. Returns True when the key was used."""
        if not self.visible or self.typing or self.modal or not getattr(self, "_activities", None):
            return False
        if e.ctrl or e.alt or e.meta:
            return False
        key = (e.key or "").replace("Numpad ", "")
        row, day = self.cursor or self._default_cursor()
        acts = self._activities
        if key in ("Arrow Up", "Arrow Down"):
            row = max(0, min(len(acts) - 1, row + (-1 if key == "Arrow Up" else 1)))
        elif key in ("Arrow Left", "Arrow Right"):
            day = max(0, min(self._last_editable_day(), day + (-1 if key == "Arrow Left" else 1)))
        elif key in ("1", "2", "3", "4"):
            act_id, _, _, is_neg = acts[row]
            opts = options_for(is_neg)
            idx = int(key) - 1
            if idx >= len(opts):
                return True
            self.set_status(act_id, day, is_neg, opts[idx][0])
            self._logs = db.get_current_week_logs(self.year, self.week)
            row = self._next_row(row, day)
        elif key in ("0", "Backspace", "Delete"):
            act_id, _, _, is_neg = acts[row]
            self.set_status(act_id, day, is_neg, "-")
        else:
            return False
        self.cursor = (row, day)
        self.render()
        return True

    def _default_cursor(self):
        day = self._last_editable_day()
        if day < 0:
            return 0, 0
        first_open = next((i for i, a in enumerate(self._activities)
                           if self._logs.get((a[0], day), ("-", None))[1] is None), 0)
        return first_open, day

    # ------------------------------------------------------------ habits
    def on_delete_activity(self, activity_id):
        db.delete_activity(activity_id)
        self.render()
        update_desktop_wallpaper()

    def on_move_activity(self, activity_id: int, direction: str):
        db.move_activity(activity_id, direction)
        self.render()
        update_desktop_wallpaper()

    def _dialog(self, dlg):
        self.modal = True
        self.app_page.show_dialog(dlg)

    def _close(self, e=None):
        self.modal = False
        self.app_page.pop_dialog()

    def _edit_activity(self, act):
        act_id, name, category, is_neg = act
        name_f = ft.TextField(label="Name", value=name, dense=True, autofocus=True)
        cats = ["Vice / Avoid"] if is_neg else [c for c in CATEGORIES if c != "Vice / Avoid"]
        cat_dd = ft.Dropdown(label="Category", value=category if category in cats else cats[0], dense=True,
                             options=[ft.DropdownOption(c) for c in cats])

        def save(e=None):
            if (name_f.value or "").strip():
                db.update_activity(act_id, name=name_f.value.strip(), category=cat_dd.value)
            self._close()
            self.render()

        name_f.on_submit = save
        self._dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Edit habit", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=400, content=ft.Column([
                name_f, cat_dd,
                ft.Text("Vice / bad habit (inverted scoring)" if is_neg else "Positive habit", size=12,
                        color=ft.Colors.GREY_400),
            ], spacing=12, tight=True)),
            actions=[ft.TextButton("Cancel", on_click=self._close), ft.Button("Save", on_click=save)]))

    def _confirm_delete(self, act):
        self.modal = True  # shortcuts stay off while the dialog is open

        def done():
            self.modal = False
            self.on_delete_activity(act[0])

        confirm_action(self.app_page, "Delete habit?",
                       f"'{act[1]}' will be removed from the grid, charts and daily XP.", done,
                       on_cancel=lambda: setattr(self, "modal", False))

    def _reminder_settings(self):
        current = reminder_time()
        enabled = ft.Switch(label="Remind me to do my check-in", value=bool(current))
        times = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        time_dd = ft.Dropdown(label="At", value=current or DEFAULT_REMINDER, dense=True, width=140, menu_height=320,
                              options=[ft.DropdownOption(t) for t in times])

        def save(e):
            db.set_hud_setting(SETTING_REMINDER, time_dd.value if enabled.value else "")
            self._close()
            self.render()

        self._dialog(ft.AlertDialog(
            modal=True, title=ft.Row([ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED),
                                      ft.Text("Nightly check-in reminder", weight=ft.FontWeight.BOLD)]),
            content=ft.Container(width=420, content=ft.Column([
                enabled, time_dd,
                ft.Text("A tray notification appears at this time only if some of today's habits are still "
                        "unmarked. The tracker also opens on this tab.", size=12, color=ft.Colors.GREY_400),
            ], spacing=12, tight=True)),
            actions=[ft.TextButton("Cancel", on_click=self._close), ft.Button("Save", on_click=save)]))

    # ------------------------------------------------------------ rendering
    def render(self):
        self.controls.clear()
        self._sync_week()
        self._logs = db.get_current_week_logs(self.year, self.week)
        self._activities = db.get_activities()
        if self._activities:
            if self.cursor is None or self.cursor[0] >= len(self._activities) or \
                    self.cursor[1] > self._last_editable_day():
                self.cursor = self._default_cursor()

        self.controls.append(self._banner())
        self.controls.append(self._title_row())
        self.controls.append(self._header_row())
        for row, act in enumerate(self._activities):
            self.controls.append(self._activity_row(row, act))
        self.controls.append(self._add_row())
        self.controls.append(self._footer_row())
        self.calculate_daily_scores()

    def _banner(self):
        return ft.Container(
            content=ft.Row([
                ft.Row([ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, color=ft.Colors.ORANGE_ACCENT, size=28), self.streak_text]),
                ft.VerticalDivider(width=30),
                ft.Column([self.level_text, ft.Row([self.xp_bar, self.xp_fraction_text])], spacing=3),
                ft.Row([
                    ft.Button(content="Quick-Fill Today", icon=ft.Icons.BOLT, icon_color=ft.Colors.AMBER_ACCENT,
                              on_click=self.quick_fill_today, disabled=not self.viewing_current,
                              tooltip="Marks every unmarked habit today as Ok / Resisted"),
                    ft.Button(content="Export CSV", icon=ft.Icons.DOWNLOAD, on_click=self.export_csv_clicked),
                ]),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=12, padding=15,
            margin=ft.Margin.symmetric(horizontal=15, vertical=10))

    def _title_row(self):
        if self.viewing_current and self._activities:
            marked = sum(1 for a in self._activities
                         if self._logs.get((a[0], self.today_idx), ("-", None))[1] is not None)
            total = len(self._activities)
            progress = ft.Container(
                content=ft.Text(f"Today {marked}/{total} marked" + (" ✓" if marked == total else ""), size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLACK if marked == total else ft.Colors.CYAN_ACCENT),
                bgcolor=ft.Colors.GREEN_ACCENT if marked == total else ft.Colors.with_opacity(0.12, ft.Colors.CYAN),
                border_radius=12, padding=ft.Padding.symmetric(horizontal=10, vertical=4))
        else:
            progress = ft.Text("• Editing a past week (XP updates accordingly)", size=14, color=ft.Colors.CYAN_ACCENT)
        rem = reminder_time()
        return ft.Container(
            content=ft.Row([
                ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=ft.Colors.CYAN_ACCENT, tooltip="Previous week",
                              on_click=lambda e: self._shift_week(-1)),
                ft.Text(f"Week {self.week} ({self.year})", size=22, weight=ft.FontWeight.BOLD),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=ft.Colors.CYAN_ACCENT, tooltip="Next week",
                              disabled=self.viewing_current, on_click=lambda e: self._shift_week(1)),
                ft.Text(self._week_range_label(), size=14, color=ft.Colors.GREY_400),
                progress,
                ft.Button(content="This week", icon=ft.Icons.TODAY, disabled=self.viewing_current,
                          on_click=lambda e: self._go_current_week()),
                ft.Container(expand=True),
                ft.Text("Keys: 1-4 mark • 0 clear • arrows move", size=11, color=ft.Colors.GREY_500),
                ft.IconButton(ft.Icons.NOTIFICATIONS_ACTIVE if rem else ft.Icons.NOTIFICATIONS_OFF_OUTLINED,
                              icon_color=ft.Colors.AMBER_ACCENT if rem else ft.Colors.GREY_500,
                              tooltip=f"Check-in reminder at {rem}" if rem else "Check-in reminder off",
                              on_click=lambda e: self._reminder_settings()),
            ], spacing=8),
            padding=ft.Padding.only(left=20, right=20, top=5, bottom=5))

    def _day_width(self, d):
        return TODAY_W if d == self.today_idx else DAY_W

    def _header_row(self):
        cells = [ft.Container(content=ft.Text("Activity & Category", weight=ft.FontWeight.BOLD, size=14),
                              width=TITLE_W, padding=10)]
        for i, day in enumerate(DAY_NAMES):
            is_today = i == self.today_idx
            future = i > self._last_editable_day()
            cells.append(ft.Container(
                content=ft.Text(day + (" (Today)" if is_today else ""), weight=ft.FontWeight.BOLD,
                                color=ft.Colors.CYAN_ACCENT if is_today else (
                                    ft.Colors.GREY_600 if future else ft.Colors.WHITE)),
                width=self._day_width(i), alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.BLUE_GREY_900 if is_today else ft.Colors.TRANSPARENT,
                border_radius=8, padding=5))
        cells.append(ft.Container(width=ACTIONS_W))
        return ft.Container(content=ft.Row(cells), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8,
                            padding=5, margin=ft.Margin.symmetric(horizontal=15))

    def _activity_row(self, row, act):
        act_id, act_name, category, is_negative = act
        cat_color = CATEGORY_COLORS.get(category, ft.Colors.GREY_400)
        cells = [ft.Container(
            content=ft.Row([
                ft.Text(act_name, size=13, weight=ft.FontWeight.W_500, expand=True),
                ft.Container(content=ft.Text(category, size=10, color=cat_color, weight=ft.FontWeight.BOLD),
                             border=ft.Border.all(1, cat_color), border_radius=4,
                             padding=ft.Padding.symmetric(horizontal=4, vertical=1)),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            width=TITLE_W, padding=ft.Padding.only(left=10, right=5))]
        for d in range(7):
            status, score = self._logs.get((act_id, d), ("-", None))
            focused = self.cursor == (row, d)
            if d == self.today_idx:
                cell = self._today_cell(row, act, status)
            elif d > self._last_editable_day():
                cell = ft.Container(content=ft.Text("", size=11), width=DAY_W - 8, height=30, border_radius=6,
                                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE))
            else:
                cell = self._past_cell(row, act, d, status, score)
            cells.append(ft.Container(
                content=cell, width=self._day_width(d), alignment=ft.Alignment.CENTER, padding=2, border_radius=8,
                border=ft.Border.all(2, ft.Colors.CYAN_ACCENT) if focused else None,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.CYAN) if d == self.today_idx else None))
        cells.append(ft.Container(
            content=ft.Row([
                ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=16, icon_color=ft.Colors.GREY_400, tooltip="Edit habit",
                              on_click=lambda e, a=act: self._edit_activity(a)),
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16, icon_color=ft.Colors.GREY_400, tooltip="Move Up",
                              on_click=lambda e, a=act_id: self.on_move_activity(a, "up")),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=16, icon_color=ft.Colors.GREY_400, tooltip="Move Down",
                              on_click=lambda e, a=act_id: self.on_move_activity(a, "down")),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, icon_size=18,
                              tooltip="Delete activity", on_click=lambda e, a=act: self._confirm_delete(a)),
            ], spacing=0, alignment=ft.MainAxisAlignment.END),
            width=ACTIONS_W, alignment=ft.Alignment.CENTER))
        return ft.Container(content=ft.Row(cells), padding=ft.Padding.symmetric(horizontal=15, vertical=2))

    def _today_cell(self, row, act, current):
        """One click per habit: every option is a button; clicking the selected one clears it."""
        buttons = []
        for i, (status, score) in enumerate(options_for(act[3]), 1):
            selected = status == current
            color = score_color(score)
            buttons.append(ft.Container(
                content=ft.Text(SHORT_LABELS.get(status, status), size=11, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE if selected else ft.Colors.GREY_400, no_wrap=True),
                bgcolor=color if selected else None,
                border=ft.Border.all(1, color if selected else ft.Colors.GREY_700),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=6),
                alignment=ft.Alignment.CENTER, expand=True, ink=True,
                tooltip=f"{status} (+{score}) • key {i}" + (" • click again to clear" if selected else ""),
                on_click=lambda e, s=status: self._click_today(row, act, s, current)))
        return ft.Row(buttons, spacing=3)

    def _past_cell(self, row, act, d, status, score):
        """A coloured square; one click opens a short menu to set/correct it."""
        answered = score is not None
        chip = ft.Container(
            content=ft.Text(SHORT_LABELS.get(status, status) if answered else "—", size=11,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if answered else ft.Colors.GREY_500),
            width=DAY_W - 8, height=30, border_radius=6, alignment=ft.Alignment.CENTER,
            bgcolor=score_color(score) if answered else ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=None if answered else ft.Border.all(1, ft.Colors.GREY_800))
        items = [ft.PopupMenuItem(content=ft.Text(f"{s}  (+{sc})"), checked=s == status,
                                  on_click=lambda e, s=s: self._pick_past(row, act, d, s))
                 for s, sc in options_for(act[3])]
        items.append(ft.PopupMenuItem(content=ft.Text("Clear"), on_click=lambda e: self._pick_past(row, act, d, "-")))
        return ft.PopupMenuButton(content=chip, items=items, tooltip=f"{DAY_NAMES[d]}: {status if answered else 'not marked'}")

    def _add_row(self):
        new_input = ft.TextField(hint_text="New activity name...", width=200, dense=True, text_size=13)
        new_input.on_focus = lambda e: setattr(self, "typing", True)
        new_input.on_blur = lambda e: setattr(self, "typing", False)
        cat_dropdown = ft.Dropdown(value="Routine", width=130, dense=True, text_size=12, content_padding=5,
                                   options=[ft.DropdownOption(cat) for cat in CATEGORIES])
        bad_habit = ft.Checkbox(label="Vice / Bad Habit", value=False)

        def on_cat_change(e):
            bad_habit.value = cat_dropdown.value == "Vice / Avoid"
            self.app_page.update()

        cat_dropdown.on_select = on_cat_change

        def add_clicked(e=None):
            if new_input.value and new_input.value.strip():
                db.add_activity(name=new_input.value.strip(), category=cat_dropdown.value,
                                is_negative=bad_habit.value)
                new_input.value = ""
                self.typing = False
                self.render()

        new_input.on_submit = add_clicked
        return ft.Container(
            content=ft.Row([new_input, cat_dropdown, bad_habit,
                            ft.IconButton(icon=ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.CYAN_ACCENT, icon_size=28,
                                          tooltip="Add Activity", on_click=add_clicked)]),
            padding=ft.Padding.only(left=15, top=10))

    def _footer_row(self):
        cells = [ft.Container(content=ft.Text("Daily Score (0-10)", weight=ft.FontWeight.BOLD, size=14),
                              width=TITLE_W, padding=10)]
        for d in range(7):
            text = ft.Text("- / 10", weight=ft.FontWeight.BOLD, size=13)
            self.daily_score_texts[d] = text
            cells.append(ft.Container(
                content=text, width=self._day_width(d), alignment=ft.Alignment.CENTER, border_radius=8, padding=8,
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.CYAN) if d == self.today_idx
                else ft.Colors.SURFACE_CONTAINER_HIGHEST))
        cells.append(ft.Container(width=ACTIONS_W))
        return ft.Container(content=ft.Row(cells), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, border_radius=8,
                            padding=5, margin=ft.Margin.only(left=15, right=15, top=20, bottom=30))
