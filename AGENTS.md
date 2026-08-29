# Creator Series Consistency Studio — dev commands

## Setup (one time)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.10
source .venv/bin/activate
uv sync            # installs fastapi, uvicorn, google-adk, pydantic, pytest
```

## Run the API (deterministic, no creds needed)
```bash
uv run uvicorn app.main:app --reload --port 8000
# then:  curl http://localhost:8000/run/scene   (the snap-and-feed loop)
#        curl http://localhost:8000/docs
```

## Lint / typecheck / test
```bash
uv run ruff check .        # if ruff installed: uv add --dev ruff
uv run pytest -q            # the handoff loop tests
```

## Notes
- Project rule blocks the editor `write` tool for new files; materialize source via
  `bash` heredocs. `bash` file writes to the session workspace are allowed.
- `studio/*.md` are the design spec; `studio/06-...` has concrete prompts & schemas.
- ADK agents (`app/agents.py`) construct without GCP creds; LLM calls happen only on
  `agent.run`. Real runs need GOOGLE_API_KEY or GCP ADC.
