"""
Tests for the photo/drawing upload safety boundary: a real photo may only
become a character's appearance for an ADULT relationship; a child's own
drawing is unrestricted since it isn't a photographic likeness of a real
face. This is the one rule in the whole project that must never regress.
"""

from __future__ import annotations

from dadhero.safety import is_minor_relationship
from dadhero.tools import save_character_from_photo, stylize_drawing


def test_minor_relationships_are_detected():
    for term in ["daughter", "son", "my kid", "the child", "our toddler", "his student"]:
        assert is_minor_relationship(term), f"'{term}' should be flagged as a minor relationship"


def test_adult_relationships_are_not_flagged():
    for term in ["dad", "mom", "husband", "wife", "grandma", "uncle", "myself", "a family friend"]:
        assert not is_minor_relationship(term), f"'{term}' should NOT be flagged as a minor relationship"


def test_save_character_from_photo_refuses_a_child_relationship(tmp_path):
    fake_photo = tmp_path / "photo.png"
    fake_photo.write_bytes(b"fake")

    result = save_character_from_photo(
        photo_path=str(fake_photo),
        character_name="Aisha",
        relationship="daughter",
    )
    assert result["status"] == "error"
    assert "child" in result["content"][0]["text"].lower() or "refused" in result["content"][0]["text"].lower()


def test_save_character_from_photo_proceeds_for_an_adult_relationship(tmp_path, monkeypatch):
    import dadhero.tools as tools_mod

    fake_photo = tmp_path / "photo.png"
    fake_photo.write_bytes(b"fake")

    # Force mock provider regardless of environment so this test never
    # depends on network/API keys.
    monkeypatch.setattr(tools_mod, "get_provider", lambda: __import__("dadhero.image_providers", fromlist=["MockImageProvider"]).MockImageProvider())
    monkeypatch.setattr(tools_mod.memory, "MEMORY_PATH", tmp_path / "family_memory.json")

    import dadhero.image_providers as ip

    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path / "generated")

    result = save_character_from_photo(
        photo_path=str(fake_photo),
        character_name="Papa Nurlan",
        relationship="dad",
        family_id="test_family",
    )
    assert "error" not in result or result.get("status") != "error"
    assert result["character_name"] == "Papa Nurlan"
    assert "reference_image_path" in result


def test_stylize_drawing_has_no_relationship_restriction(tmp_path, monkeypatch):
    import dadhero.image_providers as ip
    import dadhero.tools as tools_mod

    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(tools_mod, "get_provider", lambda: ip.MockImageProvider())

    drawing = tmp_path / "drawing.png"
    drawing.write_bytes(b"fake")

    result = stylize_drawing(drawing_path=str(drawing), output_name="monster1")
    assert "image_path" in result
