import flet as ft
import flet_charts as fch
import database as db
from constants import DAY_NAMES

CATEGORY_COLORS = {
    "Health": ft.Colors.GREEN_400,
    "Study": ft.Colors.BLUE_400,
    "Routine": ft.Colors.PURPLE_300,
    "Vice / Avoid": ft.Colors.RED_400,
}

class GraphsView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False)
        self.app_page = page
        self.year, self.week, _ = db.get_current_week_info()

    def build_kpi_card(self, title: str, value: str, subtext: str, icon: str, icon_color: str):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=icon_color, size=20),
                    ft.Text(title, size=12, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500)
                ], spacing=8),
                ft.Text(value, size=22, weight=ft.FontWeight.BOLD),
                ft.Text(subtext, size=11, color=ft.Colors.GREY_500)
            ], spacing=4),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=15,
            expand=True
        )

    def refresh(self):
        """Re-reads database logs and builds the full analytics dashboard."""
        self.controls.clear()
        logs = db.get_current_week_logs(self.year, self.week)
        active_ids = {a[0] for a in db.get_activities()}
        insights = db.get_weekly_insights(self.year, self.week)

        # 1. Header Title
        self.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text("📊 Performance & Analytics Dashboard", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Week {self.week} Overview", size=14, color=ft.Colors.CYAN_ACCENT)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.Padding.only(left=20, right=20, top=20, bottom=5)
            )
        )

        # 2. Daily Scores for Chart 1
        day_averages = []
        recorded_days = []
        for d in range(7):
            scores = [
                score for (act_id, day), (_, score) in logs.items() 
                if day == d and score is not None and act_id in active_ids
            ]
            avg = (sum(scores) / len(scores)) if scores else 0.0
            day_averages.append(avg)
            if scores:
                recorded_days.append((DAY_NAMES[d], avg))

        week_avg = (sum([sc for _, sc in recorded_days]) / len(recorded_days)) if recorded_days else 0.0
        best_day = max(recorded_days, key=lambda x: x[1]) if recorded_days else ("-", 0.0)

        # 3. KPI Cards Row
        passing_status = "🎯 Passing Goal (≥7.0)" if week_avg >= 7.0 else "⚠️ Below Goal (<7.0)"
        vice_text = f"{insights['vice_rate']:.0f}% Resisted" if insights['vice_rate'] is not None else "No Vices Logged"

        kpi_row = ft.Row([
            self.build_kpi_card("Week Average", f"{week_avg:.1f} / 10", passing_status, ft.Icons.SPEED, ft.Colors.CYAN_ACCENT),
            self.build_kpi_card("Completion Rate", f"{insights['completion_rate']:.0f}%", "Completed tasks vs skips", ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN_ACCENT),
            self.build_kpi_card("Vice Control", vice_text, "Bad habits successfully avoided", ft.Icons.SHIELD, ft.Colors.AMBER_ACCENT),
            self.build_kpi_card("Best Day", f"{best_day[0]} ({best_day[1]:.1f})", "Peak performance day", ft.Icons.STAR, ft.Colors.PURPLE_300),
        ], spacing=12)

        self.controls.append(ft.Container(content=kpi_row, padding=ft.Padding.symmetric(horizontal=20, vertical=10)))

        # 4. Chart 1: Daily Breakdown (Mon-Sun)
        current_week_rods = []
        for d in range(7):
            avg = day_averages[d]
            color = ft.Colors.GREEN_ACCENT if avg >= 7.5 else (ft.Colors.ORANGE_ACCENT if avg >= 4.5 else ft.Colors.RED_ACCENT)
            current_week_rods.append(
                fch.BarChartGroup(
                    x=d,
                    rods=[fch.BarChartRod(from_y=0, to_y=avg, width=28, color=color, border_radius=ft.BorderRadius.all(4))]
                )
            )

        daily_chart = fch.BarChart(
            groups=current_week_rods,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            left_axis=fch.ChartAxis(
                labels=[fch.ChartAxisLabel(value=i, label=ft.Text(str(i))) for i in range(0, 11, 2)],
                label_size=30
            ),
            bottom_axis=fch.ChartAxis(
                labels=[fch.ChartAxisLabel(value=i, label=ft.Text(day)) for i, day in enumerate(DAY_NAMES)],
                label_size=30
            ),
            horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.GREY_800, interval=2),
            min_y=0,
            max_y=10,
            interactive=True,
            expand=True
        )

        daily_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Daily Scores (Current Week)", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text("Scale 0 to 10 • Passing threshold: 7.0", size=12, color=ft.Colors.GREY_400)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(content=daily_chart, height=220, padding=10)
            ]),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=15,
            margin=ft.Margin.symmetric(horizontal=20, vertical=5)
        )
        self.controls.append(daily_section)

        # 5. Chart 2: Week-over-Week Evolution (Last 6 Weeks)
        past_weeks = db.get_past_weeks_scores(num_weeks=6)
        if past_weeks:
            past_rods = []
            past_labels = []
            for idx, (yr, wk, avg) in enumerate(past_weeks):
                color = ft.Colors.CYAN_ACCENT if (yr == self.year and wk == self.week) else ft.Colors.BLUE_GREY_400
                past_rods.append(
                    fch.BarChartGroup(
                        x=idx,
                        rods=[fch.BarChartRod(from_y=0, to_y=avg, width=28, color=color, border_radius=ft.BorderRadius.all(4))]
                    )
                )
                past_labels.append(fch.ChartAxisLabel(value=idx, label=ft.Text(f"W{wk}")))

            past_chart = fch.BarChart(
                groups=past_rods,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                left_axis=fch.ChartAxis(
                    labels=[fch.ChartAxisLabel(value=i, label=ft.Text(str(i))) for i in range(0, 11, 2)],
                    label_size=30
                ),
                bottom_axis=fch.ChartAxis(labels=past_labels, label_size=30),
                horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.GREY_800, interval=2),
                min_y=0,
                max_y=10,
                interactive=True,
                expand=True
            )

            multi_week_section = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Multi-Week Progression", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Weekly averages over time (Cyan = Active Week)", size=12, color=ft.Colors.GREY_400)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(content=past_chart, height=200, padding=10)
                ]),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=10,
                padding=15,
                margin=ft.Margin.symmetric(horizontal=20, vertical=5)
            )
            self.controls.append(multi_week_section)

        # 6. Section 3: Category Breakdown & Habit Insights
        cat_bars = []
        for cat, pct in insights["category_scores"].items():
            bar_color = CATEGORY_COLORS.get(cat, ft.Colors.CYAN_ACCENT)
            cat_bars.append(
                ft.Column([
                    ft.Row([
                        ft.Text(cat, size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"{pct:.0f}%", size=13, weight=ft.FontWeight.BOLD, color=bar_color)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(value=pct / 100.0, color=bar_color, bgcolor=ft.Colors.GREY_800, height=8)
                ], spacing=4)
            )

        if not cat_bars:
            cat_bars.append(ft.Text("Log tasks to view category breakdown.", color=ft.Colors.GREY_500, size=13))

        category_card = ft.Container(
            content=ft.Column([
                ft.Text("Category Mastery", size=15, weight=ft.FontWeight.BOLD),
                ft.Column(cat_bars, spacing=12)
            ]),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=15,
            expand=True
        )

        # Hero vs Nemesis Card
        strongest_txt = f"{insights['strongest_habit'][0]} ({insights['strongest_habit'][1]:.1f}/10)" if insights['strongest_habit'] else "None yet"
        nemesis_txt = f"{insights['nemesis_habit'][0]} ({insights['nemesis_habit'][1]:.1f}/10)" if insights['nemesis_habit'] else "None yet"

        insights_card = ft.Container(
            content=ft.Column([
                ft.Text("Habit Highlights", size=15, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Icon(ft.Icons.EMOJI_EVENTS, color=ft.Colors.AMBER_ACCENT, size=24),
                    ft.Column([
                        ft.Text("Strongest Habit", size=11, color=ft.Colors.GREY_400),
                        ft.Text(strongest_txt, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_ACCENT)
                    ], spacing=2)
                ], spacing=10),
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_ACCENT, size=24),
                    ft.Column([
                        ft.Text("Nemesis Habit (Needs Focus)", size=11, color=ft.Colors.GREY_400),
                        ft.Text(nemesis_txt, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_ACCENT)
                    ], spacing=2)
                ], spacing=10),
            ], spacing=12),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=15,
            expand=True
        )

        bottom_row = ft.Row([category_card, insights_card], spacing=12)
        self.controls.append(
            ft.Container(
                content=bottom_row,
                padding=ft.Padding.only(left=20, right=20, top=5, bottom=25)
            )
        )