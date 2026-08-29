"""Config tests: provider wiring for TokenRouter vs Gemini (no network)."""
from app import config


def test_tokenrouter_defaults():
    assert config.TOKEN_ROUTER_BASE_URL == "https://api.tokenrouter.com/v1"
    assert config.TOKEN_ROUTER_MODEL == "z-ai/glm-5.3-free"
    assert config.USE_GEMINI is False


def test_make_llm_requires_key(monkeypatch):
    monkeypatch.delenv("TOKEN_ROUTER_API_KEY", raising=False)
    monkeypatch.setenv("STUDIO_USE_GEMINI", "0")
    try:
        config.make_llm()
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "make_llm must refuse to build without the key"


def test_make_llm_gemini_path(monkeypatch):
    monkeypatch.setenv("STUDIO_USE_GEMINI", "1")
    assert config.make_llm() == "gemini-2.0-flash"


def test_make_llm_tokenrouter(monkeypatch):
    monkeypatch.setenv("TOKEN_ROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("STUDIO_USE_GEMINI", "0")
    llm = config.make_llm()
    # LiteLlm stores provider kwargs in _additional_args (litellm receives them at call time)
    assert llm.model == "openai/z-ai/glm-5.3-free", llm.model
    args = llm._additional_args
    assert args["api_base"] == "https://api.tokenrouter.com/v1", args
    assert args["api_key"] == "sk-test", args
