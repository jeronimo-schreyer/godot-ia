"""Creates the next game from this one, passing the agent kit on.

    python tools/gdh.py new ../my-game --name "My Game"
    python tools/gdh.py selftest

The kit (paths listed in tools/kit.json) lives inside every game: there is no central copy.
Each game improves its own kit while it's being built; the next game is created from the most
recent one and inherits those improvements. `new` copies tools/template (a minimal game honouring
the testing contract) plus every kit path, records the lineage, writes CLAUDE.md, and imports the
project once so Godot registers its classes. `selftest` proves the kit still produces a working game.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]  # the game this kit lives in
TEXT_SUFFIXES = {".gd", ".tscn", ".godot", ".py", ".md", ".cfg", ".txt"}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.uid", ".pytest_cache")


def kit_manifest(source: Path = SOURCE) -> dict:
    return json.loads((source / "tools" / "kit.json").read_text(encoding="utf-8"))


def create(dest: Path, name: str, source: Path = SOURCE) -> Path:
    """Creates a game in [dest] from the template and the kit of [source] (the current game)."""
    dest = dest.resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} exists and isn't empty")
    kit = kit_manifest(source)

    # 1. The starting game itself.
    shutil.copytree(source / "tools" / "template", dest, dirs_exist_ok=True, ignore=IGNORE)
    for f in dest.rglob("*"):
        if f.is_file() and f.suffix in TEXT_SUFFIXES:
            f.write_text(f.read_text(encoding="utf-8").replace("{{NAME}}", name), encoding="utf-8")

    # 2. The kit, exactly as listed in the manifest.
    for rel in kit["paths"]:
        src, dst = source / rel, dest / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # 3. Lineage and instructions for the agent that will work on the new game.
    kit["lineage"] = kit["lineage"] + [f"{name} ({dest.name})"]
    (dest / "tools" / "kit.json").write_text(json.dumps(kit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    claude_md = (source / "tools" / "CLAUDE.template.md").read_text(encoding="utf-8")
    claude_md = claude_md.replace("{{NAME}}", name).replace("{{LINEAGE}}", " -> ".join(kit["lineage"]))
    (dest / "CLAUDE.md").write_text(claude_md, encoding="utf-8")

    godot = shutil.which("godot") or shutil.which("godot4")
    if godot:
        subprocess.run([godot, "--headless", "--path", str(dest), "--import"], capture_output=True, timeout=300)
    print(f"Created {name} in {dest}")
    print(f"Kit lineage: {' -> '.join(kit['lineage'])}")
    print("Next: open a Claude Code session in that folder and run `python tools/gdh.py test` there.")
    return dest


def selftest(source: Path = SOURCE) -> bool:
    """Checks the kit is fit to pass on: creates a throwaway game from it and runs its tests
    (twice: the first run creates the visual baseline and may only fail because of that)."""
    tmp = Path(tempfile.mkdtemp(prefix="kit-selftest-"))
    try:
        return _selftest_in(tmp, source)
    finally:
        _remove_tree(tmp)


def _selftest_in(tmp: Path, source: Path) -> bool:
    game = create(tmp / "selftest-game", "Selftest", source)
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]
    first = subprocess.run(cmd, cwd=game, capture_output=True, text=True)
    failures = [line for line in first.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    if any("test_visual" not in line for line in failures):
        print(first.stdout[-4000:])
        print("KIT SELFTEST FAILED on the first run")
        return False
    second = subprocess.run(cmd, cwd=game, capture_output=True, text=True)
    if second.returncode != 0:
        print(second.stdout[-4000:] or second.stderr[-4000:])
        print("KIT SELFTEST FAILED")
        return False
    print(second.stdout.strip().splitlines()[-1])
    print("Kit selftest passed: a new game created from this kit builds and passes its tests.")
    return True


def _remove_tree(path: Path) -> None:
    # On Windows a Godot process that just exited can keep files locked for a moment.
    for _ in range(10):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.5)
    print(f"(could not remove {path}; delete it later)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    create(Path(sys.argv[1]), sys.argv[2])
