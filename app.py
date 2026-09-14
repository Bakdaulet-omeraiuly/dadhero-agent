"""
DadHero demo UI (Streamlit).

Run with: streamlit run app.py

The agent's response is markdown containing ![alt](local_path) image
references, but Streamlit's st.markdown() can't display local filesystem
images through that syntax (no static file route for them) -- it just
renders a broken-image icon. render_story() below splits the text on
those references and renders each text chunk with st.markdown() and each
image as a base64-embedded, framed "comic panel" <img>, in order.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import uuid
from pathlib import Path

import streamlit as st

from dadhero import memory_backend as memory
from dadhero.agent import build_agent

_IMAGE_MD = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
_DEMO_DIR = Path(__file__).resolve().parent / "docs" / "demo"

st.set_page_config(page_title="DadHero", page_icon="🦸", layout="centered")

# ---------------------------------------------------------------- styling --
# Subject-grounded palette: a warm storybook page (not the generic AI
# cream+terracotta+serif combo -- accent is a two-crayon pairing, coral +
# teal, like a kid's crayon box) with a playful display face for headings
# and a clean rounded body face for reading. Full light/dark token sets so
# it holds in both hosts.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700;800&family=Nunito:wght@400;600;700;800&display=swap');

    :root {
        --paper: #FBF5E9;
        --card: #FFFDF8;
        --ink: #2E241A;
        --ink-soft: #7A6B57;
        --border: #E9DCC0;
        --accent: #EE7B4F;
        --accent-ink: #FFFFFF;
        --accent2: #2F9C8F;
        --shadow: rgba(46, 36, 26, 0.10);
    }
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
            --paper: #211A12;
            --card: #2A2216;
            --ink: #F3EAD9;
            --ink-soft: #B9AA90;
            --border: #40331F;
            --accent: #F3936A;
            --accent-ink: #241A10;
            --accent2: #52C2B2;
            --shadow: rgba(0, 0, 0, 0.35);
        }
    }
    :root[data-theme="dark"] {
        --paper: #211A12;
        --card: #2A2216;
        --ink: #F3EAD9;
        --ink-soft: #B9AA90;
        --border: #40331F;
        --accent: #F3936A;
        --accent-ink: #241A10;
        --accent2: #52C2B2;
        --shadow: rgba(0, 0, 0, 0.35);
    }

    .stApp { background: var(--paper); color: var(--ink); }
    html, body, [class*="css"] { font-family: 'Nunito', sans-serif; }
    h1, h2, h3 { font-family: 'Baloo 2', sans-serif !important; color: var(--ink) !important; }

    /* Hide Streamlit's own chrome (Deploy button, hamburger menu, "Made
       with Streamlit" footer) -- config.toml's toolbarMode="minimal"
       does most of this already; this is belt-and-suspenders for the
       footer/badge a viewer's URL params could otherwise reveal. The
       single biggest thing that makes a Streamlit app read as a
       template instead of a real product. */
    #MainMenu, footer, [data-testid="stStatusWidget"] { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    /* Sidebar's example-prompt card (replaces a raw st.code() block,
       which doesn't wrap and was clipping mid-word at the sidebar's
       fixed width -- this is prose, not code). Hardcoded dark colors to
       match the sidebar's own always-dark treatment above, not the
       light-mode --paper/--border tokens this sits among elsewhere. */
    .dh-example-card {
        font-style: italic; font-size: 13px; line-height: 1.5;
        color: #B9AA90 !important; background: #2A2216;
        border: 1.5px dashed #40331F; border-radius: 10px;
        padding: 10px 12px;
    }

    /* "Why this is an agent" -- small feature rows (icon + one line)
       instead of a plain bullet list, same product-feature-grid
       language a real landing page uses. */
    .dh-feature-row {
        display: flex; align-items: flex-start; gap: 10px;
        padding: 7px 0; border-bottom: 1px solid #40331F;
    }
    .dh-feature-row:last-child { border-bottom: none; }
    .dh-feature-row span { font-size: 17px; line-height: 1.4; flex-shrink: 0; }
    .dh-feature-row p { margin: 0; font-size: 13.5px; line-height: 1.4; color: #F3EAD9; }

    /* Hero header */
    .dh-hero {
        display: flex; align-items: center; gap: 16px;
        padding: 18px 22px; margin-bottom: 6px;
        background: var(--card); border: 2px solid var(--border);
        border-radius: 20px; box-shadow: 0 6px 18px var(--shadow);
    }
    .dh-hero-emoji { font-size: 42px; line-height: 1; }
    .dh-hero h1 { margin: 0; font-size: 30px; font-weight: 800; }
    .dh-hero p { margin: 2px 0 0; color: var(--ink-soft); font-size: 15px; font-weight: 600; }

    /* Sidebar -- deliberately dark regardless of the main page's light/dark
       theme (a docs-style nav rail, not just the storybook card color),
       the same ink-dark palette already defined above for dark mode,
       hardcoded here so it doesn't flip with the OS setting. */
    [data-testid="stSidebar"] {
        background: #211A12 !important;
        border-right: 2px solid #40331F !important;
    }
    [data-testid="stSidebar"] * { color: #F3EAD9; }
    [data-testid="stSidebar"] h3 {
        font-size: 15px !important; margin-top: 18px !important;
        text-transform: uppercase; letter-spacing: .04em;
        color: #F3936A !important; font-family: 'Baloo 2', sans-serif !important;
    }
    [data-testid="stSidebar"] hr { border-color: #40331F !important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] small { color: #B9AA90 !important; }
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background: #2A2216 !important; border: 1px solid #40331F !important; border-radius: 12px;
    }
    [data-testid="stSidebar"] [data-testid="stCodeBlock"] pre,
    [data-testid="stSidebar"] code {
        background: #2A2216 !important; color: #F3936A !important;
        border: 1px solid #40331F !important; border-radius: 10px !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        border-color: #F3936A !important; color: #F3936A !important; background: transparent !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #F3936A !important; color: #241A10 !important;
    }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: var(--card); border: 2px solid var(--border);
        border-radius: 18px; padding: 4px 6px; margin-bottom: 10px;
        box-shadow: 0 3px 10px var(--shadow);
    }
    /* The agent's own "### Page N" heading right before each panel --
       styled as a small caps label (matching .dh-panel-label) rather
       than a full-size heading, now that it's the only label. */
    [data-testid="stChatMessage"] h3 {
        font-size: 13px !important; letter-spacing: .03em; text-transform: uppercase;
        color: var(--accent2) !important; margin: 10px 2px 4px !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 999px !important; border: 2px solid var(--accent) !important;
        color: var(--accent) !important; font-weight: 700 !important; background: transparent !important;
    }
    .stButton > button:hover { background: var(--accent) !important; color: var(--accent-ink) !important; }

    /* Chat input pill */
    [data-testid="stChatInput"] {
        border: 2px solid var(--border) !important; border-radius: 999px !important;
        background: var(--card) !important;
    }

    /* Comic panel image frame */
    .dh-panel {
        border: 3px solid var(--ink); border-radius: 14px; overflow: hidden;
        margin: 10px 0 14px; box-shadow: 4px 4px 0 var(--accent);
        background: var(--card);
    }
    .dh-panel img { display: block; width: 100%; }
    .dh-panel-label {
        font-family: 'Baloo 2', sans-serif; font-weight: 700; font-size: 13px;
        letter-spacing: .03em; text-transform: uppercase; color: var(--accent2);
        margin: 2px 2px 6px;
    }

    /* Tool-call trace pills */
    .dh-tools { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .dh-tool-pill {
        font-size: 11px; font-weight: 700; color: var(--accent2);
        border: 1.5px solid var(--accent2); border-radius: 999px; padding: 2px 9px;
    }

    .dh-gallery-card {
        border: 3px solid var(--ink); border-radius: 14px; overflow: hidden;
        box-shadow: 3px 3px 0 var(--accent2); background: var(--card);
    }
    .dh-gallery-card img { display: block; width: 100%; }

    /* Workshop panel -- live trace of the agent's tool calls while a
       story is being made: real steps, not a generic spinner. */
    .dh-workshop-label {
        font-family: 'Baloo 2', sans-serif; font-weight: 700; font-size: 13px;
        letter-spacing: .04em; text-transform: uppercase; color: var(--accent2);
        margin: 2px 2px 6px;
    }
    [data-testid="stExpander"] {
        border: 2px solid var(--border) !important; border-radius: 12px !important;
        background: var(--card) !important; margin-bottom: 6px !important;
        box-shadow: 0 2px 6px var(--shadow);
    }
    [data-testid="stExpander"] summary {
        font-family: 'Baloo 2', sans-serif !important; font-weight: 700 !important;
        font-size: 14px !important;
    }
    [data-testid="stExpander"] summary:hover { background: var(--paper) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


_TOOL_LABELS: dict[str, tuple[str, str]] = {
    "get_family_memory": ("🧠", "Reading this family's Story Universe"),
    "get_saved_character": ("🔎", "Looking up a saved character"),
    "save_character": ("📇", "Writing the Character Bible"),
    "save_character_from_photo": ("📸", "Stylizing the reference photo"),
    "stylize_drawing": ("✏️", "Bringing the drawing to life"),
    "save_place": ("🏞️", "Saving a recurring place"),
    "record_family_memory": ("💭", "Recording a real family memory"),
    "record_progress": ("📈", "Recording a progress update"),
    "check_story_fact": ("🧩", "Checking story continuity"),
    "check_page_safety": ("🛡️", "Screening a page for age-appropriateness"),
    "generate_page_image": ("🖼️", "Illustrating a page"),
    "record_finished_story": ("✅", "Recording the finished story"),
}


def _tool_label(name: str) -> tuple[str, str]:
    return _TOOL_LABELS.get(name, ("⚙️", name))


def render_workshop(steps: list[dict]) -> None:
    """One expander per tool call, in order -- the running step stays open,
    finished ones collapse to a checkmark, expandable to see exactly what
    the agent passed in (and got back, once available)."""
    if not steps:
        return
    st.markdown('<div class="dh-workshop-label">🔨 Workshop</div>', unsafe_allow_html=True)
    for i, step in enumerate(steps):
        icon, label = _tool_label(step["name"])
        running = step["status"] == "running"
        badge = "⏳" if running else "✅"
        with st.expander(f"{icon} {label} {badge}", expanded=running and i == len(steps) - 1):
            if step.get("input"):
                st.json(step["input"], expanded=False)
            elif running:
                st.caption("Working...")
            if step.get("output") and not (isinstance(step["output"], dict) and step["output"].get("status") == "error"):
                st.caption("Done.")
            elif isinstance(step.get("output"), dict) and step["output"].get("status") == "error":
                st.caption("⚠️ This step reported an error -- see the reply above for how the agent handled it.")


def _extract_tool_trace(agent) -> list[dict]:
    """Every (name, input, output) for every tool call in agent.messages,
    in order. A @tool function's plain-dict return (no "status"/"content"
    keys of its own) gets JSON-serialized into the toolResult's one text
    block by strands' decorator -- json.loads it back here."""
    pending: dict[str, dict] = {}
    order: list[str] = []
    for msg in agent.messages:
        for block in msg.get("content", []):
            if not isinstance(block, dict):
                continue
            if "toolUse" in block:
                tu = block["toolUse"]
                tid = tu.get("toolUseId")
                pending[tid] = {"name": tu.get("name", "tool"), "input": tu.get("input", {}), "output": None}
                order.append(tid)
            elif "toolResult" in block:
                tr = block["toolResult"]
                tid = tr.get("toolUseId")
                if tid not in pending:
                    continue
                for c in tr.get("content", []):
                    if isinstance(c, dict) and "text" in c:
                        try:
                            pending[tid]["output"] = json.loads(c["text"])
                        except (json.JSONDecodeError, TypeError):
                            pending[tid]["output"] = {"text": c["text"]}
                        break
    return [pending[tid] for tid in order]


def save_uploaded_file(uploaded_file) -> str:
    """Save a Streamlit UploadedFile to disk and return its absolute path,
    so the agent can pass that path straight to save_character_from_photo /
    stylize_drawing -- the LLM never needs to see the image itself, only
    know where it is."""
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded_file.name).suffix or ".png"
    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(uploaded_file.getvalue())
    return str(dest)


def _img_tag(path: str) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    ext = Path(path).suffix.lstrip(".") or "png"
    return f'<img src="data:image/{ext};base64,{data}" />'


def render_story(text: str) -> None:
    pos = 0
    for match in _IMAGE_MD.finditer(text):
        before = text[pos : match.start()].strip()
        alt, path = match.group(1), match.group(2)
        # The agent's own text already puts a "### Page N" heading right
        # before each image (see agent.py's system prompt, step 9) --
        # showing the image's alt text as ITS OWN small label too just
        # duplicated that same "Page N" twice in a row. Only fall back to
        # the alt-text label when the agent's text didn't already supply
        # a heading immediately above this image.
        had_heading = bool(before)
        if before:
            st.markdown(before)
        if os.path.exists(path):
            label = "" if had_heading else (f'<div class="dh-panel-label">{alt}</div>' if alt else "")
            st.markdown(f'{label}<div class="dh-panel">{_img_tag(path)}</div>', unsafe_allow_html=True)
        else:
            st.caption(f"(missing image: {path})")
        pos = match.end()
    tail = text[pos:].strip()
    if tail:
        st.markdown(tail)


st.markdown(
    """
    <div class="dh-hero">
      <div class="dh-hero-emoji">🦸</div>
      <div>
        <h1>DadHero</h1>
        <p>Turns a child's real life -- fears, milestones, memories -- into personalized illustrated stories that grow with them.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "agent" not in st.session_state:
    st.session_state.agent = build_agent()
    st.session_state.history = []

with st.sidebar:
    st.subheader("🌟 Session")
    if st.button("Start a new story"):
        st.session_state.agent = build_agent()
        st.session_state.history = []
        st.rerun()

    provider = os.environ.get("DADHERO_IMAGE_PROVIDER", "mock")
    if provider == "mock":
        st.warning("Image provider: **mock** (placeholder art). Set DADHERO_IMAGE_PROVIDER=gemini for real illustrations.")
    else:
        st.success(f"Image provider: **{provider}** 🎨")

    # Makes the Story Universe's persistence (data/family_memory.json --
    # unaffected by a page refresh or a new browser tab, unlike
    # st.session_state.history) something a visitor can actually SEE,
    # not just a claim in the bullet list below.
    profile = memory.get_family_profile("default_family")
    saved_characters = profile.get("characters", {})
    saved_places = profile.get("places", {})
    saved_stories = profile.get("stories", [])
    if saved_characters or saved_places or saved_stories:
        st.subheader("🗂️ Story Universe")
        if saved_characters:
            with st.expander(f"👤 Characters ({len(saved_characters)})"):
                for name, bible in saved_characters.items():
                    subtitle = bible.get("relationship", "")
                    if bible.get("role_in_story"):
                        subtitle += f" · {bible['role_in_story']}"
                    st.markdown(f"**{name}**  \n{subtitle}")
                    if bible.get("appearance"):
                        st.caption(bible["appearance"])
                    ref = bible.get("reference_image_path")
                    if ref and os.path.exists(ref):
                        st.markdown(f'<div class="dh-gallery-card">{_img_tag(ref)}</div>', unsafe_allow_html=True)
        if saved_places:
            with st.expander(f"🏞️ Places ({len(saved_places)})"):
                for name, description in saved_places.items():
                    st.markdown(f"**{name}**")
                    st.caption(description)
        if saved_stories:
            with st.expander(f"📖 Stories ({len(saved_stories)})"):
                for s in saved_stories:
                    line = f"**{s.get('title', 'Untitled')}**"
                    if s.get("goal"):
                        line += f"  \n_Goal: {s['goal']}_"
                    st.markdown(line)
                    if s.get("idea"):
                        st.caption(s["idea"])

    st.subheader("🧠 Why this is an agent")
    # <strong>, not **markdown** -- these get concatenated straight into
    # raw HTML below (unsafe_allow_html), and CommonMark doesn't run
    # markdown-style emphasis back over text already inside a raw HTML
    # block, so ** would show up literally instead of rendering bold.
    _AGENT_FEATURES = [
        ("📇", "Builds a <strong>Character Bible</strong> once, reuses it verbatim per page"),
        ("📐", "Plans a 5-8 page story arc from a proven template"),
        ("🔗", "Chains a reference image forward for visual consistency"),
        ("🔁", "Regenerates only the page you flag on feedback"),
        ("🗂️", "<strong>Remembers</strong> characters, places, goals &amp; progress across sessions"),
    ]
    st.markdown(
        "".join(
            f'<div class="dh-feature-row"><span>{emoji}</span><p>{text}</p></div>'
            for emoji, text in _AGENT_FEATURES
        ),
        unsafe_allow_html=True,
    )

    st.subheader("💬 Try")
    # A prose example, not code -- st.code() renders a fixed-width
    # terminal block that doesn't wrap, clipping mid-word in the
    # sidebar's fixed narrow width. Plain markdown wraps naturally.
    st.markdown(
        '<div class="dh-example-card">'
        "“My husband has short black hair, glasses, and a red hoodie. "
        "I want a 5-page comic where he's a brave astronaut who saves a "
        "lost baby star, for our 5-year-old daughter.”"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "📎 attach a photo of an **adult** family member for a likeness-based "
        "portrait, or your child's own drawing to bring to life -- never a "
        "photo of the child (see the safety note in the README)."
    )

_QUICK_PROMPTS = [
    ("😰", "First day of school", "My daughter is nervous about her first day of school -- make her a brave astronaut story about it."),
    ("🦷", "A real milestone", "My son lost his first tooth today! Turn it into a fun adventure."),
    ("🤝", "Teach a lesson", "Teach my daughter about sharing through a short, warm bedtime story."),
]

quick_start_text: str | None = None

# Show the page "at rest" with real generated proof instead of a blank
# chat -- a first-time visitor sees what this actually makes before
# typing anything, plus one-click starting points (the same "suggested
# prompt" pattern most AI products use) so a first message doesn't
# require staring at a blank input.
if not st.session_state.history:
    if _DEMO_DIR.exists():
        demo_images = sorted(_DEMO_DIR.glob("example_page*.png"))
        if demo_images:
            st.markdown("##### 📖 A story DadHero actually made")
            cols = st.columns(len(demo_images))
            for col, img_path in zip(cols, demo_images):
                with col:
                    st.markdown(f'<div class="dh-gallery-card">{_img_tag(str(img_path))}</div>', unsafe_allow_html=True)
            st.caption("Real output -- same locked character, chained across pages. Now describe your own idea below.")
            st.divider()

    st.markdown("##### ✨ Or start with one of these")
    cols = st.columns(len(_QUICK_PROMPTS))
    for col, (emoji, label, prompt) in zip(cols, _QUICK_PROMPTS):
        with col:
            if st.button(f"{emoji} {label}", key=f"quickstart_{label}", use_container_width=True):
                quick_start_text = prompt
    st.divider()

for role, text in st.session_state.history:
    with st.chat_message(role, avatar="🦸" if role == "assistant" else "🙂"):
        render_story(text)

chat_value = st.chat_input(
    "Describe your idea, or attach a photo/drawing...",
    accept_file=True,
    file_type=["png", "jpg", "jpeg"],
)

if chat_value or quick_start_text:
    if chat_value:
        user_text = chat_value.text or ""
        display_text = user_text
        for uploaded in chat_value.files:
            saved_path = save_uploaded_file(uploaded)
            user_text += f"\n\n[Uploaded file: {saved_path}]"
            display_text += f"\n\n![attached]({saved_path})"
        if not user_text.strip():
            user_text = "(see attached file)"
            display_text = "(see attached file)"
    else:
        user_text = display_text = quick_start_text

    st.session_state.history.append(("user", display_text))
    with st.chat_message("user", avatar="🙂"):
        render_story(display_text)

    with st.chat_message("assistant", avatar="🦸"):
        workshop_slot = st.empty()
        steps: list[dict] = []

        async def _consume() -> None:
            async for event in st.session_state.agent.stream_async(user_text):
                tool_use = (
                    event.get("event", {})
                    .get("contentBlockStart", {})
                    .get("start", {})
                    .get("toolUse")
                )
                if not tool_use:
                    continue
                if steps:
                    steps[-1]["status"] = "done"
                steps.append({"name": tool_use.get("name", "tool"), "status": "running", "input": None, "output": None})
                with workshop_slot.container():
                    render_workshop(steps)

        with st.spinner("Making the story..."):
            asyncio.run(_consume())

        # Live steps only had a bare tool name (input streams in as
        # JSON deltas, not available at contentBlockStart) -- now that
        # the turn is over, backfill each one's real input/output from
        # the completed message history and collapse them all.
        trace = _extract_tool_trace(st.session_state.agent)
        this_turn = trace[-len(steps):] if steps else []
        for step, t in zip(steps, this_turn):
            step["input"] = t.get("input")
            step["output"] = t.get("output")
            step["status"] = "done"
        with workshop_slot.container():
            render_workshop(steps)

        last_msg = st.session_state.agent.messages[-1]
        response_text = "".join(
            block.get("text", "") for block in last_msg.get("content", []) if isinstance(block, dict) and "text" in block
        )
        render_story(response_text)

    st.session_state.history.append(("assistant", response_text))
