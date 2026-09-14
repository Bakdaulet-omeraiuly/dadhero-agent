"""dadhero/seed.py: fills an EMPTY data/family_memory.json with example
characters/books (for a fresh clone or a fresh, ephemeral Streamlit
Cloud container), but must never touch real existing data. No live
model or image-API calls."""

from __future__ import annotations

import json

from dadhero import seed


def test_ensure_seeded_does_nothing_when_real_data_already_exists(monkeypatch, tmp_path):
    real_memory = tmp_path / "family_memory.json"
    real_memory.write_text('{"default_family": {"characters": {"Someone": {}}}}', encoding="utf-8")
    monkeypatch.setattr(seed.memory, "MEMORY_PATH", real_memory)

    seed.ensure_seeded()

    assert json.loads(real_memory.read_text())["default_family"]["characters"] == {"Someone": {}}


def test_ensure_seeded_does_nothing_when_no_seed_file_exists(monkeypatch, tmp_path):
    missing_memory = tmp_path / "family_memory.json"
    monkeypatch.setattr(seed.memory, "MEMORY_PATH", missing_memory)
    monkeypatch.setattr(seed, "SEED_MEMORY_FILE", tmp_path / "no_such_seed.json")

    seed.ensure_seeded()

    assert not missing_memory.exists()


def test_ensure_seeded_copies_seed_and_rewrites_image_paths_to_current_output_dir(monkeypatch, tmp_path):
    seed_dir = tmp_path / "seed"
    seed_images = seed_dir / "generated_pages"
    seed_images.mkdir(parents=True)
    (seed_images / "hero_cover.png").write_bytes(b"fake-png")

    seed_memory_file = seed_dir / "family_memory.json"
    seed_memory_file.write_text(
        json.dumps(
            {
                "default_family": {
                    "characters": {
                        "Jake": {"reference_image_path": "/some/other/machine/path/hero_cover.png"}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    real_memory = tmp_path / "data" / "family_memory.json"
    output_dir = tmp_path / "data" / "generated_pages"
    monkeypatch.setattr(seed.memory, "MEMORY_PATH", real_memory)
    monkeypatch.setattr(seed, "SEED_MEMORY_FILE", seed_memory_file)
    monkeypatch.setattr(seed, "SEED_IMAGES_DIR", seed_images)
    monkeypatch.setattr(seed, "OUTPUT_DIR", output_dir)

    seed.ensure_seeded()

    assert real_memory.exists()
    data = json.loads(real_memory.read_text())
    rewritten_path = data["default_family"]["characters"]["Jake"]["reference_image_path"]
    assert rewritten_path == str(output_dir / "hero_cover.png")
    assert (output_dir / "hero_cover.png").exists()


def test_get_seed_story_library_returns_empty_list_without_a_seed_file(monkeypatch, tmp_path):
    monkeypatch.setattr(seed, "SEED_STORY_LIBRARY_FILE", tmp_path / "no_such_file.json")
    assert seed.get_seed_story_library() == []


def test_get_seed_story_library_skips_a_story_whose_images_are_missing_on_disk(monkeypatch, tmp_path):
    output_dir = tmp_path / "data" / "generated_pages"
    output_dir.mkdir(parents=True)
    story_file = tmp_path / "story_library.json"
    story_file.write_text(
        json.dumps(
            [
                {
                    "title": "A Story With No Real Files",
                    "pages": [{"slug": "x_cover", "label": "Cover", "image_path": "missing.png", "is_cover": True}],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(seed, "SEED_STORY_LIBRARY_FILE", story_file)
    monkeypatch.setattr(seed, "OUTPUT_DIR", output_dir)

    assert seed.get_seed_story_library() == []


def test_get_seed_story_library_resolves_real_pages_against_current_output_dir(monkeypatch, tmp_path):
    output_dir = tmp_path / "data" / "generated_pages"
    output_dir.mkdir(parents=True)
    (output_dir / "hero_cover.png").write_bytes(b"fake-png")
    (output_dir / "hero_page1.png").write_bytes(b"fake-png")

    story_file = tmp_path / "story_library.json"
    story_file.write_text(
        json.dumps(
            [
                {
                    "title": "Hero's Big Day",
                    "pages": [
                        {"slug": "hero_cover", "label": "Cover", "image_path": "hero_cover.png", "is_cover": True},
                        {"slug": "hero_page1", "label": "Page 1", "image_path": "hero_page1.png", "is_cover": False},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(seed, "SEED_STORY_LIBRARY_FILE", story_file)
    monkeypatch.setattr(seed, "OUTPUT_DIR", output_dir)

    result = seed.get_seed_story_library()

    assert len(result) == 1
    assert result[0]["title"] == "Hero's Big Day"
    assert result[0]["thumb"] == str(output_dir / "hero_cover.png")
    assert len(result[0]["pages"]) == 2
    assert result[0]["pages"][1]["image_path"] == str(output_dir / "hero_page1.png")
