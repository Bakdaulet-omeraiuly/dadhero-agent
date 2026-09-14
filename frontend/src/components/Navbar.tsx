import { supabase } from "../supabaseClient";

type View = "chat" | "gallery";

// A real product top bar -- brand mark, primary nav links, a secondary
// action on the right -- instead of two standalone pill buttons floating
// above the page. Same shape as any SaaS app's header (logo left, nav
// center-left, account action right), scaled to DadHero's two views.
export function Navbar({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <header className="dh-topbar">
      <button type="button" className="dh-topbar-brand" onClick={() => onChange("chat")}>
        <span className="dh-topbar-emoji">🦸</span>
        <span>DadHero</span>
      </button>
      <nav className="dh-topbar-links">
        <button
          type="button"
          className={`dh-topbar-link${view === "chat" ? " active" : ""}`}
          onClick={() => onChange("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={`dh-topbar-link${view === "gallery" ? " active" : ""}`}
          onClick={() => onChange("gallery")}
        >
          My Universe
        </button>
      </nav>
      <button type="button" className="dh-topbar-signout" onClick={() => supabase.auth.signOut()}>
        Sign out
      </button>
    </header>
  );
}
