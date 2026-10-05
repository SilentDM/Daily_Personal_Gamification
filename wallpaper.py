"""Desktop wallpaper HUD: a modular card (blocks you turn on/off and order) drawn over a background.

Settings live in hud_settings (see SETTING_* and BLOCKS). The original wallpaper is copied before the
first apply so the HUD can be paused and the user's wallpaper restored.
"""
import ctypes
import io
import json
import logging
import shutil
import threading
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import database as db
from constants import SCORE_PASSING, SCORE_ORANGE

log = logging.getLogger("gamification")

COLOR_PALETTES = {
    "Amber / Gold": {"border": (255, 180, 0, 180), "header": (255, 195, 0, 255), "bar": (255, 180, 0, 255)},
    "Cyan": {"border": (0, 220, 255, 180), "header": (0, 225, 255, 255), "bar": (0, 220, 255, 255)},
    "Neon Green": {"border": (0, 255, 150, 180), "header": (0, 255, 150, 255), "bar": (0, 255, 150, 255)},
    "Purple": {"border": (190, 100, 255, 180), "header": (200, 120, 255, 255), "bar": (190, 100, 255, 255)},
    "Crimson": {"border": (255, 75, 75, 180), "header": (255, 90, 90, 255), "bar": (255, 75, 75, 255)},
}
POSITIONS = ["Top-Right", "Top-Left", "Bottom-Right", "Bottom-Left", "Top-Center", "Center"]
BG_BLACK = "Pure Black (Minimalist)"
BG_PROJECT = "Custom Image (base_wallpaper.jpg)"
BG_FOLDER = "Rotate images from a folder"
BG_MODES = [BG_BLACK, BG_PROJECT, BG_FOLDER]
SIZES = {"Compact": 0.85, "Normal": 1.0, "Large": 1.25}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# block id -> label (the order here is the default order)
BLOCKS = {
    "status": "Streak & today's score",
    "xp": "Level & XP bar",
    "insight": "Insight of the day (Gemini)",
    "quests": "Active quests",
    "studies": "Studies & reviews due",
    "calendar": "Upcoming calendar",
    "documents": "Document alerts",
}
_OLD_FLAGS = {"status": "show_score", "xp": "show_xp_bar", "quests": "show_quests", "studies": "show_studies",
              "calendar": "show_calendar"}

SETTING_BLOCKS = "hud_blocks"
SETTING_COLUMNS = "hud_columns"
SETTING_SIZE = "hud_size"
SETTING_PAUSED = "hud_paused"
SETTING_ORIGINAL = "hud_original_wallpaper"
SETTING_FOLDER = "bg_folder"
SETTING_ROTATION = "bg_rotation_offset"

SPI_SETDESKWALLPAPER = 20
SPI_GETDESKWALLPAPER = 0x0073


def _enable_dpi_awareness():
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


def _data_dir() -> Path:
    return Path(db.get_db_path()).parent


def hud_path() -> Path:
    return _data_dir() / "current_wallpaper_hud.bmp"


# ------------------------------------------------------------------ settings
def get_blocks(settings=None):
    """Ordered [{"id", "on"}]; migrates the old show_* flags and adds blocks introduced later."""
    settings = settings or db.get_hud_settings()
    blocks = []
    try:
        blocks = [b for b in json.loads(settings.get(SETTING_BLOCKS) or "[]") if b.get("id") in BLOCKS]
    except (ValueError, TypeError):
        blocks = []
    if not blocks:
        blocks = [{"id": bid, "on": settings.get(_OLD_FLAGS[bid], "true") == "true" if bid in _OLD_FLAGS else
                   (bid == "documents")} for bid in BLOCKS]
    known = {b["id"] for b in blocks}
    blocks += [{"id": bid, "on": False} for bid in BLOCKS if bid not in known]
    return blocks


def save_blocks(blocks):
    db.set_hud_setting(SETTING_BLOCKS, json.dumps([{"id": b["id"], "on": bool(b["on"])} for b in blocks]))


def is_paused() -> bool:
    return db.get_hud_settings().get(SETTING_PAUSED, "false") == "true"


# ------------------------------------------------------------------ fonts / screen
def get_font(size: int, bold: bool = False):
    font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
    font_path = Path("C:/Windows/Fonts") / font_name
    if font_path.exists():
        return ImageFont.truetype(str(font_path), max(8, int(size)))
    return ImageFont.load_default()


def get_screen_resolution():
    try:
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        w = h = 0
    return w if w > 0 else 1920, h if h > 0 else 1080


# ------------------------------------------------------------------ background
def list_folder_images(folder: str):
    try:
        p = Path(folder)
        return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS) if folder and p.is_dir() else []
    except OSError:
        return []


def current_folder_image(settings=None, on: date = None):
    """The folder image for today: one per day, in name order; the offset lets the user skip ahead."""
    settings = settings or db.get_hud_settings()
    images = list_folder_images(settings.get(SETTING_FOLDER, ""))
    if not images:
        return None
    try:
        offset = int(settings.get(SETTING_ROTATION, "0") or 0)
    except ValueError:
        offset = 0
    return images[((on or date.today()).toordinal() + offset) % len(images)]


def _background_source(settings):
    mode = settings.get("bg_mode", BG_PROJECT)
    if mode == BG_FOLDER:
        return current_folder_image(settings)
    if mode == BG_PROJECT:
        for ext in (".jpg", ".png", ".jpeg"):
            candidate = Path(__file__).resolve().parent / f"base_wallpaper{ext}"
            if candidate.exists():
                return candidate
    return None


def get_base_wallpaper(settings, screen_w: int, screen_h: int):
    """The background, scaled to *cover* the screen (cropped, never stretched)."""
    src = _background_source(settings)
    if src is not None:
        try:
            key = (str(src), src.stat().st_mtime, screen_w, screen_h)
            if _BASE_CACHE.get("key") != key:
                with Image.open(src) as img:
                    img = ImageOps.exif_transpose(img).convert("RGBA")
                    _BASE_CACHE["img"] = ImageOps.fit(img, (screen_w, screen_h), Image.Resampling.LANCZOS)
                _BASE_CACHE["key"] = key
            return _BASE_CACHE["img"].copy()
        except Exception:
            log.exception("Could not load wallpaper background %s", src)
    return Image.new("RGBA", (screen_w, screen_h), (12, 14, 18, 255))


# ------------------------------------------------------------------ data
def _gather():
    """Everything the blocks need, each part isolated so one failure doesn't blank the HUD."""
    data = {}

    def safe(key, fn, default=None):
        try:
            data[key] = fn()
        except Exception:
            log.exception("HUD data '%s' failed", key)
            data[key] = default

    safe("streak", db.get_current_streak, 0)
    safe("xp", db.get_user_xp_and_level, (0.0, 1, 0.0, "Novice"))

    def today_avg():
        year, week, today_idx = db.get_current_week_info()
        logs = db.get_current_week_logs(year, week)
        active = {a[0] for a in db.get_activities()}
        scores = [s for (aid, d), (_, s) in logs.items() if d == today_idx and s is not None and aid in active]
        return (sum(scores) / len(scores)) if scores else None

    safe("today_avg", today_avg)
    safe("quests", lambda: [q for q in db.get_quests(statuses=("Active",)) if not q["done_this_period"]][:3], [])
    safe("studies", lambda: [s for s in db.get_study_sessions() if s["status"] in ("Studying", "Reviewing")][:2], [])
    safe("reviews", lambda: db.get_pending_reviews(until=date.today()), [])
    safe("events", lambda: db.get_upcoming_events(limit=3), [])
    safe("documents", lambda: db.get_expiring_documents()[:3], [])

    def insight():
        import ai_insight
        return ai_insight.cached_today()

    safe("insight", insight)
    return data


# ------------------------------------------------------------------ drawing helpers
def _wrap(text: str, font, width: int):
    """Wraps by pixel width (long words are cut)."""
    words, lines, line = (text or "").split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if font.getlength(trial) <= width:
            line = trial
            continue
        if line:
            lines.append(line)
        while font.getlength(word) > width and len(word) > 1:
            cut = len(word)
            while cut > 1 and font.getlength(word[:cut] + "…") > width:
                cut -= 1
            lines.append(word[:cut] + "…")
            word = ""
        line = word
    if line:
        lines.append(line)
    return lines


class _Ctx:
    def __init__(self, scale, accent):
        s = scale
        self.s = s
        self.accent = accent
        self.title = get_font(18 * s, True)
        self.sub = get_font(12 * s, True)
        self.body = get_font(13 * s)
        self.body_bold = get_font(14 * s, True)
        self.small = get_font(11 * s)
        self.line_h = int(22 * s)
        self.pad = int(25 * s)


def _section(ctx, title, color, items, width, bullet=True):
    """A titled list block: (height, draw_fn)."""
    lines = []
    for item in items:
        wrapped = _wrap(item, ctx.body, width - int(14 * ctx.s))
        for i, ln in enumerate(wrapped):
            lines.append(("• " if bullet and i == 0 else ("   " if bullet else "")) + ln)
    head_h = int(32 * ctx.s)
    height = head_h + len(lines) * ctx.line_h + int(6 * ctx.s)

    def draw(d, x, y, w, fill=(240, 240, 240, 255)):
        d.line([x, y + int(4 * ctx.s), x + w, y + int(4 * ctx.s)], fill=(50, 60, 75, 255), width=1)
        d.text((x, y + int(12 * ctx.s)), title, fill=color, font=ctx.sub)
        cy = y + head_h
        for ln in lines:
            d.text((x, cy), ln, fill=fill, font=ctx.body)
            cy += ctx.line_h

    return height, draw


def _block(ctx, bid, data, width):
    """(height, draw_fn) for a block, or None when it has nothing to show."""
    s = ctx.s
    if bid == "status":
        avg = data.get("today_avg")
        if avg is None:
            status, color, txt = "NO ENTRIES YET", (160, 170, 185, 255), "Today: - / 10"
        else:
            status = "PASSING" if avg >= SCORE_PASSING else ("NEUTRAL" if avg >= SCORE_ORANGE else "NEEDS FOCUS")
            color = (0, 255, 180, 255) if avg >= SCORE_PASSING else (
                (255, 180, 0, 255) if avg >= SCORE_ORANGE else (255, 85, 85, 255))
            txt = f"Today: {avg:.1f} / 10"
        streak = data.get("streak") or 0

        def draw(d, x, y, w):
            d.text((x, y), f"STREAK: {streak} day{'s' if streak != 1 else ''}", fill=(255, 175, 40, 255),
                   font=ctx.body_bold)
            right = f"{txt} [{status}]"
            d.text((x + w - ctx.body_bold.getlength(right), y), right, fill=color, font=ctx.body_bold)

        return int(32 * s), draw

    if bid == "xp":
        total_xp, level, xp_in_level, _ = data.get("xp") or (0.0, 1, 0.0, "")

        def draw(d, x, y, w):
            bar_h = max(6, int(8 * s))
            d.rounded_rectangle([x, y + int(4 * s), x + w, y + int(4 * s) + bar_h], radius=bar_h // 2,
                                fill=(40, 45, 55, 255))
            fill_w = int(w * min(1.0, xp_in_level / 10.0))
            if fill_w > 0:
                d.rounded_rectangle([x, y + int(4 * s), x + fill_w, y + int(4 * s) + bar_h], radius=bar_h // 2,
                                    fill=ctx.accent["bar"])
            d.text((x, y + int(18 * s)), f"{xp_in_level:.1f} / 10 XP to Level {min(100, level + 1)} "
                                         f"(Total: {total_xp:.1f}/1000)", fill=(160, 170, 185, 255), font=ctx.small)

        return int(42 * s), draw

    if bid == "insight":
        text = data.get("insight")
        if not text:
            return None
        return _section(ctx, "INSIGHT OF THE DAY:", ctx.accent["header"], [text], width, bullet=False)

    if bid == "quests":
        quests = data.get("quests") or []
        items = [f"{q['title']} ({int(q['progress_pct'])}%)" if q["progress_pct"] > 0 else q["title"] for q in quests]
        return _section(ctx, "ACTIVE QUESTS:", (200, 210, 225, 255), items or ["All quests completed!"], width)

    if bid == "studies":
        items = []
        due = data.get("reviews") or []
        if due:
            items.append(f"REVIEW DUE ({len(due)}): " + ", ".join(r["topic"] for r in due[:2]) +
                         ("..." if len(due) > 2 else ""))
        for st in data.get("studies") or []:
            items.append(f"{st['topic']} -> {st['next_step']}" if st["next_step"] else f"{st['topic']} ({st['source']})")
        return _section(ctx, "STUDIES:", ctx.accent["header"], items or ["No active chapters right now."], width)

    if bid == "calendar":
        events = data.get("events") or []
        if not events:
            return None
        items = []
        for occ in events:
            start = db.occurrence_start(occ)
            when = "All day" if occ["all_day"] else f"{start:%H:%M}"
            items.append(f"[{start:%d-%m} {when}] {occ['title']}")
        return _section(ctx, "UPCOMING CALENDAR:", (255, 200, 100, 255), items, width)

    if bid == "documents":
        docs = data.get("documents") or []
        if not docs:
            return None
        items = [f"{title} [{'EXPIRED ' + str(abs(days)) + 'd ago' if days < 0 else 'expires in ' + str(days) + 'd'}]"
                 for title, _, _, days in docs]
        return _section(ctx, "DOCUMENT ALERTS:", (255, 100, 100, 255), items, width)
    return None


# ------------------------------------------------------------------ composition
def build_hud_image(settings=None, screen=None):
    """The full wallpaper (RGB) with the HUD card; nothing is written or applied."""
    settings = settings or db.get_hud_settings()
    screen_w, screen_h = screen or get_screen_resolution()
    base = get_base_wallpaper(settings, screen_w, screen_h)
    accent = COLOR_PALETTES.get(settings.get("accent_color", "Amber / Gold"), COLOR_PALETTES["Amber / Gold"])
    scale = max(0.6, screen_h / 1080.0) * SIZES.get(settings.get(SETTING_SIZE, "Normal"), 1.0)
    ctx = _Ctx(scale, accent)
    columns = 2 if settings.get(SETTING_COLUMNS, "1") == "2" else 1
    col_w = int(430 * scale)
    gap = int(30 * scale)
    data = _gather()

    rendered = [r for r in (_block(ctx, b["id"], data, col_w) for b in get_blocks(settings) if b["on"]) if r]
    # split in order: the first column takes blocks until it holds about half the height
    cols = [rendered]
    if columns == 2 and len(rendered) > 1:
        total, acc, cut = sum(h for h, _ in rendered), 0, len(rendered)
        for i, (h, _) in enumerate(rendered):
            if acc + h / 2 > total / 2 and i > 0:
                cut = i
                break
            acc += h
        cols = [rendered[:cut], rendered[cut:]]
    used_cols = len([c for c in cols if c])
    header_h = int(72 * scale)
    body_h = max((sum(h for h, _ in c) for c in cols), default=0)
    card_w = ctx.pad * 2 + col_w * max(1, used_cols) + gap * (max(1, used_cols) - 1)
    card_h = header_h + body_h + ctx.pad

    margin_x, margin_y = int(70 * scale), int(60 * scale)
    pos = settings.get("position", "Top-Right")
    if pos == "Top-Left":
        x1, y1 = margin_x, margin_y
    elif pos == "Bottom-Left":
        x1, y1 = margin_x, screen_h - card_h - margin_y
    elif pos == "Bottom-Right":
        x1, y1 = screen_w - card_w - margin_x, screen_h - card_h - margin_y
    elif pos == "Top-Center":
        x1, y1 = (screen_w - card_w) // 2, margin_y
    elif pos == "Center":
        x1, y1 = (screen_w - card_w) // 2, (screen_h - card_h) // 2
    else:
        x1, y1 = screen_w - card_w - margin_x, margin_y

    overlay = Image.new("RGBA", (screen_w, screen_h), (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle([x1, y1, x1 + card_w, y1 + card_h], radius=int(16 * scale), fill=(18, 22, 30, 225),
                        outline=accent["border"], width=max(2, int(2 * scale)))
    total_xp, level, _, rank = data.get("xp") or (0.0, 1, 0.0, "Novice")
    d.text((x1 + ctx.pad, y1 + int(18 * scale)), "DAILY GAMIFICATION HUD", fill=accent["header"], font=ctx.sub)
    d.text((x1 + ctx.pad, y1 + int(38 * scale)), f"Level {level} / 100 • {rank}", fill=(255, 255, 255, 255),
           font=ctx.title)
    for ci, col in enumerate(c for c in cols if c):
        cx = x1 + ctx.pad + ci * (col_w + gap)
        cy = y1 + header_h
        for h, draw in col:
            draw(d, cx, cy, col_w)
            cy += h
    return Image.alpha_composite(base, overlay).convert("RGB")


def render_preview(max_width: int = 960) -> bytes:
    """PNG bytes of the HUD as it would look (scaled down) — never touches the desktop."""
    img = build_hud_image()
    img.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ apply / pause / restore
def _current_wallpaper() -> str:
    buf = ctypes.create_unicode_buffer(520)
    try:
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 520, buf, 0)
    except Exception:
        return ""
    return buf.value


def _set_wallpaper(path: str) -> bool:
    try:
        return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, str(path), 3))
    except Exception:
        log.exception("Could not set the wallpaper")
        return False


def _remember_original():
    """Copies the user's wallpaper once (before the HUD first replaces it)."""
    saved = db.get_hud_settings().get(SETTING_ORIGINAL, "")
    if saved and Path(saved).exists():
        return
    current = _current_wallpaper()
    if not current or Path(current).resolve() == hud_path().resolve() or not Path(current).exists():
        return
    ext = Path(current).suffix.lower() if Path(current).suffix.lower() in IMAGE_EXTS else ".jpg"
    dest = _data_dir() / f"original_wallpaper{ext}"
    try:
        shutil.copy2(current, dest)
        db.set_hud_setting(SETTING_ORIGINAL, str(dest))
    except OSError:
        log.exception("Could not keep a copy of the original wallpaper")


def has_original() -> bool:
    saved = db.get_hud_settings().get(SETTING_ORIGINAL, "")
    return bool(saved) and Path(saved).exists()


def render_wallpaper():
    """Builds the HUD and sets it as the desktop wallpaper (does nothing while paused)."""
    try:
        if is_paused():
            return
        img = build_hud_image()
        _remember_original()
        path = hud_path()
        img.save(str(path), "BMP")
        _set_wallpaper(str(path))
    except Exception:
        log.exception("Wallpaper update error")


def pause_hud() -> bool:
    """Stops updating the HUD and puts the original wallpaper back. Returns True if it was restored."""
    global _timer
    db.set_hud_setting(SETTING_PAUSED, "true")
    with _timer_lock:
        if _timer is not None:
            _timer.cancel()
        _timer = None
    saved = db.get_hud_settings().get(SETTING_ORIGINAL, "")
    return bool(saved) and Path(saved).exists() and _set_wallpaper(saved)


def resume_hud():
    db.set_hud_setting(SETTING_PAUSED, "false")
    request_wallpaper_update(delay=0)


# ------------------------------------------------------------------ debounced / background refresh
_timer = None
_timer_lock = threading.Lock()
_render_lock = threading.Lock()


def _run_update():
    with _render_lock:
        render_wallpaper()


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
