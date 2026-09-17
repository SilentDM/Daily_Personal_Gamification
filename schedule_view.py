import flet as ft
import database as db
from constants import (
    POSITIVE_SCORES, 
    NEGATIVE_SCORES, 
    CATEGORIES, 
    DAY_NAMES, 
    get_rank_title
)

CATEGORY_COLORS = {
    "Health": ft.Colors.GREEN_400,
    "Study": ft.Colors.BLUE_400,
    "Routine": ft.Colors.PURPLE_300,
    "Vice / Avoid": ft.Colors.RED_400,
}

class ScheduleView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True)
        self.app_page = page
        self.daily_score_texts = {}
        self.year, self.week, self.today_idx = db.get_current_week_info()

        # Gamification banner elements
        self.streak_text = ft.Text("🔥 0 Days Streak", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_ACCENT)
        self.level_text = ft.Text("Level 1 • Novice", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT)
        self.xp_bar = ft.ProgressBar(value=0.0, width=180, color=ft.Colors.CYAN_ACCENT, bgcolor=ft.Colors.GREY_800)
        self.xp_fraction_text = ft.Text("0 / 100 XP", size=12, color=ft.Colors.GREY_400)

        self.render()
        self.calculate_daily_scores()

    def update_gamification_stats(self):
        """Updates the Streak, Level, and XP bar."""
        streak = db.get_current_streak()
        total_xp, level, xp_in_level = db.get_user_xp_and_level()
        rank_title = get_rank_title(level)

        self.streak_text.value = f"🔥 {streak} Day{'s' if streak != 1 else ''} Streak"
        self.level_text.value = f"Level {level} • {rank_title}"
        self.xp_bar.value = xp_in_level / 100.0
        self.xp_fraction_text.value = f"{xp_in_level} / 100 XP (Total: {total_xp})"

    def calculate_daily_scores(self):
        logs = db.get_current_week_logs(self.year, self.week)
        active_ids = {a[0] for a in db.get_activities()}
        
        for d in range(7):
            day_scores = [
                score for (act_id, day), (status, score) in logs.items() 
                if day == d and score is not None and act_id in active_ids
            ]
            if day_scores:
                avg = sum(day_scores) / len(day_scores)
                self.daily_score_texts[d].value = f"{avg:.1f} / 10"
                if avg >= 8.0:
                    self.daily_score_texts[d].color = ft.Colors.GREEN_ACCENT
                elif avg >= 5.0:
                    daily_score = ft.Colors.ORANGE_ACCENT
                    self.daily_score_texts[d].color = daily_score
                else:
                    self.daily_score_texts[d].color = ft.Colors.RED_ACCENT
            else:
                self.daily_score_texts[d].value = "- / 10"
                self.daily_score_texts[d].color = ft.Colors.GREY_500
                
        self.update_gamification_stats()
        if self.app_page:
            self.app_page.update()

    def on_status_change(self, e, activity_id, day_idx, is_negative):
        selected_status = e.control.value
        score_map = NEGATIVE_SCORES if is_negative else POSITIVE_SCORES
        score = score_map.get(selected_status)
        db.save_log(activity_id, self.year, self.week, day_idx, selected_status, score)
        self.calculate_daily_scores()

    def on_delete_activity(self, activity_id):
        db.delete_activity(activity_id)
        self.render()
        self.calculate_daily_scores()

    def quick_fill_today(self, e):
        """Fills all unselected activities for today with a passing mark."""
        logs = db.get_current_week_logs(self.year, self.week)
        activities = db.get_activities()

        for act_id, _, _, is_neg in activities:
            current_status = logs.get((act_id, self.today_idx), ("-", None))[0]
            if current_status in ("-", None):
                default_status = "Resisted" if is_neg else "Ok"
                score = 10 if is_neg else 7
                db.save_log(act_id, self.year, self.week, self.today_idx, default_status, score)

        self.render()
        self.calculate_daily_scores()

    def export_csv_clicked(self, e):
        path = db.export_to_csv()
        e.control.content = "Exported to Desktop!"
        e.control.icon = ft.Icons.CHECK
        self.app_page.update()

    def render(self):
        self.controls.clear()
        logs = db.get_current_week_logs(self.year, self.week)
        activities = db.get_activities()

        # 1. Top Gamification Banner
        gamification_banner = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, color=ft.Colors.ORANGE_ACCENT, size=28),
                    self.streak_text
                ]),
                ft.VerticalDivider(width=30),
                ft.Column([
                    self.level_text,
                    ft.Row([self.xp_bar, self.xp_fraction_text])
                ], spacing=3),
                ft.Row([
                    # Modern ft.Button
                    ft.Button(
                        content="Quick-Fill Today",
                        icon=ft.Icons.BOLT,
                        icon_color=ft.Colors.AMBER_ACCENT,
                        on_click=self.quick_fill_today
                    ),
                    ft.Button(
                        content="Export CSV",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=self.export_csv_clicked
                    )
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=15,
            margin=ft.Margin.symmetric(horizontal=15, vertical=10)
        )
        self.controls.append(gamification_banner)

        # Title Row
        self.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(f"Week {self.week} ({self.year})", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(f"• Today is {DAY_NAMES[self.today_idx]}", size=15, color=ft.Colors.CYAN_ACCENT)
                ]),
                padding=ft.Padding.only(left=20, top=5, bottom=5)
            )
        )

        # Header Row
        header_cells = [
            ft.Container(
                content=ft.Text("Activity & Category", weight=ft.FontWeight.BOLD, size=14),
                width=250,
                padding=10
            )
        ]

        for i, day in enumerate(DAY_NAMES):
            is_today = (i == self.today_idx)
            header_cells.append(
                ft.Container(
                    content=ft.Text(
                        day + (" (Today)" if is_today else ""), 
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.CYAN_ACCENT if is_today else ft.Colors.WHITE
                    ),
                    width=115,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.BLUE_GREY_900 if is_today else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    padding=5
                )
            )

        header_cells.append(ft.Container(width=50))

        self.controls.append(
            ft.Container(
                content=ft.Row(header_cells),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=8,
                padding=5,
                margin=ft.Margin.symmetric(horizontal=15)
            )
        )

        # Activity Rows
        for act_id, act_name, category, is_negative in activities:
            cat_color = CATEGORY_COLORS.get(category, ft.Colors.GREY_400)
            
            badge = ft.Container(
                content=ft.Text(category, size=10, color=cat_color, weight=ft.FontWeight.BOLD),
                border=ft.Border.all(1, cat_color),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=4, vertical=1)
            )

            title_col = ft.Container(
                content=ft.Row([
                    ft.Text(act_name, size=13, weight=ft.FontWeight.W_500, expand=True),
                    badge
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                width=250,
                padding=ft.Padding.only(left=10, right=5)
            )

            row_cells = [title_col]

            if is_negative:
                options = [
                    ft.DropdownOption(key="Resisted", text="Resisted (+10)"),
                    ft.DropdownOption(key="Slipped", text="Slipped (+4)"),
                    ft.DropdownOption(key="Relapsed", text="Relapsed (0)"),
                    ft.DropdownOption(key="-", text="-")
                ]
            else:
                options = [
                    ft.DropdownOption(key="Excellent", text="Excellent"),
                    ft.DropdownOption(key="Ok", text="Ok"),
                    ft.DropdownOption(key="A Little", text="A Little"),
                    ft.DropdownOption(key="Skipped", text="Skipped"),
                    ft.DropdownOption(key="-", text="-")
                ]

            for d in range(7):
                is_today = (d == self.today_idx)
                current_val = logs.get((act_id, d), ("-", None))[0]

                dropdown = ft.Dropdown(
                    value=current_val,
                    width=110,
                    text_size=11,
                    content_padding=5,
                    options=options,
                    on_select=lambda e, a=act_id, day=d, neg=is_negative: self.on_status_change(e, a, day, neg)
                )

                row_cells.append(
                    ft.Container(
                        content=dropdown,
                        width=115,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.CYAN) if is_today else None,
                        border_radius=6,
                        padding=2
                    )
                )

            row_cells.append(
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        icon_size=20,
                        tooltip="Delete activity",
                        on_click=lambda e, a=act_id: self.on_delete_activity(a)
                    ),
                    width=50,
                    alignment=ft.Alignment.CENTER
                )
            )

            self.controls.append(
                ft.Container(
                    content=ft.Row(row_cells),
                    padding=ft.Padding.symmetric(horizontal=15, vertical=3)
                )
            )

        # 3. Add Activity Row
        new_activity_input = ft.TextField(
            hint_text="New activity name...",
            width=200,
            dense=True,
            text_size=13
        )

        cat_dropdown = ft.Dropdown(
            value="Routine",
            width=130,
            dense=True,
            text_size=12,
            content_padding=5,
            options=[ft.DropdownOption(cat) for cat in CATEGORIES]
        )

        bad_habit_checkbox = ft.Checkbox(label="Vice / Bad Habit", value=False)

        def on_cat_change(e):
            if cat_dropdown.value == "Vice / Avoid":
                bad_habit_checkbox.value = True
            else:
                bad_habit_checkbox.value = False
            self.app_page.update()

        cat_dropdown.on_select = on_cat_change

        def add_clicked(e):
            if new_activity_input.value and new_activity_input.value.strip():
                db.add_activity(
                    name=new_activity_input.value.strip(),
                    category=cat_dropdown.value,
                    is_negative=bad_habit_checkbox.value
                )
                new_activity_input.value = ""
                self.render()
                self.calculate_daily_scores()

        self.controls.append(
            ft.Container(
                content=ft.Row([
                    new_activity_input,
                    cat_dropdown,
                    bad_habit_checkbox,
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE,
                        icon_color=ft.Colors.CYAN_ACCENT,
                        icon_size=28,
                        tooltip="Add Activity",
                        on_click=add_clicked
                    )
                ]),
                padding=ft.Padding.only(left=15, top=10)
            )
        )

        # 4. Daily Score Footer Row
        footer_cells = [
            ft.Container(
                content=ft.Text("Daily Score (0-10)", weight=ft.FontWeight.BOLD, size=14),
                width=250,
                padding=10
            )
        ]

        for d in range(7):
            is_today = (d == self.today_idx)
            text_ctl = ft.Text("- / 10", weight=ft.FontWeight.BOLD, size=13)
            self.daily_score_texts[d] = text_ctl

            footer_cells.append(
                ft.Container(
                    content=text_ctl,
                    width=115,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.CYAN) if is_today else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=8,
                    padding=8
                )
            )

        footer_cells.append(ft.Container(width=50))

        self.controls.append(
            ft.Container(
                content=ft.Row(footer_cells),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                border_radius=8,
                padding=5,
                margin=ft.Margin.only(left=15, right=15, top=20, bottom=30)
            )
        )