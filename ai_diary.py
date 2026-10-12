"""Gentle reflection on a diary day (opt-in, one click per day; nothing is ever sent automatically).

Only that day's page, exercises, habit notes and mood go to Gemini, and only after the user agreed
once to the notice in the Diary tab. The reflection is stored encrypted with the entry.
"""
import ai_gemini
import ai_insight
import database as db

SETTING_CONSENT = "diary_ai_consent"
MAX_PROMPT_CHARS = 12000

SYSTEM = """You are a warm, thoughtful journaling companion inside a personal-growth app. The user shares one
day of their private diary. Write a short reflection for them:
- start from what they actually wrote; name one or two specific things (a feeling, an effort, a small win);
- validate feelings without judging; notice strengths and progress, however small;
- offer at most one gentle question to think about OR one small, concrete idea for tomorrow;
- you are not a therapist: never diagnose, never label, never lecture, no toxic positivity;
- if the text suggests they might be in danger or thinking about self-harm, say with care that they deserve
  support right now, encourage them to talk to someone they trust and to contact a crisis line
  (in Brazil: CVV, call 188, free, 24h, or cvv.org.br; elsewhere: local emergency services);
- plain text, 2 short paragraphs, at most 150 words, no headings or lists, at most one emoji.
Write in {language}."""


def has_consent() -> bool:
    return db.get_hud_settings().get(SETTING_CONSENT) == "yes"


def give_consent():
    db.set_hud_setting(SETTING_CONSENT, "yes")


def build_prompt(day, exercise_titles: dict = None) -> str:
    """The day's diary content as text (what is sent to Gemini)."""
    entry = db.get_diary_entry(day)
    parts = [f"DATE: {entry['entry_date']}"]
    if entry["mood"]:
        parts.append(f"MOOD: {entry['mood']}/5")
    if entry["energy"]:
        parts.append(f"ENERGY: {entry['energy']}/5")
    if entry["body"].strip():
        parts.append("DIARY PAGE:\n" + entry["body"].strip())
    for ex in db.get_diary_exercises(day):
        title = (exercise_titles or {}).get(ex["kind"], ex["kind"])
        lines = [f"- {k}: {v}" for k, v in ex["fields"].items() if v]
        if lines:
            parts.append(f"EXERCISE ({title}):\n" + "\n".join(lines))
    notes = db.get_habit_notes(day)
    if notes:
        parts.append("NOTES ON HABITS:\n" + "\n".join(
            f"- {n['habit']} ({n['status'] if n['status'] != '-' else 'not marked'})"
            f"{' [highlight]' if n['highlight'] else ''}: {n['note']}" for n in notes))
    return "\n\n".join(parts)[:MAX_PROMPT_CHARS]


def has_content(day) -> bool:
    entry = db.get_diary_entry(day)
    return bool(entry["body"].strip() or db.get_diary_exercises(day) or db.get_habit_notes(day))


def reflect(day, exercise_titles: dict = None) -> str:
    """Asks Gemini for the reflection, saves it (encrypted) and returns it. Raises ai_gemini.AIError."""
    if not has_consent():
        raise ai_gemini.AIError("Confirm the notice first.")
    if not has_content(day):
        raise ai_gemini.AIError("Write something first: there is nothing to reflect on yet.")
    text, _ = ai_gemini.generate(build_prompt(day, exercise_titles),
                                 SYSTEM.format(language=ai_insight.language()),
                                 temperature=0.7, max_output_tokens=1024)
    db.set_diary_reflection(day, text.strip())
    return text.strip()
