"""Real public-domain comic-book page images, used as an EXTRA visual
reference (alongside the character's own reference portrait) when a
story is drawn in the "Comic book" art style -- actual panel/caption/
inking conventions from a printed comic, not just a text description of
one. See dadhero/assets/comic_refs/LICENSES.md for sourcing.

Deliberately scoped to ONE style: these three scans are golden-age
comic-book pages, not generically "art references" -- forcing them onto
watercolor/claymation/pixel-art etc. would be a style mismatch, not an
enhancement. Only "Comic book" gets one.
"""

from __future__ import annotations

from pathlib import Path

_REFS_DIR = Path(__file__).parent / "assets" / "comic_refs"

# One representative page per style key. Only "Comic book" has an
# entry -- see module docstring for why the other 8 styles don't.
COMIC_STYLE_REFERENCE_IMAGES: dict[str, Path] = {
    "Comic book": _REFS_DIR / "pep_comics_71_page35_1949.png",
}


def get_style_reference_image(art_style_label: str | None) -> str | None:
    """The local file path for a real comic-page reference matching this
    art style label, or None if there isn't one (any style other than
    "Comic book", a missing/renamed file, or art_style_label being None).
    Fails open -- a missing reference image should never block generation,
    just skip the extra conditioning."""
    if not art_style_label:
        return None
    path = COMIC_STYLE_REFERENCE_IMAGES.get(art_style_label)
    if path and path.exists():
        return str(path)
    return None
