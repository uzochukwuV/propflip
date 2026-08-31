"""Workflow orchestrator: story -> script -> scene with MockLLM/RealLLM and revision loops."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.core.continuity import ConsistencyEngine, ResourceEnvelope
from app.core.continuity_check import critique_story, verify_script, verify_scene
from app.state.store import CharacterState, SceneScript, StateStore
from app.llm import RealLLM
from app.media_backend import MockMediaBackend


class MockLLM:
    """Deterministic, context-aware mock LLM."""

    def write_story(self, episode: str, store: StateStore, trap: str | None = None) -> str:
        base = (
            f"[{episode}]\n"
            "Kara's right hand still bleeds from the breach. Rex watches the airlock.\n"
            "They do not speak of who disabled the comms array.\n"
        )
        if trap:
            if trap == "heal_wound":
                return (
                    f"[{episode}]\n"
                    "Kara's right hand is healed now, the wound closed clean.\n"
                    "She smiles, untroubled.\n"
                )
        return base

    def adapt_script(self, story: str, store: StateStore, episode: str) -> list[dict[str, Any]]:
        kara = store.load_character("kara")
        rex = store.load_character("rex")
        assets = store.latest_assets("kara", 3)
        prev = assets[-1] if assets else ""
        return [
            {
                "scene_id": f"{episode}_S3",
                "setting": "corridor",
                "lighting": "dim red",
                "seed": 42,
                "characters": [
                    {"name": "kara", "emotion": kara.emotional_residue or "grim focus",
                     "action": "wipes blood from right hand"},
                ],
                "prev_frame_ref": prev,
                "camera": "medium close-up",
                "style": "gritty noir",
            },
            {
                "scene_id": f"{episode}_S4",
                "setting": "airlock",
                "lighting": "emergency orange",
                "seed": 43,
                "characters": [
                    {"name": "kara", "emotion": "sardonic half-smile",
                     "action": "grips valve, scarf torn"},
                    {"name": "rex", "emotion": "tense", "action": "monitors pressure"},
                ],
                "prev_frame_ref": "",
                "camera": "wide",
                "style": "gritty noir",
            },
        ]

    def generate_scene(self, scene_script: dict[str, Any], envelope: ResourceEnvelope,
                       store: StateStore) -> dict[str, Any]:
        sid = scene_script["scene_id"]
        chars = scene_script.get("characters", [])
        frames = []
        for c in chars:
            frames.append({
                "character": c["name"],
                "path": str(store.assets / f"char_{c['name']}_base.png"),
                "size": (1024, 576),
            })
        return {
            "scene_id": sid,
            "frames": frames,
            "salvage_hints": [
                {"character": "kara", "kind": "wound",
                 "detail": "blood on right hand (wiped, diminished)"},
                {"character": "kara", "kind": "costume_detail",
                 "detail": "scarf torn"},
                {"character": "kara", "kind": "expression",
                 "detail": "sardonic half-smile"},
            ],
        }


def _resolve_llm() -> MockLLM | RealLLM:
    if os.environ.get("STUDIO_LLM", "mock").lower() == "real":
        return RealLLM()
    return MockLLM()


def _resolve_media() -> MockMediaBackend:
    return MockMediaBackend()


def run_story_loop(store: StateStore, episode: str, llm: MockLLM | RealLLM | None = None,
                   trap: str | None = None) -> str:
    if llm is None:
        llm = _resolve_llm()
    max_rev = 3
    story = ""
    rev = 0
    for rev in range(max_rev):
        story = llm.write_story(episode, store, trap if rev == 0 else None)
        result = critique_story(store, story, episode)
        if result.ok:
            break
    else:
        story = llm.write_story(episode, store, None)
    stories_dir = store.root / "state" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / f"{episode}.json").write_text(json.dumps({
        "episode": episode, "status": "approved", "text": story,
        "revisions": rev + 1,
    }, indent=2))
    return story


def run_script_loop(store: StateStore, story: str, episode: str,
                    llm: MockLLM | RealLLM | None = None) -> list[SceneScript]:
    if llm is None:
        llm = _resolve_llm()
    max_rev = 2
    scripts: list[dict[str, Any]] = []
    rev = 0
    for rev in range(max_rev):
        scripts = llm.adapt_script(story, store, episode)
        result = verify_script(store, {"scenes": scripts})
        if result.ok:
            break
    else:
        scripts = llm.adapt_script(story, store, episode)
    out = [SceneScript(**s) for s in scripts]
    scripts_dir = store.root / "state" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / f"{episode}.json").write_text(json.dumps({
        "episode": episode, "status": "approved",
        "scripts": [asdict(s) for s in out],
    }, indent=2))
    return out


def run_scene(store: StateStore, engine: ConsistencyEngine, scene_script: SceneScript,
              llm: MockLLM | RealLLM | None = None, media: MockMediaBackend | None = None,
              vision: Any = None) -> dict[str, Any]:
    if llm is None:
        llm = _resolve_llm()
    if media is None:
        media = _resolve_media()
    script_dict = asdict(scene_script)
    envelope = engine.build_envelope(scene_script)
    max_tries = 2
    for attempt in range(max_tries):
        scene_out = llm.generate_scene(script_dict, envelope, store)
        assets = engine.salvage(scene_out)
        changed = engine.apply(assets)
        new_state = {k: asdict(v) for k, v in changed.items()}
        prev_assets = [a.path for a in assets]
        result = verify_scene(store, prev_assets, new_state)
        if result.ok or attempt == max_tries - 1:
            return {
                "scene_id": scene_script.scene_id,
                "salvaged_assets": [asdict(a) for a in assets],
                "updated_state": new_state,
                "verify": asdict(result),
                "iterations": attempt + 1,
                "ok": result.ok,
            }
    return {"scene_id": scene_script.scene_id, "ok": False}


def prepare_envelope(store: StateStore, episode: str,
                     scene_script: SceneScript) -> ResourceEnvelope:
    bible = _load_bible(store)
    for c in scene_script.characters:
        name = c["name"]
        st = store.load_character(name)
        if not st.visual_ref:
            raise ValueError(f"envelope incomplete: character {name} missing state card")
    engine = ConsistencyEngine(store)
    env = engine.build_envelope(scene_script)
    if not env.reference_images:
        raise ValueError("envelope incomplete: no reference images")
    return env


def generate_notes(store: StateStore, episode: str, llm: MockLLM | RealLLM | None = None) -> dict[str, Any]:
    if llm is None:
        llm = _resolve_llm()
    bible = _load_bible(store)
    prompt = (
        f"Generate show notes for episode '{episode}' of '{bible.get('title', 'Untitled')}'. "
        "Include: key events, continuity callbacks, and character state changes. "
        "Output markdown only."
    )
    notes = llm._call(prompt) if hasattr(llm, "_call") else str(llm)
    return {"episode": episode, "kind": "notes", "content": notes}


def generate_teaser(store: StateStore, episode: str, media: MockMediaBackend | None = None) -> dict[str, Any]:
    if media is None:
        media = _resolve_media()
    return media.generate_teaser(episode, store)


def generate_thumbnail(store: StateStore, scene_id: str, media: MockMediaBackend | None = None) -> dict[str, Any]:
    if media is None:
        media = _resolve_media()
    return media.generate_thumbnail(scene_id, store)


def run_eval(store: StateStore, episode: str, scene_id: str,
             llm: MockLLM | RealLLM | None = None) -> dict[str, Any]:
    if llm is None:
        llm = _resolve_llm()
    trace = run_full(store, episode, scene_id, llm)
    score = 1.0 if trace.get("ok") else 0.0
    for stage in trace.get("stage", {}).values():
        if isinstance(stage, dict) and not stage.get("ok", True):
            score -= 0.2
    score = max(0.0, min(1.0, score))
    metric = store.load_metric(store.root.name.split("/")[-1] if "/" in str(store.root) else "series",
                               episode, scene_id)
    if metric is None:
        from app.state.store import Metric, datetime, timezone
        metric = Metric(
            series_id="series",
            episode_id=episode,
            scene_id=scene_id,
            score=score,
            breakdown={"overall": score},
            ts=datetime.now(timezone.utc).isoformat(),
        )
        store.save_metric(metric)
    return {"continuity_accuracy": score, "trace": trace}


def run_full(store: StateStore, episode: str, scene_id: str,
             llm: MockLLM | RealLLM | None = None, vision: Any = None) -> dict[str, Any]:
    if llm is None:
        llm = _resolve_llm()
    trace: dict[str, Any] = {
        "episode": episode, "scene": scene_id,
        "stage": {}, "violations": [],
    }

    bible_path = store.root / "bible.json"
    if not bible_path.exists():
        store.seed_series({
            "series_id": "red_dust", "title": "Red Dust",
            "characters": [{"id": "kara"}, {"id": "rex"}],
            "world_rules": ["no FTL comms beyond 5AU"],
            "tone_rules": ["gritty noir"],
            "open_loops": [], "major_arcs": [],
        })

    story = run_story_loop(store, episode, llm)
    story_res = critique_story(store, story, episode)
    trace["stage"]["story"] = {
        "ok": story_res.ok, "violations": story_res.violations,
        "quality_score": story_res.quality_score,
    }
    trace["violations"].extend(story_res.violations)

    scripts = run_script_loop(store, story, episode, llm)
    script_res = verify_script(store, {"scenes": [asdict(s) for s in scripts]})
    trace["stage"]["script"] = {
        "ok": script_res.ok, "violations": script_res.violations,
        "quality_score": script_res.quality_score,
    }
    trace["violations"].extend(script_res.violations)

    target_script = next((s for s in scripts if s.scene_id == scene_id), scripts[-1])
    engine = ConsistencyEngine(store)
    try:
        envelope = prepare_envelope(store, episode, target_script)
    except ValueError as exc:
        raise ValueError(f"envelope incomplete: {exc}")

    scene_res = run_scene(store, engine, target_script, llm, vision=vision)
    trace["stage"]["scene"] = {
        "ok": scene_res.get("verify", {}).get("ok", True),
        "violations": scene_res.get("verify", {}).get("violations", []),
        "iterations": scene_res.get("iterations", 1),
    }
    trace["violations"].extend(scene_res.get("verify", {}).get("violations", []))
    trace["salvage_assets"] = scene_res.get("salvaged_assets", [])
    trace["updated_state"] = scene_res.get("updated_state", {})

    nxt = SceneScript(
        scene_id=f"{episode}_NX",
        setting=target_script.setting,
        lighting=target_script.lighting,
        seed=target_script.seed + 1,
        characters=target_script.characters,
        prev_frame_ref=scene_res.get("salvaged_assets", [{}])[-1].get("path", ""),
        camera=target_script.camera,
        style=target_script.style,
    )
    trace["next_envelope"] = asdict(engine.build_envelope(nxt))
    trace["ok"] = all(
        v.get("ok", True) for v in trace["stage"].values()
        if isinstance(v, dict)
    )
    return trace


def _load_bible(store: StateStore) -> dict[str, Any]:
    p = store.root / "bible.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())

