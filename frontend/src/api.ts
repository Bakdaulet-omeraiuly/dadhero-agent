import { supabase } from "./supabaseClient";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not signed in");
  return { Authorization: `Bearer ${token}` };
}

export interface Message {
  id: string;
  role: "parent" | "assistant";
  content: string;
  tool_calls: string[];
  created_at: string;
}

export async function listMessages(conversationId: string): Promise<Message[]> {
  const headers = await authHeader();
  const res = await fetch(`${API_BASE}/me/conversations/${conversationId}/messages`, { headers });
  if (!res.ok) throw new Error(`listMessages failed: ${res.status}`);
  const body = await res.json();
  return body.data as Message[];
}

/** attachment: an adult reference photo, or a child's own drawing --
 * never a real photo of the child (enforced server-side regardless). */
export async function sendMessage(
  conversationId: string,
  content: string,
  attachment?: File
): Promise<Message> {
  const headers = await authHeader();
  const form = new FormData();
  form.append("content", content);
  if (attachment) form.append("attachment", attachment);

  const res = await fetch(`${API_BASE}/me/conversations/${conversationId}/messages`, {
    method: "POST",
    headers, // no Content-Type -- fetch sets the multipart boundary itself
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `sendMessage failed: ${res.status}`);
  }
  return res.json();
}
