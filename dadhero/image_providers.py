"""
Image generation backends behind one small interface, so tools.py never
cares which provider is actually drawing the picture.

Providers:
  - MockImageProvider: draws a real PNG locally (no network, no cost) with
    the prompt text baked in. Lets the ENTIRE agent loop (character bible ->
    story plan -> per-page generation -> assembly -> feedback -> regenerate)
    be built and tested end-to-end today, while the real image API is
    blocked by billing/org policy. This is not a stub that returns nothing
    -- app.py/cli_demo.py render its output exactly like a real image.
  - GeminiImageProvider: real "Nano Banana" (gemini-3-pro-image) backend,
    using the official `google-genai` SDK. The call shape and response
    parsing (candidates[0].content.parts[i].inline_data.data) ARE verified
    -- confirmed live: text generation succeeds, and an image request
    reaches the model and fails with a clean, expected 429 quota error
    (free tier gives image models 0 quota until billing is enabled), not a
    shape/parsing error. What's still unverified is the actual image
    bytes/quality and multi-turn reference-image consistency, since no
    account with image billing enabled was available during development
    -- see README's status section before trusting this in a live demo.

Select the active provider via DADHERO_IMAGE_PROVIDER=mock|gemini (default
mock, so a fresh checkout runs without any API key).
"""

from __future__ import annotations

import os
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "generated_pages"


@dataclass
class GeneratedImage:
    path: str
    provider: str
    note: str = ""


class ImageProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        output_name: str,
        reference_image_path: str | None = None,
        style_reference_image_path: str | None = None,
    ) -> GeneratedImage:
        """Generate one image from `prompt`.

        reference_image_path: when set, the provider should condition on
        that prior image to keep the same character consistent (this is
        the whole reason Nano Banana was chosen -- see README). A provider
        that can't do this yet may ignore the argument, but should say so
        in the returned GeneratedImage.note.

        style_reference_image_path: a SEPARATE reference -- a real comic
        page (see dadhero/comic_style_refs.py), not the character's own
        portrait -- for panel/inking/composition conventions rather than
        the character's appearance. Optional; a provider may ignore it.
        """


class MockImageProvider(ImageProvider):
    """Zero-cost, zero-network placeholder so the full pipeline is
    demoable and testable before/without a paid image API."""

    def generate(
        self,
        prompt: str,
        *,
        output_name: str,
        reference_image_path: str | None = None,
        style_reference_image_path: str | None = None,
    ) -> GeneratedImage:
        from PIL import Image, ImageDraw, ImageFont

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{output_name}.png"

        img = Image.new("RGB", (768, 768), color=(255, 247, 230))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
            small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
        except OSError:
            font = ImageFont.load_default()
            small = font

        draw.rectangle([16, 16, 752, 752], outline=(210, 160, 90), width=4)
        draw.text((40, 40), "[ MOCK IMAGE -- no image API configured ]", fill=(180, 90, 40), font=small)
        wrapped = textwrap.fill(prompt, width=46)
        draw.multiline_text((40, 90), wrapped, fill=(70, 55, 40), font=font, spacing=8)
        if reference_image_path:
            draw.text(
                (40, 700),
                f"(would condition on: {Path(reference_image_path).name})",
                fill=(150, 150, 150),
                font=small,
            )
        if style_reference_image_path:
            draw.text(
                (40, 720),
                f"(would style-condition on: {Path(style_reference_image_path).name})",
                fill=(150, 150, 150),
                font=small,
            )
        img.save(path)

        note = "Placeholder image -- set DADHERO_IMAGE_PROVIDER=gemini with a working API key for real art."
        if reference_image_path:
            note += f" (would condition on {Path(reference_image_path).name} for consistency)"
        if style_reference_image_path:
            note += f" (would style-condition on {Path(style_reference_image_path).name})"

        return GeneratedImage(path=str(path), provider="mock", note=note)


class GeminiImageProvider(ImageProvider):
    """Nano Banana (gemini-3-pro-image) -- UNVERIFIED, see module docstring."""

    def __init__(self, api_key: str | None = None, model_id: str = "gemini-3-pro-image"):
        from google import genai

        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set for GeminiImageProvider.")
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id

    def generate(
        self,
        prompt: str,
        *,
        output_name: str,
        reference_image_path: str | None = None,
        style_reference_image_path: str | None = None,
    ) -> GeneratedImage:
        from google.genai import types

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{output_name}.png"

        contents: list = []
        # Style reference goes in FIRST and is explicitly named as a
        # composition/inking reference only -- it must never be confused
        # with the character reference below (a real vintage comic page
        # has its own unrelated characters on it).
        if style_reference_image_path and Path(style_reference_image_path).exists():
            with open(style_reference_image_path, "rb") as f:
                mime = "image/png" if style_reference_image_path.endswith(".png") else "image/jpeg"
                contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
            contents.append(
                "The image above is a real vintage printed comic-book page, shown ONLY "
                "as a reference for panel composition, ink linework, and caption-box "
                "style -- ignore its actual characters and story entirely."
            )
        if reference_image_path and Path(reference_image_path).exists():
            with open(reference_image_path, "rb") as f:
                contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
            contents.append(
                "Using the exact same character shown in this reference image "
                f"(same face, hair, outfit, art style), draw a new scene: {prompt}"
            )
        else:
            contents.append(prompt)

        response = self.client.models.generate_content(model=self.model_id, contents=contents)

        candidates = response.candidates or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates for prompt: {prompt!r}")

        image_bytes = None
        for part in candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                image_bytes = inline.data
                break
        if image_bytes is None:
            raise RuntimeError(
                f"Gemini response had no image part (got: {[type(p).__name__ for p in candidates[0].content.parts]})"
            )

        with open(path, "wb") as f:
            f.write(image_bytes)

        note = "Conditioned on reference image." if reference_image_path else "No reference image used."
        if style_reference_image_path:
            note += " Also style-conditioned on a real vintage comic page."

        return GeneratedImage(path=str(path), provider="gemini", note=note)


def get_provider() -> ImageProvider:
    provider = os.environ.get("DADHERO_IMAGE_PROVIDER", "mock").lower()
    if provider == "gemini":
        return GeminiImageProvider()
    return MockImageProvider()
