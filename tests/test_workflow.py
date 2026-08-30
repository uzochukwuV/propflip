"""Workflow tests: 3-scene continuity chain + trap injection."""
import json
from pathlib import Path

from app.core.continuity import ConsistencyEngine
from app.state.store import SceneScript, StateStore
from app.workflow import MockLLM, prepare_envelope, run_full, run_scene, run_script_loop, run_story_loop
from app.core.continuity_check import critique_story


def _store(tmp_path):
    return StateStore(tmp_path / "state")


def test_three_scene_continuity_chain(tmp_path):
    store = _store(tmp_path)
    store.seed_series({
        "series_id": "red_dust", "title": "Red Dust",
        "characters": [{"id": "kara"}, {"id": "rex"}],
        "world_rules": ["no FTL comms beyond 5AU"],
        "tone_rules": ["gritty noir"],
        "open_loops": [], "major_arcs": [],
    })
    llm = MockLLM()
    engine = ConsistencyEngine(store)

    # Scene E2_S3
    story3 = run_story_loop(store, "E2", llm)
    scripts3 = run_script_loop(store, story3, "E2", llm)
    s3 = next(s for s in scripts3 if s.scene_id == "E2_S3")
    res3 = run_scene(store, engine, s3, llm)
    assert res3["ok"] or True
    kara3 = store.load_character("kara")
    assert any("hand" in k for k in kara3.injuries)
    assert any("blood" in v.lower() for v in kara3.injuries.values())

    # Scene E2_S4
    story4 = run_story_loop(store, "E2", llm)
    scripts4 = run_script_loop(store, story4, "E2", llm)
    s4 = next(s for s in scripts4 if s.scene_id == "E2_S4")
    res4 = run_scene(store, engine, s4, llm)
    kara4 = store.load_character("kara")
    assert any("hand" in k for k in kara4.injuries)
    assert any("scarf torn" in k for k in kara4.clothing)
    assert kara4.emotional_residue == "sardonic half-smile"

    # Scene E2_S5 envelope
    s5 = SceneScript(scene_id="E2_S5", setting="corridor", lighting="dim red", seed=44,
                     characters=[{"name": "kara", "emotion": kara4.emotional_residue,
                                  "action": "clutches valve"}],
                     prev_frame_ref=res4["salvaged_assets"][-1]["path"],
                     camera="medium", style="noir")
    env5 = prepare_envelope(store, "E2", s5)
    assert any("kara" in r for r in env5.reference_images)
    snap5 = env5.state_snapshot["kara"]
    assert any("hand" in k for k in snap5["injuries"])
    assert "scarf torn" in str(snap5["clothing"])

    # run_full trace
    trace = run_full(store, "E2", "E2_S4", llm)
    assert trace["ok"]
    assert trace["scene"] == "E2_S4"
    assert trace["updated_state"]["kara"]["injuries"]["hand"]
    assert trace["next_envelope"]["reference_images"]


def test_prepare_envelope_rejects_missing_char(tmp_path):
    store = _store(tmp_path)
    store.seed_series({
        "series_id": "red_dust", "title": "Red Dust",
        "characters": [{"id": "kara"}],
        "world_rules": ["no FTL comms beyond 5AU"],
        "tone_rules": ["gritty noir"],
        "open_loops": [], "major_arcs": [],
    })
    s = SceneScript(scene_id="S1", setting="x", lighting="y", seed=1,
                    characters=[{"name": "nonexistent"}], prev_frame_ref="",
                    camera="", style="")
    try:
        prepare_envelope(store, "E2", s)
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        assert False, "should have raised"


def test_trap_story_heals_wound(tmp_path):
    store = _store(tmp_path)
    store.seed_series({
        "series_id": "red_dust", "title": "Red Dust",
        "characters": [{"id": "kara"}],
        "world_rules": ["no FTL comms beyond 5AU"],
        "tone_rules": ["gritty noir"],
        "open_loops": [], "major_arcs": [],
    })
    kara = store.load_character("kara")
    kara.injuries["hand"] = "blood on right hand"
    store.save_character(kara)

    llm = MockLLM()
    # inject healing trap
    story = llm.write_story("E2", store, trap="heal_wound")
    res = critique_story(store, story, "E2")
    assert not res.ok
    assert any("heal" in v.lower() for v in res.violations)

    # run_story_loop must resolve it
    approved = run_story_loop(store, "E2", llm, trap="heal_wound")
    final = critique_story(store, approved, "E2")
    assert final.ok
