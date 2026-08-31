# Creator Series Consistency Studio — Build Plan (Local First)

> Goal: full end-to-end workflow for a video series runs locally with TokenRouter LLM
> and mocked video generation. Cloud services (Firestore, Cloud Run, ClickHouse) are
> explicitly deferred until local is green.

## TokenRouter Config (already wired in `app/config.py`)

```bash
export TOKEN_ROUTER_API_KEY="sk-qoEDCqdBz4PIXGJruX3Io4BNjLcpwyVTSPhC2INuZDaQv0zV"
export TOKEN_ROUTER_BASE_URL="https://api.tokenrouter.com/v1"
export TOKEN_ROUTER_MODEL="z-ai/glm-5.3-free"
export STUDIO_USE_GEMINI=0
```

---

## Phase 1 — Core Engine Completeness (blocking everything else)

- [ ] Add missing Pydantic / dataclass models:
  - `Location` (canonical, variants, visual_ref, description)
  - `Fact` (claim, source_scene, confidence)
  - `ConsistencyFinding` (type, target, severity, excerpt, suggestion, evidence_ref)
  - `GeneratedAsset` (key, kind, ref, workflow_id, version)
  - `Metric` (series_id, episode_id, scene_id, score, breakdown, ts)
  - `Series` top-level aggregate
- [ ] Add `rapidfuzz` to `pyproject.toml` dependencies
- [ ] Implement `name_variant_check` and `callback_coverage` in `app/core/continuity_check.py`
- [ ] Implement `Metric` persistence in `StateStore` (JSON files under `metrics/`)
- [ ] Fix `pyproject.toml` entry point:
  - current: `studio = "studio:main"` (points to non-existent `src/studio/__init__.py` stub)
  - change to: `studio = "app.main:app"` (the FastAPI app is the real entry)
- [ ] Fix `scripts/bootstrap.sh` and `scripts/build_and_test.sh` hardcoded session paths
  - use `$(pwd)` or script-relative path instead of absolute session ID

## Phase 2 — Real LLM Integration (replace MockLLM for local runs)

- [ ] Add `app/llm.py` with a `RealLLM` class that calls TokenRouter via `LiteLlm`
  - re-use `make_llm()` from `app/config.py`
  - methods: `write_story`, `adapt_script`, `generate_scene`, `salvage_vision`
- [ ] Add `app/media_backend.py` with a `MockMediaBackend`:
  - returns deterministic stubbed scene outputs (frame paths, salvage_hints)
  - no real video API calls; writes placeholder PNG assets
- [ ] Add CLI flag / env switch in workflow to use `RealLLM` + `MockMediaBackend`:
  - `STUDIO_LLM=real` → TokenRouter
  - `STUDIO_MEDIA=mock` (default) → stubbed video
- [ ] Verify `uv run uvicorn app.main:app --reload` starts and agents construct without GCP creds

## Phase 3 — Full Local Workflow (story → script → scene → continuity → assets)

- [ ] Extend `app/workflow.py`:
  - `run_full` currently seeds series internally; make it accept `SeriesBible` input
  - add `generate_notes` and `generate_thumbnail` stubs (markdown + image placeholder)
  - add `run_eval` skeleton: baseline vs agent, continuity_accuracy metric
- [ ] Add FastAPI endpoint `POST /studio/run/eval` that runs baseline-vs-agent eval
- [ ] Add FastAPI endpoint `POST /studio/assets/teaser` and `/studio/assets/thumbnail`
- [ ] Wire the 8 ADK agents in `app/agents.py` to actually call the real LLM when `STUDIO_LLM=real`
  - currently they build but don't run; ensure `agent.run()` works end-to-end
- [ ] Add `/studio/run/scene` documented smoke path (already exists, verify it works)

## Phase 4 — Testing (must pass before touching cloud)

- [ ] Unit tests:
  - `tests/test_models.py` — instantiate every new dataclass / Pydantic model
  - `tests/test_continuity_check.py` — extend with name-variant + callback tests
  - `tests/test_store.py` — Metric persistence, asset listing, timeline append
- [ ] Integration tests:
  - `tests/test_workflow_real_llm.py` — run_full with RealLLM + MockMediaBackend
    - asserts: story approved, script approved, scene verified, next envelope has refs
  - `tests/test_api_smoke.py` — TestClient calls to every `/studio/*` route
- [ ] Hard-case / trap tests (per micro1 rubric):
  - healing wound without scene basis → story loop must fix
  - script invents clothing → script loop must fix
  - missing character state card → envelope returns 422
- [ ] Run:
  ```bash
  uv run ruff check .
  uv run pytest -q
  ```

## Phase 5 — Reproducibility & Docs (micro1-ready, applies to all layers)

- [ ] Add `Dockerfile`:
  ```dockerfile
  FROM python:3.10-slim
  RUN pip install uv
  COPY . /app
  WORKDIR /app
  RUN uv sync
  CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- [ ] Add `tox.ini` for multi-env runs (micro1 requirement)
- [ ] Add `mypy.ini` / `pyproject.toml` `[tool.mypy]` section
- [ ] Add `REPRODUCTION.md`:
  - clone + `docker build` + `docker run` steps
  - expected curl commands + responses
- [ ] Update `README.md`:
  - setup with uv
  - TokenRouter env vars
  - run locally (`uvicorn`)
  - test commands
  - ambiguity log / known limitations (micro1 requirement)

## Phase 6 — Verification Gate (do not proceed to cloud until green)

```bash
# 1. install
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.10
uv sync

# 2. lint + typecheck
uv run ruff check .
uv run mypy app tests

# 3. tests
uv run pytest -q

# 4. smoke run
export TOKEN_ROUTER_API_KEY="sk-qoEDCqdBz4PIXGJruX3Io4BNjLcpwyVTSPhC2INuZDaQv0zV"
export TOKEN_ROUTER_BASE_URL="https://api.tokenrouter.com/v1"
export TOKEN_ROUTER_MODEL="z-ai/glm-5.3-free"
uv run uvicorn app.main:app --reload --port 8000
# in another shell:
curl -s http://localhost:8000/studio/health
curl -s -X POST http://localhost:8000/studio/bible -H 'content-type: application/json' -d '{"title":"Red Dust"}'
curl -s http://localhost:8000/studio/run/scene
```

## Out of Scope Until Local Is Green

- FirestoreStore backend (swap `StateStore` backend)
- Cloud Run deployment
- Pub/Sub worker
- WebMCP React frontend (`document.modelContext.registerTool`)
- Comfy Cloud MCP integration
- ClickHouse / mcp-clickhouse
- Grafana Cloud MCP
- Veo-on-Vertex AI video generation
