"""
AXIS FastAPI Backend
All agent tools exposed as REST API endpoints.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.schemas.schemas import (
    GetAvailableStaffRequest, GetAvailableStaffResponse,
    ValidateScheduleRequest, ValidationResult,
    CreateShiftRequest, CreateShiftResponse,
    FindSwapCandidatesRequest, FindSwapCandidatesResponse,
    NotifyWorkerRequest, NotifyWorkerResponse,
    NotifyManagerRequest, EscalateToManagerRequest, EscalationResponse,
    ExplainDecisionRequest, ExplainDecisionResponse,
    ScheduleRequest, ScheduleResponse,
    OrchestratorInput, OrchestratorOutput,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load SBU configs, init DB pool
    print("AXIS backend starting...")
    yield
    # Shutdown
    print("AXIS backend shutting down...")


app = FastAPI(
    title="AXIS - Agentic Workforce Intelligence System",
    description="Backend API for the AXIS scheduling platform. All agent tools are exposed here.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ──

@app.get("/health")
async def health():
    return {"status": "ok", "service": "axis-backend"}


# ── Agent Tool Endpoints ──

@app.post("/tools/get-available-staff", response_model=GetAvailableStaffResponse)
async def get_available_staff(request: GetAvailableStaffRequest):
    """
    Tool: GetAvailableStaff()
    Called by: Scheduler Agent
    Returns eligible workers for a shift slot filtered by SBU, dept, date, certs.
    """
    # TODO: Query DB for workers matching criteria
    # - Filter by department and SBU
    # - Check availability for the date
    # - Exclude workers on leave
    # - Calculate weekly hours used
    # - Calculate fairness scores
    # - Sort by fairness score (highest first)
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/validate-schedule", response_model=ValidationResult)
async def validate_schedule(request: ValidateScheduleRequest):
    """
    Tool: ValidateSchedule()
    Called by: Scheduler Agent, Swap Agent
    Runs full validation pipeline: overlap, availability, hours, rest, certs.
    """
    # TODO: Load worker data, existing shifts, SBU config
    # Call rules.engine.validate_assignment()
    # Return structured result
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/create-shift", response_model=CreateShiftResponse)
async def create_shift(request: CreateShiftRequest):
    """
    Tool: CreateShift()
    Called by: Scheduler Agent, Swap Agent
    Writes confirmed assignment to database and returns coverage stats.
    """
    # TODO: Insert shift record
    # Calculate updated coverage stats for the shift type + date
    # Return confirmation
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/find-swap-candidates", response_model=FindSwapCandidatesResponse)
async def find_swap_candidates(request: FindSwapCandidatesRequest):
    """
    Tool: FindSwapCandidates()
    Called by: Swap Agent
    Returns ranked eligible workers to cover a specific shift.
    """
    # TODO: Load the shift needing coverage
    # Find all workers in same dept with matching certs
    # Filter by availability for that date/time
    # Score by fairness + overtime risk
    # Return ranked list
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/notify-worker", response_model=NotifyWorkerResponse)
async def notify_worker(request: NotifyWorkerRequest):
    """
    Tool: NotifyWorker()
    Called by: Scheduler Agent, Swap Agent
    Sends push notification (Expo) + email (SendGrid) to worker.
    """
    # TODO: Send email via SendGrid API
    # Send push via Expo Push API
    # Log notification
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/notify-manager")
async def notify_manager(request: NotifyManagerRequest):
    """
    Tool: NotifyManager()
    Called by: Swap Agent
    Notifies the department manager of a resolution.
    """
    # TODO: Find manager for department
    # Send notification
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/escalate-to-manager", response_model=EscalationResponse)
async def escalate_to_manager(request: EscalateToManagerRequest):
    """
    Tool: EscalateToManager()
    Called by: Scheduler Agent, Swap Agent
    Writes unresolvable conflict to manager inbox with agent's explanation.
    """
    # TODO: Create escalation record
    # Notify manager
    # Return escalation ID
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/tools/explain-decision", response_model=ExplainDecisionResponse)
async def explain_decision(request: ExplainDecisionRequest):
    """
    Tool: ExplainDecision()
    Called by: Scheduler Agent
    Generates and stores a natural language explanation for an assignment.
    Uses Claude API to generate the explanation from the reasoning trace.
    """
    # TODO: Call Claude API with reasoning context
    # Store explanation on the shift record
    # Return explanation text
    raise HTTPException(status_code=501, detail="Not yet implemented")


# ── High-Level Endpoints ──

@app.post("/schedule/generate", response_model=ScheduleResponse)
async def generate_schedule(request: ScheduleRequest):
    """
    Main scheduling endpoint.
    Orchestrator parses intent → Scheduler fills slots via ReAct loop.
    """
    # TODO: This is the main integration point
    # 1. Load SBU config
    # 2. Determine shift slots to fill
    # 3. For each slot, run ReAct loop:
    #    a. GetAvailableStaff
    #    b. ValidateSchedule (top candidate)
    #    c. CreateShift (on pass) or try next candidate
    #    d. ExplainDecision
    #    e. EscalateToManager (if all candidates exhausted)
    # 4. Return complete schedule with reasoning
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/orchestrator/process", response_model=OrchestratorOutput)
async def process_message(request: OrchestratorInput):
    """
    Orchestrator Agent entry point.
    Parses natural language → extracts intent and params → routes to specialist agent.
    """
    # TODO: Call Claude API for intent classification
    # Extract: intent, SBU, dept, date range, constraints
    # Route to appropriate agent
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/swap/resolve")
async def resolve_leave(leave_request_id: int):
    """
    Swap Agent entry point.
    Triggered when a leave request is submitted.
    Autonomously finds replacement, validates, assigns, notifies.
    """
    # TODO: Load leave request and affected shift
    # Run Swap Agent pipeline:
    #   FindSwapCandidates → ValidateSchedule → CreateShift → NotifyWorker → NotifyManager
    # Or EscalateToManager if no valid candidate
    raise HTTPException(status_code=501, detail="Not yet implemented")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
