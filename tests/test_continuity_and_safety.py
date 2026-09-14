"""Tests for the continuity fact-tracker and the age-appropriateness screen."""

from __future__ import annotations

from dadhero import continuity
from dadhero.safety import check_age_appropriateness


def test_first_fact_is_recorded_ok():
    continuity.reset_story("story_a")
    result = continuity.check_and_record_fact("story_a", "backpack_color", "red")
    assert result["status"] == "ok"


def test_matching_repeat_fact_is_still_ok():
    continuity.reset_story("story_b")
    continuity.check_and_record_fact("story_b", "backpack_color", "red")
    result = continuity.check_and_record_fact("story_b", "backpack_color", "Red")  # case-insensitive
    assert result["status"] == "ok"


def test_conflicting_fact_is_flagged():
    continuity.reset_story("story_c")
    continuity.check_and_record_fact("story_c", "backpack_color", "red")
    result = continuity.check_and_record_fact("story_c", "backpack_color", "blue")
    assert result["status"] == "conflict"
    assert result["previous_value"] == "red"
    assert result["new_value"] == "blue"


def test_facts_are_scoped_per_story():
    continuity.reset_story("story_d1")
    continuity.reset_story("story_d2")
    continuity.check_and_record_fact("story_d1", "location", "school")
    result = continuity.check_and_record_fact("story_d2", "location", "space station")
    assert result["status"] == "ok"  # different story, no conflict


def test_safe_text_passes():
    result = check_age_appropriateness("The baby star giggled and floated home to its family.", child_age=5)
    assert result["passed"] is True
    assert result["concerning_terms_found"] == []


def test_concerning_term_is_flagged():
    result = check_age_appropriateness("The dragon tried to kill the knight with a sword.", child_age=6)
    assert result["passed"] is False
    assert "kill" in result["concerning_terms_found"]


def test_overly_long_page_is_flagged_for_young_child():
    long_text = " ".join(["word"] * 200)
    result = check_age_appropriateness(long_text, child_age=4)
    assert result["passed"] is False
    assert result["length_flag"] is not None


def test_no_age_given_skips_length_check():
    long_text = " ".join(["word"] * 200)
    result = check_age_appropriateness(long_text, child_age=None)
    assert result["length_flag"] is None
