"""
Typed structures for DadHero -- the equivalent of StoryMatch's Narrative
Fingerprint, but for "turn a parent's idea into a consistent illustrated
character across N comic pages."

Kept as plain dataclasses (not Strands tool parameters) because tool
signatures stay flatter/more reliable as individual str/list[str] args (see
StoryMatch's README on tool granularity) -- these classes are the *internal*
representation tools.py builds and passes around, not what the LLM fills in
directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_ART_STYLE = (
    "warm, flat-color children's storybook illustration; soft rounded "
    "shapes; simple clean background; gentle warm lighting; no photorealism"
)

# A parent-facing style picker (Story settings panel) -- each value is a
# real, distinct art-direction prompt fragment, not just a label. Kept
# here (not hardcoded into DEFAULT_ART_STYLE) so save_character/
# save_character_from_photo can accept an explicit art_style override
# while every existing call site that doesn't pass one keeps getting
# today's default, unchanged.
ART_STYLES: dict[str, str] = {
    "Storybook (default)": DEFAULT_ART_STYLE,
    "Watercolor": (
        "soft watercolor children's book illustration; visible paper texture; "
        "gentle bleeding edges and light washes of color; delicate ink outlines; "
        "dreamy, hand-painted feel; no photorealism"
    ),
    "Comic book": (
        "bold comic-book illustration; thick black ink outlines; bright flat "
        "colors with halftone-dot shading; dynamic panel-style composition; "
        "energetic linework; no photorealism"
    ),
    "Anime / manga": (
        "clean anime-style illustration; large expressive eyes; soft cel "
        "shading; simple bold linework; bright saturated colors; no "
        "photorealism"
    ),
    "Claymation / 3D": (
        "soft 3D-rendered claymation-style illustration; rounded clay-like "
        "shapes; visible fingerprint/sculpted texture; warm soft studio "
        "lighting; no photorealism"
    ),
    "Pixel art": (
        "retro 8-bit/16-bit pixel-art illustration; visible square pixels; "
        "a limited, vibrant retro-game color palette; crisp hard edges; no "
        "gradients, no photorealism"
    ),
    "Chalk & crayon": (
        "hand-drawn children's chalk-and-crayon illustration; visible waxy "
        "crayon texture and chalky strokes; slightly imperfect, childlike "
        "linework; warm paper-colored background; no photorealism"
    ),
    "Paper cutout / collage": (
        "layered paper-cutout collage illustration; visible paper edges and "
        "soft drop shadows between layers; flat textured-paper shapes; "
        "handcrafted look; no photorealism"
    ),
    "Classic fairytale": (
        "ornate vintage fairytale-book illustration; intricate detailed "
        "linework; rich jewel-toned colors; classic storybook engraving "
        "feel reminiscent of old fairy tale collections; no photorealism"
    ),
}

# A small library of proven picture-book story shapes. The agent picks one
# (or blends) when planning pages instead of inventing structure from
# scratch every time -- keeps a 6-8 page story readable to a 4-7 year old
# instead of meandering.
STORY_TEMPLATES = {
    "problem_helper_solution": {
        "label": "Problem -> Helper -> Solution",
        "beats": [
            "Everyday setting introduces the hero and the child's world",
            "A problem or wish appears",
            "The hero decides to help / sets off",
            "First attempt or obstacle",
            "The hero tries a clever or brave solution",
            "The problem is solved",
            "Warm ending: hero and child together, lesson or feeling named",
        ],
    },
    "small_adventure": {
        "label": "Small Adventure Loop",
        "beats": [
            "Ordinary day, hero notices something unusual",
            "Hero investigates / a call to adventure",
            "A new world or challenge appears",
            "Hero faces the challenge with a specific skill or trait",
            "A moment of doubt or a small setback",
            "Hero overcomes it, often helped by love for the child",
            "Return home, changed a little, ready for bed",
        ],
    },
    "bedtime_wind_down": {
        "label": "Bedtime Wind-Down",
        "beats": [
            "Hero and child start an imaginative game before bed",
            "The game grows into a gentle adventure",
            "A small, low-stakes challenge appears",
            "It resolves warmly and quietly",
            "The adventure winds down, energy softens",
            "Hero tucks the child in within the story itself",
        ],
    },
}


@dataclass
class CharacterBible:
    """The single source of truth for one recurring character's appearance.

    Reused VERBATIM in every page's image prompt -- the actual lever for
    keeping "Dad" looking like the same person across a comic. See
    image_providers.py for how a reference image tightens this further.
    """

    character_name: str
    relationship: str  # e.g. "dad", "mom", "grandpa" -- who this is to the child
    appearance: str  # hair, eyes, build, signature clothing/accessory, distinguishing feature
    personality_traits: list[str] = field(default_factory=list)
    role_in_story: str = ""  # the "costume"/theme mom picked: astronaut, knight, firefighter...
    art_style: str = DEFAULT_ART_STYLE
    reference_image_path: str | None = None  # set once page 1's portrait is generated

    def prompt_fragment(self) -> str:
        traits = ", ".join(self.personality_traits) if self.personality_traits else "warm and kind"
        role = f" dressed as {self.role_in_story}" if self.role_in_story else ""
        return (
            f"{self.character_name} (the child's {self.relationship}){role}: "
            f"{self.appearance}. Personality comes through as {traits}. "
            f"Art style: {self.art_style}."
        )


@dataclass
class StoryPage:
    page_number: int
    scene_description: str  # what's happening, for the image prompt
    text: str  # 1-3 sentences of child-facing narration
    image_path: str | None = None


@dataclass
class StoryOutline:
    title: str
    idea: str  # the parent's original one-line idea
    template_key: str
    child_name: str | None
    pages: list[StoryPage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "idea": self.idea,
            "template": STORY_TEMPLATES.get(self.template_key, {}).get("label", self.template_key),
            "child_name": self.child_name,
            "pages": [
                {"page_number": p.page_number, "text": p.text, "scene_description": p.scene_description, "image_path": p.image_path}
                for p in self.pages
            ],
        }
