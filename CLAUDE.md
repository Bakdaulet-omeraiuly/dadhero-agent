# DadHero-Agent -- agent notes

Personalized family comic agent (Strands Agents + Bedrock/Anthropic +
Gemini image generation). See `README.md` for the full picture: safety
design, verified transcripts, status.

## Available skills (installed via the EdgeLab Space "Стек вайбкодера" lesson)

- **Supabase** + **Postgres Best Practices** -- installed via
  `npx skills add supabase/agent-skills` (tracked in `skills-lock.json`;
  re-run that command to restore them after a fresh clone -- the actual
  skill files under `.agents/skills/` and their `.claude/skills/`
  symlinks are gitignored, not committed). Use when migrating
  `dadhero/memory.py`'s local-JSON Story Universe schema (characters,
  places, stories, memories, lessons_taught, progress) to a self-hosted
  Supabase Postgres + Auth + RLS backend for a real multi-user
  platform-with-cabinet rebuild.
- **Superpowers** (Claude Code plugin, `superpowers@claude-plugins-official`,
  installed via `claude plugin install`) -- structured dev methodology
  (design -> plan -> TDD -> review). Useful for the same rebuild; the
  current prototype already has 30 passing pytest cases in `tests/`
  following the same discipline informally.

Not installed (evaluated, not relevant to this project): senior-brainstorm
(architecture was already decided in-session), telegram-bot-builder
(DadHero isn't a Telegram bot).

## REST API design (docs/api/)

`docs/api/design-notes.md` + `docs/api/openapi.yaml` (valid OpenAPI 3.1,
checked with `openapi-spec-validator`) -- the REST API for the
platform-with-cabinet rebuild below, designed using the `mcp-api-build`
skill's domain-model -> resource-inventory -> OpenAPI process (Google
AIP / Stripe conventions). Design only, no server implements it yet.
Despite that skill's name, no MCP server was built or is planned here --
confirmed with the project owner this is REST-only.

Key calls: resources live under `/v1/me/...` (family id comes from the
Supabase JWT, never the URL); a conversational
`POST /me/conversations/{id}/messages` wraps a full agent turn for the
chat UI, alongside plain CRUD resources (characters/stories/pages/etc.)
for a dashboard/gallery view; `check_story_fact`/`check_page_safety` stay
internal (folded into `POST .../pages`), never public endpoints.

## Platform rebuild (platform-with-cabinet format) -- backend built, frontend not started

Per the vibe-coder-stack lesson's classification, a production version of
DadHero is a "platform with cabinet," not a public SEO surface -- the app
itself needs no SEO (CSR is fine), only a separate public landing page
would (SSG/Astro/Cloudflare Pages, if built).

**Built** (`backend/`, see `backend/README.md`): FastAPI implementing
`docs/api/openapi.yaml`'s 12 routes, reusing `dadhero/` (the same Strands
agent/tools/Gemini provider the Streamlit demo runs) unchanged. Three new
pluggable backends selected by env var, mirroring `image_providers.py`'s
existing pattern:
  - `dadhero/memory_backend.py` -- local JSON (`memory.py`, Streamlit) or
    Supabase Postgres (`memory_supabase.py`, platform), selected by
    `DADHERO_MEMORY_BACKEND`.
  - `dadhero/storage.py` -- local disk passthrough or Supabase Storage
    upload, by `DADHERO_STORAGE_BACKEND`.
  - `dadhero/request_context.py` -- a ContextVar holding the
    server-verified `family_id` (never trusted from an LLM tool-call
    argument) and the per-request, user-JWT-scoped Supabase client that
    makes Postgres RLS the actual enforcement boundary.
- Backend stays **Python (FastAPI)**, not the lesson's default Hono+Bun --
  rewriting the Strands agent/tools in TS would discard tested, working
  code for no benefit.
- Schema: `supabase/migrations/0001_init.sql` (characters, places,
  stories, pages, memories, progress_updates, conversation_messages, all
  RLS-scoped to `auth.uid()`).
- **UNTESTED against a live Supabase project** -- backend/README.md has
  the verification checklist (auth round-trip, RLS actually isolates two
  users, Storage signed-URL access, conversation persistence across a
  restart). Do not claim this works in a demo before running it.
- 152-FZ note: only binds if there are Russian Federation citizen users;
  confirm the target audience before deciding server location for that
  data specifically.

**Built** (`frontend/`, see `frontend/README.md`): React + Vite + TypeScript
MVP -- Supabase Auth login/signup (`Login.tsx`), a chat UI at Streamlit-UX
parity (`Chat.tsx`, `MessageBubble.tsx`) calling `backend`'s conversational
endpoint, same visual identity (`styles.css` mirrors `app.py`'s palette
exactly). `npm install && npx tsc -b && npx vite build` all pass clean.
Deliberately no router (two views, branch on session state instead -- see
README for why) and no character/story/place gallery views (backend's CRUD
routes exist, nothing calls them from this frontend yet).

**UNTESTED end-to-end** -- frontend, backend, and the Supabase project all
need to be live together for the first real run; neither README's
verification checklist has been executed. Do both before claiming this
works in a demo.

**Not built:** deployment, a conversation-switcher / past-conversations
list, character/story/place gallery views, and the `pages` table gap noted
in `backend/routers/stories.py`.

**The Streamlit app (`../app.py`) is untouched and remains the verified,
working hackathon submission** -- this backend+frontend pair is new,
additive surface area, not a replacement, until/unless it reaches parity
and is actually verified live.
