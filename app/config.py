"""Model-provider configuration — swap TokenRouter <-> Gemini via one env flag.

TokenRouter (OpenAI-compatible) is the default so the agents can run against
z-ai/glm-5.3-free immediately. Switch to Google Gemini later with:
    export STUDIO_USE_GEMINI=1   # requires GOOGLE_API_KEY or GCP ADC

NOTE on secrets: the API key is NEVER stored in source. Export it at runtime:
    export TOKEN_ROUTER_API_KEY="sk-..."
"""
from __future__ import annotations

import os

# --- TokenRouter (OpenAI-compatible) defaults (non-secret config) ---
TOKEN_ROUTER_BASE_URL = os.environ.get(
    "TOKEN_ROUTER_BASE_URL", "https://api.tokenrouter.com/v1")
TOKEN_ROUTER_MODEL = os.environ.get("TOKEN_ROUTER_MODEL", "z-ai/glm-5.3-free")
TOKEN_ROUTER_API_KEY = os.environ.get("TOKEN_ROUTER_API_KEY", "")

# --- Gemini toggle (default off) ---
USE_GEMINI = os.environ.get("STUDIO_USE_GEMINI", "0") == "1"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def make_llm():
    """Return the ADK model for the active provider.

    Reads env vars LIVE (at call time) so provider can be switched without
    restarting the process / for tests. Returns a model string for native
    Google Gemini, or a LiteLlm instance for TokenRouter (litellm is
    imported lazily, so importing this module never requires litellm/creds).
    """
    if os.environ.get("STUDIO_USE_GEMINI", "0") == "1":
        return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    key = os.environ.get("TOKEN_ROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "TOKEN_ROUTER_API_KEY env var is not set. "
            "Run: export TOKEN_ROUTER_API_KEY='sk-...'")
    from google.adk.models.lite_llm import LiteLlm  # lazy import
    base = os.environ.get("TOKEN_ROUTER_BASE_URL", "https://api.tokenrouter.com/v1")
    model = os.environ.get("TOKEN_ROUTER_MODEL", "z-ai/glm-5.3-free")
    # 'openai/' prefix tells litellm to route via the custom api_base.
    return LiteLlm(model=f"openai/{model}", api_base=base, api_key=key)
