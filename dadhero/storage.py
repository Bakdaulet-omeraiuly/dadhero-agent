"""
Where a generated image FILE ends up, separate from which model generated
it (image_providers.py) and which family it belongs to (memory_backend.py).

A deployed backend cannot rely on local disk the way the Streamlit demo
does -- a second server instance, a redeploy, or just a container restart
loses anything written to data/generated_pages/. Selected the same way as
the other two axes: DADHERO_STORAGE_BACKEND=local|supabase.

UNTESTED against a live Supabase Storage bucket as of writing -- same
"verify before trusting it in a demo" discipline as the rest of the
platform code. See backend/README.md for the standalone check to run.
"""

from __future__ import annotations

import os
from pathlib import Path

from dadhero.request_context import current_family_id, current_supabase_client

_BUCKET = "dadhero-pages"


def persist(local_path: str) -> str:
    """Return the path/URL callers should store and render. Local backend:
    unchanged, returns local_path as-is. Supabase backend: uploads the file
    to Storage under this family's own prefix and returns a signed URL."""
    backend = os.environ.get("DADHERO_STORAGE_BACKEND", "local").lower()
    if backend != "supabase":
        return local_path

    client = current_supabase_client.get()
    if client is None:
        raise RuntimeError("No Supabase client bound to this request for storage upload.")

    fid = current_family_id.get()
    filename = Path(local_path).name
    storage_path = f"{fid}/{filename}"

    with open(local_path, "rb") as f:
        client.storage.from_(_BUCKET).upload(
            storage_path, f, {"content-type": "image/png", "upsert": "true"}
        )

    signed = client.storage.from_(_BUCKET).create_signed_url(storage_path, 60 * 60 * 24 * 7)
    return signed["signedURL"]
