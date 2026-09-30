#!/usr/bin/env python3
"""
Aplica as melhorias (itens 1 a 5 da revisão) nos arquivos do projeto.

Uso (dentro da pasta do projeto, com a venv ativada):
    python apply_patches.py

- Idempotente: pode rodar mais de uma vez, o que já foi aplicado é ignorado.
- Cria <arquivo>.bak antes de alterar qualquer arquivo.
- Se algum trecho-âncora não for encontrado em um arquivo, NADA é gravado
  naquele arquivo e o motivo é mostrado (arquivo diferente do esperado).
- Preserva quebras de linha (CRLF/LF).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class P:
    """Um patch. old/new literais, ou regex (new usa \\g<1>)."""

    def __init__(self, old, new, count=1, regex=False, done=None, desc=""):
        self.old, self.new, self.count = old, new, count
        self.regex, self.done, self.desc = regex, done, desc

    def is_done(self, text):
        if self.done is not None:
            return self.done in text
        if self.regex:
            return False
        if self.old in self.new:
            return self.new in text
        return self.old not in text

    def apply(self, text):
        if self.regex:
            out, n = re.subn(self.old, self.new, text)
        else:
            n = text.count(self.old)
            out = text.replace(self.old, self.new)
        return out, n


class Append:
    def __init__(self, marker, block, desc=""):
        self.marker, self.block, self.desc = marker, block, desc

    def is_done(self, text):
        return self.marker in text

    def apply(self, text):
        return text.rstrip("\n") + "\n" + self.block, 1

    count = 1


# --------------------------------------------------------------------------
# constants.py
# --------------------------------------------------------------------------
CONSTANTS = [
    P(
        "QUEST_BONUS_XP = 20",
        """# XP awarded per source (single source of truth, used by database.py and the views)
XP_QUEST = 15
XP_STUDY = 15
XP_EVENT = 10
XP_NOTE_PROGRESS = 2.0
QUEST_BONUS_XP = XP_QUEST  # alias kept for todo_view

# Daily score thresholds (0-10 scale), shared by streak, table colors and charts
SCORE_PASSING = 7.0
SCORE_GREEN = SCORE_PASSING
SCORE_ORANGE = 5.0""",
        done="XP_QUEST = 15",
        desc="XP e limiares centralizados",
    ),
]

# --------------------------------------------------------------------------
# database.py
# --------------------------------------------------------------------------
DB_APPEND = '''
# --- Manual quest status (quests without subquests) ---
def set_task_manual_status(task_id: int, complete: bool):
    """Completes / reopens a quest that has no subquests."""
    if get_subtasks(task_id):
        return  # progress is driven by the subquests
    year, week, _ = get_current_week_info()
    update_task_status(task_id, "Complete" if complete else "Planning", year, week)

# --- Automatic daily backup with rotation ---
def backup_db(keep: int = 14):
    """Creates one consistent backup per day. Set GAMIFICATION_BACKUP_DIR to also
    copy it to another folder (e.g. OneDrive / Google Drive)."""
    src = Path(get_db_path())
    if not src.exists():
        return None

    dst_dir = src.parent / "backups"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"gamification_{date.today():%Y%m%d}.db"
    if dst.exists():
        return str(dst)

    tmp = dst.with_suffix(".tmp")
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(tmp))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    tmp.replace(dst)

    for old in sorted(dst_dir.glob("gamification_*.db"))[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass

    extra = os.getenv("GAMIFICATION_BACKUP_DIR")
    if extra and Path(extra).is_dir():
        try:
            shutil.copy2(dst, Path(extra) / dst.name)
        except OSError:
            pass
    return str(dst)
'''

DATABASE = [
    P("import sqlite3, os, csv, json\n", "import sqlite3, os, csv, json, shutil\n"),
    P(
        "from constants import get_rank_title\n",
        "from constants import get_rank_title, XP_QUEST, XP_STUDY, XP_EVENT, XP_NOTE_PROGRESS, SCORE_PASSING\n",
    ),
    P(
        "    return sqlite3.connect(get_db_path())",
        "    return sqlite3.connect(get_db_path(), timeout=10)",
        desc="timeout (o wallpaper agora roda em outra thread)",
    ),
    P(
        "    # 1. Base Tables\n",
        '''    conn.execute("PRAGMA journal_mode=WAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Routine',
            is_negative INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    # 1. Base Tables
''',
        done="CREATE TABLE IF NOT EXISTS activities",
        desc="1.1 tabela activities + WAL",
    ),
    P("quest_xp = (cursor.fetchone()[0] or 0) * 15.0", "quest_xp = (cursor.fetchone()[0] or 0) * XP_QUEST"),
    P("study_xp = (cursor.fetchone()[0] or 0) * 15.0", "study_xp = (cursor.fetchone()[0] or 0) * XP_STUDY"),
    P("event_xp = (cursor.fetchone()[0] or 0) * 10.0", "event_xp = (cursor.fetchone()[0] or 0) * XP_EVENT"),
    P("xp_gained = 2.0", "xp_gained = XP_NOTE_PROGRESS"),
    P("if date_scores.get(today, 0) < 7.0:", "if date_scores.get(today, 0) < SCORE_PASSING:"),
    P("if avg >= 7.0:", "if avg >= SCORE_PASSING:"),
    P(
        r"(def update_task_status\(task_id: int, status: str, year: int, week: int\):\s+"
        r"conn = get_connection\(\)\s+cursor = conn\.cursor\(\))",
        r"""\g<1>
    cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    _row = cursor.fetchone()
    if _row and _row[0] == status:
        conn.close()
        return  # nothing changed: keeps the original completed_week""",
        regex=True,
        done="if _row and _row[0] == status:",
        desc="1.3b completed_week nao e mais sobrescrito",
    ),
    P(
        r"subtasks = get_subtasks\(task_id\)\s+if not subtasks:\s+return",
        """subtasks = get_subtasks(task_id)
    if not subtasks:
        update_task_status(task_id, "Planning", year, week)
        return""",
        regex=True,
        done='update_task_status(task_id, "Planning", year, week)\n        return',
        desc="1.3 apagar a ultima subtask nao deixa a quest 'Complete'",
    ),
    P(
        '        update_task_status(task_id, "In Progress", year, week)',
        '        update_task_status(task_id, "In Progress" if progress_pct > 0 else "Planning", year, week)',
    ),
    Append("def set_task_manual_status", DB_APPEND, desc="status manual + backup"),
]

# --------------------------------------------------------------------------
# wallpaper.py
# --------------------------------------------------------------------------
WALLPAPER_APPEND = '''
# --- Debounced / background wallpaper refresh ---
_timer = None
_timer_lock = threading.Lock()
_render_lock = threading.Lock()


def _run_update():
    with _render_lock:
        update_desktop_wallpaper()


def request_wallpaper_update(delay: float = 2.0):
    """Schedules a wallpaper refresh in a background thread. Calls made within
    `delay` seconds are merged into a single render (the UI never blocks)."""
    global _timer
    with _timer_lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay, _run_update)
        _timer.daemon = True
        _timer.start()


def flush_wallpaper_update():
    """Runs a pending refresh immediately (call before quitting)."""
    global _timer
    with _timer_lock:
        pending = _timer is not None and _timer.is_alive()
        if _timer is not None:
            _timer.cancel()
        _timer = None
    if pending:
        _run_update()
'''

WALLPAPER = [
    P("import textwrap\n", "import textwrap\nimport threading\n"),
    P(
        "import database as db\n",
        "import database as db\nfrom constants import SCORE_PASSING, SCORE_ORANGE\n",
    ),
    P(
        "def get_font(size: int, bold: bool = False):",
        '''def _enable_dpi_awareness():
    """Without this, GetSystemMetrics returns a scaled (blurry) resolution."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_dpi_awareness()
_BASE_CACHE = {}


def get_font(size: int, bold: bool = False):''',
        done="_enable_dpi_awareness()",
        desc="3.2 DPI awareness + cache",
    ),
    P(
        'candidate = Path(f"base_wallpaper{ext}")',
        'candidate = Path(__file__).resolve().parent / f"base_wallpaper{ext}"',
        desc="3.2 caminho absoluto",
    ),
    P(
        r'img = Image\.open\(candidate\)\.convert\("RGBA"\)\s+'
        r"return img\.resize\(\(screen_w, screen_h\), Image\.Resampling\.LANCZOS\)",
        """key = (str(candidate), candidate.stat().st_mtime, screen_w, screen_h)
                if _BASE_CACHE.get("key") != key:
                    img = Image.open(candidate).convert("RGBA")
                    _BASE_CACHE["img"] = img.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
                    _BASE_CACHE["key"] = key
                return _BASE_CACHE["img"]""",
        regex=True,
        done='_BASE_CACHE.get("key")',
        desc="3.1 cache da imagem base redimensionada",
    ),
    P("today_avg >= 7.0", "today_avg >= SCORE_PASSING", count=2),
    P("today_avg >= 5.0", "today_avg >= SCORE_ORANGE", count=2),
    Append("def request_wallpaper_update", WALLPAPER_APPEND, desc="3.1 debounce em thread"),
]

# --------------------------------------------------------------------------
# views
# --------------------------------------------------------------------------
ALIAS = P(
    "from wallpaper import update_desktop_wallpaper\n",
    "from wallpaper import request_wallpaper_update as update_desktop_wallpaper\n",
    desc="3.1 views usam a versao debounced",
)

SCHEDULE = [
    ALIAS,
    P("from constants import (\n", "from constants import (\n    SCORE_GREEN,\n    SCORE_ORANGE,\n",
      done="    SCORE_GREEN,\n"),
    P("if avg >= 8.0:", "if avg >= SCORE_GREEN:"),
    P("elif avg >= 5.0:", "elif avg >= SCORE_ORANGE:"),
]

GRAPHS = [
    P("from constants import DAY_NAMES\n", "from constants import DAY_NAMES, SCORE_PASSING, SCORE_GREEN, SCORE_ORANGE\n"),
    P("avg >= 7.5", "avg >= SCORE_GREEN"),
    P("avg >= 4.5", "avg >= SCORE_ORANGE"),
    P("week_avg >= 7.0", "week_avg >= SCORE_PASSING"),
]

CALENDAR = [ALIAS]
DOCUMENTS = [ALIAS]

WALLPAPER_VIEW = [
    P("from wallpaper import update_desktop_wallpaper, COLOR_PALETTES",
      "from wallpaper import request_wallpaper_update, COLOR_PALETTES"),
    P("        update_desktop_wallpaper()\n", "        request_wallpaper_update(delay=0)\n"),
]

TODO = [
    ALIAS,
    P("self.expanded_tasks = set()", "self.expanded_tasks = set()\n        self.notes_drafts = {}",
      done="self.notes_drafts = {}"),
    P(
        "    def toggle_expand(self, task_id):",
        '''    def on_toggle_quest(self, task_id: int, complete: bool):
        db.set_task_manual_status(task_id, complete)
        self.render()
        update_desktop_wallpaper()

    def toggle_expand(self, task_id):''',
        done="def on_toggle_quest",
        desc="1.3 quest sem subtasks pode ser concluida",
    ),
    P(
        r"ft\.Icon\(\s+ft\.Icons\.CHECK_CIRCLE if is_complete else ft\.Icons\.RADIO_BUTTON_UNCHECKED,\s+"
        r"color=ft\.Colors\.GREEN_ACCENT if is_complete else ft\.Colors\.CYAN_ACCENT,\s+size=20\s+\)",
        """(ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE if is_complete else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        icon_color=ft.Colors.GREEN_ACCENT if is_complete else ft.Colors.CYAN_ACCENT,
                        icon_size=20,
                        tooltip="Reopen quest" if is_complete else "Mark quest as complete",
                        on_click=lambda e, tid=task_id, done=is_complete: self.on_toggle_quest(tid, not done)
                    ) if not subtasks else ft.Icon(
                        ft.Icons.CHECK_CIRCLE if is_complete else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=ft.Colors.GREEN_ACCENT if is_complete else ft.Colors.CYAN_ACCENT,
                        size=20
                    ))""",
        regex=True,
        done="self.on_toggle_quest(tid, not done)",
    ),
    P("value=notes,", "value=self.notes_drafts.get(task_id, notes),", done="self.notes_drafts.get(task_id, notes)",
      desc="1.2 rascunho das notas sobrevive a re-render"),
    P(
        'save_btn = ft.Button(content="Save Notes", icon=ft.Icons.SAVE)',
        '''def _on_notes_change(e, tid=task_id):
                    self.notes_drafts[tid] = e.control.value

                def _on_notes_blur(e, tid=task_id):
                    db.save_task_notes_with_progress(tid, e.control.value)
                    self.notes_drafts.pop(tid, None)

                notes_field.on_change = _on_notes_change
                notes_field.on_blur = _on_notes_blur
                save_btn = ft.Button(content="Save Notes", icon=ft.Icons.SAVE)''',
        done="notes_field.on_blur = _on_notes_blur",
        desc="1.2 autosave das notas ao sair do campo",
    ),
    P(
        "xp_earned = db.save_task_notes_with_progress(task_id, notes_val)",
        "xp_earned = db.save_task_notes_with_progress(task_id, notes_val)\n        self.notes_drafts.pop(task_id, None)",
        done="self.notes_drafts.pop(task_id, None)",
    ),
]

STUDY = [
    P('"Mastered (+30 XP)"', "MASTERED_LABEL", count=2, desc="1.4 rotulo de XP vem de constants"),
    P(
        "from wallpaper import update_desktop_wallpaper\n",
        "from wallpaper import request_wallpaper_update as update_desktop_wallpaper\n"
        "from constants import XP_STUDY\n\n"
        'MASTERED_LABEL = f"Mastered (+{XP_STUDY} XP)"\n',
        done="MASTERED_LABEL = ",
    ),
    P(
        "self.editor_container = ft.Column(",
        """self._loaded_session_id = None
        self._snapshot = None
        for _f in (self.topic_title_input, self.eli5_input, self.code_input,
                   self.break_input, self.recall_input):
            _f.on_blur = lambda e: self.save_current()
        for _dd in (self.source_dropdown, self.status_dropdown):
            _dd.on_select = lambda e: self.save_current()

        self.editor_container = ft.Column(""",
        done="self._snapshot = None",
        desc="1.2 autosave ao sair do campo",
    ),
    P(
        "    def select_chapter(self, session_id: int):",
        '''    def _current_values(self):
        clean_status = "Mastered" if "Mastered" in (self.status_dropdown.value or "") else "In Progress"
        return (
            (self.topic_title_input.value or "").strip() or "Untitled",
            self.source_dropdown.value,
            self.eli5_input.value or "",
            self.code_input.value or "",
            self.break_input.value or "",
            self.recall_input.value or "",
            clean_status,
        )

    def save_current(self):
        """Autosaves the open chapter if anything changed. Returns True if saved."""
        sid = self.selected_session_id
        if sid is None or self._loaded_session_id != sid or self._snapshot is None:
            return False
        values = self._current_values()
        if values == self._snapshot:
            return False
        topic, source, eli5, code, break_t, recall, status = values
        db.update_study_session(
            session_id=sid, topic=topic, source=source, eli5=eli5, code_sandbox=code,
            break_test=break_t, recall_questions=recall, status=status
        )
        self._snapshot = values
        update_desktop_wallpaper()
        return True

    def select_chapter(self, session_id: int):''',
        done="def save_current(self):",
    ),
    P(
        '"""Immediately loads editor AND updates sidebar highlight."""\n        self.selected_session_id = session_id',
        '"""Immediately loads editor AND updates sidebar highlight."""\n        self.save_current()  # never lose what was typed in the previous chapter\n        self.selected_session_id = session_id',
        done="self.save_current()  # never lose",
    ),
    P(
        "def refresh_list(self):\n        sessions = db.get_study_sessions()",
        "def refresh_list(self):\n        self.save_current()  # pending edits are saved before reloading from the DB\n        sessions = db.get_study_sessions()",
        done="self.save_current()  # pending edits",
    ),
    P(
        "self.recall_input.value = recall if (recall and recall.strip()) else DEFAULT_RECALL",
        "self.recall_input.value = recall if (recall and recall.strip()) else DEFAULT_RECALL\n"
        "        self._loaded_session_id = session_id\n"
        "        self._snapshot = self._current_values()",
        done="self._loaded_session_id = session_id",
    ),
    P(
        r'e\.control\.content = "Saved!"\s+self\.render_sidebar_tiles\(\)',
        'e.control.content = "Saved!"\n            self._snapshot = self._current_values()\n            self.render_sidebar_tiles()',
        regex=True,
        done='"Saved!"\n            self._snapshot',
    ),
]

# --------------------------------------------------------------------------
# main.py
# --------------------------------------------------------------------------
MUTEX_BLOCK = r'''import sys as _sys
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
'''

MAIN = [
    P(
        "from wallpaper import update_desktop_wallpaper\n",
        "from wallpaper import request_wallpaper_update as update_desktop_wallpaper, flush_wallpaper_update\n",
    ),
    P(
        "import flet as ft\nimport database as db\n",
        MUTEX_BLOCK,
        done="DailyGamificationTracker",
        desc="1.7 instancia unica",
    ),
    P(
        "    db.init_db()",
        """    try:
        db.backup_db()  # backup BEFORE migrations touch the database
    except Exception:
        pass  # a failed backup must never stop the app from starting

    db.init_db()""",
        done="db.backup_db()",
        desc="2.5 backup diario",
    ),
    P(
        r"global tray_icon_instance\s+try:\s+if tray_icon_instance:",
        """global tray_icon_instance
        try:
            flush_wallpaper_update()  # do not lose a pending wallpaper refresh
        except Exception:
            pass
        try:
            if tray_icon_instance:""",
        regex=True,
        done="flush_wallpaper_update()",
    ),
    P(
        r"(def force_refresh_wallpaper\(icon, item\):\s+)update_desktop_wallpaper\(\)",
        r"\g<1>update_desktop_wallpaper(delay=0)",
        regex=True,
        done="update_desktop_wallpaper(delay=0)",
    ),
]

FILES = {
    "constants.py": CONSTANTS,
    "database.py": DATABASE,
    "wallpaper.py": WALLPAPER,
    "schedule_view.py": SCHEDULE,
    "graphs_view.py": GRAPHS,
    "calendar_view.py": CALENDAR,
    "documents_view.py": DOCUMENTS,
    "wallpaper_view.py": WALLPAPER_VIEW,
    "todo_view.py": TODO,
    "study_view.py": STUDY,
    "main.py": MAIN,
}


def patch_file(name, patches):
    path = ROOT / name
    if not path.exists():
        print(f"[FALTA] {name}: arquivo nao encontrado em {ROOT}")
        return False

    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")

    problems, applied, skipped = [], 0, 0
    for i, p in enumerate(patches, 1):
        if p.is_done(text):
            skipped += 1
            continue
        new_text, n = p.apply(text)
        if n != p.count:
            snippet = (p.old if hasattr(p, "old") else p.marker)[:70].replace("\n", "\\n")
            problems.append(f"patch #{i} (achou {n}x, esperado {p.count}x): {snippet}")
            continue
        text = new_text
        applied += 1

    if problems:
        print(f"[ERRO ] {name}: nada foi gravado.")
        for pr in problems:
            print("        -", pr)
        return False

    if applied:
        bak = path.with_name(path.name + ".bak")
        if not bak.exists():
            bak.write_bytes(raw.encode("utf-8"))
        out = text.replace("\n", "\r\n") if crlf else text
        path.write_bytes(out.encode("utf-8"))
        print(f"[ OK  ] {name}: {applied} alteracao(oes) aplicada(s), {skipped} ja existente(s)")
    else:
        print(f"[ --  ] {name}: ja estava atualizado")
    return True


def pin_requirements():
    """Fixes dependency versions to what is installed in the current venv."""
    path = ROOT / "requirements.txt"
    if not path.exists():
        return
    from importlib import metadata

    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if all("==" in l for l in lines):
        print("[ --  ] requirements.txt: ja esta com versoes fixas")
        return
    out = []
    for l in lines:
        if "==" in l or l.startswith("#"):
            out.append(l)
            continue
        try:
            out.append(f"{l}=={metadata.version(l)}")
        except metadata.PackageNotFoundError:
            print(f"        ! {l} nao esta instalado nesta venv; mantido sem versao")
            out.append(l)
    bak = path.with_name("requirements.txt.bak")
    if not bak.exists():
        bak.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("[ OK  ] requirements.txt: versoes fixadas ->", ", ".join(out))


def main():
    ok = True
    for name, patches in FILES.items():
        ok &= patch_file(name, patches)
    pin_requirements()
    print("\nConcluido." if ok else "\nConcluido COM PENDENCIAS (veja [ERRO ]/[FALTA] acima).")
    print("Lembrete: substitua tambem o updater.py pelo novo e faca commit das mudancas.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())