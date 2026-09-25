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
        self.expanded_tasks = set()
        self.render()

    def on_status_change(self, e, task_id):
        new_status = e.control.value
        db.update_task_status(task_id, new_status, self.year, self.week)
        self.render()
        update_desktop_wallpaper()

    def on_delete_task(self, task_id):
        db.delete_task(task_id)
        self.expanded_tasks.discard(task_id)
        self.render()
        update_desktop_wallpaper()

    def on_move_task(self, task_id: int, direction: str):
        db.move_task(task_id, direction)
        self.render()

    def toggle_notes(self, task_id):
        if task_id in self.expanded_tasks:
            self.expanded_tasks.remove(task_id)
        else:
            self.expanded_tasks.add(task_id)
        self.render()

    def save_notes_clicked(self, task_id: int, notes_val: str, btn: ft.Button):
        xp_earned = db.save_task_notes_with_progress(task_id, notes_val)
        
        if xp_earned > 0:
            btn.content = f"Saved! (+{xp_earned:.0f} XP 🔥)"
            btn.icon = ft.Icons.BOLT
        else:
            btn.content = "Saved!"
            btn.icon = ft.Icons.CHECK
            
        update_desktop_wallpaper()
        if self.app_page:
            self.app_page.update()

    def render(self):
        self.controls.clear()
        tasks = db.get_tasks()
        self.year, self.week, _ = db.get_current_week_info()
        completed_this_week = db.get_weekly_completed_tasks_count(self.year, self.week)
        bonus_xp = completed_this_week * QUEST_BONUS_XP

        # 1. Header Banner
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
                    "Click on any quest's note icon to expand its private notepad and steps!",
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

        # 2. Add New Quest Row
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

        # 3. Table Header
        header_row = ft.Container(
            content=ft.Row([
                ft.Text("Quest / Project", weight=ft.FontWeight.BOLD, size=14, expand=True),
                ft.Container(content=ft.Text("Current Stage", weight=ft.FontWeight.BOLD, size=14), width=160),
                ft.Container(content=ft.Text("Bonus", weight=ft.FontWeight.BOLD, size=14), width=110),
                ft.Container(content=ft.Text("Notes", weight=ft.FontWeight.BOLD, size=14), width=65),
                ft.Container(width=110)  # Spacer for reorder and delete buttons
            ]),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=15, vertical=10),
            margin=ft.Margin.only(left=20, right=20, top=10, bottom=5)
        )
        self.controls.append(header_row)

        if not tasks:
            self.controls.append(
                ft.Container(
                    content=ft.Text("No active quests. Add one above!", color=ft.Colors.GREY_500, size=14),
                    padding=20,
                    alignment=ft.Alignment.CENTER
                )
            )

        # 4. Quest Rows (With Collapsible Notepad & Reorder Buttons)
        for task_id, title, status, comp_yr, comp_wk, notes in tasks:
            is_complete = (status == "Complete")
            is_expanded = (task_id in self.expanded_tasks)
            color = STAGE_COLORS.get(status, ft.Colors.WHITE)

            title_text = ft.Text(
                title,
                size=14,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.GREY_400 if is_complete else ft.Colors.WHITE,
                style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_complete else ft.TextDecoration.NONE)
            )

            status_dropdown = ft.Dropdown(
                value=status,
                width=150,
                text_size=12,
                content_padding=5,
                options=[ft.DropdownOption(s) for s in TASK_STAGES],
                on_select=lambda e, tid=task_id: self.on_status_change(e, tid)
            )

            bonus_badge = ft.Container(
                content=ft.Text(
                    f"+{QUEST_BONUS_XP} XP (W{comp_wk})" if is_complete else "Pending",
                    size=11,
                    color=ft.Colors.GREEN_ACCENT if is_complete else ft.Colors.GREY_500,
                    weight=ft.FontWeight.BOLD if is_complete else ft.FontWeight.NORMAL
                ),
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN) if is_complete else ft.Colors.TRANSPARENT,
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4)
            )

            # Main summary row
            main_row = ft.Row([
                ft.Row([
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if is_complete else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=ft.Colors.GREEN_ACCENT if is_complete else color,
                        size=18
                    ),
                    title_text
                ], expand=True),
                ft.Container(content=status_dropdown, width=160),
                ft.Container(content=bonus_badge, width=110),
                ft.Container(
                    content=ft.IconButton(
                        ft.Icons.EDIT_NOTE if is_expanded else ft.Icons.NOTES,
                        icon_color=ft.Colors.CYAN_ACCENT if is_expanded or notes else ft.Colors.GREY_500,
                        tooltip="Expand / Collapse Notes",
                        on_click=lambda e, tid=task_id: self.toggle_notes(tid)
                    ),
                    width=65
                ),
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.ARROW_UPWARD,
                            icon_size=16,
                            icon_color=ft.Colors.GREY_400,
                            tooltip="Move Up",
                            on_click=lambda e, tid=task_id: self.on_move_task(tid, "up")
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_DOWNWARD,
                            icon_size=16,
                            icon_color=ft.Colors.GREY_400,
                            tooltip="Move Down",
                            on_click=lambda e, tid=task_id: self.on_move_task(tid, "down")
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            icon_size=18,
                            tooltip="Delete Quest",
                            on_click=lambda e, tid=task_id: self.on_delete_task(tid)
                        )
                    ], spacing=0, alignment=ft.MainAxisAlignment.END),
                    width=110,
                    alignment=ft.Alignment.CENTER
                )
            ])

            # Collapsible Notepad Area (Full-Width Expansion)
            row_items = [main_row]

            if is_expanded:
                notes_field = ft.TextField(
                    value=notes,
                    hint_text="Write steps, reference links, parts, notes, or ideas here...",
                    multiline=True,
                    min_lines=4,
                    max_lines=14,
                    text_size=13
                )
                
                save_btn = ft.Button(content="Save Notes", icon=ft.Icons.SAVE)
                save_btn.on_click = lambda e, tid=task_id, nf=notes_field, b=save_btn: self.save_notes_clicked(tid, nf.value, b)

                notepad_box = ft.Container(
                    content=ft.Column([
                        ft.Divider(color=ft.Colors.GREY_800, height=1),
                        notes_field,
                        ft.Row([
                            save_btn,
                            ft.Text(f"{len(notes)} characters saved", size=11, color=ft.Colors.GREY_500)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    padding=ft.Padding.only(left=25, right=10, top=5, bottom=10)
                )
                row_items.append(notepad_box)

            quest_card = ft.Container(
                content=ft.Column(row_items, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_complete else ft.Colors.with_opacity(0.05, ft.Colors.GREEN),
                border=ft.Border.all(1, ft.Colors.CYAN_ACCENT) if is_expanded else None,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=15, vertical=6),
                margin=ft.Margin.symmetric(horizontal=20, vertical=3)
            )

            self.controls.append(quest_card)

        if self.app_page:
            self.app_page.update()