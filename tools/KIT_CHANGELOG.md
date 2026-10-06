# Agent kit changelog

The kit travels from game to game: each new game is created from the previous one with
`python tools/gdh.py new` and inherits this file. Add an entry whenever you change a kit file
(the `paths` in tools/kit.json), newest first, naming the game where the change was made, and run
`python tools/gdh.py selftest` before finishing.

## Gusanos (gamedev-ia) — origin

- godot-agent-dev skill: the loop (reproduce -> change -> test -> look -> mutation-check), the
  testing contract, lessons with their causes, the AI-opponent pattern, how the kit evolves.
- agent_harness addon (AgentProbe): `eval` with engine singletons, node arguments, typed-array
  `set`, in-engine frame sequences.
- gdharness: `launch(window, fast)` with `--fixed-fps` (3-6x faster, identical results), 120 s
  socket timeout, game-time waits and `wait_until`, contact sheets, masked snapshots, pytest
  plugin that fails tests on engine errors, `window` / `allow_engine_errors` markers.
- gdh CLI: run, shot, test, new, selftest. Kit manifest with lineage (tools/kit.json).
- Template game honouring the testing contract, with smoke and visual tests.
