"""Scene-to-scene continuity: keyframe salvage + resource-envelope builder.

Implements the Level-2 handoff from studio/05-agentic-workflow.md:
after a scene renders, run a vision pass to extract wounds/expressions/
props/costume details, persist them into CharacterState, and build the
3-part resource envelope fed into the NEXT scene generation call.

Framework-agnostic. A VisionBackend is Callable[[bytes, str], str]
(image bytes, task_prompt -> raw model JSON). When None, a deterministic
mock is used so the loop runs end-to-end without a vision backend.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from ..state.store import CharacterState, SceneScript, StateStore, SalvagedAsset

VISION_TASK_PROMPT = (
    "You are a continuity extractor. From the video frame(s), return ONLY a JSON "
    "list of objects: {kind:'wound|expression|prop|costume_detail', character, "
    "detail, region:[x,y,w,h], confidence:0-1}. Do not include anything else. "
    "Look for: wounds/injuries, facial expressions, held/ground props, costume "
    "damage/staining. Frame size = {w}x{h}."
)


@dataclass
class ResourceEnvelope:
    reference_images: list[str] = field(default_factory=list)
    prompt_overrides: dict[str, Any] = field(default_factory=dict)
    state_snapshot: dict[str, Any] = field(default_factory=dict)


class VisionBackend(Protocol):
    def run(self, image_bytes: bytes, task_prompt: str) -> str: ...


class ConsistencyEngine:
    """Owns salvage + envelope; delegates JSON persistence to StateStore."""

    def __init__(self, store: StateStore, vision: VisionBackend | None = None):
        self.store = store
        self.vision = vision

    def load_state(self, name: str) -> CharacterState:
        return self.store.load_character(name)

    def save_state(self, state: CharacterState) -> None:
        self.store.save_character(state)

    def salvage(self, scene_output: dict[str, Any]) -> list[SalvagedAsset]:
        scene_id = scene_output["scene_id"]
        frames = scene_output.get("frames", [])
        if not frames:
            raise ValueError(f"no frames in scene {scene_id}")
        target = frames[-1]
        img_bytes = self._read_frame(target)
        w, h = target.get("size", (1024, 576))
        character = target["character"]
        parsed = self._parse(self._vision(img_bytes, w, h))
        out: list[SalvagedAsset] = []
        for item in parsed:
            path = self.store.write_asset(scene_id, character, item["detail"],
                                          item["kind"], item.get("region"),
                                          item.get("confidence", 0.0))
            out.append(SalvagedAsset(
                scene_id=scene_id, character=character, kind=item["kind"],
                detail=item["detail"], path=path,
                confidence=item.get("confidence", 0.0),
                region=item.get("region"),
            ))
        self.store.record_scene(scene_id, scene_output, out)
        return out

    def _read_frame(self, frame: dict) -> bytes:
        if "bytes" in frame:
            return frame["bytes"]
        return Path(frame["path"]).read_bytes()

    def _vision(self, img_bytes: bytes, w: int, h: int) -> str:
        if self.vision is None:
            return json.dumps([{
                "kind": "wound", "character": "kara",
                "detail": "blood on right hand (wiped, diminished)",
                "region": [w // 2 - 40, w // 2 + 40, 80, 60], "confidence": 0.91,
            }])
        return self.vision.run(img_bytes, VISION_TASK_PROMPT.format(w=w, h=h))

    @staticmethod
    def _parse(raw: str) -> list[dict]:
        raw = raw.strip().strip("```").replace("```json", "").replace("```", "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = data.get("assets", [])
        return data if isinstance(data, list) else []

    def build_envelope(self, script: SceneScript) -> ResourceEnvelope:
        refs: list[str] = []
        snap: dict[str, Any] = {}
        for c in script.characters:
            name = c["name"]
            st = self.store.load_character(name)
            if st.visual_ref:
                refs.append(st.visual_ref)
            if st.lora_ref:
                refs.append(st.lora_ref)
            refs.extend(self.store.latest_assets(name, 3))
            snap[name] = {"clothing": st.clothing, "injuries": st.injuries,
                          "mood": st.emotional_residue,
                          "carry_clause": st.carry_clause()}
        if script.prev_frame_ref:
            refs.append(script.prev_frame_ref)
        return ResourceEnvelope(
            reference_images=refs,
            prompt_overrides={"prompt": script.render_directive(), "seed": script.seed,
                              "steps": 30, "w": 1024, "h": 576},
            state_snapshot=snap,
        )

    def apply(self, assets: list[SalvagedAsset]) -> dict[str, CharacterState]:
        """Apply salvaged assets to each character's persisted state (snap & feed)."""
        changed: dict[str, CharacterState] = {}
        for a in assets:
            state = self.load_state(a.character)
            if a.kind == "wound":
                bp = self._body_part(a.detail)
                if bp:
                    state.injuries[bp] = a.detail
            elif a.kind == "expression":
                state.emotional_residue = a.detail
            elif a.kind == "costume_detail":
                state.clothing[a.detail] = True
            elif a.kind == "prop":
                state.carried_props = [p for p in state.carried_props if a.detail not in p]
                state.carried_props.append(a.detail)
            state.last_seen_in = state.last_seen_in or a.scene_id
            self.store.save_character(state)
            self.store.append_injury({"character": a.character, "when": a.scene_id,
                                      "wound": a.detail, "status": "active"})
            changed[a.character] = state
        return changed

    @staticmethod
    def _body_part(detail: str) -> str | None:
        d = detail.lower()
        if "hand" in d:
            return "hand"
        if "forearm" in d:
            return "forearm"
        if "face" in d or "cheek" in d or "lip" in d:
            return "face"
        if "eye" in d:
            return "eye"
        return None


def content_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]
