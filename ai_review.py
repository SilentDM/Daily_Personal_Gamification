"""AI Deep Review: Gemini turns a mastered chapter (journal + wrap-up) into a review pack,
and grades the answers typed during reviews.

One generation call per chapter (stored in study_ai_packs, so reviews work offline);
one grading call per answer the student chooses to check.
"""
import logging
import threading
import time
from typing import List

from pydantic import BaseModel, Field

import ai_gemini
import database as db
from constants import REVIEW_DAYS

log = logging.getLogger("gamification")

SETTING_AUTO = "ai_auto_pack"          # hud_settings: "true" / "false"
MAX_PROMPT_CHARS = 60_000              # newest journal entries are kept first
RETRY_THROTTLE_SECONDS = 600


# ------------------------------------------------------------------ schemas
class Concept(BaseModel):
    name: str = Field(description="Short name of the concept")
    explanation: str = Field(description="Clear explanation in 1-3 sentences")


class Gap(BaseModel):
    issue: str = Field(description="What is wrong, unclear or missing in the student's notes")
    correction: str = Field(description="The correct explanation")


class ReviewQuestion(BaseModel):
    stage: int = Field(description="Review stage 1-4 (1: recall, 2: application, 3: scenarios/edge cases, "
                                   "4: synthesis/teach-back)")
    kind: str = Field(description="One of: recall, application, scenario, code, synthesis")
    question: str = Field(description="The question, answerable without looking at notes")
    answer: str = Field(description="Model answer, concise but complete")


class ReviewPack(BaseModel):
    summary: str = Field(description="What the lesson was about, written cleanly from the student's notes "
                                     "(one or two short paragraphs)")
    key_concepts: List[Concept] = Field(description="The 4-8 most important concepts")
    gaps: List[Gap] = Field(description="Real mistakes or gaps in the notes; empty list if none")
    questions: List[ReviewQuestion] = Field(description="3-4 questions for each of the 4 stages")


class Grade(BaseModel):
    verdict: str = Field(description="One of: correct, partial, incorrect")
    feedback: str = Field(description="Encouraging, precise feedback: what was right and what to fix")
    missing: List[str] = Field(description="Key points the answer missed; empty list if none")


# ------------------------------------------------------------------ prompts
PACK_SYSTEM = f"""You are an expert tutor preparing a spaced-repetition review for a student who has just
finished studying a topic. You receive the student's study journal (notes written while studying) and
their wrap-up (summary, code example, edge cases, flashcards).

Build a review pack:
- summary: what the lesson was really about, based on the notes (fix inaccuracies silently there).
- key_concepts: the most important ideas, explained simply.
- gaps: actual mistakes, misconceptions or important omissions in the notes, each with a correction.
  Do not nitpick style; return an empty list when the notes are correct.
- questions: 3-4 per stage, getting harder. Reviews happen on days {", ".join(map(str, REVIEW_DAYS))}:
  stage 1 = recall of definitions and facts; stage 2 = applying the idea to a small problem;
  stage 3 = realistic scenarios, edge cases, debugging or "what happens if"; stage 4 = synthesis:
  compare, justify, teach it back. Include code questions when the topic is about programming.
Stay on the topic the student studied; you may add closely related essentials they missed.
Write everything in the same language as the student's notes."""

GRADE_SYSTEM = """You grade a student's answer during a spaced-repetition review.
Compare it with the model answer: "correct" if the essential points are there (wording may differ),
"partial" if some essentials are missing or slightly wrong, "incorrect" otherwise.
Give short, encouraging, specific feedback. Answer in the same language as the student's answer."""


def _wrap_up_sections(chapter: dict):
    from study_view import WRAP_UP_FIELDS, is_filled  # templates live with the view
    for key, label, template, _, _ in WRAP_UP_FIELDS:
        if is_filled(chapter.get(key, ""), template):
            yield label.split("(")[0].strip(), chapter[key].strip()


def build_pack_prompt(chapter: dict, journal: list) -> str:
    head = [f"TOPIC: {chapter['topic']}", f"SOURCE: {chapter.get('source') or '-'}"]
    wrap = [f"### {title}\n{text}" for title, text in _wrap_up_sections(chapter)]
    budget = MAX_PROMPT_CHARS - sum(len(x) for x in head + wrap)
    entries = []
    for e in journal:  # newest first
        minutes = f", {e['minutes']} min" if e.get("minutes") else ""
        block = f"[{e['entry_date']}{minutes}]\n{e['notes'].strip()}"
        if e.get("next_step"):
            block += f"\n(next step: {e['next_step']})"
        if budget - len(block) < 0:
            break
        budget -= len(block)
        entries.append(block)
    entries.reverse()  # chronological for the model
    parts = head + ["\n## STUDY JOURNAL (chronological)", *(entries or ["(no journal entries)"]),
                    "\n## WRAP-UP", *(wrap or ["(wrap-up not filled in)"])]
    return "\n\n".join(parts)


def questions_for_stage(pack: dict, review_no: int):
    """Questions of the stage matching this review (1..4); all questions if that stage is empty."""
    stage = max(1, min(review_no, len(REVIEW_DAYS)))
    questions = pack.get("questions") or []
    return [q for q in questions if q.get("stage") == stage] or questions


# ------------------------------------------------------------------ settings
def auto_enabled() -> bool:
    return db.get_hud_settings().get(SETTING_AUTO, "true") == "true"


def set_auto_enabled(value: bool):
    db.set_hud_setting(SETTING_AUTO, "true" if value else "false")


# ------------------------------------------------------------------ generation
_in_flight = set()
_in_flight_lock = threading.Lock()
_last_retry = 0.0


def generate_pack(session_id: int) -> bool:
    """Generates (or regenerates) a chapter's pack synchronously. Returns True on success."""
    chapter = db.get_study_session(session_id)
    if not chapter:
        return False
    db.set_ai_pack(session_id, "generating")
    try:
        pack, model = ai_gemini.generate(build_pack_prompt(chapter, db.get_journal(session_id)),
                                         PACK_SYSTEM, schema=ReviewPack, temperature=0.4)
    except ai_gemini.AINotConfigured as exc:
        db.set_ai_pack(session_id, "pending", error=str(exc))  # waits for a key, no attempt used
        return False
    except Exception as exc:
        log.warning("AI review pack for chapter %s failed: %s", session_id, exc)
        db.set_ai_pack(session_id, "failed", error=str(exc), count_attempt=True)
        return False
    db.set_ai_pack(session_id, "ready", content=pack.model_dump(), model=model.removeprefix("models/"),
                   reset_attempts=True)
    return True


def _run(session_ids, on_done):
    for sid in session_ids:
        try:
            generate_pack(sid)
        finally:
            with _in_flight_lock:
                _in_flight.discard(sid)
        if on_done:
            try:
                on_done(sid)
            except Exception:
                log.exception("AI pack callback failed")


def start_generation(session_ids, on_done=None) -> bool:
    """Generates packs in a background thread (skips ones already running). Returns True if started."""
    if isinstance(session_ids, int):
        session_ids = [session_ids]
    with _in_flight_lock:
        todo = [s for s in session_ids if s not in _in_flight]
        _in_flight.update(todo)
    if not todo:
        return False
    threading.Thread(target=_run, args=(todo, on_done), daemon=True, name="ai-review-pack").start()
    return True


def is_generating(session_id: int) -> bool:
    with _in_flight_lock:
        return session_id in _in_flight


def queue_on_mastery(session_id: int, on_done=None):
    """Called when a chapter is mastered: queue its pack and generate it now if Gemini is set up."""
    if not auto_enabled():
        return
    db.set_ai_pack(session_id, "pending", reset_attempts=True)
    if ai_gemini.is_configured():
        start_generation(session_id, on_done)


def retry_pending(on_done=None, force: bool = False) -> bool:
    """Retries pending/failed packs (throttled). Safe to call often."""
    global _last_retry
    if not ai_gemini.is_configured():
        return False
    if not force and time.monotonic() - _last_retry < RETRY_THROTTLE_SECONDS:
        return False
    _last_retry = time.monotonic()
    todo = db.get_ai_packs_to_generate()
    return start_generation(todo, on_done) if todo else False


# ------------------------------------------------------------------ grading
def grade_answer(topic: str, question: str, model_answer: str, student_answer: str) -> Grade:
    prompt = (f"TOPIC: {topic}\n\nQUESTION:\n{question}\n\nMODEL ANSWER:\n{model_answer}\n\n"
              f"STUDENT ANSWER:\n{student_answer}")
    grade, _ = ai_gemini.generate(prompt, GRADE_SYSTEM, schema=Grade, temperature=0.2, max_output_tokens=2048)
    return grade
