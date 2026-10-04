import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
env = {
    **os.environ,
    **{k: v for k, v in dotenv_values(root / ".env").items() if v is not None},
}
env.setdefault(
    "DATABASE_URL", f"sqlite:///{(root / '.local' / 'streamdoctor.db').as_posix()}"
)
env.setdefault("AI_SERVICE_URL", "http://127.0.0.1:9000/analyze")
raise SystemExit(
    subprocess.call(
        [sys.executable, "-m", "app.cli", *sys.argv[1:]], cwd=root / "backend", env=env
    )
)
