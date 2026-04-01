"""
AXIS Agent 2: Scheduler Agent (ReAct Loop)
Uses a Reason-Act-Observe loop to fill shift slots one by one.
Iterates until every slot is filled or escalates unresolvable conflicts.
"""
from langchain_core.messages import SystemMessage, HumanMessage

from agents.deepseek import has_deepseek_key, langchain_chat_model
from agents.tools import SCHEDULER_TOOLS

SCHEDULER_SYSTEM_PROMPT = """You are the AXIS Scheduler Agent. You fill shift slots one by one using a 
Reason-Act-Observe loop.

You have been given a scheduling request by the Orchestrator Agent. Your job is to fill every 
requested shift slot with the best available worker.

FOR EACH SLOT, follow this process:
1. REASON: Identify the next unfilled slot. Determine what worker type is needed.
2. ACT: Call GetAvailableStaff to find eligible candidates.
3. OBSERVE: Review the candidates, pick the one with the highest fairness score.
4. ACT: Call ValidateSchedule on the top candidate.
5. OBSERVE: If validation passes, call CreateShift. If it fails, try the next candidate.
6. ACT: Call ExplainDecision to generate an audit trail entry.
7. ITERATE: Move to the next slot.

If ALL candidates for a slot are exhausted, call EscalateToManager with your full reasoning.

CRITICAL RULES:
- NEVER assign a worker without calling ValidateSchedule first
- NEVER skip the ExplainDecision step - every assignment needs an audit trail
- ALWAYS prefer the candidate with the highest fairness score
- If a candidate fails validation, explain WHY in your reasoning before trying the next one
- Track cumulative assignments: a worker assigned in slot 1 may no longer be valid for slot 5

You will receive the scheduling parameters as structured JSON from the Orchestrator.
Work through every slot methodically. Do not rush or skip validation.
"""


def create_scheduler_agent():
    """Create the Scheduler Agent with ReAct loop using LangChain."""
    if not has_deepseek_key():
        raise RuntimeError("DEEPSEEK_API_KEY is required for the scheduler agent")
    llm = langchain_chat_model(max_tokens=4096, temperature=0)
    return llm.bind_tools(SCHEDULER_TOOLS)


def run_scheduler(schedule_params: dict, sbu_config: dict) -> dict:
    """
    Execute the scheduling ReAct loop.
    
    Args:
        schedule_params: Extracted parameters from the Orchestrator
            - department_code: str
            - date_range_start: str (YYYY-MM-DD)
            - date_range_end: str (YYYY-MM-DD)
            - shift_type: str or list
            - headcount: int
            - constraints: dict
        sbu_config: The loaded SBU configuration profile
    
    Returns:
        Schedule result with filled/escalated slots and reasoning.
    """
    agent = create_scheduler_agent()

    # Build the task description for the agent
    task = f"""Schedule the following:
    
SBU Config: {sbu_config.get('name', 'Unknown')}
Department: {schedule_params.get('department_code', 'all')}
Date Range: {schedule_params.get('date_range_start')} to {schedule_params.get('date_range_end')}
Shift Types: {schedule_params.get('shift_type', 'all configured types')}
Headcount per shift: {schedule_params.get('headcount', 1)}
Additional constraints: {schedule_params.get('constraints', 'none')}

Available shift types in this SBU config:
{_format_shift_types(sbu_config)}

Begin filling slots. Work through each date, each shift type, each required headcount position.
"""

    messages = [
        SystemMessage(content=SCHEDULER_SYSTEM_PROMPT),
        HumanMessage(content=task)
    ]

    # ReAct Loop - iterate until completion
    results = {
        "slots": [],
        "filled": 0,
        "escalated": 0,
        "reasoning_steps": []
    }

    max_iterations = 50  # Safety limit
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = agent.invoke(messages)
        messages.append(response)

        # Check if agent used tools
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                # Execute the tool
                tool_fn = _get_tool_by_name(tool_name)
                if tool_fn:
                    try:
                        tool_result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        tool_result = {"error": str(e)}

                    # Track reasoning
                    results["reasoning_steps"].append({
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": tool_args,
                        "result_summary": _summarize_result(tool_result)
                    })

                    # Track slot results
                    if tool_name == "create_shift":
                        results["filled"] += 1
                    elif tool_name == "escalate_to_manager":
                        results["escalated"] += 1

                    # Feed result back to agent
                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"]
                    ))
        else:
            # Agent finished (no more tool calls)
            results["summary"] = response.content
            break

    results["total_iterations"] = iteration
    return results


def _format_shift_types(sbu_config: dict) -> str:
    """Format shift types from config for the agent prompt."""
    shift_types = sbu_config.get("shift_types", [])
    if not shift_types:
        return "No shift types configured"
    lines = []
    for st in shift_types:
        lines.append(
            f"- {st['name']}: {st['start_time']}-{st['end_time']} "
            f"(requires: {', '.join(st.get('required_certifications', ['none']))})"
        )
    return "\n".join(lines)


def _get_tool_by_name(name: str):
    """Look up a tool function by name."""
    for tool in SCHEDULER_TOOLS:
        if tool.name == name:
            return tool
    return None


def _summarize_result(result) -> str:
    """Create a brief summary of a tool result for logging."""
    if isinstance(result, dict):
        if "error" in result:
            return f"Error: {result['error']}"
        if "candidates" in result:
            return f"Found {len(result['candidates'])} candidates"
        if "is_valid" in result:
            return f"Valid: {result['is_valid']} - {result.get('reason', '')}"
        if "shift_id" in result:
            return f"Shift created: #{result['shift_id']}"
    return str(result)[:100]
