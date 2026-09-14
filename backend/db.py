"""
Per-request Supabase client, authenticated as the requesting user (not a
service-role client) -- Postgres RLS is the actual tenant-isolation
enforcement, so PostgREST/Storage calls must carry that user's own JWT.

CONFIRMED against a live Supabase project that `client.postgrest.auth(token)`
alone is NOT enough: it only updates postgrest's own httpx session, while
`client.storage` is a separate sub-client lazily built (and cached) from
`client.options.headers` the first time it's accessed -- calling
`.postgrest.auth()` never touches that dict, so storage uploads kept going
out under the anon/publishable key and got a 403 from the RLS policy on
storage.objects (no `auth.uid()` to match against). Confirmed by reading
supabase-py's `SyncClient.create`/`_get_auth_headers`/`_listen_to_auth_events`
(supabase/_sync/client.py): every sub-client (postgrest, storage,
functions) is built from `self.options.headers["Authorization"]`, so
setting that directly -- before either sub-client has been touched, since
each is created once and cached -- covers both correctly.
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
    # Must happen before client.postgrest / client.storage is first
    # accessed anywhere (both are lazily built from this dict and then
    # cached) -- see module docstring.
    client.options.headers["Authorization"] = f"Bearer {access_token}"
    return client
