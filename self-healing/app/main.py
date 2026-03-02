from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException


@dataclass(frozen=True)
class Settings:
    unstable_fail_first_n: int


def load_settings() -> Settings:
    raw = os.getenv("UNSTABLE_FAIL_FIRST_N", "3").strip()
    try:
        n = int(raw)
    except ValueError as exc:
        raise ValueError("UNSTABLE_FAIL_FIRST_N must be an integer") from exc
    if n < 0:
        raise ValueError("UNSTABLE_FAIL_FIRST_N must be >= 0")
    return Settings(unstable_fail_first_n=n)


settings = load_settings()
app = FastAPI(title="Self-healing demo API", version="0.1.0")

_unstable_lock = threading.Lock()
_unstable_calls = 0

# Simulate failed health on first server start (so CI kills and restarts).
_HEALTH_START_COUNT_LOADED = False
_HEALTH_FAIL_UNTIL: Optional[float] = None
_HEALTH_LOCK = threading.Lock()
_HEALTH_COUNT_FILE = Path(__file__).resolve().parent.parent / "logs" / "health_start_count"


@app.get("/health")
def health() -> dict:
    global _HEALTH_START_COUNT_LOADED, _HEALTH_FAIL_UNTIL
    with _HEALTH_LOCK:
        if not _HEALTH_START_COUNT_LOADED:
            _HEALTH_START_COUNT_LOADED = True
            _HEALTH_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                n = int(_HEALTH_COUNT_FILE.read_text().strip())
            except (FileNotFoundError, ValueError):
                n = 0
            n += 1
            _HEALTH_COUNT_FILE.write_text(str(n))
            if n == 1:
                _HEALTH_FAIL_UNTIL = time.time() + 36  # fail for 36s so runner times out (30s)
            else:
                _HEALTH_FAIL_UNTIL = None
        fail_until = _HEALTH_FAIL_UNTIL
    if fail_until is not None and time.time() < fail_until:
        raise HTTPException(status_code=503, detail="simulated unhealthy (first start)")
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: int) -> dict:
    if item_id < 0:
        raise HTTPException(status_code=400, detail="item_id must be >= 0")
    return {"item_id": item_id, "name": f"item-{item_id}"}


@app.get("/unstable")
def unstable() -> dict:
    """
    Deterministically flaky endpoint: fails the first N calls after process start.
    Useful for demonstrating CI self-healing (test reruns) without randomness.
    """
    global _unstable_calls
    with _unstable_lock:
        _unstable_calls += 1
        call_num = _unstable_calls

    if call_num <= settings.unstable_fail_first_n:
        raise HTTPException(status_code=500, detail="simulated transient failure")

    return {"status": "ok", "call": call_num}
