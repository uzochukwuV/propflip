"""Deterministic Critic and Verifier — no LLM.

Pure-Python checks against the persisted state store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CritiqueResult:
    violations: list[str] = field(default_factory=list)
    quality_score: float = 1.0
    ok: bool = True

    def flag(self, msg: str) -> None:
        self.violations.append(msg)
        self.ok = False
        self.quality_score = max(0.0, self.quality_score - 0.25)


def critique_story(store: Any, story_text: str, episode: str) -> CritiqueResult:
    result = CritiqueResult()
    text = story_text.lower()
    bible = _load_bible(store)
    characters = {c["id"]: c for c in bible.get("characters", [])}

    for cid, cdata in characters.items():
        st = store.load_character(cid)
        for bp, wound in st.injuries.items():
            if not wound:
                continue
            heal_kw = ["heal", "mending", "closed", "scabbed", "healed", "unhurt", "intact"]
            lowered = wound.lower()
            if any(k in lowered for k in heal_kw):
                continue
            # if wound is active, story must not describe it healed/absent
            for kw in heal_kw:
                if kw in text and bp in text:
                    # Only flag if no nearby resolution phrase
                    result.flag(f"injury contradiction: {cid} {bp} described as healed without scene basis")

    for loop in bible.get("open_loops", []):
        if loop.get("resolved"):
            continue
        lid = loop.get("id", "").lower()
        q = loop.get("question", "").lower()
        if lid and lid not in text and q and q not in text:
            result.flag(f"open-loop silent drop: {loop['id']} not referenced")

    for rule in bible.get("world_rules", []):
        kw = rule.lower().split()[0]
        if kw not in text:
            result.flag(f"world-rule keyword missing: {kw}")

    if not result.violations:
        result.quality_score = 0.95
    return result


def verify_script(store: Any, script_dict: dict[str, Any]) -> CritiqueResult:
    result = CritiqueResult()
    for scene in script_dict.get("scenes", [script_dict]):
        for c in scene.get("characters", []):
            name = c.get("name")
            if not name:
                result.flag("script character missing name")
                continue
            st = store.load_character(name)
            if not st.name or st.visual_ref == "":
                result.flag(f"script invents character without state card: {name}")
            for flag in ("clothing", "injury", "wound", "expression"):
                if flag in c:
                    result.flag(f"script invents visuals for {name}: {flag}")
        ref = scene.get("prev_frame_ref", "")
        if ref and not __import__("pathlib").Path(ref).exists():
            result.flag(f"prev_frame_ref path missing: {ref}")
    return result


def verify_scene(store: Any, prev_assets_paths: list[str], new_state: dict[str, Any]) -> CritiqueResult:
    result = CritiqueResult()
    if not prev_assets_paths:
        result.quality_score = 1.0
        return result
    for cname, cstate in new_state.items():
        st = store.load_character(cname)
        for bp, wound in cstate.get("injuries", {}).items():
            if bp not in st.injuries:
                result.flag(f"visual drift: new injury {bp} for {cname} not in state")
        if st.emotional_residue and cstate.get("emotional_residue") != st.emotional_residue:
            result.flag(f"expression drift: {cname} mood changed without basis")
    if not result.violations:
        result.quality_score = 0.85
    return result


def _load_bible(store: Any) -> dict[str, Any]:
    p = store.root / "bible.json"
    if not p.exists():
        return {}
    import json
    return json.loads(p.read_text())
