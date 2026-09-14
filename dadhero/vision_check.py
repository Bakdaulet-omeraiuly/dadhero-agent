"""
Visual consistency check -- did this new page's art actually keep the
same character, or did the image model drift? Uses Gemini's own vision
input (it can read two images + text in one call) as an independent
judge, separate from the image-generation call itself -- the same
"a second, cheaper pass verifies the expensive pass" shape as
continuity.py's deterministic fact-checking versus generation.

Deliberately fails OPEN (returns consistent=True with a note) whenever
the check itself can't run -- a missing key, a network hiccup, or mock
mode (nothing meaningful to compare in placeholder art) should never
block a page the parent is waiting on. The check adds confidence when it
runs; its absence isn't treated as a red flag.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_VISION_MODEL_ID = "gemini-2.5-flash"


def check_consistency(page_image_path: str, reference_image_path: str, character_description: str) -> dict:
    if os.environ.get("DADHERO_IMAGE_PROVIDER", "mock").lower() != "gemini":
        return {
            "consistent": True,
            "notes": "Skipped -- the mock image provider draws a text placeholder, not a face, so there's nothing to visually compare.",
        }

    if not (Path(page_image_path).exists() and Path(reference_image_path).exists()):
        return {"consistent": True, "notes": "Skipped -- one of the two image files wasn't found on disk."}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"consistent": True, "notes": "Skipped -- GEMINI_API_KEY not set."}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_id = os.environ.get("DADHERO_VISION_MODEL_ID", _DEFAULT_VISION_MODEL_ID)

        contents = [
            types.Part.from_bytes(data=Path(reference_image_path).read_bytes(), mime_type="image/png"),
            types.Part.from_bytes(data=Path(page_image_path).read_bytes(), mime_type="image/png"),
            (
                f"Image 1 is the reference portrait of a children's-book character: {character_description}\n"
                "Image 2 is a new illustrated page meant to feature the SAME character.\n"
                "Does the character in Image 2 look like the same character as Image 1 -- "
                "same face shape, hair, skin tone, and any signature clothing/accessory? "
                "A different pose, expression, or camera angle is fine and NOT a mismatch. "
                "Reply with exactly one line: either the word CONSISTENT, or "
                "INCONSISTENT followed by a colon and a short reason."
            ),
        ]
        response = client.models.generate_content(model=model_id, contents=contents)
        text = (response.text or "").strip()
    except Exception as e:  # noqa: BLE001 -- a checker failure must never block the actual page
        return {"consistent": True, "notes": f"Check failed to run ({e}) -- not blocking the page over a checker error."}

    consistent = text.upper().startswith("CONSISTENT")
    return {"consistent": consistent, "notes": text or "(empty response)"}
