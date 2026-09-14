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

## Planned rebuild (platform-with-cabinet format, not yet started)

Per the vibe-coder-stack lesson's classification, a production version of
DadHero is a "platform with cabinet," not a public SEO surface -- the app
itself needs no SEO (CSR is fine), only a separate public landing page
would (SSG/Astro/Cloudflare Pages, if built).

- Frontend: React + Vite (CSR) + TanStack Router/Query/Form.
- Backend: **stays Python (FastAPI)**, not the lesson's default
  Hono+Bun -- `dadhero/agent.py`'s Strands Agent and tools are Python;
  rewriting them in TS would discard tested, working code for no benefit.
- DB/Auth: self-host Supabase (Postgres + Auth + RLS), replacing
  `data/family_memory.json` and its hardcoded single `default_family`.
- File storage: Supabase Storage, replacing `data/generated_pages/`.
- 152-FZ note: only binds if there are Russian Federation citizen users;
  confirm the target audience before deciding server location for that
  data specifically.

This is a post-hackathon-submission roadmap item, not scoped for the
current Streamlit prototype, which is the actual submission and already
verified end-to-end (see README).
