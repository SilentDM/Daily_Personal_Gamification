"""Honest reflection on a diary day (opt-in, one click per day; nothing is ever sent automatically).

Only that day's page, exercises, habit notes, habit answers and mood go to Gemini, and only after the
user agreed once to the notice in the Diary tab. The reflection is stored encrypted with the entry.
"""
from datetime import date

import ai_gemini
import ai_insight
import database as db

SETTING_CONSENT = "diary_ai_consent"
MAX_PROMPT_CHARS = 12000

SYSTEM = """You read one day of the user's private diary (plus that day's habit answers) and give an honest,
impartial reflection. The user asked for a straight, useful read of what is going on, not comfort:
- be direct; don't soften, flatter or sugar-coat, and don't take the user's side by default;
- look at every side: where they were right, where their own account shows they contributed to a problem,
  and how other people involved may have seen it;
- name patterns, contradictions and blind spots you notice (between what they say and what they do, between
  goals and habits, between days of effort and how they talk about themselves) and explain why they matter;
- acknowledge real progress plainly, without hype;
- give concrete, practical next steps (what to do, how small to start, what to watch for); when the text
  mentions physical or mental health warning signs, say clearly when it's worth seeing a professional;
- ground everything in what they wrote; don't invent facts, don't moralize, don't diagnose or label;
- if the text suggests they might be in danger or thinking about self-harm, say so plainly and urge them to
  talk to someone they trust and contact a crisis line now (in Brazil: CVV, call 188, free, 24h, or
  cvv.org.br; elsewhere: local emergency services);
- plain text, short paragraphs (no headings or tables), roughly 200-400 words.
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
    answers = _habit_answers(day)
    if answers:
        parts.append("HABITS THAT DAY:\n" + "\n".join(f"- {name}: {status}" for name, status in answers))
    notes = db.get_habit_notes(day)
    if notes:
        parts.append("NOTES ON HABITS:\n" + "\n".join(
            f"- {n['habit']} ({n['status'] if n['status'] != '-' else 'not marked'})"
            f"{' [highlight]' if n['highlight'] else ''}: {n['note']}" for n in notes))
    return "\n\n".join(parts)[:MAX_PROMPT_CHARS]


def _habit_answers(day):
    """[(habit, answer)] marked on that day (active habits), for context next to the diary text."""
    d = day if isinstance(day, date) else date.fromisoformat(str(day))
    iso = d.isocalendar()
    logs = db.get_current_week_logs(iso[0], iso[1])
    return [(name, logs[(aid, iso[2] - 1)][0]) for aid, name, _, _ in db.get_activities()
            if logs.get((aid, iso[2] - 1), ("-", None))[0] != "-"]


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
                                 temperature=0.5, max_output_tokens=4096)
    db.set_diary_reflection(day, text.strip())
    return text.strip()
