# DadHero platform frontend (React + Vite)

Minimal MVP consuming `../backend`'s API: Supabase Auth login/signup, then
a chat interface at parity with the Streamlit demo's UX (message list,
text input, photo/drawing attachment, generated pages shown as framed
"comic panels").

## Status: builds and type-checks cleanly; UNTESTED against a live backend

`npm install && npx tsc -b && npx vite build` all pass with zero errors --
the code is structurally sound. It has **not** been run against a live
Supabase project + `backend` instance (chicken-and-egg with
`backend/README.md`'s own "UNTESTED" status) -- do the manual check below
once both are live.

## Deliberate scope cuts (stated plainly)

- **No TanStack Router.** `docs/api/design-notes.md` and `CLAUDE.md`
  mention TanStack Router as part of the target stack; this MVP has
  exactly two views (signed out -> `Login`, signed in -> `Chat`), so
  `App.tsx` just branches on session state. Adding a router for two
  screens would be ceremony, not architecture -- reach for it when a
  second real page (a character/story gallery) actually exists.
- **One conversation per browser tab**, remembered via `localStorage`
  (see `Chat.tsx`) -- no "past conversations" list. `GET
  /me/conversations/{id}/messages` already supports listing a given
  conversation's history; a conversation-switcher UI is straightforward
  to add on top but wasn't, for time.
- **No character/story/place gallery views** -- `backend`'s CRUD routers
  for those exist and work from `curl`, nothing in this frontend calls
  them yet. The chat is the only surface.

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # fill in VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
                        # (same project as backend/.env) and VITE_API_BASE_URL
npm run dev             # http://localhost:5173
```

Needs `backend` running at `VITE_API_BASE_URL` (default
`http://localhost:8000`) and CORS on that backend allowing
`http://localhost:5173` (`backend/main.py`'s `DADHERO_CORS_ORIGINS`
default already matches).

## Verification checklist (do this before trusting it in a demo)

1. Sign up a test account through the actual `Login` form (not curl) --
   confirms Supabase Auth + the email-confirmation flow work end to end
   from a browser, not just the API.
2. Send a text-only message ("my dad is..."), confirm a reply with
   generated page images actually renders as framed panels, not broken
   `<img>` tags -- this is the same class of bug the Streamlit app hit
   once already (`![](path)` needing explicit handling, not passed
   straight to a naive renderer).
3. Attach a photo, confirm the upload round-trips through
   `sendMessage`'s `multipart/form-data` body correctly.
4. Reload the page mid-conversation -- confirm history reloads from
   `GET .../messages` (proves persistence isn't just optimistic client
   state).
5. Open the app in a second browser (or incognito) signed in as a
   *different* account -- confirm you see an empty conversation, not the
   first account's history (this is the same RLS check backend/README.md
   asks for, exercised from the actual client this time).
