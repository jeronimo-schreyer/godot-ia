"""The Game handle: a thin, agent-friendly layer over a godot-e2e connection."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Union

from godot_e2e import GodotE2E

from . import visual

PROBE = "/root/AgentProbe"
NODE_TAG = "_node"
# godot-e2e's client gives up on a reply after 2 s, which breaks any wait longer than that.
SOCKET_TIMEOUT = 120.0


class GameTimeout(AssertionError):
    """A wait_until condition didn't become true in time (game seconds)."""


class EngineErrors(AssertionError):
    """The engine logged errors (script errors, push_error...) that nobody expected."""


def node(path: str) -> dict:
    """Marks an argument as a node reference: g.call(ai, "predict", node(worm_path), ...)."""
    return {NODE_TAG: path}


def find_project(start: Union[str, Path, None] = None) -> Path:
    """The Godot project folder: $GDH_PROJECT, or the first folder with project.godot found
    walking up from [start] (default: the current directory)."""
    env = os.environ.get("GDH_PROJECT")
    if env:
        return Path(env).resolve()
    here = Path(start or os.getcwd()).resolve()
    for folder in [here, *here.parents]:
        if (folder / "project.godot").exists():
            return folder
    raise FileNotFoundError(f"no project.godot in {here} or its parents (set GDH_PROJECT)")


@contextmanager
def launch(project=None, *, window: bool = False, fast: bool = True, scene: str = "",
           ticks_per_second: int = 60, log_verbosity: str = "warning", extra_args: Iterable[str] = (),
           artifacts: Union[str, Path, None] = None):
    """Starts the game and yields a [Game].

    window: False runs headless (no rendering: screenshots impossible, fastest).
    fast:   --fixed-fps: every frame advances exactly 1/ticks_per_second of game time and the
            engine doesn't wait for real time, so results are identical to normal speed but
            arrive several times sooner. Don't use Engine.time_scale for this: it enlarges the
            physics step and changes the outcome of the simulation.
    scene:  res:// scene to start with instead of the main scene.
    """
    project = Path(project).resolve() if project else find_project()
    args = [] if window else ["--headless"]
    if fast:
        args += ["--fixed-fps", str(ticks_per_second)]
        if window:
            args.append("--disable-vsync")
    args += list(extra_args)
    if scene:
        args.append(scene)
    client = GodotE2E.launch(str(project), extra_args=args, log_verbosity=log_verbosity)
    client._client._sock.settimeout(SOCKET_TIMEOUT)
    game = Game(client, project, window=window, ticks_per_second=ticks_per_second,
                artifacts=Path(artifacts) if artifacts else project / "screenshots" / "harness")
    try:
        yield game
    finally:
        client.close()


class Game:
    """Every method waits in *game* time (physics frames), never in wall-clock time, so tests
    behave the same in fast and real-time mode. Unknown attributes fall through to the
    godot-e2e client (press_action, input_key, click_node, find_by_group, ...)."""

    def __init__(self, client: GodotE2E, project: Path, *, window: bool, ticks_per_second: int, artifacts: Path):
        self.e2e = client
        self.project = project
        self.window = window
        self.tps = ticks_per_second
        self.artifacts = artifacts
        self.snapshot_dir = project / "tests" / "snapshots"
        self.update_snapshots = os.environ.get("GDH_UPDATE_SNAPSHOTS") == "1"

    def __getattr__(self, name):
        return getattr(self.e2e, name)

    # --- Reading and changing the game ---------------------------------------------------

    def get(self, path: str, prop: str):
        return self.e2e.get_property(path, prop)

    def set(self, path: str, prop: str, value) -> None:
        """Like set_property, but accepts node(...) values and fills typed arrays."""
        self.e2e.call(PROBE, "set_value", [path, prop, value])

    def call(self, path: str, method: str, *args):
        """Calls a method. Pass nodes with node(path); nodes in the result come back as
        {"_node": path}."""
        return self.e2e.call(PROBE, "invoke", [path, method, list(args)])

    def eval(self, expression: str, base: str = "/root"):
        """Evaluates a GDScript Expression with the node at [base] as `self`, e.g.
        g.eval("teams.size() == 2 and state_name() == 'TURN'", base="/root/Main")."""
        return self.e2e.call(PROBE, "eval", [expression, base])

    def exists(self, path: str) -> bool:
        return self.e2e.node_exists(path)

    def tree(self, path: str = "/root", depth: int = 4) -> str:
        """The scene tree under [path] as indented text ("Name (Type) script.gd"; % marks
        scene-unique names). Print it to check structure or what a spawner left behind."""
        return self.e2e.call(PROBE, "tree", [path, depth])

    # --- Signals ----------------------------------------------------------------------------

    def watch(self, path: str, signal: str) -> "SignalWatch":
        """Starts recording a signal (args + frame of every emission). Event-driven games
        expose what happened as signals: wait on them instead of polling state.
            w = g.watch("/root/Main", "match_started"); ...; w.wait(); assert w.last == [7]"""
        key = self.e2e.call(PROBE, "watch_signal", [path, signal])
        if not key:
            raise ValueError(f"can't watch {path}:{signal} (see engine errors)")
        return SignalWatch(self, key)

    # --- Project health (book rule: every scene runs on its own) --------------------------

    def check_project(self) -> list:
        """Loads every script, scene and resource of the game (not addons/tools/tests). Parse
        errors and broken references become engine errors; returns the paths that failed."""
        return list(self.e2e.call(PROBE, "load_all", ["res://"]))

    def scenes(self) -> list:
        """res:// paths of the game's .tscn files."""
        return list(self.e2e.call(PROBE, "scene_files", ["res://"]))

    def try_scene(self, scene: str, frames: int = 10) -> list:
        """Runs [scene] alone under /root/AgentSandbox for [frames] physics frames, then frees it.
        A well-built scene works without a particular parent (no get_parent()/"../" lookups).
        Engine errors raised meanwhile fail the test as usual; returns the names of nodes the
        scene left directly under /root (they would survive a restart)."""
        if not self.e2e.call(PROBE, "isolate_scene", [scene]):
            raise ValueError(f"can't instance {scene}")
        self.frames(frames)
        leaked = list(self.e2e.call(PROBE, "end_isolation", []))
        self.frames(1)
        return leaked

    # --- Time -------------------------------------------------------------------------------

    def frames(self, count: int = 1) -> None:
        """Advances [count] physics frames."""
        while count > 0:
            step = min(count, 600)
            self.e2e.wait_physics_frames(step)
            count -= step

    def wait(self, seconds: float) -> None:
        """Advances [seconds] of game time."""
        self.frames(max(1, round(seconds * self.tps)))

    def game_time(self) -> float:
        return self.e2e.call(PROBE, "physics_frames", []) / self.tps

    def wait_until(self, condition: Union[str, Callable[[], object]], timeout: float = 10.0,
                   base: str = "/root", every: int = 3, message: str = ""):
        """Polls [condition] every [every] physics frames until it's truthy and returns its
        value. [condition] is a GDScript expression (evaluated with [base] as self) or a Python
        callable. [timeout] is in game seconds."""
        check = condition if callable(condition) else (lambda: self.eval(condition, base))
        deadline = self.game_time() + timeout
        value = check()
        while not value:
            if self.game_time() >= deadline:
                raise GameTimeout(message or f"still false after {timeout}s of game time: {condition!r}")
            self.frames(every)
            value = check()
        return value

    def hold(self, action: str, seconds: float) -> None:
        self.e2e.input_action(action, True)
        self.wait(seconds)
        self.e2e.input_action(action, False)

    def tap(self, action: str) -> None:
        self.e2e.press_action(action)

    # --- Engine errors ---------------------------------------------------------------------

    def errors(self, clear: bool = True) -> list:
        """Errors the engine logged since the last call (script errors, push_error, ...).
        godot-e2e collects them, but a test passes anyway unless someone looks."""
        client = self.e2e._client
        found = [entry for entry in client.collected_logs if entry.level == "error"]
        if clear:
            client.reset_collected_logs()
        return found

    def assert_no_errors(self) -> None:
        found = self.errors()
        if found:
            raise EngineErrors("engine logged errors:\n" + "\n".join(f"  {e}" for e in found))

    # --- Pictures ---------------------------------------------------------------------------

    def screenshot(self, name: str) -> Path:
        """Saves the current frame as <artifacts>/<name>.png (needs window=True)."""
        self._need_window("screenshot")
        path = self.artifacts / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.e2e.screenshot(str(path))
        return path

    def sequence(self, name: str, count: int = 8, every: int = 6, columns: int = 4,
                 crop: tuple = None) -> Path:
        """Captures [count] frames, one every [every] physics frames (timed inside the engine,
        so the spacing is exact), and composes them into a labelled contact sheet. Returns the
        sheet's path; the individual frames sit next to it in <name>/. Use it to *look* at
        motion: a single screenshot hides most movement bugs."""
        self._need_window("sequence")
        folder = self.artifacts / name
        for old in folder.glob("*.png") if folder.exists() else []:
            old.unlink()
        start = self.game_time()
        self.e2e.call(PROBE, "capture_sequence", [str(folder), count, every])
        self.frames(1)
        while self.get(PROBE, "sequence_running"):
            self.frames(every)
        files = sorted(folder.glob("*.png"))
        labels = [f"#{i}  t+{i * every / self.tps:.2f}s" for i in range(len(files))]
        return visual.contact_sheet(files, self.artifacts / f"{name}.sheet.png", labels=labels,
                                    columns=columns, crop=crop, title=f"{name}  (from t={start:.2f}s)")

    def snapshot(self, name: str, mask: Iterable[tuple] = (), tolerance: int = 24,
                 max_ratio: float = 0.001) -> Path:
        """Compares the current frame with tests/snapshots/<name>.png.

        mask:      (x, y, w, h) screen rectangles to ignore (timers, animated bits).
        tolerance: per-channel difference (0-255) below which a pixel counts as equal.
        max_ratio: fraction of differing pixels allowed.
        A missing baseline is created (and the call fails so it gets reviewed); set
        GDH_UPDATE_SNAPSHOTS=1 (pytest --update-snapshots) to accept the current look.
        On mismatch, <artifacts>/snapshots/<name>.diff.png shows base | new | changes."""
        current = self.screenshot(f"snapshots/{name}")
        baseline = self.snapshot_dir / f"{name}.png"
        if self.update_snapshots or not baseline.exists():
            existed = baseline.exists()
            visual.save_copy(current, baseline)
            if not existed and not self.update_snapshots:
                raise AssertionError(f"new snapshot {baseline} created: review it, then re-run")
            return baseline
        result = visual.compare(baseline, current, mask=list(mask), tolerance=tolerance,
                                diff_path=self.artifacts / "snapshots" / f"{name}.diff.png")
        if result.ratio > max_ratio:
            raise AssertionError(f"snapshot {name!r} differs in {result.ratio:.3%} of pixels "
                                 f"(allowed {max_ratio:.3%}); see {result.diff_path}")
        return baseline

    def _need_window(self, what: str) -> None:
        if not self.window:
            raise RuntimeError(f"{what} needs a rendered game: launch(window=True) / pytest mark 'window'")


class SignalWatch:
    """Emissions of one signal, recorded in-engine from the moment Game.watch() was called."""

    def __init__(self, game: Game, key: str):
        self.game = game
        self.key = key

    @property
    def emissions(self) -> list:
        """[{"frame": physics frame, "args": [...]}, ...]"""
        return self.game.e2e.call(PROBE, "signal_log", [self.key, False])

    @property
    def count(self) -> int:
        return len(self.emissions)

    @property
    def args(self) -> list:
        """The arguments of every emission, oldest first."""
        return [e["args"] for e in self.emissions]

    @property
    def last(self):
        """Arguments of the latest emission (None if it never fired)."""
        found = self.emissions
        return found[-1]["args"] if found else None

    def wait(self, count: int = 1, timeout: float = 10.0, every: int = 1) -> list:
        """Waits (game time) until the signal fired at least [count] times in total; returns
        the arguments of every emission so far."""
        self.game.wait_until(lambda: self.count >= count, timeout=timeout, every=every,
                             message=f"{self.key} fired {self.count} of {count} times in {timeout}s")
        return self.args

    def clear(self) -> None:
        self.game.e2e.call(PROBE, "signal_log", [self.key, True])

    def close(self) -> None:
        self.game.e2e.call(PROBE, "unwatch_signal", [self.key])
