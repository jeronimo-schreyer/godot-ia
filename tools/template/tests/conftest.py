"""Top-level test config: loads the agent harness (tools/gdharness) for every test folder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

pytest_plugins = ["gdharness.pytest_plugin"]
