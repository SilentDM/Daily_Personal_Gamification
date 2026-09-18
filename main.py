import flet as ft
import database as db
from schedule_view import ScheduleView
from graphs_view import GraphsView
from todo_view import TodoView

def main(page: ft.Page):
    page.title = "Personal Gamification Tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1320
    page.window.height = 840
    page.padding = 0

    db.init_db()

    if not db.get_activities():
        initial_tasks = [
            "Workout / Gym", "Stretching", "Healthy Diet",
            "1h Study / Course", "Walk with Dog"
        ]
        for task in initial_tasks:
            db.add_activity(task)

    # Views
    schedule_view = ScheduleView(page)
    graphs_view = GraphsView(page)
    todo_view = TodoView(page)

    def on_nav_change(e):
        idx = e.control.selected_index
        # Toggle visibility
        schedule_view.visible = (idx == 0)
        graphs_view.visible = (idx == 1)
        todo_view.visible = (idx == 2)

        if idx == 0:
            schedule_view.render()
            schedule_view.calculate_daily_scores()
        elif idx == 1:
            graphs_view.refresh()
        elif idx == 2:
            todo_view.render()

        page.update()

    # 3-Tab Navigation Rail
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
            ft.NavigationRailDestination(
                icon=ft.Icons.CHECKLIST_OUTLINED,
                selected_icon=ft.Icons.CHECKLIST,
                label="Quests"
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
                graphs_view,
                todo_view
            ],
            expand=True
        )
    )

ft.run(main)