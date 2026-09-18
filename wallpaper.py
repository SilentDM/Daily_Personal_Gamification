import os
import ctypes
import database as db
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COLOR_PALETTES = {
    "Cyan": {"border": (0, 220, 255, 180), "header": (0, 225, 255, 255), "bar": (0, 220, 255, 255)},
    "Amber / Gold": {"border": (255, 180, 0, 180), "header": (255, 195, 0, 255), "bar": (255, 180, 0, 255)},
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
    """Detects primary monitor dimensions."""
    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w if w > 0 else 1920, h if h > 0 else 1080

def get_base_wallpaper(bg_mode: str, screen_w: int, screen_h: int):
    """Generates pure black canvas or loads custom image."""
    if bg_mode != "Pure Black (Minimalist)":
        for ext in [".jpg", ".png", ".jpeg"]:
            candidate = Path(f"base_wallpaper{ext}")
            if candidate.exists():
                img = Image.open(candidate).convert("RGBA")
                return img.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
    
    # Pure Minimalist Black Canvas
    return Image.new("RGBA", (screen_w, screen_h), (12, 14, 18, 255))

def update_desktop_wallpaper():
    """Generates the customizable HUD overlay and sets Windows wallpaper."""
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

        tasks = db.get_tasks()
        active_quests = [t[1] for t in tasks if t[2] != "Complete"][:3]

        # 2. Layout dimensions
        show_quests = settings["show_quests"] == "true"
        show_score = settings["show_score"] == "true"
        show_xp_bar = settings["show_xp_bar"] == "true"
        accent = COLOR_PALETTES.get(settings["accent_color"], COLOR_PALETTES["Cyan"])

        hud_w = 460
        hud_h = 130
        if show_score:
            hud_h += 35
        if show_xp_bar:
            hud_h += 45
        if show_quests:
            hud_h += 50 + (len(active_quests) * 26)

        margin_x = 70
        margin_y = 60
        pos = settings["position"]

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
        else:  # Default: Top-Right
            x1, y1 = screen_w - hud_w - margin_x, margin_y

        x2, y2 = x1 + hud_w, y1 + hud_h

        # 3. Draw HUD Card
        draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=16,
            fill=(18, 22, 30, 220),
            outline=accent["border"],
            width=2
        )

        font_title = get_font(18, bold=True)
        font_sub = get_font(12, bold=True)
        font_body = get_font(14, bold=False)
        font_body_bold = get_font(14, bold=True)

        # Header & Rank
        draw.text((x1 + 25, y1 + 20), "DAILY GAMIFICATION HUD", fill=accent["header"], font=font_sub)
        draw.text((x1 + 25, y1 + 42), f"Level {level} / 100 • {rank_title}", fill=(255, 255, 255, 255), font=font_title)

        curr_y = y1 + 78

        # Streak & Today's Score (Clean icon, no broken emoji boxes!)
        if show_score:
            score_status = "PASSING" if today_avg >= 7.0 else ("NEUTRAL" if today_avg >= 5.0 else "NEEDS FOCUS")
            score_color = (0, 255, 180, 255) if today_avg >= 7.0 else ((255, 180, 0, 255) if today_avg >= 5.0 else (255, 80, 80, 255))
            
            # Using clean text glyphs so it never renders a square [?]
            draw.text((x1 + 25, curr_y), f"★ STREAK: {streak} Days", fill=(255, 165, 50, 255), font=font_body_bold)
            draw.text((x1 + 230, curr_y), f"Today: {today_avg:.1f} / 10 [{score_status}]", fill=score_color, font=font_body_bold)
            curr_y += 32

        # Level XP Progress Bar
        if show_xp_bar:
            bar_x = x1 + 25
            bar_w = hud_w - 50
            bar_h = 8
            fill_w = int(bar_w * (xp_in_level / 10.0))

            draw.rounded_rectangle([bar_x, curr_y + 6, bar_x + bar_w, curr_y + 14], radius=4, fill=(40, 45, 55, 255))
            if fill_w > 0:
                draw.rounded_rectangle([bar_x, curr_y + 6, bar_x + fill_w, curr_y + 14], radius=4, fill=accent["bar"])

            draw.text((x1 + 25, curr_y + 20), f"{xp_in_level:.1f} / 10 XP to Level {min(100, level+1)} (Total: {total_xp:.1f}/1000)", fill=(160, 170, 185, 255), font=get_font(11))
            curr_y += 42

        # Quests Section
        if show_quests:
            draw.line([x1 + 25, curr_y + 6, x2 - 25, curr_y + 6], fill=(50, 60, 75, 255), width=1)
            draw.text((x1 + 25, curr_y + 16), "ACTIVE QUESTS:", fill=(200, 210, 225, 255), font=font_sub)
            
            q_y = curr_y + 38
            if active_quests:
                for q in active_quests:
                    clean_q = (q[:38] + "...") if len(q) > 38 else q
                    draw.text((x1 + 25, q_y), f"• {clean_q}", fill=(240, 240, 240, 255), font=font_body)
                    q_y += 26
            else:
                draw.text((x1 + 25, q_y), "• All quests completed! Great job.", fill=(120, 220, 140, 255), font=font_body)

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