"""
DadHero demo UI (Streamlit).

Run with: streamlit run app.py

The agent's response is markdown containing ![alt](local_path) image
references, but Streamlit's st.markdown() can't display local filesystem
images through that syntax (no static file route for them) -- it just
renders a broken-image icon. render_story() below splits the text on
those references and renders each text chunk with st.markdown() and each
image with st.image(), in order.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import streamlit as st

from dadhero.agent import build_agent

_IMAGE_MD = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"


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


def render_story(text: str) -> None:
    pos = 0
    for match in _IMAGE_MD.finditer(text):
        before = text[pos : match.start()].strip()
        if before:
            st.markdown(before)
        alt, path = match.group(1), match.group(2)
        if os.path.exists(path):
            st.image(path, caption=alt or None, width="stretch")
        else:
            st.caption(f"(missing image: {path})")
        pos = match.end()
    tail = text[pos:].strip()
    if tail:
        st.markdown(tail)

st.set_page_config(page_title="DadHero", page_icon="🦸", layout="centered")

st.title("🦸 DadHero")
st.caption("Tell it your idea. It turns a family member into your child's comic-book hero.")

if "agent" not in st.session_state:
    st.session_state.agent = build_agent()
    st.session_state.history = []

with st.sidebar:
    st.subheader("Session")
    if st.button("Start a new story"):
        st.session_state.agent = build_agent()
        st.session_state.history = []
        st.rerun()

    provider = os.environ.get("DADHERO_IMAGE_PROVIDER", "mock")
    if provider == "mock":
        st.warning("Image provider: **mock** (placeholder art). Set DADHERO_IMAGE_PROVIDER=gemini for real illustrations.")
    else:
        st.success(f"Image provider: **{provider}**")

    st.subheader("Why this is an agent")
    st.markdown(
        "- Builds a **Character Bible** once, reuses it verbatim per page\n"
        "- Plans a 5-8 page story arc from a proven template\n"
        "- Calls `generate_page_image` once per page, chaining a\n"
        "  reference image forward for visual consistency\n"
        "- Regenerates only the page you flag on feedback\n"
        "- Remembers the character across future stories"
    )

    st.subheader("Try")
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

for role, text in st.session_state.history:
    with st.chat_message(role):
        if role == "assistant":
            render_story(text)
        else:
            render_story(text)  # user turns may also carry an attached image reference

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
    with st.chat_message("user"):
        render_story(display_text)

    with st.chat_message("assistant"):
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
            st.caption("Tool calls this turn: " + " → ".join(tool_calls[-10:]))

    st.session_state.history.append(("assistant", response_text))
