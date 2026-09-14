"""
Deterministic story-fact continuity tracking -- StorySprout's "Killer
Feature: Story Continuity" (page 1 says red backpack, page 4 says blue),
implemented the same way StoryMatch verified evidence: plain Python state
comparison, not a second LLM call hoping it "remembers." Cheap, reliable,
and demoable -- the agent calling this tool is visible proof a real check
happened, not just a claim.

Facts are simple key/value strings scoped to one story (by story_slug) so
multiple in-progress stories don't collide. Not persisted across process
restarts by design -- continuity only matters within one story's
generation session; long-term memory across stories is dadhero/memory.py's
job (recurring characters, past titles).
"""

from __future__ import annotations

from typing import Any

_STORY_FACTS: dict[str, dict[str, str]] = {}
_STORY_PLANS: dict[str, dict[str, Any]] = {}


def check_and_record_fact(story_slug: str, fact_key: str, fact_value: str) -> dict:
    """
    Record a concrete story detail (e.g. fact_key="backpack_color",
    fact_value="red"). If this key was already recorded with a DIFFERENT
    value earlier in the same story, returns a conflict instead of
    silently overwriting it.
    """
    facts = _STORY_FACTS.setdefault(story_slug, {})
    existing = facts.get(fact_key)

    if existing is not None and existing.strip().lower() != fact_value.strip().lower():
        return {
            "status": "conflict",
            "fact_key": fact_key,
            "previous_value": existing,
            "new_value": fact_value,
            "message": (
                f"Continuity conflict: '{fact_key}' was previously '{existing}' "
                f"earlier in this story, but this page uses '{fact_value}'."
            ),
        }

    facts[fact_key] = fact_value
    return {"status": "ok", "fact_key": fact_key, "value": fact_value}


def get_story_facts(story_slug: str) -> dict[str, str]:
    return dict(_STORY_FACTS.get(story_slug, {}))


def record_story_plan(story_slug: str, plan: dict[str, Any]) -> None:
    """Record the page-by-page plan the agent committed to before
    generating any images (see tools.create_story_plan) -- makes planning
    a real, inspectable tool call instead of reasoning the agent never
    externalizes, and gives later calls something to check pages against."""
    _STORY_PLANS[story_slug] = plan


def get_story_plan(story_slug: str) -> dict[str, Any] | None:
    return _STORY_PLANS.get(story_slug)


def reset_story(story_slug: str) -> None:
    _STORY_FACTS.pop(story_slug, None)
    _STORY_PLANS.pop(story_slug, None)
