import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Run the StreamDoctor local workspace")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    npm = shutil.which("npm")
    if not npm:
        parser.error("Install Node.js 24 and run npm ci --prefix frontend first.")
    env = {
        **os.environ,
        **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None},
    }
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    env.setdefault("AI_SERVICE_URL", "http://127.0.0.1:9000/analyze")
    if args.demo:
        demo = local / "demo"
        if not demo.exists():
            subprocess.run(
                [sys.executable, "-m", "app.demo", "--directory", str(demo)],
                cwd=ROOT / "backend",
                env=env,
                check=True,
            )
        env.update(
            {k: v for k, v in dotenv_values(demo / "demo.env").items() if v is not None}
        )
        print(f"Synthetic demo accounts: {demo / 'credentials.json'}", flush=True)
    else:
        env.setdefault(
            "DATABASE_URL", f"sqlite:///{(local / 'streamdoctor.db').as_posix()}"
        )
        env.setdefault("UPLOAD_DIR", str(local / "photos"))
        env.setdefault("AI_MODE", "http")
        if env["AI_MODE"] == "http" and not env.get("GEMINI_API_KEY", "").strip():
            parser.error(
                "Set GEMINI_API_KEY in the root .env, or use --demo for synthetic mock analysis."
            )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=env,
            check=True,
        )
    env["AI_SERVICE_TOKEN"] = env.get("AI_SERVICE_TOKEN") or secrets.token_urlsafe(32)
    env["API_PROXY_TARGET"] = "http://127.0.0.1:8000"
    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT / "backend",
        ),
        ([npm, "run", "dev", "--", "--host", "127.0.0.1"], ROOT / "frontend"),
    ]
    if env["AI_MODE"] == "http":
        commands.insert(
            0,
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "ai_agent.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "9000",
                ],
                ROOT,
            ),
        )
    children = []
    try:
        for command, cwd in commands:
            children.append(subprocess.Popen(command, cwd=cwd, env=env))
        print(
            "StreamDoctor: http://127.0.0.1:5173 | API docs: http://127.0.0.1:8000/docs",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise SystemExit("A service stopped; check the output above.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
