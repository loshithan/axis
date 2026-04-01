"""
AXIS Agent Tool Definitions
LangChain tool wrappers that call the FastAPI backend endpoints.
These are the tools the AI agents have access to.
"""
import os

import httpx
from langchain_core.tools import tool
from typing import Optional

API_BASE = os.getenv("AXIS_API_BASE", "http://localhost:8001")


@tool
def get_available_staff(
    sbu_code: str,
    department_code: str,
    date: str,
    shift_type_id: int,
    required_certifications: list[str] = []
) -> dict:
    """Get eligible workers for a shift slot.
    
    Args:
        sbu_code: The SBU code (e.g., "hospitals", "mobility")
        department_code: Department code (e.g., "icu", "ground_crew")
        date: Date in YYYY-MM-DD format
        shift_type_id: ID of the shift type to fill
        required_certifications: List of required certification codes
    
    Returns:
        List of eligible workers with availability, certifications, weekly hours, and fairness scores.
    """
    response = httpx.post(f"{API_BASE}/tools/get-available-staff", json={
        "sbu_code": sbu_code,
        "department_code": department_code,
        "date": date,
        "shift_type_id": shift_type_id,
        "required_certifications": required_certifications
    })
    return response.json()


@tool
def validate_schedule(
    worker_id: int,
    shift_type_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> dict:
    """Validate a proposed shift assignment against all business rules.
    
    Checks overlap detection, availability, weekly hours cap, minimum rest period,
    and certification matching. Returns pass/fail with a plain-English reason.
    
    Args:
        worker_id: The worker to validate
        shift_type_id: The shift type being assigned
        date: Date in YYYY-MM-DD format
        start_time: Shift start time in HH:MM format
        end_time: Shift end time in HH:MM format
    
    Returns:
        Validation result with is_valid boolean and reason string.
    """
    response = httpx.post(f"{API_BASE}/tools/validate-schedule", json={
        "worker_id": worker_id,
        "shift_type_id": shift_type_id,
        "date": date,
        "start_time": start_time,
        "end_time": end_time
    })
    return response.json()


@tool
def create_shift(
    worker_id: int,
    shift_type_id: int,
    date: str,
    start_time: str,
    end_time: str,
    explanation: str = "",
    confirmed: bool = False
) -> dict:
    """Create a shift assignment in the database.
    
    Args:
        worker_id: The worker being assigned
        shift_type_id: The shift type
        date: Date in YYYY-MM-DD format
        start_time: Shift start in HH:MM format
        end_time: Shift end in HH:MM format
        explanation: Plain-English explanation for the assignment
        confirmed: If True, mark as confirmed immediately
    
    Returns:
        Shift record with coverage statistics.
    """
    response = httpx.post(f"{API_BASE}/tools/create-shift", json={
        "worker_id": worker_id,
        "shift_type_id": shift_type_id,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "explanation": explanation,
        "confirmed": confirmed
    })
    return response.json()


@tool
def find_swap_candidates(shift_id: int) -> dict:
    """Find ranked eligible workers to cover a specific shift.
    
    Used by the Swap Agent when a worker submits a leave request.
    Returns workers ranked by availability and fairness score.
    
    Args:
        shift_id: The shift that needs coverage
    
    Returns:
        Ranked list of swap candidates with risk assessment.
    """
    response = httpx.post(f"{API_BASE}/tools/find-swap-candidates", json={
        "shift_id": shift_id
    })
    return response.json()


@tool
def notify_worker(
    worker_id: int,
    notification_type: str,
    subject: str,
    message: str,
    shift_id: Optional[int] = None
) -> dict:
    """Send notification to a worker (push + email).
    
    Args:
        worker_id: Worker to notify
        notification_type: One of "assignment", "swap", "schedule_change"
        subject: Notification subject
        message: Notification body
        shift_id: Related shift ID (optional)
    
    Returns:
        Confirmation of email and push delivery.
    """
    response = httpx.post(f"{API_BASE}/tools/notify-worker", json={
        "worker_id": worker_id,
        "notification_type": notification_type,
        "subject": subject,
        "message": message,
        "shift_id": shift_id
    })
    return response.json()


@tool
def notify_manager(
    department_code: str,
    subject: str,
    summary: str,
    related_shift_ids: list[int] = [],
    manager_id: Optional[int] = None
) -> dict:
    """Notify the department manager of a resolution or update.
    
    Args:
        department_code: Department code to find the manager
        subject: Notification subject
        summary: Resolution summary
        related_shift_ids: Related shift IDs
        manager_id: Specific manager ID (optional, defaults to dept manager)
    
    Returns:
        Notification confirmation.
    """
    response = httpx.post(f"{API_BASE}/tools/notify-manager", json={
        "department_code": department_code,
        "subject": subject,
        "summary": summary,
        "related_shift_ids": related_shift_ids,
        "manager_id": manager_id
    })
    return response.json()


@tool
def escalate_to_manager(
    shift_type_id: int,
    date: str,
    conflict_description: str,
    agent_reasoning: str,
    attempted_candidates: list[dict] = []
) -> dict:
    """Escalate an unresolvable scheduling conflict to the manager.
    
    Called when no valid candidate can be found for a shift slot.
    Includes the agent's full reasoning so the manager understands what was tried.
    
    Args:
        shift_type_id: The shift type that couldn't be filled
        date: The date in YYYY-MM-DD format
        conflict_description: What the conflict is
        agent_reasoning: Full explanation of what the agent tried
        attempted_candidates: List of candidates tried and why they failed
    
    Returns:
        Escalation record with ID.
    """
    response = httpx.post(f"{API_BASE}/tools/escalate-to-manager", json={
        "shift_type_id": shift_type_id,
        "date": date,
        "conflict_description": conflict_description,
        "agent_reasoning": agent_reasoning,
        "attempted_candidates": attempted_candidates
    })
    return response.json()


@tool
def explain_decision(
    worker_id: int,
    shift_id: int,
    assignment_context: dict,
    reasoning_trace: list[dict]
) -> dict:
    """Generate and store a natural language explanation for an assignment.
    
    Uses Claude to produce a human-readable explanation from the agent's
    reasoning trace. Stored as part of the audit trail.
    
    Args:
        worker_id: The assigned worker
        shift_id: The shift assignment
        assignment_context: What slot was being filled, who else was considered
        reasoning_trace: Steps the agent took to reach this decision
    
    Returns:
        The generated explanation text.
    """
    response = httpx.post(f"{API_BASE}/tools/explain-decision", json={
        "worker_id": worker_id,
        "shift_id": shift_id,
        "assignment_context": assignment_context,
        "reasoning_trace": reasoning_trace
    })
    return response.json()


# ── Tool Registry ──

SCHEDULER_TOOLS = [
    get_available_staff,
    validate_schedule,
    create_shift,
    explain_decision,
    escalate_to_manager,
]

SWAP_TOOLS = [
    find_swap_candidates,
    validate_schedule,
    create_shift,
    notify_worker,
    notify_manager,
    escalate_to_manager,
]
