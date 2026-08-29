"""ADK agent factories for the 8-stage continuity workflow.

Each agent's system prompt mirrors studio/06 §B. The core engine
functions are wrapped as ADK FunctionTools so the agent can call them;
the engine itself stays framework-agnostic (pure Python).

Model cards / endpoints:
- Planner/Writer/Critic/Script-Adapter : gemini-2.0-flash
- Visual State Manager / Continuity Verifier : gemini-2.0-flash (vision)
- Scene Generator : delegates to Comfy/Veo via tool calls
- Series Bible Agent : gemini-2.0-flash

These build only when constructed; they invoke the LLM only on `agent.run`,
so the app imports & starts without GCP credentials.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .core.continuity import ConsistencyEngine as _Engine
from .state.store import StateStore

MODEL = "gemini-2.0-flash"


def _engine_tools(engine: _Engine) -> list[FunctionTool]:
    return [
        FunctionTool(engine.salvage),
        FunctionTool(engine.build_envelope),
        FunctionTool(engine.apply),
    ]


def build_planner(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="episode_planner",
        model=MODEL,
        instruction=(
            "You are the Episode Planner. From the Series Bible, emit a JSON "
            "beat-sheet (Hook, 2 rising beats, Midpoint twist, Climax, "
            "Resolution, series-hook). List characters present per beat and any "
            "NEW injuries/damage/tension to carry forward. Register open loops "
            "into the store. Never invent injuries already resolved in the "
            "Timeline. Output JSON only."
        ),
        tools=_engine_tools(engine),
    )


def build_script_adapter(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="script_adapter",
        model=MODEL,
        instruction=(
            "You are the Script Adapter. Convert the approved story into a "
            "SceneScript list. RULE: do not invent clothing, injuries, "
            "expressions, or props. Pull the CURRENT visual state from the "
            "CharacterState cards and write it as a CONTINUITY flag on each "
            "action line. Include dialogue intonation parentheticals."
        ),
        tools=_engine_tools(engine),
    )


def build_scene_generator(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="scene_generator",
        model=MODEL,
        instruction=(
            "You are the Scene Generator. Conditionally generate the scene via "
            "Comfy Veo. Prompt: 'Match {character} injuries, clothing, and "
            "expression from reference crops EXACTLY. Only change what the new "
            "action requires.' PIN seed={seed}. Do not alter character state; "
            "hand the output frame to the Visual State Manager."
        ),
        tools=_engine_tools(engine),
    )


def build_visual_state_manager(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="visual_state_manager",
        model=MODEL,
        instruction=(
            "You are the Visual State Manager. After each scene: run vision "
            "salvage (wounds/expressions/props/costume-detail), crop those "
            "regions into assets, UPDATE each CharacterState / Location / "
            "PropTracker, append to the Timeline injury_log, and pass the "
            "updated records to the next Scene Generator."
        ),
        tools=_engine_tools(engine),
    )


def build_critic(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="critic",
        model=MODEL,
        instruction=(
            "You are the Critic. Verify story against world_rules, tone, and "
            "Timeline causality. Reject with a VIOLATION LIST if anything breaks; "
            "otherwise PASS and register new open loops. Never let a character "
            "do something before knowing it (check Timeline). Output JSON."
        ),
        tools=_engine_tools(engine),
    )


def build_continuity_verifier(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="continuity_verifier",
        model=MODEL,
        instruction=(
            "You are the Continuity Verifier. Score drift (appearance, clothing, "
            "expression, prop location) between the new frame and prior "
            "CharacterState. If ANY score < 0.75 return REJECT + report and force "
            "regeneration; else ACCEPT. Log scores for the ClickHouse/Cinema layer."
        ),
        tools=_engine_tools(engine),
    )


def build_series_bible_agent(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="series_bible_agent",
        model=MODEL,
        instruction=(
            "You are the Series Bible Keeper. Produce/keep the living Series "
            "Bible JSON: characters (id, want/need/lie/wounds), exactly 3 world "
            "rules, 3 tone rules, major arcs, open_loops (with introduced_in). "
            "Revise when new loops appear. Output JSON only."
        ),
        tools=_engine_tools(engine),
    )


def build_story_writer(store: StateStore) -> LlmAgent:
    from .core.continuity import ConsistencyEngine
    engine = ConsistencyEngine(store)
    return LlmAgent(
        name="story_writer",
        model=MODEL,
        instruction=(
            "You are the Story Writer. Write the full prose story for the "
            "episode following the Planner's beat-sheet. Do NOT change character "
            "injuries/visuals from the Timeline. End by appending a line: "
            "'VISUAL_STATE_CHANGES:' with exact state changes to apply."
        ),
        tools=_engine_tools(engine),
    )


def all_agents(store: StateStore) -> dict[str, LlmAgent]:
    return {
        "series_bible": build_series_bible_agent(store),
        "planner": build_planner(store),
        "story_writer": build_story_writer(store),
        "critic": build_critic(store),
        "script_adapter": build_script_adapter(store),
        "scene_generator": build_scene_generator(store),
        "visual_state_manager": build_visual_state_manager(store),
        "continuity_verifier": build_continuity_verifier(store),
    }
