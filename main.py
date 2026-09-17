import flet as ft
import database as db
from schedule_view import ScheduleView
from graphs_view import GraphsView

def main(page: ft.Page):
    # App Window Setup
    page.title = "Personal Gamification Tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1320
    page.window.height = 840
    page.padding = 0

    # Initialize Database
    db.init_db()

    # Pre-seed default activities if the table is empty
    if not db.get_activities():
        initial_tasks = [
            "Workout / Gym", "Stretching", "Healthy Diet",
            "1h Study / Course", "Walk with Dog"
        ]
        for task in initial_tasks:
            db.add_activity(task)

    # Initialize Views
    schedule_view = ScheduleView(page)
    graphs_view = GraphsView(page)

    # Tab navigation handler
    def on_nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            schedule_view.visible = True
            graphs_view.visible = False
        elif idx == 1:
            schedule_view.visible = False
            graphs_view.refresh()
            graphs_view.visible = True
        page.update()

    # Navigation Sidebar
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=160,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.CALENDAR_VIEW_WEEK_OUTLINED,
                selected_icon=ft.Icons.CALENDAR_VIEW_WEEK,
                label="Schedule"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED,
                selected_icon=ft.Icons.BAR_CHART,
                label="Graphs"
            ),
        ],
        on_change=on_nav_change
    )

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                schedule_view,
                graphs_view
            ],
            expand=True
        )
    )

ft.run(main)