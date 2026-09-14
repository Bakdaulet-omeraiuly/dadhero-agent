"""
Request-scoped identity for the platform (FastAPI) backend.

Why this exists: tools.py's functions take `family_id` as an ordinary
parameter with a default, because Strands lets the LLM choose any
argument value for a tool call. That's fine for the local-JSON,
single-tenant Streamlit demo, but it would be a real security bug for a
multi-tenant backend -- an LLM (via a crafted prompt, or just an
adversarial user) deciding which tenant's row to read or write is not
something the API layer should trust.

The FastAPI request handler sets this ContextVar to the Supabase-verified
`auth.uid()` BEFORE invoking the agent for that request; memory_supabase.py
reads it directly and ignores whatever family_id value the LLM's tool call
happened to pass. Untouched for the Streamlit app (local memory.py never
imports this), which keeps trusting the parameter -- correct for a single
local user with nothing to isolate from.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

current_family_id: ContextVar[str] = ContextVar("current_family_id", default="default_family")

# Holds a Supabase client already authenticated as the requesting user (its
# PostgREST calls carry the user's own JWT), so Postgres RLS -- not just
# this contextvar -- is the actual enforcement boundary. Typed Any rather
# than importing `supabase` here so dadhero/ has no hard dependency on it
# for the Streamlit (local-JSON) path.
current_supabase_client: ContextVar[Any] = ContextVar("current_supabase_client", default=None)

# The platform-conversation this agent turn belongs to, if any. Lets
# memory_supabase.py's record_story() upsert the SAME stories row that
# backend/routers/conversations.py's page-sync already created as a draft
# (pages are normally generated in an earlier turn than the one that
# calls record_finished_story) instead of inserting a second, duplicate
# row. None for Streamlit and for any request that isn't inside a
# conversational turn (e.g. the direct pages/{id} routes set their own
# story row directly and never touch this).
current_conversation_id: ContextVar[str | None] = ContextVar("current_conversation_id", default=None)
