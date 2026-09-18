import flet as ft
import database as db
from wallpaper import update_desktop_wallpaper
from constants import TASK_STAGES, QUEST_BONUS_XP

STAGE_COLORS = {
    "Planning": ft.Colors.BLUE_GREY_400,
    "Started": ft.Colors.BLUE_400,
    "In Progress": ft.Colors.ORANGE_400,
    "Almost There": ft.Colors.AMBER_400,
    "Complete": ft.Colors.GREEN_ACCENT,
}

class TodoView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False)
        self.app_page = page
        self.year, self.week, _ = db.get_current_week_info()
        self.render()

    def on_status_change(self, e, task_id):
        new_status = e.control.value
        db.update_task_status(task_id, new_status, self.year, self.week)
        self.render()
        update_desktop_wallpaper()

    def on_delete_task(self, task_id):
        db.delete_task(task_id)
        self.render()

    def render(self):
        self.controls.clear()
        tasks = db.get_tasks()
        completed_this_week = db.get_weekly_completed_tasks_count(self.year, self.week)
        bonus_xp = completed_this_week * QUEST_BONUS_XP

        # 1. Header & Weekly Bonus Banner
        bonus_banner = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.MILITARY_TECH, color=ft.Colors.AMBER_ACCENT, size=32),
                    ft.Column([
                        ft.Text(f"Quests Completed This Week: {completed_this_week}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"🎁 Week {self.week} Bonus: +{bonus_xp} XP earned", size=13, color=ft.Colors.GREEN_ACCENT)
                    ], spacing=2)
                ]),
                ft.Text(
                    "One-off quests don't lower your habit score, but reward massive bonus XP when completed!",
                    size=12,
                    color=ft.Colors.GREY_400,
                    italic=True
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=15,
            margin=ft.Margin.symmetric(horizontal=20, vertical=10)
        )
        self.controls.append(bonus_banner)

        # 2. Add New Task Row
        new_task_input = ft.TextField(
            hint_text="Enter new quest or project to complete...",
            expand=True,
            dense=True,
            text_size=13
        )

        stage_dropdown = ft.Dropdown(
            value="Planning",
            width=150,
            dense=True,
            text_size=12,
            content_padding=5,
            options=[ft.DropdownOption(s) for s in TASK_STAGES]
        )

        def add_clicked(e):
            if new_task_input.value and new_task_input.value.strip():
                db.add_task(new_task_input.value.strip(), stage_dropdown.value)
                new_task_input.value = ""
                self.render()

        add_bar = ft.Container(
            content=ft.Row([
                new_task_input,
                stage_dropdown,
                ft.Button(
                    content="Add Quest",
                    icon=ft.Icons.ADD_TASK,
                    on_click=add_clicked
                )
            ]),
            padding=ft.Padding.symmetric(horizontal=20, vertical=5)
        )
        self.controls.append(add_bar)

        # 3. Tasks List Header
        header_row = ft.Container(
            content=ft.Row([
                ft.Text("Quest / Project", weight=ft.FontWeight.BOLD, size=14, expand=True),
                ft.Container(content=ft.Text("Current Stage", weight=ft.FontWeight.BOLD, size=14), width=160),
                ft.Container(content=ft.Text("Bonus", weight=ft.FontWeight.BOLD, size=14), width=120),
                ft.Container(width=50)  # Spacer for delete button
            ]),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=15, vertical=10),
            margin=ft.Margin.only(left=20, right=20, top=10, bottom=5)
        )
        self.controls.append(header_row)

        # 4. Render Task Rows
        if not tasks:
            self.controls.append(
                ft.Container(
                    content=ft.Text("No active quests. Add one above!", color=ft.Colors.GREY_500, size=14),
                    padding=20,
                    alignment=ft.Alignment.CENTER
                )
            )

        for task_id, title, status, comp_yr, comp_wk in tasks:
            is_complete = (status == "Complete")
            color = STAGE_COLORS.get(status, ft.Colors.WHITE)

            # Title formatting
            title_text = ft.Text(
                title,
                size=14,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.GREY_400 if is_complete else ft.Colors.WHITE,
                style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_complete else ft.TextDecoration.NONE)
            )

            # Dropdown for status transition
            status_dropdown = ft.Dropdown(
                value=status,
                width=150,
                text_size=12,
                content_padding=5,
                options=[ft.DropdownOption(s) for s in TASK_STAGES],
                on_select=lambda e, tid=task_id: self.on_status_change(e, tid)
            )

            # Bonus badge
            if is_complete:
                bonus_badge = ft.Container(
                    content=ft.Text(f"+{QUEST_BONUS_XP} XP (W{comp_wk})", size=11, color=ft.Colors.GREEN_ACCENT, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4)
                )
            else:
                bonus_badge = ft.Container(
                    content=ft.Text("Pending", size=11, color=ft.Colors.GREY_500),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4)
                )

            row = ft.Container(
                content=ft.Row([
                    ft.Row([
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE if is_complete else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            color=ft.Colors.GREEN_ACCENT if is_complete else color,
                            size=18
                        ),
                        title_text
                    ], expand=True),
                    ft.Container(content=status_dropdown, width=160),
                    ft.Container(content=bonus_badge, width=120),
                    ft.Container(
                        content=ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            icon_size=20,
                            tooltip="Delete Quest",
                            on_click=lambda e, tid=task_id: self.on_delete_task(tid)
                        ),
                        width=50,
                        alignment=ft.Alignment.CENTER
                    )
                ]),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_complete else ft.Colors.with_opacity(0.05, ft.Colors.GREEN),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=15, vertical=6),
                margin=ft.Margin.symmetric(horizontal=20, vertical=3)
            )
            self.controls.append(row)

        if self.app_page:
            self.app_page.update()