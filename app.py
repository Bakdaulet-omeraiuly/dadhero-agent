"""
DadHero demo UI (Streamlit).

Run with: streamlit run app.py

Renders the agent's markdown response directly -- it already contains
page text plus ![](image_path) references, which Streamlit's markdown
renderer displays as images since the paths are local files.
"""

from __future__ import annotations

import os

import streamlit as st

from dadhero.agent import build_agent

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

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

user_text = st.chat_input("Describe your idea...")

if user_text:
    st.session_state.history.append(("user", user_text))
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Making the story..."):
            result = st.session_state.agent(user_text)
            response_text = str(result)
        st.markdown(response_text)

        tool_calls = [
            block["toolUse"]["name"]
            for msg in st.session_state.agent.messages
            for block in msg.get("content", [])
            if isinstance(block, dict) and "toolUse" in block
        ]
        if tool_calls:
            st.caption("Tool calls this turn: " + " → ".join(tool_calls[-10:]))

    st.session_state.history.append(("assistant", response_text))
