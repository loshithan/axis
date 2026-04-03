"""
AXIS FastAPI Backend
All agent tools exposed as REST API endpoints.
"""
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.models import Department, Escalation, EscalationStatus, LeaveRequest, LeaveStatus, OTApplication, OTApplicationStatus, OTRequest, OTRequestStatus, SBU, Shift, ShiftStatus, ShiftType, Worker
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
    ManualCreateShiftRequest,
    UpdateShiftRequest,
    NotifyOTRequest,
    NotifyOTResponse,
    ApplyOTRequest,
    ApplyOTResponse,
    AssignOTResponse,
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
    get_ot_workers_impl,
    list_ot_requests_impl,
    list_ot_applications_impl,
    notify_ot_workers_impl,
    apply_for_ot_impl,
    assign_first_ot_applicant_impl,
    get_worker_weekly_stats,
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
            worker_id=r.worker_id,
            worker_name=r.worker.name if r.worker else "",
            worker_type=r.worker.employee_type if r.worker else "",
            shift_type_id=r.shift_type_id,
            shift_type_name=r.shift_type.name if r.shift_type else "",
            department_code=r.shift_type.department_code if r.shift_type else "",
            date=r.date,
            start_time=r.start_time,
            end_time=r.end_time,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in rows
        if r.start_time and r.end_time
    ]


@app.post("/schedule/shifts", response_model=ShiftListItem)
async def create_shift_manual(
    body: ManualCreateShiftRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a shift manually; worker_id=null creates an open shift."""
    shift_type = (
        await session.execute(
            select(ShiftType).where(ShiftType.id == body.shift_type_id)
        )
    ).scalar_one_or_none()
    if not shift_type:
        raise HTTPException(status_code=404, detail="Shift type not found")

    try:
        status = ShiftStatus(body.status)
    except ValueError:
        status = ShiftStatus.CONFIRMED

    if body.worker_id is None:
        status = ShiftStatus.OPEN

    # Conflict check for assigned worker
    if body.worker_id is not None:
        conflicts = (
            await session.execute(
                select(Shift).where(
                    Shift.worker_id == body.worker_id,
                    Shift.date == body.date,
                    Shift.status.notin_([ShiftStatus.CANCELLED, ShiftStatus.SWAPPED]),
                )
            )
        ).scalars().all()
        for ex in conflicts:
            if body.start_time < ex.end_time and ex.start_time < body.end_time:
                raise HTTPException(
                    status_code=409,
                    detail=f"Conflict: worker already has shift #{ex.id} on {body.date} ({ex.start_time}–{ex.end_time})",
                )

    shift = Shift(
        worker_id=body.worker_id,
        shift_type_id=body.shift_type_id,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
        status=status,
        created_by="manual",
    )
    session.add(shift)
    await session.commit()

    stmt = (
        select(Shift)
        .options(selectinload(Shift.worker), selectinload(Shift.shift_type))
        .where(Shift.id == shift.id)
    )
    shift = (await session.execute(stmt)).scalar_one()
    return ShiftListItem(
        id=shift.id,
        worker_id=shift.worker_id,
        worker_name=shift.worker.name if shift.worker else "",
        worker_type=shift.worker.employee_type if shift.worker else "",
        shift_type_id=shift.shift_type_id,
        shift_type_name=shift.shift_type.name if shift.shift_type else "",
        department_code=shift.shift_type.department_code if shift.shift_type else "",
        date=shift.date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        status=shift.status.value,
    )


@app.put("/schedule/shifts/{shift_id}", response_model=ShiftListItem)
async def update_shift(
    shift_id: int,
    body: UpdateShiftRequest,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Shift)
        .options(selectinload(Shift.worker), selectinload(Shift.shift_type))
        .where(Shift.id == shift_id)
    )
    shift = (await session.execute(stmt)).scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # Resolve new values (explicit None for worker_id = open shift)
    new_worker_id = body.worker_id if "worker_id" in body.model_fields_set else shift.worker_id
    new_date = body.date if body.date is not None else shift.date
    new_start = body.start_time if body.start_time is not None else shift.start_time
    new_end = body.end_time if body.end_time is not None else shift.end_time
    new_type_id = body.shift_type_id if body.shift_type_id is not None else shift.shift_type_id

    # Conflict detection when a worker is being assigned
    if new_worker_id is not None:
        conflict_stmt = select(Shift).where(
            Shift.worker_id == new_worker_id,
            Shift.date == new_date,
            Shift.id != shift_id,
            Shift.status.notin_([ShiftStatus.CANCELLED, ShiftStatus.SWAPPED]),
        )
        for ex in (await session.execute(conflict_stmt)).scalars().all():
            if new_start < ex.end_time and ex.start_time < new_end:
                raise HTTPException(
                    status_code=409,
                    detail=f"Conflict: worker already has shift #{ex.id} on {new_date} ({ex.start_time}–{ex.end_time})",
                )

    shift.worker_id = new_worker_id
    shift.date = new_date
    shift.start_time = new_start
    shift.end_time = new_end
    shift.shift_type_id = new_type_id

    # Auto-derive status if not explicitly set
    if body.status:
        try:
            shift.status = ShiftStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    elif new_worker_id is None:
        shift.status = ShiftStatus.OPEN
    elif shift.status == ShiftStatus.OPEN:
        shift.status = ShiftStatus.CONFIRMED

    await session.commit()

    stmt2 = (
        select(Shift)
        .options(selectinload(Shift.worker), selectinload(Shift.shift_type))
        .where(Shift.id == shift_id)
    )
    shift = (await session.execute(stmt2)).scalar_one()
    return ShiftListItem(
        id=shift.id,
        worker_id=shift.worker_id,
        worker_name=shift.worker.name if shift.worker else "",
        worker_type=shift.worker.employee_type if shift.worker else "",
        shift_type_id=shift.shift_type_id,
        shift_type_name=shift.shift_type.name if shift.shift_type else "",
        department_code=shift.shift_type.department_code if shift.shift_type else "",
        date=shift.date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        status=shift.status.value,
    )


@app.delete("/schedule/shifts/{shift_id}")
async def delete_shift(
    shift_id: int,
    session: AsyncSession = Depends(get_db),
):
    shift = (await session.execute(select(Shift).where(Shift.id == shift_id))).scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    await session.delete(shift)
    await session.commit()
    return {"deleted": True, "shift_id": shift_id}


@app.get("/employees")
async def list_all_employees(
    sbu_code: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Worker)
        .options(
            selectinload(Worker.department).selectinload(Department.sbu)
        )
        .join(Department, Department.id == Worker.department_id)
        .join(SBU, SBU.id == Department.sbu_id)
        .order_by(Worker.name)
    )
    if sbu_code:
        stmt = stmt.where(SBU.code == sbu_code)
    rows = (await session.execute(stmt)).scalars().all()
    result = []
    for r in rows:
        stats = await get_worker_weekly_stats(session, r.id, r.max_weekly_hours or 40)
        result.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "name": r.name,
            "email": r.email,
            "phone": r.phone,
            "employee_type": r.employee_type or "nurse",
            "department_code": r.department.code if r.department else "",
            "department_name": r.department.name if r.department else "",
            "sbu_code": r.department.sbu.code if r.department and r.department.sbu else "",
            "sbu_name": r.department.sbu.name if r.department and r.department.sbu else "",
            "certifications": list(r.certifications or []),
            "max_weekly_hours": r.max_weekly_hours,
            "weekly_hours_used": stats["weekly_hours_used"],
            "ot_hours": stats["ot_hours"],
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result


@app.get("/meta/workers/search")
async def search_worker(
    name: str,
    sbu_code: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Worker)
        .options(selectinload(Worker.department))
        .join(Department, Department.id == Worker.department_id)
        .join(SBU, SBU.id == Department.sbu_id)
        .where(SBU.code == sbu_code, Worker.is_active.is_(True), Worker.name.ilike(f"%{name}%"))
        .order_by(Worker.name)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": r.id, "name": r.name, "employee_id": r.employee_id, "department_code": r.department.code if r.department else ""} for r in rows]


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
            "employee_type": r.employee_type or "nurse",
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


@app.get("/swap/leave-requests")
async def list_leave_requests(
    sbu_code: str,
    department_code: str,
    status: str = "pending",
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.worker),
            selectinload(LeaveRequest.shift).selectinload(Shift.shift_type),
        )
        .join(Worker, Worker.id == LeaveRequest.worker_id)
        .join(Department, Department.id == Worker.department_id)
        .join(SBU, SBU.id == Department.sbu_id)
        .where(SBU.code == sbu_code, Department.code == department_code)
        .order_by(LeaveRequest.created_at.desc())
    )
    if status != "all":
        try:
            stmt = stmt.where(LeaveRequest.status == LeaveStatus(status))
        except ValueError:
            pass
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "worker_id": r.worker_id,
            "worker_name": r.worker.name if r.worker else "",
            "shift_id": r.shift_id,
            "shift_type_name": r.shift.shift_type.name if r.shift and r.shift.shift_type else None,
            "date": r.date.isoformat(),
            "reason": r.reason,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "resolution_summary": r.resolution_summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/swap/leave-request")
async def create_leave_request(
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    lr = LeaveRequest(
        worker_id=body["worker_id"],
        shift_id=body.get("shift_id"),
        date=date.fromisoformat(body["date"]),
        reason=body.get("reason", ""),
        status=LeaveStatus.PENDING,
    )
    session.add(lr)

    # Mark the linked shift as PENDING so the calendar flags it as uncovered
    if body.get("shift_id"):
        shift = await session.get(Shift, body["shift_id"])
        if shift and shift.status not in (ShiftStatus.CANCELLED, ShiftStatus.SWAPPED):
            shift.status = ShiftStatus.PENDING

    await session.commit()
    await session.refresh(lr)
    return {"id": lr.id, "status": lr.status.value}


@app.get("/swap/escalations")
async def list_escalations(
    sbu_code: str,
    department_code: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Escalation)
        .options(selectinload(Escalation.shift_type))
        .join(ShiftType, ShiftType.id == Escalation.shift_type_id)
        .join(SBU, SBU.id == ShiftType.sbu_id)
        .where(
            SBU.code == sbu_code,
            ShiftType.department_code == department_code,
            Escalation.status == EscalationStatus.OPEN,
        )
        .order_by(Escalation.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "shift_type_name": r.shift_type.name if r.shift_type else None,
            "date": r.date.isoformat(),
            "description": r.description,
            "agent_reasoning": r.agent_reasoning,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/swap/resolve")
async def resolve_leave(
    body: ResolveSwapRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await resolve_leave_request_impl(session, body.leave_request_id)
    except ValueError as e:
        raise _http_from_value(e) from e


# ── OT Management ──

@app.get("/ot/workers")
async def get_ot_workers(
    sbu_code: str,
    department_code: str,
    shift_date: date,
    session: AsyncSession = Depends(get_db),
):
    return await get_ot_workers_impl(session, sbu_code, department_code, shift_date)


@app.get("/ot/requests")
async def list_ot_requests(
    sbu_code: str,
    department_code: str,
    status: str = "open",
    session: AsyncSession = Depends(get_db),
):
    return await list_ot_requests_impl(session, sbu_code, department_code, status)


@app.get("/ot/requests/{ot_request_id}/applications")
async def list_ot_applications(
    ot_request_id: int,
    session: AsyncSession = Depends(get_db),
):
    return await list_ot_applications_impl(session, ot_request_id)


@app.post("/ot/notify", response_model=NotifyOTResponse)
async def notify_ot(
    body: NotifyOTRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await notify_ot_workers_impl(session, body.ot_request_id, body.worker_ids)
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/ot/applications/{ot_request_id}/apply", response_model=ApplyOTResponse)
async def apply_ot(
    ot_request_id: int,
    body: ApplyOTRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await apply_for_ot_impl(session, ot_request_id, body.worker_id)
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/ot/requests/{ot_request_id}/assign-first", response_model=AssignOTResponse)
async def assign_first_ot(
    ot_request_id: int,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await assign_first_ot_applicant_impl(session, ot_request_id)
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
