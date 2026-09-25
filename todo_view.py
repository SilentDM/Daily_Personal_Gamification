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
        self.expanded_tasks = set()
        self.render()

    def on_delete_task(self, task_id):
        db.delete_task(task_id)
        self.expanded_tasks.discard(task_id)
        self.render()
        update_desktop_wallpaper()

    def on_move_task(self, task_id: int, direction: str):
        db.move_task(task_id, direction)
        self.render()

    def toggle_expand(self, task_id):
        if task_id in self.expanded_tasks:
            self.expanded_tasks.remove(task_id)
        else:
            self.expanded_tasks.add(task_id)
        self.render()

    def on_subtask_status_change(self, subtask_id: int, new_status: str):
        db.update_subtask_status(subtask_id, new_status)
        self.render()
        update_desktop_wallpaper()

    def on_add_subtask(self, task_id: int, title_field: ft.TextField):
        if title_field.value and title_field.value.strip():
            db.add_subtask(task_id, title_field.value.strip())
            title_field.value = ""
            self.render()
            update_desktop_wallpaper()

    def on_delete_subtask(self, subtask_id: int):
        db.delete_subtask(subtask_id)
        self.render()
        update_desktop_wallpaper()

    def on_move_subtask(self, subtask_id: int, direction: str):
        db.move_subtask(subtask_id, direction)
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
        year, week, _ = db.get_current_week_info()
        self.controls.clear()
        tasks = db.get_tasks()
        completed_this_week = db.get_weekly_completed_tasks_count(year, week)
        bonus_xp = completed_this_week * QUEST_BONUS_XP

        # 1. Header Banner
        bonus_banner = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.MILITARY_TECH, color=ft.Colors.AMBER_ACCENT, size=32),
                    ft.Column([
                        ft.Text(f"Quests Completed This Week: {completed_this_week}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"🎁 Week {week} Bonus: +{bonus_xp} XP earned", size=13, color=ft.Colors.GREEN_ACCENT)
                    ], spacing=2)
                ]),
                ft.Text(
                    "Click on any quest to unfold subquests, track steps, and edit notes!",
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

        # 2. Add New Main Quest Row
        new_task_input = ft.TextField(
            hint_text="Enter main quest or project (e.g. Perder Peso, Resolver IR, RPG Campaign)...",
            expand=True,
            dense=True,
            text_size=13
        )

        def add_main_clicked(e):
            if new_task_input.value and new_task_input.value.strip():
                new_id = db.add_task(new_task_input.value.strip())
                new_task_input.value = ""
                self.expanded_tasks.add(new_id)  # Auto-expand to add subquests
                self.render()

        add_bar = ft.Container(
            content=ft.Row([
                new_task_input,
                ft.Button(
                    content="Add Main Quest",
                    icon=ft.Icons.ADD_TASK,
                    on_click=add_main_clicked
                )
            ]),
            padding=ft.Padding.symmetric(horizontal=20, vertical=5)
        )
        self.controls.append(add_bar)

        # 3. Table Header
        header_row = ft.Container(
            content=ft.Row([
                ft.Text("Main Quest", weight=ft.FontWeight.BOLD, size=14, expand=True),
                ft.Container(content=ft.Text("Progress", weight=ft.FontWeight.BOLD, size=14), width=230),
                ft.Container(content=ft.Text("Bounty", weight=ft.FontWeight.BOLD, size=14), width=110),
                ft.Container(width=110)  # Spacer for Reorder/Delete
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

        # 4. Quest Cards
        for task_id, title, status, comp_yr, comp_wk, notes, subtasks, progress_pct in tasks:
            is_complete = (status == "Complete" or progress_pct >= 99.9)
            is_expanded = (task_id in self.expanded_tasks)

            # Progress Bar Color
            if is_complete:
                bar_color = ft.Colors.GREEN_ACCENT
            elif progress_pct >= 60.0:
                bar_color = ft.Colors.CYAN_ACCENT
            elif progress_pct >= 25.0:
                bar_color = ft.Colors.ORANGE_ACCENT
            else:
                bar_color = ft.Colors.BLUE_GREY_400

            completed_subs = sum(1 for s in subtasks if s[2] == "Complete")
            ratio_text = f"{completed_subs}/{len(subtasks)} ({int(progress_pct)}%)" if subtasks else f"{int(progress_pct)}%"

            # Progress Bar Widget
            progress_widget = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Progress", size=11, color=ft.Colors.GREY_400),
                        ft.Text(ratio_text, size=11, weight=ft.FontWeight.BOLD, color=bar_color)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(value=progress_pct / 100.0, color=bar_color, bgcolor=ft.Colors.GREY_800, height=8)
                ], spacing=4),
                width=230
            )

            # Bounty Badge
            bounty_badge = ft.Container(
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
                    ft.IconButton(
                        icon=ft.Icons.KEYBOARD_ARROW_DOWN if is_expanded else ft.Icons.KEYBOARD_ARROW_RIGHT,
                        icon_size=20,
                        icon_color=ft.Colors.CYAN_ACCENT,
                        tooltip="Expand / Collapse Steps",
                        on_click=lambda e, tid=task_id: self.toggle_expand(tid)
                    ),
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if is_complete else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=ft.Colors.GREEN_ACCENT if is_complete else ft.Colors.CYAN_ACCENT,
                        size=20
                    ),
                    ft.Text(
                        title,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREY_400 if is_complete else ft.Colors.WHITE,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if is_complete else ft.TextDecoration.NONE),
                        expand=True
                    )
                ], expand=True),
                progress_widget,
                ft.Container(content=bounty_badge, width=110),
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

            card_items = [main_row]

            # --- Expanded Content (Subquests List + Inline Add + Notepad) ---
            if is_expanded:
                sub_rows = []

                # Render existing subquests
                for sub_id, sub_title, sub_status, _ in subtasks:
                    sub_done = (sub_status == "Complete")
                    sub_color = STAGE_COLORS.get(sub_status, ft.Colors.WHITE)

                    sub_dropdown = ft.Dropdown(
                        value=sub_status,
                        width=150,
                        text_size=11,
                        content_padding=5,
                        options=[ft.DropdownOption(s) for s in TASK_STAGES],
                        on_select=lambda e, sid=sub_id: self.on_subtask_status_change(sid, e.control.value)
                    )

                    sub_row = ft.Container(
                        content=ft.Row([
                            ft.Row([
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE if sub_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                    size=16,
                                    color=ft.Colors.GREEN_ACCENT if sub_done else sub_color
                                ),
                                ft.Text(
                                    sub_title,
                                    size=13,
                                    color=ft.Colors.GREY_400 if sub_done else ft.Colors.WHITE,
                                    style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if sub_done else ft.TextDecoration.NONE),
                                    expand=True
                                )
                            ], expand=True),
                            sub_dropdown,
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.Icons.ARROW_UPWARD,
                                    icon_size=14,
                                    icon_color=ft.Colors.GREY_500,
                                    tooltip="Move Step Up",
                                    on_click=lambda e, sid=sub_id: self.on_move_subtask(sid, "up")
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.ARROW_DOWNWARD,
                                    icon_size=14,
                                    icon_color=ft.Colors.GREY_500,
                                    tooltip="Move Step Down",
                                    on_click=lambda e, sid=sub_id: self.on_move_subtask(sid, "down")
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    icon_color=ft.Colors.RED_300,
                                    tooltip="Delete Step",
                                    on_click=lambda e, sid=sub_id: self.on_delete_subtask(sid)
                                )
                            ], spacing=0)
                        ]),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4)
                    )
                    sub_rows.append(sub_row)

                # Quick Add-Subquest input
                new_sub_input = ft.TextField(
                    hint_text="Add milestone / step (e.g. -2kg, Coletar documentos, Preparar mapas)...",
                    expand=True,
                    dense=True,
                    text_size=12
                )

                add_sub_bar = ft.Row([
                    new_sub_input,
                    ft.Button(
                        content="Add Step",
                        icon=ft.Icons.ADD,
                        on_click=lambda e, tid=task_id, nsi=new_sub_input: self.on_add_subtask(tid, nsi)
                    )
                ], spacing=10)

                # Notepad Section for this Quest
                notes_field = ft.TextField(
                    value=notes,
                    hint_text="Write notes, reference links, parts, notes, or ideas here...",
                    multiline=True,
                    min_lines=3,
                    max_lines=10,
                    text_size=13
                )
                save_btn = ft.Button(content="Save Notes", icon=ft.Icons.SAVE)
                save_btn.on_click = lambda e, tid=task_id, nf=notes_field, b=save_btn: self.save_notes_clicked(tid, nf.value, b)

                expanded_panel = ft.Container(
                    content=ft.Column([
                        ft.Divider(color=ft.Colors.GREY_800, height=1),
                        ft.Text("SUBQUESTS & MILESTONES:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
                        ft.Column(sub_rows, spacing=4) if sub_rows else ft.Text("No subquests added yet. Add your first step below!", size=12, color=ft.Colors.GREY_500, italic=True),
                        add_sub_bar,
                        ft.Divider(color=ft.Colors.GREY_800, height=1),
                        ft.Text("QUEST NOTEPAD:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
                        notes_field,
                        ft.Row([
                            save_btn,
                            ft.Text(f"{len(notes)} characters saved", size=11, color=ft.Colors.GREY_500)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    padding=ft.Padding.only(left=35, right=15, top=5, bottom=12)
                )
                card_items.append(expanded_panel)

            quest_card = ft.Container(
                content=ft.Column(card_items, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_complete else ft.Colors.with_opacity(0.05, ft.Colors.GREEN),
                border=ft.Border.all(1, ft.Colors.CYAN_ACCENT) if is_expanded else None,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=15, vertical=8),
                margin=ft.Margin.symmetric(horizontal=20, vertical=4)
            )

            self.controls.append(quest_card)

        if self.app_page:
            self.app_page.update()