"""
AXIS Workflow Integration Tests
Verifies all 4 requirements from the Shift Management and Swap System spec.

Run from the repo root (backend must be running at localhost:8001):
    cd axis
    pip install pytest httpx
    pytest backend/tests/test_workflows.py -v
"""
import pytest
import httpx
from datetime import date, timedelta

BASE_URL = "http://localhost:8001"
SBU_CODE = "hospitals"
DEPT_CODE = "icu"

# ── Shared helpers ────────────────────────────────────────────────────────────

def get(client: httpx.Client, path: str, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, f"GET {path} → {r.status_code}: {r.text}"
    return r.json()


def post(client: httpx.Client, path: str, body: dict, expected: int = 200):
    r = client.post(path, json=body)
    assert r.status_code == expected, f"POST {path} → {r.status_code}: {r.text}"
    return r.json()


def delete(client: httpx.Client, path: str, expected: int = 200):
    r = client.delete(path)
    assert r.status_code == expected, f"DELETE {path} → {r.status_code}: {r.text}"
    return r.json()


def safe_delete_shift(client: httpx.Client, shift_id: int) -> None:
    """Delete a shift; if blocked by FK (leave request), cancel it first then delete."""
    # Try direct delete
    r = client.delete(f"/schedule/shifts/{shift_id}")
    if r.status_code in (200, 404):
        return
    # FK blocked — cancel the shift so the leave request is orphaned, then retry
    client.put(f"/schedule/shifts/{shift_id}", json={"status": "cancelled"})
    client.delete(f"/schedule/shifts/{shift_id}")


def cleanup_worker_shifts_on_date(
    client: httpx.Client, sbu_code: str, dept_code: str, worker_id: int, date_str: str
) -> None:
    """Remove any existing shifts for a worker on a specific date (idempotent pre-test cleanup)."""
    existing = get(client, "/schedule/shifts",
                   sbu_code=sbu_code, department_code=dept_code,
                   start=date_str, end=date_str)
    for s in existing:
        if s.get("worker_id") == worker_id:
            safe_delete_shift(client, s["id"])


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=20) as c:
        yield c


@pytest.fixture(scope="module")
def workers(client):
    return {w["name"]: w for w in get(client, "/meta/workers",
                                       sbu_code=SBU_CODE, department_code=DEPT_CODE)}


@pytest.fixture(scope="module")
def shift_types(client):
    return {st["name"]: st for st in get(client, "/meta/shift-types",
                                           sbu_code=SBU_CODE, department_code=DEPT_CODE)}


@pytest.fixture(scope="module")
def test_date():
    """A future date unlikely to have conflicts — 60 days out."""
    return (date.today() + timedelta(days=60)).isoformat()


# ═════════════════════════════════════════════════════════════════════════════
# REQ 1 — Shift Templates: 8-hour slots, 40h/week baseline, auto-assign
# ═════════════════════════════════════════════════════════════════════════════

class TestReq1ShiftTemplates:
    """Verify the 8-hour shift structure and auto-assignment logic."""

    def test_icu_shift_types_exist(self, client):
        """All 3 standard 8-hour ICU shift types must be defined."""
        shift_types = get(client, "/meta/shift-types",
                          sbu_code=SBU_CODE, department_code=DEPT_CODE)
        names = [st["name"] for st in shift_types]
        assert any("morning" in n.lower() or "06" in n for n in names), \
            f"No Morning shift type found. Got: {names}"
        assert any("afternoon" in n.lower() or "14" in n for n in names), \
            f"No Afternoon shift type found. Got: {names}"
        assert any("night" in n.lower() or "22" in n for n in names), \
            f"No Night shift type found. Got: {names}"

    def test_shift_types_are_8_hours(self, client):
        """Each shift type must span exactly 8 hours."""
        shift_types = get(client, "/meta/shift-types",
                          sbu_code=SBU_CODE, department_code=DEPT_CODE)
        for st in shift_types:
            sh, sm = map(int, st["start_time"][:5].split(":"))
            eh, em = map(int, st["end_time"][:5].split(":"))
            start_mins = sh * 60 + sm
            end_mins = eh * 60 + em
            diff = (end_mins - start_mins) % (24 * 60)   # handle overnight
            assert diff == 480, (
                f"{st['name']}: expected 8h (480 min), got {diff} min "
                f"({st['start_time']}–{st['end_time']})"
            )

    def test_workers_have_40h_baseline(self, client):
        """
        Nurses must have max_weekly_hours <= 40.
        Doctors may have up to 48h per the seed data config.
        """
        workers = get(client, "/meta/workers",
                       sbu_code=SBU_CODE, department_code=DEPT_CODE)
        assert len(workers) > 0, "No workers found"
        for w in workers:
            limit = 48 if w.get("employee_type") == "doctor" else 40
            assert w["max_weekly_hours"] <= limit, (
                f"{w['name']} ({w.get('employee_type')}) has "
                f"max_weekly_hours={w['max_weekly_hours']} > {limit}"
            )

    def test_auto_assign_fills_empty_slots(self, client, test_date):
        """Schedule generation must fill at least one slot automatically."""
        # Use a date range of 1 day so the result is deterministic
        result = post(client, "/schedule/generate", {
            "sbu_code": SBU_CODE,
            "department_code": DEPT_CODE,
            "date_range_start": test_date,
            "date_range_end": test_date,
            "headcount_per_shift": 1,
            "session_id": "test-req1",
        })
        assert result["total_slots"] > 0, "No slots attempted"
        assert result["filled"] > 0, (
            f"Auto-assign filled 0 slots: {result['reasoning_summary']}"
        )

    def test_manual_shift_creation(self, client, workers, shift_types, test_date):
        """Creating a shift manually must succeed and return the correct worker."""
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        # Clean up any prior test shift for this worker/date
        existing = get(client, "/schedule/shifts", sbu_code=SBU_CODE,
                        department_code=DEPT_CODE, start=test_date, end=test_date)
        for s in existing:
            if s["worker_id"] == worker["id"]:
                delete(client, f"/schedule/shifts/{s['id']}")

        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": test_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })
        assert shift["worker_id"] == worker["id"]
        assert shift["date"] == test_date
        assert shift["status"] == "confirmed"

        # Cleanup
        delete(client, f"/schedule/shifts/{shift['id']}")

    def test_conflict_blocked_for_same_worker_same_day(self, client, workers, shift_types, test_date):
        """A second shift for the same worker on the same day must be rejected (409)."""
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": test_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })

        # Second shift on same day → must be 409
        r = client.post("/schedule/shifts", json={
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": test_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })
        assert r.status_code == 409, f"Expected 409 conflict, got {r.status_code}: {r.text}"

        # Cleanup
        delete(client, f"/schedule/shifts/{shift['id']}")


# ═════════════════════════════════════════════════════════════════════════════
# REQ 2 — Swap/Pending Workflow
# ═════════════════════════════════════════════════════════════════════════════

class TestReq2SwapPendingWorkflow:
    """Verify leave request creation marks the shift as PENDING."""

    def test_leave_request_marks_shift_pending(self, client, workers, shift_types):
        """When a leave request is raised for a shift, that shift's status → pending."""
        leave_date = (date.today() + timedelta(days=61)).isoformat()
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        # Pre-test cleanup — remove any stale shift from a previous run
        cleanup_worker_shifts_on_date(client, SBU_CODE, DEPT_CODE, worker["id"], leave_date)

        # Create a confirmed shift
        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": leave_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })
        shift_id = shift["id"]

        # Create a leave request for that shift
        lr = post(client, "/swap/leave-request", {
            "worker_id": worker["id"],
            "shift_id": shift_id,
            "date": leave_date,
            "reason": "Test leave",
        })
        assert lr["status"] == "pending", f"Leave request not pending: {lr}"

        # The shift must now have status=pending
        shifts = get(client, "/schedule/shifts", sbu_code=SBU_CODE,
                      department_code=DEPT_CODE, start=leave_date, end=leave_date)
        target = next((s for s in shifts if s["id"] == shift_id), None)
        assert target is not None, "Shift not found after leave request"
        assert target["status"] == "pending", (
            f"Shift status expected 'pending', got '{target['status']}'"
        )

        # Cleanup — shift may have FK reference from leave request; use safe delete
        safe_delete_shift(client, shift_id)

    def test_leave_requests_listed_with_pending_status(self, client, workers, shift_types):
        """GET /swap/leave-requests must return the new leave request as pending."""
        leave_date = (date.today() + timedelta(days=62)).isoformat()
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        # Pre-test cleanup
        cleanup_worker_shifts_on_date(client, SBU_CODE, DEPT_CODE, worker["id"], leave_date)

        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": leave_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })

        lr = post(client, "/swap/leave-request", {
            "worker_id": worker["id"],
            "shift_id": shift["id"],
            "date": leave_date,
            "reason": "Test leave listing",
        })

        leave_list = get(client, "/swap/leave-requests",
                          sbu_code=SBU_CODE, department_code=DEPT_CODE, status="pending")
        matching = [item for item in leave_list if item["id"] == lr["id"]]
        assert len(matching) == 1, "Leave request not visible in pending list"
        assert matching[0]["status"] == "pending"

        # Cleanup — shift FK-referenced by leave request
        safe_delete_shift(client, shift["id"])


# ═════════════════════════════════════════════════════════════════════════════
# REQ 3 — OT Validation: weekly-hours data available for warning prompt
# ═════════════════════════════════════════════════════════════════════════════

class TestReq3OTValidation:
    """Verify the backend exposes weekly hours so the UI can trigger the OT warning."""

    def test_ot_workers_endpoint_returns_weekly_hours(self, client):
        """GET /ot/workers must return weekly_hours_used and max_weekly_hours."""
        future_date = (date.today() + timedelta(days=7)).isoformat()
        workers = get(client, "/ot/workers",
                       sbu_code=SBU_CODE, department_code=DEPT_CODE,
                       shift_date=future_date)
        assert isinstance(workers, list), "Expected a list"
        if workers:
            w = workers[0]
            assert "weekly_hours_used" in w, "Missing weekly_hours_used"
            assert "max_weekly_hours" in w, "Missing max_weekly_hours"
            assert "hours_remaining" in w, "Missing hours_remaining"
            assert w["hours_remaining"] == w["max_weekly_hours"] - w["weekly_hours_used"]

    def test_ot_hours_reflect_confirmed_shifts(self, client, workers, shift_types):
        """A worker with a confirmed shift must show >0 weekly_hours_used."""
        future_date = (date.today() + timedelta(days=70)).isoformat()
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        # Ensure no shifts already on that date
        existing = get(client, "/schedule/shifts", sbu_code=SBU_CODE,
                        department_code=DEPT_CODE, start=future_date, end=future_date)
        for s in existing:
            if s["worker_id"] == worker["id"]:
                delete(client, f"/schedule/shifts/{s['id']}")

        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": future_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })

        ot_workers = get(client, "/ot/workers", sbu_code=SBU_CODE,
                          department_code=DEPT_CODE, shift_date=future_date)
        ot_entry = next((w for w in ot_workers if w["id"] == worker["id"]), None)
        assert ot_entry is not None, "Worker not in OT workers list"
        assert ot_entry["weekly_hours_used"] >= 8, (
            f"Expected ≥8h used after one 8h shift, got {ot_entry['weekly_hours_used']}"
        )

        # Cleanup
        delete(client, f"/schedule/shifts/{shift['id']}")


# ═════════════════════════════════════════════════════════════════════════════
# REQ 4 — Status Transitions: Pending → Covered, worker name updated
# ═════════════════════════════════════════════════════════════════════════════

class TestReq4StatusTransitions:
    """Verify the full Pending → Covered transition and data update."""

    def test_swap_resolve_transitions_to_covered(self, client, workers, shift_types):
        """
        Full workflow:
        1. Create shift for worker A
        2. Raise leave request → shift becomes pending
        3. Resolve the swap → leave status becomes covered
        4. Verify resolution summary contains replacement worker name
        """
        resolve_date = (date.today() + timedelta(days=80)).isoformat()
        worker_list = list(workers.values())
        assert len(worker_list) >= 2, "Need at least 2 ICU workers for swap test"
        worker_a = worker_list[0]
        st_entry = next(iter(shift_types.values()))

        # Pre-test cleanup
        cleanup_worker_shifts_on_date(client, SBU_CODE, DEPT_CODE, worker_a["id"], resolve_date)

        # Step 1: Create the shift
        shift = post(client, "/schedule/shifts", {
            "worker_id": worker_a["id"],
            "shift_type_id": st_entry["id"],
            "date": resolve_date,
            "start_time": st_entry["start_time"],
            "end_time": st_entry["end_time"],
            "status": "confirmed",
        })

        # Step 2: Leave request
        lr = post(client, "/swap/leave-request", {
            "worker_id": worker_a["id"],
            "shift_id": shift["id"],
            "date": resolve_date,
            "reason": "Test swap resolve",
        })

        # Step 3: Resolve
        result = post(client, "/swap/resolve", {"leave_request_id": lr["id"]})

        # Step 4: Assertions
        if result.get("status") == "resolved":
            assert result["replacement_worker_id"] != worker_a["id"], \
                "Replacement must be a different worker"
            assert result["replacement_worker_name"], "Replacement worker name must not be empty"

            # Leave request itself must now show as covered
            leave_list = get(client, "/swap/leave-requests",
                              sbu_code=SBU_CODE, department_code=DEPT_CODE, status="covered")
            matched = [l for l in leave_list if l["id"] == lr["id"]]
            assert len(matched) == 1, "Leave request not visible in covered list"
            assert matched[0]["status"] == "covered"
        else:
            # No eligible candidate found — shift should now be open (escalated)
            shifts = get(client, "/schedule/shifts", sbu_code=SBU_CODE,
                          department_code=DEPT_CODE, start=resolve_date, end=resolve_date)
            original = next((s for s in shifts if s["id"] == shift["id"]), None)
            if original:
                assert original["status"] in ("open", "swapped"), \
                    f"Expected open or swapped after failed resolve, got {original['status']}"

    def test_shift_status_update_reflected_in_list(self, client, workers, shift_types):
        """Updating a shift's status via PUT must be visible in GET /schedule/shifts."""
        update_date = (date.today() + timedelta(days=90)).isoformat()
        worker = next(iter(workers.values()))
        st = next(iter(shift_types.values()))

        shift = post(client, "/schedule/shifts", {
            "worker_id": worker["id"],
            "shift_type_id": st["id"],
            "date": update_date,
            "start_time": st["start_time"],
            "end_time": st["end_time"],
            "status": "confirmed",
        })

        r = client.put(f"/schedule/shifts/{shift['id']}", json={"status": "cancelled"})
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"

        updated = get(client, "/schedule/shifts", sbu_code=SBU_CODE,
                       department_code=DEPT_CODE, start=update_date, end=update_date)
        target = next((s for s in updated if s["id"] == shift["id"]), None)
        assert target is not None
        assert target["status"] == "cancelled", f"Expected cancelled, got {target['status']}"

        # Cleanup
        delete(client, f"/schedule/shifts/{shift['id']}")
