import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { listMessages, sendMessage, type Message } from "../api";
import { MessageBubble } from "./MessageBubble";

// One conversation per browser tab for this MVP -- persisted in
// localStorage so a reload doesn't start a fresh thread. A real "past
// conversations" list is out of scope here; see backend/README.md's
// known-gaps list.
function getConversationId(): string {
  const key = "dadhero_conversation_id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export function Chat() {
  const conversationId = useRef(getConversationId()).current;
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const messagesQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => listMessages(conversationId),
  });

  const sendMutation = useMutation({
    mutationFn: (vars: { content: string; attachment?: File }) =>
      sendMessage(conversationId, vars.content, vars.attachment),
    onMutate: async (vars) => {
      // Optimistic parent bubble so the UI doesn't sit blank while the
      // agent turn (which can take several seconds -- image generation
      // isn't instant) runs.
      const optimistic: Message = {
        id: `optimistic-${Date.now()}`,
        role: "parent",
        content: vars.content || "(attached file)",
        tool_calls: [],
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData<Message[]>(["messages", conversationId], (prev) => [...(prev ?? []), optimistic]);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesQuery.data, sendMutation.isPending]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() && !attachment) return;
    sendMutation.mutate({ content: draft, attachment: attachment ?? undefined });
    setDraft("");
    setAttachment(null);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <p className="dh-chat-tagline">Turns a child's real life into personalized illustrated stories that grow with them.</p>

      <div className="dh-chat-scroll" style={{ flex: 1 }}>
        {messagesQuery.isLoading && <p style={{ color: "var(--ink-soft)" }}>Loading your Story Universe...</p>}
        {messagesQuery.isError && (
          <p className="dh-error">Couldn't load messages -- is the backend running at the configured API URL?</p>
        )}
        {messagesQuery.data?.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {sendMutation.isPending && (
          <div className="dh-bubble assistant">
            <p style={{ color: "var(--ink-soft)" }}>Making the story...</p>
          </div>
        )}
        {sendMutation.isError && (
          <p className="dh-error">{(sendMutation.error as Error).message}</p>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="dh-composer" onSubmit={handleSubmit}>
        <label className="dh-button" style={{ padding: "10px 14px" }}>
          📎
          <input
            type="file"
            accept="image/png,image/jpeg"
            style={{ display: "none" }}
            onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          />
        </label>
        <input
          type="text"
          className="dh-input"
          placeholder={attachment ? `Attached: ${attachment.name}` : "Describe your idea, or attach a photo/drawing..."}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={sendMutation.isPending}
        />
        <button className="dh-button" type="submit" disabled={sendMutation.isPending}>
          Send
        </button>
      </form>
    </div>
  );
}
