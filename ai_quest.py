"""AI quest planner: Gemini turns a goal into a quest plan (type, difficulty, subquests, first step,
optional measurable target). The student edits the plan before anything is saved.

No dates, deadlines or timelines on purpose: the app is about improving, not about pressure.
"""
from typing import List

from pydantic import BaseModel, Field

import ai_gemini
from constants import QUEST_TYPES, QUEST_DIFFICULTY_XP, QUEST_REPEATS


class QuestPlan(BaseModel):
    title: str = Field(description="Short, motivating quest title")
    quest_type: str = Field(description="One of: Main (important goal), Side (smaller/optional), "
                                        "Epic (long, multi-month journey)")
    difficulty: str = Field(description="One of: Easy, Normal, Hard, Epic — the effort needed")
    repeat: str = Field(description="none for a one-time goal; weekly or monthly only for routines "
                                    "that should be done again every period")
    description: str = Field(description="Two or three sentences: what success looks like and why it matters")
    subquests: List[str] = Field(description="4-10 small, concrete steps in a sensible order; each one "
                                             "doable in a single sitting. Empty for very small quests.")
    first_step: str = Field(description="The very first tiny action to start today (one sentence)")
    measurable: bool = Field(description="True only if progress is naturally a number (kg, books, money, km…)")
    metric_unit: str = Field(description="Unit of the number when measurable (e.g. kg, books, R$); else empty")
    metric_start: float = Field(description="Starting value when measurable and known from the input; else 0")
    metric_target: float = Field(description="Target value when measurable; else 0")


SYSTEM = f"""You are a supportive coach inside a personal gamification app. Turn the user's goal into a quest.
Rules:
- NEVER include dates, deadlines, durations, schedules or time pressure anywhere. Order steps logically instead.
- Steps must be small and concrete, phrased as actions, and written for this person's situation.
- quest_type must be one of {QUEST_TYPES}; difficulty one of {list(QUEST_DIFFICULTY_XP)};
  repeat one of {QUEST_REPEATS}.
- Only mark measurable when the goal is naturally a number; use the user's current value as metric_start
  when they mention it.
- Write in the same language the user wrote in."""


def _normalize(plan: QuestPlan) -> QuestPlan:
    """Keeps the model's answer inside the app's vocabulary."""
    plan.quest_type = next((t for t in QUEST_TYPES if t.lower() == plan.quest_type.strip().lower()), "Main")
    plan.difficulty = next((d for d in QUEST_DIFFICULTY_XP if d.lower() == plan.difficulty.strip().lower()),
                           "Normal")
    plan.repeat = plan.repeat.strip().lower() if plan.repeat.strip().lower() in QUEST_REPEATS else "none"
    plan.subquests = [s.strip() for s in plan.subquests if s and s.strip()][:15]
    if plan.repeat != "none" or not plan.metric_unit.strip() or plan.metric_target == plan.metric_start:
        plan.measurable = False
    return plan


def plan_quest(goal: str, context: str = "", existing: dict = None) -> QuestPlan:
    """Asks Gemini for a plan. `existing` (a quest dict) asks for extra subquests for that quest."""
    parts = [f"GOAL: {goal.strip()}"]
    if context.strip():
        parts.append(f"CONTEXT FROM THE USER:\n{context.strip()}")
    if existing:
        parts.append("This quest already exists. Suggest ADDITIONAL subquests that are missing, without "
                     "repeating these existing ones:\n" +
                     "\n".join(f"- {s['title']}" for s in existing.get("subquests", [])))
        if existing.get("notes"):
            parts.append(f"QUEST DESCRIPTION:\n{existing['notes']}")
    plan, _ = ai_gemini.generate("\n\n".join(parts), SYSTEM, schema=QuestPlan, temperature=0.6,
                                 max_output_tokens=4096)
    return _normalize(plan)
