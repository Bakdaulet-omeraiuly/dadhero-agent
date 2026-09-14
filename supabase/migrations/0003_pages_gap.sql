-- Closes the documented "pages table is never written to" gap (see
-- backend/routers/stories.py's original docstring). generate_page_image
-- (dadhero/tools.py) is unchanged -- it still only persists the image
-- file, so Streamlit's tested tool signature stays untouched. Instead:
--   - backend/routers/conversations.py reconciles a `pages` row for every
--     generate_page_image call it finds in the agent's tool-call history
--     after each turn, resolving (or creating, as a draft) a `stories`
--     row via `conversation_id` -- pages are usually generated in an
--     earlier turn than the one that calls record_finished_story.
--   - backend/routers/stories.py's new POST/PATCH .../pages routes (the
--     OpenAPI spec's direct, non-chat page generation) write here too.

alter table stories add column if not exists conversation_id uuid;
alter table pages add column if not exists image_url text;

-- Looked up once per turn to find/create this conversation's story row.
create index if not exists stories_conversation_id_idx on stories (family_id, conversation_id);
