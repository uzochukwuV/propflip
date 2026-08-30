"""FastAPI routes mapped to the workflow stages (studio/05 §C).

Deterministic + runnable without GCP creds: scene generation/salvage use a
mocked scene_output so the continuity handoff (snap -> state update ->
envelope) is demoable end-to-end. Real LLM agents live in app/agents.py.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.continuity import ConsistencyEngine
from ..core.continuity_check import verify_script
from ..state.store import CharacterState, SceneScript, StateStore
from ..workflow import MockLLM, prepare_envelope, run_full, run_scene

router = APIRouter(prefix="/studio", tags=["studio"])
_STATE_DIR = os.environ.get("STUDIO_STATE_DIR", "/tmp/studio_state")


def get_store() -> StateStore:
    return StateStore(_STATE_DIR)


def get_engine(store: StateStore = Depends(get_store)) -> ConsistencyEngine:
    return ConsistencyEngine(store)


# ---- request bodies ----
class BibleIn(BaseModel):
    title: str = "Red Dust"
    logline: str = "Merchant crew on a Martian cargo run discover the cargo is alive."
    characters: list[dict[str, Any]] = Field(default_factory=lambda: [
        {"id": "kara", "arc": "freedom/trust", "wounds": "abandoned by crew"},
        {"id": "rex", "arc": "proof/faith", "wounds": "ex-military"},
    ])
    world_rules: list[str] = ["no FTL comms beyond 5AU", "oxygen 48h in breach"]
    tone_rules: list[str] = ["gritty noir", "claustrophobic", "dry humor under stress"]
    style_bible: dict[str, Any] = Field(default_factory=lambda: {
        "palette": ["#4b2e2e", "#c08081", "#2a1a18"], "camera": ["tight", "handheld"]})


class ScriptIn(BaseModel):
    scene_id: str
    setting: str
    lighting: str
    seed: int
    characters: list[dict[str, Any]] = Field(default_factory=list)
    prev_frame_ref: str = ""
    camera: str = ""
    style: str = ""


@router.post("/bible")
def create_bible(b: BibleIn, store: StateStore = Depends(get_store)):
    store.seed_series({
        "series_id": "red_dust", "title": b.title, "logline": b.logline,
        "characters": b.characters, "world_rules": b.world_rules,
        "tone_rules": b.tone_rules,
        "style_bible": b.style_bible,
        "major_arcs": [],
        "open_loops": [{"id": "OL-01", "question": "who disabled the comms array?",
                        "introduced_in": "E1", "resolved": False}],
    })
    return {"ok": True, "seeded": b.title}


@router.get("/bible")
def read_bible(store: StateStore = Depends(get_store)):
    p = store.root / "bible.json"
    if not p.exists():
        raise HTTPException(404, "bible not seeded; POST /studio/bible")
    return {"bible": p.read_text()}


@router.get("/state/{character}")
def get_state(character: str, store: StateStore = Depends(get_store)):
    return asdict(store.load_character(character))


@router.post("/plan/{episode}")
def plan_episode(episode: str):
    """Deterministic episode outline (Planner stage). Reads seeded bible."""
    store = get_store()
    bible = _load_bible(store)
    beats = [
        {"beat": "Hook", "chars": ["kara", "rex"], "state_changes": ["kara.right_hand: blood"]},
        {"beat": "Rising 1", "chars": ["kara"], "state_changes": ["comlink: cracked"]},
        {"beat": "Midpoint", "chars": ["rex"], "state_changes": []},
        {"beat": "Climax", "chars": ["kara", "rex"], "state_changes": ["kara.right_hand: diminished"]},
        {"beat": "Resolution + hook", "chars": ["kara"], "state_changes": []},
    ]
    return {"episode": episode, "bible_title": bible["title"], "beats": beats}


def _load_bible(store: StateStore) -> dict[str, Any]:
    p = store.root / "bible.json"
    if not p.exists():
        raise HTTPException(404, "bible not seeded; POST /studio/bible")
    import json
    return json.loads(p.read_text())


@router.post("/script")
def write_script(s: ScriptIn, store: StateStore = Depends(get_store)):
    """Script Adapter stage: pull CURRENT character state, never invent visuals."""
    script = SceneScript(scene_id=s.scene_id, setting=s.setting, lighting=s.lighting,
                         seed=s.seed, characters=s.characters,
                         prev_frame_ref=s.prev_frame_ref, camera=s.camera, style=s.style)
    flag = ""
    for c in s.characters:
        st = store.load_character(c["name"])
        flag += f" | (CONTINUITY {c['name']}: {st.carry_clause()})"
    return {"scene": s.scene_id, "directive": script.render_directive() + flag}


@router.post("/generate-scene")
def generate_scene(s: ScriptIn, engine: ConsistencyEngine = Depends(get_engine)):
    """Scene Generator stage (mocked): returns a stubbed scene_output + envelope."""
    script = SceneScript(scene_id=s.scene_id, setting=s.setting, lighting=s.lighting,
                         seed=s.seed, characters=s.characters,
                         prev_frame_ref=s.prev_frame_ref, camera=s.camera, style=s.style)
    env = engine.build_envelope(script)
    return {"seed": s.seed,
            "prompt": env.prompt_overrides["prompt"],
            "reference_images": env.reference_images,
            "state_snapshot": env.state_snapshot}


@router.post("/run/scene")
def run_scene_cycle(engine: ConsistencyEngine = Depends(get_engine)):
    """Full snap-and-feed loop (studio/05 §C): salvage -> apply -> envelope."""
    store = engine.store
    scene_output = {
        "scene_id": "E2_S5",
        "frames": [{
            "character": "kara",
            "path": str(store.assets / "char_kara_base.png") or "",
            "size": (1024, 576),
        }],
    }
    # ensure the base asset exists for the mock frame path
    (store.assets / "char_kara_base.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assets = engine.salvage(scene_output)
    changed = engine.apply(assets)
    # build envelope that the NEXT scene would consume
    from app.state.store import SceneScript
    nxt = SceneScript(scene_id="E3_S1", setting="cargo bay", lighting="emergency orange",
                      seed=42,
                      characters=[{"name": "kara", "emotion": "grim focus",
                                   "action": "wipes right hand on sleeve"}],
                      prev_frame_ref=assets[-1].path if assets else "",
                      camera="medium close-up, push-in")
    env = engine.build_envelope(nxt)
    return {
        "salvaged_assets": [asdict(a) for a in assets],
        "updated_state": {k: asdict(v) for k, v in changed.items()},
        "next_envelope": asdict(env),
    }


@router.get("/envelope/{episode}/{scene}")
def get_envelope(episode: str, scene: str, store: StateStore = Depends(get_store)):
    script = SceneScript(
        scene_id=scene, setting="", lighting="", seed=0,
        characters=[], prev_frame_ref="", camera="", style="",
    )
    try:
        env = prepare_envelope(store, episode, script)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return asdict(env)


class RunFullIn(BaseModel):
    llm: str = "mock"


@router.post("/run/full")
def run_full_endpoint(
    episode: str, scene: str,
    body: RunFullIn | None = None,
    store: StateStore = Depends(get_store),
):
    llm = MockLLM()
    engine = ConsistencyEngine(store)
    script = SceneScript(
        scene_id=scene, setting="", lighting="", seed=0,
        characters=[], prev_frame_ref="", camera="", style="",
    )
    try:
        trace = run_full(store, episode, scene, llm=llm)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return trace


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "layer": "fastapi+adk"}
