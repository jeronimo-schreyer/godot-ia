# Lessons (symptom -> cause -> rule)

Each one cost real time on the Worms project. Most are now handled by the harness; the rule says
what to keep doing anyway.

## Testing and tooling

- **Test passed with a bug inside.** A called method hit "Out of bounds get index" and returned
  `[]`; godot-e2e reported success. -> The harness fails any test during which the engine logged
  an error. Keep it on; use `allow_engine_errors` only for deliberate errors.
- **"Connection timed out" on a 4 s wait.** godot-e2e's client socket times out after 2 s ->
  the harness raises it to 120 s. If you use raw godot-e2e, chunk waits.
- **Speeding up with `Engine.time_scale` changed results.** Bigger physics step = different
  trajectories, AI predictions no longer match. -> `--fixed-fps` (harness `fast=True`).
- **GUI tests failed only headless.** `click_node` misses and the cursor position isn't
  tracked without a window. -> `window` marker for GUI/mouse modules (still fast).
- **Snapshot differed between identical runs.** An arrow bobbed with `Time.get_ticks_msec()`.
  -> Animate from accumulated delta, reset per state; mask genuinely changing HUD bits.
- **GDSnap-style "first frame of a scene" snapshots** never caught a real bug and needed
  regenerating after every HUD tweak. -> Snapshot meaningful *moments* (after an explosion) and
  rely on contact sheets for motion.
- **Wind test passed with wind ignored.** The target was close enough that drift stayed inside
  the blast radius. -> Mutation-check every non-trivial test.
- **"AI didn't hit the enemy"** - it hit a *different*, easier enemy. -> Remove ambiguity from
  scenarios (kill/move everything irrelevant) and read why it failed before changing the game.
- **Flat test arena hid a bug** (rope froze on any slope). -> Debug arenas are for exact
  assertions; also reproduce user reports on real content.
- **Autoloads missing under `godot --script`.** -> Make profiling/utility runners a scene
  (`tests/tools/ai_profile.tscn` pattern) and run `godot --headless --path . res://that.tscn`.
- **Nested `project.godot` (templates) clashed** with the game's `class_name`s. -> `.gdignore`
  in folders Godot must not scan (`tools/`).

- **Architecture rules only help if something checks them.** Rules from *Godot 4 Best Practices*
  that break determinism or isolation are now mechanical: `gdh lint` (global RNG, clock,
  parent lookups, root spawns), the project-health tests (everything loads, scenes run alone),
  strict typing as error. The rest is in architecture.md as judgement.

## Godot gotchas met

- Canvas shaders: `TEXTURE` isn't accessible inside helper functions, and passing it as a
  `sampler2D` argument failed to compile -> inline the sampling in `fragment()`.
- Controls under anchors: set `offset_*` (or `set_anchors_and_offsets_preset` with
  `PRESET_MODE_MINSIZE` for content-sized panels), not `position`/`size`.
- `get_global_mouse_position()` ignores simulated (`parse_input_event`) motion -> track the
  cursor from `InputEventMouse` events if tests must drive it.
- Rebuilding UI rows with `queue_free` while a button inside is being pressed renames/frees
  things under your feet -> build once, show/hide and update.
- Typed arrays (`Array[bool]`) can't be assigned from a plain array via `set()` -> `assign()`
  (harness `set` does it).
- Pixel-perfect kinematic movement: an all-or-nothing diagonal step against the ground freezes
  objects; resolve per axis or bounce.
- GDScript warnings set to error (`debug/gdscript/warnings/<name>=2`) are enforced at runtime
  too, headless included: the script fails to load with "Warning treated as error". That's how
  the kit enforces static typing without an editor (addons are excluded by default).
- `ResourceLoader.load()` of a script with a parse error returns a non-null `Script` that can't
  be instantiated -> check `can_instantiate()` (and `is_abstract()`), not `== null`.
- Recording any signal generically: a variadic method (`func f(...args: Array)`, 4.5+) connected
  with `.bind(key)` receives the signal's args with the bound key appended last.
- `Image.get_pixel` is slow in hot loops; keep a `PackedByteArray` copy (`image.get_data()`,
  refreshed lazily after edits) for lookups.

## Environment (Windows)

- Python's default file encoding is cp1252: edits through ad-hoc Python silently failed to match
  non-ASCII text. Use `PYTHONUTF8=1` / `encoding="utf-8"`, or the Edit tool.
- Godot on PATH via scoop (`godot`); `GODOT_PATH` overrides.

## Performance method

1. Instrument (wall time vs CPU time, counts) and get a baseline on several seeds.
2. Profile per category in a headless scene (`ai_profile.tscn`): it showed grenades cost 2x
   bazookas (bounces), two weapons simulating identical flights, and 0.75 us per pixel lookup.
3. Fix the biggest item, re-measure, check behaviour tests still pass (shared physics changed!).
Result on the AI: 2.7-5.7 s -> 1.0-2.1 s per decision while adding features.
