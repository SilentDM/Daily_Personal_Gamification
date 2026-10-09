import sys as _sys
import ctypes as _ctypes
import time as _time

RESTART_FLAG = "--restarted"
_restarting = RESTART_FLAG in _sys.argv

try:
    import settings as _settings
    _auto_update = _settings.flag("auto_update")
except Exception:  # first run: no database yet
    _auto_update = True

if _auto_update and not _restarting:
    try:
        from updater import check_for_updates
        check_for_updates()
    except Exception:
        pass

# Single-instance guard (after the updater, so an update restart is never blocked).
# After "Restart now" the old instance needs a moment to exit, so the new one waits for it.
_MUTEX = None
if _sys.platform == "win32":
    _k32 = _ctypes.WinDLL("kernel32", use_last_error=True)
    _already = False
    for _attempt in range(60 if _restarting else 1):
        _MUTEX = _k32.CreateMutexW(None, False, "Local\\DailyGamificationTracker")
        _already = _ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
        if not _already:
            break
        _k32.CloseHandle(_MUTEX)
        _time.sleep(0.25)
    if _already:
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
import ai_review
import threading
import time
import os
import subprocess
import ctypes
import pystray
import winsound
from datetime import datetime, date, timedelta
from pathlib import Path
from PIL import Image, ImageDraw
from wallpaper import request_wallpaper_update as update_desktop_wallpaper, flush_wallpaper_update, get_blocks as get_hud_blocks
import wallpaper
import ai_insight
import settings
import assistant_tools
from assistant import assistant
from notifier import Notifier
from applog import setup_logging

from schedule_view import ScheduleView, SETTING_REMINDED, reminder_time as schedule_reminder_time
from graphs_view import GraphsView
from todo_view import TodoView
from study_view import StudyView
from wallpaper_view import WallpaperView
from calendar_view import CalendarView
from documents_view import DocumentsView
from options_view import OptionsView

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
            if settings.flag("close_to_tray"):
                hide_window_to_tray()
            else:
                clean_quit()

    page.window.on_event = on_window_event

    # 2. Foolproof Clean Exit: Destroys GUI client and kills entire process tree
    def clean_quit():
        global tray_icon_instance
        assistant.stop()
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

    def restart_app():
        """Starts a fresh copy (it waits for this one to exit) and quits; used after changing tabs."""
        script = str(Path(_sys.argv[0]).resolve())
        # Through "cmd /c start": the new copy is not our child, so clean_quit's taskkill /T spares it
        subprocess.run(["cmd", "/c", "start", "", _sys.executable, script, RESTART_FLAG],
                       cwd=str(Path(script).parent), creationflags=0x08000000, timeout=15)
        clean_quit()

    # Views: Schedule is always on; the others only load when enabled in Options
    enabled = settings.enabled_tabs()
    wallpaper.set_enabled("wallpaper" in enabled)
    schedule_view = ScheduleView(page)
    graphs_view = GraphsView(page) if "graphs" in enabled else None
    todo_view = TodoView(page) if "quests" in enabled else None
    study_view = StudyView(page) if "study" in enabled else None
    wallpaper_view = WallpaperView(page) if "wallpaper" in enabled else None
    calendar_view = CalendarView(page) if "calendar" in enabled else None
    documents_view = DocumentsView(page) if "documents" in enabled else None
    options_view = OptionsView(page, assistant=assistant, on_restart=restart_app, loaded_tabs=enabled)

    icons = ft.Icons
    tabs = [t for t in [
        (schedule_view, lambda: schedule_view.render(),
         icons.CALENDAR_VIEW_WEEK_OUTLINED, icons.CALENDAR_VIEW_WEEK, "Schedule"),
        (graphs_view, lambda: graphs_view.refresh(), icons.BAR_CHART_OUTLINED, icons.BAR_CHART, "Graphs"),
        (todo_view, lambda: todo_view.render(), icons.CHECKLIST_OUTLINED, icons.CHECKLIST, "Quests"),
        (study_view, lambda: study_view.refresh_list(), icons.SCHOOL_OUTLINED, icons.SCHOOL, "Study"),
        (wallpaper_view, lambda: wallpaper_view.render(), icons.WALLPAPER_OUTLINED, icons.WALLPAPER, "Wallpaper"),
        (calendar_view, lambda: calendar_view.render(),
         icons.CALENDAR_MONTH_OUTLINED, icons.CALENDAR_MONTH, "Calendar"),
        (documents_view, lambda: documents_view.render(),
         icons.FOLDER_SHARED_OUTLINED, icons.FOLDER_SHARED, "Documents"),
        (options_view, lambda: options_view.render(), icons.SETTINGS_OUTLINED, icons.SETTINGS, "Options"),
    ] if t[0] is not None]

    def on_nav_change(e):
        show_tab(e.control.selected_index)

    def show_tab(idx: int):
        rail.selected_index = idx
        for i, tab in enumerate(tabs):
            tab[0].visible = (i == idx)
        tabs[idx][1]()
        page.update()

    def refresh_visible():
        """Re-renders what is on screen after the Telegram assistant changed data (runs in its thread)."""
        try:
            schedule_view.render()
            schedule_view.update_gamification_stats()
            for view, refresh, *_ in tabs[1:]:
                if view.visible:
                    refresh()
            update_desktop_wallpaper()
            page.update()
        except Exception:
            log.exception("refresh after an assistant action failed")

    assistant_tools.on_data_changed(refresh_visible)

    # Navigation Rail with Power-Off button at the bottom
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=160,
        destinations=[ft.NavigationRailDestination(icon=icon, selected_icon=selected, label=label)
                      for _, _, icon, selected, label in tabs],
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

    # Keyboard shortcuts for the Schedule grid (1-4 mark, 0 clear, arrows move)
    def on_keyboard(e: ft.KeyboardEvent):
        try:
            schedule_view.handle_key(e)
        except Exception:
            log.exception("keyboard shortcut failed")

    page.on_keyboard_event = on_keyboard

    page.add(
        ft.Row([rail, ft.VerticalDivider(width=1), *[t[0] for t in tabs]], expand=True)
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
            if calendar_view:
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

    def doc_reminder_text(doc, stage):
        exp = date.fromisoformat(doc["expiration_date"])
        if stage == "due":
            return f"'{doc['title']}' " + ("expires today." if doc["days_left"] == 0 else
                                          f"expired on {exp:%d/%m/%Y}.") + " Renew it when you can."
        if stage == "week":
            return f"'{doc['title']}' expires in {doc['days_left']} days ({exp:%d/%m/%Y})."
        return f"'{doc['title']}' expires on {exp:%d/%m/%Y} — time to plan the renewal."

    assistant.start()  # Telegram (only when turned on in Options and a token is saved)
    notifier = Notifier(assistant, checkin_time=schedule_reminder_time)

    def reminder_loop():
        last_checked_day = date.today()
        last_checked_hour = datetime.now().hour
        next_doc_check = time.monotonic() + 60  # shortly after startup, then hourly

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
                    if calendar_view:
                        calendar_view.render()
                    update_desktop_wallpaper()
                    page.update()

                # 2. Hourly Wallpaper Refresh
                elif now.hour != last_checked_hour:
                    last_checked_hour = now.hour
                    update_desktop_wallpaper()
                    if study_view:
                        ai_review.retry_pending(on_done=study_view._ai_done)  # queued/failed AI review packs

                # 3. Nightly check-in reminder (once a day, only if something is still unmarked)
                remind_at = schedule_reminder_time()
                if remind_at and now.strftime("%H:%M") >= remind_at and                         db.get_hud_settings().get(SETTING_REMINDED) != today_str:
                    db.set_hud_setting(SETTING_REMINDED, today_str)
                    left = db.count_unmarked_today()
                    if left:
                        show_tab(0)  # the tracker opens straight on the Schedule
                        try:
                            tray_icon_instance.notify(
                                f"{left} habit{'s' if left != 1 else ''} still unmarked today.",
                                "Daily check-in")
                        except Exception:
                            log.exception("check-in notification failed")

                # 4. Documents: renewal quests + tray reminders at milestones (08:00-22:00)
                if time.monotonic() >= next_doc_check:
                    next_doc_check = time.monotonic() + 3600
                    if documents_view and db.sync_renewal_quests() and todo_view:
                        todo_view.render()
                    if wallpaper_view and any(b["id"] == "insight" and b["on"] for b in get_hud_blocks()):
                        ai_insight.ensure_today(on_ready=update_desktop_wallpaper)  # once a day, background
                    if documents_view and 8 <= now.hour < 22:
                        for doc, stage in db.get_doc_notifications():
                            try:
                                tray_icon_instance.notify(doc_reminder_text(doc, stage), "Document reminder")
                                db.mark_doc_notified(doc["id"], stage)
                            except Exception:
                                log.exception("document notification failed")

                # 5. Telegram assistant: briefing, reminders, check-in, achievements (no-op when off)
                notifier.tick(now)

                # 6. Calendar reminders (each event has its own lead time) and start alarms
                if not calendar_view:
                    continue
                tomorrow = today + timedelta(days=1)
                done = db.get_completed_events(today_str, tomorrow.isoformat())
                for day_events in db.get_events_between(today, tomorrow).values():
                    for occ in day_events:
                        key = (occ["id"], occ["date"])
                        if key in done:
                            continue
                        title = occ["title"]
                        start = db.occurrence_start(occ)

                        # a) tray notification at the reminder time (no focus stealing)
                        remind_at = db.reminder_time(occ)
                        if remind_at is not None:
                            window_end = remind_at + timedelta(hours=2) if occ["all_day"] else start
                            if remind_at <= now < window_end and key + ("remind",) not in NOTIFIED_ALARMS:
                                NOTIFIED_ALARMS.add(key + ("remind",))
                                if occ["all_day"]:
                                    when = "today (all day)" if start.date() == today else "tomorrow (all day)"
                                else:
                                    mins = int((start - now).total_seconds() // 60) + 1
                                    when = f"at {start:%H:%M} (in {mins} min)" if mins <= 90 else f"at {start:%H:%M}"
                                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                                try:
                                    tray_icon_instance.notify(f"'{title}' {when}", "Upcoming appointment")
                                except Exception:
                                    log.exception("tray notification failed")

                        # b) alarm dialog when a timed event starts (up to 30 min late, e.g. after sleep)
                        if not occ["all_day"] and start <= now <= start + timedelta(minutes=30):
                            if key + ("start",) not in NOTIFIED_ALARMS:
                                NOTIFIED_ALARMS.add(key + ("start",))
                                NOTIFIED_ALARMS.add(key + ("remind",))
                                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                                restore_window_from_tray(page)
                                show_alarm_dialog(
                                    "🚨 Event Starting NOW!",
                                    f"'{title}' starts now ({start:%H:%M})!",
                                    occ["id"], occ["date"]
                                )
            except Exception:
                log.exception("reminder loop failed")

    threading.Thread(target=reminder_loop, daemon=True).start()

ft.run(main)