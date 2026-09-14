import { FormEvent, useState } from "react";
import { supabase } from "../supabaseClient";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signIn" | "signUp">("signIn");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === "signIn") {
        const { error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) throw err;
      } else {
        const { error: err } = await supabase.auth.signUp({ email, password });
        if (err) throw err;
        setInfo("Check your email to confirm your account, then sign in.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dh-card" style={{ maxWidth: 380, margin: "60px auto" }}>
      <h2 style={{ marginBottom: 4 }}>{mode === "signIn" ? "Welcome back" : "Create your account"}</h2>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, marginTop: 0, marginBottom: 18 }}>
        {mode === "signIn" ? "Sign in to your family's Story Universe." : "One account per family -- your kids' characters, places, and stories all live here."}
      </p>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <input
          className="dh-input"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="dh-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={6}
          required
        />
        <button className="dh-button" type="submit" disabled={busy}>
          {busy ? "One moment..." : mode === "signIn" ? "Sign in" : "Sign up"}
        </button>
      </form>
      {error && <p className="dh-error">{error}</p>}
      {info && <p style={{ color: "var(--accent2)", fontSize: 13, marginTop: 6 }}>{info}</p>}
      <button
        type="button"
        onClick={() => setMode(mode === "signIn" ? "signUp" : "signIn")}
        style={{ background: "none", border: "none", color: "var(--accent2)", fontSize: 13, marginTop: 14, cursor: "pointer", padding: 0 }}
      >
        {mode === "signIn" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
