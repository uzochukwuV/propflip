# Considerations, Constraints & Submission Checklists

> Research-verified against official rules (Aug 29, 2026). These are the things
> that trip people up. Treat them as gates before you commit code.

## 1. micro1 — the hard constraint you must not ignore

**micro1 Frontier Engineering Challenge 2026** (Aug 28–31) is fundamentally different
from the other three:

- It is a **3-day problem-sprint**. The challenge statement is released at **kickoff
  (Aug 28, 15:00 UTC)** and deliberately withheld beforehand: *"expect to build at the
  frontier of agentic AI without details that would reveal the problem in advance."*
- You solve **micro1's problem**, not your own idea. Coding-agent use is **mandatory**;
  you must **disclose tools used** and **submit trajectories**.
- Evaluation = "correct, reproducible, testable, clearly explained." There is **no**
  baseline-vs-agent changelog, no "purposeful agents with memory/verification/skills"
  scoring — that's micro1's general eval framework, not this hackathon's rubric.

**Implication for the studio plan:**
The "Creator Series Consistency Studio" only maps to micro1 if the released problem
turns out to be about creator/content continuity. Check the problem at kickoff. If it
isn't, **do not force the studio onto micro1** — it will read as off-prompt.

What you SHOULD carry into micro1 regardless of the problem:
- Locked deps (`uv.lock`) + `Dockerfile` → single-command `docker build && docker run`.
- A `trajectories/` folder with captured coding-agent turns.
- `pytest` suite whose tests **fail if behavior is wrong** (edge cases, failure modes),
  not just happy paths.
- A write-up that **names each ambiguity, states the interpretation you chose, and
  justifies it** — micro1 explicitly rewards "stating a limitation honestly" as judgment.
- Disclose the coding agent(s) you used (Claude Code / Cursor / Codex etc.).

micro1 registration was extended to **Aug 29, 23:59 UTC** (verified on LinkedIn), so
you still have a narrow window — but you can't pre-build the answer.

## 2. Deadline stacking & build order

| Hack | Ends | Days from now (Aug 29) | Priority |
|---|---|---|---|
| All Things Agentic | Aug 31 17:00 PDT | ~2.3 | 🔴 CRITICAL |
| micro1 Frontier Eng. | Aug 31 18:00 UTC | ~2.5 | 🟠 Problem-dependent |
| WebMCP Challenge | Sep 3 13:00 PDT | ~5 | 🔴 CRITICAL |
| Agentic Cinema | Sep 9 14:00 PDT | ~11 | 🟡 Build after L2/L3 |

**Recommended sequence** (matches the architecture doc):
1. Core engine + pytest suite (reusable everywhere). — **start now**
2. ADK agent (Gemini 3.5 + Firestore + Cloud Run) → All Things submission. — **L2 first**
3. WebMCP React app (`document.modelContext.registerTool` + Pyodide/FastAPI) → WebMCP submission. — **parallel**
4. ClickHouse `mcp-clickhouse` MCPToolset wiring + Grafana observability → Cinema submission. — **after L2/L3**

micro1 sits in parallel; slot the core + reproducibility tooling into whatever problem
drops at kickoff.

## 3. The two WebMCP ecosystems (don't mix them up)

| | Native Chrome `document.modelContext` | `@jason.today/webmcp` (npm) |
|---|---|---|
| Spec | webmachinelearning/webmcp (W3C-style) | OpenAI-provided bridge |
| API | `document.modelContext.registerTool({name,desc,inputSchema,execute})` | `mcp.registerTool(name, desc, schema, execute)` |
| Judge client | ChatGPT in-app browser / Chrome 149+ `chrome://flags/#enable-webmcp-testing` | same browsers, via MCP bridge |
| Which the rules reference | ✅ the example `document.modelContext.registerTool(...)` in the Official Rules | ❌ not the format shown in the rules |
| Recommendation | **Target this** for the WebMCP Challenge | Avoid — solves a different problem |

If you want belt-and-suspenders, ship the `document.modelContext` API as primary and
fall back to a small polyfill (`webmcp-polyfill.js`, used by Google's own demos) so
judges in non-flagged browsers still see the tools. The polyfill does NOT satisfy the
challenge alone — real WebMCP clients must see the native registrations.

## 4. Per-hackathon submission checklists

### WebMCP Challenge (Sep 3)
- [ ] Live URL reachable in ChatGPT in-app browser **and** Chrome 149+ (`chrome://flags/#enable-webmcp-testing`)
- [ ] App sets `Origin-Agent-Cluster: ?1` (origin isolation) — else tools won't register
- [ ] Uses `document.modelContext.registerTool(...)` (native API), ≥1 non-trivial tool
- [ ] Public GitHub repo + **open-source license visible in repo "About" section**
- [ ] `<3-min` YouTube video (audio) showing the project + human/agent collaboration
- [ ] Text description: why WebMCP fit, how it's better together, how WebMCP was implemented

### All Things Agentic (Aug 31)
- [ ] Uses **Gemini 3.5+ via Vertex AI or Gemini API** (`google-cloud-aiplatform` or `google-genai`)
- [ ] Uses **one Google agent framework** (ADK / GenAI SDK / Antigravity / GenKit)
- [ ] Uses **one GCP service** (Cloud Run, Firestore, Pub/Sub, Cloud SQL, GKE…)
- [ ] Picks ONE track (Collaborative Partner recommended for the studio)
- [ ] Public or private repo (private → grant `testing@devpost.com` + `cloudhackathons@google.com`)
- [ ] Spin-up README (local or cloud, single-command)
- [ ] Architecture diagram (Gemini ↔ backend ↔ DB ↔ frontend)
- [ ] ≤4-min demo video showing backend on GCP (Cloud Run dashboard, Vertex AI logs, `.run.app` URL)

### Agentic Cinema (Sep 9)
- [ ] Uses **Gemini + Google Cloud Agent Builder** (`google-adk`, `google-genai`,
  `google-cloud-aiplatform` — legacy libs count too)
- [ ] **Integrates ONE partner at runtime in code** (not README):
  - ClickHouse → `mcp-clickhouse` as ADK `MCPToolset` (recommended)
  - Parallel → `parallel-web` SDK `@parallel_web/parallel` / `ParallelWebSearchTool`
  - Grafana → hosted `mcp-grafana` MCP server via ADK MCPToolset
  - IBM → IBM Bob used in the dev/build process + Confluent optional
  - Replit → built with Replit Agent + hosted on replit.app/replit.dev
- [ ] **No non-Google AI** — no Anthropic/OpenAI/Claude models anywhere in the AI path
  (hosting, DBs, non-AI libs are fine)
- [ ] **Public repo** + open-source license at top of repo page
- [ ] Hosted project URL
- [ ] ~3-min demo video (YouTube/Vimeo, English or subtitled)
- [ ] Selects partner track on Devpost

### micro1 (Aug 31)
- [ ] Coding agents used (disclose tool names)
- [ ] Trajectories submitted (`trajectories/` folder)
- [ ] Solution is **correct / reproducible / testable / clearly explained**
- [ ] `Dockerfile` + lockfile + single-command setup (reproducibility gate)
- [ ] Tests cover failure modes (not just happy paths)
- [ ] Write-up logs each ambiguity + your chosen interpretation + justification

## 5. Cross-cutting constraints

**No mixed AI vendors for GAT & Cinema.** Both forbid non-Google AI in the agent/AI
path. The studio's core engine can use open-source/local models for NER/embedding
(`sentence-transformers`, `gpt-4all`, spaCy small) — those are not "AI APIs," just libs.
If you use Gemini for the LLM tier, route **all** of it through Vertex AI / Google only.

**Reproducibility is scored everywhere** — micro1 (locked env), WebMCP (repo must run),
GAT (spin-up README), Cinema (repo must run). Use `uv` + `uv.lock` + `Dockerfile`
consistently across all layers.

**Origin isolation (WebMCP) vs GCP (GAT/Cinema):** don't run the WebMCP SPA on Cloud Run
with a conflicting `Origin-Agent-Cluster`. Host the WebMCP app on Vercel/Cloudflare
free tier (no GCP needed) and point the GCP layer at separate services.

**Cost discipline:** total free credits available ≈ $150 (GCP) + $100 (GCP Cinema) +
$400 (ClickHouse) + $100 (Grafana) + Vercel/Netlify free = enough for $0 demos. The one
trap is **ClickHouse `mcp-clickhouse` as a stdio subprocess on Cloud Run** — make it
HTTP transport with a token, or run ClickHouse locally in the same container for the
demo. For a hackathon demo, local-process ClickHouse (Docker) + the agent calling it
in the same Cloud Run container is simplest and cheapest.

## 6. Partner-selection decision tree (for Cinema)

```
Does your continuity agent benefit most from...
  ├─ storing/querying metrics & episode analytics?  → ClickHouse (cleanest)
  ├─ researching/fact-checking real-world references across episodes?  → Parallel
  ├─ observing/monitoring the agent's own tool calls?  → Grafana MCP (use as 2nd,
  │   not the compliance partner, unless you frame it as "observability is the product")
  ├─ building with an AI coding assistant?  → IBM Bob (dev-process requirement)
  └─ simplest possible hosting?  → Replit (must deploy on replit.app)
```

**Recommended for this studio:** ClickHouse (Layer 3 default) — the consistency engine
naturally emits episode-level `Metric` rows, and `mcp-clickhouse` lets the agent query
them at runtime ("which episodes have the worst name drift?"). Add Grafana as the
observability bonus so the demo shows agent traces + cost dashboards.

If you pick Parallel instead, wire `@parallel_web/parallel` to fact-check claims the
LLM tier flags as "uncertain" — also a strong story, and Parallel credits are automatic
on signup.

## 7. What "improvement story" to keep identical across submissions

To make the baseline-vs-agent evidence transfer across WebMCP / GAT / Cinema (and
micro1 if it fits), fix **one evaluation dataset** and **one metric**:

- **Dataset:** a small synthetic 4-episode series with planted continuity bugs
  (misspelled character name in ep 2, contradictory fact in ep 3, missing callback in
  ep 4, tone drift in ep 3 narration).
- **Baseline:** one-shot prompt to Gemini 3.5 ("generate show notes for ep 4") with
  no memory — count how many of the 4 bugs it misses.
- **Agent:** memory-backed studio run — count how many it catches + fixes.
- **Metric:** `continuity_accuracy = (bugs_caught + corrections_made) / 4`.
- **Artifacts:** `evals/report.json`, `changelog.md` (baseline → agent, with evidence),
  `trajectories/` (turn logs).

This single eval drives the "measurable improvement" narrative for every applicable
submission and gives judges a concrete number.
