from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELF_HEALING_DIR = PROJECT_ROOT / "self-healing"
LOGS_DIR = SELF_HEALING_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_LOG = LOGS_DIR / "server.log"
TEST_LOG = LOGS_DIR / "tests.log"

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def start_server() -> subprocess.Popen:
    """
    Start the FastAPI app via uvicorn in a subprocess.
    """
    env = os.environ.copy()
    env.setdefault("UNSTABLE_FAIL_FIRST_N", "3")  # fail first 3 calls to /unstable

    SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
    server_log_fh = SERVER_LOG.open("ab", buffering=0)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    print(f"Starting server: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(SELF_HEALING_DIR),
        env=env,
        stdout=server_log_fh,
        stderr=subprocess.STDOUT,
    )
    return proc


def stop_server(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return

    print("Stopping server...", flush=True)
    try:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            pass
        proc.kill()
    except Exception:
        proc.kill()


def wait_for_health(timeout_seconds: float = 30.0, poll_interval: float = 1.0) -> bool:
    """
    Poll the /health endpoint until it returns 200 or timeout.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            r = httpx.get(f"{API_BASE_URL}/health", timeout=3.0)
            if r.status_code == 200:
                print("Health check passed.", flush=True)
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    print("Health check did not pass before timeout.", flush=True)
    return False


def run_pytest() -> int:
    """
    Run pytest with rerun support and log output to file.
    """
    env = os.environ.copy()
    env.setdefault("API_BASE_URL", API_BASE_URL)

    TEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TEST_LOG.open("wb") as fh:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "self-healing/tests",
            "-q",
        ]
        print(f"Running tests: {' '.join(cmd)}", flush=True)
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
        return proc.wait()


def main() -> int:
    max_server_restarts = 3
    attempt = 0
    server_proc: Optional[subprocess.Popen] = None

    try:
        while attempt < max_server_restarts:
            attempt += 1
            print(f"=== Server start attempt {attempt}/{max_server_restarts} ===")
            server_proc = start_server()

            if not wait_for_health(timeout_seconds=30.0, poll_interval=1.0):
                print("Server failed health check; stopping and will retry.", flush=True)
                stop_server(server_proc)
                backoff = min(5 * attempt, 30)
                print(f"Backing off for {backoff} seconds before restart.", flush=True)
                time.sleep(backoff)
                continue

            # Server is healthy; run tests once and break out of restart loop.
            exit_code = run_pytest()
            if exit_code == 0:
                print("Tests succeeded.", flush=True)
            else:
                print(f"Tests failed with exit code {exit_code}.", flush=True)
            return exit_code

        print("Exceeded maximum server restart attempts. Marking CI run as failed.", flush=True)
        return 1
    finally:
        stop_server(server_proc)


if __name__ == "__main__":
    raise SystemExit(main())

