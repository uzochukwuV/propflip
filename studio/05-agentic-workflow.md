# Agentic Workflow — Three Levels

> This is the *product* the Studio actually delivers: an agentic pipeline that turns a
> one-line idea into a multi-episode AI-video series with frame-accurate continuity
> (same character looks, same wounds, same laugh, same costume — across scenes and
> episodes). Built on the shared core from `02-architecture-and-flow.md`.

```
Level 1  STORY & SCRIPT      (the "brain")   — 1 long, coherent series first
          ↓
Level 2  SCENE / CHARACTER    (the "hands")   — images+video, details persist scene→scene
          ↓
Level 3  AUDIO                (the "soul")    — music/sound/dialogue per scene  (lower priority)
```

---

## Level 1 — Story & Script Generation (the brain)

### 1a. Story generation: how do agents write *good* stories?

A good long story needs structure + continuity discipline, not just a freeform LLM dump.
The StoryPlanner agent scaffolds structure, then iterates.

**Story templates / sources (the agent can pull from any of these):**
- **Structure templates**: Hero's Journey, Save-the-Cat beat sheet, Dan Harmon story circle,
  Pixar spine (`Once upon a time… every day… but one day… because of that… until finally…`).
  These give the agent a skeleton for pacing + a place for every beat.
- **Seed sources**: a user one-line prompt; or a public-domain story (Project Gutenberg,
  Grimm) the agent *adapts* (rename characters, relocate setting) to dodge copyright and
  jump-start a coherent arc.
- **World + character cards**: the agent emits a `SeriesBible.json` — characters (name,
  visual reference, costume palette, mannerisms), locations, tone rules, the series
  arc (episode-by-episode beat sheet), and **callback/foreshadowing registry** (this is
  the seed for the continuity checker).

**Making agents generate good stories — the loop:**
```
idea → outline → self-critique outline (pacing? missing callback?) → expand beats
   → self-critique beats (contradictions?) → produce SeriesBible.json
   → (optional) external critique pass (human or a second LLM call) → finalize
```
The agent logs every revision to trajectories (micro1 evidence), and the SeriesBible is
the **first persisted artifact** — everything downstream references it.

**Crucial output of this level:** for *each character*, the agent commissions a
**reference portrait** (via Comfy `partner_generate` with Gemini, or Veo image) that becomes
that character's `visual_ref` + `lora_ref` (trained from that portrait). No more "who does
this character look like" ambiguity downstream.

### 1b. Script generation — emotion, action, costume, dialogue

The script is the **per-scene directive** fed into generation. It is *not* a film screenplay
only — it is a structured manifest the agent + Comfy graph consume.

**Per scene, the script contains:**
```
{
  "scene_id": "S1_E1_03",
  "setting":  "cargo bay, emergency lighting, steam",   // ties to Location.visual_ref
  "lighting": "low, orange, volumetric",
  "characters": [
    {"name": "Kara", "emotion": "frustrated-laughing", "action": "wipes blood from her glove",
     "costume_ref": "char_Kara_wardrobe_A",             // resolved from Character.lora_ref
     "dialogue": [{"line": "...", "intonation": "sardonic, rising"}]}
  ],
  "prev_frame_ref": "assets/S1_E1_02_Kara_hands_bloody.png",  // LEVEL 2 handoff slot
  "seed": 42,                                              // pinned for reproducibility
  "camera": "medium close-up, push-in"
}
```

**Key design decision (your note):** *"what they are wearing will always be inferred from
the images that will be fed to the agents."* → **The script does not invent costumes.**
Costume, look, and injury state are read from the persisted `Character` record + salvaged
keyframes from the previous scene, and written into the script as `costume_ref`/
`prev_frame_ref`. The scriptwriter agent *reads* the visual state, it doesn't re-imagine it.

---

## Level 2 — Scene / Character Generation (the hands)

### The core continuity loop (where your "snap and feed" idea lives)

After scene N is generated, the agent **salvages salient frames** and **persists state**,
then feeds both into scene N+1. This is the agentic workflow's "state handoff."

```
Scene N-1 video/image
   │
   ├─► [Vision-LM (Gemini 3.5 Vision) salvalage pass]
   │       • "segment Kara's hands, isolate the blood patch"
   │       • "capture the exact laughing mouth shape + eyebrow raise"
   │       • "capture the wound bandage on her left forearm"
   │       → save assets/S1_E1_02_Kara_hands_bloody.png, _laugh.png, _bandage.png
   │
   ├─► [State update]  Character["Kara"].state = {
   │       wounds: {hands: "blood", forearm: "bandage"},
   │       mood: "frustrated-laughing",
   │       costume: "wardrobe_A (blood-stained left sleeve)"
   │     }  persisted to Firestore (long-term memory)
   │
   └─► Scene N prompt = SceneScript(N)
            + Character["Kara"].visual_ref / lora_ref      (who she is)
            + Character["Kara"].state                      (what happened to her)
            + asset/S1_E1_02_Kara_hands_bloody.png        (visual continuity anchor)
            + asset/S1_E1_02_Kara_laugh.png                 (emotion continuity anchor)
            + seed pinned to SceneScript.seed
      ──► generate_scenes()  [Comfy run_template / Veo]
            → Scene N video
            → (loop back for scene N+1)
```

### How each "persisted detail" is enforced at generation

| Detail type | How it's carried forward | Where enforced |
|---|---|---|
| **Character look** | `visual_ref` portrait + trained `lora_ref`; same ref image + LoRA loaded in every Comfy graph | Scene planner pins these to every `run_template` call |
| **Wounds / blood / props** | salvaged keyframes (`assets/<scene>_<char>_<detail>.png`) + `Character.state.wounds` record; salvaged frame used as **image-to-video** seed / ControlNet reference in Comfy | Vision-LM salvage pass + Comfy `LoadImage`/`ControlNet` |
| **Expression / emotion** | `Scene.characters[].emotion` directive baked into prompt + salvaged reaction frame as a **reference image** for the next scene's emotional carry-over | Gemini Vision captures the micro-expression; fed as `prev_frame_ref` |
| **Clothing / costume** | `Character.state.costume`; if a sleeve got blood-stained in N-1, scene N reuses the *stained* asset + a ref image of the torn sleeve | Scriptwriter reads persisted state; Comfy image-to-image / Veo reference |
| **Settings / lighting** | `Location.visual_ref`; consistent seed; lighting baked into scene directive | Scene planner pins same lighting + ref |

### Resource flow into the next agent call

Your note: *"what resource do we use to prompt the next agent?"* — the answer is a **3-part
resource envelope** passed to each generation:
1. **Reference images**: character `visual_ref`/LoRA + salvaged keyframes (`assets/*.png`).
2. **Structured prompt overrides**: `SceneScript(N)` rendered into the Comfy template's
   `apply_slots` override (prompt, seed, steps, ref-image path, ControlNet weight).
3. **State snapshot**: `Character.state` JSON (wounds, mood, costume) appended into the prompt
   as a "carry-over" clause so the model *knows* ep3 Kara is bloodied from ep2.

Comfy makes this concrete: `search_templates("img2img video")` → `apply_slots({prompt, seed,
image: assets/...png, ...})` → `wait_for_job` → `get_output`.

---

## Level 3 — Audio (lower priority)

After scenes are locked: an AudioAgent calls Comfy's audio templates (Lyria 3 for music,
Gemini 3.1 Flash TTS for dialogue) keyed off `SceneScript.dialogue` + `Scene.characters.emotion`
+ `Location.setting`. Not in scope for the first demo — defer.

---

## Agent topology (how many agents, why)

The story + script + scene work is genuinely open-ended continuity planning, so per the
agentic standard this justifies an **orchestrator + sub-agents**, not a single L2 agent:

```
┌──────────────────────────────────────────────────────────┐
│  Orchestrator LlmAgent (Gemini 3.5)                      │
│   owns: planning, delegation, state handoff, final QC    │
│   tools: plan_scenes, generate_scenes, check_consistency,│
│          save_state, salvage_keyframes                   │
│             │                                             │
│   ┌─────────┴──────────┐  ┌──────────────┐  ┌───────────┐ │
│   │ StoryAgent         │  │ SceneAgent   │  │ Checker  │ │
│   │ (Level 1)          │  │ (Level 2)    │  │ (verify) │ │
│   │ - story_bible      │  │ - salvage_   │  │ - drift  │ │
│   │ - write_script     │  │   keyframes  │  │   scan   │ │
│   │                    │  │ - gen via    │  │          │ │
│   └────────────────────┘  │   Comfy/Veo  │  └───────────┘ │
└──────────────────────────────────────────────────────────┘
          ▲                 ▲            ▲
          │                 │            │
   Comfy MCP (templates,   Comfy MCP   Veo adapter
   run_template, get_       (submit/    (google-cloud-
   output)                  wait/get)   aiplatform)
```

**Hackathon-speed simplification:** a **single ADK LlmAgent** with all core tools + Comfy +
Veo is sufficient for demos (the orchestrator *is* the agent; sub-agents collapse into tool
calls). Use the full topology only if you have runway past Sep 3.

---

## How this maps to the four hackathons

| Hackathon | Which levels shown | Why |
|---|---|---|
| WebMCP | L1 story outline + L2 scene salvage (demo 2–3 scenes) | Live page: agent generates outline, generates a scene, human salvages a "blood on hands" frame in the UI, next scene reuses it |
| All Things Agentic | L1 + L2 end-to-end on Cloud Run (Firestore state) | "Collaborative Partner": agent asks "keep Kara's blood stain into ep3?" and remembers across sessions |
| Agentic Cinema | L1 + L2 + ClickHouse metrics (Veo for the AI) | "Continuity agent for indie creators": Veo-generated scenes, drift metrics in ClickHouse |
| micro1 | whatever the kickoff problem is; reuse `salvage_keyframes` + fixed-seed reproducibility as the engineering pattern | Reproducible env + trajectory dumps of the salvage/state loop |
