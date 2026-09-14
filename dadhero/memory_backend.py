"""
Selects the local-JSON (Streamlit demo) or Supabase (platform backend)
memory implementation at import time, based on DADHERO_MEMORY_BACKEND.
tools.py imports this module as `memory` -- every existing call site
(memory.save_character(...), etc.) keeps working unchanged regardless of
which backend is active.
"""

from __future__ import annotations

import os

if os.environ.get("DADHERO_MEMORY_BACKEND", "local").lower() == "supabase":
    from dadhero import memory_supabase as _backend
else:
    from dadhero import memory as _backend

get_family_profile = _backend.get_family_profile
save_character = _backend.save_character
get_character = _backend.get_character
save_place = _backend.save_place
record_story = _backend.record_story
record_memory = _backend.record_memory
record_progress = _backend.record_progress
reset_family = _backend.reset_family
