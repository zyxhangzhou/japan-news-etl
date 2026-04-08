from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT_DIR) if not existing_pythonpath else f"{ROOT_DIR}{os.pathsep}{existing_pythonpath}"
    subprocess.run(command, check=True, cwd=ROOT_DIR, env=env)


def wait_for_query_api(base_url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/api/query",
                json={"query": "今天的AI新闻有哪些"},
                timeout=10,
            )
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise TimeoutError(f"API did not become ready in {timeout_seconds}s")


def main() -> int:
    api_base = os.getenv("E2E_API_BASE", "http://localhost:8081")

    print("[1/3] Starting docker services")
    run(["docker", "compose", "up", "-d"])

    print("[2/3] Running one manual ETL batch")
    run(["uv", "run", "python", "scripts/test_idempotency.py"])

    print("[3/3] Calling query API")
    wait_for_query_api(api_base)
    response = requests.post(
        f"{api_base.rstrip('/')}/api/query",
        json={"query": "今天的日本科技新闻有什么重点？"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    print("answer:", payload.get("answer", "")[:200])
    print("articles:", len(payload.get("articles") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
