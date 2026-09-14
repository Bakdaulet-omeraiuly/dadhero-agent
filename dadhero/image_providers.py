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
  - GeminiImageProvider: real "Nano Banana" (gemini-3-pro-image) backend.
    WRITTEN BUT NOT YET VERIFIED AGAINST A LIVE RESPONSE -- the API key
    available during development hit a billing/org-policy wall before a
    single real image came back (see README's status section). The request
    shape below follows Gemini's documented image-output + multi-turn
    image-editing pattern; confirm it against a real response before
    trusting it in a demo, and adjust generationConfig/field names if the
    API has moved.

Select the active provider via DADHERO_IMAGE_PROVIDER=mock|gemini (default
mock, so a fresh checkout runs without any API key).
"""

from __future__ import annotations

import base64
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
    ) -> GeneratedImage:
        """Generate one image from `prompt`.

        reference_image_path: when set, the provider should condition on
        that prior image to keep the same character consistent (this is
        the whole reason Nano Banana was chosen -- see README). A provider
        that can't do this yet may ignore the argument, but should say so
        in the returned GeneratedImage.note.
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
        img.save(path)

        note = "Placeholder image -- set DADHERO_IMAGE_PROVIDER=gemini with a working API key for real art."
        if reference_image_path:
            note += f" (would condition on {Path(reference_image_path).name} for consistency)"

        return GeneratedImage(path=str(path), provider="mock", note=note)


class GeminiImageProvider(ImageProvider):
    """Nano Banana (gemini-3-pro-image) -- UNVERIFIED, see module docstring."""

    def __init__(self, api_key: str | None = None, model_id: str = "gemini-3-pro-image"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_id = model_id
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set for GeminiImageProvider.")

    def generate(
        self,
        prompt: str,
        *,
        output_name: str,
        reference_image_path: str | None = None,
    ) -> GeneratedImage:
        import requests

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{output_name}.png"

        parts: list[dict] = []
        if reference_image_path and Path(reference_image_path).exists():
            with open(reference_image_path, "rb") as f:
                ref_b64 = base64.b64encode(f.read()).decode("ascii")
            parts.append({"inline_data": {"mime_type": "image/png", "data": ref_b64}})
            parts.append(
                {
                    "text": (
                        "Using the exact same character shown in this reference image "
                        f"(same face, hair, outfit, art style), draw a new scene: {prompt}"
                    )
                }
            )
        else:
            parts.append({"text": prompt})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_id}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        image_b64 = None
        for part in candidates[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                image_b64 = inline["data"]
                break
        if not image_b64:
            raise RuntimeError(f"Gemini response had no image part: {data}")

        with open(path, "wb") as f:
            f.write(base64.b64decode(image_b64))

        return GeneratedImage(
            path=str(path),
            provider="gemini",
            note="Conditioned on reference image." if reference_image_path else "No reference image used.",
        )


def get_provider() -> ImageProvider:
    provider = os.environ.get("DADHERO_IMAGE_PROVIDER", "mock").lower()
    if provider == "gemini":
        return GeminiImageProvider()
    return MockImageProvider()
