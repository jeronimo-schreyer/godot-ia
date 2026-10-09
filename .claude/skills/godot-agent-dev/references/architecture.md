# Architecture rules (Godot 4)

Distilled from *Godot 4 Best Practices* (Henning, Packt 2026, targets Godot 4.7), filtered for
what matters to an agent that must keep a game testable while it grows. Rules marked
**[kit]** are enforced or checked by the harness (`gdh lint`, `tests/e2e/test_project.py`, the
`untyped_declaration` = error project setting). Everything else is judgement: apply it when the
code reaches the size where it pays. **Prototype first:** a jam game or a mechanic you're still
proving doesn't need factories, buses or layers. Hard-code until it's fun. Extract a pattern
when the second or third copy appears.

## 1. Pick the right kind of object

| Needs to draw, collide, or own child transforms? | Use |
|---|---|
| Yes | **Node / scene** (simulation and presentation) |
| No, it's designer data or saved data | **Resource** (`class_name X extends Resource` + `@export`) |
| No, it's logic or temporary state | **RefCounted** (frees itself), or **static funcs** if it has no state |
| Needs tree services only (timer, sound, animation) | Timer / AudioStreamPlayer / AnimationPlayer node |

- Don't use the tree as a database. An inventory made of child nodes pays node overhead per
  item, can't be saved simply, and dies with the UI. Model it as `Array[ItemData]` in a Resource
  and call `emit_changed()`. A view listens to `changed` and rebuilds.
- Pure rules (damage formulas, scoring, ballistics, AI scoring) go in RefCounted or static classes.
  Tests can call them with no scene, and the AI can call the *same* code (see ai-opponents.md).
  Pass the RNG and the time in as parameters.
- Write `extends RefCounted` explicitly. Omitting it means the same thing, but hides how memory
  is managed.

## 2. Scenes: structure in .tscn, behaviour in .gd

- **Declarative vs imperative.** Static structure (children, textures, positions) belongs in the
  scene. Don't build it in `_ready()` with `Node.new()`/`add_child()`. Behaviour and values that
  change often belong in scripts or Resources, because .tscn diffs are noisy.
- **One focused idea per scene, and it runs on its own** (F6). It must not crash because a
  particular parent is missing. **[kit]** `test_every_scene_runs_alone` instances each scene
  alone in a sandbox and fails on engine errors or on nodes it leaked under `/root`. Scenes that
  genuinely need a host go in `NEEDS_A_HOST`, with the reason.
- **Keep gameplay hierarchies shallow.** Split big things into sub-scenes (Ship ⊃ Engine ⊃
  thrusters). If the same node structure appears twice, make it a scene and instance it.
- **Instancing is composition. Inherited scenes are visual or structural specialisation**
  (BaseEnemy.tscn → Goblin.tscn). Script inheritance is for logic specialisation. Components are
  for added abilities. Put variant *numbers* in Resources (`goblin_stats.tres`), not in
  per-scene Inspector overrides.
- **References inside a scene:**
  - Use `@export var x: Type` when a designer or test should set it. It survives renames.
  - Use `%UniqueName` for internal wiring.
  - Never use paths that climb (`get_parent()`, `"../X"`). **[kit]** The lint rule
    `parent-lookup` flags them.
- **Spawned things go into a container the level owns, never into the shooter or the root.**
  Bullets parented to the ship move with it. Bullets in `get_tree().root` survive the restart.
  - **[kit]** The lint rule `root-spawn` flags them.
  - **[kit]** The template's `%Entities` node is cleared by `start_match()`.
- **Loading:**
  - Use `const X := preload(...)` or `@export var scene: PackedScene` for what you spawn during
    play. **[kit]** The lint rule `load-in-loop` flags `load("...")` in per-frame callbacks.
  - Use `load()` only for dynamic paths or big rarely-used assets.
  - Use `ResourceLoader.load_threaded_request/_get_status/_get` for big levels, and only once a
    freeze is actually visible.
- **Prefer `@export var scenes: Array[PackedScene]` to hard-coded `preload("res://...")` lists.**
  The Inspector stores UIDs, so moving a file doesn't break them.

## 3. Communication: call down, signal up, events out

- **A parent calls methods on its children. A child emits signals and never knows its parent.
  Siblings talk through the parent.** Direct references *inside* one encapsulated scene are fine
  (`blaster.fire()`). Across unrelated scenes (Player → HUD) they are the anti-pattern.
- **The receiver subscribes.** The Player emits `health_changed(new: int)`; the HUD connects. The
  Player then works with no HUD, which is exactly how tests run it.
- **Prefer narrow, typed signals to one fat signal** (`health_depleted`, `ammo_changed`, not
  `player_updated(dict)`). Once a payload keeps growing, emit one **event object** (a RefCounted
  with fields), so adding a field doesn't break listeners.
- **Connect runtime-spawned objects in code when you instance them** (`enemy.died.connect(_on_died)`).
  The spawner can **relay**: it listens to each enemy's `died` and re-emits `enemy_defeated(score)`.
  Each layer only talks to its neighbours.
- **Event bus** = an autoload that `extends Node` and holds *only* typed signals (use
  `@warning_ignore("unused_signal")`). No variables, no logic.
  - Use it for **parallel, independent reactions** to cross-tree events (sound, HUD, stats).
  - **One hop:** an event triggers a final reaction, not another event. Put chains in a manager
    that listens once and calls things directly.
  - **Never put order-dependent logic on the bus.** Listener order isn't guaranteed.
  - Critical global events carry `source`/`reason` parameters, so failures are traceable.
  - Components don't emit on the global bus. Their owner relays what matters.
- **Push then pull:** a listener connects first, then reads the current value from the source of
  truth. That way it never misses a value emitted before it connected.
- **Groups are tags, the hierarchy is ownership.** Use semantic names in constants
  (`const GROUP_ENEMY := &"enemy"`). `call_group("x", "method")` fails silently on typos.
  Prefer typed signals for anything non-trivial.
- **`await signal` is for linear sequences** (cutscenes, animations).
  - After an await, check `is_instance_valid()`: the object may be gone.
  - An await on a node that gets freed never resumes. Make sure every awaited thing completes.
- **Notifications are for engine and OS events** (`NOTIFICATION_WM_FOCUS_OUT`,
  `NOTIFICATION_WM_CLOSE_REQUEST`). Signals are for gameplay.

## 4. Autoloads: systems, not state

- **Good autoloads:** audio (pooled players, so sounds aren't cut off by `queue_free`), scene
  loader, network peer, event bus, settings, a save *service* (writes what it is given).
- **Never put match or player state in an autoload.** It survives game over and restart, needs
  hand-written reset code, and breaks with local multiplayer.
  - **[kit contract]** `start_match()` must reset every autoload that holds match state.
  - The best fix is to have no such autoloads: keep that state in a Resource or RefCounted owned
    by the gameplay root, and pass it down.
- **No `Global.gd` / GameManager god object.** Split it into small single-purpose services.
- **Low-level objects don't call autoloads directly** (`GameManager.add_score(10)` in a Coin).
  The coin emits `collected(amount)`, and the owning level wires it to the service. The coin is
  then portable and testable.
- **Service seam for tests:** hold the service in a typed variable that defaults to the autoload
  (`var audio: AudioService = Audio`) or look it up softly (`get_node_or_null("/root/Audio")`).
  A test can then swap in a recording fake.
- **Before adding an autoload, ask whether it really needs to be global.** Alternatives:
  - static funcs for stateless utilities;
  - a shared Resource for one source of truth;
  - the tree for ownership.

## 5. State, strategy, components

- **Refactor into a state machine** when you see:
  - boolean soup (`is_jumping and not is_attacking and ...`);
  - a `match` longer than about 50 lines;
  - an enum+match growing inside `_physics_process`.
- **A state machine made of nodes** (`StateMachine` with `State` children: `enter/exit/update/
  physics_update` plus `signal transition_requested(from: State, to_id: StringName)`):
  - The machine collects the children into a `Dictionary`, enters `initial_state` (an
    `@export`), and delegates the per-frame calls to the current state only.
  - States *request* transitions through the signal. Ignore requests from a state that isn't
    current, so late timers don't cause "ghost" transitions.
  - On a transition, call `exit()` on the old state and then `enter()` on the new one.
  - **[kit contract]** Expose the active state for tests: `state_name()` returns
    `current_state.state_id`, and the machine emits `state_changed(from, to)`.
  - Don't make a state machine for a door. A bool is enough.
- **Strategy = the same job with a swappable algorithm.** Implement it as a Resource with a
  virtual method, and use `@abstract` (Godot 4.5+) for the base class and method:
  ```gdscript
  @abstract class_name AttackPattern extends Resource
  @export var damage := 10
  @abstract func execute(user: Node2D, target: Node2D, world: Node) -> void
  ```
  Resources can't `add_child` or `get_tree`, so pass the world or container in.
- **Components:** single-purpose child nodes with `class_name`, `@export` tuning and signals out.
  They have no external dependencies.
  - A `HealthComponent` emits `died`. It doesn't `queue_free` its owner, play particles or emit
    on the bus.
  - The entity root is a thin "motherboard" that wires its components together in `_ready()`.
  - Hitbox (`Area2D`, physics) and Health (data) are separate. Several hitboxes can feed one
    health pool. The projectile is the active agent: it calls `hitbox.damage(n)`.
  - Guard one-shot events (`if _dead: return`) so `died` doesn't fire twice.
- **Prefer composition to deep inheritance.** Ask "what can it do?" rather than "what is it?".
  Use inheritance only when the subclass overrides behaviour.
- **Liskov:** an override keeps the parent's exact signature and return type. GDScript only
  catches violations at runtime. **[kit]** Strict typing (`untyped_declaration` = error) is your
  main defence.

## 6. Creation, commands, data

- **Factory / spawner:** one generic node does instantiate → choose the container → `add_child`
  → place → emit `product_created(p)` → return `p`.
  - It takes `@export product_scene` and `@export container`.
  - It returns null with `push_error` when misconfigured, so callers must null-check.
  - Decorators can hook into `product_created`.
  - From a physics callback, use `container.add_child.call_deferred(p)`, and set the position
    *before* adding.
- **Builder** (a RefCounted with chained methods that return `self`, then `build()`) is for one
  object that needs about 10 setup steps, such as dynamic UI. A **parameter object** (a
  RefCounted or Resource config with defaults) beats a long argument list.
- **Commands** (RefCounted, `execute(actor)` with the receiver passed in):
  - Input maps InputMap *actions* to commands. The AI produces the same commands.
  - A recorded command stream gives replays, kill-cams, scripted test players and undo.
  - Undo caches the start state inside `execute()`. Cap the history (about 50 entries). Make sure
    every awaited command completes. Check `is_instance_valid(actor)` before a delayed execute.
  - Real-time games execute commands each frame without awaiting. Await-queues are for
    turn-based games.
  - Determinism: a command must carry everything it needs (including delta), and all randomness
    must come from the seeded RNG.
- **Data-driven design:** code says *how* the game works; data says *what* it is.
  - Write one generic `Weapon` script fed by `WeaponStats.tres`, not a `FireSword` class.
  - Game rules ("soft architecture") have no hard-coded numbers: use `velocity = dir * stats.speed`.
- **Prototype pattern:** a shared Resource holds static per-type data. The instance node holds
  per-entity state (`current_health = stats.base_health` in `_ready`).
  - **Never mutate a shared Resource:** one hit would drain all 50 goblins.
  - If a Resource must hold mutable state, `duplicate()` it per instance. Use `duplicate(true)` /
    `duplicate_deep()` (4.5+) for nested data, or set *Local to Scene*.
  - A test that damages one of two instances catches this bug.
- **External data (JSON, mods, saves) is zero-trust.** Check, in order: the file exists, the
  parse returns OK (report the line and message), the root type, each required key, each key's
  type, and ranges.
  - JSON numbers arrive as float, so cast with `int()`.
  - Load with defaults (`data.get("score", 0)`).
  - Save data objects, never node paths. Read mods from `user://mods/`.
  - **[kit]** These `push_error` paths fail tests by design. Tests that feed bad files on purpose
    use `@pytest.mark.allow_engine_errors`.

## 7. Gameplay logic in layers (once the game is bigger than a prototype)

- **Domain:** rules, state machines and maths, in RefCounted/Resource objects, with no tree
  access.
- **Presentation:** dumb nodes that draw what they're told (`show_score(n)`) and forward input.
- **Persistence:** save/load as a stateless service.
- **Data flows down:** data → rules → visuals.
- **Never keep game state in visual nodes** (a ProgressBar's `value`, a Label's text, a cosmetic
  Timer used as a cooldown). Deleting the cosmetic node must not change the rules.
- **A context node creates the state and injects it** (`LevelController.new(level_state)`),
  wiring domain signals to presentation methods. GameplayContext owns the match state privately,
  so the menu can't touch it.
- **Organise folders by feature** (`res://player/`: .tscn, .gd, .png together) and enforce one
  layout.
  - Files are snake_case. A scene's root node is PascalCase. `class_name` matches the file name.

## 8. Engine gotchas from the book (Godot 4.4-4.7)

- **Resources are shared by reference.** `load()`/`preload()` return the cached instance, so
  mutating it changes it everywhere. A shallow `duplicate()` leaves nested resources, arrays and
  dictionaries shared.
- **`_ready` order:** children before parents, siblings in tree order, autoloads before the main
  scene. Don't rely on a sibling's `_ready` having run.
- **Setters fire on every assignment**, including `+=` and `.tres` loading, possibly before
  listeners exist.
- **`queue_free()`d nodes stay in `get_children()` until the end of the frame.** If anything
  counts children, call `remove_child()` first.
- **Typed dictionaries** (`Dictionary[String, State]`) need 4.4+. `@abstract` and variadic
  functions (`func f(...args: Array)`) need 4.5+.
- **`@tool` runs the whole script in the editor.** Guard it with `Engine.is_editor_hint()`, and
  keep `@tool` off gameplay scripts. Configuration warnings don't run headless, so assert
  required exports in a test.
- **A `NOTIFICATION_WM_FOCUS_OUT` → pause handler pauses unfocused test windows.** Skip it
  under the harness.
- **Collision layers and masks:** name them in Project Settings. Filtering happens in C++ before
  any script callback, so it's the cheapest way to cut collision work.
- **The book's own snippets have bugs:**
  - integer division (`hp / 50 * 100`);
  - `died` emitted on every hit at or below 0;
  - `int += int * float`;
  - an `extends Node` class with a required `_init` argument (it can't be instanced from a
    scene).

  Don't copy them literally.
