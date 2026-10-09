"""Static checks for GDScript that break the testing contract or the architecture rules in
.claude/skills/godot-agent-dev/references/architecture.md. Plain text matching: fast, no Godot.

    python tools/gdh.py lint            # the game's scripts (not addons/, tools/, tests/)
    python tools/gdh.py lint path.gd    # specific files or folders

Silence one line deliberately with a trailing comment naming the rule and saying why:
    seed_value = randi()  # gdh: allow(global-rng) picking a random seed is the point

Typing is enforced by Godot itself (project setting debug/gdscript/warnings/untyped_declaration
= error), not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {"addons", "tools", "tests", "screenshots", ".godot", ".git", ".claude", ".agents"}
ALLOW = re.compile(r"#\s*gdh:\s*allow\(([\w\-, ]+)\)")

# Rules that need to see string contents (node paths, resource paths); the others ignore them.
READS_STRINGS = {"parent-lookup", "load-in-loop"}
# rule -> (pattern, why / what to do instead)
RULES = {
    "global-rng": (
        re.compile(r"(?<![\w.])(randf|randi|randf_range|randi_range|randfn|randomize|seed)\s*\(|"
                   r"\.(pick_random|shuffle)\s*\("),
        "global RNG: results change between runs with the same seed. Use the match's seeded "
        "RandomNumberGenerator (rng.randi_range, arr[rng.randi() % arr.size()]).",
    ),
    "wall-clock": (
        re.compile(r"\bTime\.get_(ticks_msec|ticks_usec|unix_time\w*|datetime\w*)\s*\(|\bOS\.get_ticks"),
        "system clock in game logic: animations/timers differ between runs and in --fixed-fps. "
        "Accumulate delta instead (budgets for AI thinking time are a legitimate allow).",
    ),
    "time-scale": (
        re.compile(r"\bEngine\.time_scale\s*[+\-*/]?="),
        "Engine.time_scale enlarges the physics step and changes results; tests use --fixed-fps.",
    ),
    "parent-lookup": (
        re.compile(r"\bget_parent\s*\(\s*\)|(get_node(_or_null)?|NodePath)\s*\(\s*\"\.\.|\$\"?\.\./"),
        "reaching up/sideways the tree couples the scene to one parent (breaks running it alone). "
        "Call down, signal up: emit a signal, or receive the reference via @export / a setup method.",
    ),
    "root-spawn": (
        re.compile(r"get_tree\s*\(\s*\)\s*\.\s*(root|current_scene)\s*\.\s*(add_child|call_deferred)"),
        "spawning into the root/current scene: the node outlives the level and survives "
        "start_match(). Add it to a container the level owns (and clears on restart).",
    ),
    "load-in-loop": (
        re.compile(r"(?<![\w.])load\s*\(\s*\""),
        "load() with a constant path inside a per-frame callback hitches. Use a preload() const "
        "or an @export var scene: PackedScene.",
    ),
}
PER_FRAME = re.compile(r"^func\s+(_process|_physics_process|_draw|_input|_unhandled_input)\b")
FUNC = re.compile(r"^(static\s+)?func\s")


@dataclass
class Finding:
    path: Path
    line: int
    rule: str
    text: str
    why: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.text.strip()}\n    -> {self.why}"


def _split_code(line: str) -> tuple[str, str]:
    """(code without the trailing comment, same with string contents blanked)."""
    out, blank, quote = [], [], None
    for ch in line:
        if quote:
            out.append(ch)
            blank.append(ch if ch == quote else "_")
            if ch == quote:
                quote = None
            continue
        if ch == "#":
            break
        out.append(ch)
        blank.append(ch)
        if ch in "\"'":
            quote = ch
    return "".join(out), "".join(blank)


def lint_file(path: Path) -> list[Finding]:
    findings = []
    in_per_frame = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FUNC.match(raw):
            in_per_frame = bool(PER_FRAME.match(raw))
        code, code_no_strings = _split_code(raw)
        if not code.strip():
            continue
        allowed = set()
        m = ALLOW.search(raw)
        if m:
            allowed = {r.strip() for r in m.group(1).split(",")}
        for rule, (pattern, why) in RULES.items():
            if rule in allowed:
                continue
            if rule == "load-in-loop" and not in_per_frame:
                continue
            if pattern.search(code if rule in READS_STRINGS else code_no_strings):
                findings.append(Finding(path, number, rule, raw, why))
    return findings


def game_scripts(project: Path) -> list[Path]:
    out = []
    for path in sorted(project.rglob("*.gd")):
        rel = path.relative_to(project).parts
        if any(part in SKIP_DIRS for part in rel[:-1]):
            continue
        if any((project.joinpath(*rel[:i]) / ".gdignore").exists() for i in range(1, len(rel))):
            continue
        out.append(path)
    return out


def lint(project: Path, targets=()) -> list[Finding]:
    files = []
    for target in targets or [project]:
        target = Path(target)
        if target.is_dir():
            files += game_scripts(target.resolve())
        else:
            files.append(target)
    findings = []
    for f in files:
        findings += lint_file(f)
    return findings
