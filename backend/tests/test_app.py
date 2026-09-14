"""
Structural + auth-boundary tests that don't need a live Supabase project.
Confirms the app builds with the full expected route table and that every
protected route actually rejects an unauthenticated request -- the one
thing that must never silently regress, since auth.py + deps.py are the
first half of this platform's tenant-isolation story (Postgres RLS in
supabase/migrations/0001_init.sql is the second half, and can't be tested
without a live project -- see backend/README.md's checklist for that).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

EXPECTED_PATHS = {
    "/health",
    "/me/characters",
    "/me/characters/{character_id}",
    "/me/places",
    "/me/places/{place_id}",
    "/me/stories",
    "/me/stories/{story_id}",
    "/me/stories/{story_id}/pages",
    "/me/stories/{story_id}/pages/{page_number}",
    "/me/memories",
    "/me/memories/{memory_id}",
    "/me/progress-updates",
    "/me/conversations/{conversation_id}/messages",
}

PROTECTED_GET_PATHS = [
    "/me/characters",
    "/me/characters/abc",
    "/me/places",
    "/me/stories",
    "/me/stories/abc/pages",
    "/me/stories/abc/pages/1",
    "/me/memories",
    "/me/progress-updates",
    "/me/conversations/abc/messages",
]


def test_all_designed_routes_exist():
    schema = app.openapi()
    assert set(schema["paths"].keys()) == EXPECTED_PATHS


def test_health_is_public():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_protected_routes_reject_missing_auth_header():
    for path in PROTECTED_GET_PATHS:
        resp = client.get(path)
        assert resp.status_code in (401, 422), f"{path} should require auth, got {resp.status_code}"


def test_protected_routes_reject_garbage_token():
    headers = {"Authorization": "Bearer not-a-real-jwt"}
    for path in PROTECTED_GET_PATHS:
        resp = client.get(path, headers=headers)
        assert resp.status_code in (401, 500), f"{path} should reject a bogus token, got {resp.status_code}"


def test_bearer_prefix_is_required():
    resp = client.get("/me/characters", headers={"Authorization": "not-bearer-scheme"})
    assert resp.status_code == 401
