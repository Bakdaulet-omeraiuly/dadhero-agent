"""GET/POST /me/stories, GET/PATCH/DELETE /me/stories/{id}, and the full
pages sub-resource (GET list, POST create, GET/PATCH one page).

The `pages` table used to never get written to (dadhero/tools.py's
generate_page_image only persists the image FILE, by design -- see its
docstring, kept that way so Streamlit's tested tool signature stays
untouched). It's populated two ways now: conversations.py reconciles a
row for every generate_page_image call after each chat turn (see its
_sync_pages), and createPage/regeneratePage below write directly for a
dashboard that bypasses the chat -- both paths call the SAME
dadhero.tools functions (check_story_fact, check_page_safety,
generate_page_image) the agent itself uses, same pattern as
characters.py's create_character, so the continuity/safety checks live
in exactly one place.

Verified against a live Supabase project -- see backend/README.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import BoundRequest, bound_request
from dadhero.tools import check_page_safety, check_story_fact, generate_page_image

router = APIRouter(prefix="/me/stories", tags=["stories"])


def _get_owned_story(ctx: BoundRequest, story_id: str) -> dict:
    rows = ctx.client.table("stories").select("*").eq("id", story_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Story not found")
    return rows[0]


def _get_story_character(ctx: BoundRequest, story: dict) -> dict:
    character_id = story.get("character_id")
    if not character_id:
        raise HTTPException(status_code=422, detail="Story has no character_id set -- nothing to keep visually consistent")
    rows = ctx.client.table("characters").select("*").eq("id", character_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Story's character not found")
    return rows[0]


@router.get("")
async def list_stories(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
    ctx: BoundRequest = Depends(bound_request),
):
    query = ctx.client.table("stories").select("*").eq("family_id", ctx.user_id)
    if status:
        query = query.eq("status", status)
    rows = query.order("created_at", desc=True).limit(min(limit, 100)).execute().data
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("", status_code=201)
async def create_story(body: dict, ctx: BoundRequest = Depends(bound_request)):
    row = {
        "family_id": ctx.user_id,
        "title": body["title"],
        "idea": body.get("idea"),
        "template_key": body["template_key"],
        "character_id": body.get("character_id"),
        "goal": body.get("goal"),
        "status": "draft",
    }
    return ctx.client.table("stories").insert(row).execute().data[0]


@router.get("/{story_id}")
async def get_story(story_id: str, ctx: BoundRequest = Depends(bound_request)):
    rows = ctx.client.table("stories").select("*").eq("id", story_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Story not found")
    return rows[0]


@router.patch("/{story_id}")
async def update_story(story_id: str, body: dict, ctx: BoundRequest = Depends(bound_request)):
    allowed = {k: v for k, v in body.items() if k in ("status", "goal", "title")}
    rows = ctx.client.table("stories").update(allowed).eq("id", story_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Story not found")
    return rows[0]


@router.delete("/{story_id}", status_code=204)
async def delete_story(story_id: str, ctx: BoundRequest = Depends(bound_request)):
    ctx.client.table("stories").delete().eq("id", story_id).eq("family_id", ctx.user_id).execute()


@router.get("/{story_id}/pages")
async def list_pages(story_id: str, cursor: str | None = None, limit: int = 20, ctx: BoundRequest = Depends(bound_request)):
    _get_owned_story(ctx, story_id)
    rows = (
        ctx.client.table("pages")
        .select("*")
        .eq("story_id", story_id)
        .order("page_number")
        .limit(min(limit, 100))
        .execute()
        .data
    )
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


def _generate_and_save_page(ctx: BoundRequest, story: dict, page_number: int, body: dict) -> dict:
    """Shared by createPage and regeneratePage: same checks, same tool,
    same upsert -- only how page_number/reference_image_path are chosen
    differs between the two callers."""
    character = _get_story_character(ctx, story)
    scene_description = body["scene_description"]
    caption_text = body["caption_text"]

    story_slug = story["id"]  # stable per-story key for continuity's in-process fact tracking
    for fact_key, fact_value in (body.get("facts") or {}).items():
        check = check_story_fact(story_slug=story_slug, fact_key=fact_key, fact_value=fact_value)
        if check.get("status") == "conflict":
            raise HTTPException(status_code=409, detail=check)

    safety = check_page_safety(page_text=caption_text)
    if not safety.get("passed", True):
        raise HTTPException(status_code=422, detail=safety)

    prior = (
        ctx.client.table("pages")
        .select("image_path")
        .eq("story_id", story["id"])
        .lt("page_number", page_number)
        .order("page_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    reference_image_path = prior[0]["image_path"] if prior else None

    result = generate_page_image(
        scene_description=scene_description,
        character_prompt_fragment=character["prompt_fragment"],
        page_slug=f"{story['id']}_p{page_number}",
        caption_text=caption_text,
        reference_image_path=reference_image_path,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result["content"][0]["text"])

    row = {
        "story_id": story["id"],
        "page_number": page_number,
        "scene_description": scene_description,
        "caption_text": caption_text,
        "image_path": result.get("image_path", ""),
        "image_url": result.get("image_url", ""),
        "is_placeholder": result.get("provider") == "mock",
    }
    return ctx.client.table("pages").upsert(row, on_conflict="story_id,page_number").execute().data[0]


@router.post("/{story_id}/pages", status_code=201)
async def create_page(story_id: str, body: dict, ctx: BoundRequest = Depends(bound_request)):
    story = _get_owned_story(ctx, story_id)
    last = (
        ctx.client.table("pages")
        .select("page_number")
        .eq("story_id", story_id)
        .order("page_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    page_number = (last[0]["page_number"] + 1) if last else 1
    return _generate_and_save_page(ctx, story, page_number, body)


@router.get("/{story_id}/pages/{page_number}")
async def get_page(story_id: str, page_number: int, ctx: BoundRequest = Depends(bound_request)):
    _get_owned_story(ctx, story_id)
    rows = (
        ctx.client.table("pages")
        .select("*")
        .eq("story_id", story_id)
        .eq("page_number", page_number)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Page not found")
    return rows[0]


@router.patch("/{story_id}/pages/{page_number}")
async def regenerate_page(story_id: str, page_number: int, body: dict, ctx: BoundRequest = Depends(bound_request)):
    story = _get_owned_story(ctx, story_id)
    return _generate_and_save_page(ctx, story, page_number, body)
