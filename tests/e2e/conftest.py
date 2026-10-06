"""End-to-end test fixtures (agent harness: tools/gdharness).

One Godot process per test module: headless and fast unless the module is marked `window`.
Every test fails if the engine logged an error during it.
"""
import pytest

MAIN = "/root/Main"
SEED = 42


@pytest.fixture
def game(godot):
    """A fresh, deterministic match for every test."""
    godot.wait_for_node(MAIN, timeout=10.0)
    godot.call(MAIN, "start_match", SEED)
    godot.frames(2)
    yield godot
    for action in ("move_left", "move_right", "move_up", "move_down"):
        godot.input_action(action, False)
