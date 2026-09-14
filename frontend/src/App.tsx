import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { Login } from "./components/Login";
import { supabase } from "./supabaseClient";

export function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

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

  return session ? <Chat /> : <Login />;
}
