"""
Tests for the Story Universe memory schema: places, real memories, and
Before -> During -> After progress tracking on top of the existing
characters/stories. The regression this guards against is real: an
earlier version of _family() shared one literal {} default dict across
every family_id, so writing to family A silently corrupted family B.
"""

from __future__ import annotations

from dadhero import memory


def test_new_family_gets_full_empty_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")
    profile = memory.get_family_profile("brand_new_family")
    assert profile == {
        "characters": {},
        "places": {},
        "stories": [],
        "memories": [],
        "lessons_taught": [],
        "progress": [],
    }


def test_families_do_not_share_state(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")

    memory.save_character("fam_a", "Dad", {"x": 1})
    memory.record_memory("fam_a", "Trip to Kazakhstan")

    fam_b = memory.get_family_profile("fam_b")
    assert fam_b["characters"] == {}
    assert fam_b["memories"] == []

    fam_a = memory.get_family_profile("fam_a")
    assert "Dad" in fam_a["characters"]
    assert len(fam_a["memories"]) == 1


def test_save_place_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")
    memory.save_place("fam1", "Grandma's House", "a cozy cottage with a red door")
    profile = memory.get_family_profile("fam1")
    assert profile["places"]["Grandma's House"] == "a cozy cottage with a red door"


def test_record_story_with_goal_also_tracks_lesson(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")
    memory.record_story("fam1", "The Sharing Box", "teach sharing", "problem_helper_solution", goal="sharing")
    profile = memory.get_family_profile("fam1")
    assert profile["stories"][0]["goal"] == "sharing"
    assert "sharing" in profile["lessons_taught"]


def test_record_story_without_goal_does_not_pollute_lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")
    memory.record_story("fam1", "Just a Fun Adventure", "space fun", "small_adventure")
    profile = memory.get_family_profile("fam1")
    assert profile["stories"][0]["goal"] is None
    assert profile["lessons_taught"] == []


def test_record_progress_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "family_memory.json")
    memory.record_progress("fam1", "Arman", "shared his dinosaur today", "The Dinosaur Village")
    profile = memory.get_family_profile("fam1")
    assert profile["progress"][0] == {
        "related_to": "Arman",
        "update": "shared his dinosaur today",
        "story_title": "The Dinosaur Village",
    }


def test_older_family_record_without_new_fields_gets_backfilled(tmp_path, monkeypatch):
    """Simulates a family_memory.json saved before Story Universe fields existed."""
    import json

    path = tmp_path / "family_memory.json"
    path.write_text(json.dumps({"old_family": {"characters": {"Dad": {}}, "stories": []}}))
    monkeypatch.setattr(memory, "MEMORY_PATH", path)

    profile = memory.get_family_profile("old_family")
    assert profile["characters"] == {"Dad": {}}
    assert profile["places"] == {}
    assert profile["memories"] == []
    assert profile["progress"] == []
