"""AppTest entry point for Causal Evidence & Experimentation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "app", ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from views.causal_evidence import render

render()
