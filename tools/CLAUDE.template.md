# {{NAME}} (Godot 4)

Kit lineage: {{LINEAGE}}. This game was created from the previous one with `tools/gdh.py new`
and carries its own copy of the agent kit (the paths in `tools/kit.json`).

## Working on this game

Use the `godot-agent-dev` skill: it has the loop (reproduce -> change -> test -> look ->
mutation-check), the harness reference and the lessons from earlier games.

- Tests: `python tools/gdh.py test` (fast/headless by default; modules marked `window` render;
  any engine error fails the test). The first run creates the visual baseline in
  `tests/snapshots/` and fails once so it gets reviewed.
- Look at the game: `python tools/gdh.py run --window -c "print(g.sequence('look', 8, 10))"`,
  then read the contact sheet PNG.
- Requirements: Godot 4.5+ on PATH (or `GODOT_PATH`), `pip install godot-e2e pillow pytest`.

## Improve the kit as you go (continuously)

The next game will be created from this one, so the kit you leave here is what it inherits.
Whenever the tooling slows you down, misleads you, or you learn something that isn't specific to
this game, fix it in the kit right then (see "The kit evolves with every game" in the skill):
tool fixes in `tools/gdharness` / `addons/agent_harness`, lessons in the skill's
`references/lessons.md`, template fixes in `tools/template`. Log each change in
`tools/KIT_CHANGELOG.md` and run `python tools/gdh.py selftest` before finishing.

## Testing contract (keep it while the game grows)

- `scripts/game.gd`: `start_match(seed)` restarts deterministically; `state_name()`; one seeded
  RNG; `--seed=N` on the command line; `debug_*` helpers to set up situations for tests.
- Animate from accumulated delta, never from the system clock.
- If something (an AI, a preview) must predict game behaviour, it calls the same code the game runs.
