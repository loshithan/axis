"""
AXIS Database Models
SQLAlchemy ORM models for the workforce scheduling platform.
"""
from datetime import datetime, date, time
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Time, Boolean,
    Float, ForeignKey, Text, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# ── Enums ──

class ShiftStatus(str, PyEnum):
    OPEN = "open"
    PENDING = "pending"   # assigned worker has a pending leave request
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    SWAPPED = "swapped"


class OTRequestStatus(str, PyEnum):
    OPEN = "open"
    NOTIFIED = "notified"
    ASSIGNED = "assigned"
    CANCELLED = "cancelled"


class OTApplicationStatus(str, PyEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    REJECTED = "rejected"


class LeaveStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COVERED = "covered"  # Leave approved AND replacement found


class EscalationStatus(str, PyEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ── Core Models ──

class SBU(Base):
    """Strategic Business Unit - each has its own scheduling config."""
    __tablename__ = "sbus"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)  # e.g., "hospitals", "mobility"
    timezone = Column(String(50), default="Asia/Colombo")
    config = Column(JSON, nullable=False)  # Full SBU configuration profile
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    departments = relationship("Department", back_populates="sbu")
    shift_types = relationship("ShiftType", back_populates="sbu")


class Department(Base):
    """Department within an SBU (e.g., ICU, Emergency, Ground Crew)."""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    sbu_id = Column(Integer, ForeignKey("sbus.id"), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False)

    sbu = relationship("SBU", back_populates="departments")
    workers = relationship("Worker", back_populates="department")

    __table_args__ = (UniqueConstraint("sbu_id", "code"),)


class ShiftType(Base):
    """Shift type definition per SBU (e.g., Morning ICU, Night Ground)."""
    __tablename__ = "shift_types"

    id = Column(Integer, primary_key=True)
    sbu_id = Column(Integer, ForeignKey("sbus.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Morning ICU"
    code = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    required_certifications = Column(JSON, default=list)  # List of cert codes
    min_headcount = Column(Integer, default=1)
    department_code = Column(String(50), nullable=False)

    sbu = relationship("SBU", back_populates="shift_types")

    __table_args__ = (UniqueConstraint("sbu_id", "code"),)


class Worker(Base):
    """Employee who can be assigned to shifts."""
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200))
    phone = Column(String(20))
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    employee_type = Column(String(50), default="nurse")  # nurse, doctor, technician, admin
    certifications = Column(JSON, default=list)  # List of cert codes
    max_weekly_hours = Column(Float, default=40.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department", back_populates="workers")
    shifts = relationship("Shift", back_populates="worker")
    availability = relationship("Availability", back_populates="worker")
    leave_requests = relationship("LeaveRequest", back_populates="worker", foreign_keys="[LeaveRequest.worker_id]")


class Availability(Base):
    """Worker availability declaration for a specific date/slot."""
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_available = Column(Boolean, default=True)

    worker = relationship("Worker", back_populates="availability")

    __table_args__ = (UniqueConstraint("worker_id", "date", "start_time"),)


class Shift(Base):
    """An assigned shift - the core scheduling record."""
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    shift_type_id = Column(Integer, ForeignKey("shift_types.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(Enum(ShiftStatus, name="shift_status", create_type=False, values_callable=lambda x: [e.value for e in x]), default=ShiftStatus.OPEN)
    fairness_score = Column(Float)  # Score at time of assignment
    explanation = Column(Text)  # Plain-English decision explanation
    reasoning_trace = Column(JSON)  # Full agent reasoning for audit
    created_by = Column(String(50), default="agent")  # "agent" or "manual"
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime)

    worker = relationship("Worker", back_populates="shifts")
    shift_type = relationship("ShiftType")

    __table_args__ = (UniqueConstraint("worker_id", "date", "start_time"),)


class LeaveRequest(Base):
    """Worker leave request - triggers the Swap Agent."""
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"))  # The shift needing coverage
    date = Column(Date, nullable=False)
    reason = Column(Text)
    status = Column(Enum(LeaveStatus, name="leave_status", create_type=False, values_callable=lambda x: [e.value for e in x]), default=LeaveStatus.PENDING)
    replacement_worker_id = Column(Integer, ForeignKey("workers.id"))
    resolution_summary = Column(Text)  # Agent's summary of what happened
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    worker = relationship("Worker", back_populates="leave_requests", foreign_keys="[LeaveRequest.worker_id]")
    shift = relationship("Shift")
    replacement = relationship("Worker", foreign_keys=[replacement_worker_id])


class Escalation(Base):
    """Unresolvable conflict escalated to manager by an agent."""
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True)
    shift_type_id = Column(Integer, ForeignKey("shift_types.id"))
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    agent_reasoning = Column(Text, nullable=False)
    status = Column(Enum(EscalationStatus, name="escalation_status", create_type=False, values_callable=lambda x: [e.value for e in x]), default=EscalationStatus.OPEN)
    resolved_by = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    shift_type = relationship("ShiftType")


class OTRequest(Base):
    """An open shift advertised for overtime coverage."""
    __tablename__ = "ot_requests"

    id                 = Column(Integer, primary_key=True)
    shift_id           = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    escalation_id      = Column(Integer, ForeignKey("escalations.id"), nullable=True)
    leave_request_id   = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
    status             = Column(Enum(OTRequestStatus, name="ot_request_status", create_type=False,
                                    values_callable=lambda x: [e.value for e in x]),
                                default=OTRequestStatus.OPEN)
    created_at         = Column(DateTime, default=datetime.utcnow)
    assigned_at        = Column(DateTime, nullable=True)
    assigned_worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    notes              = Column(Text, nullable=True)

    shift           = relationship("Shift")
    escalation      = relationship("Escalation")
    leave_request   = relationship("LeaveRequest")
    assigned_worker = relationship("Worker", foreign_keys=[assigned_worker_id])
    applications    = relationship("OTApplication", back_populates="ot_request",
                                   order_by="OTApplication.applied_at")


class OTApplication(Base):
    """A worker's application (or notification) for an OT shift — FIFO ordered by applied_at."""
    __tablename__ = "ot_applications"

    id             = Column(Integer, primary_key=True)
    ot_request_id  = Column(Integer, ForeignKey("ot_requests.id"), nullable=False)
    worker_id      = Column(Integer, ForeignKey("workers.id"), nullable=False)
    status         = Column(Enum(OTApplicationStatus, name="ot_application_status", create_type=False,
                                 values_callable=lambda x: [e.value for e in x]),
                            default=OTApplicationStatus.PENDING)
    applied_at     = Column(DateTime, default=datetime.utcnow)
    resolved_at    = Column(DateTime, nullable=True)
    notified_at    = Column(DateTime, nullable=True)
    email_sent     = Column(Boolean, default=False)

    ot_request = relationship("OTRequest", back_populates="applications")
    worker     = relationship("Worker")

    __table_args__ = (UniqueConstraint("ot_request_id", "worker_id"),)


class AgentLog(Base):
    """Full reasoning trace log for every agent interaction."""
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True)
    agent_name = Column(String(50), nullable=False)  # orchestrator, scheduler, swap, compliance
    session_id = Column(String(100), nullable=False)
    input_message = Column(Text)
    reasoning_steps = Column(JSON)  # List of {thought, action, observation}
    tools_called = Column(JSON)  # List of tool names and inputs
    output = Column(JSON)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
