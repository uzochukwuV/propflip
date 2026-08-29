"""FastAPI routes mapped to the 8 workflow stages.

Deterministic + runnable without GCP creds: scene generation/salvage use a
mocked scene_output so the continuity handoff is end-to-end demonstrable.
Real LLM agents live in app/agents.py and can be wired in via /run/episode.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.continuity import ConsistencyEngine, ResourceEnvelope
from ..state.store import StateStore, CharacterState, SceneScript

router = APIRouter(prefix="/studio", tags=["studio"])

_STATE_DIR = os.environ.get("STUDIO_STATE_DIR", "/tmp/studio_state")


def get_store() -> StateStore:
    return StateStore(_STATE_DIR)


def get_engine(store: StateStore = Depends(get_store)) -> ConsistencyEngine:
    return ConsistencyEngine(store)


# ---- schemas ----
class BibleIn(BaseModel):
    title: str = "Red Dust"
    logline: str = "Merchant crew on a Martian cargo run discover the cargo is alive."
    characters: list[dict[str, str]] = Field(default_factory=lambda: [
        {"id": "kara", "want": "freedom", "need": "trust", "lie": "no one stays",
         "wounds": "abandoned by crew"},
        {"id": "rex", "want": "proof", "need": "faith", "lie": "trust is weakness",
         "wounds": "ex-military"},
    ])
    world_rules: list[str] = ["no FTL comms beyond 5AU", "oxygen 48h in breach"]
    tone_rules: list[str] = ["gritty noir", "claustrophobic", "dry humor under stress"]


@router.post("/bible")
def create_bible(b: BibleIn, store: StateStore = Depends(get_store)):
    bible = {
        "series_id": "red_dust", "title": b.title, "logline": b.logline,
        "characters": b.characters, "world_rules": b.world_rules,
        "tone_rules": b.tone_rules, "major_arcs": [],
        "open_loops": [{"id": "OL-01", "question": "who disabled the comms array?",
                        "introduced_in": "E1", "resolved": False}],
        "style_bible": {"palette": ["#4b2e2e", "#c08081", "#2a1a18"],
                        "camera": ["tight interiors", "handheld"], "dialogue": "tech-short"},
    }
    store.seed_series(bible)
    return {"ok": True, "bible": bible}


@router.get("/bible")
def read_bible(store: StateStore = Depends(get_store)):
    p = store.root / "bible.json"
    if not p.exists():
        raise HTTPException(404, "bible not seeded; POST /studio/bible")
    return {"bible": p.read_text()}


@router.get("/state/{character}")
def get_state(character: str, store: StateStore = Depends(get_store)):
    return store.load_character(character)


# ---- Stage: plan (deterministic from bible) ----
@router.post("/plan/{episode}")
def plan_episode(episode: str, engine: ConsistencyEngine = Depends(get_engine)):
    store = engine.store
    bible = _load_bible(store)
    beats = [
        {"beat": "Hook", "characters": ["kara", "rex"], "state_changes": ["kara.right_hand: blood"]},
        {"beat": "Rising 1", "characters": ["kara"], "state_changes": ["comlink: cracked screen"]},
        {"beat": "Midpoint", "characters": ["rex"], "state_changes": []},
        {"beat": "Climax", "characters": ["kara", "rex"], "state_changes": ["kara.right_hand: diminished"]},
        {"beat": "Resolution + hook", "characters": ["kara"], "state_changes": []},
    ]
    plan = {"episode": episode, "bible_title": bible["title"], "beats": beats,
            "open_loops_referenced": bible.get("open_loops", [])}
    return plan


# ---- Stage: script (reads current character state — no invention) ----
@router.post("/script")
def write_script(script: SceneScript, store: StateStore = Depends(get_store)):
    st = store.load_character(script.characters[0]["name"])
    continuity_flag = f"(CONTINUITY: {st.carry_clause()})"
    directive = script.render_directive() + " " + continuity_flag
    return {"scene": script.scene_id, "directive": directive,
            "char_state": st.carry_clause()}


# ---- Stage: run ONE handoff cycle (salvage -> apply -> envelope) ----
@router.post("/run/scene")
def run_scene_cycle(engine: ConsistencyEngine = Depends(get_engine)):
    """End-to-end demo of the snap-and-feed loop, no vision backend needed."""
    store = engine.store
    # scene N output (mocked frame carrying "kara" + blood on hand)
    scene_output = {
        "scene_id": "E2_S5",
        "frames": [{
            "character": "kara",
            "path": store.assets / "char_kara_base.png",
            "size": (1024, 576),
        }],
    }
    assets = engine.salvage(scene_output)
    changed = engine.apply(assets)
    # build the envelope that the NEXT scene generator would consume
    next_script = SceneScript(
        scene_id="E3_S1", setting="cargo bay", lighting="emergency orange",
        seed=42,
        characters=[{"name": "kara", "emotion": "grim focus",
                     "action": "wipes right hand on sleeve, inspects comlink"}],
        prev_frame_ref=assets[-1].path if assets else "",
        camera="medium close-up",
    )
    envelope = engine.build_envelope(next_script)
    return {
        "salvaged_assets": [a.__dict__ for a in assets],
        "updated_state": {k: v.carry_clause() for k, v in changed.items()},
        "next_envelope": envelope,
    }


@router.get("/envelope/{scene}")
def envelope(scene: str, script: SceneScript, engine: ConsistencyEngine = Depends(get_engine)):
    script.scene_id = scene
    return engine.build_envelope(script)


def _load_bible(store: StateStore) -> dict:
    p = store.root / "bible.json"
    if not p.exists():
        raise HTTPException(404, "bible not seeded")
    import json
    return json.loads(p.read_text())
