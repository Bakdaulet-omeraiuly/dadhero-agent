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
comic's hero, personalized from an uploaded photo. We deliberately did not
build that: feeding a real minor's photo into a generative image pipeline
is a real child-safety and privacy concern, independent of how the feature
is marketed.

The actual line that matters isn't "never depict a child" -- it's **never
build a character's appearance from a real photo of a real person**. A
benign, text-described child character (name, hair color, a favorite
t-shirt) having an illustrated adventure is the same thing personalized
children's book companies (Wonderbly and similar) have shipped for years
without controversy, because there's no real photo of a real identifiable
person anywhere in the pipeline.

So DadHero supports **any family member as the hero -- including the
child** -- but the character's appearance always comes from the parent's
TEXT description, never an upload. `dadhero/agent.py`'s system prompt makes
this an explicit, non-negotiable rule: decline a photo if one is offered,
ask for a text description instead, regardless of who the character is.

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
live model using it.

`GeminiImageProvider` (Nano Banana / `gemini-3-pro-image`, chosen
specifically for its reference-image character consistency) uses the
official `google-genai` SDK, and its call/response shape IS confirmed live:
a text call through the same SDK succeeds, and an image call reaches the
model and returns a clean, expected `429 RESOURCE_EXHAUSTED` (free tier =
0 quota for image models until billing is enabled) -- not a parsing or
shape error. What's still unverified is the actual generated image
quality and multi-turn character consistency, since no account with image
billing enabled was available during development. See "Before the real
demo" below for the exact two-image test to run once that's unblocked.

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
- **`dadhero/continuity.py`** -- deterministic per-story fact tracking
  (StorySprout's "red backpack on page 1, blue on page 4" problem). Plain
  Python state comparison, not a second LLM call hoping it remembers --
  same philosophy as StoryMatch's evidence verification.
- **`dadhero/safety.py`** -- a real, explainable age-appropriateness screen
  (concerning-term list + length-vs-age heuristic) run on every page's
  text before it's shown, instead of just trusting the model's judgment
  silently.
- **`dadhero/tools.py`** -- 7 Strands `@tool` functions: `save_character`,
  `get_saved_character`, `generate_page_image`, `get_family_memory`,
  `check_story_fact`, `check_page_safety`, `record_finished_story`. Story
  *planning* (the page-by-page outline, and mapping the parent's intention
  to a story objective) is deliberately NOT a tool -- like StoryMatch's
  Narrative Fingerprint extraction, it's the agent's own reasoning, because
  there's nothing external to call for it. Only steps that touch
  persistence, verification state, or generate real media are tools.
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

A second, later verification run tested the child-as-hero path plus the
new continuity/safety tools, from a StorySprout-style *intention* rather
than a plot:

**Parent:** *"My son Arman is 7 and nervous about starting a new school.
Make a funny adventure where he becomes braver and makes a friend. He has
curly brown hair and always wears his favorite green dinosaur t-shirt."*

-> The agent turned "nervous about school" into a treasure-hunt story
where Arman's bravery is *shown* through escalating small challenges
(climbing a tree, crossing a wobbly bridge, calling out to a stranger) --
never a stated moral -- ending with him making a friend, tying his
dinosaur t-shirt into a joke the two new friends bond over. Full tool
trace for the 7-page story:

```
get_family_memory -> save_character
-> check_story_fact x2 -> check_page_safety -> generate_page_image   (page 1)
-> check_page_safety -> generate_page_image                          (page 2)
-> check_story_fact x2 -> check_page_safety -> generate_page_image   (page 3)
-> check_page_safety -> generate_page_image                          (page 4)
-> check_story_fact x2 -> check_page_safety -> generate_page_image   (page 5)
-> check_page_safety -> generate_page_image                          (page 6)
-> check_page_safety -> generate_page_image                          (page 7)
```

22 tool calls for one story -- `check_story_fact` and `check_page_safety`
fire on real pages, not just `generate_page_image` seven times. That
verification density is the actual evidence this is doing agentic work,
not decorating a single prompt.

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
   demo. The request/response plumbing is already confirmed correct (see
   Status above); this step is purely about judging real output quality.

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
> DadHero turns that into something the child can see: describe an idea --
> or just an intention, like "he's nervous about starting school" -- and it
> maps that to a story objective, builds a consistent illustrated character
> (any family member, including the child, always from a text description,
> never a photo), plans a page-by-page arc that shows the lesson instead of
> stating it, checks its own continuity and age-appropriateness on every
> page, and remembers the character for next time.

## Credit

The child-safety reframe (adult-hero-by-default) and initial scope were
this project's own decision; the parent-intention framing, continuity
fact-checking, and explicit safety-tool ideas were adapted from a
teammate's `StorySprout_Hackathon_Idea.md` design doc, with the photo-based
child depiction it proposed deliberately left out for the reasons above.
