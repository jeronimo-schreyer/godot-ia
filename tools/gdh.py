"""Command line for the agent harness. Run from the game's folder.

  python tools/gdh.py run  [--window] [--realtime] [--scene RES] (-c CODE | FILE)
        Starts the game and runs Python with `g` (a gdharness.Game) and `node` in scope.
        Ad-hoc checks and visual inspection without writing a test:
          python tools/gdh.py run --window -c "g.call('/root/Main','start_match',42); print(g.sequence('intro', 8, 10))"
  python tools/gdh.py shot [--scene RES] [--wait SECONDS] [--name NAME]
        Screenshot after a few seconds of game time; prints the PNG path.
  python tools/gdh.py test [pytest args...]
        Runs tests/ with the harness (fast and headless unless a module is marked `window`).
  python tools/gdh.py lint [PATHS...]
        Static checks of the game's GDScript (global RNG, system clock, get_parent()/"../",
        spawning into the root, load() per frame...). Exit 1 on findings. See gdharness/lint.py.
  python tools/gdh.py new DEST --name "Game Name"
        Creates the next game from this one, passing the agent kit (tools/kit.json) on.
  python tools/gdh.py selftest
        Creates a throwaway game from this kit and runs its tests. Run it after changing any
        kit file, so the next game inherits a kit that works.
"""
from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from gdharness import launch, node  # noqa: E402


def cmd_run(a):
    with launch(window=a.window, fast=not a.realtime, scene=a.scene) as g:
        scope = {"g": g, "node": node}
        if a.code:
            exec(a.code, scope)
        else:
            runpy.run_path(a.file, init_globals=scope)
        found = g.errors()
        if found:
            print("ENGINE ERRORS:\n" + "\n".join(f"  {e}" for e in found), file=sys.stderr)
            sys.exit(1)


def cmd_shot(a):
    with launch(window=True, scene=a.scene) as g:
        g.wait(a.wait)
        print(g.screenshot(a.name))


def cmd_test(a, rest):
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests", *rest]))


def cmd_lint(a):
    from gdharness import find_project
    from gdharness.lint import lint
    findings = lint(find_project(), a.paths)
    for f in findings:
        print(f)
    print(f"{len(findings)} finding(s)" if findings else "lint: clean")
    sys.exit(1 if findings else 0)


def cmd_new(a):
    from new_game import create
    create(Path(a.dest), a.name)


def cmd_selftest(a):
    from new_game import selftest
    sys.exit(0 if selftest() else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--window", action="store_true")
    run.add_argument("--realtime", action="store_true")
    run.add_argument("--scene", default="")
    run.add_argument("-c", dest="code")
    run.add_argument("file", nargs="?")
    shot = sub.add_parser("shot")
    shot.add_argument("--scene", default="")
    shot.add_argument("--wait", type=float, default=1.0)
    shot.add_argument("--name", default="shot")
    sub.add_parser("test")
    lint_p = sub.add_parser("lint")
    lint_p.add_argument("paths", nargs="*")
    new = sub.add_parser("new")
    new.add_argument("dest")
    new.add_argument("--name", required=True)
    sub.add_parser("selftest")
    a, rest = parser.parse_known_args()
    if a.cmd == "run":
        if not (a.code or a.file):
            parser.error("run needs -c CODE or a FILE")
        cmd_run(a)
    elif a.cmd == "shot":
        cmd_shot(a)
    elif a.cmd == "test":
        cmd_test(a, rest)
    elif a.cmd == "lint":
        cmd_lint(a)
    elif a.cmd == "new":
        cmd_new(a)
    elif a.cmd == "selftest":
        cmd_selftest(a)


if __name__ == "__main__":
    main()
