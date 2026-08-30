"""Tests for StateStore persistence and listing."""
from pathlib import Path

from app.state.store import StateStore


def test_seed_series_creates_files(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.seed_series({
        "series_id": "red_dust", "title": "Red Dust",
        "characters": [{"id": "kara"}, {"id": "rex"}],
        "world_rules": ["no FTL comms beyond 5AU"],
        "tone_rules": ["gritty noir"],
        "open_loops": [], "major_arcs": [],
    })
    assert (tmp_path / "state" / "bible.json").exists()
    assert (tmp_path / "state" / "character_state" / "kara.json").exists()
    assert (tmp_path / "state" / "assets" / "char_kara_base.png").exists()


def test_load_character_default(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    st = store.load_character("unknown")
    assert st.name == "unknown"
    assert st.injuries == {}


def test_latest_assets_empty(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    assert store.latest_assets("kara") == []


def test_record_scene_and_timeline(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.seed_series({"characters": [{"id": "kara"}]})
    store.record_scene("S1", {"frames": []}, [])
    assert (tmp_path / "state" / "scenes" / "S1.json").exists()
    store.append_injury(character="kara", when="S1", detail="blood", kind="wound",
                        status="active")
    tl = tmp_path / "state" / "scenes" / "timeline.jsonl"
    assert tl.exists()
    lines = tl.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    rec = json.loads(lines[0])
    assert rec["character"] == "kara"
