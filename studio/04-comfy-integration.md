# ComfyUI / Comfy Cloud MCP Integration

> Researched & verified against official Comfy docs (`docs.comfy.org/agent-tools/mcp`) on Aug 29, 2026. This is how Comfy Cloud MCP (`https://cloud.comfy.org/mcp`) plugs into the Creator Series Consistency Studio across the four hackathons, and where your **5 free AI video runs** land.

## 1. What ComfyUI / Comfy Cloud MCP actually is

**ComfyUI** is a node-based, visual workflow engine for generative AI (images, video,
audio, 3D). Think: a graph canvas where you chain model nodes → post-process → export.

**Comfy Cloud MCP** (`https://cloud.comfy.org/mcp`) is Comfy's **hosted MCP server** that
exposes Comfy Cloud's GPU-backed ComfyUI workflows as **MCP tools** over
**Streamable HTTP**. You add one URL to any MCP-capable agent, sign in once (OAuth or
API key), and the agent can search templates/models/nodes, submit workflows, and retrieve
generated media.

Two connections (pick one — you can run both):

| Connection | Where it runs | Auth | Free to start? | 5 free runs apply to |
|---|---|---|---|---|
| **Comfy Cloud MCP** (hosted) | `https://cloud.comfy.org/mcp` (Cloud GPUs) | OAuth (Claude Code/Claude Desktop/Codex/OpenClaw) or `X-API-Key` header (Cursor/headless) | Discovery free w/ account | ✅ Yes — cloud generations |
| **Local Comfy MCP** (`comfy-mcp` PyPI → stdio) | Your machine / ComfyUI install | none (local) | Fully free (your GPU) | ❌ No — local-only |

### Your 5 free AI video runs
Verified directly from the docs: *"new users get 5 free runs to try it out."* Sign up at
`cloud.comfy.org`, connect the MCP server to your agent, and the 5 runs cover video
generation (e.g. Wan 2.2, LTX, Seedance templates).

**Caveat (important):** *"A credit or top-up balance alone does not grant access: you need
an active subscription to run generations, even if you have unused credits."* So the 5 free
runs come with the signup/subscription window. They're real and usable for a hackathon
demo — just don't assume they persist beyond the free period. Discovery tools
(`search_templates`, `search_models`, `search_nodes`) are free with only a Comfy account,
no subscription needed.

## 2. Comfy Cloud MCP tool surface (the ones that matter)

**Discovery (free, no subscription):**
- `search_templates` — find a video template by model/media-type (e.g., "Wan 2.2 video").
- `get_template` / `get_template_schema` — inspect + see which params you can override.

**Generation:**
- `run_template` — run a pre-built template by name (preferred path).
- `submit_workflow` — run a raw ComfyUI API workflow JSON.
- `partner_generate` — generate with partner-API models (Flux, Grok, **Gemini**, OpenAI,
  Ideogram, Seedream/Seedance).
- `upload_file` — upload an input image (e.g., a keyframe / character sheet) to seed a gen.

**Jobs (async orchestration primitives):**
- `get_job_status` / `wait_for_job` — poll or block until a generation finishes.
- `get_output` — retrieve the result (returns a **temporary signed URL** + a ready-to-run
  `curl` command — see "shell download step" caveat below).
- `submit_batch` / `get_batch_status` / `get_batch_output` / `wait_for_batch` — batch up
  to 50 generations from one call; the batch ID survives sessions (great for generating a
  whole series of teasers).
- `use_previous_output` — chain workflows (ep N asset → ep N+1 continuation).
- `cancel_job` / `get_queue` — manage the GPU queue.

**Sharing (reproducibility — key for micro1):**
- `save_workflow` / `update_workflow` / `run_saved_workflow` — versioned, rerunnable.
- `share_workflow` / `import_shared_workflow` — publish a `?share=<id>` URL anyone can
  rerun.
- `get_workflow_canvas_url` — link that opens the workflow on the Comfy Cloud canvas
  (proof it really ran; embeds the exact params).

**Account:**
- `get_billing_status` — check remaining free runs / credits (useful in a demo to prove
  "5 free runs" are consumed).

## 3. Where Comfy Cloud MCP plugs into each studio layer

```
                        Core engine (Python)
                              │
  ┌───────────────────────────┼────────────────────────────┐
  │ Layer                     │ Comfy role                 │
  │ 1 WebMCP (Sep 3)          │  Creative asset generator  │
  │ 2 All Things (Aug 31)     │  Supporting-gen tool (Gemini│
  │ 3 Agentic Cinema (Sep 9)  │   is the AI; partner=ClickH│
  │ 4 micro1 (Aug 31)         │  Bonus asset gen if prob.  │
  │                          │  fits creator tool)         │
  └───────────────────────────┴────────────────────────────┘
```

### Layer 1 — WebMCP Challenge (best home for Comfy video)
**Why it fits:** WebMCP has **no AI-vendor restriction**. The OpenAI challenge wants "a
web app where humans and agents collaborate." Comfy Cloud MCP gives you the GPU-backed
generations; WebMCP gives you the in-page tools the agent calls.

**Architecture:** The external agent (Claude Code / Codex / Cursor, or ChatGPT in-app
browser) is configured with **two** tool sources simultaneously:
1. The WebMCP-enabled page (`https://your-app.vercel.app`) → `load_series`,
   `check_consistency`, `generate_notes`, `update_glossary` (native `document.modelContext`).
2. Comfy Cloud MCP (`https://cloud.comfy.org/mcp`) → `search_templates`, `run_template`,
   `wait_for_job`, `get_output`.

The agent orchestrates both:
> "Check continuity for series S1, then generate a 5-second teaser video for ep 4 using
> the 'Wan 2.2 video' template with the prompt 'retro-futuristic newsroom' and the
> character sheet I just uploaded."

The agent calls WebMCP tools on the page, then calls Comfy tools in its own environment,
then writes the resulting asset back onto the page (via a `set_episode_asset` WebMCP tool
you define) so the human sees it update live.

### Key constraint: WebMCP tools live in YOUR frontend, not on existing sites

WebMCP does **not** auto-instrument arbitrary websites. The page itself must opt in by
calling `document.modelContext.registerTool(...)` in its own JS/TS. An external agent
(Claude Code / ChatGPT in-app / Cursor) then discovers those declared tools and invokes
them. Existing platforms only expose WebMCP tools if their owners already shipped that
`registerTool` code. Therefore the WebMCP Challenge *requires* you to build/adapt the
frontend that declares the tools — there is no shortcut.

**WebMCP tool to expose asset write-back:**
```javascript
await document.modelContext.registerTool({
  name: "set_episode_asset",
  description: "Attach a generated image/video/audio asset (Comfy Cloud output) to an episode in the UI. src is a signed URL from get_output, mime is 'image/png'|'video/mp4'|'audio/mp4'.",
  inputSchema: {
    type: "object",
    properties: {
      episode_id: { type: "string" },
      src:        { type: "string" },
      mime:       { type: "string", enum: ["image/png","video/mp4","audio/mp4"] },
      alt:        { type: "string" }
    },
    required: ["episode_id", "src", "mime"]
  },
  execute: async (input) => {
    window.SeriesStudio.attachAsset(input);   // updates the live DOM
    return `Attached ${input.mime} to ${input.episode_id}`;
  }
});
```

**Host:** the WebMCP SPA on Vercel/Cloudflare (free tier). Comfy runs in the agent's
environment — no backend needed on your side. Your 5 free runs are consumed here.

### Layer 2 — All Things Agentic (ADK + Comfy as a tool)
**Constraint:** must use **Gemini 3.5+** (satisfied by the ADK agent) + GCP.
**Does NOT forbid** other models — Comfy is fine here as a *supporting-generation* tool.

**Architecture:** the ADK agent (Gemini 3.5, Firestore memory, Cloud Run) has the core
tools **plus** Comfy Cloud MCP tools. When `generate_notes` is done and the human asks for
a teaser, the agent:
1. `search_templates` → finds a Wan 2.2 video template.
2. `upload_file` → uploads the episode keyframe / character sheet.
3. `run_template` with overrides (prompt derived from the show-notes + character canon).
4. `wait_for_job` → `get_output` → downloads → stores in Cloud Storage → returns URL.

**ADK wiring (Python):**
```python
import os
from google.adk.tools import FunctionTool, MCPToolset, McpConnectionParams
from core.engine import load_series, check_consistency, generate_notes, update_glossary

# Core engine — first-class ADK tools
core_tools = [FunctionTool(load_series), FunctionTool(check_consistency),
              FunctionTool(generate_notes), FunctionTool(update_glossary)]

# Comfy Cloud MCP — remote Streamable HTTP. Use API key (headless Cloud Run)
# OR OAuth (dev machine). Key from platform.comfy.org/profile/api-keys.
comfy_tools = MCPToolset(
    connection_params=McpConnectionParams(
        transport="streamable-http",
        url="https://cloud.comfy.org/mcp",
        headers={"X-API-Key": os.environ["COMFY_API_KEY"]},
    )
)

agent = LlmAgent(
    model="gemini-3.5-flash-002",
    name="continuity_agent",
    tools=[*core_tools, comfy_tools],   # agent sees both
    memory=FirestoreMemory("studio_memory"),
)
```

**Caveats:**
- Verify your ADK version supports `streamable-http` MCP transport (the Grafana guide at
  `github.com/google/adk-docs/.../grafana-cloud.md` shows ADK supports remote HTTP MCP —
  Streamable HTTP support tracks the ADK/SDK version). If it doesn't, fall back to a
  custom `FunctionTool` that uses the `mcp` Python SDK to call Comfy Cloud and wraps the
  result — same effect, no ADK-transit dependency.
- Cloud Run is a headless environment → use **API key** auth (`X-API-Key` header), not
  OAuth. Store the key in **Secret Manager**, not env vars in code.

### Layer 3 — Agentic Cinema (the hard case)
**Constraint (verified, strict):** *"Projects may only use Google Cloud artificial
intelligence tools... and the built-in AI-powered features of the specific Partner's
product... No other AI models, agent frameworks, or AI APIs are permitted, regardless of
vendor."*

**Implication for Comfy:** Comfy's **own** video models (Wan, LTX, SD, Seedance) are NOT
Google — using them as the generation backend in a Cinema submission risks disqualification
for using a non-Google AI model. **Exception:** `partner_generate` lists **Gemini** as a
partner model — generating with `partner_generate` using Gemini is a Google model, so it
is compliant.

| Comfy capability | Cinema-compliant? | Why / how |
|---|---|---|
| `run_template` (Wan 2.2 / LTX video) | ❌ | Non-Google model |
| `partner_generate` with **Gemini** | ✅ | Google model, via Comfy's partner integration |
| `search_templates` / `search_nodes` (discovery) | ✅ | No model execution |
| `save_workflow` / `share_workflow` (reproducibility) | ✅ | No model execution |

**Recommendation:** Use Comfy in Cinema **only** for:
- Discovery + reproducibility tooling (`search_templates`, `save_workflow`,
  `share_workflow`, `get_workflow_canvas_url`) — all free, no AI.
- Asset **serving/retrieval** (the 5 free runs consumed on Layer 1 or 2, not in the Cinema
  submission).
- If you want *generation* in Cinema, use `partner_generate` with **Gemini** explicitly.

The **compliance partner** for Cinema should remain **ClickHouse** (or Parallel), as
documented in `03-considerations-and-checklists.md`. Comfy is a supporting utility, not
the partner. Do **not** list Comfy as your Cinema partner track.

### Layer 4 — micro1 sprint
If the released problem is creator/continuity tooling, Comfy is a legitimate asset
generator and your `share_workflow` + `get_workflow_canvas_url` outputs are strong
**reproducibility evidence** (a judge can rerun the exact workflow). If the problem is
unrelated, skip Comfy here and save the 5 free runs for the WebMCP/GAT demos.

## 4. The async orchestration pattern (where Comfy shines)

Comfy generations are **slow** (10s–min) and **async**. The studio's Pub/Sub worker (Layer 2)
or batch path is where this matters:

```
Human uploads ep4 transcript  ──►  Cloud Storage
                                       │ (finalize) Pub/Sub
                                       ▼
                          Cloud Run worker
                                       │
                    check_consistency(ep4)  ──► Firestore (findings)
                    generate_notes(ep4)     ──► Firestore (notes) + GCS (asset URL)
                    if needs_teaser:          # optional, batched
                      search_templates("Wan 2.2 video")
                      upload_file(keyframe)
                      run_template(prompt=notes.headline, ...)
                      wait_for_job
                      get_output  ──► download ──► Cloud Storage
                      save_workflow               # reproducibility artifact
                      share_workflow  ──► ?share=id URL (re-runnable proof)
                                       │
                                       ▼
                      Notify human (email/PubSub) with share URL
```

**Batch mode** (`submit_batch`) is the killer feature for series creators: queue teasers
for ep1→epN in one call, poll `wait_for_batch`, download all outputs together.

## 5. Known limitations that affect the studio (verified)

- **Shell download step:** `get_output` returns a **temporary signed URL** + a `curl`
  command. The agent/user must run that verbatim in a shell — you cannot just return the
  raw URL to a browser and expect it to work (signatures expire, headers break on
  re-encode). For the WebMCP layer, the agent runs the curl in its own shell then calls
  `set_episode_asset`. For ADK/Cloud Run, wrap this in your tool so the curl runs server-side
  and you re-host the file on Cloud Storage before returning a permanent URL.
- **No browser client for MCP:** `claude.ai` (web) and ChatGPT web accept **remote
  connectors only**. The local `comfy-mcp` (stdio) connection needs a client that can
  spawn a subprocess — so Claude Code, Cursor, Codex, Claude Desktop. Plan your WebMCP
  demo agent accordingly.
- **Upload size limits** may apply depending on the MCP client.
- **Workflow-building depends on agent accuracy** — complex multi-node graphs may need a
  retry; keep your video prompt templates simple and use `search_templates` to start from
  a known-good template rather than building graphs from scratch.
- **Assets from `submit_workflow` may not embed workflow metadata** (won't reopen in
  ComfyUI canvas) — prefer `run_template` / `run_saved_workflow` for clean reproducibility.

## 6. Quick start commands

```bash
# 1. Comfy account + 5 free runs
open https://cloud.comfy.org   # sign up → get 5 free runs

# 2A. Claude Code (OAuth, interactive demo)
/plugin marketplace add Comfy-Org/comfy-skills
/plugin install comfy-cloud@comfy-skills
/mcp  →  comfy-cloud → Authenticate

# 2B. Cursor / headless (API key)
#   config: curl -H "X-API-Key: $COMFY_API_KEY" https://cloud.comfy.org/mcp
comfy_api_key=$(curl -s https://platform.comfy.org/profile/api-keys ...)  # get key

# 3. Verify in agent
# ask: "search_templates for 'Wan 2.2 video'"  → should return templates
#        "get_billing_status"                  → should show 5 free runs
```

**Cost:** discovery = free; your 5 free runs cover the demo video generations. After that,
Comfy Cloud subscriptions start low (~$5–10/mo for hobby GPUs). Total hackathon spend on
Comfy = $0 if you stay within the 5 free runs.

---

## 7. Resolving the conflict: "no Google stack for video" → Veo on Vertex AI

You said: *"we must use Google stack and not Comfy, but no Google stack for video, so it's best
we use Comfy for video generation."* **This conflict is resolvable on both fronts.**

### 7a. There IS a Google-native video stack: Veo on Vertex AI (verified)

Google's video model is **Veo** (Veo 3.1, GA on Vertex AI as of Aug 2026). It is a first-class
Google Cloud AI tool, callable via the **Vertex AI SDK / `google-cloud-aiplatform`** (the exact
packages the hackathons whitelist):

- Publisher endpoint: `projects/{project}/locations/{location}/publishers/google/models/veo-003`
- API method: `PredictionServiceClient.predict` with a `VideoGenerationModelInstance`
  (Google's own docs reference this exact name).
- Via Gemini API: `model: "veo-3.0-generate-preview"` (for prototyping). Available in `us-central1`.
- Capabilities (Aug 2026): 4/6/8-second videos, 9:16 aspect ratio, reference-image-to-video,
  1080p→4K upscaling, native audio.
- Quota (Vertex AI, per project): 5 RPM, 3 concurrent ops, 60 min/day. Pricing ~`0.25–0.35/sec`.
  The standard GCP **$300 free trial** (or $150–$100 hackathon credits) absorbs several demo videos.

=> Use **Veo directly on Vertex AI** for any Cinema or All Things submission that needs Google
video. No Comfy involved → no vendor question.

### 7b. Comfy Cloud ALSO routes video through Google's Veo as a partner model

Comfy's partner catalog explicitly lists **Veo and Gemini** as partner-API nodes (verified in
`comfy-skills` generate-video routing + `comfy-mcp` README). The agent flow is:

1. `search_templates(tag="API", type="video")` or `search_nodes("Veo")` → finds the Google Veo
   partner node / a Veo-tagged template.
2. `partner_generate` with `type="video"` + the Google model slug → runs **Google's Veo** on
   Comfy's GPU partner infra, spends Comfy credits (your 5 free runs).
3. `wait_for_job` + `get_output` → download.

So **Comfy is the orchestrator; Veo (Google) is the model.** This is the key reconciliation:
you can use Comfy's batch/scheduling/template orchestration AND keep the AI itself on Google.

### 7c. Where to spend your 5 free Comfy runs (recommendation)

| Layer | Video model via Comfy | Google-compliant? | Recommendation |
|---|---|---|---|
| **WebMCP Challenge** (Sep 3) | OSS (Wan 2.2 / LTX) OR `partner_generate` with **Veo/Gemini** | ✅ no vendor restriction anyway | ✅ Use all 5 free runs here — best home |
| **All Things Agentic** (Aug 31) | `partner_generate` with **Veo** (Google) | ✅ (requires Gemini in stack; Veo is Google) | ✅ Use a free run to prove Google video via Comfy orchestration |
| **Agentic Cinema** (Sep 9) | `partner_generate` with **Veo** (Google) — *arguable* OR Veo directly on Vertex AI | ⚠️ gray (Comfy is a 3rd-party framework) | ❗ Prefer **Veo-on-Vertex AI** directly; use Comfy only for non-AI orchestration (templates/search/share) |
| **micro1** (Aug 31) | whatever fits the problem | — | Use if the problem involves media generation |

### 7d. Concrete agent move (ADK, GAT/Cinema-safe core)

```python
# core/video.py — framework-agnostic
def make_teaser_vid(prompt: str, series_id: str, model: str = "veo") -> str:
    """Generate a short teaser. model='veo' => Google Veo (Vertex); falls back to Comfy partner_generate."""
    if model == "veo":
        return _veo_vertex(prompt)          # google-cloud-aiplatform → 100% compliant
    else:
        return _comfy_partner_generate("video", provider="veo")  # Comfy orchestration of Google's Veo
```

**Bottom line:** Google video exists (Veo). Comfy can *orchestrate* Veo (Google) or OSS video.
Spend your 5 free Comfy runs on the **WebMCP demo** (no vendor limit) and on **GAT** (Comfy+Veo).
For **Cinema**, call **Veo directly on Vertex AI** to be unambiguously compliant, and use Comfy
only as a workflow/library layer (search/templates/share) that doesn't execute the AI.
