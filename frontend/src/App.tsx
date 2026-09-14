import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { Gallery } from "./components/Gallery";
import { Login } from "./components/Login";
import { Navbar } from "./components/Navbar";
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
      <Navbar view={view} onChange={setView} />
      {view === "chat" ? <Chat /> : <Gallery />}
    </>
  );
}
