"""
AXIS Business Rules Engine
All constraint validation runs here — NOT in the AI agent.
The agent calls these rules through the ValidateSchedule tool.
"""
from datetime import date, time, datetime, timedelta
from dataclasses import dataclass


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    reason: str


# ── Overlap Detection ──

def check_overlap(
    new_start: time,
    new_end: time,
    new_date: date,
    existing_shifts: list[dict]
) -> ValidationCheck:
    """
    Overlap exists when:
      NewShiftStart < ExistingShiftEnd AND NewShiftEnd > ExistingShiftStart
    """
    for shift in existing_shifts:
        if shift["date"] != new_date:
            continue
        if new_start < shift["end_time"] and new_end > shift["start_time"]:
            return ValidationCheck(
                name="overlap",
                passed=False,
                reason=f"Overlaps with existing shift ({shift['start_time']}-{shift['end_time']}) "
                       f"for {shift.get('shift_type', 'unknown type')}"
            )
    return ValidationCheck(name="overlap", passed=True, reason="No overlapping shifts")


# ── Availability Check ──

def check_availability(
    worker_id: int,
    shift_date: date,
    start_time: time,
    end_time: time,
    leave_dates: list[date],
    availability_slots: list[dict],
) -> ValidationCheck:
    """Verify worker is not on leave and has declared availability."""
    # Check leave
    if shift_date in leave_dates:
        return ValidationCheck(
            name="availability",
            passed=False,
            reason=f"Worker is on approved leave for {shift_date}"
        )

    # Check declared availability
    has_slot = any(
        slot["date"] == shift_date
        and slot["start_time"] <= start_time
        and slot["end_time"] >= end_time
        and slot["is_available"]
        for slot in availability_slots
    )
    if not has_slot:
        return ValidationCheck(
            name="availability",
            passed=False,
            reason=f"Worker has not declared availability for {shift_date} {start_time}-{end_time}"
        )

    return ValidationCheck(name="availability", passed=True, reason="Worker is available")


# ── Weekly Hours Cap ──

def check_weekly_hours(
    current_weekly_hours: float,
    shift_duration_hours: float,
    max_weekly_hours: float = 40.0
) -> ValidationCheck:
    """Ensure assignment won't exceed weekly hour cap."""
    projected = current_weekly_hours + shift_duration_hours
    if projected > max_weekly_hours:
        return ValidationCheck(
            name="weekly_hours",
            passed=False,
            reason=f"Would exceed weekly cap: {projected:.1f}h / {max_weekly_hours:.1f}h max"
        )
    return ValidationCheck(
        name="weekly_hours",
        passed=True,
        reason=f"Within limits: {projected:.1f}h / {max_weekly_hours:.1f}h"
    )


# ── Minimum Rest Period ──

def check_rest_period(
    shift_date: date,
    shift_start: time,
    shift_end: time,
    adjacent_shifts: list[dict],
    min_rest_hours: float = 11.0
) -> ValidationCheck:
    """Check minimum rest period between consecutive shifts (SBU-configurable)."""
    new_start_dt = datetime.combine(shift_date, shift_start)
    new_end_dt = datetime.combine(shift_date, shift_end)

    for adj in adjacent_shifts:
        adj_start_dt = datetime.combine(adj["date"], adj["start_time"])
        adj_end_dt = datetime.combine(adj["date"], adj["end_time"])

        # Gap between this shift end and next shift start
        if adj_start_dt > new_end_dt:
            gap = (adj_start_dt - new_end_dt).total_seconds() / 3600
            if gap < min_rest_hours:
                return ValidationCheck(
                    name="rest_period",
                    passed=False,
                    reason=f"Only {gap:.1f}h rest before next shift (min {min_rest_hours}h required)"
                )

        # Gap between previous shift end and this shift start
        if new_start_dt > adj_end_dt:
            gap = (new_start_dt - adj_end_dt).total_seconds() / 3600
            if gap < min_rest_hours:
                return ValidationCheck(
                    name="rest_period",
                    passed=False,
                    reason=f"Only {gap:.1f}h rest after previous shift (min {min_rest_hours}h required)"
                )

    return ValidationCheck(name="rest_period", passed=True, reason="Adequate rest period")


# ── Certification Matching ──

def check_certifications(
    worker_certs: list[str],
    required_certs: list[str]
) -> ValidationCheck:
    """Verify worker holds all required certifications for the shift."""
    missing = [c for c in required_certs if c not in worker_certs]
    if missing:
        return ValidationCheck(
            name="certifications",
            passed=False,
            reason=f"Missing required certifications: {', '.join(missing)}"
        )
    return ValidationCheck(name="certifications", passed=True, reason="All certifications met")


# ── Fairness Scoring ──

def calculate_fairness_score(
    weekly_hours: float,
    max_weekly_hours: float,
    consecutive_shifts: int,
    avg_team_hours: float
) -> tuple[float, str]:
    """
    Fairness Score calculation:
      -20 if worker is in overtime
      -15 if worker has consecutive shifts (3+)
      +15 if worker is underutilised this period
    Returns (score, explanation)
    """
    score = 0.0
    reasons = []

    # Overtime penalty
    if weekly_hours >= max_weekly_hours:
        score -= 20
        reasons.append(f"-20 (in overtime: {weekly_hours:.0f}h/{max_weekly_hours:.0f}h)")

    # Consecutive shifts penalty
    if consecutive_shifts >= 3:
        score -= 15
        reasons.append(f"-15 (consecutive shifts: {consecutive_shifts})")

    # Underutilisation bonus
    if weekly_hours < avg_team_hours * 0.7:
        score += 15
        reasons.append(f"+15 (underutilised: {weekly_hours:.0f}h vs team avg {avg_team_hours:.0f}h)")

    explanation = " | ".join(reasons) if reasons else "Neutral (no modifiers)"
    return score, explanation


# ── Full Validation Pipeline ──

def validate_assignment(
    worker: dict,
    shift_proposal: dict,
    existing_shifts: list[dict],
    leave_dates: list[date],
    availability_slots: list[dict],
    adjacent_shifts: list[dict],
    sbu_config: dict
) -> tuple[bool, str, list[dict]]:
    """
    Run all validation checks in order. Returns:
      (is_valid, reason_string, checks_list)
    """
    checks = []

    # 1. Certifications
    cert_check = check_certifications(
        worker.get("certifications", []),
        shift_proposal.get("required_certifications", [])
    )
    checks.append({"check": cert_check.name, "passed": cert_check.passed, "reason": cert_check.reason})
    if not cert_check.passed:
        return False, cert_check.reason, checks

    # 2. Availability
    avail_check = check_availability(
        worker["id"], shift_proposal["date"],
        shift_proposal["start_time"], shift_proposal["end_time"],
        leave_dates, availability_slots
    )
    checks.append({"check": avail_check.name, "passed": avail_check.passed, "reason": avail_check.reason})
    if not avail_check.passed:
        return False, avail_check.reason, checks

    # 3. Overlap
    overlap_check = check_overlap(
        shift_proposal["start_time"], shift_proposal["end_time"],
        shift_proposal["date"], existing_shifts
    )
    checks.append({"check": overlap_check.name, "passed": overlap_check.passed, "reason": overlap_check.reason})
    if not overlap_check.passed:
        return False, overlap_check.reason, checks

    # 4. Weekly hours
    shift_hours = _calc_shift_hours(shift_proposal["start_time"], shift_proposal["end_time"])
    hours_check = check_weekly_hours(
        worker.get("weekly_hours_used", 0),
        shift_hours,
        worker.get("max_weekly_hours", sbu_config.get("max_weekly_hours", 40))
    )
    checks.append({"check": hours_check.name, "passed": hours_check.passed, "reason": hours_check.reason})
    if not hours_check.passed:
        return False, hours_check.reason, checks

    # 5. Rest period
    min_rest = sbu_config.get("min_rest_hours", 11)
    rest_check = check_rest_period(
        shift_proposal["date"], shift_proposal["start_time"],
        shift_proposal["end_time"], adjacent_shifts, min_rest
    )
    checks.append({"check": rest_check.name, "passed": rest_check.passed, "reason": rest_check.reason})
    if not rest_check.passed:
        return False, rest_check.reason, checks

    return True, "All checks passed", checks


def _calc_shift_hours(start: time, end: time) -> float:
    """Calculate shift duration in hours."""
    start_dt = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)  # Overnight shift
    return (end_dt - start_dt).total_seconds() / 3600
