"""
Per-request Supabase client, authenticated as the requesting user (not a
service-role client) -- Postgres RLS is the actual tenant-isolation
enforcement, so PostgREST/Storage calls must carry that user's own JWT.

UNTESTED against a live Supabase project. `client.postgrest.auth(token)`
is documented supabase-py behavior for scoping subsequent table calls to
a user's own token; whether it also affects `client.storage` calls the
same way has NOT been confirmed against a real response -- verify this
explicitly (upload as one user, confirm a second user's client 403s
reading it) before trusting Storage RLS in a demo. See README.md's
verification checklist.
"""

from __future__ import annotations

import os

from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def client_for(access_token: str) -> Client:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY not configured on the server")
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client
