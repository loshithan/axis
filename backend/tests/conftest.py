"""
Shared pytest fixtures for AXIS backend integration tests.
Uses httpx.AsyncClient against the live Docker backend (localhost:8001).
"""
import pytest
import httpx

BASE_URL = "http://localhost:8001"

# ── Reusable constants ────────────────────────────────────────────────────────
SBU_CODE = "hospitals"
DEPT_CODE = "icu"


@pytest.fixture(scope="session")
def client():
    """Synchronous httpx client for the live backend."""
    with httpx.Client(base_url=BASE_URL, timeout=15) as c:
        yield c


@pytest.fixture(scope="session")
def sbu_code():
    return SBU_CODE


@pytest.fixture(scope="session")
def dept_code():
    return DEPT_CODE


@pytest.fixture(scope="session")
def worker_ids(client):
    """Return {name: id} for ICU workers."""
    r = client.get("/meta/workers", params={"sbu_code": SBU_CODE, "department_code": DEPT_CODE})
    assert r.status_code == 200, r.text
    return {w["name"]: w["id"] for w in r.json()}


@pytest.fixture(scope="session")
def shift_type_ids(client):
    """Return {name: id} for ICU shift types."""
    r = client.get("/meta/shift-types", params={"sbu_code": SBU_CODE, "department_code": DEPT_CODE})
    assert r.status_code == 200, r.text
    return {st["name"]: st for st in r.json()}
