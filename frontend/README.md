# DadHero platform frontend (React + Vite)

Minimal MVP consuming `../backend`'s API: Supabase Auth login/signup, then
a chat interface at parity with the Streamlit demo's UX (message list,
text input, photo/drawing attachment, generated pages shown as framed
"comic panels").

## Status: builds and type-checks cleanly; backend it talks to is live-verified, this frontend itself hasn't been run against it yet

`npm install && npx tsc -b && npx vite build` all pass with zero errors --
the code is structurally sound. `backend/README.md`'s checklist has since
passed against a real Supabase project; this frontend hasn't been pointed
at that live pair yet -- do the manual check below once you have.

## Deliberate scope cuts (stated plainly)

- **No TanStack Router**, even with a second real view now (`Gallery.tsx`,
  a "Story Universe" tab next to Chat). `App.tsx` still just branches on
  local state (`view: "chat" | "gallery"`) the same way it branches on
  session state for Login/Chat -- two tabs is still ceremony-free without
  a router; reach for one if/when this grows a third independently-
  addressable page (deep links, browser back/forward).
- **One conversation per browser tab**, remembered via `localStorage`
  (see `Chat.tsx`) -- no "past conversations" list. `GET
  /me/conversations/{id}/messages` already supports listing a given
  conversation's history; a conversation-switcher UI is straightforward
  to add on top but wasn't, for time.
- **Gallery views are read-only.** `Gallery.tsx` lists characters,
  places, and stories (expandable to that story's illustrated pages) via
  `backend`'s CRUD GET routes -- creating/editing still only happens
  through the chat, matching the OpenAPI spec's split between the
  conversational endpoint and the plain resource routes.

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
