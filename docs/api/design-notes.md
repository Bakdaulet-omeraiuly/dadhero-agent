# DadHero REST API — design notes

Applies the `mcp-api-build` skill's **Path A** (domain model → resource
inventory → OpenAPI spec) to DadHero's existing agent capabilities
(`dadhero/tools.py`). This is a design artifact for the platform-with-cabinet
rebuild noted in `CLAUDE.md` — no server implements it yet.

Despite the skill's name, this produces a **REST API only**. No MCP server
is being built here (confirmed with the project owner) — DadHero's tools
stay internal to the Strands agent; the API below is what the React
frontend (and nothing else) talks to.

## Domain model

**Entities:** Family (tenant, implicit via Supabase Auth — not a resource
clients CRUD directly), Character, Place, Story (lifecycle: `draft` →
`finished`), Page (belongs to a Story), Memory, ProgressUpdate,
Conversation/Message.

**Consumer:** one client — the DadHero web app, as an authenticated parent
(Supabase Auth JWT). No third-party API consumers exist or are planned, so
no public developer-facing versioning ceremony beyond `/v1` is warranted
yet.

## Two layers, on purpose

1. **Conversational** — `POST /v1/me/conversations/{id}/messages`. Wraps
   one full Strands agent turn (the natural-language interaction the whole
   product is built around: "my son lost his first tooth today..."). This
   is what the chat UI calls.
2. **Resource CRUD** — plain `characters`/`stories`/`places`/etc.
   endpoints, for a dashboard/gallery view (browse past stories, list
   saved characters) that shouldn't have to replay an agent turn just to
   render a list. Same split OpenAI's Assistants API makes (threads/runs
   for the agent loop, plus direct resource listing).

## What is deliberately NOT public API

`check_story_fact` and `check_page_safety` (see `dadhero/tools.py`) are
internal agent verification steps. They run *inside* the message-handling
and page-generation logic server-side and are never exposed as
client-callable endpoints — a public `POST /check-safety` would let a
client generate a page through some other path and skip it. Verification
is plumbing, not a resource.

## Resource inventory / CRUD matrix

| Resource | List | Get | Create | Update | Delete |
|---|---|---|---|---|---|
| `/v1/me/characters` | ✓ | ✓ | ✓ (text or photo via `source`) | ✓ | ✓ |
| `/v1/me/places` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/v1/me/stories` | ✓ | ✓ | ✓ (creates a `draft`) | ✓ (finish, set `goal`) | ✓ |
| `/v1/me/stories/{id}/pages` | ✓ | ✓ | ✓ (generates + verifies) | ✓ (regenerate) | — |
| `/v1/me/memories` | ✓ | ✓ | ✓ | ✓ (link `used_in_story`) | — |
| `/v1/me/progress-updates` | ✓ | ✓ | ✓ | — | — |
| `/v1/me/conversations/{id}/messages` | ✓ | — | ✓ | — | — |
| `/v1/health` | — | ✓ (public) | — | — | — |

## Design decisions, and why

- **`/v1/me/...`, not `/v1/families/{family_id}/...`.** `family_id` comes
  from the authenticated Supabase JWT, never from the client — the same
  pattern Stripe uses for account-scoped resources reached via the
  request's own auth. Accepting a client-supplied family/tenant id in the
  URL invites IDOR (guess/enumerate another family's id); this closes that
  off structurally rather than relying on remembering an authorization
  check per handler.
- **One creation endpoint per resource, not one per input source.**
  `save_character` and `save_character_from_photo` collapse into a single
  `POST /characters`, discriminated by a `source: "text" | "photo"` field
  — a resource has one creation endpoint; how its data was supplied is a
  request attribute, not a different URL. (The safety branch — refusing a
  photo for a child relationship — happens server-side regardless of
  `source`, per the existing `is_minor_relationship` guard.)
- **Page creation is one atomic operation.** `POST /stories/{id}/pages`
  runs `check_story_fact` → `check_page_safety` → `generate_page_image`
  as one server-side sequence. Three internal tool calls, one client-facing
  request — a client can't reach image generation without the checks
  running first, by construction.
- **Idempotency-Key required** on both `POST /characters` (photo source)
  and `POST .../pages` — both call a paid, non-instant Gemini API call;
  a dropped connection must be retry-safe without generating (and paying
  for) a duplicate image.
- **Cursor pagination everywhere**, not offset — a growing `stories` list
  with offset pagination silently skips/duplicates rows as new stories are
  added between page loads.
- **ETag on `GET /characters/{id}` and `GET /stories/{id}`** for optimistic
  concurrency (two devices editing the same character/story).
- **Photo/drawing upload rides the same `POST`** as `multipart/form-data`,
  not a separate upload-then-reference round trip.
- Snake_case JSON fields, plural nouns, no verbs in URLs, `/v1` version
  prefix, consistent list envelope and error shape — per the skill's REST
  quick-reference.
- The self-host-Supabase and 152-FZ decisions from `CLAUDE.md` are a
  *hosting* concern and don't change this API's shape.

## Not designed here (out of scope for this pass)

- Auth endpoints themselves (signup/login/session) — these are Supabase
  Auth's own REST API, not something DadHero re-implements.
- Billing/subscription tiers — not part of the current product.
- Real-time page-generation progress (SSE/websocket) for a >5s Gemini
  call — worth adding once the endpoint exists to measure actual latency
  against; noted here so it isn't forgotten.
