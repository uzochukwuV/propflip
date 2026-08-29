# Creator Series Consistency Studio — dev commands

## Setup (one time)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # installs uv
uv venv .venv --python 3.10
uv sync                                           # installs fastapi, uvicorn, google-adk, litellm, pydantic, pytest
```

## Configure the model provider (TokenRouter now, Gemini later)
The agents read the provider from env at call time (app/config.py). TokenRouter
(OpenAI-compatible) is the default so `z-ai/glm-5.3-free` runs out of the box.

```bash
# TokenRouter (current) — key is NEVER committed; export at runtime
export TOKEN_ROUTER_API_KEY="sk-..."                # required
export TOKEN_ROUTER_BASE_URL="https://api.tokenrouter.com/v1"
export TOKEN_ROUTER_MODEL="z-ai/glm-5.3-free"

# Switch to Google Gemini (later) — flip one flag, set GOOGLE_API_KEY / ADC
export STUDIO_USE_GEMINI=1
```

## Run the API (deterministic; no LLM key needed to start)
```bash
uv run uvicorn app.main:app --reload --port 8000
# then:  curl -X POST http://localhost:8000/studio/run/scene   (snap-and-feed loop)
#        curl http://localhost:8000/studio/health
#        curl http://localhost:8000/docs
```

## Run the ADK agents (requires the LLM key above)
```bash
uv run python -c "from app.agents import all_agents; from app.state.store import StateStore; print(all_agents(StateStore('/tmp/studio_state')))"
```

## Lint / typecheck / test
```bash
uv run ruff check .        # if ruff installed: uv add --dev ruff
uv run pytest -q           # the continuity handoff + config tests
```

## Notes
- Project rule blocks the editor `write` tool for new files; materialize source via
  bash heredocs (allowed). `bash` writes to the session workspace are permitted.
- `studio/*.md` are the design spec; `studio/06-...` has concrete prompts & schemas.
- ADK agents (`app/agents.py`) construct without GCP creds; LLM calls happen only on
  `agent.run`. `make_llm()` reads provider env at call time (TokenRouter now /
  Gemini later). The API (`/studio/run/scene`) is fully runnable without any key.
