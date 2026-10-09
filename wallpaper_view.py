import threading
from pathlib import Path

import flet as ft

import ai_gemini
import ai_insight
import database as db
import wallpaper as wp


class WallpaperView(ft.Row):
    """HUD customizer: settings on the left, a live preview on the right. Every change is saved and
    re-previewed; 'Apply' updates the desktop."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0, visible=False, vertical_alignment=ft.CrossAxisAlignment.START)
        self.app_page = page
        self.preview = ft.Container()  # gets an ft.Image once the first preview is ready
        self.preview_status = ft.Text("", size=12, color=ft.Colors.GREY_400)
        self.settings_col = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.message = ""
        self._preview_lock = threading.Lock()
        self._preview_pending = False
        self.controls = [
            ft.Container(content=self.settings_col, width=560, padding=ft.Padding.only(left=20, right=10, top=15,
                                                                                     bottom=20)),
            ft.Container(content=ft.Column([
                ft.Row([ft.Text("Preview", size=16, weight=ft.FontWeight.BOLD), self.preview_status], spacing=10),
                self.preview,
            ], spacing=8), expand=True, padding=ft.Padding.only(left=10, right=20, top=20)),
        ]
        self.render()

    # ------------------------------------------------------------ helpers
    def _update(self):
        if self.app_page:
            self.app_page.update()

    def _set(self, key, value, refresh_settings=False):
        db.set_hud_setting(key, value)
        if refresh_settings:
            self.render()
        else:
            self.refresh_preview()

    def refresh_preview(self):
        """Re-renders the preview in the background (coalescing rapid changes)."""
        with self._preview_lock:
            if self._preview_pending:
                return
            self._preview_pending = True
        self.preview_status.value = "Updating…"
        self._update()

        def work():
            try:
                png = wp.render_preview()
                self.preview.content = ft.Image(src=png, fit=ft.BoxFit.CONTAIN, border_radius=8)
                self.preview_status.value = "This is how your desktop will look."
            except Exception as exc:
                self.preview_status.value = f"Preview failed: {exc}"
            finally:
                with self._preview_lock:
                    self._preview_pending = False
            try:
                self._update()
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name="hud-preview").start()

    # ------------------------------------------------------------ actions
    def apply(self, e=None):
        if wp.is_paused():
            wp.resume_hud()
        else:
            wp.request_wallpaper_update(delay=0)
        self.message = "Applied to your desktop."
        self.render()

    def toggle_pause(self, e=None):
        if wp.is_paused():
            wp.resume_hud()
            self.message = "HUD resumed."
        else:
            restored = wp.pause_hud()
            self.message = "Paused — your original wallpaper is back." if restored else \
                "Paused. (No copy of your original wallpaper was found, so the current one stays.)"
        self.render()

    def _move_block(self, idx, delta):
        blocks = wp.get_blocks()
        j = idx + delta
        if 0 <= j < len(blocks):
            blocks[idx], blocks[j] = blocks[j], blocks[idx]
            wp.save_blocks(blocks)
            self.render()

    def _toggle_block(self, idx, on):
        blocks = wp.get_blocks()
        blocks[idx]["on"] = on
        wp.save_blocks(blocks)
        if on and blocks[idx]["id"] == "insight":
            ai_insight.ensure_today(on_ready=self._insight_ready)
        self.render()

    def _insight_ready(self):
        self.render()
        wp.request_wallpaper_update()

    def _regenerate_insight(self, e=None):
        if ai_insight.ensure_today(on_ready=self._insight_ready, force=True):
            self.message = "Gemini is writing today's insight…"
        self.render()

    async def _browse_folder(self, e):
        try:
            picker = ft.FilePicker()
            self.app_page.services.append(picker)
            folder = await picker.get_directory_path(dialog_title="Folder with wallpaper images")
        except Exception:
            self.message = "The folder picker isn't available here — paste the folder path instead."
            self.render()
            return
        if folder:
            db.set_hud_setting(wp.SETTING_FOLDER, folder)
            self.render()

    def _next_image(self, e=None):
        try:
            offset = int(db.get_hud_settings().get(wp.SETTING_ROTATION, "0") or 0)
        except ValueError:
            offset = 0
        db.set_hud_setting(wp.SETTING_ROTATION, str(offset + 1))
        self.render()

    # ------------------------------------------------------------ rendering
    def render(self):
        settings = db.get_hud_settings()
        paused = settings.get(wp.SETTING_PAUSED, "false") == "true"
        controls = [ft.Row([ft.Icon(ft.Icons.WALLPAPER, color=ft.Colors.CYAN_ACCENT, size=26),
                            ft.Text("Desktop Wallpaper HUD", size=22, weight=ft.FontWeight.BOLD)])]

        # status + apply / pause
        controls.append(ft.Container(content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.PAUSE_CIRCLE if paused else ft.Icons.CHECK_CIRCLE,
                            color=ft.Colors.AMBER_ACCENT if paused else ft.Colors.GREEN_ACCENT),
                    ft.Text("Paused — your own wallpaper is showing." if paused else
                            "Active — refreshes when you log things and every hour.", size=13, expand=True)]),
            ft.Row([ft.Button("Apply now", icon=ft.Icons.WALLPAPER, on_click=self.apply),
                    ft.TextButton("Resume" if paused else "Pause & restore my wallpaper",
                                  icon=ft.Icons.PLAY_ARROW if paused else ft.Icons.PAUSE, on_click=self.toggle_pause)],
                   spacing=8),
        ], spacing=8), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=12))
        if self.message:
            controls.append(ft.Text(self.message, color=ft.Colors.GREEN_ACCENT, size=12))
            self.message = ""

        # layout
        controls.append(self._card("Layout", [
            ft.Row([
                ft.Dropdown(label="Position", value=settings.get("position", "Top-Right"), width=170, dense=True,
                            options=[ft.DropdownOption(p) for p in wp.POSITIONS],
                            on_select=lambda e: self._set("position", e.control.value)),
                ft.Dropdown(label="Accent color", value=settings.get("accent_color", "Amber / Gold"), width=170,
                            dense=True, options=[ft.DropdownOption(c) for c in wp.COLOR_PALETTES],
                            on_select=lambda e: self._set("accent_color", e.control.value)),
            ], spacing=10),
            ft.Row([
                ft.Text("Columns", size=13, width=70),
                ft.SegmentedButton(segments=[ft.Segment(value="1", label=ft.Text("1")),
                                             ft.Segment(value="2", label=ft.Text("2"))],
                                   selected=[settings.get(wp.SETTING_COLUMNS, "1")], show_selected_icon=False,
                                   on_change=lambda e: self._set(wp.SETTING_COLUMNS, e.control.selected[0])),
                ft.Text("Size", size=13, width=40),
                ft.SegmentedButton(segments=[ft.Segment(value=s, label=ft.Text(s)) for s in wp.SIZES],
                                   selected=[settings.get(wp.SETTING_SIZE, "Normal")], show_selected_icon=False,
                                   on_change=lambda e: self._set(wp.SETTING_SIZE, e.control.selected[0])),
            ], spacing=10, wrap=True),
            ft.Text("Text scales with your screen resolution automatically (sharp on 1440p / 4K).", size=11,
                    color=ft.Colors.GREY_500),
        ]))

        # background
        mode = settings.get("bg_mode", wp.BG_PROJECT)
        bg_controls = [ft.Dropdown(label="Background", value=mode, dense=True, width=480,
                                   options=[ft.DropdownOption(m) for m in wp.BG_MODES],
                                   on_select=lambda e: self._set("bg_mode", e.control.value, refresh_settings=True))]
        if mode == wp.BG_FOLDER:
            folder = settings.get(wp.SETTING_FOLDER, "")
            images = wp.list_folder_images(folder)
            folder_f = ft.TextField(label="Folder", value=folder, dense=True, expand=True,
                                    hint_text=r"e.g. C:\Users\you\Pictures\Wallpapers")
            folder_f.on_submit = lambda e: self._set(wp.SETTING_FOLDER, (e.control.value or "").strip(), True)
            folder_f.on_blur = lambda e: self._set(wp.SETTING_FOLDER, (e.control.value or "").strip(), True) \
                if (e.control.value or "").strip() != folder else None
            today_img = wp.current_folder_image(settings)
            bg_controls += [
                ft.Row([folder_f, ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Browse…", on_click=self._browse_folder)]),
                ft.Row([
                    ft.Text(f"{len(images)} image{'s' if len(images) != 1 else ''} found" +
                            (f" • today: {today_img.name}" if today_img else ""), size=12,
                            color=ft.Colors.GREY_400 if images else ft.Colors.AMBER_ACCENT, expand=True),
                    ft.TextButton("Next image", icon=ft.Icons.SKIP_NEXT, on_click=self._next_image,
                                  disabled=len(images) < 2),
                ]),
                ft.Text("A new image each day (in name order). Images fill the screen without being stretched.",
                        size=11, color=ft.Colors.GREY_500),
            ]
        controls.append(self._card("Background", bg_controls))

        # blocks
        blocks = wp.get_blocks(settings)
        rows = []
        for i, b in enumerate(blocks):
            extra = []
            if b["id"] == "insight":
                if not ai_gemini.is_configured():
                    extra.append(ft.Text("needs a Gemini key (Study → ✨)", size=11, color=ft.Colors.AMBER_ACCENT))
                elif ai_insight.is_generating():
                    extra.append(ft.Text("writing…", size=11, color=ft.Colors.GREY_400))
                elif b["on"]:
                    extra.append(ft.IconButton(ft.Icons.REFRESH, icon_size=16, tooltip="New insight for today",
                                               on_click=self._regenerate_insight))
            rows.append(ft.Row([
                ft.Checkbox(value=b["on"], label=wp.BLOCKS[b["id"]], expand=True,
                            on_change=lambda e, idx=i: self._toggle_block(idx, bool(e.control.value))),
                *extra,
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16, tooltip="Move block up", disabled=i == 0,
                              on_click=lambda e, idx=i: self._move_block(idx, -1)),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=16, tooltip="Move block down",
                              disabled=i == len(blocks) - 1, on_click=lambda e, idx=i: self._move_block(idx, 1)),
            ], spacing=0))
        insight_text = ai_insight.cached_today()
        lang_dd = ft.Dropdown(label="AI & messages language", value=ai_insight.language(), width=240, dense=True,
                              options=[ft.DropdownOption(lang) for lang in ai_insight.LANGUAGES],
                              on_select=lambda e: db.set_hud_setting(ai_insight.SETTING_LANGUAGE, e.control.value))
        block_controls = rows + [lang_dd]
        if insight_text:
            block_controls.append(ft.Text(f"Today: “{insight_text}”", size=12, italic=True, color=ft.Colors.GREY_300))
        block_controls.append(ft.Text("Blocks with nothing to show (no events, no alerts…) are hidden automatically.",
                                      size=11, color=ft.Colors.GREY_500))
        controls.append(self._card("Blocks (order = top to bottom)", block_controls))

        self.settings_col.controls = controls
        self._update()
        self.refresh_preview()

    @staticmethod
    def _card(title, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=15, weight=ft.FontWeight.BOLD), *controls],
                                              spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=16)
