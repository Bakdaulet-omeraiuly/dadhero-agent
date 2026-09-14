"""
Supabase-backed Story Universe -- same function surface as memory.py
(local JSON), so dadhero/memory_backend.py can swap between them and every
existing call site in tools.py keeps working unchanged.

Security: `family_id` arguments here are IGNORED in favor of
request_context.current_family_id -- the server-verified authenticated
user, never whatever value an LLM tool call happened to pass. The actual
enforcement boundary is Postgres RLS (see supabase/migrations/0001_init.sql):
current_supabase_client is a client already carrying the requesting user's
own JWT, so even a bug here that leaked another family_id would still be
rejected at the database. Belt AND suspenders, not either/or.

UNTESTED against a live Supabase project as of writing -- see
backend/README.md for the standalone round-trip check to run once
SUPABASE_URL/SUPABASE_ANON_KEY are available (same "don't trust it until
you've seen a real response" discipline as image_providers.GeminiImageProvider
before it was verified).
"""

from __future__ import annotations

from typing import Any

from dadhero.request_context import current_family_id, current_supabase_client


def _client():
    client = current_supabase_client.get()
    if client is None:
        raise RuntimeError(
            "No Supabase client bound to this request -- backend/main.py must call "
            "request_context.current_supabase_client.set(...) before invoking the agent."
        )
    return client


def _fid(_ignored_family_id: str) -> str:
    """The parameter every function below accepts (for signature parity
    with memory.py) is deliberately discarded in favor of the server-
    verified identity -- see module docstring."""
    return current_family_id.get()


def get_family_profile(family_id: str) -> dict[str, Any]:
    fid = _fid(family_id)
    c = _client()
    characters = c.table("characters").select("*").eq("family_id", fid).execute().data
    places = c.table("places").select("*").eq("family_id", fid).execute().data
    stories = c.table("stories").select("*").eq("family_id", fid).execute().data
    memories = c.table("memories").select("*").eq("family_id", fid).execute().data
    progress = c.table("progress_updates").select("*").eq("family_id", fid).execute().data

    return {
        "characters": {row["character_name"]: row for row in characters},
        "places": {row["place_name"]: row["description"] for row in places},
        "stories": stories,
        "memories": memories,
        "lessons_taught": [s["goal"] for s in stories if s.get("goal")],
        "progress": progress,
    }


def save_character(family_id: str, character_name: str, bible: dict[str, Any]) -> dict[str, Any]:
    fid = _fid(family_id)
    c = _client()
    row = {
        "family_id": fid,
        "character_name": character_name,
        "relationship": bible.get("relationship", ""),
        "appearance_text": bible.get("appearance"),
        "personality_traits": bible.get("personality_traits", []),
        "role_in_story": bible.get("role_in_story", ""),
        "art_style": bible.get("art_style", ""),
        "reference_image_path": bible.get("reference_image_path"),
        "prompt_fragment": bible.get("prompt_fragment", ""),
    }
    existing = (
        c.table("characters").select("id").eq("family_id", fid).eq("character_name", character_name).execute().data
    )
    if existing:
        result = c.table("characters").update(row).eq("id", existing[0]["id"]).execute()
    else:
        result = c.table("characters").insert(row).execute()
    return result.data[0]


def get_character(family_id: str, character_name: str) -> dict[str, Any] | None:
    fid = _fid(family_id)
    c = _client()
    rows = c.table("characters").select("*").eq("family_id", fid).eq("character_name", character_name).execute().data
    return rows[0] if rows else None


def save_place(family_id: str, place_name: str, description: str) -> dict[str, Any]:
    fid = _fid(family_id)
    c = _client()
    row = {"family_id": fid, "place_name": place_name, "description": description}
    existing = c.table("places").select("id").eq("family_id", fid).eq("place_name", place_name).execute().data
    if existing:
        c.table("places").update(row).eq("id", existing[0]["id"]).execute()
    else:
        c.table("places").insert(row).execute()
    return {"place_name": place_name, "description": description}


def record_story(
    family_id: str,
    title: str,
    idea: str,
    template_key: str,
    goal: str | None = None,
) -> None:
    fid = _fid(family_id)
    c = _client()
    c.table("stories").insert(
        {
            "family_id": fid,
            "title": title,
            "idea": idea,
            "template_key": template_key,
            "goal": goal,
            "status": "finished",
        }
    ).execute()


def record_memory(family_id: str, memory_text: str, used_in_story: str | None = None) -> None:
    fid = _fid(family_id)
    c = _client()
    c.table("memories").insert(
        {"family_id": fid, "text": memory_text, "used_in_story_id": used_in_story}
    ).execute()


def record_progress(
    family_id: str,
    related_to: str,
    update_text: str,
    story_title: str | None = None,
) -> None:
    fid = _fid(family_id)
    c = _client()
    story_id = None
    if story_title:
        rows = c.table("stories").select("id").eq("family_id", fid).eq("title", story_title).limit(1).execute().data
        story_id = rows[0]["id"] if rows else None
    c.table("progress_updates").insert(
        {"family_id": fid, "related_to": related_to, "update_text": update_text, "story_id": story_id}
    ).execute()


def reset_family(family_id: str) -> None:
    fid = _fid(family_id)
    c = _client()
    for table in ("characters", "places", "stories", "memories", "progress_updates"):
        c.table(table).delete().eq("family_id", fid).execute()
