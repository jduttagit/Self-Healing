import os

import httpx
import pytest


def base_url() -> str:
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def test_health() -> None:
    r = httpx.get(f"{base_url()}/health", timeout=5.0)
    r.raise_for_status()
    assert r.json()["status"] == "ok"


def test_get_item() -> None:
    r = httpx.get(f"{base_url()}/items/123", timeout=5.0)
    r.raise_for_status()
    assert r.json() == {"item_id": 123, "name": "item-123"}


@pytest.mark.flaky(reruns=3, reruns_delay=1)  # need 3 reruns when first 3 /unstable calls fail
def test_unstable_eventually_ok() -> None:
    r = httpx.get(f"{base_url()}/unstable", timeout=5.0)
    r.raise_for_status()
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["call"], int)

