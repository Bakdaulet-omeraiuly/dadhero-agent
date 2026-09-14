"""
POST /me/conversations/{conversation_id}/messages -- the endpoint the
whole product runs through. Reconstructs conversation history from
Supabase (so it survives restarts and isn't tied to one server process),
runs one full Strands agent turn via the SAME dadhero.agent.build_agent()
the Streamlit demo uses, and persists both sides of the turn.

UNTESTED against a live Supabase project -- see backend/README.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.deps import BoundRequest, bound_request
from dadhero.agent import build_agent

router = APIRouter(prefix="/me/conversations", tags=["conversations"])


def _to_strands_messages(rows: list[dict]) -> list[dict]:
    role_map = {"parent": "user", "assistant": "assistant"}
    return [{"role": role_map[r["role"]], "content": [{"text": r["content"]}]} for r in rows]


def _extract_tool_calls(agent) -> list[str]:
    return [
        block["toolUse"]["name"]
        for msg in agent.messages
        for block in msg.get("content", [])
        if isinstance(block, dict) and "toolUse" in block
    ]


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    cursor: str | None = None,
    limit: int = 20,
    ctx: BoundRequest = Depends(bound_request),
):
    query = (
        ctx.client.table("conversation_messages")
        .select("*")
        .eq("family_id", ctx.user_id)
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(min(limit, 100))
    )
    rows = query.execute().data
    return {"data": rows, "page_info": {"next_cursor": None, "has_more": False}}


@router.post("/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: str,
    content: str = Form(...),
    attachment: UploadFile | None = File(None),
    ctx: BoundRequest = Depends(bound_request),
):
    if not content.strip() and attachment is None:
        raise HTTPException(status_code=422, detail="content or attachment required")

    history_rows = (
        ctx.client.table("conversation_messages")
        .select("*")
        .eq("family_id", ctx.user_id)
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    initial_messages = _to_strands_messages(history_rows)

    user_text = content
    if attachment is not None:
        # Same pattern as app.py's save_uploaded_file: save to a local temp
        # path and tell the agent the path in plain text -- the LLM never
        # needs to see the image itself, only a tool (save_character_from_photo
        # / stylize_drawing) that reads it as a reference for image generation.
        import tempfile
        from pathlib import Path

        suffix = Path(attachment.filename or "upload.png").suffix or ".png"
        tmp_path = Path(tempfile.gettempdir()) / f"dadhero_upload_{uuid.uuid4().hex}{suffix}"
        tmp_path.write_bytes(await attachment.read())
        user_text += f"\n\n[Uploaded file: {tmp_path}]"

    ctx.client.table("conversation_messages").insert(
        {
            "family_id": ctx.user_id,
            "conversation_id": conversation_id,
            "role": "parent",
            "content": content,
        }
    ).execute()

    agent = build_agent(initial_messages=initial_messages)
    result = agent(user_text)
    reply_text = str(result)
    tool_calls = _extract_tool_calls(agent)

    saved = (
        ctx.client.table("conversation_messages")
        .insert(
            {
                "family_id": ctx.user_id,
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": reply_text,
                "tool_calls": tool_calls,
            }
        )
        .execute()
        .data[0]
    )
    return saved
