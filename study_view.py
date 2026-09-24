import flet as ft
import database as db
from wallpaper import update_desktop_wallpaper

DEFAULT_ELI5 = """• What is it?
-> 

• What problem does it solve?
-> 

• Real-world analogy / Simple metaphor:
-> """

DEFAULT_CODE = """# 2. Minimal Proof of Work Example
# (Write from scratch from memory, not copied from the video)

def proof_of_work():
    pass
"""

DEFAULT_BREAK = """• If I remove or change [X], what error happens?
-> 

• When should I NOT use this?
-> 

• Common edge cases & pitfalls:
-> """

DEFAULT_RECALL = """Q1: 
A1: 

Q2: 
A2: """

class StudyView(ft.Row):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0, visible=False)
        self.app_page = page
        self.selected_session_id = None

        self.topic_list_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=6)
        
        self.topic_title_input = ft.TextField(label="Topic / Chapter Title", text_size=15, dense=True, expand=True)
        self.source_dropdown = ft.Dropdown(
            label="Course / Source",
            value="FIAP",
            options=[
                ft.DropdownOption("FIAP"),
                ft.DropdownOption("Alura"),
                ft.DropdownOption("Nano Courses"),
                ft.DropdownOption("Documentation / Book"),
                ft.DropdownOption("Self-Study")
            ],
            width=180,
            dense=True
        )
        self.status_dropdown = ft.Dropdown(
            label="Status",
            value="In Progress",
            options=[
                ft.DropdownOption("In Progress"),
                ft.DropdownOption("Mastered (+30 XP)")
            ],
            width=200,
            dense=True
        )

        self.eli5_input = ft.TextField(label="1. The ELI5 Summary (Explain in simple terms without jargon)", multiline=True, min_lines=6, max_lines=None, text_size=13)
        self.code_input = ft.TextField(label="2. The Toy Sandbox (Proof of Work code example)", multiline=True, min_lines=7, max_lines=None, text_size=12, text_style=ft.TextStyle(font_family="Consolas"))
        self.break_input = ft.TextField(label="3. The Break-It Test (Edge cases & common failures)", multiline=True, min_lines=6, max_lines=None, text_size=13)
        self.recall_input = ft.TextField(label="4. Active Recall Flashcard (Test for future self)", multiline=True, min_lines=6, max_lines=None, text_size=13)

        self.editor_container = ft.Column(
            scroll=ft.ScrollMode.AUTO, 
            expand=True, 
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH
        )
        
        self.build_layout()
        self.refresh_list()

    def build_layout(self):
        new_topic_field = ft.TextField(hint_text="New chapter name...", expand=True, dense=True, text_size=13)
        
        def add_topic_clicked(e):
            if new_topic_field.value and new_topic_field.value.strip():
                new_id = db.add_study_session(new_topic_field.value.strip())
                new_topic_field.value = ""
                self.select_chapter(new_id)

        left_sidebar = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.CYAN_ACCENT, size=24),
                        ft.Text("Study Chapters", size=18, weight=ft.FontWeight.BOLD)
                    ]),
                    padding=ft.Padding.only(bottom=10)
                ),
                ft.Row([
                    new_topic_field,
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE,
                        icon_color=ft.Colors.CYAN_ACCENT,
                        tooltip="Add Chapter",
                        on_click=add_topic_clicked
                    )
                ]),
                ft.Divider(color=ft.Colors.GREY_800),
                self.topic_list_column
            ]),
            width=320,
            padding=15,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW
        )

        right_workspace = ft.Container(
            content=self.editor_container,
            expand=True,
            padding=ft.Padding.only(left=20, right=30, top=15, bottom=30)
        )

        self.controls = [
            left_sidebar,
            ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
            right_workspace
        ]

    def select_chapter(self, session_id: int):
        """Immediately loads editor AND updates sidebar highlight."""
        self.selected_session_id = session_id
        self.load_editor(session_id)
        self.render_sidebar_tiles()
        if self.app_page:
            self.app_page.update()

    def render_sidebar_tiles(self):
        """Re-draws sidebar tiles so the active one highlights in real time."""
        self.topic_list_column.controls.clear()
        sessions = db.get_study_sessions()

        if not sessions:
            self.topic_list_column.controls.append(
                ft.Text("No chapters yet.\nAdd one above!", color=ft.Colors.GREY_500, size=13)
            )
            return

        for s in sessions:
            sid, topic, source, _, _, _, _, status, _ = s
            is_selected = (sid == self.selected_session_id)
            is_mastered = (status == "Mastered")
            badge_color = ft.Colors.GREEN_ACCENT if is_mastered else ft.Colors.ORANGE_ACCENT

            tile = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(topic, size=14, weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL, expand=True),
                        ft.Container(
                            content=ft.Text(status, size=10, color=badge_color, weight=ft.FontWeight.BOLD),
                            border=ft.Border.all(1, badge_color),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=4, vertical=1)
                        )
                    ]),
                    ft.Text(source, size=11, color=ft.Colors.GREY_500)
                ], spacing=2),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if is_selected else ft.Colors.TRANSPARENT,
                border_radius=8,
                padding=10,
                on_click=lambda e, s_id=sid: self.select_chapter(s_id)  # Instant selection!
            )
            self.topic_list_column.controls.append(tile)

    def refresh_list(self):
        sessions = db.get_study_sessions()
        if not sessions:
            self.show_empty_editor()
            self.render_sidebar_tiles()
            return

        if self.selected_session_id is None or not any(s[0] == self.selected_session_id for s in sessions):
            self.selected_session_id = sessions[0][0]

        self.render_sidebar_tiles()
        self.load_editor(self.selected_session_id)

    def load_editor(self, session_id: int):
        sessions = db.get_study_sessions()
        session = next((s for s in sessions if s[0] == session_id), None)

        if not session:
            self.show_empty_editor()
            return

        sid, topic, source, eli5, code, break_t, recall, status, created_at = session

        self.topic_title_input.value = topic
        self.source_dropdown.value = source
        self.status_dropdown.value = "Mastered (+30 XP)" if status == "Mastered" else "In Progress"

        self.eli5_input.value = eli5 if (eli5 and eli5.strip()) else DEFAULT_ELI5
        self.code_input.value = code if (code and code.strip()) else DEFAULT_CODE
        self.break_input.value = break_t if (break_t and break_t.strip()) else DEFAULT_BREAK
        self.recall_input.value = recall if (recall and recall.strip()) else DEFAULT_RECALL

        def save_clicked(e):
            clean_status = "Mastered" if "Mastered" in self.status_dropdown.value else "In Progress"
            db.update_study_session(
                session_id=self.selected_session_id,
                topic=self.topic_title_input.value.strip(),
                source=self.source_dropdown.value,
                eli5=self.eli5_input.value,
                code_sandbox=self.code_input.value,
                break_test=self.break_input.value,
                recall_questions=self.recall_input.value,
                status=clean_status
            )
            e.control.content = "Saved!"
            self.render_sidebar_tiles()
            update_desktop_wallpaper()
            if self.app_page:
                self.app_page.update()

        def delete_clicked(e):
            db.delete_study_session(self.selected_session_id)
            self.selected_session_id = None
            self.refresh_list()
            update_desktop_wallpaper()

        self.editor_container.controls = [
            ft.Row([
                self.topic_title_input,
                self.source_dropdown,
                self.status_dropdown,
                ft.Button(
                    content="Save Notes",
                    icon=ft.Icons.SAVE,
                    on_click=save_clicked
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Delete Chapter",
                    on_click=delete_clicked
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=10),
            ft.Divider(color=ft.Colors.GREY_800),
            ft.Text("Proof of Work Study Template", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
            self.eli5_input,
            self.code_input,
            self.break_input,
            self.recall_input,
        ]

    def show_empty_editor(self):
        self.editor_container.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=48, color=ft.Colors.GREY_600),
                    ft.Text("Select a chapter on the left or add a new one to begin studying!", color=ft.Colors.GREY_400, size=14)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.Alignment.CENTER,
                padding=50
            )
        ]