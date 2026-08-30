"""Real LLM integration using TokenRouter (default) or Gemini via make_llm()."""
from __future__ import annotations

import os
from typing import Any

from app.config import make_llm


class RealLLM:
    """Thin wrapper around TokenRouter / Gemini LLM calls.

    Uses litellm.completion under the hood (via LiteLlm or direct string model).
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or make_llm()
        self._key = os.environ.get("TOKEN_ROUTER_API_KEY", "")
        self._base = os.environ.get("TOKEN_ROUTER_BASE_URL", "https://api.tokenrouter.com/v1")

    def _call(self, prompt: str) -> str:
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError("litellm is required for RealLLM") from exc

        model = self.model
        if isinstance(model, str) and model.startswith("openai/"):
            model = model[len("openai/"):]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "api_base": self._base,
            "api_key": self._key,
        }
        resp = completion(**kwargs)
        text = resp.choices[0].message.content or ""
        return text.strip()

    def write_story(self, episode: str, store: Any, trap: str | None = None) -> str:
        prompt = (
            f"Write a short episode story for '{episode}' respecting the series bible. "
            "Do not heal unresolved injuries unless a scene explicitly resolves them. "
            "Output plain text only."
        )
        return self._call(prompt)

    def adapt_script(self, story: str, store: Any, episode: str) -> list[dict[str, Any]]:
        prompt = (
            "Adapt the following story into a JSON list of scene scripts. "
            "Each scene needs: scene_id, setting, lighting, seed (random int), "
            "characters (list of {name, emotion, action}), prev_frame_ref (empty string), "
            "camera, style. Do not invent clothing or injuries not in the story. "
            f"Story: {story}"
        )
        raw = self._call(prompt)
        try:
            import json
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "scenes" in data:
                return data["scenes"]
        except Exception:
            pass
        return []

    def generate_scene(self, scene_script: dict[str, Any], envelope: Any,
                       store: Any) -> dict[str, Any]:
        prompt = (
            f"Generate a scene for {scene_script.get('scene_id')}. "
            f"Setting: {scene_script.get('setting')}. "
            f"Prompt: {envelope.prompt_overrides.get('prompt') if hasattr(envelope, 'prompt_overrides') else scene_script}"
        )
        self._call(prompt)
        return {
            "scene_id": scene_script.get("scene_id", "unknown"),
            "frames": [{
                "character": scene_script.get("characters", [{}])[0].get("name", "kara"),
                "path": str(store.assets / "char_kara_base.png"),
                "size": (1024, 576),
            }],
            "salvage_hints": [],
        }
