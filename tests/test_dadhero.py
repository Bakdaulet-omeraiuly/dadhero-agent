"""
Pytest suite for the parts of DadHero that don't need a live model:
models, memory persistence, and the mock image provider's pipeline
wiring. Agent behavior (story planning quality, feedback handling,
character consistency reasoning) needs a live LLM and was verified
manually -- see README.md's transcript.
"""

from __future__ import annotations

import importlib

import dadhero.memory as memory
from dadhero.image_providers import GeneratedImage, MockImageProvider, get_provider
from dadhero.models import STORY_TEMPLATES, CharacterBible


def test_character_bible_prompt_fragment_includes_all_fields():
    bible = CharacterBible(
        character_name="Papa Nurlan",
        relationship="dad",
        appearance="short black hair, glasses, red hoodie",
        personality_traits=["brave", "warm"],
        role_in_story="astronaut",
    )
    fragment = bible.prompt_fragment()
    assert "Papa Nurlan" in fragment
    assert "dad" in fragment
    assert "astronaut" in fragment
    assert "red hoodie" in fragment
    assert "brave" in fragment


def test_character_bible_handles_no_role_or_traits():
    bible = CharacterBible(character_name="Mom", relationship="mom", appearance="curly hair")
    fragment = bible.prompt_fragment()
    assert "Mom" in fragment
    assert "warm and kind" in fragment  # default trait phrase


def test_story_templates_have_beats():
    for key, template in STORY_TEMPLATES.items():
        assert "label" in template
        assert len(template["beats"]) >= 4


def test_memory_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")

    empty = memory.get_family_profile("fam1")
    assert empty["characters"] == {} and empty["stories"] == []  # full schema covered in test_story_universe.py

    saved = memory.save_character("fam1", "Papa Nurlan", {"appearance": "red hoodie"})
    assert saved["appearance"] == "red hoodie"
    assert memory.get_character("fam1", "Papa Nurlan")["appearance"] == "red hoodie"
    assert memory.get_character("fam1", "Someone Else") is None

    memory.record_story("fam1", "Space Star", "astronaut saves a star", "small_adventure")
    profile = memory.get_family_profile("fam1")
    assert len(profile["stories"]) == 1
    assert profile["stories"][0]["title"] == "Space Star"

    memory.reset_family("fam1")
    reset = memory.get_family_profile("fam1")
    assert reset["characters"] == {} and reset["stories"] == []


def test_mock_image_provider_writes_a_real_file(tmp_path, monkeypatch):
    import dadhero.image_providers as ip

    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    provider = MockImageProvider()
    result = provider.generate("A brave astronaut dad", output_name="test_page")

    assert isinstance(result, GeneratedImage)
    assert result.provider == "mock"
    assert (tmp_path / "test_page.png").exists()
    assert (tmp_path / "test_page.png").stat().st_size > 0


def test_mock_image_provider_notes_reference_image(tmp_path, monkeypatch):
    import dadhero.image_providers as ip

    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    provider = MockImageProvider()
    ref = tmp_path / "page1.png"
    ref.write_bytes(b"fake")
    result = provider.generate("Scene 2", output_name="page2", reference_image_path=str(ref))
    assert "page1.png" in result.note or "condition" in result.note.lower()


def test_get_provider_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("DADHERO_IMAGE_PROVIDER", raising=False)
    assert isinstance(get_provider(), MockImageProvider)


def test_get_provider_selects_gemini_when_configured(monkeypatch):
    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-only")
    provider = get_provider()
    assert provider.__class__.__name__ == "GeminiImageProvider"
