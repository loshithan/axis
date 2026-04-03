"""
AXIS Agent 1: Orchestrator Agent
Every message from a manager hits this agent first.
It parses intent, extracts parameters, loads SBU config, and routes.
"""
import json

from agents.deepseek import chat_completion, has_deepseek_key

ORCHESTRATOR_SYSTEM_PROMPT = """You are the AXIS Orchestrator Agent. Your role is to understand manager messages
and route them to the correct specialist agent.

You do NOT schedule, swap, or validate. You ONLY route.

For every message, determine:
1. Intent: "schedule" | "swap" | "query" | "report"
2. SBU context (from session or message)
3. Extracted parameters

RESPOND ONLY WITH JSON (no markdown, no backticks):
{
    "intent": "schedule|swap|query|report",
    "routed_to": "scheduler|swap_agent|direct_response",
    "extracted_params": {
        "department_code": "...",
        "date_range_start": "YYYY-MM-DD",
        "date_range_end": "YYYY-MM-DD",
        "start_time": "HH:MM:SS or null",
        "end_time": "HH:MM:SS or null",
        "shift_type": "exact shift type name mentioned (e.g. 'Afternoon ICU', 'Morning Emergency') or null",
        "headcount": 1,
        "constraints": {},
        "worker_name": "full name of the specific worker mentioned in the message, or null if no specific worker is named",
        "leave_date": "YYYY-MM-DD (for swap intent only, the specific date of leave, or null)"
    },
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this intent was chosen"
}

Intent classification rules:
- "schedule": Any request to create, assign, or generate shifts/rosters. If a specific worker name is mentioned, extract it into worker_name. If a specific shift type is mentioned (e.g. "afternoon ICU"), extract it into shift_type.
- "swap": Any request about leave, replacement, coverage, or shift exchange. Extract worker_name and leave_date.
- "query": Questions about existing shifts, staff, availability, or schedule status. Always extract date_range_start and date_range_end even for single-day queries.
- "report": Requests for compliance reports, fairness summaries, dashboards

Date rules:
- Always resolve relative dates ("tomorrow", "next week", "7th April") to absolute YYYY-MM-DD using Today's date provided above.
- For a single day query, set date_range_start and date_range_end to the same date.
- Never leave date fields null if a date was mentioned in the message.
"""


def classify_intent(message: str, sbu_code: str, session_id: str) -> dict:
    """
    Parse a manager's natural language message and classify the intent.
    Returns structured routing information for the specialist agent.
    """
    from datetime import date
    today = date.today().isoformat()
    result_text = chat_completion(
        system=ORCHESTRATOR_SYSTEM_PROMPT,
        user=(
            f"Today's date: {today}\n"
            f"SBU Context: {sbu_code}\nSession: {session_id}\n\nManager message: {message}"
        ),
        max_tokens=500,
    )
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "intent": "query",
                "routed_to": "direct_response",
                "extracted_params": {},
                "confidence": 0.0,
                "reasoning": "Failed to parse intent"
            }

    # Ensure sbu_code is in the params
    result.setdefault("extracted_params", {})
    result["extracted_params"]["sbu_code"] = sbu_code

    return result


def load_sbu_config(sbu_code: str) -> dict:
    """Load the SBU configuration profile from the database or file."""
    # TODO: Load from DB in production. For MVP, load from JSON file.
    import os
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "configs", f"{sbu_code}.json"
    )
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    raise FileNotFoundError(f"SBU config not found: {sbu_code}")


def process_message(message: str, sbu_code: str, session_id: str) -> dict:
    """
    Full Orchestrator pipeline:
    1. Classify intent
    2. Load SBU config
    3. Return routing decision with config context
    """
    if has_deepseek_key():
        routing = classify_intent(message, sbu_code, session_id)
    else:
        routing = {
            "intent": "query",
            "routed_to": "direct_response",
            "extracted_params": {"sbu_code": sbu_code},
            "confidence": 0.0,
            "reasoning": "DEEPSEEK_API_KEY not set — no LLM routing",
        }

    # Step 2: Load config
    try:
        sbu_config = load_sbu_config(sbu_code)
        routing["sbu_config_loaded"] = True
        routing["sbu_config"] = sbu_config
    except FileNotFoundError:
        routing["sbu_config_loaded"] = False
        routing["sbu_config"] = {}

    return routing
