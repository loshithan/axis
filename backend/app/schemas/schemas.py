"""
AXIS API Schemas
Pydantic models for request/response validation across all agent tools.
"""
from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Shared ──

class WorkerSummary(BaseModel):
    id: int
    employee_id: str
    name: str
    certifications: list[str] = []
    weekly_hours_used: float = 0.0
    fairness_score: float = 0.0
    is_available: bool = True


# ── GetAvailableStaff ──

class GetAvailableStaffRequest(BaseModel):
    sbu_code: str
    department_code: str
    date: date
    shift_type_id: int
    required_certifications: list[str] = []


class GetAvailableStaffResponse(BaseModel):
    candidates: list[WorkerSummary]
    total_eligible: int
    shift_info: dict


# ── ValidateSchedule ──

class ValidateScheduleRequest(BaseModel):
    worker_id: int
    shift_type_id: int
    date: date
    start_time: time
    end_time: time


class ValidationResult(BaseModel):
    is_valid: bool
    reason: str  # Plain-English explanation
    checks_performed: list[dict] = []  # [{check: "overlap", passed: true}, ...]


# ── CreateShift ──

class CreateShiftRequest(BaseModel):
    worker_id: int
    shift_type_id: int
    date: date
    start_time: time
    end_time: time
    explanation: str = ""
    reasoning_trace: dict = {}
    confirmed: bool = False  # If True, skip the "proposed" state


class CreateShiftResponse(BaseModel):
    shift_id: int
    status: str
    worker_name: str
    coverage_stats: dict  # {filled: 3, total: 5, coverage_pct: 60}


# ── FindSwapCandidates ──

class FindSwapCandidatesRequest(BaseModel):
    shift_id: int


class SwapCandidate(BaseModel):
    worker: WorkerSummary
    swap_risk: str  # "low", "medium", "high" (overtime risk)
    reason_ranked: str  # Why this candidate is ranked here


class FindSwapCandidatesResponse(BaseModel):
    candidates: list[SwapCandidate]
    shift_details: dict
    total_candidates: int


# ── NotifyWorker ──

class NotifyWorkerRequest(BaseModel):
    worker_id: int
    notification_type: str  # "assignment", "swap", "schedule_change"
    subject: str
    message: str
    shift_id: Optional[int] = None


class NotifyWorkerResponse(BaseModel):
    email_sent: bool
    push_sent: bool
    worker_name: str


# ── NotifyManager / EscalateToManager ──

class NotifyManagerRequest(BaseModel):
    manager_id: Optional[int] = None  # If None, notify dept manager
    department_code: str
    subject: str
    summary: str
    related_shift_ids: list[int] = []


class EscalateToManagerRequest(BaseModel):
    shift_type_id: int
    date: date
    conflict_description: str
    agent_reasoning: str
    attempted_candidates: list[dict] = []


class EscalationResponse(BaseModel):
    escalation_id: int
    status: str
    message: str


# ── ExplainDecision ──

class ExplainDecisionRequest(BaseModel):
    worker_id: int
    shift_id: int
    assignment_context: dict  # What slot, who else was considered
    reasoning_trace: list[dict]  # Steps the agent took


class ExplainDecisionResponse(BaseModel):
    explanation: str  # Natural language explanation
    stored: bool


# ── Schedule Generation (Orchestrator → Scheduler) ──

class ScheduleRequest(BaseModel):
    """The structured payload the Orchestrator sends to the Scheduler."""
    sbu_code: str
    department_code: str
    date_range_start: date
    date_range_end: date
    shift_type_ids: list[int] = []  # Empty = all shift types for this dept
    headcount_per_shift: int = Field(default=1, ge=1)
    constraints: dict = {}  # Additional constraints from the NL input
    session_id: str = ""


class ScheduleSlotResult(BaseModel):
    date: date
    shift_type: str
    assigned_worker: Optional[str] = None
    status: str  # "filled", "escalated", "pending"
    explanation: str = ""


class ScheduleResponse(BaseModel):
    slots: list[ScheduleSlotResult]
    total_slots: int
    filled: int
    escalated: int
    reasoning_summary: str


# ── Orchestrator ──

class OrchestratorInput(BaseModel):
    """Raw message from the manager."""
    message: str
    sbu_code: str  # From session context
    session_id: str


class OrchestratorOutput(BaseModel):
    intent: str  # "schedule", "swap", "query", "report"
    routed_to: str  # "scheduler", "swap_agent", "direct_response"
    extracted_params: dict
    sbu_config_loaded: bool


class ResolveSwapRequest(BaseModel):
    leave_request_id: int


class NotifyManagerResponse(BaseModel):
    logged: bool
    email_sent: bool = False


class ShiftListItem(BaseModel):
    id: int
    worker_id: Optional[int] = None
    worker_name: str
    shift_type_id: int
    shift_type_name: str
    department_code: str
    date: date
    start_time: time
    end_time: time
    status: str


class DepartmentItem(BaseModel):
    id: int
    code: str
    name: str


class ShiftTypeItem(BaseModel):
    id: int
    code: str
    name: str
    department_code: str
    start_time: time
    end_time: time


class ManualCreateShiftRequest(BaseModel):
    """Manual shift creation — worker_id=None creates an open shift."""
    worker_id: Optional[int] = None
    shift_type_id: int
    date: date
    start_time: time
    end_time: time
    status: str = "confirmed"


class UpdateShiftRequest(BaseModel):
    """Partial update — only fields present in the body are applied."""
    worker_id: Optional[int] = None          # explicit null → open shift
    shift_type_id: Optional[int] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[str] = None
