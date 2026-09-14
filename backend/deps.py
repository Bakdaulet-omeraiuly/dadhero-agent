"""
Binds one request's authenticated identity into dadhero/request_context.py
BEFORE any route handler runs the agent or touches memory_backend --
that's what makes memory_supabase.py's family_id enforcement real instead
of decorative. Every route that touches the Story Universe depends on
`bound_request`, not `auth.get_current_user` directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from supabase import Client

from backend import db
from backend.auth import AuthedUser, get_current_user
from dadhero.request_context import current_family_id, current_supabase_client


@dataclass
class BoundRequest:
    user_id: str
    client: Client


async def bound_request(user: AuthedUser = Depends(get_current_user)) -> BoundRequest:
    client = db.client_for(user.access_token)

    family_token = current_family_id.set(user.user_id)
    client_token = current_supabase_client.set(client)
    try:
        yield BoundRequest(user_id=user.user_id, client=client)
    finally:
        current_family_id.reset(family_token)
        current_supabase_client.reset(client_token)
