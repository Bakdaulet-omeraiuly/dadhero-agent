"""
Strands tools for DadHero.

Same discipline as StoryMatch: few tools, each doing a real external
action (persistence or image generation), not one tool per conceptual
step. Page-by-page story PLANNING is the agent's own reasoning (like
Narrative Fingerprint extraction was in StoryMatch) -- there's no
"plan_story" tool because there's nothing external to call for that; the
agent just writes the outline and then calls generate_page for each page.
"""

from __future__ import annotations

from typing import List, Optional

from strands import tool

from dadhero import continuity, memory
from dadhero.image_providers import get_provider
from dadhero.models import DEFAULT_ART_STYLE, CharacterBible
from dadhero.safety import check_age_appropriateness as _check_age_appropriateness


@tool
def save_character(
    character_name: str,
    relationship: str,
    appearance: str,
    personality_traits: Optional[List[str]] = None,
    role_in_story: str = "",
    family_id: str = "default_family",
) -> dict:
    """Save a character's appearance so it can be reused consistently across pages and future stories.

    Call this once per story before generating any pages -- every
    generate_page_image call should reuse the exact prompt_fragment this
    returns, unchanged, so the character stays visually consistent.

    Args:
        character_name: The character's name as the child knows them (e.g. "Dad", "Papa Nurlan").
        relationship: Who they are to the child (e.g. "dad", "grandma", "uncle").
        appearance: Concrete visual details -- hair, eyes, build, signature clothing or accessory, one distinguishing feature. Be specific; vague descriptions cause inconsistent art.
        personality_traits: A few traits that should show in expression/pose (e.g. ["brave", "goofy", "gentle"]).
        role_in_story: The "costume"/theme for this story (e.g. "astronaut", "knight", "firefighter"). Leave empty for a realistic depiction.
        family_id: Identifier for this family (default "default_family").
    """
    bible = CharacterBible(
        character_name=character_name,
        relationship=relationship,
        appearance=appearance,
        personality_traits=personality_traits or [],
        role_in_story=role_in_story,
        art_style=DEFAULT_ART_STYLE,
    )
    record = {
        "character_name": bible.character_name,
        "relationship": bible.relationship,
        "appearance": bible.appearance,
        "personality_traits": bible.personality_traits,
        "role_in_story": bible.role_in_story,
        "art_style": bible.art_style,
        "prompt_fragment": bible.prompt_fragment(),
    }
    memory.save_character(family_id, character_name, record)
    return record


@tool
def get_saved_character(character_name: str, family_id: str = "default_family") -> dict:
    """Look up a previously saved character so the same person can star in a new story without redescribing them.

    Args:
        character_name: The character's name as saved before.
        family_id: Identifier for this family (default "default_family").
    """
    record = memory.get_character(family_id, character_name)
    if not record:
        return {"status": "error", "content": [{"text": f"No saved character named '{character_name}' for this family."}]}
    return record


@tool
def generate_page_image(
    scene_description: str,
    character_prompt_fragment: str,
    page_slug: str,
    reference_image_path: Optional[str] = None,
) -> dict:
    """Generate the illustration for one comic page.

    Args:
        scene_description: What's happening in this specific page/panel -- action, setting, mood. Don't re-describe the character's fixed appearance here, that's what character_prompt_fragment is for.
        character_prompt_fragment: The exact, unchanged prompt_fragment string returned by save_character/get_saved_character -- reused verbatim so the character looks the same across pages.
        page_slug: A short unique filename-safe id for this page, e.g. "space_dad_page3".
        reference_image_path: The file path of a previously generated page's image (usually page 1's portrait) to condition on for visual consistency. Omit only for the very first image of a character.
    """
    provider = get_provider()
    prompt = f"{character_prompt_fragment}\n\nScene: {scene_description}"
    try:
        result = provider.generate(prompt, output_name=page_slug, reference_image_path=reference_image_path)
    except Exception as e:  # noqa: BLE001 -- surface any provider failure to the agent, not a crash
        return {"status": "error", "content": [{"text": f"Image generation failed: {e}"}]}
    return {"image_path": result.path, "provider": result.provider, "note": result.note}


@tool
def get_family_memory(family_id: str = "default_family") -> dict:
    """Read this family's saved characters and past story titles/themes.

    Call this near the start of a conversation so you can offer to reuse a
    saved character or avoid repeating a theme used recently.

    Args:
        family_id: Identifier for this family (default "default_family").
    """
    return memory.get_family_profile(family_id)


@tool
def check_story_fact(story_slug: str, fact_key: str, fact_value: str) -> dict:
    """Record and continuity-check one concrete story detail before using it on a page.

    Call this for anything a reader would notice if it changed later --
    an object's color, a location, a sidekick's name, what time of day it
    is. If this fact_key was already established differently earlier in
    the same story, this returns a conflict so you can fix the page
    instead of introducing an inconsistency (StorySprout's "red backpack
    on page 1, blue on page 4" problem).

    Args:
        story_slug: The same short id used for this story's generate_page_image calls.
        fact_key: A short identifier for the detail (e.g. "backpack_color", "sidekick_name", "location").
        fact_value: The value this page is about to use for that detail.
    """
    return continuity.check_and_record_fact(story_slug, fact_key, fact_value)


@tool
def check_page_safety(page_text: str, child_age: Optional[int] = None) -> dict:
    """Screen one page's narration text for age-appropriateness before presenting it.

    Call this on every page's text before showing it to the parent. If
    passed is False, revise the text (soften the concerning term, or
    shorten it) and check again rather than presenting it as-is.

    Args:
        page_text: The exact narration text for this page.
        child_age: The child's age if known -- sharpens the length guideline.
    """
    return _check_age_appropriateness(page_text, child_age)


@tool
def record_finished_story(
    title: str,
    idea: str,
    template_key: str,
    family_id: str = "default_family",
) -> dict:
    """Record a completed story so future conversations know what's already been made.

    Args:
        title: The story's title.
        idea: The parent's original one-line idea for the story.
        template_key: Which story shape was used (e.g. "problem_helper_solution", "small_adventure", "bedtime_wind_down").
        family_id: Identifier for this family (default "default_family").
    """
    memory.record_story(family_id, title, idea, template_key)
    return {"status": "success", "content": [{"text": f"Recorded '{title}'."}]}
