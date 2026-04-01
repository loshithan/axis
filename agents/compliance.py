"""
AXIS Agent 4: Compliance Agent
Runs on a schedule (not triggered by user messages).
Scans active shifts, generates compliance reports, updates retention dashboard.
"""
from datetime import datetime, date

from agents.deepseek import chat_completion, has_deepseek_key


COMPLIANCE_SYSTEM_PROMPT = """You are the AXIS Compliance Agent. You run on a scheduled basis to audit 
the workforce scheduling system.

You check three things:
1. Are all active shifts compliant with rest rules?
2. Are any workers approaching burnout thresholds?
3. What does this month's fairness summary show?

Generate a structured compliance report with:
- Violations found (shift IDs, worker names, rule broken)
- Workers at burnout risk (hours worked, consecutive shifts, fairness score)
- Fairness summary (distribution of shifts across workers)
- Recommendations for managers

Respond ONLY with JSON (no markdown, no backticks):
{
    "report_date": "YYYY-MM-DD",
    "sbu_code": "...",
    "violations": [...],
    "burnout_risks": [...],
    "fairness_summary": {...},
    "recommendations": [...]
}
"""


def run_compliance_check(sbu_code: str, shifts_data: list, workers_data: list, sbu_config: dict) -> dict:
    """
    Run the compliance check for an SBU.
    
    Args:
        sbu_code: The SBU to check
        shifts_data: All active shifts for the current period
        workers_data: All workers with their current hours/stats
        sbu_config: SBU configuration with compliance rules
    
    Returns:
        Compliance report as structured dict.
    """
    # Pre-compute metrics before sending to LLM
    violations = _check_rest_violations(shifts_data, sbu_config)
    burnout_risks = _check_burnout_risks(workers_data, sbu_config)
    fairness = _calculate_fairness_summary(workers_data)

    # Use DeepSeek to generate human-readable report and recommendations
    context = f"""SBU: {sbu_config.get('name', sbu_code)}
Date: {date.today().isoformat()}

REST VIOLATIONS FOUND:
{_format_violations(violations)}

BURNOUT RISK WORKERS:
{_format_burnout_risks(burnout_risks)}

FAIRNESS METRICS:
{_format_fairness(fairness)}

Generate the compliance report with actionable recommendations.
"""

    import json

    raw = ""
    if has_deepseek_key():
        try:
            raw = chat_completion(
                system=COMPLIANCE_SYSTEM_PROMPT,
                user=context,
                max_tokens=2000,
            )
        except Exception:
            raw = ""
    try:
        report = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        report = None
    if not report:
        report = {
            "report_date": date.today().isoformat(),
            "sbu_code": sbu_code,
            "violations": violations,
            "burnout_risks": burnout_risks,
            "fairness_summary": fairness,
            "recommendations": [
                "Unable to generate AI recommendations (set DEEPSEEK_API_KEY or review data manually)."
            ],
            "raw_response": raw or None,
        }

    return report


def _check_rest_violations(shifts: list, config: dict) -> list:
    """Check all shifts for minimum rest period violations."""
    min_rest = config.get("min_rest_hours", 11)
    violations = []

    # Group shifts by worker
    worker_shifts = {}
    for shift in shifts:
        wid = shift.get("worker_id")
        worker_shifts.setdefault(wid, []).append(shift)

    for wid, w_shifts in worker_shifts.items():
        sorted_shifts = sorted(w_shifts, key=lambda s: (s["date"], s["start_time"]))
        for i in range(1, len(sorted_shifts)):
            prev = sorted_shifts[i - 1]
            curr = sorted_shifts[i]
            # Calculate gap (simplified)
            gap_hours = _estimate_gap_hours(prev, curr)
            if gap_hours is not None and gap_hours < min_rest:
                violations.append({
                    "worker_id": wid,
                    "shift_ids": [prev.get("id"), curr.get("id")],
                    "rule": "minimum_rest_period",
                    "detail": f"Only {gap_hours:.1f}h rest (min {min_rest}h required)"
                })

    return violations


def _check_burnout_risks(workers: list, config: dict) -> list:
    """Identify workers approaching burnout thresholds."""
    max_weekly = config.get("max_weekly_hours", 40)
    threshold = max_weekly * 0.85  # Flag at 85% of max

    risks = []
    for worker in workers:
        hours = worker.get("weekly_hours_used", 0)
        consecutive = worker.get("consecutive_shifts", 0)

        risk_level = "low"
        reasons = []

        if hours >= max_weekly:
            risk_level = "critical"
            reasons.append(f"In overtime: {hours:.0f}h/{max_weekly:.0f}h")
        elif hours >= threshold:
            risk_level = "high"
            reasons.append(f"Approaching limit: {hours:.0f}h/{max_weekly:.0f}h")

        if consecutive >= 5:
            risk_level = "critical" if risk_level != "critical" else risk_level
            reasons.append(f"Consecutive shifts: {consecutive}")
        elif consecutive >= 3:
            if risk_level == "low":
                risk_level = "medium"
            reasons.append(f"Consecutive shifts: {consecutive}")

        if risk_level != "low":
            risks.append({
                "worker_id": worker.get("id"),
                "worker_name": worker.get("name"),
                "risk_level": risk_level,
                "reasons": reasons,
                "weekly_hours": hours,
                "consecutive_shifts": consecutive
            })

    return sorted(risks, key=lambda r: {"critical": 0, "high": 1, "medium": 2}.get(r["risk_level"], 3))


def _calculate_fairness_summary(workers: list) -> dict:
    """Calculate fairness distribution across the team."""
    if not workers:
        return {"avg_hours": 0, "std_dev": 0, "min_hours": 0, "max_hours": 0}

    hours_list = [w.get("weekly_hours_used", 0) for w in workers]
    avg = sum(hours_list) / len(hours_list)
    variance = sum((h - avg) ** 2 for h in hours_list) / len(hours_list)
    std_dev = variance ** 0.5

    return {
        "avg_hours": round(avg, 1),
        "std_dev": round(std_dev, 1),
        "min_hours": round(min(hours_list), 1),
        "max_hours": round(max(hours_list), 1),
        "total_workers": len(workers),
        "distribution_quality": "good" if std_dev < avg * 0.2 else "needs_improvement"
    }


def _estimate_gap_hours(prev_shift: dict, curr_shift: dict) -> float | None:
    """Estimate hours between two consecutive shifts."""
    try:
        prev_end = datetime.combine(prev_shift["date"], prev_shift["end_time"])
        curr_start = datetime.combine(curr_shift["date"], curr_shift["start_time"])
        gap = (curr_start - prev_end).total_seconds() / 3600
        return gap if gap >= 0 else None
    except (KeyError, TypeError):
        return None


def _format_violations(violations: list) -> str:
    if not violations:
        return "None found."
    return "\n".join(f"- Worker {v['worker_id']}: {v['detail']}" for v in violations)


def _format_burnout_risks(risks: list) -> str:
    if not risks:
        return "No workers at risk."
    return "\n".join(
        f"- {r['worker_name']} ({r['risk_level']}): {', '.join(r['reasons'])}"
        for r in risks
    )


def _format_fairness(fairness: dict) -> str:
    return (
        f"Average hours: {fairness['avg_hours']}h | "
        f"Std Dev: {fairness['std_dev']}h | "
        f"Range: {fairness['min_hours']}-{fairness['max_hours']}h | "
        f"Quality: {fairness.get('distribution_quality', 'unknown')}"
    )
