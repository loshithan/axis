"""
AXIS Agent 3: Swap Agent
Activates when a worker submits a leave request.
Operates without human intervention to find a valid replacement.
"""
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agents.tools import SWAP_TOOLS

SWAP_SYSTEM_PROMPT = """You are the AXIS Swap Agent. You activate when a worker submits a leave request.
Your ONLY goal: find a valid replacement, assign them, notify them, and tell the manager.

You operate WITHOUT human intervention. Follow this exact pipeline:

1. Call FindSwapCandidates with the shift_id that needs coverage.
2. Take the top-ranked candidate.
3. Call ValidateSchedule to verify the candidate is valid.
4. If valid:
   a. Call CreateShift to assign the replacement.
   b. Call NotifyWorker to inform the replacement (push + email).
   c. Call NotifyManager to inform the manager of the resolution.
   d. DONE.
5. If invalid:
   a. Note WHY the candidate failed.
   b. Move to the next candidate.
   c. Repeat from step 3.
6. If ALL candidates exhausted:
   a. Call EscalateToManager with your full reasoning of every candidate tried.

CRITICAL:
- Never assign without validating first
- Always notify both the worker AND the manager
- If overtime risk is HIGH for a candidate, prefer someone with lower risk
- Include the failed candidates and reasons in any escalation
"""


def create_swap_agent():
    """Create the Swap Agent with tool access."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        temperature=0,
        max_tokens=2048,
    )
    return llm.bind_tools(SWAP_TOOLS)


def resolve_leave_request(leave_request: dict, shift: dict, sbu_config: dict) -> dict:
    """
    Execute the swap resolution pipeline.
    
    Args:
        leave_request: The leave request record
        shift: The shift that needs coverage
        sbu_config: SBU configuration for context
    
    Returns:
        Resolution result: replacement assigned, or escalation created.
    """
    agent = create_swap_agent()

    task = f"""A worker has submitted a leave request. Find a replacement.

Leave Request:
- Worker: {leave_request.get('worker_name', 'Unknown')} (ID: {leave_request.get('worker_id')})
- Date: {leave_request.get('date')}
- Reason: {leave_request.get('reason', 'Not specified')}

Shift Needing Coverage:
- Shift ID: {shift.get('id')}
- Type: {shift.get('shift_type', 'Unknown')}
- Date: {shift.get('date')}
- Time: {shift.get('start_time')} - {shift.get('end_time')}
- Department: {shift.get('department_code')}
- Required Certifications: {shift.get('required_certifications', [])}

SBU: {sbu_config.get('name', 'Unknown')}

Find a replacement now. Start by calling FindSwapCandidates with shift_id={shift.get('id')}.
"""

    messages = [
        SystemMessage(content=SWAP_SYSTEM_PROMPT),
        HumanMessage(content=task)
    ]

    result = {
        "status": "pending",
        "replacement_worker_id": None,
        "replacement_worker_name": None,
        "candidates_tried": [],
        "escalated": False,
        "reasoning_steps": []
    }

    max_iterations = 20
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = agent.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                tool_fn = _get_tool_by_name(tool_name)
                if tool_fn:
                    try:
                        tool_result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        tool_result = {"error": str(e)}

                    result["reasoning_steps"].append({
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    if tool_name == "create_shift":
                        result["status"] = "resolved"
                        result["replacement_worker_id"] = tool_args.get("worker_id")
                    elif tool_name == "escalate_to_manager":
                        result["status"] = "escalated"
                        result["escalated"] = True
                    elif tool_name == "notify_manager":
                        # Pipeline complete after manager notification
                        pass

                    messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"]
                    ))
        else:
            result["summary"] = response.content
            break

    return result


def _get_tool_by_name(name: str):
    for tool in SWAP_TOOLS:
        if tool.name == name:
            return tool
    return None
