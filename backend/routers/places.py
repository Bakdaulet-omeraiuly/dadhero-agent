"""GET/POST /me/places, GET/PATCH/DELETE /me/places/{id}. UNTESTED against
a live Supabase project -- see backend/README.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import BoundRequest, bound_request

router = APIRouter(prefix="/me/places", tags=["places"])


@router.get("")
async def list_places(cursor: str | None = None, limit: int = 20, ctx: BoundRequest = Depends(bound_request)):
    rows = (
        ctx.client.table("places")
        .select("*")
        .eq("family_id", ctx.user_id)
        .order("created_at", desc=True)
        .limit(min(limit, 100))
        .execute()
        .data
    )
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("", status_code=201)
async def create_place(body: dict, ctx: BoundRequest = Depends(bound_request)):
    row = {"family_id": ctx.user_id, "place_name": body["place_name"], "description": body["description"]}
    return ctx.client.table("places").insert(row).execute().data[0]


@router.get("/{place_id}")
async def get_place(place_id: str, ctx: BoundRequest = Depends(bound_request)):
    rows = ctx.client.table("places").select("*").eq("id", place_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Place not found")
    return rows[0]


@router.patch("/{place_id}")
async def update_place(place_id: str, body: dict, ctx: BoundRequest = Depends(bound_request)):
    allowed = {k: v for k, v in body.items() if k in ("place_name", "description")}
    rows = ctx.client.table("places").update(allowed).eq("id", place_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Place not found")
    return rows[0]


@router.delete("/{place_id}", status_code=204)
async def delete_place(place_id: str, ctx: BoundRequest = Depends(bound_request)):
    ctx.client.table("places").delete().eq("id", place_id).eq("family_id", ctx.user_id).execute()
