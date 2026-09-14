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

## ✅ Status: real image generation is verified and working

**Update:** after resolving a Google Cloud API-key/billing chain (three
separate keys hit three separate walls -- org policy, a project the
account didn't administer, and depleted prepay credit, in that order --
before one finally worked), `GeminiImageProvider` produced real,
consistent, publication-quality art. Two independent test stories confirm
it:

<p float="left">
  <img src="docs/demo/example_page1.png" width="270" alt="Page 1: Papa Nurlan discovers a crying baby star" />
  <img src="docs/demo/example_page2.png" width="270" alt="Page 2: Papa Nurlan reaches for the baby star" />
  <img src="docs/demo/example_page3.png" width="270" alt="Page 3: Papa Nurlan reunites the star with its family" />
</p>

Same face, hair, glasses, and suit design across all three pages,
generated from **one locked character description**, each page
conditioned on page 1's image via `reference_image_path` -- nothing here
is hand-picked or touched up. (Gemini also spontaneously added a
"DAD-STRONAUT" name badge and a Kazakhstan flag patch on the suit,
unprompted -- consistent across all three pages too.) A second story (a
gardener rescuing a lost bunny) confirmed this wasn't a one-off: braid,
scarf, and apron stayed consistent across its pages as well.

Set `DADHERO_IMAGE_PROVIDER=gemini` with a working `GEMINI_API_KEY` (see
"Getting a working Gemini key" below -- it took three attempts to find a
key/project combination without an infrastructure wall) to reproduce this.
`MockImageProvider` remains the zero-cost default so a fresh checkout with
no API key still runs the full pipeline end-to-end.

### Getting a working Gemini key (learned the hard way)

Not every Google account/project combination works. In order, what
actually blocked each attempt:

1. A key from an org-managed Google Workspace project: `API Keys are
   Disallowed -- Your organization's security policy disallows API keys.`
   -- not fixable by the account holder; the org admin disabled key auth
   entirely.
2. A key from a project the account didn't administer: Google Cloud
   Console's "Enable API" page showed `You need additional access to the
   project` (`resourcemanager.projects.get` missing) -- not this
   account's project to configure.
3. A key from the account's own default **"My First Project"**: worked for
   auth, but `Your prepayment credits are depleted` -- fixed by adding
   credit at https://aistudio.google.com/apikey (NOT the old-style
   `AIzaSy...` key from the Cloud Console credentials wizard -- the working
   key came from AI Studio's own "Create API key" flow, format
   `AQ.Ab8R...`).

Takeaway: use a personal (non-Workspace) Google account, generate the key
directly from **aistudio.google.com/apikey** (not the Cloud Console
credentials wizard), and make sure that project's prepay credit isn't at
zero.

**AWS Bedrock**, separately, is still blocked as of this writing: payment
instrument fixed, then held at a standard post-payment account
verification quota of 0. `DADHERO_MODEL_PROVIDER` defaults to `anthropic`
for this reason -- see StoryMatch's README for the full Bedrock timeline
(same AWS account). Bedrock remains the documented path back for the
actual submission once verification clears.

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

`dadhero/agent.py` auto-loads a `.env` file (via `python-dotenv`) if one
exists, so set your real values there once instead of exporting them every
shell session:

```bash
source .venv/bin/activate

# Web demo -- reads provider/keys from .env if present
streamlit run app.py

# Terminal demo
python cli_demo.py                # interactive
python cli_demo.py --scripted     # unattended, matches the transcripts above

# Or override per-invocation without touching .env:
DADHERO_IMAGE_PROVIDER=gemini GEMINI_API_KEY=... streamlit run app.py
DADHERO_MODEL_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... streamlit run app.py
```

Reset family memory / generated images between demo runs:
`rm -rf data/family_memory.json data/generated_pages`

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
