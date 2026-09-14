# DadHero platform backend (FastAPI)

Reuses `dadhero/` -- the exact same Strands agent, tools, and Gemini image
provider the Streamlit demo runs -- behind a REST API backed by Supabase
(Postgres + Auth + Storage) instead of local JSON/disk. **The Streamlit
app (`../app.py`) is untouched and still works** -- this is new, separate
surface area, not a replacement of the tested submission.

## Status: architecture complete, UNTESTED against a live Supabase project

Every piece here compiles, the route table matches `../docs/api/openapi.yaml`,
and the underlying agent/tools are the same ones verified extensively
against real Anthropic + Gemini calls (see the main README). What hasn't
been run yet is the actual Supabase wiring -- `memory_supabase.py`,
`storage.py`'s Supabase path, and `db.py`/`auth.py`'s JWT handling. Do the
checklist below with a real project before demoing this.

## Setup

1. Create a Supabase project (dashboard, free tier is fine for a demo):
   https://supabase.com/dashboard -- note the Project URL, `anon` public
   key, and (Settings -> API -> JWT Settings) the JWT secret.
2. Apply the schema:
   ```bash
   # via the Supabase CLI, from the repo root
   supabase link --project-ref <your-project-ref>
   supabase db push   # applies supabase/migrations/0001_init.sql
   ```
   or paste `supabase/migrations/0001_init.sql`'s contents into the
   dashboard's SQL Editor and run it once.
3. Create a Storage bucket named `dadhero-pages` (Storage -> New bucket,
   private) -- `dadhero/storage.py` uploads under `{family_id}/{filename}`
   and reads back via a signed URL, so the bucket itself does not need to
   be public.
4. `cp .env.example .env` (see below) and fill in the four Supabase values.
5. ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn backend.main:app --reload --port 8000   # run from the repo root
   ```

## `.env` (backend/.env, or exported)

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=...              # Settings -> API -> JWT Settings
GEMINI_API_KEY=...                    # same key the Streamlit app uses
DADHERO_CORS_ORIGINS=http://localhost:5173
```

`backend/main.py` forces `DADHERO_MEMORY_BACKEND=supabase` and defaults
`DADHERO_STORAGE_BACKEND`/`DADHERO_IMAGE_PROVIDER` to `supabase`/`gemini`
regardless of `.env` -- a platform backend silently falling back to local
JSON/disk would be a much worse failure than refusing to start without
real Supabase credentials.

## Verification checklist (do this before trusting it in a demo)

Same discipline as `image_providers.GeminiImageProvider` before it had
produced a real image -- architecture being sound is not the same claim
as it working.

1. **Auth round-trip**: sign up a test user via the Supabase JS client or
   `curl -X POST {SUPABASE_URL}/auth/v1/signup`, get back an
   `access_token`, and confirm `GET /me/characters` with
   `Authorization: Bearer <token>` returns `200` with an empty list (not
   a 401/500).
2. **RLS actually isolates**: create two test users, save a character as
   user A, confirm user B's `GET /me/characters` does NOT see it. This is
   the one check that matters most -- everything else is convenience,
   this is the security boundary.
3. **Storage path**: send a message with a photo attachment, confirm the
   `characters` row's `reference_image_path` (local) and the returned
   `image_url` (signed Supabase Storage URL) both resolve to a real,
   viewable image -- and that a *different* authenticated user's client
   cannot read that same signed URL's underlying object directly (see
   `db.py`'s docstring -- whether `postgrest.auth()` scoping extends to
   `client.storage` calls the same way has not been confirmed).
4. **Conversation persistence**: send two messages in the same
   `conversation_id`, restart the `uvicorn` process, send a third --
   confirm the agent's reply references context from before the restart
   (proves history reconstruction from `conversation_messages` works, not
   just in-memory state that happened to survive).

## Known gaps (stated plainly, see individual file docstrings)

- `pages` table is never written to -- `dadhero/tools.py`'s
  `generate_page_image` persists the image file but not a page row (see
  `routers/stories.py`'s docstring for why this wasn't closed under time
  pressure, and the two ways to close it properly).
- `POST`/`PATCH .../pages` (direct client-triggered page generation,
  bypassing the chat flow) from the OpenAPI spec are unimplemented -- all
  page generation currently happens inside an agent turn.
- No frontend yet consumes this API.
- Deployment (this needs a persistent Python process, not static
  hosting -- Render/Railway/Fly.io are reasonable free-tier options) is
  not set up.
