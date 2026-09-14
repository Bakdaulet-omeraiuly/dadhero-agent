import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listCharacters, listPages, listPlaces, listStories, type Story } from "../api";

// Read-only dashboard for the CRUD routes the chat flow already writes to
// (backend/routers/characters.py, places.py, stories.py) -- the chat
// itself is still the only way to CREATE any of this, matching the
// OpenAPI spec's split between the conversational endpoint and these
// plain resource views. No router: a local tab switch, same "two views,
// branch on state" choice App.tsx already made between Login/Chat.
type Tab = "characters" | "places" | "stories";

export function Gallery() {
  const [tab, setTab] = useState<Tab>("stories");

  // Fetched here (not just inside each tab) so the counts strip below
  // reflects all three regardless of which tab is open -- React Query
  // dedupes against the identical queryKey each tab's own useQuery uses,
  // so this doesn't cost extra requests once a tab is opened.
  const stories = useQuery({ queryKey: ["stories"], queryFn: listStories });
  const characters = useQuery({ queryKey: ["characters"], queryFn: listCharacters });
  const places = useQuery({ queryKey: ["places"], queryFn: listPlaces });

  return (
    <div className="dh-card">
      <div className="dh-universe-stats">
        <div className="dh-stat-chip">
          <strong>{stories.data?.length ?? "–"}</strong>
          <span>Stories</span>
        </div>
        <div className="dh-stat-chip">
          <strong>{characters.data?.length ?? "–"}</strong>
          <span>Characters</span>
        </div>
        <div className="dh-stat-chip">
          <strong>{places.data?.length ?? "–"}</strong>
          <span>Places</span>
        </div>
      </div>
      <div className="dh-gallery-tabs">
        {(["stories", "characters", "places"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`dh-button dh-tab${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "stories" ? "Stories" : t === "characters" ? "Characters" : "Places"}
          </button>
        ))}
      </div>
      {tab === "characters" && <CharactersTab />}
      {tab === "places" && <PlacesTab />}
      {tab === "stories" && <StoriesTab />}
    </div>
  );
}

function CharactersTab() {
  const q = useQuery({ queryKey: ["characters"], queryFn: listCharacters });
  if (q.isLoading) return <p style={{ color: "var(--ink-soft)" }}>Loading characters...</p>;
  if (q.isError) return <p className="dh-error">Couldn't load characters.</p>;
  if (!q.data?.length) return <p style={{ color: "var(--ink-soft)" }}>No saved characters yet -- describe one in the chat.</p>;
  return (
    <div className="dh-gallery-grid">
      {q.data.map((c) => (
        <div key={c.id} className="dh-gallery-item">
          <h3>{c.character_name}</h3>
          <p className="dh-gallery-meta">{c.relationship}{c.role_in_story ? ` · ${c.role_in_story}` : ""}</p>
          {c.appearance_text && <p>{c.appearance_text}</p>}
        </div>
      ))}
    </div>
  );
}

function PlacesTab() {
  const q = useQuery({ queryKey: ["places"], queryFn: listPlaces });
  if (q.isLoading) return <p style={{ color: "var(--ink-soft)" }}>Loading places...</p>;
  if (q.isError) return <p className="dh-error">Couldn't load places.</p>;
  if (!q.data?.length) return <p style={{ color: "var(--ink-soft)" }}>No saved places yet -- they show up once a story settles somewhere recurring.</p>;
  return (
    <div className="dh-gallery-grid">
      {q.data.map((p) => (
        <div key={p.id} className="dh-gallery-item">
          <h3>{p.place_name}</h3>
          <p>{p.description}</p>
        </div>
      ))}
    </div>
  );
}

function StoriesTab() {
  const q = useQuery({ queryKey: ["stories"], queryFn: listStories });
  const [openStoryId, setOpenStoryId] = useState<string | null>(null);

  if (q.isLoading) return <p style={{ color: "var(--ink-soft)" }}>Loading stories...</p>;
  if (q.isError) return <p className="dh-error">Couldn't load stories.</p>;
  if (!q.data?.length) return <p style={{ color: "var(--ink-soft)" }}>No stories yet -- ask for one in the chat.</p>;

  return (
    <div className="dh-gallery-grid">
      {q.data.map((s) => (
        <div key={s.id} className="dh-gallery-item">
          <button type="button" className="dh-story-toggle" onClick={() => setOpenStoryId(openStoryId === s.id ? null : s.id)}>
            <h3>{s.title}</h3>
            <span className={`dh-status-pill ${s.status}`}>{s.status}</span>
          </button>
          {s.idea && <p>{s.idea}</p>}
          {s.goal && <p className="dh-gallery-meta">Goal: {s.goal}</p>}
          {openStoryId === s.id && <StoryPages story={s} />}
        </div>
      ))}
    </div>
  );
}

function StoryPages({ story }: { story: Story }) {
  const q = useQuery({ queryKey: ["pages", story.id], queryFn: () => listPages(story.id) });
  if (q.isLoading) return <p style={{ color: "var(--ink-soft)" }}>Loading pages...</p>;
  if (q.isError) return <p className="dh-error">Couldn't load pages.</p>;
  if (!q.data?.length) return <p style={{ color: "var(--ink-soft)" }}>No illustrated pages saved for this story yet.</p>;
  return (
    <div className="dh-page-strip">
      {q.data.map((p) => (
        <div key={p.page_number} className="dh-panel">
          <img src={p.image_url} alt={`Page ${p.page_number}`} loading="lazy" />
        </div>
      ))}
    </div>
  );
}
