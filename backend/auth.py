"""
Supabase JWT verification for FastAPI. Extracts the authenticated user's
id (== family_id everywhere in this schema) from the Authorization header
and rejects anything else -- this, not any application-level check, is
step one of the tenant-isolation story (Postgres RLS is step two; see
supabase/migrations/0001_init.sql and dadhero/memory_supabase.py).

UNTESTED against a live Supabase project as of writing. Uses the legacy
shared-secret (HS256) verification path, which every Supabase project
supports; newer projects can additionally issue asymmetric (RS256/ES256)
JWTs via a JWKS endpoint -- if SUPABASE_JWT_SECRET decoding fails on a
real token, check your project's Settings -> API -> JWT Settings for
which signing scheme is active and adjust accordingly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


@dataclass
class AuthedUser:
    user_id: str
    access_token: str  # forwarded to db.client_for() so PostgREST/Storage calls carry this user's own auth, not a service role -- RLS is what actually enforces isolation.


async def get_current_user(authorization: str = Header(...)) -> AuthedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    if not SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET not configured on the server")

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token has no subject")

    return AuthedUser(user_id=user_id, access_token=token)
