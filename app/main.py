from fastapi import FastAPI
from .api.routes import router
from .state.store import StateStore

app = FastAPI(
    title="Creator Series Consistency Studio",
    description="Agentic pipeline: story -> script -> scene generation -> "
                "visual-state handoff -> continuity verify. FastAPI + ADK.",
    version="0.1.0",
)
app.include_router(router)


@app.on_event("startup")
def _seed_demo() -> None:
    """Seed a default series so /states, /run/scene work without a separate call."""
    store = StateStore("/tmp/studio_state")
    if not (store.root / "bible.json").exists():
        store.seed_series({
            "series_id": "red_dust", "title": "Red Dust",
            "characters": [{"id": "kara"}, {"id": "rex"}],
            "world_rules": ["no FTL comms beyond 5AU"],
            "tone_rules": ["gritty noir"],
            "open_loops": [], "major_arcs": [],
        })


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "layer": "fastapi+adk"}


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "Creator Series Consistency Studio", "docs": "/docs",
            "routes": "/studio/...see /docs"}
