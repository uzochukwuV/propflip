"""Tests for new state models and persistence."""
from pathlib import Path

from app.state.store import (
    ConsistencyFinding,
    Fact,
    GeneratedAsset,
    Location,
    Metric,
    Series,
    StateStore,
)


def test_location_model():
    loc = Location(canonical="cargo bay", variants=["bay"], visual_ref="img.png",
                   description="A large cargo bay")
    assert loc.canonical == "cargo bay"


def test_fact_model():
    fact = Fact(claim="FTL comms fail beyond 5AU", source_scene="E1_S1", confidence=0.9)
    assert fact.confidence == 0.9


def test_consistency_finding_model():
    finding = ConsistencyFinding(
        type="appearance_drift", target="kara", severity="high",
        excerpt="hair color changed", suggestion="reuse ref image",
        evidence_ref="frame_001.png",
    )
    assert finding.type == "appearance_drift"


def test_generated_asset_model():
    asset = GeneratedAsset(key="k1", kind="video", ref="gcs://bucket/v.mp4",
                           workflow_id="w1", version="v1")
    assert asset.kind == "video"


def test_metric_model():
    metric = Metric(series_id="s1", episode_id="E1", scene_id="S1", score=0.85,
                    breakdown={"appearance": 0.9}, ts="2026-08-30T00:00:00+00:00")
    assert metric.score == 0.85


def test_series_model():
    series = Series(series_id="s1", name="Red Dust",
                    characters=[{"id": "kara"}],
                    tone_rules=["gritty noir"])
    assert series.name == "Red Dust"


def test_store_save_load_metric(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.seed_series({"characters": [{"id": "kara"}]})
    m = Metric(series_id="s1", episode_id="E1", scene_id="S1", score=0.9)
    store.save_metric(m)
    loaded = store.load_metric("s1", "E1", "S1")
    assert loaded is not None
    assert loaded.score == 0.9


def test_store_save_list_findings(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.seed_series({"characters": [{"id": "kara"}]})
    f = ConsistencyFinding(type="wound", target="kara", severity="med",
                           excerpt="blood missing", suggestion="keep blood",
                           evidence_ref="frame.png")
    store.save_finding(f)
    findings = store.list_findings("kara")
    assert len(findings) == 1
    assert findings[0].type == "wound"
