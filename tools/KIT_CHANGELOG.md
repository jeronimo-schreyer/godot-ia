# Agent kit changelog

The kit travels from game to game: each new game is created from the previous one with
`python tools/gdh.py new` and inherits this file. Add an entry whenever you change a kit file
(the `paths` in tools/kit.json), newest first, naming the game where the change was made, and run
`python tools/gdh.py selftest` before finishing.

## Nuevo Juego (nuevo-juego) — Godot 4 Best Practices pass

Read *Godot 4 Best Practices* (Henning, Packt 2026) and turned what keeps a growing game
testable into kit rules and checks.
- skill: new `references/architecture.md` (node vs Resource vs RefCounted, scenes, call down /
  signal up, event bus rules, autoloads as systems, FSM/strategy/components, factory/command,
  data-driven + zero-trust data, layers, engine gotchas); Architecture section in SKILL.md;
  contract extended (no global RNG, %Entities cleared on restart, autoload reset, strict typing,
  scenes run alone); harness.md and lessons.md updated.
- gdharness: `g.watch(path, signal)` -> `SignalWatch` (wait/count/last/args), `g.tree()`,
  `g.check_project()`, `g.scenes()`, `g.try_scene()`; new `gdharness/lint.py` + `gdh.py lint`
  (global-rng, wall-clock, time-scale, parent-lookup, root-spawn, load-in-loop; `# gdh: allow(rule)`).
- AgentProbe: `watch_signal`/`signal_log`/`unwatch_signal`, `tree`, `load_all`, `scene_files`,
  `isolate_scene`/`end_isolation` (reports nodes leaked under /root).
- template: `untyped_declaration` = error; game.gd emits `match_started`/`state_changed`, owns a
  `%Entities` container cleared by `start_match`, `debug_win()`; new tests `test_lint.py`,
  `e2e/test_project.py`, signal test in `test_smoke.py`.
- new_game.py writes LF line endings on Windows.

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
