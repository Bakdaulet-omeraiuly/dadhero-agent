"""Tests for the newer tool-based checkpoints: create_story_plan
(planning as a real, recorded call), check_visual_consistency (fails
open whenever there's nothing meaningful to check), audit_story_continuity
(the post-generation review pass), and generate_page_image's cover flag.
No live model or image-API calls -- same discipline as test_dadhero.py."""

from __future__ import annotations

from pathlib import Path

from dadhero import continuity, vision_check
from dadhero.safety import check_age_appropriateness
from dadhero.tools import audit_story_continuity, create_story_plan, generate_page_image, stylize_drawing


def test_create_story_plan_records_and_returns_the_plan():
    continuity.reset_story("plan_story_a")
    result = create_story_plan(
        title="Arman and the Star",
        story_slug="plan_story_a",
        template_key="small_adventure",
        page_beats=["Arman finds a lost star", "They journey home together"],
    )
    assert result["page_count"] == 2
    assert result["title"] == "Arman and the Star"
    stored = continuity.get_story_plan("plan_story_a")
    assert stored["page_count"] == 2
    assert stored["beats"] == ["Arman finds a lost star", "They journey home together"]


def test_create_story_plan_caps_at_sixteen_pages():
    continuity.reset_story("plan_story_b")
    beats = [f"beat {i}" for i in range(20)]
    result = create_story_plan(
        title="Very Long Story",
        story_slug="plan_story_b",
        template_key="small_adventure",
        page_beats=beats,
    )
    assert result["page_count"] == 16
    assert len(continuity.get_story_plan("plan_story_b")["beats"]) == 16


def test_audit_story_continuity_reports_facts_and_plan():
    continuity.reset_story("plan_story_c")
    continuity.check_and_record_fact("plan_story_c", "backpack_color", "red")
    create_story_plan(
        title="Test",
        story_slug="plan_story_c",
        template_key="bedtime_wind_down",
        page_beats=["one", "two", "three"],
    )
    report = audit_story_continuity("plan_story_c")
    assert report["fact_count"] == 1
    assert report["facts"]["backpack_color"] == "red"
    assert report["planned_page_count"] == 3


def test_audit_story_continuity_handles_a_story_with_no_plan_recorded():
    continuity.reset_story("plan_story_d")
    report = audit_story_continuity("plan_story_d")
    assert report["fact_count"] == 0
    assert report["planned_page_count"] is None


def test_visual_consistency_check_skips_under_mock_provider(monkeypatch):
    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "mock")
    result = vision_check.check_consistency("page.png", "ref.png", "a brave dad")
    assert result["consistent"] is True
    assert "mock" in result["notes"].lower()


def test_visual_consistency_check_skips_when_files_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    result = vision_check.check_consistency(
        str(tmp_path / "missing_page.png"), str(tmp_path / "missing_ref.png"), "a brave dad"
    )
    assert result["consistent"] is True
    assert "found" in result["notes"].lower()


def test_visual_consistency_check_skips_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    page = tmp_path / "page.png"
    ref = tmp_path / "ref.png"
    page.write_bytes(b"fake")
    ref.write_bytes(b"fake")
    result = vision_check.check_consistency(str(page), str(ref), "a brave dad")
    assert result["consistent"] is True
    assert "GEMINI_API_KEY" in result["notes"]


def test_generate_page_image_marks_cover_pages(monkeypatch, tmp_path):
    import dadhero.image_providers as ip

    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "mock")
    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("dadhero.storage.persist", lambda path: path)

    result = generate_page_image(
        scene_description="Arman stands proudly under a starry sky",
        character_prompt_fragment="Arman: a brave boy",
        page_slug="arman_cover",
        caption_text="Arman and the Star",
        is_cover=True,
    )
    assert result["is_cover"] is True

    page_result = generate_page_image(
        scene_description="Arman waves at a passing star",
        character_prompt_fragment="Arman: a brave boy",
        page_slug="arman_p1",
        caption_text="Arman waved at the star.",
    )
    assert page_result["is_cover"] is False


def test_safety_flags_bullying_and_dangerous_content():
    bullying = check_age_appropriateness("The other kids started bullying him at recess.")
    assert bullying["passed"] is False
    assert "bullying" in bullying["concerning_terms_found"]

    matches = check_age_appropriateness("She found some matches and almost lit them.")
    assert matches["passed"] is False
    assert "matches" in matches["concerning_terms_found"]


def test_stylize_drawing_respects_art_style(monkeypatch, tmp_path):
    import dadhero.image_providers as ip

    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "mock")
    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("dadhero.storage.persist", lambda path: path)
    drawing = tmp_path / "sketch.png"
    drawing.write_bytes(b"fake")

    captured_prompts = []
    real_generate = ip.MockImageProvider.generate

    def spy_generate(self, prompt, **kwargs):
        captured_prompts.append(prompt)
        return real_generate(self, prompt, **kwargs)

    monkeypatch.setattr(ip.MockImageProvider, "generate", spy_generate)

    stylize_drawing(drawing_path=str(drawing), output_name="test_out", art_style="Pixel art")
    assert "pixel-art" in captured_prompts[0].lower()

    stylize_drawing(drawing_path=str(drawing), output_name="test_out2")
    assert "pixel-art" not in captured_prompts[1].lower()


def test_generate_page_image_style_conditions_only_comic_book(monkeypatch, tmp_path):
    """A real public-domain comic page should be sent as an extra
    reference ONLY for art_style="Comic book" -- every other style (or
    none) must generate exactly as before, no style reference at all."""
    import dadhero.image_providers as ip

    monkeypatch.setenv("DADHERO_IMAGE_PROVIDER", "mock")
    monkeypatch.setattr(ip, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("dadhero.storage.persist", lambda path: path)

    captured = []
    real_generate = ip.MockImageProvider.generate

    def spy_generate(self, prompt, **kwargs):
        captured.append(kwargs.get("style_reference_image_path"))
        return real_generate(self, prompt, **kwargs)

    monkeypatch.setattr(ip.MockImageProvider, "generate", spy_generate)

    comic_result = generate_page_image(
        scene_description="A hero waves hello",
        character_prompt_fragment="A brave kid",
        page_slug="style_test_comic",
        art_style="Comic book",
    )
    assert captured[-1] is not None
    assert Path(captured[-1]).name == "pep_comics_71_page35_1949.png"
    assert "style-condition" in comic_result["note"].lower()

    watercolor_result = generate_page_image(
        scene_description="A hero waves hello",
        character_prompt_fragment="A brave kid",
        page_slug="style_test_watercolor",
        art_style="Watercolor",
    )
    assert captured[-1] is None
    assert "style-condition" not in watercolor_result["note"].lower()

    no_style_result = generate_page_image(
        scene_description="A hero waves hello",
        character_prompt_fragment="A brave kid",
        page_slug="style_test_none",
    )
    assert captured[-1] is None
    assert "style-condition" not in no_style_result["note"].lower()
