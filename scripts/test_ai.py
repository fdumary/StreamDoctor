import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / "backend")]
raise SystemExit(pytest.main([str(root / "ai_agent" / "tests"), "-q"]))
