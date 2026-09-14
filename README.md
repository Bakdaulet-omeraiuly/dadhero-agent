# DadHero

> Tell it your idea. It turns a family member into your child's comic-book hero.

An agentic personalized-comic generator built on **Strands Agents** +
**Amazon Bedrock**, for the "Agents for Humans" (Strands Agents) hackathon,
Everyday Agents track. A parent describes an idea; the agent builds a
consistent illustrated character, plans a short story arc, generates each
page, and refines on feedback -- across sessions, remembering the character
so they don't need re-describing next time.

## The safety decision this product is built around

Early versions of this idea considered depicting the **child** as the
comic's hero, personalized with their photo and name. We deliberately did
not build that: generating images of a real minor from an uploaded photo is
a real child-safety and privacy concern, independent of how the feature is
marketed.

**DadHero depicts an adult family member instead** (a dad, mom, grandparent,
etc.), described in text by the parent who is making the gift -- never a
photo, never the child. This keeps the emotional hook that made the idea
worth building ("my child's own dad, drawn as their hero") while removing
the part that shouldn't be built. `dadhero/agent.py`'s system prompt
explicitly refuses to depict a child and redirects toward an adult family
member if asked.

## ⚠️ Status: image generation is the one unverified piece

Three separate infrastructure walls were hit building this, in order:

1. **AWS Bedrock** -- payment instrument fixed, then blocked by standard
   post-payment account verification (quota held at 0). Same account used
   for the StoryMatch project; see that repo's README for the full
   timeline. Still pending as of this writing.
2. **First Gemini API key** -- rejected with `API Keys are Disallowed:
   Your organization's security policy disallows API keys. Please use
   Application Default Credentials (ADC) instead.` The Google Cloud
   project behind this key is under an org policy (likely a
   Workspace/enterprise identity) that blocks API-key auth entirely.
3. **Second Gemini API key** -- a different project; blocked on two
   independent things: `generativelanguage.googleapis.com` requests
   flagged as "blocked" (a key-level API restriction), and the Generative
   Language API not enabled on that project at all
   (`console.developers.google.com/apis/api/generativelanguage.googleapis.com`).

**None of this blocked the build.** `dadhero/image_providers.py` defines a
provider interface with a `MockImageProvider` that draws a real, labeled
placeholder PNG locally (no network, no cost) -- the entire agent loop
(character bible -> story plan -> per-page generation, chaining a
reference image forward for consistency -> feedback -> single-page
regeneration -> family memory) was built and verified end-to-end against a
live model using it. `GeminiImageProvider` (Nano Banana /
`gemini-3-pro-image`, chosen specifically for its reference-image character
consistency) is fully written but **has not yet produced a single real
image** -- confirm its request shape against an actual response before
trusting it in a demo. See that file's docstring for exactly what to check.

## Why Gemini "Nano Banana" over Bedrock's image models for this specific job

Bedrock's Titan Image Generator and Stability models support
style-conditioning from a reference image, but Nano Banana
(`gemini-3-pro-image`, and the newer `gemini-3.1-flash-image`) is
specifically built and marketed for keeping **the same subject** consistent
across a multi-turn, edited conversation -- which is the single hardest
technical problem in this product (a comic where "Dad" looks like a
different person on every page fails immediately). If Bedrock access clears
before Gemini access does, Titan Image is the documented fallback path
(same provider-interface pattern -- add a `TitanImageProvider` implementing
`ImageProvider`), at some cost to consistency quality.

## What's built (MVP)

- **`dadhero/models.py`** -- `CharacterBible` (the "Narrative Fingerprint"
  equivalent for this domain: a locked, reusable appearance description)
  and a small library of proven picture-book story shapes
  (`STORY_TEMPLATES`) the agent picks from instead of inventing structure
  from scratch each time.
- **`dadhero/memory.py`** -- local JSON family memory: saved character
  bibles (reuse "Dad the Astronaut" without redescribing him) and a log of
  past story titles/themes.
- **`dadhero/image_providers.py`** -- the `ImageProvider` interface,
  `MockImageProvider` (proven), `GeminiImageProvider` (written,
  unverified -- see Status above).
- **`dadhero/tools.py`** -- 5 Strands `@tool` functions: `save_character`,
  `get_saved_character`, `generate_page_image`, `get_family_memory`,
  `record_finished_story`. Story *planning* (the page-by-page outline) is
  deliberately NOT a tool -- like StoryMatch's Narrative Fingerprint
  extraction, it's the agent's own reasoning, because there's nothing
  external to call for it. Only steps that touch persistence or generate
  real media are tools.
- **`dadhero/agent.py`** -- the Strands `Agent`, Bedrock primary /
  Anthropic fallback (same pattern as StoryMatch), with a system prompt
  encoding the full workflow including the child-safety redirect above.
- **`app.py`** -- Streamlit chat UI; renders the agent's own markdown
  (which embeds `![](image_path)` references) directly.
- **`cli_demo.py`** -- terminal fallback with a `--scripted` mode replaying
  a verified real transcript, unattended.
- **`tests/`** -- pytest for everything that doesn't need a live model
  (CharacterBible formatting, memory round-trips, mock image provider,
  agent tool wiring). Run with `python -m pytest tests/ -q`.

## Verified end-to-end (real transcript, Anthropic API, mock images)

Three-turn conversation, run for real during development:

1. **Parent:** *"My husband Nurlan has short black hair, always wears
   black-framed glasses and a red hoodie, and a big warm laugh. I want a
   5-page comic where he's a brave astronaut who rescues a lost baby star,
   for our 5-year-old daughter Aisha."*
   -> Agent called `get_family_memory` (empty, first time), `save_character`
   (locking in Papa Nurlan's `prompt_fragment`), then `generate_page_image`
   five times -- page 1 with no reference, pages 2-5 each passing page 1's
   `image_path` as `reference_image_path`. Produced a full 5-page story
   with warm, age-appropriate text and (mock) illustrations, and correctly
   labeled them as placeholders rather than claiming they were final art.

2. **Parent:** *"Love it! Page 2 feels a little sad -- can you make the
   baby star look curious instead of scared? Everything else is perfect."*
   -> Agent regenerated **only page 2** (same character fragment, same
   reference image), left pages 1/3/4/5 untouched, and asked if the story
   was ready to save.

3. **Parent:** *"Save this story please!"*
   -> Called `record_finished_story`. Confirmed Papa Nurlan is now saved
   for reuse in future stories without redescribing him.

## Setup

```bash
cd DadHero-Agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit as needed
```

## Run

```bash
source .venv/bin/activate

# Web demo (mock images, no API key needed)
streamlit run app.py

# Terminal demo
python cli_demo.py                # interactive
python cli_demo.py --scripted     # unattended, matches the transcript above

# Once Gemini access is confirmed working:
DADHERO_IMAGE_PROVIDER=gemini GEMINI_API_KEY=... streamlit run app.py

# Local dev without waiting on AWS Bedrock:
DADHERO_MODEL_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... streamlit run app.py
```

Reset family memory / generated images between demo runs:
`rm -rf data/family_memory.json data/generated_pages`

## Before the real demo: verify GeminiImageProvider against a live response

1. Fix whichever of the three blockers above resolves first (Bedrock
   verification clearing, or a Gemini project with billing enabled, API-key
   auth allowed, and the Generative Language API enabled).
2. Generate ONE image standalone and inspect it:
   ```python
   from dadhero.image_providers import GeminiImageProvider
   p = GeminiImageProvider()
   result = p.generate("A friendly cartoon dad astronaut, flat illustration style", output_name="test1")
   print(result)  # open result.path
   ```
3. Generate a second image passing `reference_image_path=result.path` with
   a different scene, and actually look at both side by side -- confirm
   the character looks like the same person before trusting this in a live
   demo. If the response shape differs from what `image_providers.py`
   expects (field names, missing `inlineData`, etc.), fix it there --
   that's the one part of this codebase written without being able to see
   a real response.

## What's deliberately not built (cut for time)

- Multiple children / multiple simultaneous heroes in one story.
- Export to a shareable PDF/printable comic layout -- pages currently exist
  as separate PNG files plus markdown text, not composited into panels.
- A proper "character sheet" reference-sheet generation step (turnaround
  views) before the first story page -- would likely improve consistency
  further but adds a generation step and cost.
- The Bedrock Titan Image fallback provider mentioned above -- only sketched
  in this README, not implemented.

## Pitch (for the submission form)

> Every parent has told their kid a bedtime story where they're the hero.
> DadHero turns that into something the child can actually see: describe an
> idea, and it builds a short illustrated comic starring a real family
> member -- consistent from page to page, remembered for next time, and
> designed from the ground up to never need a photo of your child to work.
