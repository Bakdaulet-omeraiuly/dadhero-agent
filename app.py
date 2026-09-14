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

import base64
import json
import os
import re
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml

from dadhero.agent import build_agent

_IMAGE_MD = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
_DEMO_DIR = Path(__file__).resolve().parent / "docs" / "demo"
_OPENAPI_PATH = Path(__file__).resolve().parent / "docs" / "api" / "openapi.yaml"

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

    /* Sidebar */
    [data-testid="stSidebar"] { background: var(--card); border-right: 2px solid var(--border); }
    [data-testid="stSidebar"] h3 { font-size: 17px !important; margin-top: 6px; }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: var(--card); border: 2px solid var(--border);
        border-radius: 18px; padding: 4px 6px; margin-bottom: 10px;
        box-shadow: 0 3px 10px var(--shadow);
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
    </style>
    """,
    unsafe_allow_html=True,
)


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


def render_api_reference() -> None:
    """Embed the designed (not yet implemented) OpenAPI spec as a Redoc
    panel inside the app itself -- one site, not a link out to a separate
    artifact. The spec is inlined as JSON directly into the component's
    HTML rather than fetched from a URL, since this runs in its own
    sandboxed iframe with no route to serve docs/api/openapi.yaml from."""
    if not _OPENAPI_PATH.exists():
        st.info("API spec not found at docs/api/openapi.yaml.")
        return

    with open(_OPENAPI_PATH, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    spec_json = json.dumps(spec)

    html = f"""
    <div id="redoc-container" style="background:#FBF5E9;"></div>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"></script>
    <script>
      Redoc.init({spec_json}, {{
        theme: {{
          colors: {{
            primary: {{ main: '#EE7B4F' }},
            success: {{ main: '#2F9C8F' }},
            text: {{ primary: '#2E241A', secondary: '#7A6B57' }},
            border: {{ dark: '#E9DCC0', light: '#F3EAD9' }},
            http: {{ get: '#2F9C8F', post: '#EE7B4F', patch: '#c9a227', delete: '#c0392b' }}
          }},
          typography: {{
            fontFamily: "'Nunito', sans-serif",
            headings: {{ fontFamily: "'Baloo 2', sans-serif" }},
            code: {{ fontSize: '13px' }}
          }},
          rightPanel: {{ backgroundColor: '#2E241A' }},
          sidebar: {{ backgroundColor: '#FFFDF8', textColor: '#2E241A' }}
        }},
        hideDownloadButton: false,
        expandResponses: '201,200',
      }}, document.getElementById('redoc-container'));
    </script>
    """
    components.html(html, height=1100, scrolling=True)


def render_story(text: str) -> None:
    pos = 0
    for match in _IMAGE_MD.finditer(text):
        before = text[pos : match.start()].strip()
        if before:
            st.markdown(before)
        alt, path = match.group(1), match.group(2)
        if os.path.exists(path):
            label = f'<div class="dh-panel-label">{alt}</div>' if alt else ""
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

tab_app, tab_api = st.tabs(["🦸 Story Maker", "📘 API Design"])

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

    st.subheader("🧠 Why this is an agent")
    st.markdown(
        "- Builds a **Character Bible** once, reuses it verbatim per page\n"
        "- Plans a 5-8 page story arc from a proven template\n"
        "- Chains a reference image forward for visual consistency\n"
        "- Regenerates only the page you flag on feedback\n"
        "- **Remembers** characters, places, goals & progress across sessions"
    )

    st.subheader("💬 Try")
    st.code(
        "My husband has short black hair, glasses, and a red\n"
        "hoodie. I want a 5-page comic where he's a brave\n"
        "astronaut who saves a lost baby star, for our\n"
        "5-year-old daughter.",
        language=None,
    )
    st.caption(
        "📎 attach a photo of an **adult** family member for a likeness-based "
        "portrait, or your child's own drawing to bring to life -- never a "
        "photo of the child (see the safety note in the README)."
    )

    st.divider()
    st.subheader("📘 For developers")
    st.caption(
        "See the **API Design** tab above for a designed (not yet built) "
        "REST API for a future web platform version of DadHero -- "
        "documentation only, embedded right here, no server behind it."
    )

with tab_app:
    # Show the page "at rest" with real generated proof instead of a blank
    # chat -- a first-time visitor sees what this actually makes before
    # typing anything.
    if not st.session_state.history and _DEMO_DIR.exists():
        demo_images = sorted(_DEMO_DIR.glob("example_page*.png"))
        if demo_images:
            st.markdown("##### 📖 A story DadHero actually made")
            cols = st.columns(len(demo_images))
            for col, img_path in zip(cols, demo_images):
                with col:
                    st.markdown(f'<div class="dh-gallery-card">{_img_tag(str(img_path))}</div>', unsafe_allow_html=True)
            st.caption("Real output -- same locked character, chained across pages. Now describe your own idea below.")
            st.divider()

    for role, text in st.session_state.history:
        with st.chat_message(role, avatar="🦸" if role == "assistant" else "🙂"):
            render_story(text)

    chat_value = st.chat_input(
        "Describe your idea, or attach a photo/drawing...",
        accept_file=True,
        file_type=["png", "jpg", "jpeg"],
    )

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

        st.session_state.history.append(("user", display_text))
        with st.chat_message("user", avatar="🙂"):
            render_story(display_text)

        with st.chat_message("assistant", avatar="🦸"):
            with st.spinner("Making the story..."):
                result = st.session_state.agent(user_text)
                response_text = str(result)
            render_story(response_text)

            tool_calls = [
                block["toolUse"]["name"]
                for msg in st.session_state.agent.messages
                for block in msg.get("content", [])
                if isinstance(block, dict) and "toolUse" in block
            ]
            if tool_calls:
                pills = "".join(f'<span class="dh-tool-pill">{name}</span>' for name in tool_calls[-10:])
                st.markdown(f'<div class="dh-tools">{pills}</div>', unsafe_allow_html=True)

        st.session_state.history.append(("assistant", response_text))

with tab_api:
    st.markdown("##### 🧩 DadHero REST API -- design, not yet built")
    st.caption(
        "OpenAPI 3.1 spec for a future web platform version of DadHero. "
        "No server implements this -- see docs/api/design-notes.md for the rationale."
    )
    render_api_reference()
