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

export interface Character {
  id: string;
  character_name: string;
  relationship: string;
  appearance_text: string | null;
  role_in_story: string;
  reference_image_path: string | null;
  created_at: string;
}

export interface Place {
  id: string;
  place_name: string;
  description: string;
}

export interface Story {
  id: string;
  title: string;
  idea: string | null;
  template_key: string;
  goal: string | null;
  status: "draft" | "finished";
  character_id: string | null;
  created_at: string;
}

export interface Page {
  story_id: string;
  page_number: number;
  scene_description: string;
  caption_text: string;
  image_url: string;
  is_placeholder: boolean;
  created_at: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const headers = await authHeader();
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const listCharacters = () => getJSON<{ data: Character[] }>("/me/characters").then((b) => b.data);
export const listPlaces = () => getJSON<{ data: Place[] }>("/me/places").then((b) => b.data);
export const listStories = () => getJSON<{ data: Story[] }>("/me/stories").then((b) => b.data);
export const listPages = (storyId: string) =>
  getJSON<{ data: Page[] }>(`/me/stories/${storyId}/pages`).then((b) => b.data);
