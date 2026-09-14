import type { Message } from "../api";

// Mirrors app.py's render_story(): the agent's reply is markdown with
// ![alt](image_url) references (see dadhero/agent.py step 9 -- it's told
// to embed image_url, a real Supabase Storage URL here, not the internal
// image_path). Unlike the Streamlit version we don't need to read local
// files as base64 -- image_url is already a normal <img src> the browser
// can fetch directly.
const IMAGE_MD = /!\[([^\]]*)\]\(([^)]+)\)/g;

type Segment = { type: "text"; value: string } | { type: "image"; alt: string; src: string };

function splitContent(content: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  for (const match of content.matchAll(IMAGE_MD)) {
    const [full, alt, src] = match;
    const index = match.index ?? 0;
    const before = content.slice(lastIndex, index).trim();
    if (before) segments.push({ type: "text", value: before });
    segments.push({ type: "image", alt, src });
    lastIndex = index + full.length;
  }
  const tail = content.slice(lastIndex).trim();
  if (tail) segments.push({ type: "text", value: tail });
  return segments;
}

export function MessageBubble({ message }: { message: Message }) {
  const segments = splitContent(message.content);
  return (
    <div className={`dh-bubble ${message.role}`}>
      {segments.map((seg, i) =>
        seg.type === "text" ? (
          <p key={i}>{seg.value}</p>
        ) : (
          <div className="dh-panel" key={i}>
            <img src={seg.src} alt={seg.alt} loading="lazy" />
          </div>
        )
      )}
      {message.tool_calls.length > 0 && (
        <div className="dh-tools">
          {message.tool_calls.map((name, i) => (
            <span className="dh-tool-pill" key={i}>
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
