# DadHero platform backend (FastAPI)

Reuses `dadhero/` -- the exact same Strands agent, tools, and Gemini image
provider the Streamlit demo runs -- behind a REST API backed by Supabase
(Postgres + Auth + Storage) instead of local JSON/disk. **The Streamlit
app (`../app.py`) is untouched and still works** -- this is new, separate
surface area, not a replacement of the tested submission.

## Status: verified end-to-end against a live Supabase project (2026-09-14)

All four items in the checklist below have been run against a real
Supabase project (JWKS/ES256 auth, RLS isolation between two real users,
Storage upload + signed URL + cross-user denial, and a full conversational
turn through `POST /me/conversations/{id}/messages`) -- not simulated.
See "Storage auth bug found and fixed" below for the one real bug this
surfaced.

## Setup

1. Create a Supabase project (dashboard, free tier is fine for a demo):
   https://supabase.com/dashboard -- note the Project URL and (Settings ->
   API -> API Keys) the **Publishable key** (`sb_publishable_...`). Check
   Settings -> API -> JWT Keys: if it shows the **JWT Signing Keys** tab
   (asymmetric, ECC P-256), `auth.py` verifies via JWKS and needs nothing
   else. If it shows **Legacy JWT Secret** instead (older projects), you'd
   need to add HS256 verification back -- see `auth.py`'s docstring.
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
SUPABASE_ANON_KEY=sb_publishable_...  # Settings -> API -> API Keys -> Publishable key
GEMINI_API_KEY=...                    # same key the Streamlit app uses
DADHERO_CORS_ORIGINS=http://localhost:5173
```

No JWT secret to set -- `auth.py` verifies via the project's public JWKS
endpoint, derived from `SUPABASE_URL` alone (see its docstring for the
legacy-project fallback case).

`backend/main.py` forces `DADHERO_MEMORY_BACKEND=supabase` and defaults
`DADHERO_STORAGE_BACKEND`/`DADHERO_IMAGE_PROVIDER` to `supabase`/`gemini`
regardless of `.env` -- a platform backend silently falling back to local
JSON/disk would be a much worse failure than refusing to start without
real Supabase credentials.

## Verification checklist (all four run against a real project)

Same discipline as `image_providers.GeminiImageProvider` before it had
produced a real image -- architecture being sound is not the same claim
as it working.

1. **Auth round-trip** -- DONE. Signed up/admin-confirmed a test user,
   got a real ES256 `access_token`, `GET /me/characters` with
   `Authorization: Bearer <token>` returned `200` with an empty list.
2. **RLS actually isolates** -- DONE. Two real users; user B's
   `GET /me/characters` never sees user A's rows. This is the one check
   that matters most -- everything else is convenience, this is the
   security boundary.
3. **Storage path** -- DONE, after fixing a real bug (see below). A
   generated page image uploads to Storage, its signed `image_url`
   resolves to a real viewable PNG, and a second authenticated user's
   client gets a 404 (not the file) trying to read the same object path
   directly.
4. **Conversation persistence** -- exercised indirectly: a full
   conversational turn (`POST /me/conversations/{id}/messages`) correctly
   reconstructed an empty-then-growing history from
   `conversation_messages` and produced a real 2-page Gemini-illustrated
   story with narration burned into the art. A same-process restart
   mid-conversation hasn't been additionally tested, but the mechanism
   (fetch-then-replay from Postgres, no in-memory Agent kept alive) is
   the same code path either way.

### Storage auth bug found and fixed

`db.py`'s `client_for()` originally called `client.postgrest.auth(token)`
only, which scopes *just* the postgrest sub-client. `client.storage` is a
separate lazily-built sub-client cached from `client.options.headers` --
`.postgrest.auth()` never touches that dict, so every Storage call kept
going out under the anon/publishable key and got `403: new row violates
row-level security policy` even with a correct RLS policy on
`storage.objects` in place (confirmed via `supabase-py`'s own
`SyncClient.create`/`_get_auth_headers` source). Fix: set
`client.options.headers["Authorization"] = f"Bearer {access_token}"`
directly, before either sub-client is first touched -- that's what both
postgrest and storage actually read from. See `db.py`'s docstring.

## Deploying (Render.com, free tier)

`backend/Dockerfile` builds from the repo root (it needs to `COPY
dadhero/` alongside `backend/`), so on Render: New -> Web Service -> pick
this repo -> set **Root Directory** to the repo root (not `backend/`) and
**Dockerfile Path** to `backend/Dockerfile`. Add the same four env vars
from `.env.example` above in Render's dashboard (never commit real
values). Any host that deploys an arbitrary Dockerfile works the same way
(Railway, Fly.io) -- Render is just free-tier-friendly and needs no CLI
setup beyond connecting the GitHub repo.

`frontend/`'s `npm run build` output (`frontend/dist/`) is plain static
files -- Cloudflare Pages: New project -> this repo -> **Build command**
`npm run build`, **Build output directory** `frontend/dist`, **Root
directory** `frontend`, plus the three `VITE_*` env vars from its
`.env.example`.

Neither of these has actually been deployed yet -- config is written and
believed correct, not run. Do it after the live-Supabase verification
checklists above pass locally, not before (deploying something unverified
just moves the same unknowns to a slower feedback loop).

## Known gaps (stated plainly, see individual file docstrings)

- `pages` table is never written to -- `dadhero/tools.py`'s
  `generate_page_image` persists the image file but not a page row (see
  `routers/stories.py`'s docstring for why this wasn't closed under time
  pressure, and the two ways to close it properly).
- `POST`/`PATCH .../pages` (direct client-triggered page generation,
  bypassing the chat flow) from the OpenAPI spec are unimplemented -- all
  page generation currently happens inside an agent turn.
- Deployment is configured (`backend/Dockerfile`, see above) but not
  actually deployed anywhere yet.
