# DadHero -- 5-minute demo video script

No camera needed -- screen recording + voiceover (or on-screen text) is
fine per the submission rules. Read each VOICEOVER line roughly as
written; ACTION tells you what to have on screen. Total: ~5:00.

Record the live demo section (1:15-3:35) as ONE continuous take against
the real Streamlit app with `DADHERO_MODEL_PROVIDER=gemini` and
`DADHERO_IMAGE_PROVIDER=gemini` set, so the story generation is real --
not scripted/mocked. It genuinely takes a few minutes (real Gemini
calls); either speed up that footage 2-4x with your recorder/editor
while the voiceover keeps pace, or let the Workshop panel's live steps
do the talking under a shorter voiceover and cut to the finished book.

---

## 0:00-0:30 -- The problem

**ACTION:** Title card or the README's opening line on screen: "DadHero
-- turns a child's real life into personalized illustrated stories."

**VOICEOVER:**
"Every parent has told their kid a bedtime story where they're the
hero. AI comic generators exist for this now -- but they're one-shot: describe
a theme, get a comic, forget it happened. They don't remember the
character next time. They don't know 'today he lost his first tooth' is
different from 'make him an astronaut.' And they don't check whether the
character even still looks the same on page 4 as page 1."

## 0:30-1:00 -- Who it's for, and why it matters

**ACTION:** Show the Story Universe sidebar with saved characters/places/stories.

**VOICEOVER:**
"DadHero is for parents who want more than a generator -- a companion
that builds an ongoing Story Universe for their kid: saved characters,
places, past adventures, lessons that actually landed. And it's built
around one non-negotiable safety rule: a real photo of a child is NEVER
used to generate that child's likeness -- only a text description, or
the child's own drawing brought to life. That's not a settings toggle,
it's enforced in the tool layer itself."

## 1:00-1:15 -- Architecture, fast

**ACTION:** Show `docs/architecture/architecture-diagram.png` (or the
README's rendered Mermaid diagram) for a few seconds.

**VOICEOVER:**
"Under the hood: one Strands Agent, 15 purpose-built tools, deciding for
itself which to call and in what order -- not a single giant prompt."

## 1:15-3:35 -- Live demo

**ACTION 1 (1:15-1:45):** Open the live Streamlit app. Click a
quick-start prompt ("A real milestone" -- "My son lost his first tooth
today!") or type a real-life event.

**VOICEOVER:** "Watch what happens when I tell it something that
actually happened today."

**ACTION 2 (1:45-2:45):** Let the Workshop panel run. Expand a couple of
steps live to show the plain-language detail (not raw JSON) -- "Recording
a real family memory," "Creating story plan," "Illustrating a page,"
"Checking visual consistency."

**VOICEOVER:** "Every one of these is a real tool call, not narration --
it reads the family's memory first, decides this is a real event worth
remembering, plans the whole book as a recorded checkpoint before
drawing anything, generates a cover, then each page -- and after every
page, an independent Gemini vision call checks the character still
looks like the same kid. If it drifted, it would regenerate just that
one page."

**ACTION 3 (2:45-3:15):** Show the finished book -- cover + pages,
narration burned into the art.

**VOICEOVER:** "And here's the finished book -- a real cover, the
narration burned right into each panel like an actual printed page, not
a caption underneath."

**ACTION 4 (3:15-3:35):** Click "Continue this adventure." Show it
picking up with the same character.

**VOICEOVER:** "And because it remembers, I can say 'continue this
adventure' and get the next book in the same series -- same character,
no redescribing him."

## 3:35-4:15 -- The parent controls + safety

**ACTION:** Open the "⚙️ Story settings" expander -- age, tone, length,
scary level, educational goal, include/avoid.

**VOICEOVER:** "Parents can set real constraints -- age, tone, how long,
how much tension, a specific lesson like courage or sharing -- and the
agent treats every one as a hard constraint for that story, not a
suggestion. And every page gets screened for age-appropriateness before
it's shown, with a real, explainable check -- not just trusting the
model's judgment silently."

## 4:15-4:45 -- Beyond the hackathon

**ACTION:** Quick flash of the React frontend's "My Universe" gallery
view (`frontend/`), or the OpenAPI reference.

**VOICEOVER:** "This same agent, the exact same tools, also runs behind
a real multi-tenant REST API on FastAPI and Supabase -- Postgres row-
level security, JWT auth, a React frontend -- live-verified end to end,
not just designed. That's the path beyond a hackathon demo."

## 4:45-5:00 -- Close

**ACTION:** Repo URL + live demo URL on screen.

**VOICEOVER:** "DadHero -- github.com/Bakdaulet-omeraiuly/dadhero-agent.
Thanks for watching."

---

## Checklist before you record

- [ ] `DADHERO_MODEL_PROVIDER=gemini` and `DADHERO_IMAGE_PROVIDER=gemini`
      set (real generation, not mock placeholders)
- [ ] Streamlit Cloud sharing set to **Public** (so the live URL you show
      actually works for a viewer who isn't you)
- [ ] Fresh browser tab, not already signed into anything unrelated
- [ ] `data/family_memory.json` has a FEW saved characters/stories
      already (so the Story Universe sidebar isn't empty when you show it) --
      or record that part after your first demo story lands
- [ ] Screen resolution readable at 1080p export (Streamlit's text
      shrinks fast on a 4K screen recorded at native resolution)
