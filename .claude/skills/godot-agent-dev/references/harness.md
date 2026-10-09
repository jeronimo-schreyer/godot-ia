# Agent harness reference

Pieces (all copied into new games by `tools/gdh.py new`):

| Piece | Where | Role |
|---|---|---|
| godot-e2e | `addons/godot_e2e` + `pip install godot-e2e` | TCP transport: input, properties, calls, screenshots, engine logs. Dormant without `--e2e`. |
| AgentProbe | `addons/agent_harness` (autoload) | `eval` expressions, node arguments, typed-array assignment, exact-timing frame capture. |
| gdharness | `tools/gdharness` | Python API, pytest plugin, contact sheets, snapshot diffs. |
| gdh CLI | `tools/gdh.py` | `run`, `shot`, `test`, `new`, `selftest`. |
| Kit manifest | `tools/kit.json`, `tools/KIT_CHANGELOG.md` | What travels to the next game, lineage, history of kit changes. |

Requirements: Godot 4.5+ on PATH (or `GODOT_PATH`), Python 3.9+, `pip install godot-e2e pillow pytest`.

## launch()

```python
launch(project=None, *, window=False, fast=True, scene="", ticks_per_second=60,
       log_verbosity="warning", extra_args=(), artifacts=None)
```

| window | fast | Godot args | Use |
|---|---|---|---|
| False | True | `--headless --fixed-fps 60` | logic tests (default, fastest) |
| True | True | `--fixed-fps 60 --disable-vsync` | screenshots, sequences, GUI/mouse tests |
| True | False | (none) | watching at real speed |

Measured on the Worms game, 3 s grenade fuse: real time 3.0 s; headless fast 0.46 s; window
fast 1.1 s; all three land on the identical pixel. `Engine.time_scale = 4` took 0.85 s and
landed 30 px off.

`project` defaults to `$GDH_PROJECT` or the nearest folder with `project.godot`.
Artifacts go to `<project>/screenshots/harness/` (git-ignored, `.gdignore`d).

## Game methods

| Method | Notes |
|---|---|
| `get(path, prop)` | property (godot-e2e types: `Vector2`, `NodePath`, ...) |
| `set(path, prop, value)` | also fills typed arrays (`Array[bool]`), accepts `node(...)` |
| `call(path, method, *args)` | `node("/root/X")` passes a node; nodes return as `{"_node": path}` |
| `eval(expr, base="/root")` | GDScript `Expression` with `base` as self: `"state_name() == 'TURN'"`, `"str(active_worm.get_path())"`; `Engine`, `Input`, `Time`, `OS`, `ProjectSettings`, `DisplayServer` available |
| `exists(path)` | node exists |
| `tree(path="/root", depth=4)` | scene tree as indented text (`%` = unique name, script file shown) |
| `watch(path, signal)` | records every emission in-engine -> `SignalWatch`: `.wait(count, timeout)`, `.count`, `.last`, `.args`, `.emissions` (with physics frame), `.clear()`, `.close()` |
| `check_project()` | loads every .gd/.tscn/.tres/.res outside addons/tools/tests; returns paths that failed (parse errors also fail the test as engine errors) |
| `scenes()` | the game's .tscn paths |
| `try_scene(res, frames=10)` | runs a scene alone under `/root/AgentSandbox`, frees it; returns nodes it leaked under `/root`. Errors (e.g. missing parent) fail the test |
| `frames(n)` / `wait(seconds)` | advance game time (physics frames) |
| `game_time()` | seconds of game time since start |
| `wait_until(cond, timeout, base, every, message)` | `cond`: expression string or Python callable; timeout in game seconds; raises `GameTimeout` |
| `hold(action, seconds)` / `tap(action)` | input actions |
| `errors()` / `assert_no_errors()` | engine errors since last call (script errors, `push_error`) |
| `screenshot(name)` | window only |
| `sequence(name, count, every, columns, crop)` | window only; frames captured in-engine every `every` physics frames; returns contact sheet path |
| `snapshot(name, mask, tolerance, max_ratio)` | window only; compare with `tests/snapshots/<name>.png`; first run creates the baseline and fails for review; diff image on mismatch |
| anything else | falls through to godot-e2e (`press_action`, `input_key`, `input_mouse_button`, `input_mouse_motion`, `click_node`, `find_by_group`, `change_scene`, `wait_for_node`, ...) |

## pytest

```python
# tests/e2e/conftest.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
pytest_plugins = ["gdharness.pytest_plugin"]

@pytest.fixture
def game(godot):            # godot: one process per module
    godot.call("/root/Main", "start_match", 42)
    yield godot
```

- `pytestmark = pytest.mark.window` in modules that need rendering, mouse or GUI clicks.
- `@pytest.mark.allow_engine_errors` for tests that provoke errors on purpose.
- `--window` (render everything, to watch), `--realtime`, `--update-snapshots`.
- The godot-e2e plugin is also loaded and defines its own `game` fixture; a `game` fixture in
  your conftest overrides it.

## CLI

```
python tools/gdh.py run [--window] [--realtime] [--scene RES] (-c CODE | FILE)   # `g`, `node` in scope
python tools/gdh.py shot [--scene RES] [--wait S] [--name N]
python tools/gdh.py test [pytest args]
python tools/gdh.py lint [PATHS]               # static checks, exit 1 on findings
python tools/gdh.py new DEST --name "Game"     # next game, inherits this game's kit
python tools/gdh.py selftest                   # throwaway game from this kit + its tests
```

`run` exits 1 and prints them if the engine logged errors.

## Checks every game gets from the template

| Check | Where | Catches |
|---|---|---|
| Strict typing | `project.godot`: `debug/gdscript/warnings/untyped_declaration=2` | untyped vars/params/returns -> script fails to load -> every test fails (addons are excluded by Godot) |
| `gdh lint` | `tests/test_lint.py` (no Godot) | `global-rng`, `wall-clock`, `time-scale`, `parent-lookup`, `root-spawn`, `load-in-loop`. Deliberate case: `# gdh: allow(rule) reason` on that line |
| Project loads | `tests/e2e/test_project.py` | parse errors, broken `ext_resource`s in any scene/resource, even ones the main scene doesn't use |
| Scenes run alone | same file (`NEEDS_A_HOST` for exceptions) | `get_parent()`/`"../"` dependencies, spawning into `/root` |

## Known limits

- Headless: no rendering (screenshots fail), GUI clicks miss, viewport doesn't track the mouse.
- A command round-trip is ~1 frame; batch questions into one `eval` when polling many things.
- Expressions can't assign; use `set` or a `debug_*` method.
