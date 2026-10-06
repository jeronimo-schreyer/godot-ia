---
name: godot-agent-dev
description: How to build and change a Godot 4 game as an AI agent and actually verify it - run the game, drive it, look at it, test it fast and deterministically with the agent kit (tools/gdharness + addons/agent_harness on top of godot-e2e), and keep improving that kit so the next game inherits it. Use whenever working on a Godot project that has tools/gdh.py, when adding gameplay, weapons, UI, physics or AI opponents, when writing or fixing tests/e2e, when the user reports something "works badly", when tooling gets in the way, or when creating the next game (tools/gdh.py new).
---

# Developing Godot games as an agent

You can't play the game, so every claim about it must come from running it. This skill is the
loop and the rules that made that work on a full Worms-like game (terrain destruction, 12 weapons,
ninja rope, CPU opponents, 76 e2e tests in ~70 s).

## The loop

1. **Reproduce / observe first.** Before changing behaviour, run the game in the situation that
   matters and look: `python tools/gdh.py run --window -c "..."` with `g.sequence(...)` gives a
   contact sheet of frames over time. When the user says something "works badly", reproduce it
   on a *real* map/scene, not only on a convenient test setup (a flat debug arena hid a rope bug
   that made the worm freeze on every real slope).
2. **Change** the code. Keep game logic deterministic (see contract below).
3. **Verify by behaviour:** `python tools/gdh.py test` (or `python -m pytest tests/e2e -q`).
   Fast and headless by default; modules marked `window` render. Every test fails if the
   engine logged an error.
4. **Look at it** whenever the change is visual, UI, or about motion: a sequence/contact sheet
   or a screenshot, then *read the image*. Tests said "pass" while a menu stretched across the
   screen, a cursor didn't follow the mouse, and a rope dragged on the floor; pictures caught all three.
5. **Prove new tests can fail.** Break the thing on purpose (one-line mutation), run the test,
   see it fail, revert. A wind-compensation test passed with the wind *ignored* until the target
   was moved far enough for wind to matter.
6. Run the **whole suite** before saying it's done, and report numbers and what you looked at.

## The harness (details: [references/harness.md](references/harness.md))

```python
from gdharness import launch, node
with launch() as g:                         # headless + --fixed-fps: fastest, deterministic
    g.call("/root/Main", "start_match", 42)
    g.wait_until("state_name() == 'RETREAT'", base="/root/Main", timeout=10)
    print(g.eval("teams.size()", base="/root/Main"))
    g.assert_no_errors()
with launch(window=True) as g:              # rendered (still fast) for pictures
    g.sequence("explosion", count=8, every=6)   # -> screenshots/harness/explosion.sheet.png
    g.snapshot("start_screen", mask=[(14, 636, 76, 62)])
```

- CLI: `tools/gdh.py run|shot|test|new`. pytest: fixture `godot`, markers `window`,
  `allow_engine_errors`, options `--window`, `--realtime`, `--update-snapshots`.
- Waits are in **game time**. Never `Engine.time_scale` to go faster: it enlarges the physics
  step and changes results (a grenade landed 30 px away). `--fixed-fps` is 3-6x faster and identical.
- Mouse and GUI clicks need a window: put those tests in a `window` module.

## Make the game testable (the contract)

- `start_match(seed)` restarts deterministically; all randomness through one seeded RNG.
  `--seed=N` on the command line.
- A readable `state_name()`; signals/counters tests can wait on (`turn_number`, `explosion_count`).
- `debug_*` helpers that build a situation in one call (flat arena, place a unit, set ammo).
  They are the difference between a 3-line test and a flaky 30-line one.
- Visual animation from accumulated `delta`, never `Time.get_ticks_msec()` (it made snapshots
  differ between identical runs).
- Shared logic in one place: if the AI, a preview or a test needs to predict something, it must
  call the same code the game runs (see AI section).
- `tools/gdh.py new DEST --name X` creates the next game (already following this) from the current one.

## Rules learned the hard way ([references/lessons.md](references/lessons.md))

- Silent failures: a GDScript runtime error inside a called method returns a default value and the
  test passes. The harness now fails the test; don't disable that without a reason.
- A test that passes for the wrong reason is worse than none: build unambiguous scenarios
  (one target, everything else removed) and mutation-check them.
- When a test fails, first ask whether the test's assumption is wrong (the AI picked a *better*
  target than the one the test expected) before "fixing" the game.
- Pixel/kinematic physics: never make a move all-or-nothing against terrain; resolve per axis or
  bounce, or objects freeze on contact.
- Measure before optimizing (profile scene pattern in references/lessons.md); the bottleneck was
  `Image.get_pixel` and redundant simulations, not where it looked.

## The kit evolves with every game

There is no central copy of this kit. Each game carries its own (the paths in `tools/kit.json`),
and the next game is created from the most recent one: `python tools/gdh.py new ../next --name X`.
So improvements only survive if you make them **here, while you work** - nobody will collect them later.

- **When:** the moment tooling costs you time (a workaround, a missing helper, a misleading
  result) or you learn something true beyond this game. Don't defer it to "the end".
- **Generic vs specific:** a change belongs to the kit only if the next, different game would
  benefit. Worm/weapon/level logic stays in the game; "how to wait for X", "how to look at Y",
  Godot gotchas, testing patterns go to the kit. When in doubt, put the generic part in the kit
  and keep the specific part in the game.
- **Where:** tools -> `tools/gdharness`, `tools/gdh.py`, `addons/agent_harness`; method and
  lessons -> this skill (`references/lessons.md`: symptom -> cause -> rule); starting point ->
  `tools/template` (+ `tools/CLAUDE.template.md`). New kit files must be added to `tools/kit.json`.
- **Keep it working:** log the change in `tools/KIT_CHANGELOG.md` (newest first, with the game's
  name), keep the API backward compatible or update every caller in the kit, and run
  `python tools/gdh.py selftest` (creates a throwaway game from the kit and runs its tests)
  plus this game's own tests before finishing.
- **Keep it lean:** prune or merge lessons that are now handled by the tools; the skill should
  stay readable in one sitting.

## AI opponents ([references/ai-opponents.md](references/ai-opponents.md))

Plan by simulating candidate actions with the game's *own* code (projectile flight, walking, rope,
knockback on an off-screen "ghost" copy), score outcomes, then replay the chosen plan tick by tick.
Test that a plan without aim error lands exactly where simulated. Spread thinking over frames
with a time budget; difficulty = noise on top of the best plan.
