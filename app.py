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
import html
import json
import os
import re
import uuid
from pathlib import Path

import streamlit as st

# streamlit-drawable-canvas (last verified working -- see CLAUDE.md) is a
# community component that lags behind Streamlit's own component protocol.
# It has since broken on import against newer Streamlit releases (a real,
# reproduced StreamlitAPIException inside the package's own __init__.py,
# not a guess) -- since requirements.txt pins no upper bound on either
# package, a routine Streamlit Cloud reinstall could pull an incompatible
# pair and take the WHOLE app down at import time. Never let one optional
# feature's import crash the entire submission -- degrade to "unavailable"
# instead.
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_AVAILABLE = True
except Exception:
    st_canvas = None
    CANVAS_AVAILABLE = False

from dadhero import memory_backend as memory
from dadhero import seed
from dadhero.agent import build_agent
from dadhero.models import ART_STYLES
from dadhero.tools import stylize_drawing

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

    /* Streamlit's own <body> stays its default cool dark grey
       (rgb(14,17,23)) regardless of this page's theme -- invisible most
       of the time since .stApp normally covers the whole viewport, but
       the sticky bottom bar around the chat input sits in a region
       where that default shows through underneath, clashing with the
       warm brown everywhere else (confirmed via getComputedStyle: body
       stayed rgb(14,17,23) while .stApp correctly read the dark --paper
       token). Match it explicitly so there's no seam. */
    body { background: var(--paper); }
    .stApp { background: var(--paper); color: var(--ink); }
    /* A specific wrapper div inside the sticky bottom bar (around the
       chat input) carries its OWN hardcoded rgb(14,17,23) background,
       found by walking the DOM from stChatInput up to body -- the
       `body` rule above doesn't reach it since this div paints over
       it. Targeted by DOM position (data-testid's own container),
       not its unstable auto-generated emotion-cache class name. */
    [data-testid="stBottom"] > div { background: var(--paper) !important; }
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

    /* Chat input pill -- the outer container AND its first inner div
       (which carries its own hardcoded Streamlit light-theme grey,
       rgb(240,242,246), found the same way as the stBottom fix above)
       both need the override, or a cool grey shows through in light
       mode even though the outer pill itself is the right warm cream. */
    [data-testid="stChatInput"] {
        border: 2px solid var(--border) !important; border-radius: 999px !important;
        background: var(--card) !important;
    }
    [data-testid="stChatInput"] > div { background: var(--card) !important; }

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
    /* A character with no reference photo yet -- a monogram avatar, not
       a tiny icon adrift in a huge box (the card would otherwise size
       to the column's full width with nothing to naturally cap it,
       unlike an <img> whose own aspect ratio does that). */
    .dh-avatar-placeholder {
        display: flex; align-items: center; justify-content: center;
        height: 120px; font-family: 'Baloo 2', sans-serif; font-weight: 800;
        font-size: 44px; color: var(--accent-ink);
        background: linear-gradient(135deg, var(--accent), var(--accent2));
    }

    /* Book reader -- a bigger, centered stage for one page at a time,
       distinct from the smaller inline .dh-panel used in the chat feed. */
    .dh-book-title {
        font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 22px;
        color: var(--ink); padding-top: 4px;
    }
    .dh-book-page { max-width: 480px; margin: 10px auto 14px; }
    .dh-book-pagecount {
        text-align: center; font-family: 'Baloo 2', sans-serif; font-weight: 700;
        color: var(--accent2); padding-top: 8px;
    }

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


# Keys that are real internal wiring (a default family id, a chaining
# slug/path, the full locked character prompt reused verbatim on every
# page) -- meaningful to the code, not to a parent glancing at what the
# agent is doing. Hidden from the Workshop panel's detail view.
_STEP_DETAIL_HIDDEN_KEYS = {
    "family_id",
    "story_slug",
    "character_prompt_fragment",
    "page_slug",
    "reference_image_path",
    "is_cover",
}


def _format_step_detail(data: dict) -> str:
    """A tool call's input/output as a few plain-language lines instead
    of a raw JSON block -- a parent should see 'Idea: a lost tooth
    story', not {"family_id": "default_family", ...}."""
    lines = []
    for key, value in data.items():
        if key in _STEP_DETAIL_HIDDEN_KEYS or value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value) if value else ""
        text = str(value)
        if len(text) > 220:
            text = text[:220] + "..."
        lines.append(f"**{label}:** {text}")
    return "  \n".join(lines)


def render_workshop(steps: list[dict]) -> None:
    """One expander per tool call, in order -- the running step stays open,
    finished ones collapse to a checkmark, expandable to see (in plain
    language, not raw JSON) what the agent passed in and got back."""
    if not steps:
        return
    st.markdown('<div class="dh-workshop-label">🔨 Workshop</div>', unsafe_allow_html=True)
    for i, step in enumerate(steps):
        icon, label = _tool_label(step["name"])
        running = step["status"] == "running"
        badge = "⏳" if running else "✅"
        with st.expander(f"{icon} {label} {badge}", expanded=running and i == len(steps) - 1):
            if step.get("input"):
                detail = _format_step_detail(step["input"])
                if detail:
                    st.markdown(detail)
            elif running:
                st.caption("Working...")
            if isinstance(step.get("output"), dict) and step["output"].get("status") == "error":
                st.caption("⚠️ This step reported an error -- see the reply above for how the agent handled it.")
            elif step.get("output"):
                st.caption("Done.")


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


def save_canvas_drawing(image_data) -> str:
    """Same idea as save_uploaded_file, for a sketch drawn right in the
    browser (st_canvas's RGBA numpy array) instead of an uploaded file --
    goes through the exact same stylize_drawing path afterward, so a
    drawn sketch and an uploaded scan of one are handled identically."""
    from PIL import Image

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex}.png"
    # st_canvas gives RGBA with a transparent background where nothing was
    # drawn -- flatten onto white first, or stylize_drawing's provider
    # would see a checkerboard/black background instead of blank paper.
    img = Image.fromarray(image_data.astype("uint8"), "RGBA")
    flattened = Image.new("RGBA", img.size, (255, 255, 255, 255))
    flattened.paste(img, mask=img)
    flattened.convert("RGB").save(dest)
    return str(dest)


def _img_tag(path: str) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    ext = Path(path).suffix.lstrip(".") or "png"
    return f'<img src="data:image/{ext};base64,{data}" />'


def _settings_prefix() -> str:
    """A bracketed constraints line the sidebar's Story settings panel
    builds, prepended to the next message -- see agent.py's system
    prompt's own "PARENT SETTINGS" section for how it's read. Only
    includes values the parent actually changed from their default, so a
    plain message stays plain."""
    parts = []
    if st.session_state.get("setting_age"):
        parts.append(f"child age {st.session_state.setting_age}")
    if st.session_state.get("setting_tone", "Any") != "Any":
        parts.append(f"tone: {st.session_state.setting_tone.lower()}")
    length = st.session_state.get("setting_length", "Default (5-8 pages)")
    if not length.startswith("Default"):
        parts.append(f"length: {length.lower()}")
    if st.session_state.get("setting_scary", "Gentle") != "Gentle":
        parts.append(f"scary level: {st.session_state.setting_scary.lower()}")
    if st.session_state.get("setting_goal", "None") != "None":
        parts.append(f"educational goal: {st.session_state.setting_goal.lower()}")
    style = st.session_state.get("setting_style", "Storybook (default)")
    if not style.startswith("Storybook"):
        # The exact ART_STYLES label, unchanged -- agent.py's system
        # prompt passes this straight through as save_character's
        # art_style argument, which looks the label back up itself.
        parts.append(f"art style: {style}")
    if st.session_state.get("setting_include", "").strip():
        parts.append(f"include: {st.session_state.setting_include.strip()}")
    if st.session_state.get("setting_avoid", "").strip():
        parts.append(f"avoid: {st.session_state.setting_avoid.strip()}")
    return f"[Parent settings: {', '.join(parts)}]\n\n" if parts else ""


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
    # Fills data/family_memory.json with a couple of polished example
    # characters/books ONLY if it doesn't exist yet (a fresh clone, or a
    # fresh Streamlit Cloud container -- data/ is gitignored real
    # runtime data, so a redeploy starts with none) -- never touches it
    # if real data is already there. See dadhero/seed.py.
    seed.ensure_seeded()
    st.session_state.agent = build_agent()
    st.session_state.history = []
if "story_library" not in st.session_state:
    # Deliberately separate from `history` -- "Start a new story" resets
    # the chat feed/agent context for a fresh conversation, but a parent
    # re-reading something made 10 minutes ago shouldn't lose it just
    # because they started a different story since. Not written to disk
    # (a page reload clears it, same as the rest of session_state) --
    # dadhero/memory.py's saved stories don't carry page image paths
    # (only title/idea/goal); the platform build's Supabase `pages`
    # table is the persisted version of this library, see
    # backend/README.md.
    #
    # Seeded with a couple of example books (dadhero/seed.py) so a new
    # visitor's Story Library isn't empty -- runs every new session
    # (unlike ensure_seeded() above), since this is session-only state
    # by design; returns [] harmlessly if there's no seed file.
    st.session_state.story_library = seed.get_seed_story_library()
if "active_character_name" not in st.session_state:
    # Which saved character the CURRENT story is about, if any -- set at
    # the "Use {name}" button click and refreshed whenever a
    # save_character/get_saved_character call is seen. Deliberately a
    # plain session_state value, not something re-derived from
    # agent.messages later: Strands' default SlidingWindowConversationManager
    # (window_size=40) trims old messages once a story's tool-call count
    # grows past it, so by the time a multi-page book finishes generating,
    # an earlier turn's character-selection call may simply no longer
    # exist in agent.messages to search for -- trimmed, not just
    # out-of-turn. Persisting the name directly at the moment it's known
    # sidesteps that entirely.
    st.session_state.active_character_name = None

quick_start_text: str | None = None

# Characters persist for real (dadhero/memory.py writes to
# data/family_memory.json), unlike story_library above -- a returning
# visitor should see their roster and jump straight into using one
# without hunting through the sidebar's "Story Universe" accordion or
# retyping a description the agent already has saved.
_studio_characters = memory.get_family_profile("default_family").get("characters", {})
if _studio_characters:
    st.markdown("##### 🎭 Your Characters")
    st.caption("Saved across visits -- pick one to star in a new story.")
    names = list(_studio_characters.keys())
    for row_start in range(0, len(names), 4):
        row_names = names[row_start : row_start + 4]
        cols = st.columns(len(row_names))
        for col, name in zip(cols, row_names):
            bible = _studio_characters[name]
            with col:
                ref = bible.get("reference_image_path")
                if ref and os.path.exists(ref):
                    st.markdown(f'<div class="dh-gallery-card">{_img_tag(ref)}</div>', unsafe_allow_html=True)
                else:
                    # No reference photo (a text-described character never
                    # gets one until a page is generated) -- a monogram
                    # avatar instead of a tiny icon lost in a huge empty
                    # square. Fixed height, not width-based aspect-ratio,
                    # so it doesn't balloon into a giant box on a wide
                    # column -- a real portrait's own aspect ratio still
                    # governs the branch above.
                    initial = (name.strip()[:1] or "?").upper()
                    st.markdown(
                        f'<div class="dh-gallery-card dh-avatar-placeholder">{initial}</div>',
                        unsafe_allow_html=True,
                    )
                subtitle = bible.get("relationship", "")
                if bible.get("role_in_story"):
                    subtitle += f" · {bible['role_in_story']}"
                st.caption(f"**{name}**  \n{subtitle}")
                if st.button(f"✨ Use {name}", key=f"use_char_{name}", use_container_width=True):
                    quick_start_text = f"Use my saved character {name} for a new story."
                    st.session_state.active_character_name = name
    st.divider()

if st.session_state.story_library:
    st.markdown("##### 📚 Your Story Library")
    st.caption("Everything made this session -- click a cover to read it again, any time.")
    recent_first = list(reversed(st.session_state.story_library))[:8]
    for row_start in range(0, len(recent_first), 4):
        row = recent_first[row_start : row_start + 4]
        cols = st.columns(len(row))
        for col, story in zip(cols, row):
            with col:
                if os.path.exists(story["thumb"]):
                    st.markdown(f'<div class="dh-gallery-card">{_img_tag(story["thumb"])}</div>', unsafe_allow_html=True)
                st.caption(story["title"][:44])
                if st.button("Read Book →", key=f"read_story_{story['id']}", use_container_width=True):
                    st.session_state.reading_story_id = story["id"]
                    st.session_state.reader_page_idx = 0
                    st.rerun()

    if st.session_state.get("reading_story_id") is not None:
        match = next((s for s in st.session_state.story_library if s["id"] == st.session_state.reading_story_id), None)
        if match and match["pages"]:
            pages = match["pages"]
            idx = max(0, min(st.session_state.get("reader_page_idx", 0), len(pages) - 1))
            page = pages[idx]
            with st.container(border=True):
                title_col, close_col = st.columns([5, 1])
                with title_col:
                    st.markdown(
                        f'<div class="dh-book-title">{html.escape(match["title"])}</div>', unsafe_allow_html=True
                    )
                with close_col:
                    if st.button("✕ Close", key="close_reading", use_container_width=True):
                        st.session_state.reading_story_id = None
                        st.rerun()

                st.markdown(f'<div class="dh-panel-label">{page["label"]}</div>', unsafe_allow_html=True)
                if os.path.exists(page["image_path"]):
                    st.markdown(f'<div class="dh-panel dh-book-page">{_img_tag(page["image_path"])}</div>', unsafe_allow_html=True)
                else:
                    st.caption(f"(missing image: {page['image_path']})")

                prev_col, mid_col, next_col = st.columns([1, 2, 1])
                with prev_col:
                    if st.button("← Prev", key="reader_prev", disabled=idx == 0, use_container_width=True):
                        st.session_state.reader_page_idx = idx - 1
                        st.rerun()
                with mid_col:
                    st.markdown(
                        f'<div class="dh-book-pagecount">{idx + 1} / {len(pages)}</div>', unsafe_allow_html=True
                    )
                with next_col:
                    if st.button("Next →", key="reader_next", disabled=idx == len(pages) - 1, use_container_width=True):
                        st.session_state.reader_page_idx = idx + 1
                        st.rerun()
    st.divider()

with st.sidebar:
    st.subheader("🌟 Session")
    if st.button("Start a new story"):
        st.session_state.agent = build_agent()
        st.session_state.history = []
        st.session_state.pending_plan = None
        st.session_state.pending_drawing_path = None
        st.session_state.drawing_preview_path = None
        st.session_state.active_character_name = None
        st.session_state.last_approved_plan_title = None
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

    with st.expander("⚙️ Story settings", expanded=True):
        st.caption("Applies to your next message -- passed straight to the agent as an explicit constraint, not just a hint.")
        st.number_input("Child's age", min_value=2, max_value=12, value=None, key="setting_age", placeholder="Any")
        st.selectbox("Tone", ["Any", "Funny", "Adventure", "Calm", "Emotional"], key="setting_tone")
        st.selectbox("Length", ["Default (5-8 pages)", "Short (5-8 pages)", "Medium (9-12 pages)", "Long (13-16 pages)"], key="setting_length")
        st.select_slider("Scary/tension level", options=["Very gentle", "Gentle", "Adventurous"], value="Gentle", key="setting_scary")
        st.selectbox(
            "Educational goal",
            ["None", "Courage", "Kindness", "Sharing", "Responsibility", "Honesty", "Dealing with fear", "Friendship"],
            key="setting_goal",
        )
        st.selectbox("Art style", list(ART_STYLES.keys()), key="setting_style")
        st.text_input("Characters to include (e.g. Grandma)", key="setting_include")
        st.text_input("Characters/things to avoid (e.g. dragons)", key="setting_avoid")

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

# Human-in-the-loop checkpoint: the agent stops right after create_story_plan
# (see agent.py's step 6) instead of going straight to illustration -- the
# parent gets to reorder/reword/drop a page before any art (or API cost) is
# spent on it, not just react after the fact. Approving (with or without
# edits) sends one follow-up message that resumes the SAME conversation.
if st.session_state.get("pending_plan"):
    plan = st.session_state.pending_plan
    slug = plan.get("story_slug", "plan")
    # "page_beats" (the tool call's own argument name) is the reliable
    # field -- Strands passes a dict return through UNCHANGED when it
    # already has both "status" and "content" keys (create_story_plan's
    # does, for a friendly Workshop-panel message), which means the extra
    # title/beats/page_count fields never make it into the JSON-parsed
    # toolResult _extract_tool_trace reads for its "output" side. "beats"
    # is kept as a fallback in case that ever changes.
    beats = plan.get("page_beats") or plan.get("beats") or []
    with st.container():
        st.markdown('<div class="dh-workshop-label">📐 Review the plan before illustrating</div>', unsafe_allow_html=True)
        with st.form(key=f"plan_form_{slug}"):
            edited_title = st.text_input("Title", value=plan.get("title", ""))
            st.caption(f"Template: {plan.get('template_key', '')} · {len(beats)} pages")
            edited_beats = []
            for i, beat in enumerate(beats):
                edited_beats.append(st.text_area(f"Page {i + 1}", value=beat, height=60, key=f"beat_{slug}_{i}"))
            approved = st.form_submit_button("✅ Generate the book", use_container_width=True)
        if st.button("🔄 Scrap this plan, start over", key=f"scrap_{slug}"):
            st.session_state.pending_plan = None
            st.rerun()
        if approved:
            changed = edited_title != plan.get("title") or edited_beats != beats
            if changed:
                pages_list = "; ".join(f"{i + 1}) {b}" for i, b in enumerate(edited_beats))
                quick_start_text = (
                    f"I edited the plan -- please call create_story_plan again with these "
                    f"updated pages (same story_slug \"{slug}\"), then generate the book: "
                    f"title \"{edited_title}\"; pages: {pages_list}."
                )
            else:
                quick_start_text = "The plan looks good as-is -- please generate the book now, starting with the cover."
            # Stashed here, not read from pending_plan later -- this line
            # clears pending_plan in THIS SAME script run, before the
            # generation turn that actually produces the pages even
            # starts, so by the time that turn's code runs pending_plan is
            # already None. edited_title covers the parent having just
            # retitled it in the form, still with no markdown/preamble.
            st.session_state.last_approved_plan_title = edited_title or plan.get("title")
            st.session_state.pending_plan = None

# After at least one reply, offer to continue the same character/universe
# into a new book -- the agent's system prompt (step 2a) knows to reuse
# the saved character and keep it feeling like the next chapter, not an
# unrelated story.
if st.session_state.history and st.session_state.history[-1][0] == "assistant":
    if st.button("🔮 Continue this adventure", key="continue_adventure"):
        quick_start_text = "Continue this adventure -- write the next chapter in the same Story Universe, for the same hero."

with st.expander("✏️ Draw a sketch (instead of uploading a photo)", expanded=False):
    if not CANVAS_AVAILABLE:
        st.info(
            "The in-browser sketch canvas is temporarily unavailable in this "
            "deployment. Upload a drawing as a photo below instead -- it works "
            "exactly the same way once it's a file."
        )
    else:
        st.caption(
            "For the child's own drawing brought to life -- draw it right here, no "
            "scanner/photo needed. Safe for any subject, including the child "
            "themselves (see the safety note above: this is NOT a photo likeness). "
            "Sketch, then '✨ See Gemini's version' to preview the stylized art as "
            "many times as you like before using it."
        )
        draw_col, preview_col = st.columns(2)
        with draw_col:
            st.caption("Your sketch")
            canvas_result = st_canvas(
                stroke_width=6,
                stroke_color="#2E241A",
                background_color="#FFFFFF",
                height=320,
                width=400,
                drawing_mode="freedraw",
                return_image_data=True,
                key="drawing_canvas",
            )
        with preview_col:
            st.caption("Gemini's version")
            preview_slot = st.container(height=320, border=True)
            if st.session_state.get("drawing_preview_path"):
                preview_slot.image(st.session_state.drawing_preview_path)
            else:
                preview_slot.caption("Draw something, then click below to preview it.")

        preview_btn_col, use_btn_col = st.columns(2)
        with preview_btn_col:
            if st.button("✨ See Gemini's version", key="preview_drawing", use_container_width=True):
                if canvas_result.image_data is not None and canvas_result.image_data[:, :, 3].any():
                    # Direct tool call, not a full agent turn -- this is a fast
                    # preview loop (draw, check, draw more), not a chat message;
                    # going through the agent/model for every click would be far
                    # slower for no benefit here.
                    sketch_path = save_canvas_drawing(canvas_result.image_data)
                    selected_style = st.session_state.get("setting_style", "Storybook (default)")
                    with st.spinner("Gemini is illustrating your sketch..."):
                        result = stylize_drawing(
                            drawing_path=sketch_path,
                            output_name=f"preview_{uuid.uuid4().hex[:8]}",
                            art_style=None if selected_style.startswith("Storybook") else selected_style,
                        )
                    if result.get("status") == "error":
                        st.error(result["content"][0]["text"])
                    else:
                        st.session_state.drawing_preview_path = result["image_path"]
                        st.rerun()
                else:
                    st.warning("The canvas is empty -- draw something first.")
        with use_btn_col:
            if st.button("Use this drawing", key="use_drawing", use_container_width=True):
                if canvas_result.image_data is not None and canvas_result.image_data[:, :, 3].any():
                    st.session_state.pending_drawing_path = save_canvas_drawing(canvas_result.image_data)
                    st.session_state.drawing_preview_path = None
                    st.success("Saved -- it'll attach to your next message below.")
                else:
                    st.warning("The canvas is empty -- draw something first.")

if st.session_state.get("pending_drawing_path"):
    st.caption(f"📎 Drawing ready to attach: {Path(st.session_state.pending_drawing_path).name}")

# The core "real life -> story" moment: a parent doesn't need an idea, a
# theme, or a costume -- just what actually happened today. Routes into
# the system prompt's existing case 2b (a real memory becomes tonight's
# story), but the button itself already IS the parent's yes, so the
# message says so explicitly rather than letting the agent pause to ask.
with st.container(border=True):
    st.markdown("##### ⭐ Make tonight's story")
    st.caption("Something that really happened today, turned into tonight's bedtime story.")
    today_input_col, today_button_col = st.columns([4, 1])
    with today_input_col:
        today_event = st.text_input(
            "What happened today?",
            placeholder="e.g. Baki helped his grandfather feed the horses today.",
            key="today_event_input",
        )
    with today_button_col:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        make_tonight_clicked = st.button("✨ Make it", key="make_tonight_story", use_container_width=True)
    if make_tonight_clicked:
        if today_event.strip():
            quick_start_text = (
                f'Today: "{today_event.strip()}" -- please turn this into tonight\'s story right now, '
                "fictionalized but keeping the real moment recognizable. I already want it made -- no "
                "need to ask first, go ahead."
            )
        else:
            st.warning("Tell me what happened today first.")

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

    if st.session_state.get("pending_drawing_path"):
        drawing_path = st.session_state.pending_drawing_path
        user_text += f"\n\n[Uploaded file: {drawing_path}]"
        display_text += f"\n\n![attached drawing]({drawing_path})"
        st.session_state.pending_drawing_path = None

    st.session_state.history.append(("user", display_text))
    with st.chat_message("user", avatar="🙂"):
        render_story(display_text)

    # The settings prefix goes to the AGENT only -- the parent already
    # set these via the widgets above, echoing the bracketed line back
    # into their own chat bubble would just be noise.
    user_text = _settings_prefix() + user_text

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

        # See agent.py step 6: the agent stops right after create_story_plan
        # (no generate_page_image yet) so the parent can review/edit it --
        # that turn's own trace is the source of truth for whether this just
        # happened, not a flag the model might forget to clear.
        plan_calls = [t for t in this_turn if t["name"] == "create_story_plan"]
        page_calls = [t for t in this_turn if t["name"] == "generate_page_image"]

        # The clean title the parent actually typed/approved (from
        # create_story_plan), for the Story Library card/reader -- NOT the
        # reply text, which is the agent's own conversational sentence
        # ("Here is the finished story for **X**!") and looks wrong as a
        # book title. Read from last_approved_plan_title (stashed at the
        # "Generate the book" click, above) rather than pending_plan
        # itself -- that same click already nulls pending_plan in the SAME
        # script run, before the generation turn below even starts, so
        # pending_plan itself is already gone by the time this code runs.
        clean_title = st.session_state.get("last_approved_plan_title")
        if not clean_title and plan_calls:
            clean_title = plan_calls[-1]["input"].get("title") or plan_calls[-1]["output"].get("title")

        if plan_calls and not page_calls:
            # story_slug only lives in the call's input (it's not part of
            # what the tool returns); beats/page_count only in its output
            # (capped, post-validation) -- merge both into one plan dict.
            st.session_state.pending_plan = {**plan_calls[-1]["input"], **plan_calls[-1]["output"]}
        elif page_calls:
            st.session_state.pending_plan = None

        # Whenever THIS turn touches a saved character, remember its name
        # in session_state (not just locally) -- see active_character_name's
        # init comment above for why: the character-selection call and the
        # page-generation calls are usually in DIFFERENT turns (the
        # plan-approval pause splits them), and by the time the later turn
        # finishes, Strands' sliding-window trimming may have already
        # dropped the earlier turn's call from agent.messages, so it can't
        # be recovered by searching the trace at that point either.
        char_calls = [t for t in this_turn if t["name"] in ("save_character", "save_character_from_photo", "get_saved_character")]
        if char_calls:
            char_input, char_output = char_calls[-1]["input"], char_calls[-1]["output"]
            seen_name = char_input.get("character_name") or (char_output or {}).get("character_name")
            if seen_name:
                st.session_state.active_character_name = seen_name

        # Backfill the saved character's portrait once real art exists --
        # save_character (the text-description path, the common case)
        # never sets reference_image_path, only save_character_from_photo
        # does, so the Characters gallery above showed a placeholder
        # monogram forever even after the agent had already drawn this
        # character beautifully. First successful page/cover this
        # character ever gets "sticks" as its portrait.
        char_name = st.session_state.get("active_character_name")
        if char_name and page_calls:
            first_page_path = (page_calls[0].get("output") or {}).get("image_path")
            if first_page_path and os.path.exists(first_page_path):
                existing = memory.get_character("default_family", char_name)
                if existing and not existing.get("reference_image_path"):
                    existing["reference_image_path"] = first_page_path
                    memory.save_character("default_family", char_name, existing)

        # Turn this turn's real generate_page_image calls into Story
        # Library pages -- built from the TOOL CALLS themselves (reliable
        # page_slug + image_path), not by regex-scraping the reply text.
        # This is also what makes revision provably surgical: if a page's
        # slug already belongs to an existing story, it's a REVISION --
        # only that one page's image_path is replaced in place, every
        # other page (and the reader's current position) is untouched.
        # If none of this turn's slugs are already known, it's a new
        # story finishing generation.
        new_pages = []
        for pc in page_calls:
            img_path = (pc.get("output") or {}).get("image_path")
            if not img_path:
                continue
            new_pages.append(
                {
                    "slug": pc["input"].get("page_slug", ""),
                    "image_path": img_path,
                    "is_cover": bool((pc.get("output") or {}).get("is_cover", False)),
                }
            )

        if new_pages:
            target_story = None
            for story in st.session_state.story_library:
                existing_slugs = {p["slug"] for p in story["pages"]}
                if any(p["slug"] in existing_slugs for p in new_pages):
                    target_story = story
                    break

            if target_story is not None:
                by_slug = {p["slug"]: p for p in new_pages}
                for page in target_story["pages"]:
                    if page["slug"] in by_slug:
                        page["image_path"] = by_slug[page["slug"]]["image_path"]
                cover_page = next((p for p in target_story["pages"] if p["is_cover"]), None)
                target_story["thumb"] = (cover_page or target_story["pages"][0])["image_path"]
            else:
                cover = next((p for p in new_pages if p["is_cover"]), None)
                ordered = ([cover] if cover else []) + [p for p in new_pages if not p["is_cover"]]
                page_num = 0
                labeled = []
                for p in ordered:
                    if p["is_cover"]:
                        label = "Cover"
                    else:
                        page_num += 1
                        label = f"Page {page_num}"
                    labeled.append({**p, "label": label})
                if clean_title:
                    title_line = clean_title
                else:
                    # Fallback only -- the model skipped create_story_plan
                    # entirely (shouldn't happen per agent.py step 6, but
                    # don't leave the card titleless if it ever does).
                    image_matches = list(_IMAGE_MD.finditer(response_text))
                    before_first = response_text[: image_matches[0].start()].strip() if image_matches else ""
                    title_line = next(
                        (line.strip(" #*") for line in before_first.splitlines() if line.strip()), "Untitled story"
                    )
                st.session_state.story_library.append(
                    {
                        "id": uuid.uuid4().hex,
                        "title": title_line or "Untitled story",
                        "thumb": labeled[0]["image_path"],
                        "pages": labeled,
                    }
                )

    st.session_state.history.append(("assistant", response_text))

    # The pending_plan form, Characters gallery, and Story Library are
    # all rendered near the TOP of the script -- before this whole
    # turn-processing block runs -- so setting/appending to any of them
    # here, this late, doesn't retroactively draw them in THIS pass.
    # Rerun so the very next script pass shows the plan, the new library
    # card, or a just-enriched character portrait immediately, instead
    # of only after some unrelated later interaction.
    if st.session_state.get("pending_plan") or page_calls:
        st.rerun()
