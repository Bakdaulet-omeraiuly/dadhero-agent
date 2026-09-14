"""Ships DadHero with a couple of polished example books already in
place, instead of an empty Story Universe on first load -- important
for a demo/hackathon deployment (Streamlit Cloud's filesystem is
ephemeral: data/family_memory.json and data/generated_pages/ are
gitignored real runtime data, so every fresh container starts with
neither) and for a judge or a fresh local clone opening the app for
the first time.

Deliberately a no-op the moment REAL data exists (memory.MEMORY_PATH
already there) -- this only ever fills a genuinely empty state, never
overwrites anything a parent actually made. data/seed/ IS committed to
git (unlike the real runtime data/ paths) -- see .gitignore.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from dadhero import memory
from dadhero.image_providers import OUTPUT_DIR

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
SEED_MEMORY_FILE = SEED_DIR / "family_memory.json"
SEED_IMAGES_DIR = SEED_DIR / "generated_pages"
SEED_STORY_LIBRARY_FILE = SEED_DIR / "story_library.json"


def ensure_seeded() -> None:
    """Copy the example characters/story into the real data/ paths, but
    ONLY when data/family_memory.json doesn't exist yet. Image paths in
    the seed file are basenames (portable across machines/deployments);
    resolved here against the CURRENT OUTPUT_DIR, not whatever absolute
    path they were originally generated at."""
    if memory.MEMORY_PATH.exists() or not SEED_MEMORY_FILE.exists():
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if SEED_IMAGES_DIR.exists():
        for img in SEED_IMAGES_DIR.iterdir():
            dest = OUTPUT_DIR / img.name
            if not dest.exists():
                shutil.copy(img, dest)

    with open(SEED_MEMORY_FILE, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    for family in data.values():
        for char in family.get("characters", {}).values():
            ref = char.get("reference_image_path")
            if ref:
                char["reference_image_path"] = str(OUTPUT_DIR / Path(ref).name)

    memory.MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(memory.MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_seed_story_library() -> list[dict[str, Any]]:
    """Fresh Story Library entries for a new session's story_library init
    -- app.py's Story Library is deliberately session-only (see its own
    docstring), so unlike ensure_seeded() this runs every new session,
    not just once. Returns [] if there's no seed file (fully optional --
    a missing seed never breaks a normal empty start)."""
    if not SEED_STORY_LIBRARY_FILE.exists():
        return []
    try:
        with open(SEED_STORY_LIBRARY_FILE, encoding="utf-8") as f:
            stories = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    resolved = []
    for story in stories:
        pages = [
            {**p, "image_path": str(OUTPUT_DIR / Path(p["image_path"]).name)}
            for p in story.get("pages", [])
        ]
        if not pages or not all(Path(p["image_path"]).exists() for p in pages):
            continue  # a seed page missing on disk -- skip this story rather than show broken images
        resolved.append({"id": uuid.uuid4().hex, "title": story["title"], "thumb": pages[0]["image_path"], "pages": pages})
    return resolved
