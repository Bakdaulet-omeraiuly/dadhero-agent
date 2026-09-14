import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { Gallery } from "./components/Gallery";
import { Login } from "./components/Login";
import { supabase } from "./supabaseClient";

type View = "chat" | "gallery";

export function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [view, setView] = useState<View>("chat");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  if (session === undefined) {
    // Initial session check in flight -- avoid a Login-then-Chat flash.
    return null;
  }

  if (!session) return <Login />;

  return (
    <>
      <nav className="dh-nav">
        <button
          type="button"
          className={`dh-button dh-tab${view === "chat" ? " active" : ""}`}
          onClick={() => setView("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={`dh-button dh-tab${view === "gallery" ? " active" : ""}`}
          onClick={() => setView("gallery")}
        >
          Story Universe
        </button>
      </nav>
      {view === "chat" ? <Chat /> : <Gallery />}
    </>
  );
}
