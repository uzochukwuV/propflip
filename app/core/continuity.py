"""Scene-to-scene continuity: keyframe salvage + resource-envelope builder.

Implements the Level-2 handoff (studio/06-agent-prompts-and-schemas.md):
after a scene renders, run a vision pass to extract wounds/expressions/
props/costume details, persist them into CharacterState, and build the
3-part resource envelope fed to the NEXT scene's generation call.

Framework-agnostic. ``vision_fn`` is a Callable[[bytes, str], str] (image,
task_prompt -> raw model JSON). When None, a deterministic mock is used so
the loop runs end-to-end without a vision backend (tests, local demo).
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
    "detail, region:[x,y,w,h], confidence:0-1}. Extract wounds/injuries, distinct "
    "facial expressions, held/ground props, and costume damage/staining. Omit "
    "absent items. Frame size = {w}x{h}."
)


@dataclass
class ResourceEnvelope:
    reference_images: list[str] = field(default_factory=list)
    prompt_overrides: dict[str, Any] = field(default_factory=dict)
    state_snapshot: dict[str, Any] = field(default_factory=dict)


class VisionBackend(Protocol):
    def run(self, image_bytes: bytes, task_prompt: str) -> str: ...


class ContinuityEngine:
    """Owns salvage + envelope; delegates JSON persistence to StateStore."""

    def __init__(self, store: StateStore, vision: VisionBackend | None = None):
        self.store = store
        self.vision = vision

    # ---- salvage the just-generated scene ----
    def salvage(self, scene_output: dict[str, Any]) -> list[SalvagedAsset]:
        scene_id = scene_output["scene_id"]
        frames = scene_output.get("frames", [])
        if not frames:
            raise ValueError(f"no frames in scene {scene_id}")
        target = frames[-1]  # last keyframe carries into next scene
        w, h = target.get("size", (1024, 576))
        character = target["character"]
        img_bytes = self._read_frame(target)

        raw = self._vision(img_bytes, w, h)
        parsed = self._parse(raw)
        assets: list[SalvagedAsset] = []
        for item in parsed:
            path = self.store.write_asset(
                scene_id, character, item["detail"], item["kind"],
                item.get("region"), item.get("confidence", 0.0),
            )
            assets.append(SalvagedAsset(
                scene_id=scene_id, character=character,
                kind=item["kind"], detail=item["detail"],
                path=path, confidence=item.get("confidence", 0.0),
                region=item.get("region"),
            ))
        self.store.record_scene(scene_id, scene_output, assets)
        return assets

    # ---- apply salvaged assets into state (the "snap & feed") ----
    def apply(self, assets: list[SalvagedAsset]) -> dict[str, CharacterState]:
        changed: dict[str, CharacterState] = {}
        for a in assets:
            state = self.store.load_character(a.character)
            if a.kind == "wound":
                bp = self._body_part(a.detail)
                if bp:
                    state.injuries[bp] = a.detail
            elif a.kind == "expression":
                state.emotional_residue = a.detail
            elif a.kind == "prop":
                state.carried_props = [p for p in state.carried_props
                                       if a.detail not in p]
                state.carried_props.append(a.detail)
            elif a.kind == "costume_detail":
                state.clothing[a.detail] = True
            self.store.save_character(state)
            self.store.append_injury(
                {"character": a.character, "when": state.last_seen_in or "scene",
                 "wound": a.detail, "status": "active"})
            changed[a.character] = state
        return changed

    # ---- build the resource envelope for the next scene ----
    def build_envelope(self, script: SceneScript) -> ResourceEnvelope:
        refs: list[str] = []
        snapshot: dict[str, Any] = {}
        for c in script.characters:
            name = c["name"]
            st = self.store.load_character(name)
            if st.visual_ref:
                refs.append(st.visual_ref)
            if st.lora_ref:
                refs.append(st.lora_ref)
            refs.extend(self.store.latest_assets(name, n=3))
            snapshot[name] = {
                "clothing": st.clothing, "injuries": st.injuries,
                "mood": st.emotional_residue,
                "carry_clause": st.carry_clause(),
            }
        if script.prev_frame_ref:
            refs.append(script.prev_frame_ref)
        return ResourceEnvelope(
            reference_images=refs,
            prompt_overrides={
                "prompt": script.render_directive(),
                "seed": script.seed, "steps": 30, "w": 1024, "h": 576,
            },
            state_snapshot=snapshot,
        )

    # ---- helpers ----
    def _read_frame(self, frame: dict[str, Any]) -> bytes:
        if "bytes" in frame:
            return frame["bytes"]
        return Path(frame["path"]).read_bytes()

    def _vision(self, img_bytes: bytes, w: int, h: int) -> str:
        if self.vision is None:
            # deterministic mock: always reports the canonical hand wound so the
            # handoff chain is visible in tests without a vision backend.
            return json.dumps([{
                "kind": "wound", "character": "kara",
                "detail": "blood on right hand (wiped, diminished)",
                "region": [w // 2 - 40, w // 2 + 40, 80, 60],
                "confidence": 0.91,
            }])
        return self.vision.run(img_bytes, VISION_TASK_PROMPT.format(w=w, h=h))

    @staticmethod
    def _parse(raw: str) -> list[dict]:
        raw = raw.strip()
        if not raw:
            return []
        raw = re.sub(r"^```(json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = data.get("assets", [])
        return data if isinstance(data, list) else []

    @staticmethod
    def _body_part(detail: str) -> str | None:
        d = detail.lower()
        if "hand" in d: return "hand"
        if "forearm" in d: return "forearm"
        if "face" in d or "cheek" in d or "lip" in d: return "face"
        if "eye" in d: return "eye"
        return None


def content_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


class MockVision(VisionBackend):
    """Deterministic vision stand-in for offline tests / local demo."""

    def run(self, image_bytes: bytes, task_prompt: str) -> str:
        return json.dumps([{
            "kind": "wound", "character": "kara",
            "detail": "blood on right hand (wiped, diminished)",
            "region": [512, 256, 80, 60], "confidence": 0.91,
        }])
