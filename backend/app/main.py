"""
AXIS FastAPI Backend
All agent tools exposed as REST API endpoints.
"""
import os
from datetime import date
from dotenv import load_dotenv

# Load environment variables from the project root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.models import Department, SBU, Shift, ShiftType, Worker
from app.schemas.schemas import (
    GetAvailableStaffRequest,
    GetAvailableStaffResponse,
    ValidateScheduleRequest,
    ValidationResult,
    CreateShiftRequest,
    CreateShiftResponse,
    FindSwapCandidatesRequest,
    FindSwapCandidatesResponse,
    NotifyWorkerRequest,
    NotifyWorkerResponse,
    NotifyManagerRequest,
    EscalateToManagerRequest,
    EscalationResponse,
    ExplainDecisionRequest,
    ExplainDecisionResponse,
    ScheduleRequest,
    ScheduleResponse,
    OrchestratorInput,
    OrchestratorOutput,
    ResolveSwapRequest,
    NotifyManagerResponse,
    ShiftListItem,
    DepartmentItem,
    ShiftTypeItem,
)
from app.services.axis_service import (
    create_shift_impl,
    escalate_impl,
    explain_decision_impl,
    find_swap_candidates_impl,
    generate_schedule_impl,
    get_available_staff_impl,
    notify_manager_impl,
    notify_worker_impl,
    orchestrator_process_message,
    resolve_leave_request_impl,
    validate_schedule_impl,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("AXIS backend starting...")
    yield
    print("AXIS backend shutting down...")


app = FastAPI(
    title="AXIS - Agentic Workforce Intelligence System",
    description="Backend API for the AXIS scheduling platform. All agent tools are exposed here.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _http_from_value(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ── Health Check ──

@app.get("/health")
async def health():
    return {"status": "ok", "service": "axis-backend"}


# ── Read APIs (frontend / integrations) ──

@app.get("/meta/sbus")
async def list_sbus(session: AsyncSession = Depends(get_db)):
    stmt = select(SBU).where(SBU.is_active.is_(True)).order_by(SBU.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


@app.get("/meta/departments", response_model=list[DepartmentItem])
async def list_departments(sbu_code: str, session: AsyncSession = Depends(get_db)):
    stmt = (
        select(Department)
        .join(SBU, SBU.id == Department.sbu_id)
        .where(SBU.code == sbu_code)
        .order_by(Department.name)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [DepartmentItem(id=r.id, code=r.code, name=r.name) for r in rows]


@app.get("/meta/shift-types", response_model=list[ShiftTypeItem])
async def list_shift_types(
    sbu_code: str,
    department_code: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ShiftType)
        .join(SBU, SBU.id == ShiftType.sbu_id)
        .where(SBU.code == sbu_code, ShiftType.department_code == department_code)
        .order_by(ShiftType.name)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        ShiftTypeItem(
            id=r.id,
            code=r.code,
            name=r.name,
            department_code=r.department_code,
            start_time=r.start_time,
            end_time=r.end_time,
        )
        for r in rows
    ]


@app.get("/schedule/shifts", response_model=list[ShiftListItem])
async def list_shifts(
    sbu_code: str,
    department_code: str,
    start: date,
    end: date,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Shift)
        .options(
            selectinload(Shift.worker),
            selectinload(Shift.shift_type),
        )
        .join(ShiftType, ShiftType.id == Shift.shift_type_id)
        .join(SBU, SBU.id == ShiftType.sbu_id)
        .where(
            SBU.code == sbu_code,
            ShiftType.department_code == department_code,
            Shift.date >= start,
            Shift.date <= end,
        )
        .order_by(Shift.date, Shift.start_time)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        ShiftListItem(
            id=r.id,
            worker_name=r.worker.name if r.worker else "",
            shift_type_name=r.shift_type.name if r.shift_type else "",
            department_code=r.shift_type.department_code if r.shift_type else "",
            date=r.date,
            start_time=r.start_time,
            end_time=r.end_time,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in rows
    ]


@app.get("/meta/workers")
async def list_workers(
    sbu_code: str,
    department_code: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Worker)
        .join(Department, Department.id == Worker.department_id)
        .join(SBU, SBU.id == Department.sbu_id)
        .where(
            SBU.code == sbu_code,
            Department.code == department_code,
            Worker.is_active.is_(True),
        )
        .order_by(Worker.name)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "employee_id": r.employee_id,
            "name": r.name,
            "email": r.email,
            "certifications": list(r.certifications or []),
            "max_weekly_hours": r.max_weekly_hours,
        }
        for r in rows
    ]


# ── Agent Tool Endpoints ──

@app.post("/tools/get-available-staff", response_model=GetAvailableStaffResponse)
async def get_available_staff(
    request: GetAvailableStaffRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await get_available_staff_impl(session, request)
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/tools/validate-schedule", response_model=ValidationResult)
async def validate_schedule(
    request: ValidateScheduleRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await validate_schedule_impl(
            session,
            request.worker_id,
            request.shift_type_id,
            request.date,
            slot_start=request.start_time,
            slot_end=request.end_time,
        )
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/tools/create-shift", response_model=CreateShiftResponse)
async def create_shift(request: CreateShiftRequest, session: AsyncSession = Depends(get_db)):
    try:
        return await create_shift_impl(session, request)
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/tools/find-swap-candidates", response_model=FindSwapCandidatesResponse)
async def find_swap_candidates(
    request: FindSwapCandidatesRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await find_swap_candidates_impl(session, request)
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/tools/notify-worker", response_model=NotifyWorkerResponse)
async def notify_worker(request: NotifyWorkerRequest, session: AsyncSession = Depends(get_db)):
    try:
        email_sent, push_sent, name = await notify_worker_impl(
            session,
            request.worker_id,
            request.notification_type,
            request.subject,
            request.message,
            request.shift_id,
        )
        return NotifyWorkerResponse(
            email_sent=email_sent,
            push_sent=push_sent,
            worker_name=name,
        )
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/tools/notify-manager", response_model=NotifyManagerResponse)
async def notify_manager(request: NotifyManagerRequest, session: AsyncSession = Depends(get_db)):
    result = await notify_manager_impl(
        session,
        request.department_code,
        request.subject,
        request.summary,
        request.related_shift_ids,
    )
    return NotifyManagerResponse(**result)


@app.post("/tools/escalate-to-manager", response_model=EscalationResponse)
async def escalate_to_manager(
    request: EscalateToManagerRequest,
    session: AsyncSession = Depends(get_db),
):
    return await escalate_impl(session, request)


@app.post("/tools/explain-decision", response_model=ExplainDecisionResponse)
async def explain_decision(
    request: ExplainDecisionRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await explain_decision_impl(session, request)
    except ValueError as e:
        raise _http_from_value(e) from e


# ── High-Level Endpoints ──

@app.post("/schedule/generate", response_model=ScheduleResponse)
async def generate_schedule(
    request: ScheduleRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await generate_schedule_impl(session, request)
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/orchestrator/process", response_model=OrchestratorOutput)
async def process_message(request: OrchestratorInput):
    routing = await orchestrator_process_message(
        request.message,
        request.sbu_code,
        request.session_id,
    )
    return OrchestratorOutput(
        intent=routing.get("intent", "query"),
        routed_to=routing.get("routed_to", "direct_response"),
        extracted_params=routing.get("extracted_params") or {},
        sbu_config_loaded=bool(routing.get("sbu_config_loaded")),
    )


@app.post("/swap/resolve")
async def resolve_leave(
    body: ResolveSwapRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await resolve_leave_request_impl(session, body.leave_request_id)
    except ValueError as e:
        raise _http_from_value(e) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
