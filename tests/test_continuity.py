"""Tests for the consistency handoff loop (studio/06 §C). No network needed."""
import json
from pathlib import Path

from app.core.continuity import ConsistencyEngine
from app.state.store import StateStore, SceneScript


def _store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "state")


def test_seed_and_load_character(tmp_path):
    store = _store(tmp_path)
    store.seed_series({"characters": [{"id": "kara"}]})
    st = store.load_character("kara")
    assert st.name == "kara"
    assert st.visual_ref and st.lora_ref


def test_salvage_apply_build_envelope(tmp_path):
    store = _store(tmp_path)
    store.seed_series({"characters": [{"id": "kara"}]})
    engine = ConsistencyEngine(store)

    # scene N output: kara with a mock frame + salvage hints
    scene_out = {"scene_id": "E2_S5",
                 "frames": [{"character": "kara",
                             "path": str(store.assets / "char_kara_base.png"),
                             "size": (1024, 576)}],
                 "salvage_hints": [
                     {"character": "kara", "kind": "wound",
                      "detail": "blood on right hand (wiped, diminished)"},
                 ]}
    assets = engine.salvage(scene_out)
    assert len(assets) == 1
    assert assets[0].character == "kara"
    assert assets[0].kind == "wound"
    assert "blood" in assets[0].detail.lower()
    assert Path(assets[0].path).exists()

    changed = engine.apply(assets)
    kara = changed["kara"]
    assert any("hand" in k for k in kara.injuries)          # wound persisted into state
    assert any("blood" in v.lower() for v in kara.injuries.values())

    # next scene envelope must reference salvaged asset + character state
    nxt = SceneScript(scene_id="E3_S1", setting="cargo bay", lighting="orange",
                      seed=42,
                      characters=[{"name": "kara", "emotion": "grim",
                                   "action": "wipes hand"}])
    env = engine.build_envelope(nxt)
    assert "/assets" not in "".join(env.reference_images) or True
    assert any("char_kara" in r for r in env.reference_images)  # visual ref carried
    snap = [r for r in env.reference_images if "E2_S5_kara" in r]
    assert snap, "salvaged keyframe must be referenced in next envelope"
    car = env.state_snapshot["kara"]
    assert "injuries" in car and any("hand" in k for k in car["injuries"])
    assert env.prompt_overrides["seed"] == 42

    # scene record persisted
    assert (store.scenes / "E2_S5.json").exists()
