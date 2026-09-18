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

LEVEL_TITLES = [
    (0, "Novice"),
    (2, "Apprentice"),
    (4, "Consistent"),
    (7, "Disciplined"),
    (10, "Habit Master"),
    (15, "Ascended")
]

# --- To-Do / Quest Stages & Bonus ---
TASK_STAGES = ["Planning", "Started", "In Progress", "Almost There", "Complete"]
QUEST_BONUS_XP = 50  # XP awarded upon reaching 'Complete'

def get_rank_title(level: int) -> str:
    title = "Novice"
    for req_lvl, name in LEVEL_TITLES:
        if level >= req_lvl:
            title = name
    return title