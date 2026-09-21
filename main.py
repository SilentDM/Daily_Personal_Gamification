import flet as ft
import database as db
import threading
import time
import os
import ctypes
import pystray
import winsound
from datetime import datetime, date
from PIL import Image, ImageDraw
from wallpaper import update_desktop_wallpaper

from schedule_view import ScheduleView
from graphs_view import GraphsView
from todo_view import TodoView
from study_view import StudyView
from wallpaper_view import WallpaperView
from calendar_view import CalendarView

APP_TITLE = "Personal Gamification Tracker"

TRAY_INITIALIZED = False
tray_icon_instance = None
NOTIFIED_ALARMS = set()

def force_exit():
    """Immediately and cleanly terminates all background threads and processes."""
    try:
        if tray_icon_instance:
            tray_icon_instance.visible = False
    except Exception:
        pass
    os._exit(0)

def get_window_hwnd():
    return ctypes.windll.user32.FindWindowW(None, APP_TITLE)

def hide_window_to_tray():
    hwnd = get_window_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)

def restore_window_from_tray(page: ft.Page):
    hwnd = get_window_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 3)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
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

    # 1. Close-to-Tray: Intercept 'X'
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
    calendar_view = CalendarView(page)

    def on_nav_change(e):
        idx = e.control.selected_index
        schedule_view.visible = (idx == 0)
        graphs_view.visible = (idx == 1)
        todo_view.visible = (idx == 2)
        study_view.visible = (idx == 3)
        wallpaper_view.visible = (idx == 4)
        calendar_view.visible = (idx == 5)

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
        elif idx == 5:
            calendar_view.render()

        page.update()

    # 6-Tab Navigation Rail with Power-Off button at the bottom
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
            ft.NavigationRailDestination(icon=ft.Icons.CALENDAR_MONTH_OUTLINED, selected_icon=ft.Icons.CALENDAR_MONTH, label="Calendar"),
        ],
        trailing=ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.POWER_SETTINGS_NEW,
                icon_color=ft.Colors.RED_400,
                tooltip="Quit Application Completely",
                on_click=lambda e: force_exit()
            ),
            padding=ft.Padding.only(bottom=20)
        ),
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
                wallpaper_view,
                calendar_view
            ],
            expand=True
        )
    )

    update_desktop_wallpaper()

    # --- System Tray Handlers (Fixed Deadlock) ---
    def show_window(icon, item):
        restore_window_from_tray(page)

    def force_refresh_wallpaper(icon, item):
        update_desktop_wallpaper()

    def quit_from_tray(icon, item):
        # Trigger force_exit in an independent thread so pystray doesn't deadlock
        threading.Thread(target=force_exit, daemon=True).start()

    if not TRAY_INITIALIZED:
        TRAY_INITIALIZED = True
        tray_menu = pystray.Menu(
            pystray.MenuItem("Open Tracker", show_window, default=True),
            pystray.MenuItem("Refresh Wallpaper", force_refresh_wallpaper),
            pystray.MenuItem("Exit", quit_from_tray)
        )
        tray_icon_instance = pystray.Icon("GamificationTracker", create_tray_icon_image(), APP_TITLE, menu=tray_menu)
        threading.Thread(target=tray_icon_instance.run, daemon=True).start()

    # --- Background Calendar Alarm Daemon ---
    def show_alarm_dialog(title_text: str, subtitle: str, event_id: int, date_str: str):
        def mark_done(e):
            db.toggle_event_completion(event_id, date_str)
            if hasattr(page, "close"):
                page.close(dlg)
            else:
                dlg.open = False
            calendar_view.render()
            schedule_view.update_gamification_stats()
            update_desktop_wallpaper()
            page.update()

        def dismiss(e):
            if hasattr(page, "close"):
                page.close(dlg)
            else:
                dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.ALARM, color=ft.Colors.AMBER_ACCENT, size=28),
                ft.Text(title_text, weight=ft.FontWeight.BOLD)
            ], spacing=10),
            content=ft.Column([
                ft.Text(subtitle, size=14, color=ft.Colors.WHITE),
                ft.Text("Marking as completed awards +10 XP towards your Discipline Level!", size=12, color=ft.Colors.GREEN_ACCENT)
            ], tight=True, spacing=8),
            actions=[
                ft.Button("Dismiss", on_click=dismiss),
                ft.Button("I Did It! (+10 XP)", icon=ft.Icons.CHECK, on_click=mark_done)
            ]
        )
        if hasattr(page, "open"):
            page.open(dlg)
        else:
            page.dialog = dlg
            dlg.open = True
            page.update()

    def reminder_loop():
        while True:
            time.sleep(20)
            try:
                today = date.today()
                today_str = today.strftime("%Y-%m-%d")
                events = db.get_events_for_date(today)
                now = datetime.now()

                for ev in events:
                    eid, title, _, hour, _ = ev
                    event_dt = datetime(today.year, today.month, today.day, hour, 0, 0)
                    delta_sec = (event_dt - now).total_seconds()
                    delta_min = delta_sec / 60.0

                    if 13.0 <= delta_min <= 16.0:
                        key = (eid, today_str, "15m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                            restore_window_from_tray(page)
                            show_alarm_dialog(
                                "⏰ Upcoming Appointment (in 15m)",
                                f"'{title}' is scheduled for {hour:02d}:00!",
                                eid, today_str
                            )

                    elif -2.0 <= delta_min <= 3.0:
                        key = (eid, today_str, "0m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                            restore_window_from_tray(page)
                            show_alarm_dialog(
                                "🚨 Event Starting NOW!",
                                f"'{title}' starts now ({hour:02d}:00)!",
                                eid, today_str
                            )
            except Exception as ex:
                pass

    threading.Thread(target=reminder_loop, daemon=True).start()

ft.run(main)