"""Visual checks: rendered in a window (still fast). Baselines in tests/snapshots/; the first
run creates them and fails so you look at them. Accept intended changes with
`python -m pytest tests/e2e/test_visual.py --update-snapshots`."""
import pytest

pytestmark = pytest.mark.window


def test_start_screen(game):
    game.snapshot("start_screen")
