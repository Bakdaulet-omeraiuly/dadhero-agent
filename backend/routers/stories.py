"""GET/POST /me/stories, GET/PATCH/DELETE /me/stories/{id}, and a
read-only GET /me/stories/{id}/pages.

KNOWN GAP, stated plainly rather than glossed over: dadhero/tools.py's
generate_page_image does NOT currently write a row into the `pages` table
-- it only generates the image and persists the FILE (via storage.py).
Nothing populates `pages` yet, so list_pages will return empty even for a
story the chat flow just illustrated. Closing this means either having
conversations.py parse generate_page_image's tool results out of
agent.messages after each turn and insert them here, or giving the tool
itself a Supabase-aware write path -- deliberately not built under the
time this rebuild had; see README.md's task list.

The OpenAPI spec's POST/PATCH .../pages (direct client-triggered
generation, bypassing the chat) are unimplemented for the same reason.
UNTESTED against a live Supabase project -- see backend/README.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import BoundRequest, bound_request

router = APIRouter(prefix="/me/stories", tags=["stories"])


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
    owns = ctx.client.table("stories").select("id").eq("id", story_id).eq("family_id", ctx.user_id).execute().data
    if not owns:
        raise HTTPException(status_code=404, detail="Story not found")
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
