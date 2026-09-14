# DadHero-Agent -- agent notes

Personalized family comic agent (Strands Agents + Bedrock/Anthropic +
Gemini image generation). See `README.md` for the full picture: safety
design, verified transcripts, status.

## Agentic pipeline expansion (2026-09-14)

Extended the agent from "chat that makes a comic" toward the full
"intelligent story agent" spec: plans explicitly, verifies its own
output, and revises only what needs revising. All additive -- no
existing tool signature changed, `tests/` all still pass (39 now, was
30), Streamlit's UI structure/layout untouched per the request that
prompted this ("keep the current UI style... existing functionality").

**New tools** (`dadhero/tools.py`, wired into `agent.py`'s tool list +
system prompt workflow):
- `create_story_plan` -- records the page-by-page outline (title,
  template, page_beats, goal) the agent already worked out, BEFORE any
  image generation starts. Same propose-then-record shape
  `save_character`/`check_story_fact` already use -- doesn't do the
  creative planning FOR the agent, just makes it a real, inspectable
  checkpoint (visible in the Workshop panel) instead of reasoning that
  only ever existed inside one model response. Hard-caps at 16 pages.
- `check_visual_consistency` (`dadhero/vision_check.py`) -- an
  independent Gemini vision call comparing a just-generated page against
  the character's reference image, separate from the call that drew the
  page. Fails OPEN (`consistent: true`) whenever there's nothing
  meaningful to check: mock image provider, missing files, no API key,
  or the check call itself erroring -- a checker failure must never
  block a page the parent is waiting on.
- `audit_story_continuity` -- a final read-through of everything
  `check_story_fact` recorded for a story, called once after the last
  page. Catches cross-fact inconsistency `check_story_fact` alone can't
  (it only catches the SAME key changing value, not two different facts
  quietly contradicting each other).
- `generate_page_image` gained an `is_cover: bool = False` param
  (backward compatible, default False) -- every story now opens with a
  generated cover (title text, hero prominent) before page 1, and every
  page's `reference_image_path` chains from the COVER now, not page 1.

**Parent controls** (`app.py` sidebar, "⚙️ Story settings" expander):
child age, tone, length (short/medium/long -> page-count guidance),
scary/tension level, educational goal, characters to include/avoid.
Building `[Parent settings: ...]` and prepending it to the next message
only (never shown in the parent's own chat bubble) -- `agent.py`'s
system prompt has a dedicated section instructing the agent to treat
every value present as a hard constraint for that turn, then strip the
bracketed line before reading the rest as the parent's actual words.

**Story series**: a "🔮 Continue this adventure" button appears once
there's at least one assistant reply -- reuses the system prompt's
existing case 2a (now split out: a "continue" request reuses the saved
character/places instead of re-describing them, and gets a title that
reads as the next book in the same series).

**Safety**: `dadhero/safety.py`'s term list extended (bullying,
dangerous real-world instructions a child could copy, adult themes) --
still a deterministic keyword/heuristic screen, not full LLM-grade
moderation; stated plainly rather than oversold.

**Real comic-page style conditioning (2026-09-14)**: `generate_page_image`
gained an optional `art_style` param (the exact ART_STYLES label, same
value already passed to `save_character`/`stylize_drawing`). When it's
"Comic book", a real public-domain golden-age comic-book page (verified
individually on Wikimedia Commons, each with its own stated PD
rationale -- see `dadhero/assets/comic_refs/LICENSES.md`) is sent to
Gemini alongside the character reference image, explicitly framed as a
panel/inking/composition reference only ("ignore its actual characters
and story entirely") so it can't be confused with the character
reference. Deliberately scoped to ONE style (`dadhero/comic_style_refs.py`)
-- these are golden-age comic-book scans, not generic art references;
forcing them onto watercolor/claymation/pixel-art etc. would be a style
mismatch, not an enhancement. `ImageProvider.generate()` gained a
matching `style_reference_image_path` param (optional, both providers
handle `None` the same as before -- fully backward compatible).

**Seeded example content (2026-09-14)**: `dadhero/seed.py` fills
`data/family_memory.json`/`data/generated_pages/` with a couple of
polished example characters/books -- but ONLY when
`data/family_memory.json` doesn't exist yet, never overwriting real
data. This matters because that path (and `data/generated_pages/`) is
gitignored real runtime data -- a fresh Streamlit Cloud container (or a
fresh local clone) starts with neither, so without seeding, a judge's
first look at the live demo was an empty Story Universe. `data/seed/`
itself (unlike `data/family_memory.json`/`data/generated_pages/`) IS
committed to git -- see `.gitignore`, no change needed there since it's
a different path entirely. Image paths inside the seed files are
BASENAMES ONLY, resolved against the CURRENT `OUTPUT_DIR` at
seed-apply time -- never trust an absolute path baked in on whatever
machine generated the seed content. `app.py` calls
`seed.ensure_seeded()` once (alongside building the agent) and
`seed.get_seed_story_library()` every new session (the Story Library is
session-only by design, so this runs every time, not just once;
returns `[]` harmlessly with no seed file present).

**Deliberately deferred** (stated plainly, not silently dropped): PDF/
image-bundle export (`export_book`) -- no dependency gap (Pillow, already
a dependency, can compose a multi-page PDF from the saved PNGs) but no
demo-critical value under the time this had; an explicit `parse_parent_intent`
tool -- redundant with what the system prompt's own step 3 already does
inside one model turn, splitting it into a second tool call would add
latency with no new capability; renaming existing tools to match every
requested name 1:1 (e.g. `get_family_memory` -> `load_child_profile`) --
pure relabeling risk for zero functional gain against a system prompt
that already references the current names carefully throughout.

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
  RLS-scoped to `auth.uid()`) + `0002_storage_policies.sql` (RLS on
  `storage.objects`, since a private bucket has none by default).
- **Verified against a live Supabase project (2026-09-14)** --
  backend/README.md's full checklist passed: JWKS/ES256 auth, RLS
  isolation between two real users, Storage upload + signed URL + 404 for
  a different user, and a full conversational turn producing a real
  2-page Gemini-illustrated story persisted end-to-end. Found and fixed
  one real bug along the way: `client.postgrest.auth(token)` doesn't
  scope `client.storage` (separate sub-client, its own cached auth
  headers) -- see `backend/db.py`'s docstring.
- Model provider: `DADHERO_MODEL_PROVIDER=gemini` for both text and
  images on the platform backend (Anthropic key ran out of credit
  mid-session; `dadhero/agent.py`'s `_resolve_model()` gained a `gemini`
  branch via `strands.models.gemini.GeminiModel`). Streamlit's `.env`
  still defaults to Anthropic/Bedrock, unaffected.
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

**Backend+Supabase verified (see above); frontend not yet run against
them** -- the React app itself still hasn't been started against the now-
verified live backend+Supabase pair (only `npm run build` type-checked
cleanly). `frontend/README.md`'s checklist is the remaining unverified
piece.

**Closed since the initial rebuild:** the `pages` table gap (
`backend/routers/conversations.py`'s `_sync_pages` reconciles it from the
agent's own tool-call history after each turn; `dadhero/tools.py` itself
stays unchanged), the OpenAPI spec's direct `POST`/`PATCH .../pages`
routes (reuse the same `check_story_fact`/`check_page_safety`/
`generate_page_image` functions the chat agent calls), and read-only
character/story/place gallery views in the frontend (`Gallery.tsx`, a tab
next to Chat -- still no router, just a second local view). Needs
`supabase/migrations/0003_pages_gap.sql` applied.

**Not built:** deployment, a conversation-switcher / past-conversations
list.

**The Streamlit app (`../app.py`) is untouched and remains the verified,
working hackathon submission** -- this backend+frontend pair is new,
additive surface area, not a replacement, until/unless it reaches parity
and is actually verified live.

## In-browser sketch canvas (`streamlit-drawable-canvas`)

`app.py`'s "Draw a sketch" expander lets a parent/child draw directly in
the browser instead of needing an external drawing app + file upload,
feeding the result into the existing (unchanged) `stylize_drawing` tool.

Compatibility was NOT assumed -- `streamlit-drawable-canvas` (last
released 2023) is known to lag behind Streamlit's own component
protocol. Verified directly before adding it to `requirements.txt`:
an isolated test app showed a genuinely blank canvas on first install (no
console error, no failed network request, zero `<canvas>` elements --
a real, confirmed incompatibility symptom, not a false alarm) on one
run, then rendered and captured real strokes correctly (`image_data`
shape `(300, 300, 4)`, later `(320, 480, 4)` in the real integration)
on a clean reinstall. Re-tested inside the actual app afterward via
Playwright: draw -> "Use this drawing" -> the saved PNG is a real,
correctly-flattened (transparent canvas composited onto white, not
left transparent/black) sketch on disk, ready for `stylize_drawing`
exactly like an uploaded file. If this ever regresses again after a
`streamlit`/`streamlit-drawable-canvas` version bump, don't assume it
still works -- repeat this same check (isolated test app, real mouse
strokes via Playwright, inspect the saved file) before trusting it.

**It regressed (2026-09-14).** `requirements.txt` pins no upper bound on
either package, and a routine local/Cloud reinstall pulled a
`streamlit-drawable-canvas==0.13.0` whose own `__init__.py` now calls
`st.components.v2.component(...)` unconditionally -- confirmed broken
(reproduced directly) against every Streamlit version tried, 1.40
through 1.63: `StreamlitAPIException: Component
'streamlit-drawable-canvas.streamlit_drawable_canvas' must be declared
in pyproject.toml with asset_dir to use file-backed css`, raised at
**import time**, i.e. `from streamlit_drawable_canvas import st_canvas`
alone crashes before any UI code runs. No version combination tried
fixed it -- this looks like a real packaging bug in the current PyPI
release, not a pin problem. Since a top-level import crash would have
taken the *entire app* down (not just the drawing feature) on the next
cold start/redeploy, `app.py` now wraps that import in `try/except`
(`CANVAS_AVAILABLE` flag) and the "Draw a sketch" expander shows a
plain "upload a photo instead" fallback message when it's unavailable,
instead of crashing. Re-run the same verification checklist above
before ever removing that guard.
