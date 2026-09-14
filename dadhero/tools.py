"""
Strands tools for DadHero.

Same discipline as StoryMatch: few tools, each doing a real external
action (persistence or image generation), not one tool per conceptual
step. Page-by-page story PLANNING is still the agent's own creative
reasoning (like Narrative Fingerprint extraction was in StoryMatch) --
create_story_plan below doesn't do that reasoning FOR the agent, it
records the plan the agent already worked out, the same
propose-then-record shape save_character/check_story_fact already use.
That external record is what makes planning an inspectable tool call
(visible in the Workshop panel) instead of reasoning that only ever
existed inside one model response.
"""

from __future__ import annotations

from typing import List, Optional

from strands import tool

from dadhero import continuity, storage, vision_check
from dadhero import memory_backend as memory
from dadhero.image_providers import get_provider
from dadhero.models import ART_STYLES, DEFAULT_ART_STYLE, CharacterBible
from dadhero.safety import check_age_appropriateness as _check_age_appropriateness
from dadhero.safety import PHOTO_SAFETY_RULE, is_minor_relationship


def _resolve_art_style(art_style: Optional[str]) -> str:
    """art_style arrives as one of ART_STYLES' LABELS (e.g. "Watercolor")
    -- the agent shouldn't have to reproduce a whole art-direction prompt
    verbatim, just pick from the list agent.py shows it. Falls back to
    treating an unrecognized value as a literal style description
    (defensive, not expected in practice) rather than silently ignoring
    it, and to the default when nothing was passed."""
    if not art_style:
        return DEFAULT_ART_STYLE
    return ART_STYLES.get(art_style, art_style)


@tool
def save_character(
    character_name: str,
    relationship: str,
    appearance: str,
    personality_traits: Optional[List[str]] = None,
    role_in_story: str = "",
    family_id: str = "default_family",
    art_style: Optional[str] = None,
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
        art_style: A label from dadhero.models.ART_STYLES (e.g. "Watercolor", "Comic book") if the parent picked a style in settings -- pass the label; this function looks up the actual art-direction text. Omit for the default warm storybook look.
    """
    bible = CharacterBible(
        character_name=character_name,
        relationship=relationship,
        appearance=appearance,
        personality_traits=personality_traits or [],
        role_in_story=role_in_story,
        art_style=_resolve_art_style(art_style),
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
    stored = memory.save_character(family_id, character_name, record)
    # The Supabase backend's row has an `id` the local-JSON backend's
    # bible dict doesn't (there, characters are keyed by name, not id) --
    # pass it through when present so a caller with a real row (e.g.
    # backend/routers/characters.py's dashboard-triggered create) can use
    # it as CreateStoryRequest.character_id. Purely additive: the agent
    # itself never reads this key.
    if isinstance(stored, dict) and "id" in stored:
        record["id"] = stored["id"]
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
    art_style: Optional[str] = None,
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
        art_style: A label from dadhero.models.ART_STYLES if the parent picked a style in settings -- pass the label; this function looks up the actual art-direction text. Omit for the default warm storybook look.
    """
    if is_minor_relationship(relationship):
        return {
            "status": "error",
            "content": [{"text": f"Refused: '{relationship}' reads as a child relationship. {PHOTO_SAFETY_RULE}"}],
        }

    provider = get_provider()
    chosen_style = _resolve_art_style(art_style)
    role = f", dressed as {role_in_story}," if role_in_story else ","
    style_prompt = (
        f"Create a children's storybook illustration of the person in this "
        f"reference photo{role} in this style: {chosen_style}. Keep their recognizable "
        "features (hair, build, any glasses or signature accessory) but fully stylized "
        "per that art direction, not a photorealistic render."
    )
    portrait_slug = f"{character_name.lower().replace(' ', '_')}_reference_portrait"
    try:
        result = provider.generate(style_prompt, output_name=portrait_slug, reference_image_path=photo_path)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "content": [{"text": f"Stylizing the photo failed: {e}"}]}

    # reference_image_path stays a LOCAL path -- that's what the image
    # provider reads bytes from when chaining consistency across later
    # generate_page_image calls (see image_providers.GeminiImageProvider).
    # image_url is the separate, storage-persisted URL for anything that
    # needs to actually display or outlive this local disk (a deployed
    # backend, a UI) -- identical to result.path in local/Streamlit mode.
    image_url = storage.persist(result.path)

    bible = CharacterBible(
        character_name=character_name,
        relationship=relationship,
        appearance=f"as shown in the stylized reference portrait at {image_url}",
        personality_traits=personality_traits or [],
        role_in_story=role_in_story,
        art_style=chosen_style,
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
        "image_url": image_url,
    }
    stored = memory.save_character(family_id, character_name, record)
    # See save_character's matching comment -- passes the Supabase row's
    # `id` through when present; a no-op extra key everywhere else.
    if isinstance(stored, dict) and "id" in stored:
        record["id"] = stored["id"]
    return record


@tool
def stylize_drawing(drawing_path: str, output_name: str, style_note: str = "", art_style: Optional[str] = None) -> dict:
    """Turn a child's own drawing/sketch into a polished illustration in the comic's art style.

    Safe for any subject -- a child's drawing of themselves, a monster, or
    anything else is not a photographic likeness of a real face, so this
    has none of save_character_from_photo's restrictions.

    Args:
        drawing_path: File path to the uploaded drawing/sketch.
        output_name: A short unique filename-safe id for the output image.
        style_note: Optional extra guidance (e.g. "make the dragon friendlier, keep the crayon colors").
        art_style: A label from dadhero.models.ART_STYLES if the parent picked a style in settings -- pass the label; this function looks up the actual art-direction text. Omit for the default warm storybook look.
    """
    provider = get_provider()
    chosen_style = _resolve_art_style(art_style)
    prompt = (
        f"Bring this child's drawing to life as a polished, warm illustration in this style: "
        f"{chosen_style}. Keep the spirit, shapes, and character of the original drawing -- "
        f"don't redesign it into something unrecognizable. {style_note}".strip()
    )
    try:
        result = provider.generate(prompt, output_name=output_name, reference_image_path=drawing_path)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "content": [{"text": f"Stylizing the drawing failed: {e}"}]}
    return {
        "image_path": result.path,
        "image_url": storage.persist(result.path),
        "provider": result.provider,
        "note": result.note,
    }


@tool
def generate_page_image(
    scene_description: str,
    character_prompt_fragment: str,
    page_slug: str,
    caption_text: Optional[str] = None,
    reference_image_path: Optional[str] = None,
    is_cover: bool = False,
) -> dict:
    """Generate the illustration for one comic page, with its narration burned into the artwork like a real comic panel.

    Args:
        scene_description: What's happening in this specific page/panel -- action, setting, mood. Don't re-describe the character's fixed appearance here, that's what character_prompt_fragment is for.
        character_prompt_fragment: The exact, unchanged prompt_fragment string returned by save_character/get_saved_character -- reused verbatim so the character looks the same across pages.
        page_slug: A short unique filename-safe id for this page, e.g. "space_dad_page3". Use "..._cover" for the cover (see is_cover).
        caption_text: This page's exact narration/dialogue text, OR (when is_cover=True) the book's title. Pass it every time -- it gets rendered INTO the image, not shown separately, so the page looks like a real comic panel/book cover. Keep it short (1-2 sentences, or a few words for a title); long text renders poorly.
        reference_image_path: The file path of a previously generated page's image (usually page 1's portrait, or the cover's) to condition on for visual consistency -- ALWAYS use the image_path field from a prior result here, never image_url (that may be a remote URL the image provider can't read bytes from). Omit only for the very first image of a character.
        is_cover: True for this story's front cover -- one per story, generated first, before page 1. Composes the character prominently and renders caption_text as a large book-cover title instead of a caption box.

    Returns image_path (local file -- pass this as reference_image_path on
    later calls) and image_url (what to actually show the parent -- on the
    local/Streamlit backend these are the same value; on the platform
    backend image_url is a persisted Storage URL and image_path is a
    same-server temp file that won't survive a redeploy).
    """
    provider = get_provider()
    prompt = f"{character_prompt_fragment}\n\nScene: {scene_description}"
    if is_cover:
        prompt += (
            "\n\nCompose this as a CHILDREN'S BOOK COVER, not a comic panel: the "
            "character prominent and centered, inviting and eye-catching, a bit of "
            "matching background/scenery, room at the top for a title."
        )
        if caption_text:
            prompt += (
                "\n\nRender this exact text as a large, playful, legible book-cover "
                f'title across the top -- do not alter the wording: "{caption_text}"'
            )
    elif caption_text:
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
    return {
        "image_path": result.path,
        "image_url": storage.persist(result.path),
        "provider": result.provider,
        "note": result.note,
        "is_cover": is_cover,
    }


@tool
def create_story_plan(
    title: str,
    story_slug: str,
    template_key: str,
    page_beats: List[str],
    goal: Optional[str] = None,
) -> dict:
    """Record this story's page-by-page plan BEFORE generating any images -- a real, inspectable checkpoint (visible as its own step) rather than a plan that only ever existed inside your own reasoning.

    Call this once, right after you've worked out the outline (step 6 of
    the workflow), before the first generate_page_image call.

    Args:
        title: The story's working title.
        story_slug: The same short id you'll use for every generate_page_image/check_story_fact call in this story.
        template_key: Which story shape this follows (e.g. "problem_helper_solution", "small_adventure", "bedtime_wind_down").
        page_beats: One short phrase per page, in order, describing that page's beat (e.g. ["Emma wakes up nervous about her first day", "She meets a friendly robot hallway guide", ...]). This list's length IS the page count -- match it to what the parent asked for: ~5-8 for a short story, ~9-12 for a longer one. Hard-capped at 16 pages regardless (a young child's attention span, and a live demo's patience, both have limits).
        goal: The behavior/lesson this story targets, if any -- pass the same value you'll later pass to record_finished_story.
    """
    capped = page_beats[:16]
    plan = {
        "title": title,
        "template_key": template_key,
        "goal": goal,
        "page_count": len(capped),
        "beats": capped,
    }
    continuity.record_story_plan(story_slug, plan)
    note = f"Plan recorded: '{title}', {len(capped)} pages."
    if len(page_beats) > 16:
        note += f" (trimmed from {len(page_beats)} -- 16-page cap.)"
    return {"status": "success", "content": [{"text": note}], **plan}


@tool
def check_visual_consistency(page_image_path: str, reference_image_path: str, character_description: str) -> dict:
    """Verify a just-generated page still shows the SAME character as the reference portrait, using an independent vision check (not the same call that drew the page).

    Call this after each generate_page_image call that has a
    reference_image_path (i.e. every page after the first). If
    consistent is False, regenerate just that page (same
    character_prompt_fragment, maybe a more explicit scene_description)
    rather than presenting a page where the character looks different.

    Args:
        page_image_path: The image_path this page's generate_page_image call just returned.
        reference_image_path: The same reference_image_path you passed into that generate_page_image call.
        character_description: The character's appearance in a sentence or two (from their Character Bible) -- gives the checker something concrete to compare against.
    """
    return vision_check.check_consistency(page_image_path, reference_image_path, character_description)


@tool
def audit_story_continuity(story_slug: str) -> dict:
    """Review every concrete fact locked in so far for this story (via check_story_fact) in one pass -- a final continuity audit after all pages are generated, not just the per-page checks along the way.

    Call this once, after the last page, before presenting the finished
    story. Read through the facts for anything that reads inconsistent
    together even though no single check_story_fact call conflicted
    (e.g. a location fact and a time-of-day fact that don't make sense
    together) -- check_story_fact only catches the SAME key changing
    value, not this kind of cross-fact inconsistency.

    Args:
        story_slug: The same story_slug used for this story's check_story_fact calls.
    """
    facts = continuity.get_story_facts(story_slug)
    plan = continuity.get_story_plan(story_slug)
    return {
        "story_slug": story_slug,
        "fact_count": len(facts),
        "facts": facts,
        "planned_page_count": plan.get("page_count") if plan else None,
    }


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
