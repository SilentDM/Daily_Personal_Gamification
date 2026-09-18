import flet as ft
import database as db
import threading
import os
import ctypes
import pystray
from PIL import Image, ImageDraw
from wallpaper import update_desktop_wallpaper

from schedule_view import ScheduleView
from graphs_view import GraphsView
from todo_view import TodoView
from study_view import StudyView
from wallpaper_view import WallpaperView

APP_TITLE = "Personal Gamification Tracker"

# Global Tray flags
TRAY_INITIALIZED = False
tray_icon_instance = None

def get_window_hwnd():
    """Finds the native Windows HWND handle using the window title."""
    return ctypes.windll.user32.FindWindowW(None, APP_TITLE)

def hide_window_to_tray():
    """Tells Windows to completely remove the window from screen and taskbar."""
    hwnd = get_window_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE

def restore_window_from_tray(page: ft.Page):
    """Restores the window directly to maximized state and brings it to front."""
    hwnd = get_window_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 3)  # 3 = SW_MAXIMIZE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    
    # Sync Flet's internal window state
    page.window.maximized = True
    page.update()

def create_tray_icon_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(18, 22, 30, 255), outline=(0, 220, 255, 255), width=3)
    draw.ellipse([22, 22, 42, 42], fill=(0, 220, 255, 255))
    return img

def main(page: ft.Page):
    global TRAY_INITIALIZED, tray_icon_instance

    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1380
    page.window.height = 860
    page.window.maximized = True
    page.padding = 0

    # 1. Close-to-Tray: Intercept 'X' and execute native Windows SW_HIDE
    page.window.prevent_close = True

    def on_window_event(e):
        event_val = getattr(e, "data", None) or getattr(e, "type", None)
        if event_val in ("close", ft.WindowEventType.CLOSE):
            hide_window_to_tray()

    page.window.on_event = on_window_event

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
    study_view = StudyView(page)
    wallpaper_view = WallpaperView(page)

    def on_nav_change(e):
        idx = e.control.selected_index
        schedule_view.visible = (idx == 0)
        graphs_view.visible = (idx == 1)
        todo_view.visible = (idx == 2)
        study_view.visible = (idx == 3)
        wallpaper_view.visible = (idx == 4)

        if idx == 0:
            schedule_view.render()
            schedule_view.calculate_daily_scores()
        elif idx == 1:
            graphs_view.refresh()
        elif idx == 2:
            todo_view.render()
        elif idx == 3:
            study_view.refresh_list()
        elif idx == 4:
            wallpaper_view.render()

        page.update()

    # 5-Tab Navigation Rail
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=160,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.CALENDAR_VIEW_WEEK_OUTLINED, selected_icon=ft.Icons.CALENDAR_VIEW_WEEK, label="Schedule"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART_OUTLINED, selected_icon=ft.Icons.BAR_CHART, label="Graphs"),
            ft.NavigationRailDestination(icon=ft.Icons.CHECKLIST_OUTLINED, selected_icon=ft.Icons.CHECKLIST, label="Quests"),
            ft.NavigationRailDestination(icon=ft.Icons.SCHOOL_OUTLINED, selected_icon=ft.Icons.SCHOOL, label="Study"),
            ft.NavigationRailDestination(icon=ft.Icons.WALLPAPER_OUTLINED, selected_icon=ft.Icons.WALLPAPER, label="Wallpaper"),
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
                todo_view,
                study_view,
                wallpaper_view
            ],
            expand=True
        )
    )

    update_desktop_wallpaper()

    # 2. System Tray Handlers
    def show_window(icon, item):
        restore_window_from_tray(page)

    def force_refresh_wallpaper(icon, item):
        update_desktop_wallpaper()

    def quit_app(icon, item):
        if icon:
            icon.stop()
        os._exit(0)

    if not TRAY_INITIALIZED:
        TRAY_INITIALIZED = True

        tray_menu = pystray.Menu(
            pystray.MenuItem("Open Tracker", show_window, default=True),
            pystray.MenuItem("Refresh Wallpaper", force_refresh_wallpaper),
            pystray.MenuItem("Exit", quit_app)
        )

        tray_icon_instance = pystray.Icon(
            "GamificationTracker",
            create_tray_icon_image(),
            APP_TITLE,
            menu=tray_menu
        )

        threading.Thread(target=tray_icon_instance.run, daemon=True).start()

ft.run(main)