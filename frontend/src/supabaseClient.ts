import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

if (!url || !anonKey) {
  // Fails loudly at startup rather than letting every auth call 500 later
  // with a confusing error -- see frontend/.env.example.
  // eslint-disable-next-line no-console
  console.error(
    "VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set -- copy frontend/.env.example to frontend/.env and fill them in."
  );
}

export const supabase = createClient(url ?? "", anonKey ?? "");
