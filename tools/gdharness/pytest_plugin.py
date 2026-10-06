"""pytest integration. Enable it from tests/conftest.py:

    pytest_plugins = ["gdharness.pytest_plugin"]

Fixtures:
    godot          one fast headless game per test module (window if the module/test is
                   marked `window`, or with --window).
Markers:
    window                 the module needs rendering (screenshots, sequences, snapshots).
    allow_engine_errors    don't fail the test when the engine logs errors.
Options:
    --window               render every module (to watch / debug).
    --realtime             don't use --fixed-fps (play at wall-clock speed).
    --update-snapshots     accept the current look for every snapshot() call.

Every test fails if the engine logged an error while it ran: godot-e2e collects script
errors but would let the test pass.
"""
from __future__ import annotations

import os

import pytest

from .game import Game, launch


def pytest_addoption(parser):
    group = parser.getgroup("gdharness")
    group.addoption("--window", action="store_true", help="render every test module in a window")
    group.addoption("--realtime", action="store_true", help="run at wall-clock speed (no --fixed-fps)")
    group.addoption("--update-snapshots", action="store_true", help="accept current snapshots as baselines")


def pytest_configure(config):
    config.addinivalue_line("markers", "window: needs a rendered game (screenshots, snapshots)")
    config.addinivalue_line("markers", "allow_engine_errors: engine errors don't fail the test")
    if config.getoption("--update-snapshots"):
        os.environ["GDH_UPDATE_SNAPSHOTS"] = "1"


_ACTIVE: list[Game] = []


@pytest.fixture(scope="module")
def godot(request):
    window = request.config.getoption("--window") or request.node.get_closest_marker("window") is not None
    with launch(window=window, fast=not request.config.getoption("--realtime")) as game:
        _ACTIVE.append(game)
        try:
            yield game
        finally:
            _ACTIVE.remove(game)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    for game in _ACTIVE:
        game.errors()  # forget whatever happened before this test
    result = yield
    if item.get_closest_marker("allow_engine_errors") is None:
        for game in _ACTIVE:
            game.frames(1)  # logs ride on replies: one round trip collects the last ones
            game.assert_no_errors()
    return result
