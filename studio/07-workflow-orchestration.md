# Workflow Orchestration

## Enforced order: Story → Script → Scenes

1. **Story** — Planner produces an episode outline; Writer expands it into prose.
   Critic runs against the bible (world rules, open loops, injury causality).
   Max 3 revisions. Approved story is persisted to `state/stories/{episode}.json`.

2. **Script** — Script Adapter converts the approved story into a `SceneScript` list.
   Every character must have a state card. Script Verifier rejects invented visuals.
   Max 2 revisions. Approved script is persisted to `state/scripts/{episode}.json`.

3. **Scenes** — For each scene: envelope preparation → generation → salvage →
   apply → verify. Up to 2 regeneration attempts if verify fails.

## Approval gates

- `prepare_envelope` raises `ValueError` if any scene character lacks a state card
  or no previous keyframe exists for a continuing injury/prop.
- Story gate: `critique_story` must return `ok=True`.
- Script gate: `verify_script` must return `ok=True`.
- Scene gate: `verify_scene` must return `quality_score >= 0.7`.

## prepare_envelope completeness

3-part envelope:
- narrative (story excerpt + open loops + character arcs)
- visual (CharacterState cards + latest keyframe crops + injuries/clothing/props)
- constraints (style bible, pinned seed, forbidden inventions)

Fails closed: missing card or missing reference image → 422-style error.

## Revision-loop caps

- Story loop: max 3 revisions.
- Script loop: max 2 revisions.
- Scene regen: max 2 attempts.

## 3-scene stress-test contract

- Scene E2_S3 introduces kara's hand wound.
- Scene E2_S4 carries the wound + adds scarf torn + sardonic half-smile.
- Scene E2_S5 envelope confirms salvaged E2_S4 keyframes + updated state
  (hand wound + scarf torn + mood) are inherited.
- Trap test: healing wound without scene basis forces revision; final approved
  story must not contradict state.
