# Tools & Stacks (Why, Cost, Free Access)

> Status: researched & verified against each hackathon's official rules (Aug 29, 2026).
> Deadlines: micro1 **Aug 31**, All Things Agentic **Aug 31**, WebMCP **Sep 3**, Agentic Cinema **Sep 9**.

## 1. Core engine — Python (framework-agnostic)

**Why:** The consistency engine (glossary, checker, generators, eval harness) is
written once in pure Python and reused by all layers. It must be importable both
inside a browser (Pyodide/WASM) and by a Google ADK agent. Keeping it framework-agnostic
decouples the "brain" from each hackathon's mandatory orchestration layer.

**Stack:**
- `pydantic` — typed data model (Series / Entity / Episode / Finding)
- `rapidfuzz` — fuzzy name-variant matching across episodes
- `numpy` / `scikit-learn` — embedding sim for tone drift (optional; fallback to
  `sentence-transformers` if needed, but prefer small local model to avoid cost/tokens)
- `pytest` + `pytest-cov` — tests that **fail if wrong** (not happy-path only)
- `tox` — reproducible multi-env runs (required by micro1 "reproducible" rubric)

**Cost:** $0 (pure-Python wheels).

## 2. WebMCP layer (OpenAI WebMCP Challenge — due Sep 3)

**Why:** The challenge requires a live web page where a human and an agent
collaborate — the agent must call WebMCP tools that mutate the page state and vice-versa.

**Required API (verified, NOT the `@jason.today/webmcp` bridge lib):**
The OpenAI challenge + Chrome docs target the **native browser `document.modelContext`
imperative API** (Chrome 149+ origin trial). Registration is:

```js
await document.modelContext.registerTool({
  name, description, inputSchema, execute: async (input, { signal }) => {...}
});
```

- Origin isolation is mandatory. Enable locally via `chrome://flags/#enable-webmcp-testing`
  (Chrome 149+) or the origin trial (`4163014905550602241`).
- Judges test in **ChatGPT in-app browser** or **Chrome with the WebMCP flag**.
- Repo must be **public with an OS license** detectable in the About section.

**Stack:**
- Frontend: **React + Vite** (`.tsx`) — register tools on page load.
- Core-in-browser: **Pyodide** so the page is fully self-contained (no backend needed),
  OR a thin **FastAPI** backend on a free host that tools proxy to for heavier compute.
- Deploy host (free tier, all support the Chrome flag): **Vercel** (recommended — $30
  build credits + free Hobby) **or** **Cloudflare Pages** (free) **or** **Render**
  (free + $50 credits via hackathon form) **or** **Netlify** (free + 3000 credits).

**Cost:** $0 on free tiers. Vercel/Cloudflare free tiers are sufficient for a demo.

**Do NOT:** conflate with `@jason.today/webmcp` npm package (an OpenAI-provided MCP bridge
with a blue widget). The judges' supported client is the native `document.modelContext` API.

## 3. All Things Agentic layer (Google — due Aug 31)

**Why:** Mandatory stack = Gemini 3.5+ **AND** a Google agent framework **AND** a GCP service.

**Stack (minimum viable, cost-controlled):**
- **Gemini model:** `gemini-3.5-flash` via **Vertex AI** (preferred) or Gemini API.
  - Access: free trial at cloud.google.com/free, then request **$150 GCP credits** via the
    official form by Aug 28 @ 12:00pm PT (while supplies last).
  - `google-genai` SDK (accepted package per rules).
- **Agent framework:** **Google ADK (Python)** — `pip install "google-cloud-aiplatform[agent_engines,adk]>=1.100"`.
  ADK is the Google-recommended path and has first-class Firestore + MCP integration.
- **Cloud service:** **Cloud Run** (free tier: 2M req/mo, 180M vCPU-s) + **Firestore**
  (free tier: 50k reads/writes/d) for persistent series memory. This proves "runs on
  GCP" with a `.run.app` URL in your demo.
- **Async/event-driven (Taskmaster track):** **Cloud Pub/Sub** (free tier 10GB/mo) triggers
  a Cloud Run worker when a new episode is committed.
- **Background memory:** ADK `FirestoreMemory` or a custom Memory module backed by Firestore.

**Cost:** Near-$0 — Cloud Run always-free + Firestore free tier + $150 credits cover a
hackathon demo. Keep the deployed service small / sleep-capable.

## 4. Agentic Cinema layer (Google + ONE partner — due Sep 9)

**Why:** Mandatory = Gemini + Google Cloud Agent Builder **AND must call one partner at
runtime in code** (README mention = automatic fail). No non-Google AI allowed.

### Track recommendation: **ClickHouse** (cleanest for a continuity/analytics tool)

The consistency engine naturally produces **episode-level metrics** (consistency scores,
drift severity, callback coverage). ClickHouse stores and queries these.

**Stack:**
- **mcp-clickhouse** (official ClickHouse MCP server, `pip install mcp-clickhouse`).
  Connects to ClickHouse Cloud or self-hosted cluster. Supports stdio / HTTP / SSE
  transport.
- **Free credits:** new ClickHouse Cloud accounts get **$400 credits**
  (`promo=SIGNUP100`, verified on the resources page). The public **SQL Playground**
  (`sql-clickhouse.clickhouse.com`, user `demo`, no password) is usable for prototyping.
- **Wiring in ADK (satisfies "called at runtime in code"):**
  ```python
  from typing import Any
  from google.adk.tools import MCPToolset, McpToolPreprocessor
  from google.adk.agents import LlmAgent

  # mcp-clickhouse runs as an MCP server; ADK imports it as toolfunctions
  clickhouse_tools = MCPToolset(
      connection_params=McpConnectionParams(
          transport="stdio",
          command="mcp-clickhouse",  # real process, real calls
      )
  )
  ```
  The agent uses `sql`/`query` tools from `mcp-clickhouse` to read/write consistency
  analytics — e.g. `SELECT avg(score) FROM continuity_metrics GROUP BY series_id`.

### Alternative partner: Parallel (web research grounding)

If the problem values **grounding** over analytics:
- **parallel-web SDK** (Python/TS), `@parallel_web/parallel` package.
- Use the **Search API** at runtime to fact-check references/terms mentioned across
  episodes ("does this real-world claim hold across episodes X, Y, Z?").
- Free tier: $20–$80 credits on signup; add a card for $5/mo recurring.
- ADK wiring: `parallel_web.ParallelWebSearchTool` or native `ParallelWebSearchTool`
  (LangChain/LlamaIndex supported), exposed as an ADK tool function.

### Observability (Cinema): Grafana Cloud MCP (bonus, NOT the compliance partner)

Grafana's hosted MCP (`https://mcp.grafana.com/mcp`, OAuth 2.1, 1h token → 30d refresh)
exposes 60+ tools. ADK has built-in Grafana Cloud MCP integration
(`github.com/google/adk-docs/.../grafana-cloud.md`). Use it to **observe the agent itself**
(token cost, latency, MCP tool activity) — strengthens the demo, doesn't satisfy the
"must use a partner" rule on its own.
- **Cost:** Grafana free tier (metrics/logs/traces/alerts) + $100 credits via
  `forms.gle/XPe837tzogh8L5sX6` (Cinema credit form).

**Cost ceiling:** ClickHouse $400 credits + Grafana free tier + Cloud Run free → $0 demo.

## 5. micro1 layer (Frontier Eng. Challenge — due Aug 31)

**Constraint (verified):** This is a **3-day problem-sprint**, NOT "submit your own project."
The problem statement is released at kickoff (Aug 28 15:00 UTC) and withheld beforehand —
"nobody can pre-build." You must solve THE problem micro1 releases, using coding agents.

**Stack guidance (applies regardless of the problem):**
- **Reproducible env:** `uv` + `requirements.txt` / `uv.lock` pinned versions + `Dockerfile`.
  One-command setup (`docker build && docker run`).
- **Trajectories:** capture coding-agent turns (Claude Code / Cursor / Codex) to
  `trajectories/`. Required disclosure.
- **Lint/typecheck/test:** `ruff` + `mypy` + `pytest`. Tests must **fail if wrong**
  (cover failure modes, not just happy paths).
- **Docs:** README with environment setup, ambiguity→interpretation log, edge cases,
  known limitations.

**Cost:** $0 (local dev). Only build this once the real problem is known at kickoff.

## Cost summary (all tiers verified Aug 2026)

| Resource | Free offer | Hackathon credit | Notes |
|---|---|---|---|
| Google Cloud | $300 90-day free trial | **$150** credits (All Things form) + $100 (Cinema form) | Cloud Run, Firestore, Pub/Sub, Vertex AI |
| ClickHouse | — | **$400** credits (`SIGNUP100`) | Use public playground if no account |
| Grafana Cloud | Free tier (metrics/logs/traces) | **$100** (Cinema form) | MCP + AI Observability |
| Vercel | Hobby free | $30 credits (code OAIWEBMH-9E2F-MUT4) | WebMCP host |
| Cloudflare | Free Pages/Workers | — | WebMCP host alt |
| Render | Free web services | **$50** credits (form) | WebMCP host alt |
| Netlify | Free + 3000 credits | **$3000** credits (form) | WebMCP host alt |

**Bottom line:** The entire stack can run on free tiers + hackathon credits. Expect <$0 spend
for a demo across all four submissions.
