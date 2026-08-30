"""Shared state store — the single source of truth for series continuity.

Mirrors the schemas in studio/06 §A. Persisted as JSON files under a
``data_dir`` (Firestore swap-in is an alternate ``StoreBackend``). Every
agent and API route reads/writes through this store.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CharacterState:
    name: str
    visual_ref: str = ""
    lora_ref: str = ""
    clothing: dict[str, bool] = field(default_factory=dict)
    injuries: dict[str, str] = field(default_factory=dict)
    emotional_residue: str = ""
    pose_tendency: str = ""
    carried_props: list[str] = field(default_factory=list)
    last_seen_in: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def carry_clause(self) -> str:
        parts: list[str] = []
        if self.emotional_residue:
            parts.append(f"emotion carry-over: {self.emotional_residue}")
        if self.injuries:
            parts.append("injuries: " + ", ".join(f"{k}={v}" for k, v in self.injuries.items()))
        if self.clothing:
            parts.append("clothing: " + ", ".join(self.clothing))
        if self.carried_props:
            parts.append("props: " + ", ".join(self.carried_props))
        return " | ".join(parts)


@dataclass
class SalvagedAsset:
    scene_id: str
    character: str
    kind: str
    detail: str
    path: str
    confidence: float = 0.0
    region: list[int] | None = None


@dataclass
class SceneScript:
    scene_id: str
    setting: str
    lighting: str
    seed: int
    characters: list[dict[str, Any]] = field(default_factory=list)
    prev_frame_ref: str = ""
    camera: str = ""
    style: str = ""

    def render_directive(self) -> str:
        chars = [f"{c.get('name')} ({c.get('emotion','')}): {c.get('action','')}" for c in self.characters]
        carry = f" | CARRY {self.prev_frame_ref}" if self.prev_frame_ref else ""
        return (f"SCENE {self.scene_id} | SETTING: {self.setting} | LIGHTING: {self.lighting} "
                f"| CAMERA: {self.camera} | " + ", ".join(chars) + carry)


@dataclass
class TimelineEntry:
    character: str
    when: str
    wound: str
    status: str


class StateStore:
    """Filesystem-backed state store (swap Firestore behind the same methods)."""

    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir)
        self.chars = self.root / "character_state"
        self.scenes = self.root / "scenes"
        self.assets = self.root / "assets"
        for d in (self.chars, self.scenes, self.assets):
            d.mkdir(parents=True, exist_ok=True)

    # ---- characters ----
    def load_character(self, name: str) -> CharacterState:
        p = self.chars / f"{name}.json"
        if not p.exists():
            return CharacterState(name=name)
        return CharacterState(**json.loads(p.read_text()))

    def save_character(self, state: CharacterState) -> None:
        (self.chars / f"{state.name}.json").write_text(
            json.dumps(asdict(state), indent=2))

    # ---- assets ----
    def write_asset(self, scene_id: str, character: str, detail: str,
                    kind: str, region: list[int] | None,
                    confidence: float) -> str:
        safe = re_sub(f"{scene_id}_{character}_{detail}")
        fname = self.assets / f"{safe}.png"
        fname.write_bytes(b"\x89PNG\r\n\x1a\n")  # placeholder; real frame bytes come from Comfy/Veo
        return str(fname)

    def latest_assets(self, character: str, n: int = 3) -> list[str]:
        matches = sorted(self.assets.glob(f"*_{character}_*.png"),
                         key=lambda p: p.stat().st_mtime)
        return [str(p) for p in matches[-n:]]

    # ---- scenes / timeline ----
    def record_scene(self, scene_id: str, scene_output: dict[str, Any],
                     assets: list[SalvagedAsset]) -> None:
        rec = {
            "scene_id": scene_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_count": len(scene_output.get("frames", [])),
            "assets": [asdict(a) for a in assets],
        }
        (self.scenes / f"{scene_id}.json").write_text(json.dumps(rec, indent=2))

    def append_injury(self, entry: dict[str, Any] | None = None,
                      **kw: Any) -> None:
        tl = self.scenes / "timeline.jsonl"
        rec = entry or kw
        with tl.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    # ---- convenience seed ----
    def seed_series(self, bible: dict[str, Any]) -> None:
        (self.root / "bible.json").write_text(json.dumps(bible, indent=2))
        for c in bible.get("characters", []):
            st = CharacterState(name=c["id"])
            st.visual_ref = f"assets/char_{c['id']}_base.png"
            st.lora_ref = f"loras/{c['id']}_v1.safetensors"
            st.clothing = {"coveralls": True}
            self.save_character(st)
        for c in bible.get("characters", []):
            (self.assets / f"char_{c['id']}_base.png").write_bytes(b"\x89PNG\r\n\x1a\n")


def re_sub(s: str) -> str:
    import re as _re
    return _re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
