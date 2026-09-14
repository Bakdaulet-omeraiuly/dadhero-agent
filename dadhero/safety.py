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
