"""GET/POST /me/characters, GET/PATCH/DELETE /me/characters/{id} -- direct
table access for a dashboard view. The chat flow (conversations.py) writes
these same rows via dadhero.tools.save_character* internally; this router
is for reading/editing them without replaying an agent turn.

UNTESTED against a live Supabase project -- see backend/README.md.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from backend.deps import BoundRequest, bound_request
from dadhero.tools import save_character, save_character_from_photo

router = APIRouter(prefix="/me/characters", tags=["characters"])


@router.get("")
async def list_characters(cursor: str | None = None, limit: int = 20, ctx: BoundRequest = Depends(bound_request)):
    rows = (
        ctx.client.table("characters")
        .select("*")
        .eq("family_id", ctx.user_id)
        .order("created_at", desc=True)
        .limit(min(limit, 100))
        .execute()
        .data
    )
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("", status_code=201)
async def create_character(
    character_name: str = Form(...),
    relationship: str = Form(...),
    source: str = Form(...),
    appearance_text: str | None = Form(None),
    role_in_story: str = Form(""),
    photo: UploadFile | None = None,
    ctx: BoundRequest = Depends(bound_request),
):
    """Delegates to the SAME functions the chat agent calls
    (dadhero.tools.save_character / save_character_from_photo) rather than
    reimplementing character creation here -- one place enforces the
    photo-vs-minor-relationship safety rule, not two that could drift."""
    if source == "text":
        if not appearance_text:
            raise HTTPException(status_code=422, detail="appearance_text required when source=text")
        result = save_character(
            character_name=character_name,
            relationship=relationship,
            appearance=appearance_text,
            role_in_story=role_in_story,
            family_id=ctx.user_id,
        )
    elif source == "photo":
        if photo is None:
            raise HTTPException(status_code=422, detail="photo required when source=photo")
        suffix = Path(photo.filename or "photo.png").suffix or ".png"
        tmp_path = Path(tempfile.gettempdir()) / f"dadhero_char_photo_{uuid.uuid4().hex}{suffix}"
        tmp_path.write_bytes(await photo.read())
        result = save_character_from_photo(
            photo_path=str(tmp_path),
            character_name=character_name,
            relationship=relationship,
            role_in_story=role_in_story,
            family_id=ctx.user_id,
        )
    else:
        raise HTTPException(status_code=422, detail="source must be 'text' or 'photo'")

    if isinstance(result, dict) and result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result["content"][0]["text"])
    return result


@router.get("/{character_id}")
async def get_character(character_id: str, ctx: BoundRequest = Depends(bound_request)):
    rows = ctx.client.table("characters").select("*").eq("id", character_id).eq("family_id", ctx.user_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Character not found")
    return rows[0]


@router.patch("/{character_id}")
async def update_character(character_id: str, body: dict, ctx: BoundRequest = Depends(bound_request)):
    allowed = {k: v for k, v in body.items() if k in ("personality_traits", "role_in_story")}
    rows = (
        ctx.client.table("characters")
        .update(allowed)
        .eq("id", character_id)
        .eq("family_id", ctx.user_id)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Character not found")
    return rows[0]


@router.delete("/{character_id}", status_code=204)
async def delete_character(character_id: str, ctx: BoundRequest = Depends(bound_request)):
    ctx.client.table("characters").delete().eq("id", character_id).eq("family_id", ctx.user_id).execute()
