"""
DadHero platform backend (FastAPI). Reuses dadhero/ (the same Strands
agent, tools, and providers the Streamlit demo runs) with the Supabase-
backed memory/storage backends selected via env vars -- see README.md.

Run: uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Explicit path, not bare load_dotenv() -- that searches the CURRENT
# WORKING DIRECTORY upward, which silently finds nothing (not an error,
# just an empty environment) when uvicorn is launched from the repo root
# rather than backend/. Found this the hard way testing against a real
# Supabase project: SUPABASE_URL read as "" with no exception until much
# later, at first actual use.
load_dotenv(Path(__file__).resolve().parent / ".env")

# The platform backend always runs the Supabase-backed memory/storage
# paths, regardless of what's in .env -- DADHERO_MEMORY_BACKEND=local
# would silently write to a local JSON file no browser client could ever
# read back, which is a much worse failure mode than being opinionated
# here. Set these before importing anything from dadhero/ that reads them
# at import time.
os.environ["DADHERO_MEMORY_BACKEND"] = "supabase"
os.environ.setdefault("DADHERO_STORAGE_BACKEND", "supabase")
os.environ.setdefault("DADHERO_IMAGE_PROVIDER", "gemini")

from backend.routers import characters, conversations, memories, places, progress, stories  # noqa: E402

app = FastAPI(title="DadHero API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("DADHERO_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(characters.router)
app.include_router(places.router)
app.include_router(stories.router)
app.include_router(memories.router)
app.include_router(progress.router)
app.include_router(conversations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
