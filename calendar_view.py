import flet as ft
import calendar
from datetime import datetime, date
import database as db
from wallpaper import update_desktop_wallpaper

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
DAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

class CalendarView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False)
        self.app_page = page
        
        # State
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month
        self.selected_date = today
        self.mode = "month"  # "month" or "day"
        self.scheduling_hour = None  # None or int (0-23)

        self.render()

    def prev_month(self, e):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self.render()

    def next_month(self, e):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self.render()

    def go_to_today(self, e):
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month
        self.mode = "month"
        self.render()

    def open_day(self, target_date: date):
        self.selected_date = target_date
        self.scheduling_hour = None
        self.mode = "day"
        self.render()

    def back_to_month(self, e):
        self.scheduling_hour = None
        self.mode = "month"
        self.render()

    def select_hour_to_schedule(self, hour: int):
        self.scheduling_hour = hour
        self.render()

    def cancel_scheduling(self, e):
        self.scheduling_hour = None
        self.render()

    def save_scheduled_event(self, title: str, rec_val: str):
        if title and title.strip() and self.scheduling_hour is not None:
            db.add_calendar_event(
                title=title.strip(),
                event_date_str=self.selected_date.strftime("%Y-%m-%d"),
                start_hour=self.scheduling_hour,
                recurrence=rec_val
            )
            self.scheduling_hour = None
            self.render()
            update_desktop_wallpaper()

    def delete_event_clicked(self, event_id: int):
        db.delete_calendar_event(event_id)
        self.render()
        update_desktop_wallpaper()

    def toggle_done(self, event_id: int, date_str: str):
        db.toggle_event_completion(event_id, date_str)
        self.render()
        update_desktop_wallpaper()

    def render(self):
        self.controls.clear()
        if self.mode == "month":
            self.render_month_view()
        else:
            self.render_day_view()

        if self.app_page:
            self.app_page.update()

    def render_month_view(self):
        # 1. Navigation Header: < | Month Year | >
        nav_header = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_size=32, icon_color=ft.Colors.CYAN_ACCENT, on_click=self.prev_month),
                    ft.Text(f"{MONTH_NAMES[self.view_month]} {self.view_year}", size=24, weight=ft.FontWeight.BOLD),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=32, icon_color=ft.Colors.CYAN_ACCENT, on_click=self.next_month),
                ], spacing=10),
                ft.Button(content="Today", icon=ft.Icons.CALENDAR_TODAY, on_click=self.go_to_today)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding.only(left=20, right=20, top=15, bottom=10)
        )
        self.controls.append(nav_header)

        # 2. Day-of-Week Column Headers (Mon to Sun)
        header_row = ft.Row([
            ft.Container(
                content=ft.Text(day, weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.GREY_400),
                width=140,
                alignment=ft.Alignment.CENTER,
                padding=8
            ) for day in DAY_HEADERS
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER)

        self.controls.append(ft.Container(content=header_row, margin=ft.Margin.symmetric(horizontal=20)))

        # 3. Monthly Calendar Grid
        month_matrix = calendar.monthcalendar(self.view_year, self.view_month)
        today = date.today()

        grid_column = ft.Column(spacing=8, alignment=ft.MainAxisAlignment.CENTER)

        for week in month_matrix:
            week_row = ft.Row(spacing=8, alignment=ft.MainAxisAlignment.CENTER)
            for day_num in week:
                if day_num == 0:
                    week_row.controls.append(ft.Container(width=140, height=95))
                else:
                    cell_date = date(self.view_year, self.view_month, day_num)
                    is_today = (cell_date == today)
                    events = db.get_events_for_date(cell_date)

                    event_chips = []
                    for ev in events[:2]:
                        event_chips.append(
                            ft.Container(
                                content=ft.Text(f"{ev[3]:02d}:00 {ev[1]}", size=10, no_wrap=True),
                                bgcolor=ft.Colors.BLUE_GREY_900,
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=4, vertical=1)
                            )
                        )
                    if len(events) > 2:
                        event_chips.append(ft.Text(f"+{len(events)-2} more", size=9, color=ft.Colors.CYAN_ACCENT))

                    cell = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(str(day_num), size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT if is_today else ft.Colors.WHITE),
                                ft.Container(
                                    width=8, height=8, border_radius=4, bgcolor=ft.Colors.AMBER_ACCENT
                                ) if events else ft.Container()
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Column(event_chips, spacing=2)
                        ], spacing=3),
                        width=140,
                        height=95,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        border=ft.Border.all(2, ft.Colors.CYAN_ACCENT) if is_today else ft.Border.all(1, ft.Colors.GREY_800),
                        border_radius=8,
                        padding=8,
                        on_click=lambda e, d=cell_date: self.open_day(d)
                    )
                    week_row.controls.append(cell)

            grid_column.controls.append(week_row)

        self.controls.append(ft.Container(content=grid_column, margin=ft.Margin.symmetric(horizontal=20, vertical=5)))

    def render_day_view(self):
        # 1. Header with Back Button
        header = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=28, tooltip="Back to Month", on_click=self.back_to_month),
                    ft.Column([
                        ft.Text(self.selected_date.strftime("%A, %d %B %Y"), size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Click any hour block to schedule an event", size=13, color=ft.Colors.GREY_400)
                    ], spacing=2)
                ], spacing=10),
                ft.Button(content="Back to Calendar", icon=ft.Icons.CALENDAR_MONTH, on_click=self.back_to_month)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding.only(left=20, right=20, top=15, bottom=10)
        )
        self.controls.append(header)

        # 2. INLINE SCHEDULER CARD (Appears when an hour is clicked)
        if self.scheduling_hour is not None:
            title_input = ft.TextField(
                hint_text="e.g. Tronos de Cinzas, FIAP Exam, Dentist...",
                expand=True,
                dense=True,
                autofocus=True,
                text_size=13
            )
            rec_dropdown = ft.Dropdown(
                value="One-Time",
                width=170,
                dense=True,
                text_size=12,
                content_padding=5,
                options=[
                    ft.DropdownOption("One-Time"),
                    ft.DropdownOption("Weekly"),
                    ft.DropdownOption("Monthly")
                ]
            )

            def on_save(e):
                rec = "none"
                if rec_dropdown.value == "Weekly":
                    rec = "weekly"
                elif rec_dropdown.value == "Monthly":
                    rec = "monthly"
                self.save_scheduled_event(title_input.value, rec)

            scheduler_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ADD_ALARM, color=ft.Colors.CYAN_ACCENT, size=20),
                        ft.Text(
                            f"Scheduling for {self.scheduling_hour:02d}:00 ({self.selected_date.strftime('%d/%m/%Y')})",
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            color=ft.Colors.CYAN_ACCENT
                        )
                    ], spacing=8),
                    ft.Row([
                        title_input,
                        rec_dropdown,
                        ft.Button(content="Save Event", icon=ft.Icons.CHECK, on_click=on_save),
                        ft.IconButton(ft.Icons.CLOSE, icon_color=ft.Colors.GREY_400, tooltip="Cancel", on_click=self.cancel_scheduling)
                    ], spacing=10)
                ], spacing=8),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border=ft.Border.all(1, ft.Colors.CYAN_ACCENT),
                border_radius=10,
                padding=15,
                margin=ft.Margin.only(left=20, right=30, bottom=15)
            )
            self.controls.append(scheduler_card)

        # 3. 24-Hour Timeline List
        events = db.get_events_for_date(self.selected_date)
        events_by_hour = {}
        for ev in events:
            events_by_hour.setdefault(ev[3], []).append(ev)

        hours_column = ft.Column(spacing=4)
        date_str = self.selected_date.strftime("%Y-%m-%d")

        for h in range(24):
            is_active_selection = (h == self.scheduling_hour)

            hour_label = ft.Container(
                content=ft.Text(
                    f"{h:02d}:00", 
                    size=13, 
                    weight=ft.FontWeight.BOLD, 
                    color=ft.Colors.CYAN_ACCENT if is_active_selection else ft.Colors.GREY_300
                ),
                width=80,
                alignment=ft.Alignment.CENTER_RIGHT,
                padding=ft.Padding.only(right=15)
            )

            hour_events = events_by_hour.get(h, [])
            
            if hour_events:
                event_items = []
                for ev in hour_events:
                    eid, title, _, _, rec = ev
                    rec_badge = f" • [{rec.capitalize()}]" if rec != "none" else ""
                    is_done = db.is_event_completed(eid, date_str)

                    def make_toggle(event_id=eid, d_str=date_str):
                        return lambda e: self.toggle_done(event_id, d_str)

                    event_items.append(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                icon_color=ft.Colors.GREEN_ACCENT if is_done else ft.Colors.AMBER_ACCENT,
                                tooltip="Mark as Done (+10 XP)" if not is_done else "Completed!",
                                on_click=make_toggle()
                            ),
                            ft.Text(
                                f"{title}{rec_badge}", 
                                size=13, 
                                weight=ft.FontWeight.W_500, 
                                color=ft.Colors.GREY_400 if is_done else ft.Colors.WHITE,
                                style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_done else ft.TextDecoration.NONE),
                                expand=True
                            ),
                            ft.Container(
                                content=ft.Text("+10 XP", size=10, color=ft.Colors.GREEN_ACCENT, weight=ft.FontWeight.BOLD),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                            ) if is_done else ft.Container(),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                icon_color=ft.Colors.RED_400,
                                tooltip="Delete Event",
                                on_click=lambda e, i=eid: self.delete_event_clicked(i)
                            )
                        ], spacing=8)
                    )

                slot_content = ft.Container(
                    content=ft.Column(event_items, spacing=4),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border=ft.Border.all(1, ft.Colors.AMBER_400) if is_active_selection else None,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    expand=True,
                    on_click=lambda e, hour=h: self.select_hour_to_schedule(hour)
                )
            else:
                slot_content = ft.Container(
                    content=ft.Text(
                        f"Selected for {h:02d}:00 (use panel above to save)" if is_active_selection else f"+ Add event at {h:02d}:00",
                        size=12,
                        color=ft.Colors.CYAN_ACCENT if is_active_selection else ft.Colors.GREY_600
                    ),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.CYAN) if is_active_selection else ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                    border=ft.Border.all(1, ft.Colors.CYAN_ACCENT if is_active_selection else ft.Colors.with_opacity(0.08, ft.Colors.GREY)),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    expand=True,
                    on_click=lambda e, hour=h: self.select_hour_to_schedule(hour)
                )

            row = ft.Row([hour_label, slot_content], spacing=10)
            hours_column.controls.append(row)

        self.controls.append(
            ft.Container(
                content=hours_column,
                padding=ft.Padding.only(left=20, right=30, bottom=40)
            )
        )