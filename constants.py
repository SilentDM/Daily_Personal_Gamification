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
# XP awarded per source (single source of truth, used by database.py and the views)
XP_QUEST = 15
XP_STUDY = 15
XP_EVENT = 10
XP_NOTE_PROGRESS = 2.0
XP_STUDY_LOG = 2.0   # first journal entry of the day per chapter
XP_REVIEW = 5        # each spaced-repetition review completed
QUEST_BONUS_XP = XP_QUEST  # alias kept for todo_view

# Study chapters: stages and spaced-repetition review days (counted from mastery)
STUDY_STAGES = ["Not started", "Studying", "Reviewing", "Mastered"]
REVIEW_DAYS = (1, 3, 7, 21)

# Daily score thresholds (0-10 scale), shared by streak, table colors and charts
SCORE_PASSING = 7.0
SCORE_GREEN = SCORE_PASSING
SCORE_ORANGE = 5.0

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