"""
Family memory -- local JSON, same pattern as StoryMatch's taste memory.

This is the "Story Universe": each family accumulates characters, places,
real memories turned into stories, lessons already taught, stories told,
and progress reported back after a lesson-oriented story -- so DadHero
isn't a one-shot comic generator, it's building an ongoing world that
carries context forward. A new story can reuse an existing place or
character, and a goal-oriented story can be followed up on days later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "family_memory.json"

_EMPTY_FAMILY: dict[str, Any] = {
    "characters": {},
    "places": {},
    "stories": [],
    "memories": [],
    "lessons_taught": [],
    "progress": [],
}


def _load() -> dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {}
    try:
        with open(MEMORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _family(data: dict[str, Any], family_id: str) -> dict[str, Any]:
    # dict.setdefault with a literal {} default would share that same dict
    # object across every family_id that doesn't exist yet -- construct a
    # fresh copy per call instead.
    if family_id not in data:
        data[family_id] = {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in _EMPTY_FAMILY.items()}
    fam = data[family_id]
    # Back-compat: a family saved before the Story Universe fields existed
    # only has "characters"/"stories" -- fill in the rest so callers never
    # have to special-case an older record.
    for key, default in _EMPTY_FAMILY.items():
        fam.setdefault(key, dict(default) if isinstance(default, dict) else list(default))
    return fam


def get_family_profile(family_id: str) -> dict[str, Any]:
    data = _load()
    fam = _family(data, family_id)
    return dict(fam)


def save_character(family_id: str, character_name: str, bible: dict[str, Any]) -> dict[str, Any]:
    data = _load()
    fam = _family(data, family_id)
    fam["characters"][character_name] = bible
    _save(data)
    return fam["characters"][character_name]


def get_character(family_id: str, character_name: str) -> dict[str, Any] | None:
    data = _load()
    fam = data.get(family_id, {})
    return fam.get("characters", {}).get(character_name)


def save_place(family_id: str, place_name: str, description: str) -> dict[str, Any]:
    data = _load()
    fam = _family(data, family_id)
    fam["places"][place_name] = description
    _save(data)
    return {"place_name": place_name, "description": description}


def record_story(
    family_id: str,
    title: str,
    idea: str,
    template_key: str,
    goal: str | None = None,
) -> None:
    data = _load()
    fam = _family(data, family_id)
    fam["stories"].append({"title": title, "idea": idea, "template": template_key, "goal": goal})
    if goal:
        fam["lessons_taught"].append(goal)
    _save(data)


def record_memory(family_id: str, memory_text: str, used_in_story: str | None = None) -> None:
    """A real family memory (an event, a trip, a milestone) preserved so a
    future story can reuse it, and so the agent doesn't ask about the same
    memory twice."""
    data = _load()
    fam = _family(data, family_id)
    fam["memories"].append({"text": memory_text, "used_in_story": used_in_story})
    _save(data)


def record_progress(
    family_id: str,
    related_to: str,
    update_text: str,
    story_title: str | None = None,
) -> None:
    """The 'After' in Before -> During -> After: a parent reporting back
    how a goal-oriented story actually landed in real life."""
    data = _load()
    fam = _family(data, family_id)
    fam["progress"].append({"related_to": related_to, "update": update_text, "story_title": story_title})
    _save(data)


def reset_family(family_id: str) -> None:
    data = _load()
    data.pop(family_id, None)
    _save(data)
