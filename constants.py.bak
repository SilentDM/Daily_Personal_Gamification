# Scoring for standard positive habits
POSITIVE_SCORES = {
    "Excellent": 10,
    "Ok": 7,
    "A Little": 4,
    "Skipped": 0,
    "-": None
}

# Inverted scoring for vices / bad habits to avoid
NEGATIVE_SCORES = {
    "Resisted": 10,
    "Slipped": 4,
    "Relapsed": 0,
    "-": None
}

CATEGORIES = ["Health", "Study", "Routine", "Vice / Avoid"]

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

TASK_STAGES = ["Planning", "Started", "In Progress", "Almost There", "Complete"]

# Quest Bonus XP (matches the 1-100 level discipline scale)
QUEST_BONUS_XP = 20

# 1-100 Level Rank Tiers
def get_rank_title(level: int) -> str:
    if level >= 100:
        return "Centurion"
    elif level >= 81:
        return "Master"
    elif level >= 61:
        return "Elite"
    elif level >= 36:
        return "Disciplined"
    elif level >= 16:
        return "Apprentice"
    else:
        return "Novice"