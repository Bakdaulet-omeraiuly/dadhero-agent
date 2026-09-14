"""
POST /me/conversations/{conversation_id}/messages -- the endpoint the
whole product runs through. Reconstructs conversation history from
Supabase (so it survives restarts and isn't tied to one server process),
runs one full Strands agent turn via the SAME dadhero.agent.build_agent()
the Streamlit demo uses, and persists both sides of the turn.

Verified against a live Supabase project -- see backend/README.md.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.deps import BoundRequest, bound_request
from dadhero.agent import build_agent
from dadhero.request_context import current_conversation_id

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


def _extract_tool_pairs(agent, tool_name: str) -> list[tuple[dict, dict]]:
    """(input, output) for every call to `tool_name` in agent.messages, in
    order. A @tool-decorated function's plain-dict return value (no
    "status"/"content" keys of its own, e.g. generate_page_image's) gets
    JSON-serialized into the toolResult's one text content block by
    strands' decorator -- json.loads it back here rather than re-deriving
    the same shape a second way."""
    pending: dict[str, dict] = {}
    pairs: list[tuple[dict, dict]] = []
    for msg in agent.messages:
        for block in msg.get("content", []):
            if not isinstance(block, dict):
                continue
            if "toolUse" in block and block["toolUse"].get("name") == tool_name:
                pending[block["toolUse"]["toolUseId"]] = block["toolUse"].get("input", {})
            elif "toolResult" in block:
                tr = block["toolResult"]
                tool_input = pending.pop(tr.get("toolUseId"), None)
                if tool_input is None:
                    continue
                output: dict = {}
                for c in tr.get("content", []):
                    if isinstance(c, dict) and "text" in c:
                        try:
                            output = json.loads(c["text"])
                        except (json.JSONDecodeError, TypeError):
                            output = {}
                        break
                pairs.append((tool_input, output))
    return pairs


def _sync_pages(ctx: BoundRequest, conversation_id: str, agent) -> None:
    """Reconciles the `pages` table from this conversation's
    generate_page_image tool calls. dadhero/tools.py's generate_page_image
    itself only persists the image FILE (see its docstring) -- deliberately
    kept unchanged so Streamlit's tested tool signature stays untouched.
    Resolves (or creates, as a draft) a `stories` row keyed by
    conversation_id, since pages are usually generated in an earlier turn
    than the one that calls record_finished_story (see
    memory_supabase.record_story's upsert-by-conversation_id).

    Best-effort: any failure here is logged, never raised -- a page-table
    bookkeeping bug must not break the actual comic already delivered to
    the parent in this response."""
    page_calls = _extract_tool_pairs(agent, "generate_page_image")
    if not page_calls:
        return

    existing = (
        ctx.client.table("stories")
        .select("id")
        .eq("family_id", ctx.user_id)
        .eq("conversation_id", conversation_id)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        story_id = existing[0]["id"]
    else:
        story_id = (
            ctx.client.table("stories")
            .insert(
                {
                    "family_id": ctx.user_id,
                    "conversation_id": conversation_id,
                    "title": "Untitled story",
                    "template_key": "unknown",
                    "status": "draft",
                }
            )
            .execute()
            .data[0]["id"]
        )

    seen_slugs: dict[str, int] = {}
    rows = []
    for tool_input, tool_output in page_calls:
        if not tool_output.get("image_url"):
            continue  # this call errored (see generate_page_image's own error branch) -- nothing to persist
        slug = tool_input.get("page_slug", "")
        if slug not in seen_slugs:
            seen_slugs[slug] = len(seen_slugs) + 1
        rows.append(
            {
                "story_id": story_id,
                "page_number": seen_slugs[slug],
                "scene_description": tool_input.get("scene_description", ""),
                "caption_text": tool_input.get("caption_text") or "",
                "image_path": tool_output.get("image_path", ""),
                "image_url": tool_output.get("image_url", ""),
                "is_placeholder": tool_output.get("provider") == "mock",
            }
        )
    if rows:
        ctx.client.table("pages").upsert(rows, on_conflict="story_id,page_number").execute()


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
    token = current_conversation_id.set(conversation_id)
    try:
        result = agent(user_text)
    finally:
        current_conversation_id.reset(token)
    reply_text = str(result)
    tool_calls = _extract_tool_calls(agent)

    try:
        _sync_pages(ctx, conversation_id, agent)
    except Exception:  # noqa: BLE001 -- see _sync_pages' docstring: never break the reply over this
        pass

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
