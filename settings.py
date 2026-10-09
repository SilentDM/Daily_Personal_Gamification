"""App options (stored in hud_settings): one place for defaults and typed access.

Secrets (Gemini key, Telegram bot token) are NOT here: they live in the Windows Credential Manager.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, time as dtime
from pathlib import Path

import database as db

# Optional tabs (Schedule is the core and always on). A disabled tab is not built at all and its
# background work (reminders, renewal quests, wallpaper refresh...) stops too.
OPTIONAL_TABS = {
    "graphs": "Graphs",
    "quests": "Quests",
    "study": "Study",
    "wallpaper": "Wallpaper",
    "calendar": "Calendar",
    "documents": "Documents",
}
REPLY_MODES = {"text": "Text", "voice": "Voice", "both": "Voice + text"}
VOICES = {"female": "Female", "male": "Male"}

DEFAULTS = {
    "enabled_tabs": json.dumps(list(OPTIONAL_TABS)),
    "passing_score": "7.0",
    "rest_limit": "3",
    "close_to_tray": "true",
    "auto_update": "true",
    "backup_dir": "",
    "quiet_enabled": "true",
    "quiet_start": "22:30",
    "quiet_end": "07:00",
    # Telegram assistant
    "tg_enabled": "false",
    "tg_chat_id": "",
    "tg_reply_mode": "text",
    "tg_voice": "female",
    "tg_briefing": "07:30",          # "" = off
    "tg_calendar": "true",
    "tg_documents": "true",
    "tg_reviews": "true",
    "tg_checkin": "true",
    "tg_achievements": "true",
}


# keys where "" is a real choice (off / not set) rather than "use the default"
_EMPTY_ALLOWED = {"tg_briefing", "backup_dir", "tg_chat_id"}


def get(key: str) -> str:
    value = db.get_hud_settings().get(key)
    if value is None or (value == "" and key not in _EMPTY_ALLOWED):
        return DEFAULTS.get(key, "")
    return value


def set(key: str, value) -> None:  # noqa: A001 - mirrors get()
    if isinstance(value, bool):
        value = "true" if value else "false"
    db.set_hud_setting(key, str(value))


def flag(key: str) -> bool:
    return get(key) == "true"


# ------------------------------------------------------------------ tabs
def enabled_tabs() -> list:
    try:
        tabs = [t for t in json.loads(get("enabled_tabs")) if t in OPTIONAL_TABS]
    except (ValueError, TypeError):
        tabs = list(OPTIONAL_TABS)
    return tabs


def tab_enabled(tab: str) -> bool:
    return tab == "schedule" or tab in enabled_tabs()


def set_tab_enabled(tab: str, on: bool):
    tabs = [t for t in enabled_tabs() if t != tab]
    if on:
        tabs.append(tab)
    set("enabled_tabs", json.dumps([t for t in OPTIONAL_TABS if t in tabs]))


# ------------------------------------------------------------------ quiet hours
def _parse_hhmm(text: str, fallback: str) -> dtime:
    try:
        return datetime.strptime(text, "%H:%M").time()
    except (TypeError, ValueError):
        return datetime.strptime(fallback, "%H:%M").time()


def in_quiet_hours(now: datetime = None) -> bool:
    """True inside the quiet window (it may cross midnight, e.g. 22:30 -> 07:00)."""
    if not flag("quiet_enabled"):
        return False
    now = now or datetime.now()
    start = _parse_hhmm(get("quiet_start"), DEFAULTS["quiet_start"])
    end = _parse_hhmm(get("quiet_end"), DEFAULTS["quiet_end"])
    t = now.time()
    if start == end:
        return False
    return (start <= t or t < end) if start > end else (start <= t < end)


# ------------------------------------------------------------------ backups
def backup_dir() -> str:
    return get("backup_dir") or os.getenv("GAMIFICATION_BACKUP_DIR", "")


# ------------------------------------------------------------------ start with Windows
def _startup_shortcut() -> Path:
    appdata = os.getenv("APPDATA") or str(Path.home())
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / \
        "Personal Gamification Tracker.lnk"


def starts_with_windows() -> bool:
    return _startup_shortcut().exists()


def set_start_with_windows(on: bool) -> str:
    """Creates/removes a Startup shortcut that runs the app with pythonw (no console). Returns '' or an error."""
    link = _startup_shortcut()
    if not on:
        try:
            link.unlink(missing_ok=True)
            return ""
        except OSError as exc:
            return str(exc)
    project = Path(__file__).resolve().parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = pythonw if pythonw.exists() else Path(sys.executable)
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
        "$s.TargetPath=$env:TARGET;$s.Arguments='\"' + $env:MAINPY + '\"';"
        "$s.WorkingDirectory=$env:WORKDIR;$s.Save()"
    )
    env = {**os.environ, "LNK": str(link), "TARGET": str(target), "MAINPY": str(project / "main.py"),
           "WORKDIR": str(project)}
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True,
                                text=True, timeout=20, creationflags=0x08000000 if sys.platform == "win32" else 0)
        return "" if link.exists() else (result.stderr.strip() or "Could not create the shortcut")
    except Exception as exc:
        return str(exc)
