import calendar
from datetime import date, datetime, timedelta

import flet as ft

import database as db
from constants import DAY_NAMES, XP_EVENT
from study_view import open_review_dialog, REVIEW_COLOR
from ui_helpers import confirm_action
from wallpaper import request_wallpaper_update as update_desktop_wallpaper

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

EVENT_COLORS = {
    "Cyan": ft.Colors.CYAN_400,
    "Blue": ft.Colors.BLUE_400,
    "Green": ft.Colors.GREEN_400,
    "Amber": ft.Colors.AMBER_400,
    "Orange": ft.Colors.DEEP_ORANGE_400,
    "Red": ft.Colors.RED_400,
    "Pink": ft.Colors.PINK_300,
    "Purple": ft.Colors.PURPLE_300,
    "Grey": ft.Colors.BLUE_GREY_400,
}
DURATION_OPTIONS = [(15, "15 min"), (30, "30 min"), (45, "45 min"), (60, "1 hour"), (90, "1h 30min"),
                    (120, "2 hours"), (180, "3 hours"), (240, "4 hours"), (480, "8 hours")]
REMINDER_OPTIONS = [(db.NO_REMINDER, "No reminder"), (0, "At start time"), (5, "5 min before"),
                    (10, "10 min before"), (15, "15 min before"), (30, "30 min before"),
                    (60, "1 hour before"), (120, "2 hours before"), (1440, "1 day before")]
ALL_DAY_REMINDER_OPTIONS = [(db.NO_REMINDER, "No reminder"), (0, "On the day (09:00)"),
                            (1440, "The day before (09:00)")]

VIEWS = ("month", "week", "day", "agenda")
HOUR_HEIGHT = 48           # px per hour in the week/day time grid
MIN_BLOCK_MINUTES = 25     # very short events are drawn at least this tall
GUTTER_WIDTH = 56
DEFAULT_SCROLL_HOUR = 7
AGENDA_DAYS = 60
SEARCH_DAYS = 366


# ---------------------------------------------------------------- helpers
def color_of(occ) -> str:
    return EVENT_COLORS.get(occ.get("color"), EVENT_COLORS["Cyan"])


def fmt_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def fmt_range(occ) -> str:
    if occ["all_day"]:
        return "All day"
    start, end = db.occurrence_start(occ), db.occurrence_end(occ)
    end_txt = f"{end:%H:%M}" if end.date() == start.date() else f"{end:%H:%M} (+1d)"
    return f"{start:%H:%M} – {end_txt}"


def fmt_date_long(d: date) -> str:
    return f"{WEEKDAY_NAMES[d.weekday()]}, {d.day} {MONTH_NAMES[d.month]} {d.year}"


def fmt_date_short(d: date) -> str:
    return f"{DAY_NAMES[d.weekday()]}, {d.day} {MONTH_NAMES[d.month][:3]}"


def repeat_options(start: date):
    nth = start.day
    return [
        ("none", "Does not repeat"),
        ("daily", "Every day"),
        ("weekdays", "Every weekday (Mon–Fri)"),
        ("weekly", f"Weekly on {WEEKDAY_NAMES[start.weekday()]}"),
        ("monthly", f"Monthly on day {nth}" + (" (or last day)" if nth > 28 else "")),
        ("yearly", f"Yearly on {nth} {MONTH_NAMES[start.month]}"),
    ]


def repeat_text(occ) -> str:
    if occ["recurrence"] == "none":
        return ""
    label = dict(repeat_options(date.fromisoformat(occ["event_date"])))[occ["recurrence"]]
    if occ["recurrence_end"]:
        label += f", until {date.fromisoformat(occ['recurrence_end']):%d/%m/%Y}"
    return label


def reminder_text(occ) -> str:
    opts = ALL_DAY_REMINDER_OPTIONS if occ["all_day"] else REMINDER_OPTIONS
    return dict(opts).get(occ["reminder_min"], f"{occ['reminder_min']} min before")


def time_slots(extra_minutes=None):
    """Start times every 15 minutes (plus the event's own time if it is off-grid)."""
    slots = {h * 60 + m for h in range(24) for m in (0, 15, 30, 45)}
    if extra_minutes is not None:
        slots.add(extra_minutes)
    return sorted(slots)


def layout_timed(occs):
    """Places overlapping events side by side.

    Returns [(group_top_min, group_bottom_min, [[(occ, start_min, end_min), ...] per lane])].
    """
    items = []
    for o in occs:
        if o["all_day"]:
            continue
        start = o["start_hour"] * 60 + o["start_minute"]
        end = min(24 * 60, start + max(o["duration_min"], MIN_BLOCK_MINUTES))
        items.append((o, start, end))
    items.sort(key=lambda t: (t[1], -t[2]))

    groups, current, current_end = [], [], None
    for item in items:
        if current and item[1] >= current_end:
            groups.append(current)
            current, current_end = [], None
        current.append(item)
        current_end = item[2] if current_end is None else max(current_end, item[2])
    if current:
        groups.append(current)

    result = []
    for group in groups:
        lanes = []
        for item in group:
            for lane in lanes:
                if lane[-1][2] <= item[1]:
                    lane.append(item)
                    break
            else:
                lanes.append([item])
        result.append((group[0][1], max(i[2] for i in group), lanes))
    return result


# ---------------------------------------------------------------- view
class CalendarView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, visible=False, spacing=0)
        self.app_page = page
        self.anchor = date.today()      # the day the current view is built around
        self.search = ""
        self._grid_scroll = None
        self._pending_scroll = None
        try:
            saved = db.get_hud_settings().get("calendar_view", "month")
        except Exception:
            saved = "month"
        self.view = saved if saved in VIEWS else "month"
        self.render()

    # ------------------------------------------------------------ navigation
    def set_view(self, view: str, anchor: date = None):
        if anchor is not None:
            self.anchor = anchor
        if view != self.view:
            self.view = view
            try:
                db.set_hud_setting("calendar_view", view)
            except Exception:
                pass
        self.render()

    def go_today(self, e=None):
        self.anchor = date.today()
        self.render()

    def step(self, direction: int):
        a = self.anchor
        if self.view == "month":
            month = a.month - 1 + direction
            year, month = a.year + month // 12, month % 12 + 1
            self.anchor = date(year, month, min(a.day, calendar.monthrange(year, month)[1]))
        elif self.view == "week":
            self.anchor = a + timedelta(days=7 * direction)
        elif self.view == "day":
            self.anchor = a + timedelta(days=direction)
        else:
            self.anchor = a + timedelta(days=30 * direction)
        self.render()

    def open_day(self, d: date):
        self.set_view("day", d)

    def _changed(self):
        """Call after any data change."""
        self.render()
        update_desktop_wallpaper()

    # ------------------------------------------------------------ rendering
    def render(self):
        self.controls.clear()
        self._grid_scroll = None
        self.controls.append(self._toolbar())
        body = {
            "month": self._month_view,
            "week": self._week_view,
            "day": self._day_view,
            "agenda": self._agenda_view,
        }[self.view]()
        self.controls.append(ft.Container(content=body, expand=True,
                                          padding=ft.Padding.only(left=16, right=16, bottom=12)))
        if self.app_page:
            self.app_page.update()
        self._apply_pending_scroll()

    def _apply_pending_scroll(self):
        if self._grid_scroll is None or self._pending_scroll is None or not self.app_page:
            return
        offset, self._pending_scroll = self._pending_scroll, None
        try:
            self.app_page.run_task(self._grid_scroll.scroll_to, offset=offset)
        except Exception:
            pass

    def _title_text(self) -> str:
        a = self.anchor
        if self.view == "month":
            return f"{MONTH_NAMES[a.month]} {a.year}"
        if self.view == "week":
            start = a - timedelta(days=a.weekday())
            end = start + timedelta(days=6)
            if start.month == end.month:
                return f"{start.day} – {end.day} {MONTH_NAMES[end.month]} {end.year}"
            if start.year == end.year:
                return f"{start.day} {MONTH_NAMES[start.month][:3]} – {end.day} {MONTH_NAMES[end.month][:3]} {end.year}"
            return f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
        if self.view == "day":
            return fmt_date_long(a)
        if self.search:
            return f'Search: "{self.search}"'
        return f"Agenda from {a.day} {MONTH_NAMES[a.month][:3]} {a.year}"

    def _toolbar(self):
        switcher = ft.SegmentedButton(
            segments=[
                ft.Segment(value="month", label=ft.Text("Month"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_MONTH)),
                ft.Segment(value="week", label=ft.Text("Week"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_WEEK)),
                ft.Segment(value="day", label=ft.Text("Day"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_DAY)),
                ft.Segment(value="agenda", label=ft.Text("Agenda"), icon=ft.Icon(ft.Icons.VIEW_AGENDA)),
            ],
            selected=[self.view],
            show_selected_icon=False,
            on_change=lambda e: self.set_view(e.control.selected[0]) if e.control.selected else None,
        )
        return ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.OutlinedButton("Today", on_click=self.go_today),
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Previous", on_click=lambda e: self.step(-1)),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Next", on_click=lambda e: self.step(1)),
                    ft.Text(self._title_text(), size=22, weight=ft.FontWeight.BOLD),
                ], spacing=6),
                ft.Row([
                    switcher,
                    ft.Button("New event", icon=ft.Icons.ADD, on_click=lambda e: self.open_editor()),
                ], spacing=12),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            padding=ft.Padding.only(left=16, right=16, top=14, bottom=10),
        )

    # ------------------------------------------------------------ study reviews
    def _reviews_by_day(self, start: date, end: date):
        """Pending study reviews per day; overdue ones are shown on today."""
        today = date.today()
        out = {}
        for r in db.get_pending_reviews(until=end):
            d = max(date.fromisoformat(r["due_date"]), today)
            if start <= d <= end:
                out.setdefault(d, []).append(r)
        return out

    def _open_review(self, review):
        open_review_dialog(self.app_page, review, on_done=self._changed)

    def _review_chip(self, review):
        overdue = date.fromisoformat(review["due_date"]) < date.today()
        return ft.Container(
            content=ft.Text(f"📚 Review: {review['topic']}", size=11, no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.BLACK),
            bgcolor=ft.Colors.RED_ACCENT_100 if overdue else REVIEW_COLOR,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
            tooltip=f"Study review {review['review_no']}" + (" (overdue)" if overdue else ""),
            on_click=lambda e, r=review: self._open_review(r),
        )

    def _review_row(self, review, compact: bool = False):
        overdue = date.fromisoformat(review["due_date"]) < date.today()
        return ft.Container(
            content=ft.Row([
                ft.IconButton(ft.Icons.REPLAY, icon_color=REVIEW_COLOR, icon_size=18 if compact else 22,
                              tooltip="Start review", on_click=lambda e, r=review: self._open_review(r)),
                ft.Container(width=4, height=28 if compact else 36, bgcolor=REVIEW_COLOR, border_radius=2),
                ft.Column([
                    ft.Text(f"Review: {review['topic']}", size=13 if compact else 14, weight=ft.FontWeight.W_600,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Study review {review['review_no']}" +
                            (f" • overdue since {date.fromisoformat(review['due_date']):%d/%m}" if overdue else ""),
                            size=11, color=ft.Colors.RED_ACCENT_100 if overdue else ft.Colors.GREY_400),
                ], spacing=0, expand=True, tight=True),
            ], spacing=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8,
            padding=ft.Padding.only(right=10, top=2, bottom=2), ink=True,
            on_click=lambda e, r=review: self._open_review(r),
        )

    # ------------------------------------------------------------ month
    def _month_view(self):
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.anchor.year, self.anchor.month)
        by_day = db.get_events_between(weeks[0][0], weeks[-1][-1])
        done = db.get_completed_events(weeks[0][0].isoformat(), weeks[-1][-1].isoformat())
        reviews = self._reviews_by_day(weeks[0][0], weeks[-1][-1])
        today = date.today()

        header = ft.Row([
            ft.Container(
                content=ft.Text(name, size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500 if i >= 5 else ft.Colors.GREY_300),
                expand=True, alignment=ft.Alignment.CENTER, padding=6,
            ) for i, name in enumerate(DAY_NAMES)
        ], spacing=4)

        rows = []
        for week in weeks:
            cells = []
            for d in week:
                cells.append(self._month_cell(d, by_day[d], done, today, reviews.get(d, [])))
            rows.append(ft.Row(cells, spacing=4, expand=True,
                               vertical_alignment=ft.CrossAxisAlignment.STRETCH))
        return ft.Column([header, *rows], spacing=4, expand=True)

    def _month_cell(self, d: date, occs, done, today, reviews=()):
        in_month = d.month == self.anchor.month
        is_today = d == today
        max_chips = 3

        number = ft.Container(
            content=ft.Text(str(d.day), size=13, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLACK if is_today else (ft.Colors.WHITE if in_month else ft.Colors.GREY_600)),
            bgcolor=ft.Colors.CYAN_ACCENT if is_today else None,
            border_radius=12, width=24, height=24, alignment=ft.Alignment.CENTER,
        )
        chips = [self._review_chip(r) for r in reviews]
        chips += [self._chip(o, (o["id"], o["date"]) in done) for o in occs]
        total = len(chips)
        chips = chips[:max_chips]
        if total > max_chips:
            chips.append(ft.Text(f"+{total - max_chips} more", size=10, color=ft.Colors.CYAN_ACCENT))

        return ft.Container(
            content=ft.Column([number, *chips], spacing=2, tight=True),
            expand=True,
            padding=6,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if in_month else ft.Colors.with_opacity(0.4, ft.Colors.SURFACE_CONTAINER_HIGH),
            border=ft.Border.all(1, ft.Colors.CYAN_ACCENT if is_today else ft.Colors.with_opacity(0.15, ft.Colors.GREY)),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            ink=True,
            tooltip=f"{len(occs)} event(s) – open day" if occs else "Open day",
            on_click=lambda e, day=d: self.open_day(day),
        )

    def _chip(self, occ, is_done: bool):
        color = color_of(occ)
        label = occ["title"] if occ["all_day"] else f"{fmt_time(occ['start_hour'], occ['start_minute'])} {occ['title']}"
        return ft.Container(
            content=ft.Text(label, size=11, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.GREY_500 if is_done else ft.Colors.WHITE,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_done else None)),
            bgcolor=ft.Colors.with_opacity(0.85 if occ["all_day"] else 0.22, color),
            border=ft.Border.only(left=ft.BorderSide(3, color)),
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
            on_click=lambda e, o=occ: self.open_details(o),
        )

    # ------------------------------------------------------------ week / day time grid
    def _week_view(self):
        start = self.anchor - timedelta(days=self.anchor.weekday())
        return self._time_grid([start + timedelta(days=i) for i in range(7)], compact=True)

    def _day_view(self):
        grid = self._time_grid([self.anchor], compact=False)
        return ft.Row([
            ft.Container(content=grid, expand=True),
            ft.Container(content=self._day_side_panel(), width=280),
        ], spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH, expand=True)

    def _time_grid(self, days, compact: bool):
        by_day = db.get_events_between(days[0], days[-1])
        done = db.get_completed_events(days[0].isoformat(), days[-1].isoformat())
        today = date.today()
        now = datetime.now()

        # day headers
        header_cells = [ft.Container(width=GUTTER_WIDTH)]
        for d in days:
            is_today = d == today
            header_cells.append(ft.Container(
                content=ft.Column([
                    ft.Text(DAY_NAMES[d.weekday()].upper(), size=11,
                            color=ft.Colors.CYAN_ACCENT if is_today else ft.Colors.GREY_400),
                    ft.Container(
                        content=ft.Text(str(d.day), size=18, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLACK if is_today else ft.Colors.WHITE),
                        bgcolor=ft.Colors.CYAN_ACCENT if is_today else None,
                        border_radius=16, width=32, height=32, alignment=ft.Alignment.CENTER,
                    ),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                expand=True, padding=4, border_radius=8, ink=compact,
                on_click=(lambda e, day=d: self.open_day(day)) if compact else None,
                tooltip="Open day" if compact else None,
            ))

        # all-day strip (only when there is something to show)
        all_day_row = None
        reviews = self._reviews_by_day(days[0], days[-1])
        if reviews or any(o["all_day"] for d in days for o in by_day[d]):
            cells = [ft.Container(content=ft.Text("all-day", size=10, color=ft.Colors.GREY_500),
                                  width=GUTTER_WIDTH, alignment=ft.Alignment.CENTER_RIGHT,
                                  padding=ft.Padding.only(right=6))]
            for d in days:
                cells.append(ft.Container(
                    content=ft.Column([self._review_chip(r) for r in reviews.get(d, [])] +
                                      [self._chip(o, (o["id"], o["date"]) in done)
                                       for o in by_day[d] if o["all_day"]], spacing=2, tight=True),
                    expand=True, padding=2,
                ))
            all_day_row = ft.Row(cells, spacing=4, vertical_alignment=ft.CrossAxisAlignment.START)

        # hour gutter
        gutter = ft.Column([
            ft.Container(
                content=ft.Text(f"{h:02d}:00", size=10, color=ft.Colors.GREY_500) if h else None,
                height=HOUR_HEIGHT, width=GUTTER_WIDTH,
                alignment=ft.Alignment.TOP_RIGHT, padding=ft.Padding.only(right=6),
            ) for h in range(24)
        ], spacing=0)

        columns = [gutter]
        for d in days:
            columns.append(self._day_column(d, by_day[d], done, now, compact))

        self._grid_scroll = ft.Column(
            [ft.Row(columns, spacing=4, vertical_alignment=ft.CrossAxisAlignment.START)],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0,
        )
        first_timed = min((o["start_hour"] for d in days for o in by_day[d] if not o["all_day"]), default=None)
        scroll_hour = DEFAULT_SCROLL_HOUR
        if today in days:
            scroll_hour = max(0, now.hour - 2)
        elif first_timed is not None:
            scroll_hour = max(0, first_timed - 1)
        # Flutter lets scroll_to overshoot, so keep the last hour at the bottom edge at most
        visible = (getattr(self.app_page, "height", None) or 800) - 200
        self._pending_scroll = max(0, min(scroll_hour * HOUR_HEIGHT, 24 * HOUR_HEIGHT - visible))

        parts = [ft.Row(header_cells, spacing=4)]
        if all_day_row:
            parts.append(all_day_row)
        parts.append(ft.Divider(height=1, color=ft.Colors.GREY_800))
        parts.append(self._grid_scroll)
        return ft.Column(parts, spacing=4, expand=True)

    def _day_column(self, d: date, occs, done, now: datetime, compact: bool):
        is_today = d == now.date()
        weekend = d.weekday() >= 5
        stack = []

        # clickable hour slots (background grid)
        stack.append(ft.Column([
            ft.Container(
                height=HOUR_HEIGHT,
                border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.GREY))),
                bgcolor=ft.Colors.with_opacity(0.03 if weekend else 0.0, ft.Colors.WHITE),
                ink=True,
                tooltip=f"New event at {h:02d}:00",
                on_click=lambda e, day=d, hour=h: self.open_editor(day=day, hour=hour),
            ) for h in range(24)
        ], spacing=0))

        # event blocks (overlapping events share the width)
        for top_min, bottom_min, lanes in layout_timed(occs):
            lane_controls = []
            for lane in lanes:
                blocks = [self._block(o, s - top_min, e - s, (o["id"], o["date"]) in done, compact)
                          for o, s, e in lane]
                lane_controls.append(ft.Stack(blocks, expand=True))
            stack.append(ft.Container(
                content=ft.Row(lane_controls, spacing=2, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
                left=2, right=2,
                top=top_min / 60 * HOUR_HEIGHT,
                height=(bottom_min - top_min) / 60 * HOUR_HEIGHT,
            ))

        # current time indicator
        if is_today:
            y = (now.hour * 60 + now.minute) / 60 * HOUR_HEIGHT
            stack.append(ft.Container(height=2, bgcolor=ft.Colors.RED_ACCENT, left=0, right=0, top=y))
            stack.append(ft.Container(width=10, height=10, border_radius=5, bgcolor=ft.Colors.RED_ACCENT,
                                      left=-4, top=y - 4))

        return ft.Container(
            content=ft.Stack(stack, height=24 * HOUR_HEIGHT, clip_behavior=ft.ClipBehavior.NONE),
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.CYAN) if is_today else None,
            border_radius=6,
        )

    def _block(self, occ, top_min, length_min, is_done: bool, compact: bool):
        color = color_of(occ)
        height = length_min / 60 * HOUR_HEIGHT
        lines = [ft.Text(occ["title"], size=12, weight=ft.FontWeight.BOLD, no_wrap=compact,
                         max_lines=1 if height < 40 else 3, overflow=ft.TextOverflow.ELLIPSIS,
                         color=ft.Colors.GREY_400 if is_done else ft.Colors.WHITE,
                         style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_done else None))]
        if height >= 34:
            icons = (" ↻" if occ["recurrence"] != "none" else "") + (" ✓" if is_done else "")
            lines.append(ft.Text(fmt_range(occ) + icons, size=10, color=ft.Colors.GREY_300, no_wrap=True))
        if not compact and height >= 70 and occ["notes"]:
            lines.append(ft.Text(occ["notes"], size=10, color=ft.Colors.GREY_400, max_lines=2,
                                 overflow=ft.TextOverflow.ELLIPSIS))
        return ft.Container(
            content=ft.Column(lines, spacing=0, tight=True),
            left=0, right=0,
            top=top_min / 60 * HOUR_HEIGHT,
            height=max(height - 2, 14),
            bgcolor=ft.Colors.with_opacity(0.12 if is_done else 0.3, color),
            border=ft.Border.only(left=ft.BorderSide(3, color)),
            border_radius=4,
            padding=ft.Padding.only(left=6, right=4, top=2),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            tooltip=f"{occ['title']}\n{fmt_range(occ)}",
            on_click=lambda e, o=occ: self.open_details(o),
        )

    def _day_side_panel(self):
        a = self.anchor
        # mini month for quick navigation
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(a.year, a.month)
        busy = {d for d, occ in db.get_events_between(weeks[0][0], weeks[-1][-1]).items() if occ}
        today = date.today()

        def mini_cell(d):
            selected, is_today = d == a, d == today
            return ft.Container(
                content=ft.Column([
                    ft.Text(str(d.day), size=11,
                            color=ft.Colors.BLACK if selected else (
                                ft.Colors.CYAN_ACCENT if is_today else (
                                    ft.Colors.WHITE if d.month == a.month else ft.Colors.GREY_700))),
                    ft.Container(width=4, height=4, border_radius=2,
                                 bgcolor=(ft.Colors.BLACK if selected else ft.Colors.AMBER_ACCENT) if d in busy else None),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                width=32, height=32, border_radius=16, alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.CYAN_ACCENT if selected else None,
                on_click=lambda e, day=d: self.set_view("day", day),
            )

        mini = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_size=18,
                              on_click=lambda e: self.set_view("day", (a.replace(day=1) - timedelta(days=1)).replace(day=1))),
                ft.Text(f"{MONTH_NAMES[a.month]} {a.year}", weight=ft.FontWeight.BOLD),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=18,
                              on_click=lambda e: self.set_view("day", (a.replace(day=28) + timedelta(days=4)).replace(day=1))),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Container(content=ft.Text(n[0], size=10, color=ft.Colors.GREY_500), width=32,
                                 alignment=ft.Alignment.CENTER) for n in DAY_NAMES], spacing=2),
            *[ft.Row([mini_cell(d) for d in week], spacing=2) for week in weeks],
        ], spacing=2)

        occs = db.get_events_for_date(a)
        done = db.get_completed_events(a.isoformat(), a.isoformat())
        n_done = sum(1 for o in occs if (o["id"], o["date"]) in done)
        day_reviews = self._reviews_by_day(a, a).get(a, [])
        summary = ft.Column([
            ft.Text("DAY SUMMARY", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
            ft.Text(f"{len(occs)} event(s) • {n_done} done • +{n_done * XP_EVENT} XP", size=13),
            *[self._review_row(r, compact=True) for r in day_reviews],
            *[self._agenda_row(o, (o["id"], o["date"]) in done, compact=True) for o in occs],
        ] if occs or day_reviews else [
            ft.Text("DAY SUMMARY", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
            ft.Text("Nothing scheduled. Click an hour to add an event.", size=12, color=ft.Colors.GREY_500),
        ], spacing=6)

        return ft.Container(
            content=ft.Column([mini, ft.Divider(color=ft.Colors.GREY_800), summary],
                              spacing=8, scroll=ft.ScrollMode.AUTO),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW, border_radius=10, padding=12,
        )

    # ------------------------------------------------------------ agenda
    def _agenda_view(self):
        search_field = ft.TextField(
            value=self.search, hint_text="Search events (title or notes)…", prefix_icon=ft.Icons.SEARCH,
            dense=True, width=360,
            on_submit=lambda e: self._set_search(e.control.value),
            suffix=ft.IconButton(ft.Icons.CLOSE, icon_size=16, tooltip="Clear",
                                 on_click=lambda e: self._set_search("")) if self.search else None,
        )

        if self.search:
            start, end = date.today() - timedelta(days=SEARCH_DAYS), date.today() + timedelta(days=SEARCH_DAYS)
        else:
            start, end = self.anchor, self.anchor + timedelta(days=AGENDA_DAYS - 1)
        by_day = db.get_events_between(start, end)
        done = db.get_completed_events(start.isoformat(), end.isoformat())
        reviews = self._reviews_by_day(start, end)
        needle = self.search.lower()
        today = date.today()

        items = []
        for d in sorted(by_day):
            occs = by_day[d]
            day_reviews = reviews.get(d, [])
            if needle:
                occs = [o for o in occs if needle in o["title"].lower() or needle in o["notes"].lower()]
                day_reviews = [r for r in day_reviews if needle in r["topic"].lower()]
            if not occs and not day_reviews:
                continue
            label = "Today" if d == today else "Tomorrow" if d == today + timedelta(days=1) else \
                "Yesterday" if d == today - timedelta(days=1) else fmt_date_short(d)
            items.append(ft.Container(
                content=ft.Row([
                    ft.Text(label, size=14, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.CYAN_ACCENT if d == today else ft.Colors.WHITE),
                    ft.Text(f"{d:%d/%m/%Y}", size=12, color=ft.Colors.GREY_500),
                ], spacing=10),
                padding=ft.Padding.only(top=12, bottom=4),
                on_click=lambda e, day=d: self.open_day(day),
            ))
            items.extend(self._review_row(r) for r in day_reviews)
            items.extend(self._agenda_row(o, (o["id"], o["date"]) in done) for o in occs)

        if not items:
            msg = f'No events match "{self.search}".' if self.search else \
                f"Nothing scheduled in the next {AGENDA_DAYS} days."
            items.append(ft.Container(content=ft.Text(msg, color=ft.Colors.GREY_500), padding=20))
        elif self.search and len(items) > 400:
            items = items[:400]

        return ft.Column([
            ft.Row([search_field,
                    ft.Text("Press Enter to search the past and next 12 months" if not self.search else "",
                            size=11, color=ft.Colors.GREY_500)], spacing=12),
            ft.ListView(items, expand=True, spacing=4),
        ], expand=True, spacing=8)

    def _set_search(self, text: str):
        self.search = (text or "").strip()
        self.render()

    def _agenda_row(self, occ, is_done: bool, compact: bool = False):
        color = color_of(occ)
        subtitle = " • ".join(x for x in (repeat_text(occ), occ["notes"].splitlines()[0] if occ["notes"] else "") if x)
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    icon_color=ft.Colors.GREEN_ACCENT if is_done else color,
                    icon_size=18 if compact else 22,
                    tooltip="Undo" if is_done else f"Mark as done (+{XP_EVENT} XP)",
                    on_click=lambda e, o=occ: self.toggle_done(o),
                ),
                ft.Container(width=4, height=36 if not compact else 28, bgcolor=color, border_radius=2),
                ft.Column([
                    ft.Text(occ["title"], size=13 if compact else 14, weight=ft.FontWeight.W_600,
                            color=ft.Colors.GREY_500 if is_done else ft.Colors.WHITE,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_done else None),
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(fmt_range(occ) + (f" • {subtitle}" if subtitle and not compact else ""),
                            size=11, color=ft.Colors.GREY_400, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True, tight=True),
            ], spacing=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=8,
            padding=ft.Padding.only(right=10, top=2, bottom=2),
            ink=True,
            on_click=lambda e, o=occ: self.open_details(o),
        )

    # ------------------------------------------------------------ actions
    def toggle_done(self, occ):
        db.toggle_event_completion(occ["id"], occ["date"])
        self._changed()

    def _close_dialog(self, e=None):
        try:
            self.app_page.pop_dialog()
        except Exception:
            pass

    def open_details(self, occ):
        is_done = db.is_event_completed(occ["id"], occ["date"])
        color = color_of(occ)
        d = date.fromisoformat(occ["date"])

        def row(icon, text, color_=ft.Colors.GREY_300):
            return ft.Row([ft.Icon(icon, size=18, color=ft.Colors.GREY_500),
                           ft.Text(text, size=13, color=color_, expand=True, selectable=True)], spacing=10)

        details = [
            row(ft.Icons.SCHEDULE, f"{fmt_date_long(d)} • {fmt_range(occ)}"),
        ]
        if occ["recurrence"] != "none":
            details.append(row(ft.Icons.REPEAT, repeat_text(occ)))
        details.append(row(ft.Icons.NOTIFICATIONS_OUTLINED, reminder_text(occ)))
        if occ["notes"]:
            details.append(row(ft.Icons.NOTES, occ["notes"], ft.Colors.WHITE))
        details.append(row(ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                           f"Done (+{XP_EVENT} XP earned)" if is_done else "Not done yet",
                           ft.Colors.GREEN_ACCENT if is_done else ft.Colors.GREY_400))

        def do_toggle(e):
            self._close_dialog()
            self.toggle_done(occ)

        def do_edit(e):
            self._close_dialog()
            self.open_editor(occ=occ)

        def do_delete(e):
            self._close_dialog()
            self.ask_delete(occ)

        self.app_page.show_dialog(ft.AlertDialog(
            title=ft.Row([ft.Container(width=14, height=14, border_radius=7, bgcolor=color),
                          ft.Text(occ["title"], weight=ft.FontWeight.BOLD, expand=True)], spacing=10),
            content=ft.Container(content=ft.Column(details, spacing=10, tight=True), width=460),
            actions=[
                ft.TextButton("Delete", icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300, on_click=do_delete),
                ft.TextButton("Edit", icon=ft.Icons.EDIT, on_click=do_edit),
                ft.Button("Undo done" if is_done else f"Mark done (+{XP_EVENT} XP)",
                          icon=ft.Icons.UNDO if is_done else ft.Icons.CHECK, on_click=do_toggle),
                ft.TextButton("Close", on_click=self._close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    def _ask_scope(self, title: str, message: str, on_choice, verb: str):
        """For repeating events: this occurrence / this and following / all."""
        def choose(scope):
            def handler(e):
                self._close_dialog()
                on_choice(scope)
            return handler

        self.app_page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_dialog),
                ft.TextButton(f"{verb} this event", on_click=choose("one")),
                ft.TextButton(f"{verb} this and following", on_click=choose("following")),
                ft.Button(f"{verb} all events", on_click=choose("all")),
            ],
        ))

    def ask_delete(self, occ):
        if occ["recurrence"] == "none":
            confirm_action(self.app_page, "Delete event?", f"'{occ['title']}' will be removed.",
                           lambda: (db.delete_calendar_event(occ["id"]), self._changed()))
            return

        def apply(scope):
            if scope == "one":
                db.skip_event_occurrence(occ["id"], occ["date"])
            elif scope == "following":
                db.end_event_series(occ["id"], occ["date"])
            else:
                db.delete_calendar_event(occ["id"])
            self._changed()

        self._ask_scope("Delete repeating event",
                        f"'{occ['title']}' repeats. What do you want to delete?", apply, "Delete")

    # ------------------------------------------------------------ editor
    def open_editor(self, occ=None, day: date = None, hour: int = None):
        """Create (occ=None) or edit an event. day/hour prefill a new event."""
        editing = occ is not None
        base_date = date.fromisoformat(occ["date"]) if editing else (day or (
            self.anchor if self.view in ("day", "month", "week") else date.today()))
        if editing:
            start_min = occ["start_hour"] * 60 + occ["start_minute"]
        elif hour is not None:
            start_min = hour * 60
        else:
            now = datetime.now()
            start_min = min(23 * 60, (now.hour + 1) * 60) if base_date == date.today() else 9 * 60

        state = {
            "color": occ["color"] if editing else "Cyan",
        }

        title_f = ft.TextField(label="Title", value=occ["title"] if editing else "", autofocus=True, dense=True)
        date_f = ft.TextField(label="Date (DD/MM/YYYY)", value=f"{base_date:%d/%m/%Y}", dense=True, expand=True)
        all_day_cb = ft.Checkbox(label="All day", value=occ["all_day"] if editing else False)
        time_dd = ft.Dropdown(
            label="Start", dense=True, width=120, menu_height=320,
            value=str(start_min),
            options=[ft.DropdownOption(key=str(m), text=fmt_time(m // 60, m % 60)) for m in time_slots(start_min)],
        )
        dur_value = occ["duration_min"] if editing else 60
        dur_opts = list(DURATION_OPTIONS)
        if dur_value not in dict(dur_opts):
            dur_opts.append((dur_value, f"{dur_value} min"))
            dur_opts.sort()
        dur_dd = ft.Dropdown(label="Duration", dense=True, width=150, value=str(dur_value),
                             options=[ft.DropdownOption(key=str(v), text=t) for v, t in dur_opts])
        rep_dd = ft.Dropdown(label="Repeat", dense=True, expand=True,
                             value=occ["recurrence"] if editing else "none")
        until_f = ft.TextField(label="Until (optional)", dense=True, width=170,
                               value=(f"{date.fromisoformat(occ['recurrence_end']):%d/%m/%Y}"
                                      if editing and occ["recurrence_end"] else ""))
        rem_dd = ft.Dropdown(label="Reminder", dense=True, expand=True)
        notes_f = ft.TextField(label="Notes", value=occ["notes"] if editing else "", multiline=True,
                               min_lines=2, max_lines=5, dense=True)
        conflict_txt = ft.Text("", size=12, color=ft.Colors.AMBER_ACCENT)
        error_txt = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)
        color_row = ft.Row(spacing=6, wrap=True)

        def parsed_date():
            return db.parse_flexible_date(date_f.value or "")

        def refresh_dependent(e=None):
            d = parsed_date() or base_date
            # rebuild option lists only when their labels change (rebuilding resets the selection)
            if state.get("repeat_for") != d:
                state["repeat_for"] = d
                rep_dd.options = [ft.DropdownOption(key=k, text=t) for k, t in repeat_options(d)]
            until_f.visible = rep_dd.value != "none"
            time_dd.disabled = dur_dd.disabled = bool(all_day_cb.value)
            if state.get("reminders_for") != bool(all_day_cb.value):
                state["reminders_for"] = bool(all_day_cb.value)
                opts = ALL_DAY_REMINDER_OPTIONS if all_day_cb.value else REMINDER_OPTIONS
                current = int(rem_dd.value) if rem_dd.value not in (None, "") else (
                    occ["reminder_min"] if editing else 15)
                if current not in dict(opts):
                    current = opts[1][0]
                rem_dd.options = [ft.DropdownOption(key=str(v), text=t) for v, t in opts]
                rem_dd.value = str(current)
            # conflicts with other timed events that day
            conflict_txt.value = ""
            if not all_day_cb.value and parsed_date():
                s = int(time_dd.value)
                en = s + int(dur_dd.value)
                clashes = [o["title"] for o in db.get_events_for_date(d)
                           if not o["all_day"] and not (editing and o["id"] == occ["id"])
                           and o["start_hour"] * 60 + o["start_minute"] < en
                           and s < o["start_hour"] * 60 + o["start_minute"] + o["duration_min"]]
                if clashes:
                    conflict_txt.value = "⚠ Overlaps with: " + ", ".join(clashes[:3]) + ("…" if len(clashes) > 3 else "")
            render_colors()
            if e is not None:
                self.app_page.update()

        def render_colors():
            color_row.controls = [
                ft.Container(
                    width=26, height=26, border_radius=13, bgcolor=c,
                    border=ft.Border.all(3, ft.Colors.WHITE) if state["color"] == name else None,
                    tooltip=name,
                    on_click=lambda e, n=name: (state.update(color=n), refresh_dependent(e)),
                ) for name, c in EVENT_COLORS.items()
            ]

        for ctl in (all_day_cb,):
            ctl.on_change = refresh_dependent
        for ctl in (time_dd, dur_dd, rep_dd):
            ctl.on_select = refresh_dependent
        date_f.on_blur = refresh_dependent
        refresh_dependent()

        def pick_date(e):
            def picked(ev):
                if ev.control.value:
                    v = ev.control.value
                    date_f.value = f"{v.day:02d}/{v.month:02d}/{v.year}"
                    refresh_dependent(ev)
            self.app_page.show_dialog(ft.DatePicker(
                value=datetime.combine(parsed_date() or base_date, datetime.min.time()),
                first_date=datetime(2000, 1, 1), last_date=datetime(2100, 12, 31),
                on_change=picked,
            ))

        def collect():
            title = (title_f.value or "").strip()
            d = parsed_date()
            if not title:
                return None, "Give the event a title."
            if not d:
                return None, "Invalid date. Use DD/MM/YYYY."
            until = ""
            if rep_dd.value != "none" and (until_f.value or "").strip():
                u = db.parse_flexible_date(until_f.value)
                if not u:
                    return None, "Invalid 'Until' date. Use DD/MM/YYYY."
                if u < d:
                    return None, "'Until' must be on or after the event date."
                until = u.isoformat()
            start = int(time_dd.value)
            return {
                "title": title,
                "event_date": d.isoformat(),
                "start_hour": 0 if all_day_cb.value else start // 60,
                "start_minute": 0 if all_day_cb.value else start % 60,
                "duration_min": int(dur_dd.value),
                "all_day": bool(all_day_cb.value),
                "recurrence": rep_dd.value or "none",
                "recurrence_end": "" if rep_dd.value == "none" else until,
                "color": state["color"],
                "notes": (notes_f.value or "").strip(),
                "reminder_min": int(rem_dd.value),
            }, None

        def save(e):
            fields, err = collect()
            if err:
                error_txt.value = err
                self.app_page.update()
                return
            self._close_dialog()
            if not editing:
                event_date = fields.pop("event_date")
                db.add_calendar_event(fields.pop("title"), event_date, **fields)
                self.anchor = date.fromisoformat(event_date)  # show where it landed
                self._changed()
                return
            if occ["recurrence"] == "none":
                db.update_calendar_event(occ["id"], **fields)
                self._changed()
                return

            def apply(scope):
                if scope == "one":
                    db.edit_event_occurrence(occ["id"], occ["date"], **fields)
                elif scope == "following":
                    db.edit_event_following(occ["id"], occ["date"], **fields)
                else:
                    series = dict(fields)
                    # keep the series start unless the date itself was changed
                    if series["event_date"] == occ["date"]:
                        series["event_date"] = occ["event_date"]
                    db.update_calendar_event(occ["id"], **series)
                self._changed()

            self._ask_scope("Edit repeating event", f"'{occ['title']}' repeats. Apply the changes to:",
                            apply, "Save")

        title_f.on_submit = save

        actions = [ft.TextButton("Cancel", on_click=self._close_dialog),
                   ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)]
        if editing:
            def delete(e):
                self._close_dialog()
                self.ask_delete(occ)
            actions.insert(0, ft.TextButton("Delete", icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=ft.Colors.RED_300, on_click=delete))

        self.app_page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit event" if editing else "New event", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=520,
                content=ft.Column([
                    title_f,
                    ft.Row([date_f, ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip="Pick a date", on_click=pick_date),
                            all_day_cb], spacing=6),
                    ft.Row([time_dd, dur_dd], spacing=10),
                    ft.Row([rep_dd, until_f], spacing=10),
                    rem_dd,
                    ft.Text("Color", size=12, color=ft.Colors.GREY_400),
                    color_row,
                    notes_f,
                    conflict_txt,
                    error_txt,
                ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            ),
            actions=actions,
        ))
