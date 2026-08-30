"""Scene-to-scene continuity: keyframe salvage + resource-envelope builder.

After a scene renders, run a vision pass to extract persistent visual STATE
facets (wounds, expressions, props, costume damage, pose) and persist them
into the CharacterState card so they carry forward into the NEXT scene and
the NEXT episode. Injuries are just one facet of the general state card.

Framework-agnostic. ``vision`` is a VisionBackend (image, prompt -> JSON).
When None, salvage relies on explicit ``salvage_hints`` in the scene output
(deterministic demo path); a real vision backend (Gemini) is plugged in for
production.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from ..state.store import CharacterState, SceneScript, StateStore, SalvagedAsset

VISION_TASK_PROMPT = (
    "You are a continuity extractor. From the video frame(s), return ONLY a JSON "
    "list of objects: {kind:'wound|expression|prop|costume_detail|pose', character, "
    "detail, region:[x,y,w,h], confidence:0-1}. Extract any persistent visual state: "
    "wounds/injuries, facial expressions, held/ground props, costume damage/staining, "
    "and recurring poses/posture. Omit absent items."
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
        character = target["character"]
        w, h = target.get("size", (1024, 576))

        parsed: list[dict] = []
        if self.vision is not None:
            parsed.extend(self._parse(self._vision(target, w, h)))
        for hint in scene_output.get("salvage_hints", []):
            if isinstance(hint, dict):
                parsed.append(dict(hint))

        out: list[SalvagedAsset] = []
        seen: set[tuple[str, str, str]] = set()
        for item in parsed:
            cname = item.get("character", character)
            key = (cname, item["kind"], item["detail"])
            if key in seen:
                continue
            seen.add(key)
            path = self.store.write_asset(
                scene_id, cname, item["detail"], item["kind"],
                item.get("region"), item.get("confidence", 0.0))
            out.append(SalvagedAsset(
                scene_id=scene_id, character=cname, kind=item["kind"],
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

    def _vision(self, frame: dict, w: int, h: int) -> str:
        return self.vision.run(self._read_frame(frame), VISION_TASK_PROMPT.format(w=w, h=h))

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
            snap[name] = {
                "clothing": st.clothing, "injuries": st.injuries,
                "carried_props": st.carried_props,
                "mood": st.emotional_residue,
                "pose": st.pose_tendency,
                "carry_clause": st.carry_clause(),
            }
        if script.prev_frame_ref:
            refs.append(script.prev_frame_ref)
        return ResourceEnvelope(
            reference_images=refs,
            prompt_overrides={"prompt": script.render_directive(), "seed": script.seed,
                              "steps": 30, "w": 1024, "h": 576},
            state_snapshot=snap,
        )

    def apply(self, assets: list[SalvagedAsset]) -> dict[str, CharacterState]:
        """Apply salvaged STATE facets to each character's card (snap & feed).

        Wounds, clothing, props, expression and pose are ALL facets of the
        general state card; each is updated from a salvaged asset (never
        invented). The card is the single carrier of continuity across scenes
        and episodes.
        """
        changed: dict[str, CharacterState] = {}
        for a in assets:
            state = self.load_state(a.character)
            if a.kind == "wound":
                key = re.sub(r"[\W_]+", "_", a.detail).strip("_") or "wound"
                state.injuries[key] = a.detail
            elif a.kind == "expression":
                state.emotional_residue = a.detail
            elif a.kind == "costume_detail":
                state.clothing[a.detail] = True
            elif a.kind == "prop":
                state.carried_props = [p for p in state.carried_props if a.detail not in p]
                state.carried_props.append(a.detail)
            elif a.kind == "pose":
                state.pose_tendency = a.detail
            state.last_seen_in = state.last_seen_in or a.scene_id
            self.store.save_character(state)
            self.store.append_injury({"character": a.character, "when": a.scene_id,
                                      "detail": a.detail, "kind": a.kind, "status": "active"})
            changed[a.character] = state
        return changed


def content_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]
