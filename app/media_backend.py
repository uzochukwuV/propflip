"""Mock media backend for local testing (no real video API needed)."""
from __future__ import annotations

from typing import Any

from app.state.store import StateStore


class MockMediaBackend:
    """Deterministic scene generation for local workflow testing.

    Returns stubbed scene outputs with salvage hints so the snap-and-feed loop
    can run end-to-end without a real video generation API.
    """

    def generate_scene(self, scene_script: dict[str, Any], store: StateStore) -> dict[str, Any]:
        sid = scene_script.get("scene_id", "unknown")
        chars = scene_script.get("characters", [])
        primary = chars[0].get("name", "kara") if chars else "kara"

        asset_path = str(store.assets / f"char_{primary}_base.png")
        store.assets.mkdir(parents=True, exist_ok=True)
        store.assets.joinpath(f"char_{primary}_base.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        hints = [
            {"character": primary, "kind": "expression",
             "detail": scene_script.get("characters", [{}])[0].get("emotion", "neutral")},
        ]
        for c in chars:
            action = c.get("action", "")
            if "blood" in action.lower() or "wound" in action.lower():
                hints.append({"character": c["name"], "kind": "wound",
                               "detail": "blood on right hand (wiped, diminished)"})
            if "torn" in action.lower():
                hints.append({"character": c["name"], "kind": "costume_detail",
                               "detail": "scarf torn"})

        return {
            "scene_id": sid,
            "frames": [{"character": primary, "path": asset_path, "size": (1024, 576)}],
            "salvage_hints": hints,
        }

    def generate_teaser(self, episode_id: str, store: StateStore) -> dict[str, Any]:
        path = str(store.assets / f"teaser_{episode_id}.mp4")
        store.assets.joinpath(f"teaser_{episode_id}.mp4").write_bytes(b"\x00" * 16)
        return {"kind": "video", "ref": path, "workflow_id": "mock-teaser", "version": "v1"}

    def generate_thumbnail(self, scene_id: str, store: StateStore) -> dict[str, Any]:
        path = str(store.assets / f"thumb_{scene_id}.png")
        store.assets.joinpath(f"thumb_{scene_id}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return {"kind": "image", "ref": path, "workflow_id": "mock-thumb", "version": "v1"}
