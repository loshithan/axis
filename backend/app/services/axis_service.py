"""DB-backed implementations for AXIS tool endpoints and scheduling."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Availability,
    Department,
    Escalation,
    EscalationStatus,
    LeaveRequest,
    LeaveStatus,
    SBU,
    Shift,
    ShiftStatus,
    ShiftType,
    Worker,
)
from app.rules.engine import (
    calculate_fairness_score,
    validate_assignment,
)
from app.schemas.schemas import (
    CreateShiftRequest,
    CreateShiftResponse,
    EscalateToManagerRequest,
    EscalationResponse,
    ExplainDecisionRequest,
    ExplainDecisionResponse,
    FindSwapCandidatesRequest,
    FindSwapCandidatesResponse,
    GetAvailableStaffRequest,
    GetAvailableStaffResponse,
    ScheduleRequest,
    ScheduleResponse,
    ScheduleSlotResult,
    SwapCandidate,
    ValidationResult,
    WorkerSummary,
)

logger = logging.getLogger("axis.service")

def _week_range(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _shift_to_rule_dict(shift: Shift) -> dict:
    st = shift.shift_type
    label = st.name if st else "shift"
    return {
        "date": shift.date,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "shift_type": label,
    }


async def _load_department_sbu(
    session: AsyncSession, sbu_code: str, department_code: str
) -> tuple[SBU, Department]:
    stmt = (
        select(SBU, Department)
        .join(Department, Department.sbu_id == SBU.id)
        .where(SBU.code == sbu_code, Department.code == department_code)
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row:
        raise ValueError(f"Unknown SBU/department: {sbu_code}/{department_code}")
    sbu, dept = row[0], row[1]
    return sbu, dept


async def _load_shift_type(
    session: AsyncSession, shift_type_id: int
) -> ShiftType:
    stmt = (
        select(ShiftType)
        .options(selectinload(ShiftType.sbu))
        .where(ShiftType.id == shift_type_id)
    )
    st = (await session.execute(stmt)).scalar_one_or_none()
    if not st:
        raise ValueError(f"Unknown shift_type_id: {shift_type_id}")
    return st


async def _weekly_hours_used(
    session: AsyncSession, worker_id: int, week_start: date, week_end: date
) -> float:
    stmt = select(Shift).where(
        Shift.worker_id == worker_id,
        Shift.date >= week_start,
        Shift.date <= week_end,
        Shift.status.in_([ShiftStatus.PROPOSED, ShiftStatus.CONFIRMED]),
    )
    shifts = (await session.execute(stmt)).scalars().all()
    total = 0.0
    for sh in shifts:
        total += _duration_hours(sh.start_time, sh.end_time)
    return total


def _duration_hours(start: time, end: time) -> float:
    s = datetime.combine(date.today(), start)
    e = datetime.combine(date.today(), end)
    if e <= s:
        e += timedelta(days=1)
    return (e - s).total_seconds() / 3600.0


async def _leave_dates_in_range(
    session: AsyncSession, worker_id: int, d0: date, d1: date
) -> list[date]:
    stmt = select(LeaveRequest.date).where(
        LeaveRequest.worker_id == worker_id,
        LeaveRequest.date >= d0,
        LeaveRequest.date <= d1,
        LeaveRequest.status.in_(
            [LeaveStatus.PENDING, LeaveStatus.APPROVED, LeaveStatus.COVERED]
        ),
    )
    return list((await session.execute(stmt)).scalars().all())


async def _availability_rows(
    session: AsyncSession, worker_id: int, d0: date, d1: date
) -> list[dict]:
    stmt = select(Availability).where(
        Availability.worker_id == worker_id,
        Availability.date >= d0,
        Availability.date <= d1,
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "date": r.date,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "is_available": r.is_available,
        }
        for r in rows
    ]


async def _worker_shifts_for_rules(
    session: AsyncSession, worker_id: int, center: date
) -> list[Shift]:
    d0 = center - timedelta(days=1)
    d1 = center + timedelta(days=1)
    stmt = (
        select(Shift)
        .options(selectinload(Shift.shift_type))
        .where(
            Shift.worker_id == worker_id,
            Shift.date >= d0,
            Shift.date <= d1,
            Shift.status.in_([ShiftStatus.PROPOSED, ShiftStatus.CONFIRMED]),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def _department_mean_weekly_hours(
    session: AsyncSession, department_id: int, week_start: date, week_end: date
) -> float:
    stmt = select(Worker.id).where(
        Worker.department_id == department_id, Worker.is_active.is_(True)
    )
    ids = list((await session.execute(stmt)).scalars().all())
    if not ids:
        return 0.0
    totals = []
    for wid in ids:
        totals.append(await _weekly_hours_used(session, wid, week_start, week_end))
    return sum(totals) / len(totals)


async def _shifts_count_in_week(
    session: AsyncSession, worker_id: int, week_start: date, week_end: date
) -> int:
    stmt = select(func.count(Shift.id)).where(
        Shift.worker_id == worker_id,
        Shift.date >= week_start,
        Shift.date <= week_end,
        Shift.status.in_([ShiftStatus.PROPOSED, ShiftStatus.CONFIRMED]),
    )
    return int((await session.execute(stmt)).scalar() or 0)


def _sbu_config(sbu: SBU) -> dict:
    cfg = sbu.config or {}
    if isinstance(cfg, str):
        import json

        return json.loads(cfg)
    return dict(cfg)


async def build_validation_context(
    session: AsyncSession,
    worker: Worker,
    shift_type: ShiftType,
    on_date: date,
    sbu: SBU,
    slot_start: Optional[time] = None,
    slot_end: Optional[time] = None,
) -> tuple[dict, dict, list[date], list[dict], list[dict], dict]:
    week_start, week_end = _week_range(on_date)
    sbu_config = _sbu_config(sbu)
    weekly = await _weekly_hours_used(session, worker.id, week_start, week_end)
    leave_dates = await _leave_dates_in_range(session, worker.id, on_date, on_date)
    avail = await _availability_rows(
        session, worker.id, on_date - timedelta(days=1), on_date + timedelta(days=1)
    )
    shifts = await _worker_shifts_for_rules(session, worker.id, on_date)
    adjacent = [_shift_to_rule_dict(s) for s in shifts]
    worker_dict = {
        "id": worker.id,
        "certifications": list(worker.certifications or []),
        "weekly_hours_used": weekly,
        "max_weekly_hours": float(worker.max_weekly_hours or 40),
    }
    st_t = slot_start or shift_type.start_time
    en_t = slot_end or shift_type.end_time
    proposal = {
        "date": on_date,
        "start_time": st_t,
        "end_time": en_t,
        "required_certifications": list(shift_type.required_certifications or []),
    }
    return worker_dict, proposal, leave_dates, avail, adjacent, sbu_config


async def validate_schedule_impl(
    session: AsyncSession,
    worker_id: int,
    shift_type_id: int,
    on_date: date,
    slot_start: Optional[time] = None,
    slot_end: Optional[time] = None,
) -> ValidationResult:
    worker = (
        await session.execute(
            select(Worker)
            .options(selectinload(Worker.department).selectinload(Department.sbu))
            .where(Worker.id == worker_id)
        )
    ).scalar_one_or_none()
    if not worker:
        raise ValueError(f"Unknown worker_id: {worker_id}")
    shift_type = await _load_shift_type(session, shift_type_id)
    sbu = shift_type.sbu
    if worker.department.sbu_id != sbu.id:
        return ValidationResult(
            is_valid=False,
            reason="Worker is not in the same SBU as this shift type.",
            checks_performed=[
                {"check": "sbu_match", "passed": False, "reason": "SBU mismatch"}
            ],
        )

    (
        worker_dict,
        proposal,
        leave_dates,
        avail,
        adjacent,
        sbu_config,
    ) = await build_validation_context(
        session,
        worker,
        shift_type,
        on_date,
        sbu,
        slot_start=slot_start,
        slot_end=slot_end,
    )
    existing = [d for d in adjacent if d["date"] == on_date]
    ok, reason, checks = validate_assignment(
        worker_dict,
        proposal,
        existing,
        leave_dates,
        avail,
        adjacent,
        sbu_config,
    )
    checks_out = [{"check": c["check"], "passed": c["passed"]} for c in checks]
    return ValidationResult(is_valid=ok, reason=reason, checks_performed=checks_out)


async def get_available_staff_impl(
    session: AsyncSession,
    req: GetAvailableStaffRequest,
    exclude_worker_ids: Optional[set[int]] = None,
) -> GetAvailableStaffResponse:
    sbu, dept = await _load_department_sbu(session, req.sbu_code, req.department_code)
    shift_type = await _load_shift_type(session, req.shift_type_id)
    if shift_type.sbu_id != sbu.id or shift_type.department_code != req.department_code:
        raise ValueError("Shift type does not belong to this SBU/department.")

    req_certs = req.required_certifications or list(
        shift_type.required_certifications or []
    )
    week_start, week_end = _week_range(req.date)
    team_avg = await _department_mean_weekly_hours(
        session, dept.id, week_start, week_end
    )

    stmt = select(Worker).where(
        Worker.department_id == dept.id,
        Worker.is_active.is_(True),
    )
    workers = list((await session.execute(stmt)).scalars().all())

    candidates: list[WorkerSummary] = []
    excl = exclude_worker_ids or set()

    for w in workers:
        if w.id in excl:
            continue
        wc = list(w.certifications or [])
        if req_certs and not all(c in wc for c in req_certs):
            continue
        leave_on_day = await _leave_dates_in_range(session, w.id, req.date, req.date)
        if req.date in leave_on_day:
            continue
        avail = await _availability_rows(session, w.id, req.date, req.date)
        has_slot = any(
            slot["date"] == req.date
            and slot["start_time"] <= shift_type.start_time
            and slot["end_time"] >= shift_type.end_time
            and slot["is_available"]
            for slot in avail
        )
        if not has_slot:
            continue

        weekly = await _weekly_hours_used(session, w.id, week_start, week_end)
        consec = await _shifts_count_in_week(session, w.id, week_start, week_end)
        fairness, _ = calculate_fairness_score(
            weekly,
            float(w.max_weekly_hours or 40),
            consec,
            team_avg,
        )

        candidates.append(
            WorkerSummary(
                id=w.id,
                employee_id=w.employee_id,
                name=w.name,
                certifications=wc,
                weekly_hours_used=round(weekly, 2),
                fairness_score=round(fairness, 2),
                is_available=True,
            )
        )

    candidates.sort(key=lambda x: x.fairness_score, reverse=True)
    shift_info = {
        "shift_type_id": shift_type.id,
        "name": shift_type.name,
        "code": shift_type.code,
        "start_time": shift_type.start_time.isoformat(timespec="minutes"),
        "end_time": shift_type.end_time.isoformat(timespec="minutes"),
        "required_certifications": list(shift_type.required_certifications or []),
    }
    return GetAvailableStaffResponse(
        candidates=candidates,
        total_eligible=len(candidates),
        shift_info=shift_info,
    )


async def _coverage_stats(
    session: AsyncSession, shift_type_id: int, on_date: date
) -> dict:
    st = await _load_shift_type(session, shift_type_id)
    stmt = select(func.count(Shift.id)).where(
        Shift.shift_type_id == shift_type_id,
        Shift.date == on_date,
        Shift.status.in_([ShiftStatus.PROPOSED, ShiftStatus.CONFIRMED]),
    )
    filled = int((await session.execute(stmt)).scalar() or 0)
    need = max(st.min_headcount or 1, 1)
    pct = min(100.0, (filled / need) * 100.0) if need else 0.0
    return {"filled": filled, "total": need, "coverage_pct": round(pct, 1)}


async def create_shift_impl(
    session: AsyncSession, req: CreateShiftRequest
) -> CreateShiftResponse:
    shift_type = await _load_shift_type(session, req.shift_type_id)
    worker = (
        await session.execute(
            select(Worker)
            .options(selectinload(Worker.department))
            .where(Worker.id == req.worker_id)
        )
    ).scalar_one_or_none()
    if not worker:
        raise ValueError(f"Unknown worker_id: {req.worker_id}")
    if worker.department.sbu_id != shift_type.sbu_id:
        raise ValueError("Worker and shift type must belong to the same SBU.")

    status = ShiftStatus.CONFIRMED if req.confirmed else ShiftStatus.PROPOSED
    sh = Shift(
        worker_id=req.worker_id,
        shift_type_id=req.shift_type_id,
        date=req.date,
        start_time=req.start_time,
        end_time=req.end_time,
        status=status,
        explanation=req.explanation or None,
        reasoning_trace=req.reasoning_trace or None,
    )
    session.add(sh)
    await session.flush()
    stats = await _coverage_stats(session, req.shift_type_id, req.date)
    return CreateShiftResponse(
        shift_id=sh.id,
        status=status.value,
        worker_name=worker.name,
        coverage_stats=stats,
    )


async def worker_row_max(session: AsyncSession, worker_id: int) -> float:
    w = (
        await session.execute(select(Worker).where(Worker.id == worker_id))
    ).scalar_one_or_none()
    return float(w.max_weekly_hours) if w else 40.0


async def find_swap_candidates_impl(
    session: AsyncSession, req: FindSwapCandidatesRequest
) -> FindSwapCandidatesResponse:
    sh = (
        await session.execute(
            select(Shift)
            .options(
                selectinload(Shift.shift_type).selectinload(ShiftType.sbu),
                selectinload(Shift.worker).selectinload(Worker.department),
            )
            .where(Shift.id == req.shift_id)
        )
    ).scalar_one_or_none()
    if not sh:
        raise ValueError(f"Unknown shift_id: {req.shift_id}")

    st = sh.shift_type
    sbu = st.sbu
    dept_code = st.department_code
    greq = GetAvailableStaffRequest(
        sbu_code=sbu.code,
        department_code=dept_code,
        date=sh.date,
        shift_type_id=st.id,
        required_certifications=list(st.required_certifications or []),
    )
    staff = await get_available_staff_impl(
        session, greq, exclude_worker_ids={sh.worker_id}
    )
    out: list[SwapCandidate] = []
    for c in staff.candidates:
        mx = await worker_row_max(session, c.id)
        risk = "low"
        if c.weekly_hours_used >= (mx * 0.9):
            risk = "high"
        elif c.weekly_hours_used >= (mx * 0.75):
            risk = "medium"
        out.append(
            SwapCandidate(
                worker=c,
                swap_risk=risk,
                reason_ranked=f"Fairness {c.fairness_score}; weekly {c.weekly_hours_used}h",
            )
        )
    details = {
        "shift_id": sh.id,
        "date": sh.date.isoformat(),
        "shift_type": st.name,
        "department_code": dept_code,
    }
    return FindSwapCandidatesResponse(
        candidates=out,
        shift_details=details,
        total_candidates=len(out),
    )


async def notify_worker_impl(
    session: AsyncSession,
    worker_id: int,
    notification_type: str,
    subject: str,
    message: str,
    shift_id: Optional[int],
) -> tuple[bool, bool, str]:
    worker = (
        await session.execute(select(Worker).where(Worker.id == worker_id))
    ).scalar_one_or_none()
    if not worker:
        raise ValueError(f"Unknown worker_id: {worker_id}")

    email_sent = False
    push_sent = False
    api_key = os.getenv("SENDGRID_API_KEY")
    if api_key and worker.email:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            m = Mail(
                from_email=os.getenv("SENDGRID_FROM", "noreply@axis.local"),
                to_emails=worker.email,
                subject=subject,
                plain_text_content=message,
            )
            sg = SendGridAPIClient(api_key)
            sg.send(m)
            email_sent = True
        except Exception as e:
            logger.warning("SendGrid failed: %s", e)

    logger.info(
        "Notify worker id=%s type=%s email_sent=%s shift_id=%s",
        worker_id,
        notification_type,
        email_sent,
        shift_id,
    )
    return email_sent, push_sent, worker.name


async def notify_manager_impl(
    session: AsyncSession,
    department_code: str,
    subject: str,
    summary: str,
    related_shift_ids: list[int],
) -> dict[str, Any]:
    logger.info(
        "Notify manager dept=%s subject=%s shifts=%s — %s",
        department_code,
        subject,
        related_shift_ids,
        summary[:200],
    )
    api_key = os.getenv("SENDGRID_API_KEY")
    sent = False
    if api_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            to = os.getenv("MANAGER_NOTIFY_EMAIL")
            if to:
                m = Mail(
                    from_email=os.getenv("SENDGRID_FROM", "noreply@axis.local"),
                    to_emails=to,
                    subject=subject,
                    plain_text_content=summary,
                )
                SendGridAPIClient(api_key).send(m)
                sent = True
        except Exception as e:
            logger.warning("Manager SendGrid failed: %s", e)
    return {"logged": True, "email_sent": sent}


async def escalate_impl(
    session: AsyncSession, req: EscalateToManagerRequest
) -> EscalationResponse:
    esc = Escalation(
        shift_type_id=req.shift_type_id,
        date=req.date,
        description=req.conflict_description,
        agent_reasoning=req.agent_reasoning,
        status=EscalationStatus.OPEN,
    )
    session.add(esc)
    await session.flush()
    return EscalationResponse(
        escalation_id=esc.id,
        status=esc.status.value,
        message="Conflict escalated to manager inbox.",
    )


async def explain_decision_impl(
    session: AsyncSession, req: ExplainDecisionRequest
) -> ExplainDecisionResponse:
    sh = (
        await session.execute(select(Shift).where(Shift.id == req.shift_id))
    ).scalar_one_or_none()
    if not sh:
        raise ValueError(f"Unknown shift_id: {req.shift_id}")

    text = ""
    if os.getenv("DEEPSEEK_API_KEY"):
        try:
            from agents.deepseek import chat_completion

            def _call():
                return chat_completion(
                    system=(
                        "You write short, professional workforce scheduling explanations "
                        "(2-4 sentences). No markdown."
                    ),
                    user=(
                        "Explain why this worker was assigned to this shift.\n\n"
                        f"Context: {req.assignment_context}\n"
                        f"Trace: {req.reasoning_trace}\n"
                    ),
                    max_tokens=500,
                )

            text = await asyncio.to_thread(_call)
        except Exception as e:
            logger.warning("DeepSeek explain_decision failed: %s", e)
    if not text:
        text = (
            f"Assigned based on availability, certifications, and fairness scoring "
            f"for the slot described in context."
        )
    sh.explanation = text
    sh.reasoning_trace = {"trace": req.reasoning_trace, "context": req.assignment_context}
    return ExplainDecisionResponse(explanation=text, stored=True)


async def generate_schedule_impl(
    session: AsyncSession, req: ScheduleRequest
) -> ScheduleResponse:
    sbu, dept = await _load_department_sbu(session, req.sbu_code, req.department_code)
    stmt = select(ShiftType).where(
        ShiftType.sbu_id == sbu.id,
        ShiftType.department_code == req.department_code,
    )
    if req.shift_type_ids:
        stmt = stmt.where(ShiftType.id.in_(req.shift_type_ids))
    shift_types = list((await session.execute(stmt)).scalars().all())
    if not shift_types:
        raise ValueError("No shift types found for this department.")

    import json
    import asyncio
    
    # Load SBU config directly (assumes PYTHONPATH allows this safely or relative path works)
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "configs", f"{req.sbu_code}.json"
    )
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            sbu_config = json.load(f)
    else:
        sbu_config = {"name": sbu.code}

    schedule_params = {
        "department_code": req.department_code,
        "date_range_start": req.date_range_start.isoformat(),
        "date_range_end": req.date_range_end.isoformat(),
        "shift_type": [st.name for st in shift_types],
        "headcount": req.headcount_per_shift,
        "constraints": req.constraints,
    }

    def _run_scheduler_sync():
        from agents.scheduler import run_scheduler
        return run_scheduler(schedule_params, sbu_config)

    # Hand off entire process to the ReAct agent
    agent_result = await asyncio.to_thread(_run_scheduler_sync)

    slots_out: list[ScheduleSlotResult] = []
    
    # Parse the tools trace to populate slots_out for the UI
    for step in agent_result.get("reasoning_steps", []):
        tool = step.get("tool")
        args = step.get("args", {})
        if tool == "create_shift":
            slots_out.append(
                ScheduleSlotResult(
                    date=datetime.strptime(args.get("date", req.date_range_start.isoformat()), "%Y-%m-%d").date() if isinstance(args.get("date"), str) else args.get("date", req.date_range_start),
                    shift_type=str(args.get("shift_type_id", "assigned")),
                    assigned_worker=f"Worker {args.get('worker_id', '?')}",
                    status="filled",
                    explanation=args.get("explanation", "Assigned by AI Scheduler")
                )
            )
        elif tool == "escalate_to_manager":
            slots_out.append(
                ScheduleSlotResult(
                    date=datetime.strptime(args.get("date", req.date_range_start.isoformat()), "%Y-%m-%d").date() if isinstance(args.get("date"), str) else args.get("date", req.date_range_start),
                    shift_type=str(args.get("shift_type_id", "unassigned")),
                    assigned_worker=None,
                    status="escalated",
                    explanation=args.get("conflict_description", "Escalated by AI Scheduler")
                )
            )

    return ScheduleResponse(
        slots=slots_out,
        total_slots=agent_result.get("total_iterations", 0),
        filled=agent_result.get("filled", 0),
        escalated=agent_result.get("escalated", 0),
        reasoning_summary=agent_result.get("summary", "Complete.")
    )

async def orchestrator_process_message(message: str, sbu_code: str, session_id: str) -> dict:
    def _run():
        from agents.orchestrator import process_message as orch_pm

        return orch_pm(message, sbu_code, session_id)

    if os.getenv("DEEPSEEK_API_KEY"):
        return await asyncio.to_thread(_run)
    msg_l = message.lower()
    intent = "query"
    routed = "direct_response"
    if any(w in msg_l for w in ("schedule", "roster", "shift", "assign")):
        intent, routed = "schedule", "scheduler"
    elif any(w in msg_l for w in ("leave", "swap", "cover", "replacement")):
        intent, routed = "swap", "swap_agent"
    return {
        "intent": intent,
        "routed_to": routed,
        "extracted_params": {
            "sbu_code": sbu_code,
            "note": "Heuristic routing (no DEEPSEEK_API_KEY)",
        },
        "sbu_config_loaded": False,
    }


async def resolve_leave_request_impl(
    session: AsyncSession, leave_request_id: int
) -> dict[str, Any]:
    lr = (
        await session.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.shift).selectinload(Shift.shift_type),
                selectinload(LeaveRequest.worker),
            )
            .where(LeaveRequest.id == leave_request_id)
        )
    ).scalar_one_or_none()
    if not lr:
        raise ValueError(f"Unknown leave_request_id: {leave_request_id}")
    if not lr.shift_id or not lr.shift:
        raise ValueError("Leave request has no linked shift to cover.")

    sh = lr.shift
    sbu = sh.shift_type.sbu
    sbu_config = _sbu_config(sbu)
    _ = sbu_config

    fc = await find_swap_candidates_impl(
        session, FindSwapCandidatesRequest(shift_id=sh.id)
    )
    attempted: list[dict] = []
    for sc in fc.candidates:
        w = sc.worker
        vr = await validate_schedule_impl(session, w.id, sh.shift_type_id, sh.date)
        if not vr.is_valid:
            attempted.append({"worker_id": w.id, "reason": vr.reason})
            continue
        creq = CreateShiftRequest(
            worker_id=w.id,
            shift_type_id=sh.shift_type_id,
            date=sh.date,
            start_time=sh.start_time,
            end_time=sh.end_time,
            explanation="Swap coverage for leave request",
            confirmed=True,
        )
        cresp = await create_shift_impl(session, creq)
        await session.flush()
        lr.status = LeaveStatus.COVERED
        lr.replacement_worker_id = w.id
        lr.resolution_summary = f"Covered by {w.name} (shift #{cresp.shift_id})"
        lr.resolved_at = datetime.utcnow()
        sh.status = ShiftStatus.SWAPPED

        email_sent, _, name = await notify_worker_impl(
            session,
            w.id,
            "swap",
            "New shift assignment (coverage)",
            lr.resolution_summary or "",
            cresp.shift_id,
        )
        await notify_manager_impl(
            session,
            sh.shift_type.department_code,
            "Leave request covered",
            lr.resolution_summary or "",
            [sh.id, cresp.shift_id],
        )
        return {
            "status": "resolved",
            "replacement_worker_id": w.id,
            "replacement_worker_name": name,
            "shift_id": cresp.shift_id,
            "notify_email_sent": email_sent,
        }

    esc = await escalate_impl(
        session,
        EscalateToManagerRequest(
            shift_type_id=sh.shift_type_id,
            date=sh.date,
            conflict_description=f"No swap for leave request #{leave_request_id}",
            agent_reasoning="No swap candidate passed validation.",
            attempted_candidates=attempted,
        ),
    )
    lr.resolution_summary = "Escalated — no automatic coverage."
    return {"status": "escalated", "escalation_id": esc.escalation_id}
