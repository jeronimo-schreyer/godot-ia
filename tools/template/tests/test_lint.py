"""Static checks (no Godot): global RNG, system clock, get_parent()/"../", spawning into the root,
load() per frame. Silence a deliberate case on its line: `# gdh: allow(rule) reason`."""
from pathlib import Path

from gdharness.lint import lint

PROJECT = Path(__file__).resolve().parents[1]


def test_gdscript_follows_the_contract():
    findings = lint(PROJECT)
    assert not findings, "\n" + "\n".join(str(f) for f in findings)
