"""First tests every game should keep passing. Grow from here."""
from conftest import MAIN


def test_match_starts(game):
    assert game.eval("state_name()", base=MAIN) == "PLAYING"


def test_same_seed_same_start(game):
    first = game.get(MAIN, "player_position")
    game.call(MAIN, "start_match", 42)
    assert game.get(MAIN, "player_position") == first


def test_restart_announces_itself_and_resets_state(game):
    started = game.watch(MAIN, "match_started")
    changed = game.watch(MAIN, "state_changed")
    game.call(MAIN, "debug_win")
    assert changed.last == ["PLAYING", "WON"]
    game.call(MAIN, "start_match", 7)
    assert started.wait() == [[7]]
    assert changed.last == ["WON", "PLAYING"]
    assert game.eval("_entities.get_child_count()", base=MAIN) == 0


def test_player_moves_with_input(game):
    start = game.get(MAIN, "player_position")
    game.hold("move_right", 0.5)
    after = game.get(MAIN, "player_position")
    assert after.x > start.x + 50
