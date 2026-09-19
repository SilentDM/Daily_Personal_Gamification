import os
import ctypes
import textwrap
import database as db
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COLOR_PALETTES = {
    "Amber / Gold": {"border": (255, 180, 0, 180), "header": (255, 195, 0, 255), "bar": (255, 180, 0, 255)},
    "Cyan": {"border": (0, 220, 255, 180), "header": (0, 225, 255, 255), "bar": (0, 220, 255, 255)},
    "Neon Green": {"border": (0, 255, 150, 180), "header": (0, 255, 150, 255), "bar": (0, 255, 150, 255)},
    "Purple": {"border": (190, 100, 255, 180), "header": (200, 120, 255, 255), "bar": (190, 100, 255, 255)},
    "Crimson": {"border": (255, 75, 75, 180), "header": (255, 90, 90, 255), "bar": (255, 75, 75, 255)},
}

def get_font(size: int, bold: bool = False):
    font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
    font_path = Path("C:/Windows/Fonts") / font_name
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()

def get_screen_resolution():
    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w if w > 0 else 1920, h if h > 0 else 1080

def get_base_wallpaper(bg_mode: str, screen_w: int, screen_h: int):
    if bg_mode != "Pure Black (Minimalist)":
        for ext in [".jpg", ".png", ".jpeg"]:
            candidate = Path(f"base_wallpaper{ext}")
            if candidate.exists():
                img = Image.open(candidate).convert("RGBA")
                return img.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
    
    return Image.new("RGBA", (screen_w, screen_h), (12, 14, 18, 255))

def wrap_bullet_lines(text: str, max_chars: int = 42):
    """Wraps text into indented bullet points."""
    wrapped = textwrap.wrap(text, width=max_chars)
    if not wrapped:
        return []
    lines = [f"• {wrapped[0]}"]
    for sub in wrapped[1:]:
        lines.append(f"   {sub}")
    return lines

def update_desktop_wallpaper():
    """Generates the customizable HUD overlay with dynamic multi-line text and studies."""
    try:
        settings = db.get_hud_settings()
        screen_w, screen_h = get_screen_resolution()
        base_img = get_base_wallpaper(settings["bg_mode"], screen_w, screen_h)

        overlay = Image.new("RGBA", (screen_w, screen_h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # 1. Fetch live metrics
        streak = db.get_current_streak()
        total_xp, level, xp_in_level, rank_title = db.get_user_xp_and_level()
        year, week, today_idx = db.get_current_week_info()
        logs = db.get_current_week_logs(year, week)
        active_ids = {a[0] for a in db.get_activities()}
        
        today_scores = [
            score for (act_id, day), (_, score) in logs.items() 
            if day == today_idx and score is not None and act_id in active_ids
        ]
        today_avg = (sum(today_scores) / len(today_scores)) if today_scores else 0.0

        # Quests
        tasks = db.get_tasks()
        active_quests = [t[1] for t in tasks if t[2] != "Complete"][:3]
        
        # In-Progress Study Chapters
        study_sessions = db.get_study_sessions()
        active_studies = [f"{s[1]} ({s[2]})" for s in study_sessions if s[7] == "In Progress"][:2]

        show_quests = settings.get("show_quests", "true") == "true"
        show_studies = settings.get("show_studies", "true") == "true"
        show_score = settings.get("show_score", "true") == "true"
        show_xp_bar = settings.get("show_xp_bar", "true") == "true"
        accent = COLOR_PALETTES.get(settings.get("accent_color", "Amber / Gold"), COLOR_PALETTES["Amber / Gold"])

        # 2. Pre-calculate wrapped lines so the box height fits perfectly
        quest_lines = []
        if show_quests:
            if active_quests:
                for q in active_quests:
                    quest_lines.extend(wrap_bullet_lines(q, max_chars=40))
            else:
                quest_lines.append("• All quests completed!")

        study_lines = []
        if show_studies:
            if active_studies:
                for s in active_studies:
                    study_lines.extend(wrap_bullet_lines(s, max_chars=40))
            else:
                study_lines.append("• No active chapters right now.")

        # Compute dynamic HUD box height
        hud_w = 480
        hud_h = 100
        if show_score:
            hud_h += 36
        if show_xp_bar:
            hud_h += 48
        if show_quests:
            hud_h += 38 + (len(quest_lines) * 22)
        if show_studies:
            hud_h += 38 + (len(study_lines) * 22)

        margin_x = 70
        margin_y = 60
        pos = settings.get("position", "Top-Right")

        if pos == "Top-Left":
            x1, y1 = margin_x, margin_y
        elif pos == "Bottom-Left":
            x1, y1 = margin_x, screen_h - hud_h - margin_y
        elif pos == "Bottom-Right":
            x1, y1 = screen_w - hud_w - margin_x, screen_h - hud_h - margin_y
        elif pos == "Top-Center":
            x1, y1 = (screen_w - hud_w) // 2, margin_y
        elif pos == "Center":
            x1, y1 = (screen_w - hud_w) // 2, (screen_h - hud_h) // 2
        else:  # Top-Right default
            x1, y1 = screen_w - hud_w - margin_x, margin_y

        x2, y2 = x1 + hud_w, y1 + hud_h

        # 3. Draw Background Card
        draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=16,
            fill=(18, 22, 30, 225),
            outline=accent["border"],
            width=2
        )

        font_title = get_font(18, bold=True)
        font_sub = get_font(12, bold=True)
        font_body = get_font(13, bold=False)
        font_body_bold = get_font(14, bold=True)

        # Header Title & Level
        draw.text((x1 + 25, y1 + 18), "DAILY GAMIFICATION HUD", fill=accent["header"], font=font_sub)
        draw.text((x1 + 25, y1 + 38), f"Level {level} / 100 • {rank_title}", fill=(255, 255, 255, 255), font=font_title)

        curr_y = y1 + 72

        # Streak & Score Row
        if show_score:
            score_status = "PASSING" if today_avg >= 7.0 else ("NEUTRAL" if today_avg >= 5.0 else "NEEDS FOCUS")
            score_color = (0, 255, 180, 255) if today_avg >= 7.0 else ((255, 180, 0, 255) if today_avg >= 5.0 else (255, 85, 85, 255))
            
            draw.text((x1 + 25, curr_y), f"STREAK: {streak} Days", fill=(255, 175, 40, 255), font=font_body_bold)
            draw.text((x1 + 235, curr_y), f"Today: {today_avg:.1f} / 10 [{score_status}]", fill=score_color, font=font_body_bold)
            curr_y += 32

        # Level XP Bar
        if show_xp_bar:
            bar_x = x1 + 25
            bar_w = hud_w - 50
            bar_h = 8
            fill_w = int(bar_w * (xp_in_level / 10.0))

            draw.rounded_rectangle([bar_x, curr_y + 4, bar_x + bar_w, curr_y + 12], radius=4, fill=(40, 45, 55, 255))
            if fill_w > 0:
                draw.rounded_rectangle([bar_x, curr_y + 4, bar_x + fill_w, curr_y + 12], radius=4, fill=accent["bar"])

            draw.text((x1 + 25, curr_y + 18), f"{xp_in_level:.1f} / 10 XP to Level {min(100, level+1)} (Total: {total_xp:.1f}/1000)", fill=(160, 170, 185, 255), font=get_font(11))
            curr_y += 42

        # Active Quests Section (Multi-line wrapped)
        if show_quests:
            draw.line([x1 + 25, curr_y + 4, x2 - 25, curr_y + 4], fill=(50, 60, 75, 255), width=1)
            draw.text((x1 + 25, curr_y + 12), "ACTIVE QUESTS:", fill=(200, 210, 225, 255), font=font_sub)
            curr_y += 32

            for line in quest_lines:
                draw.text((x1 + 25, curr_y), line, fill=(240, 240, 240, 255), font=font_body)
                curr_y += 22

        # Active Study Chapters Section (Multi-line wrapped)
        if show_studies:
            draw.line([x1 + 25, curr_y + 4, x2 - 25, curr_y + 4], fill=(50, 60, 75, 255), width=1)
            draw.text((x1 + 25, curr_y + 12), "IN-PROGRESS STUDIES:", fill=accent["header"], font=font_sub)
            curr_y += 32

            for line in study_lines:
                draw.text((x1 + 25, curr_y), line, fill=(220, 240, 255, 255), font=font_body)
                curr_y += 22

        # Save & Set Windows Wallpaper
        final_img = Image.alpha_composite(base_img, overlay).convert("RGB")
        app_data = os.getenv("APPDATA") or str(Path.home())
        save_dir = Path(app_data) / "Daily_Personal_Gamification"
        save_dir.mkdir(parents=True, exist_ok=True)
        wallpaper_path = save_dir / "current_wallpaper_hud.bmp"
        
        final_img.save(str(wallpaper_path), "BMP")
        ctypes.windll.user32.SystemParametersInfoW(20, 0, str(wallpaper_path), 3)
    except Exception as ex:
        print(f"Wallpaper update error: {ex}")