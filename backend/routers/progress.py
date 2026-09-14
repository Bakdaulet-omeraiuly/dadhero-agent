"""GET/POST /me/progress-updates. UNTESTED against a live Supabase
project -- see backend/README.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import BoundRequest, bound_request

router = APIRouter(prefix="/me/progress-updates", tags=["progress-updates"])


@router.get("")
async def list_progress_updates(
    related_to: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
    ctx: BoundRequest = Depends(bound_request),
):
    query = ctx.client.table("progress_updates").select("*").eq("family_id", ctx.user_id)
    if related_to:
        query = query.eq("related_to", related_to)
    rows = query.order("created_at", desc=True).limit(min(limit, 100)).execute().data
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("", status_code=201)
async def create_progress_update(body: dict, ctx: BoundRequest = Depends(bound_request)):
    row = {
        "family_id": ctx.user_id,
        "related_to": body["related_to"],
        "update_text": body["update_text"],
        "story_id": body.get("story_id"),
    }
    return ctx.client.table("progress_updates").insert(row).execute().data[0]
