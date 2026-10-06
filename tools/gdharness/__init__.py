"""gdharness: drive a Godot game from Python, fast and deterministically.

Built on godot-e2e (the transport) plus the AgentProbe autoload (addons/agent_harness).

    from gdharness import launch

    with launch() as g:                       # headless, as fast as the CPU allows
        g.call("/root/Main", "start_match", 42)
        g.wait_until("state_name() == 'RETREAT'", base="/root/Main")
        g.assert_no_errors()

    with launch(window=True) as g:            # rendered, for screenshots
        sheet = g.sequence("explosion", count=8, every=6)

See .claude/skills/godot-agent-dev for the method this was built for.
"""
from .game import Game, GameTimeout, EngineErrors, launch, node, find_project

__all__ = ["Game", "GameTimeout", "EngineErrors", "launch", "node", "find_project"]
