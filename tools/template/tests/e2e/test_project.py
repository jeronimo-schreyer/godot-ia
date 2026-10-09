"""Project health, generic for any game: everything parses, and every scene runs on its own
(book rule "a scene must not crash because a particular parent is missing")."""
import pytest

from conftest import MAIN

# Scenes that genuinely need a host (state why). The main scene already runs as the game.
NEEDS_A_HOST: set = set()


def test_every_script_scene_and_resource_loads(game):
    assert game.check_project() == []


def test_every_scene_runs_alone(game):
    main_scene = game.eval("ProjectSettings.get_setting('application/run/main_scene')")
    for scene in game.scenes():
        if scene == main_scene or scene in NEEDS_A_HOST:
            continue
        leaked = game.try_scene(scene, frames=10)
        assert leaked == [], f"{scene} left {leaked} under /root (spawn into a container it owns)"
    game.call(MAIN, "start_match", 42)  # the sandboxed scenes may have touched shared state
