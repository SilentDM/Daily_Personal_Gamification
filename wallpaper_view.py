import flet as ft
import database as db
from wallpaper import update_desktop_wallpaper, COLOR_PALETTES

class WallpaperView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False)
        self.app_page = page
        self.render()

    def save_and_apply(self, e):
        db.set_hud_setting("position", self.pos_dropdown.value)
        db.set_hud_setting("bg_mode", self.bg_dropdown.value)
        db.set_hud_setting("accent_color", self.color_dropdown.value)
        db.set_hud_setting("show_quests", "true" if self.quests_check.value else "false")
        db.set_hud_setting("show_score", "true" if self.score_check.value else "false")
        db.set_hud_setting("show_xp_bar", "true" if self.xp_check.value else "false")
        db.set_hud_setting("show_studies", "true" if self.studies_check.value else "false")
        
        update_desktop_wallpaper()
        
        e.control.content = "Applied to Wallpaper!"
        e.control.icon = ft.Icons.CHECK
        if self.app_page:
            self.app_page.update()

    def render(self):
        self.controls.clear()
        settings = db.get_hud_settings()

        # Header Title
        self.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.WALLPAPER, color=ft.Colors.CYAN_ACCENT, size=26),
                    ft.Text("Desktop Wallpaper & HUD Customizer", size=22, weight=ft.FontWeight.BOLD)
                ]),
                padding=ft.Padding.only(left=20, top=20, bottom=5)
            )
        )

        # 1. Position & Background Card
        self.pos_dropdown = ft.Dropdown(
            label="HUD Screen Position",
            value=settings["position"],
            width=240,
            options=[
                ft.DropdownOption("Top-Right"),
                ft.DropdownOption("Top-Left"),
                ft.DropdownOption("Bottom-Right"),
                ft.DropdownOption("Bottom-Left"),
                ft.DropdownOption("Top-Center"),
                ft.DropdownOption("Center")
            ]
        )

        self.bg_dropdown = ft.Dropdown(
            label="Background Style",
            value=settings["bg_mode"],
            width=260,
            options=[
                ft.DropdownOption("Pure Black (Minimalist)"),
                ft.DropdownOption("Custom Image (base_wallpaper.jpg)")
            ]
        )

        self.color_dropdown = ft.Dropdown(
            label="Accent Theme Color",
            value=settings["accent_color"],
            width=200,
            options=[ft.DropdownOption(c) for c in COLOR_PALETTES.keys()]
        )

        pos_card = ft.Container(
            content=ft.Column([
                ft.Text("Placement & Appearance", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Choose where the HUD lives on your monitor and pick your theme color:", color=ft.Colors.GREY_400, size=13),
                ft.Row([self.pos_dropdown, self.bg_dropdown, self.color_dropdown], spacing=15),
            ], spacing=10),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=20,
            margin=ft.Margin.symmetric(horizontal=20, vertical=10)
        )
        self.controls.append(pos_card)

        # 2. Content Toggles Card
        self.score_check = ft.Checkbox(label="Show Daily Score & Streak", value=(settings.get("show_score", "true") == "true"))
        self.xp_check = ft.Checkbox(label="Show Level & XP Bar", value=(settings.get("show_xp_bar", "true") == "true"))
        self.quests_check = ft.Checkbox(label="Show Active Quests", value=(settings.get("show_quests", "true") == "true"))
        self.studies_check = ft.Checkbox(label="Show In-Progress Studies", value=(settings.get("show_studies", "true") == "true"))

        content_card = ft.Container(
            content=ft.Column([
                ft.Text("What to Display on the HUD", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Toggle which widgets appear inside your wallpaper card:", color=ft.Colors.GREY_400, size=13),
                ft.Row([self.score_check, self.xp_check, self.quests_check, self.studies_check], spacing=20, wrap=True),
            ], spacing=10),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=20,
            margin=ft.Margin.symmetric(horizontal=20, vertical=5)
        )
        self.controls.append(content_card)

        # 3. Action Button
        apply_btn = ft.Container(
            content=ft.Row([
                ft.Button(
                    content="Save & Apply to Wallpaper",
                    icon=ft.Icons.SAVE,
                    on_click=self.save_and_apply
                )
            ]),
            padding=ft.Padding.symmetric(horizontal=20, vertical=15)
        )
        self.controls.append(apply_btn)

        if self.app_page:
            self.app_page.update()