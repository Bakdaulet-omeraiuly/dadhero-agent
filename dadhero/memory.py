"""
Family memory -- local JSON, same pattern as StoryMatch's taste memory.

Stores per-family: saved character bibles (so "Dad the Astronaut" doesn't
need to be re-described every time), and a running list of themes/story
titles already used (so the agent can avoid repeating itself and can
reference "last time we did space -- want another adventure with the same
Dad, or a new costume?").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "family_memory.json"


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
    return data.setdefault(family_id, {"characters": {}, "stories": []})


def get_family_profile(family_id: str) -> dict[str, Any]:
    data = _load()
    fam = data.get(family_id, {"characters": {}, "stories": []})
    return {"characters": fam.get("characters", {}), "stories": fam.get("stories", [])}


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


def record_story(family_id: str, title: str, idea: str, template_key: str) -> None:
    data = _load()
    fam = _family(data, family_id)
    fam["stories"].append({"title": title, "idea": idea, "template": template_key})
    _save(data)


def reset_family(family_id: str) -> None:
    data = _load()
    data.pop(family_id, None)
    _save(data)
