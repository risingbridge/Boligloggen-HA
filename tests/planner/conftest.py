"""Planner tests run without Home Assistant: import ``planner`` as a top-level package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components" / "boligloggen"))
