"""GET/POST /me/memories, PATCH /me/memories/{id} (link to a story).
UNTESTED against a live Supabase project -- see backend/README.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import BoundRequest, bound_request

router = APIRouter(prefix="/me/memories", tags=["memories"])


@router.get("")
async def list_memories(cursor: str | None = None, limit: int = 20, ctx: BoundRequest = Depends(bound_request)):
    rows = (
        ctx.client.table("memories")
        .select("*")
        .eq("family_id", ctx.user_id)
        .order("created_at", desc=True)
        .limit(min(limit, 100))
        .execute()
        .data
    )
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("", status_code=201)
async def create_memory(body: dict, ctx: BoundRequest = Depends(bound_request)):
    row = {"family_id": ctx.user_id, "text": body["text"]}
    return ctx.client.table("memories").insert(row).execute().data[0]


@router.patch("/{memory_id}")
async def link_memory_to_story(memory_id: str, body: dict, ctx: BoundRequest = Depends(bound_request)):
    story_id = body.get("used_in_story_id")
    if not story_id:
        raise HTTPException(status_code=422, detail="used_in_story_id required")
    rows = (
        ctx.client.table("memories")
        .update({"used_in_story_id": story_id})
        .eq("id", memory_id)
        .eq("family_id", ctx.user_id)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Memory not found")
    return rows[0]
