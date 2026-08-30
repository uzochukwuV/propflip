# Architecture & Technical Flow

> The "Creator Series Consistency Studio" = one reusable consistency engine, wrapped
> differently for each hackathon. Build the engine first, layer integrations on top.

## 1. High-level architecture

```
                         ┌──────────────────────────────────────────┐
                         │            SHARED CORE  (Python)           │
                        │            SHARED CORE  (Python)           │
                        │  characters/locations  · checker  ·       │
                        │  scene planner  ·  media backend(abc)  ·  │
                        │  evals  ·  store(abc)  ·  test-cases    │
                         └──────────────────┬─────────────────────────┘
                                            │ import (Python)
            ┌──────────────┬───────────────┼─────────────────┬───────────────┐
            │   Layer 1    │   Layer 2     │   Layer 3       │   Layer 4     │
            │  WebMCP      │  All Things   │  Agentic Cinema │  micro1 sprint│
            │  (Sep 3)     │  (Aug 31)     │  (Sep 9)        │  (Aug 31)     │
            └──────────────┴───────────────┴─────────────────┴───────────────┘
```

**Core principles**
1. The core engine has **no dependency on any agent framework**. It exposes plain
   Python functions (`load_series`, `plan_scenes`, `generate_scenes`,
   `check_consistency`, `generate_assets`, `update_character`) and a `Store` protocol (`LocalStorageStore`, `FirestoreStore`,
   `ClickhouseAnalyticsStore`).
2. Each hackathon layer is a **thin wrapper** that mounts the engine behind that
   hackathon's required tech (WebMCP `document.modelContext`, Google ADK + GCP,
   or a coding-agent sprint with a locked env).
3. Evaluation artifacts (baseline vs agent, consistency score, trajectory diffs)
   are generated identically so the "improvement story" transfers across submissions.

## 1b. Layered boundaries — WebMCP is frontend only

```
┌─────────────────────────────┐  browser  ┌──────────────────────────────────────────┐
│  Browser (agent client)      │◄────────►│  WebMCP frontend SPA  (Layer 1 only)     │
│  (Claude Code / ChatGPT /    │  MCP       │  React+Vite, declares document.           │
│   Cursor / Codex)             │  /WebMCP   │  modelContext.registerTool(...)          │
└─────────────────────────────┘            │  Pure-browser: Pyodide core OR              │
                                           │        proxy to FastAPI backend            │
                                           └──────────────────┬────────────────────────┘
                                                              │  (HTTP / signed call)
                                           ┌──────────────────┴────────────────────────┐
                                           │  Backend services  (NOT in the browser)    │
                                           │  • Comfy Cloud MCP (https://cloud.comfy.org/mcp) │
                                           │  • Google Vertex AI / ADK agent (Cloud Run) │
                                           │  • Firestore / ClickHouse / Cloud Storage   │
                                           └──────────────────────────────────────────┘
```

WebMCP is a **browser-native** standard: the *web page itself* opts in by calling
`document.modelContext.registerTool(...)` in its own JavaScript. It is purely frontend.
An *external* agent (Claude Code, ChatGPT in-app browser, Cursor) connects to the page and
calls those tools. WebMCP therefore never touches Comfy, Vertex AI, or GCP directly — it
only mutates the live page state. Any heavy backend (media generation, persistence) is
reached through an HTTP backend the SPA proxies to. Keep the WebMCP layer and the backend
services **separate processes** (the WebMCP host has origin-isolation constraints that
conflict with running arbitrary GCP sidecars).

## 1c. End-to-end user-request flow (concrete example)

Scenario: *"I'm building a sci-fi YouTube series. I uploaded the series bible (3 main
characters + their looks/clothing, 2 locations, 5 established facts) and episode 4's script.
Break it into scenes, generate each scene as video keeping characters/look/clothing/emotion
consistent, check continuity, write YouTube notes, and make a 6-second teaser."*

**The request lands on an agent. What actually runs, per stack:**

```
User request
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│ The agent (who receives this request):                    │
│  Layer 1  → external agent on the WebMCP page             │
│  Layer 2/3→ Google ADK LlmAgent (Gemini 3.5, Cloud Run)   │
│  Layer 4  → a coding agent you pilot at micro1 kickoff    │
└───────────────────────────┬──────────────────────────────┘
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ① load_series            (same call)         (same call)
      • parse series bible   • same              • same
        (characters w/       • same              • same
         visual_ref/lora/    • same              • same
         clothing/emotions)  • same              • same
      • parse ep script →    • same              • same
        scene chunks          • same              • same
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ② plan_scenes             (same)              (same)
      • per scene: pin seed,  • same              • same
        resolve character     • same              • same
        refs + LoRA, set       • same              • same
        emotion/clothing        • same              • same
      • emit GenerationSpec    • same              • same
      (Comfy workflow JSON      • same              • same
       OR Veo params)           • same              • same
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ③ generate_scenes         (same core)         (same core)
      BUT media backend differs:
      Layer 1 (WebMCP):  backend FastAPI proxy ◄── Comfy Cloud MCP
                         (search_templates →    (Wan 2.2 OSS or
                          apply_slots →          Google Veo partner)
                          wait_for_job →
                          get_output → download)
      Layer 2 (GAT):     ADK MCPToolset ◄── Comfy Cloud MCP same as above,
                         assets → GCS + Firestore
      Layer 3 (Cinema):  ADK agent ◄── Veo-on-Vertex directly (compliant),
                         assets → GCS +
                         ClickHouse metrics     • ClickHouse
                                          (compliance partner)
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ④ check_consistency       (same)              (same)
      • appearance_drift     • same              • same
        (ref-image hash)      • same              • same
      • clothing_drift        • same              • same
      • emotion_drift         • same              • same
      • setting_drift         • same              • same
      • name_drift /          • same              • same
        callback_coverage      • same              • same
      • facts                 • same              • same
      persist Metric           • Firestore         • ClickHouse
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ⑤ generate_assets          (same)              (same)
      (teaser/thumbnail/notes,  • same              • same
       same media backends as   • same              • same
       step ③)                  • same              • same
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
   ⑥ Human result             ⑥ Firestore         ⑥ ClickHouse + GCS
      • page reflects          persisted state    metrics +
        findings + scene        + GCS assets      Veo/comfy videos
        videos + teaser         (Cloud Run)       (Cloud Run)
      (via set_episode_asset   • demo ready
       / set_scene_video)      (Cloud Run)
```

**Key invariants across all layers:**
- Steps ①–②, ④–⑤ are the **same core engine** (pure Python); only the persistence store
  and the media backend adapter differ.
- Step ③ (media generation) is the **only** divergence: ① it can run fully client-side in
   the browser for WebMCP (Pyodide core + backend proxy), ② it uses Comfy Cloud MCP for
   WebMCP/GAT (no AI-vendor restriction on either), ③ it uses **Veo-on-Vertex** directly
   for Cinema (Google-only).
- Step ⑥ is always: persist findings/metrics/assets (Firestore / ClickHouse / GCS) + a
   **reflection-back** so the human sees the live result — for WebMCP that's a tool call
   (`set_scene_video`/`set_episode_asset`) that updates the page DOM; for GAT/Cinema it's
   a Cloud Run-rendered UI or a shareable Comfy canvas link.

## 2. Data model — AI video-series continuity

```mermaid
classDiagram
    class Series {
        +series_id: str
        +name: str
        +tone_rules: list[str]        # e.g. "cinematic", "desaturated palette", "no modern tech"
        +language: str
    }
    class Character {
        +canonical: str
        +variants: list[str]          # aliases the checker flags
        +visual_ref: str             # stable reference image URL / asset key
        +lora_ref: str               # consistent LoRA/embedding for generation
        +clothing_styles: list[str]  # canonical wardrobe per scene context
        +emotion_presets: list[str]  # rage / calm / weary ...
        +first_seen: str             # scene_id
    }
    class Location {
        +canonical: str
        +variants: list[str]
        +visual_ref: str
        +description: str
    }
    class Fact {
        +claim: str
        +source_scene: str            # scene_id where it was established
        +confidence: float
    }
    class Scene {
        +scene_id: str
        +episode_id: str
        +setting: str
        +characters: list[SceneChar] # {character, emotion_directive, clothing_state}
        +script: str
        +seed: int                  # FIXED for cross-scene reproducibility
        +ref_image: str             # seed / keyframe image for this scene
        +workflow_id: str           # Comfy/Veo workflow used
        +status: planned|generated|verified
    }
    class ConsistencyFinding {
        +type: appearance_drift|clothing_drift|emotion_drift|setting_drift|name_drift|callback_coverage|facts
        +target: str                # character|location|scene_id|episode_id
        +severity: low|med|high
        +excerpt: str
        +suggestion: str
        +evidence_ref: str
    }
    class GeneratedAsset {
        +key: str
        +kind: video|teaser|thumbnail|notes
        +ref: str                   # GCS/Cloud URL or local path
        +workflow_id: str
        +version: str
    }
    class Metric {
        +series_id: str
        +episode_id: str
        +scene_id: str
        +score: float               # 0–1 continuity accuracy
        +breakdown: dict            # per-drift sub-scores
        +ts: datetime
    }
    Series "1" --> "0..*" Character : characters
    Series "1" --> "0..*" Location : locations
    Series "1" --> "0..*" Fact : facts
    Series "1" --> "0..*" Episode
    Episode "1" --> "0..*" Scene
    Scene "1" --> "0..*" ConsistencyFinding
    Scene "1" --> "0..*" GeneratedAsset
    Scene "1" --> "0..*" Metric
```

This is **frame-level / scene-level** continuity — not just text. The thing being kept
consistent is: which character is on screen, how they look (appearance), what they're
wearing (clothing), how they feel (emotion), where they are (setting), and whether they
reference something established earlier (callbacks / facts). The core engine bakes
**fixed seeds + reference images + character LoRAs** into every generation so scenes stay
visually coherent scene-to-scene and episode-to-episode.

- **Character.lora_ref / visual_ref**: the single most important continuity lever — a
  persisted character LoRA / seed image that every scene generation reuses.
- **Scene.seed**: pinned per scene and stored, so re-runs are deterministic. Drift in a
  re-run = a regression the checker can flag.
- **Metric.per scene + per episode**: written to ClickHouse (Cinema) and Firestore (GAT)
  so the agent can query "which scenes have appearance_drift > 0.5".
- **Store protocol**: `class Store(Protocol)` with `get_series / save_character /
  list_scenes / save_finding / save_metric` — implemented by local JSON (WebMCP),
  Firestore (GAT), ClickHouse (Cinema).

## 3. Core engine — internal flow (video continuity)

```
1. load_series(series_bible, episode_script) ──► Store
   |  parse series bible: characters (visual_ref/lora_ref/clothing/emotions),
   |    locations, facts, tone_rules
   |  parse episode script → chunk into scenes (setting + characters + beat)
   |
2. plan_scenes(series_id, episode_id) ──► [Scene]
   |  for each scene: resolve character refs + LoRAs + fixed seed
   |  emit a generation spec (Comfy workflow JSON OR Veo params) with
   |    seed pinned, character ref image + LoRA, emotion directive baked in
   |
3. generate_scenes(specs) ──► [GeneratedAsset.video]
   |  invoke media backend (Comfy MCP or Veo-on-Vertex) per spec
   |  wait_for_job / get_output / download → store asset + workflow_id
   |
4. check_consistency(series_id, episode_id) ──► [ConsistencyFinding]
   |  appearance_drift   : frame embedding similarity vs Character.visual_ref
   |  clothing_drift     : does the on-screen outfit match Scene.characters[i].clothing_state
   |  emotion_drift      : per-scene emotion vs intended directive (vision-LM check)
   |  setting_drift      : location coherence across scenes of the same setting
   |  name_drift         : character/place name variants vs Character.canonical
   |  callback_coverage  : planned callbacks vs actual on-screen references
   |  facts            : contradictions with stored Fact claims
   |  persist Metric(score, breakdown) per scene + per episode
   |
5. generate_assets(episode_id, kinds=[teaser, thumbnail, notes]) ──► [GeneratedAsset]
   |  teaser: short video from ep highlights (Comfy / Veo)
   |  thumbnail: key frame + overlay text (Comfy / Gemini image)
   |  notes: YouTube/Podcast/blog copy (prompt-templated, uses glossary)
   |
6. evals/run_eval(series_id, episodes, hard_cases) ──► Report
   |  baseline: one-shot generation, fresh seed, NO character refs / LoRAs
   |  agent:    plan → generate → check → correct → regenerate WITH memory + refs
   |  compare:  continuity_accuracy (drift incidents missed/fixed), token cost,
   |            rerun reproducibility (same seed → same frame check)
   |  write changelog.md + trajectories/
```

**Media-backend abstraction.** The engine does not hard-code Comfy or Veo — it produces a
`GenerationSpec` (`{model:"veo"|"comfy", seed, ref_images, prompt_overrides, video_template}`)
and a `MediaBackend` adapter runs it. This is what lets the same engine:
- stay Google-only (Veo adapter) for **Cinema**,
- use Comfy Cloud MCP (OSS or Google-Veo partner node) for **WebMCP/GAT**,
- use a coding agent's local ComfyUI for **micro1** if the problem is media continuity.

The checker's **two-tier verification** mirrors micro1's rubric:
- **Deterministic tier** (rules + fuzzy match + perceptual-hash ref-image comparison) — fast,
  reproducible, unit-tested.
- **LLM tier** (Gemini 3.5 Vision) for emotion/setting judgment + fact contradiction — called
  only when the deterministic check is ambiguous. All LLM calls are logged for trajectory
  dumps (required by micro1; useful for evals everywhere).

## 4. Layer 1 — WebMCP Challenge flow (Sep 3)

```
Browser (Chrome 149+ / ChatGPT)            Backend (optional, FastAPI on Cloud Run/Vercel)
┌──────────────────────────────────────┐   ┌─────────────────────────────────────────────┐
│ React + Vite SPA                     │   │  /api/generate → Comfy Cloud MCP             │
│                                      │   │  /api/check    → Comfy MCP + core engine     │
│  <App/> loads SeriesStudio (Pyodide) │   │  /api/plan     → plan_scenes core            │
│                                      │   │  (only if Pyodide too slow for media)        │
│  document.modelContext.registerTool( │   │                                             │
│    load_series        / plan_scenes │◀──│◀── proxy for heavy video ops                  │
│    check_consistency  / generate_   │   │                                             │
│    scenes / set_scene_video        │   │                                             │
│    update_character               │   │                                             │
│  )                                 │   │                                             │
│                                      │   │                                             │
│  Human edits character sheet ◀──►   │   │                                             │
│  Agent calls tools via MCP client  ◀──►│◀── returns scene videos + asset URLs          │
└──────────────────────────────────────┘   └─────────────────────────────────────────────┘
```

**Runtime contract:**
- On page load: `SeriesStudio.init()` registers tools + a `get_series_state` resource
  (`modelContext.registerResource`) so the agent can read the live glossary/characters.
- `load_series`: human uploads a series bible (characters + looks/clothing, locations,
  facts, tone) + episode scripts → core ingests → scene list renders live on the page.
- `plan_scenes`: agent plans scenes → returns seeds + ref-image/LoRA assignments the UI
  shows as a per-scene card (so the human sees the continuity plan).
- `check_consistency`: tool runs the core checker → UI renders a visual checklist of
  drift findings (appearance / clothing / emotion / setting / callbacks) with the
  evidence frame thumbnail — agent + human both act on it.
- `generate_scenes`: agent calls Comfy (via backend proxy) → `wait_for_job`/`get_output`
  → returns a scene-video URL the page displays inline.
- `update_character`: agent proposes a character correction → UI shows a **confirmation
  dialog**; human accepts/denies (the spec supports `requestUserConfirmation`).
- `set_scene_video`: writes a generated scene video back onto the page so the human sees
  it the instant it lands.
- All state mirrored to `localStorage` so a judge revisiting the URL sees the same series
  (reproducible demo).

**Origin isolation:** set `Origin-Agent-Cluster: ?1` header (Vercel `vercel.json` headers,
or `_headers` on Cloudflare Pages) so `document.modelContext` is enabled.

## 5. Layer 2 — All Things Agentic flow (Aug 31, Collaborative Partner track)

```
Human creator            Cloud Run (Gemini+ADK)         Firestore                  Pub/Sub
   │                         │                            │                          │
   │ "make ep 4: check       │                            │                          │
   │  continuity + scene     │                            │                          │
   │  videos + a teaser"     │                            │                          │
   ├───► LlmAgent(Gemini 3.5)│                            │                          │
   │     tools: load_series,  │                            │                          │
   │       plan_scenes,       │                            │                          │
   │       generate_scenes,   │                            │                          │
   │       check_consistency, │                            │                          │
   │       generate_assets,   │                            │                          │
   │       update_character   │                            │                          │
   │       + Comfy MCPToolset (MCPCloudMCP)   │                          │
   │     memory: FirestoreMemory ◄────────────────────────┤                          │
   │       (series canon/characters persist) │                          │
   │      ┌─────────────────────────────────┐                          │
   │      │ loop: plan→act→verify            │                          │
   │      │ ask clarifying Qs ("Jon or      │                          │
   │      │   John in ep3?")                │                          │
   │      │ propose character corrections   │                          │
   │      │ await human confirmation        ◄──────────────────────────┤
   │      └─────────────────────────────────┘                          │
   │    ◄───────────  report findings + scene videos + teaser          │
   │                        │                          │                          │
   │                        │ (async) Pub/Sub on new episode in GCS    │
   │                        │ ──► Cloud Run worker ──► check_consistency│                          │
   │                        │                            │──► save Metric│                          │
   │                        │                            │──► update Firestore│                          │
```

**Why Collaborative Partner (not Taskmaster):** the core value is a **stateful,
multi-turn, memory-backed conversation** where the agent asks "Did you really mean 'Jon' or
'John' in ep 3?" and remembers the canonical look next episode. That is the Collaborative
Partner definition verbatim ("asks clarifying questions, guides the user, captures feedback,
adapts").

- **Gemini:** `gemini-3.5-flash-002` via Vertex AI (`google-cloud-aiplatform`). Verified
  accepted package + "Gemini 3.5 or newer" rule.
- **Framework:** Google ADK Python. `LlmAgent` with core functions as `@tool`-decorated
  functions + `MCPToolset` for Comfy Cloud MCP.
- **Memory:** ADK `FirestoreMemory` keyed by `series_id` (characters, visual refs,
  canonical clothing) — survives across sessions.
- **Media:** Comfy Cloud MCP via ADK `MCPToolset` (`search_templates`/`apply_slots`/
  `wait_for_job`/`get_output`), assets to Cloud Storage + Firestore. (No AI-vendor
  restriction on GAT, so OSS video like Wan 2.2 is fine; Google Veo partner node also works.)
- **Async/Taskmaster alternative:** the Pub/Sub→Cloud Run path is the event-driven
  "Taskmaster" story (new episode → agent auto-runs checks → emails findings). Submit the
  same repo under either track by changing the framing in the README/video.

**Submission proof-of-GCP:** deploy on Cloud Run, screenshot the Cloud Run service detail
page + a Firestore document in the demo video. Cost: Cloud Run always-free + Firestore
free tier + $150 credits.

## 6. Layer 3 — Agentic Cinema flow (Sep 9, ClickHouse partner track)

Same ADK agent as Layer 2, with two hard constraints layered on top:
(a) **media AI must be Google-only** (Veo-on-Vertex via `google-cloud-aiplatform`), and
(b) **must call one partner at runtime** (ClickHouse here). Frame: *"Series Continuity &
Show-Notes Agent for independent creators."*

```
Human creator  Cloud Run (Gemini+ADK)     Firestore (state)   ClickHouse (analytics)
   │             │                          │                    │
   │ "produce ep4  │                          │                    │
   │  with visual   │                          │                    │
   │  continuity"   │                          │                    │
   ├──► LlmAgent   │                          │                    │
   │     tools: core engine (load_series,    │                    │
   │       plan_scenes, check_consistency,   │                    │
   │       generate_assets, update_char)   │                    │
   │     + Veo adapter (google-cloud-aiplatform)  ◄── only Google AI
   │     + MCPToolset(mcp-clickhouse)        │                    │
   │       → sql_query / sql_insert          │◄──► partner used  │
   │     memory: FirestoreMemory (canon)     │                    │
   │    ┌────────────────────────────────────────┐                │
   │    │ plan: load_series(bible+script)      │                │
   │    │   → plan_scenes (pins seeds + refs)  │                │
   │    │   → generate_scenes via VEO (Google) │                │
   │    │   → check_consistency (drift scan)   │                │
   │    │      → agent calls SQL_INSERT        │                │
   │    │         continuity_metrics(...)      │                │
   │    │   → generate_assets(teaser/notes)   │                │
   │    │   → SQL_QUERY "episodes w/ drift>0.5"│                │
   │    └────────────────────────────────────────┘                │
   │ ◄────── report + scene videos + metrics table               │
```

**How the partner is "used at runtime in code" (passes Cinema review):**
- `mcp-clickhouse` is launched as a real subprocess / connected over HTTP (not a README
  mention). ADK `MCPToolset` imports its `sql_query`/`sql_insert` tools into the agent.
- **Schema we create in ClickHouse** (the compliance story — a real table the agent writes to
  and reads back):
  ```sql
  CREATE TABLE continuity_metrics (
    series_id   String,
    episode_id  String,
    scene_id    String,
    metric_ts   DateTime,
    overall     Float64,
    name_drift  Float64, appearance_drift Float64,
    clothing_drift Float64, emotion_drift Float64,
    setting_drift  Float64, callback_coverage Float64
  ) ORDER BY (series_id, episode_id, scene_id);
  ```
- The agent **calls** these tools: (1) `sql_insert` continuity_metrics after every
  `check_consistency` run, (2) `sql_query` trend questions ("scenes where appearance_drift
  > 0.5", "ep4 vs ep3 character-distance") to explain findings in the demo.
- `get_billing_status` / `get_queue` from Comfy Cloud MCP prove your 5 free runs were
  consumed (nice extra evidence, not the partner).

**Why ClickHouse (not Comfy) is the Cinema partner:** Cinema's allowed AI = Google Cloud AI
or the *chosen partner's* built-in AI. Comfy is NOT a Cinema partner and its own video
models aren't Google. So:
- ✅ **Google video = Veo on Vertex AI** (`google-cloud-aiplatform`) — the AI.
- ✅ **ClickHouse = the compliance partner** — queried via `mcp-clickhouse` at runtime.
- ⚠️ **Comfy** = optional non-AI orchestration layer (templates/search/share + serving Veo
  assets), not the partner. Don't list Comfy as your Cinema track.

**ClickHouse setup:** free $400 credits via `promo=SIGNUP100` (verified); or prototype
against the public playground (`sql-clickhouse.clickhouse.com`, `demo` user). `mcp-clickhouse`
env: `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_SECURE=true`, transport `stdio` local
/ `http` + token for Cloud Run.

**Optional Grafana layer:** ADK OpenLIT instrumentation → Grafana Cloud MCP reads agent
traces. Bonus observability ("observe the agent you build"), not the compliance partner.

## 7. Layer 4 — micro1 sprint (Aug 31) — applied to the core

When the kickoff problem is known:
- Scaffold a fresh repo with `uv init`, lock deps, `Dockerfile` (one-command: `docker
  build -t studio . && docker run ...`).
- The core engine is the **candidate base**: if the problem is creator/continuity
  tooling, reuse `core/` directly; if not, use `core/` patterns (pure-Python, typed,
  tested, reproducible) to build the sprint solution.
- Capture agent **trajectories** (`trajectories/`) — coding-agent turns, edits, test runs.
- Run `pytest` (hard-case tests) + `ruff` + `mypy`; emit a `changelog.md` (baseline →
  final → evidence) and `REPRODUCTION.md` (exact clone+run steps).

If the micro1 problem is **unrelated** to series consistency, do NOT force-fit the studio:
build a focused 3-day solution but apply the same discipline (locked env, trajectory
dump, edge-case tests, ambiguity log). Document that explicitly in the write-up — micro1
explicitly rewards "stating what you deliberately did not do, and why" as engineering
judgment.

## 8. Sample ADK agent (Layer 2/3 skeleton)

```python
# agents/continuity_agent.py
import os
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool, MCPToolset, McpConnectionParams
from core.engine import load_series, plan_scenes, generate_scenes, check_consistency
from core.engine import generate_assets, update_character
from core.media_backend import VeoBackend, ComfyCloudBackend
from core.firestore_store import FirestoreMemory

# Core engine functions → ADK tools (core stays framework-agnostic)
core_tools = [
    FunctionTool(load_series),
    FunctionTool(plan_scenes),
    FunctionTool(check_consistency),
    FunctionTool(generate_assets),
    FunctionTool(update_character),
]

# Layer 2 (GAT): Comfy Cloud MCP for media (OSS video OK; Google Veo partner node OK too)
comfy_tools = MCPToolset(
    connection_params=McpConnectionParams(
        transport="streamable-http",
        url="https://cloud.comfy.org/mcp",
        headers={"X-API-Key": os.environ["COMFY_API_KEY"]},
    )
)

# Layer 3 (Cinema): ClickHouse partner (runtime) + Google Veo for the AI
clickhouse_tools = MCPToolset(
    connection_params=McpConnectionParams(
        transport="stdio", command="mcp-clickhouse"
    )
)

agent = LlmAgent(
    model="gemini-3.5-flash-002",
    name="series_continuity_agent",
    instruction=(
        "You are a continuity guardian for a creator's series. "
        "Break scripts into scenes with FIXED seeds + per-character reference images "
        "and LoRAs so characters look identical scene-to-scene. "
        "After generating, scan for appearance / clothing / emotion / setting drift. "
        "Before changing a character sheet, ask the human to confirm. "
        "Always cite which scene a fact was established in."
    ),
    tools=[*core_tools, comfy_tools],          # Layer 2
    # tools=[*core_tools, clickhouse_tools],   # Layer 3 (uncomment + Veo backend)
    memory=FirestoreMemory(collection="studio_memory"),
)
```

**Entry points:**
- `main.py` → `adk_agents.run(agent, ...)` (web/Layer 2/3 entry).
- `worker/main.py` → Pub/Sub-triggered Cloud Run job: `load_series → plan_scenes →
  generate_scenes(VeoBackend) → check_consistency → sql_insert(metrics)` (Layer 3 async).
- `cmd/local_demo.py` → runs the core engine + local ComfyUI (`comfy-mcp` stdio) end-to-end
  with no cloud (micro1-friendly, fully reproducible).
