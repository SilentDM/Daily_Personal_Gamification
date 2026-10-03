try:
    from updater import check_for_updates
    check_for_updates()
except Exception:
    pass

import sys as _sys
import ctypes as _ctypes

# Single-instance guard (after the updater, so an update restart is never blocked)
_MUTEX = None
if _sys.platform == "win32":
    _k32 = _ctypes.WinDLL("kernel32", use_last_error=True)
    _MUTEX = _k32.CreateMutexW(None, False, "Local\\DailyGamificationTracker")
    if _ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        try:  # bring the running instance to the front instead
            _hwnd = _ctypes.windll.user32.FindWindowW(None, "Personal Gamification Tracker")
            if _hwnd:
                _ctypes.windll.user32.ShowWindow(_hwnd, 3)
                _ctypes.windll.user32.SetForegroundWindow(_hwnd)
        except Exception:
            pass
        _sys.exit(0)

import flet as ft
import database as db
import threading
import time
import os
import subprocess
import ctypes
import pystray
import winsound
from datetime import datetime, date
from PIL import Image, ImageDraw
from wallpaper import request_wallpaper_update as update_desktop_wallpaper, flush_wallpaper_update
from applog import setup_logging

from schedule_view import ScheduleView
from graphs_view import GraphsView
from todo_view import TodoView
from study_view import StudyView
from wallpaper_view import WallpaperView
from calendar_view import CalendarView
from documents_view import DocumentsView

APP_TITLE = "Personal Gamification Tracker"
log = setup_logging()

TRAY_INITIALIZED = False
tray_icon_instance = None
NOTIFIED_ALARMS = set()

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

    # 2. Foolproof Clean Exit: Destroys GUI client and kills entire process tree
    def clean_quit():
        global tray_icon_instance
        try:
            flush_wallpaper_update()  # do not lose a pending wallpaper refresh
        except Exception:
            pass
        try:
            if tray_icon_instance:
                tray_icon_instance.stop()
        except Exception:
            pass

        try:
            page.window.prevent_close = False
            page.window.destroy()
        except Exception:
            pass

        # Kill the entire process tree (Python + Flutter client) instantly
        try:
            subprocess.run(
                f"taskkill /F /T /PID {os.getpid()}",
                shell=True,
                creationflags=0x08000000
            )
        except Exception:
            pass

        os._exit(0)

    try:
        db.backup_db()  # backup BEFORE migrations touch the database
    except Exception:
        log.exception("Daily backup failed")  # never stop the app from starting

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
    documents_view = DocumentsView(page)

    def on_nav_change(e):
        idx = e.control.selected_index
        schedule_view.visible = (idx == 0)
        graphs_view.visible = (idx == 1)
        todo_view.visible = (idx == 2)
        study_view.visible = (idx == 3)
        wallpaper_view.visible = (idx == 4)
        calendar_view.visible = (idx == 5)
        documents_view.visible = (idx == 6)

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
        elif idx == 6:
            documents_view.render()

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
            ft.NavigationRailDestination(icon=ft.Icons.FOLDER_SHARED_OUTLINED, selected_icon=ft.Icons.FOLDER_SHARED, label="Documents"),
        ],
        trailing=ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.POWER_SETTINGS_NEW,
                icon_color=ft.Colors.RED_400,
                tooltip="Quit Application Completely",
                on_click=lambda e: clean_quit()
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
                calendar_view,
                documents_view
            ],
            expand=True
        )
    )

    update_desktop_wallpaper()

    # --- System Tray Handlers ---
    def show_window(icon, item):
        restore_window_from_tray(page)

    def force_refresh_wallpaper(icon, item):
        update_desktop_wallpaper(delay=0)

    def quit_from_tray(icon, item):
        clean_quit()

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
            page.pop_dialog()
            calendar_view.render()
            schedule_view.update_gamification_stats()
            update_desktop_wallpaper()
            page.update()

        def dismiss(e):
            page.pop_dialog()

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
        page.show_dialog(dlg)

    def reminder_loop():
        last_checked_day = date.today()
        last_checked_hour = datetime.now().hour

        while True:
            time.sleep(20)
            try:
                now = datetime.now()
                today = now.date()
                today_str = today.strftime("%Y-%m-%d")

                # 1. Midnight Rollover
                if today != last_checked_day:
                    last_checked_day = today
                    last_checked_hour = now.hour
                    schedule_view.render()
                    schedule_view.calculate_daily_scores()
                    update_desktop_wallpaper()
                    page.update()

                # 2. Hourly Wallpaper Refresh
                elif now.hour != last_checked_hour:
                    last_checked_hour = now.hour
                    update_desktop_wallpaper()

                # 3. Calendar Event Reminders (robust to sleep/resume, skips completed events)
                for ev in db.get_events_for_date(today):
                    eid, title, _, hour, _ = ev
                    if db.is_event_completed(eid, today_str):
                        continue
                    event_dt = datetime(today.year, today.month, today.day, hour, 0, 0)
                    delta_min = (event_dt - now).total_seconds() / 60.0

                    if 0.0 < delta_min <= 15.0:
                        key = (eid, today_str, "15m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                            try:  # unobtrusive: tray notification, no focus stealing
                                tray_icon_instance.notify(
                                    f"'{title}' starts at {hour:02d}:00 (in {int(delta_min) + 1} min)",
                                    "Upcoming appointment"
                                )
                            except Exception:
                                log.exception("tray notification failed")

                    elif -30.0 <= delta_min <= 0.0:
                        key = (eid, today_str, "0m")
                        if key not in NOTIFIED_ALARMS:
                            NOTIFIED_ALARMS.add(key)
                            NOTIFIED_ALARMS.add((eid, today_str, "15m"))
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                            restore_window_from_tray(page)
                            show_alarm_dialog(
                                "🚨 Event Starting NOW!",
                                f"'{title}' starts now ({hour:02d}:00)!",
                                eid, today_str
                            )
            except Exception:
                log.exception("reminder loop failed")

    threading.Thread(target=reminder_loop, daemon=True).start()

ft.run(main)