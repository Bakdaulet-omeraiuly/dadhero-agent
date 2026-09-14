"""
Supabase JWT verification for FastAPI. Extracts the authenticated user's
id (== family_id everywhere in this schema) from the Authorization header
and rejects anything else -- this, not any application-level check, is
step one of the tenant-isolation story (Postgres RLS is step two; see
supabase/migrations/0001_init.sql and dadhero/memory_supabase.py).

Verified against this project's actual Settings -> API -> JWT Keys page
(not assumed): it uses the NEW asymmetric JWT Signing Keys (ECC P-256),
not the legacy HS256 shared secret -- a static SUPABASE_JWT_SECRET would
NOT have verified these tokens. This fetches the project's public signing
key from its JWKS endpoint instead, keyed by the token's `kid` header, and
verifies with ES256. No shared secret to manage or leak.

If you ever point this at an older project still on "Legacy JWT Secret"
(same Settings -> API -> JWT Keys page, other tab), this will need to
fall back to HS256 with that static secret instead -- check which tab
your project shows before assuming this file is right for it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")

_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL not configured on the server")
        _jwk_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwk_client


@dataclass
class AuthedUser:
    user_id: str
    access_token: str  # forwarded to db.client_for() so PostgREST/Storage calls carry this user's own auth, not a service role -- RLS is what actually enforces isolation.


async def get_current_user(authorization: str = Header(...)) -> AuthedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token has no subject")

    return AuthedUser(user_id=user_id, access_token=token)
