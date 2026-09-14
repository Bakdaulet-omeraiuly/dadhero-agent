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
from dadhero.safety import PHOTO_SAFETY_RULE, is_minor_relationship


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
def save_character_from_photo(
    photo_path: str,
    character_name: str,
    relationship: str,
    personality_traits: Optional[List[str]] = None,
    role_in_story: str = "",
    family_id: str = "default_family",
) -> dict:
    """Save a character built from an uploaded reference photo, stylized into the comic's art style.

    SAFETY: refuses if `relationship` indicates the character is a child
    (son, daughter, kid, student, etc.) -- a real child's photo must never
    be used to generate their likeness. For a child character, use
    save_character with a text description instead, or stylize_drawing if
    the child made their own drawing (that's fine regardless of subject,
    since it isn't a photographic likeness of a real face).

    Args:
        photo_path: File path to the parent's uploaded reference photo of an adult family member.
        character_name: The character's name as the child knows them.
        relationship: Who they are to the child -- must NOT be a child/minor relationship (e.g. "dad", "mom", "grandma", "uncle" are fine).
        personality_traits: A few traits that should show in expression/pose.
        role_in_story: The "costume"/theme for this story (e.g. "astronaut"). Leave empty for a realistic depiction.
        family_id: Identifier for this family (default "default_family").
    """
    if is_minor_relationship(relationship):
        return {
            "status": "error",
            "content": [{"text": f"Refused: '{relationship}' reads as a child relationship. {PHOTO_SAFETY_RULE}"}],
        }

    provider = get_provider()
    role = f", dressed as {role_in_story}," if role_in_story else ","
    style_prompt = (
        f"Create a warm, flat-color children's storybook illustration of the person in this "
        f"reference photo{role} in this style: {DEFAULT_ART_STYLE}. Keep their recognizable "
        "features (hair, build, any glasses or signature accessory) but fully stylized as a "
        "cartoon illustration, not a photorealistic render."
    )
    portrait_slug = f"{character_name.lower().replace(' ', '_')}_reference_portrait"
    try:
        result = provider.generate(style_prompt, output_name=portrait_slug, reference_image_path=photo_path)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "content": [{"text": f"Stylizing the photo failed: {e}"}]}

    bible = CharacterBible(
        character_name=character_name,
        relationship=relationship,
        appearance=f"as shown in the stylized reference portrait at {result.path}",
        personality_traits=personality_traits or [],
        role_in_story=role_in_story,
        art_style=DEFAULT_ART_STYLE,
        reference_image_path=result.path,
    )
    record = {
        "character_name": bible.character_name,
        "relationship": bible.relationship,
        "appearance": bible.appearance,
        "personality_traits": bible.personality_traits,
        "role_in_story": bible.role_in_story,
        "art_style": bible.art_style,
        "prompt_fragment": bible.prompt_fragment(),
        "reference_image_path": result.path,
    }
    memory.save_character(family_id, character_name, record)
    return record


@tool
def stylize_drawing(drawing_path: str, output_name: str, style_note: str = "") -> dict:
    """Turn a child's own drawing/sketch into a polished illustration in the comic's art style.

    Safe for any subject -- a child's drawing of themselves, a monster, or
    anything else is not a photographic likeness of a real face, so this
    has none of save_character_from_photo's restrictions.

    Args:
        drawing_path: File path to the uploaded drawing/sketch.
        output_name: A short unique filename-safe id for the output image.
        style_note: Optional extra guidance (e.g. "make the dragon friendlier, keep the crayon colors").
    """
    provider = get_provider()
    prompt = (
        f"Bring this child's drawing to life as a polished, warm illustration in this style: "
        f"{DEFAULT_ART_STYLE}. Keep the spirit, shapes, and character of the original drawing -- "
        f"don't redesign it into something unrecognizable. {style_note}".strip()
    )
    try:
        result = provider.generate(prompt, output_name=output_name, reference_image_path=drawing_path)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "content": [{"text": f"Stylizing the drawing failed: {e}"}]}
    return {"image_path": result.path, "provider": result.provider, "note": result.note}


@tool
def generate_page_image(
    scene_description: str,
    character_prompt_fragment: str,
    page_slug: str,
    caption_text: Optional[str] = None,
    reference_image_path: Optional[str] = None,
) -> dict:
    """Generate the illustration for one comic page, with its narration burned into the artwork like a real comic panel.

    Args:
        scene_description: What's happening in this specific page/panel -- action, setting, mood. Don't re-describe the character's fixed appearance here, that's what character_prompt_fragment is for.
        character_prompt_fragment: The exact, unchanged prompt_fragment string returned by save_character/get_saved_character -- reused verbatim so the character looks the same across pages.
        page_slug: A short unique filename-safe id for this page, e.g. "space_dad_page3".
        caption_text: This page's exact narration/dialogue text. Pass it every time -- it gets rendered INTO the image as a clean comic-style caption or speech bubble, not shown separately, so the page looks like a real comic panel. Keep it short (1-2 sentences); long text renders poorly.
        reference_image_path: The file path of a previously generated page's image (usually page 1's portrait) to condition on for visual consistency. Omit only for the very first image of a character.
    """
    provider = get_provider()
    prompt = f"{character_prompt_fragment}\n\nScene: {scene_description}"
    if caption_text:
        prompt += (
            "\n\nRender this exact text directly into the image as a clean, legible "
            "comic-book caption box along the bottom edge (a simple rounded white or "
            "cream box with dark readable text, or a speech bubble if a character is "
            f'speaking) -- do not alter the wording: "{caption_text}"'
        )
    try:
        result = provider.generate(prompt, output_name=page_slug, reference_image_path=reference_image_path)
    except Exception as e:  # noqa: BLE001 -- surface any provider failure to the agent, not a crash
        return {"status": "error", "content": [{"text": f"Image generation failed: {e}"}]}
    return {"image_path": result.path, "provider": result.provider, "note": result.note}


@tool
def get_family_memory(family_id: str = "default_family") -> dict:
    """Read this family's whole Story Universe: saved characters, places, past
    stories (with any goal they targeted), real memories shared so far, and
    progress reported back on earlier goal-oriented stories.

    Call this near the start of every conversation. Use it to: offer to
    reuse a saved character/place, avoid repeating a theme, check whether a
    shared memory was already turned into a story, and check the
    "progress" list for a goal you should follow up on (a parent reporting
    "he shared today" belongs to the same goal as an earlier story -- see
    record_progress).

    Args:
        family_id: Identifier for this family (default "default_family").
    """
    return memory.get_family_profile(family_id)


@tool
def save_place(place_name: str, description: str, family_id: str = "default_family") -> dict:
    """Save a recurring place in this family's Story Universe (a home, a grandparent's house, a magic forest introduced in a story) so future stories can be set there consistently.

    Args:
        place_name: Short name for the place (e.g. "Grandma's House", "the Magic Forest").
        description: A few concrete visual details, reused verbatim in scene_description when a story is set there.
        family_id: Identifier for this family (default "default_family").
    """
    return memory.save_place(family_id, place_name, description)


@tool
def record_family_memory(memory_text: str, family_id: str = "default_family", used_in_story: Optional[str] = None) -> dict:
    """Save a real family memory or event the parent shared (a trip, a milestone, something that happened today), so it can seed a future story or isn't asked about twice.

    Call this whenever a parent describes something real that happened,
    even before deciding whether to turn it into a story this turn.

    Args:
        memory_text: The real event/memory in the parent's own words (or a faithful short summary).
        family_id: Identifier for this family (default "default_family").
        used_in_story: This memory's story title, once one has been made from it -- omit until then.
    """
    memory.record_memory(family_id, memory_text, used_in_story)
    return {"status": "success", "content": [{"text": "Memory saved."}]}


@tool
def record_progress(
    related_to: str,
    update_text: str,
    story_title: Optional[str] = None,
    family_id: str = "default_family",
) -> dict:
    """Record a parent's follow-up report on how a goal-oriented story landed in real life -- the 'After' in Before -> During -> After.

    Call this when a parent reports back on behavior related to a
    character/goal from an earlier story (e.g. "he actually shared his
    toy today"), not for routine feedback on the story itself.

    Args:
        related_to: The character name or goal this update relates to (e.g. "Arman", "sharing").
        update_text: What the parent reported, in their own words.
        story_title: The earlier story this follows up on, if known.
        family_id: Identifier for this family (default "default_family").
    """
    memory.record_progress(family_id, related_to, update_text, story_title)
    return {"status": "success", "content": [{"text": "Progress recorded -- thanks for the update."}]}


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
    goal: Optional[str] = None,
    family_id: str = "default_family",
) -> dict:
    """Record a completed story so future conversations know what's already been made.

    Args:
        title: The story's title.
        idea: The parent's original one-line idea for the story.
        template_key: Which story shape was used (e.g. "problem_helper_solution", "small_adventure", "bedtime_wind_down").
        goal: The behavior/lesson this story targeted, if the parent's intention was goal-oriented (e.g. "sharing", "confidence at school") -- set this so a later parent report can be matched back to it via record_progress. Omit for a pure-fun story with no target lesson.
        family_id: Identifier for this family (default "default_family").
    """
    memory.record_story(family_id, title, idea, template_key, goal)
    return {"status": "success", "content": [{"text": f"Recorded '{title}'."}]}
