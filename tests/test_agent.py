"""Structural check that the Agent builds with the right tools -- no live model call."""

from __future__ import annotations

import os

os.environ.setdefault("DADHERO_MODEL_PROVIDER", "bedrock")

from dadhero.agent import build_agent  # noqa: E402

EXPECTED_TOOLS = {
    "save_character",
    "save_character_from_photo",
    "stylize_drawing",
    "get_saved_character",
    "generate_page_image",
    "get_family_memory",
    "check_story_fact",
    "check_page_safety",
    "record_finished_story",
}


def test_agent_builds_with_expected_tools():
    agent = build_agent()
    assert set(agent.tool_names) == EXPECTED_TOOLS


def test_agent_has_no_default_stdout_callback():
    from strands.handlers.callback_handler import PrintingCallbackHandler

    agent = build_agent()
    assert not isinstance(agent.callback_handler, PrintingCallbackHandler)
