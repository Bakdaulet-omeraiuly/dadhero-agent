"""
Deterministic, explainable age-appropriateness screen for generated page
text -- StorySprout's check_child_safety() idea, implemented as a real
keyword/heuristic pass rather than "trust the LLM said it's fine."

Not a substitute for the system prompt's own judgment (tone, whether
"peril" stays gentle) -- this catches the clear, checkable failure mode:
concerning words slipping into text meant for a young child. Cheap, fast,
and its findings are demoable (the agent calling this and getting a real
flag is more convincing to a judge than a claim of safety).
"""

from __future__ import annotations

import re

# Deliberately conservative and small -- flags for a human/agent to
# reconsider a word choice, not a hard content-moderation system. Mild
# fairy-tale peril ("worried", "lost", "scared for a moment") is fine and
# NOT flagged; this list targets clearly heavier content.
_CONCERNING_TERMS = [
    "kill", "killed", "killing", "murder", "die", "dies", "dying", "dead body",
    "blood", "gore", "gun", "knife", "weapon", "shoot", "stab",
    "suicide", "self-harm", "abuse", "kidnap",
    "curse word", "hate", "racist", "sexist",
]

_MAX_RECOMMENDED_WORDS_PER_AGE = {
    3: 25, 4: 30, 5: 35, 6: 45, 7: 55, 8: 70, 9: 85, 10: 100,
}


# Terms that mean "this character is a minor." Deliberately broad/blunt --
# a false positive here just means the parent gets asked to describe the
# character in words instead of uploading a photo, which is a mild
# inconvenience. A false negative would mean a real child's photo went
# into an image-generation pipeline, which is the actual harm this exists
# to prevent. Bias hard toward refusing when unsure.
_MINOR_RELATIONSHIP_TERMS = [
    "child", "kid", "son", "daughter", "boy", "girl", "baby", "infant",
    "toddler", "teen", "teenager", "niece", "nephew", "grandchild",
    "student", "pupil",
]


def is_minor_relationship(relationship: str) -> bool:
    """True if `relationship` suggests the character is a child, in which
    case a photo must never be used as the basis for their appearance --
    only a text description. See PHOTO_SAFETY_RULE for why."""
    lowered = relationship.strip().lower()
    return any(term in lowered for term in _MINOR_RELATIONSHIP_TERMS)


PHOTO_SAFETY_RULE = (
    "A real photo of a child must never be used to generate that child's "
    "likeness. This applies regardless of the parent's intent or "
    "permission -- describe the character in words instead (hair, an "
    "accessory, a distinguishing feature)."
)


def check_age_appropriateness(text: str, child_age: int | None = None) -> dict:
    """
    Scan one page's narration text for clearly age-inappropriate content
    and (optionally) flag if it's noticeably longer than what's typical
    for the given age.
    """
    lowered = text.lower()
    hits = [term for term in _CONCERNING_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)]

    word_count = len(text.split())
    length_flag = None
    if child_age is not None:
        # Find the nearest defined age bracket at or above child_age.
        bracket_ages = sorted(_MAX_RECOMMENDED_WORDS_PER_AGE)
        applicable = next((a for a in bracket_ages if a >= child_age), bracket_ages[-1])
        limit = _MAX_RECOMMENDED_WORDS_PER_AGE[applicable]
        if word_count > limit * 1.5:
            length_flag = f"Page is {word_count} words -- noticeably long for age {child_age} (guideline ~{limit})."

    passed = not hits and not length_flag
    return {
        "passed": passed,
        "concerning_terms_found": hits,
        "word_count": word_count,
        "length_flag": length_flag,
    }
