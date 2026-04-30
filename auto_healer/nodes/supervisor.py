"""
Supervisor Agent Node

The Supervisor is the central router that analyzes alerts and delegates tasks
to specialized worker agents (Log Expert, Infra Expert). It NEVER attempts to
fix issues itself - only routes to the appropriate specialist.

CRITICAL: Uses Pydantic Structured Outputs to enforce strict routing format.
This prevents the local LLM from hallucinating or outputting plain text.
"""

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from auto_healer.llm_config import get_llm
from auto_healer.state import AlertTeamState

logger = logging.getLogger(__name__)


class SupervisorDecision(BaseModel):
    """
    Pydantic model for Supervisor routing decisions.

    CRITICAL: This enforces structured output. The LLM MUST output this exact
    format, preventing plain text responses that could break the graph.
    """

    next_worker: Literal["log_expert", "infra_expert", "FINISH"] = Field(
        description="Route to: 'log_expert' (for code/log analysis), 'infra_expert' (for container/resource issues), or 'FINISH' (when investigation is complete)"
    )
    reasoning: str = Field(description="Brief explanation (1-2 sentences) of why you chose this route")


# System prompt for Supervisor
SUPERVISOR_SYSTEM_PROMPT = """You are an elite SRE Incident Commander with years of experience triaging production incidents.

**Your Role:**
You are the central coordinator, NOT the investigator. Your job is to read alerts and route tasks to the right specialist.

**Available Specialists:**
1. **log_expert** - Senior Backend Engineer who analyzes application logs and stack traces
   - Use for: 500 errors, code bugs, Python tracebacks, application exceptions
   - Expert at: Reading stack traces, identifying code-level root causes

2. **infra_expert** - DevOps Specialist who diagnoses infrastructure issues
   - Use for: 502/504 errors, container crashes, OOM kills, resource exhaustion
   - Expert at: Container health, memory limits, deployment issues

**Your Routing Strategy:**

For **500 Internal Server Error**:
→ Route to `log_expert` (likely code bug, need to check logs for traceback)

For **502 Bad Gateway**:
→ Route to `infra_expert` first (likely upstream service down)
→ Then `log_expert` if needed (to check for connection errors)

For **504 Gateway Timeout**:
→ Route to `infra_expert` first (likely resource/performance issue)
→ Then `log_expert` if needed (to check for long-running queries)

**When to FINISH:**
- When the root cause is clearly identified (e.g., specific exception, file:line, OOM kill)
- After both specialists have reported their findings AND provided specific conclusions
- When specialists find no critical issues and container/logs are healthy (INCONCLUSIVE is valid)
- When evidence has plateaued (repeated consultations yield no new information)
- IMPORTANT: If both log_expert and infra_expert find "no immediate issues" or "container healthy", you should FINISH with an inconclusive summary rather than continuing to loop

**Recognizing Inconclusive Scenarios:**
- Healthy container + no stack traces + handled exceptions = likely chaos/testing scenario
- Repeated agent calls with no new findings = evidence has plateaued
- Both agents consulted 2+ times with same results = time to FINISH

**CRITICAL RULES:**
1. You NEVER investigate yourself - you only route to specialists
2. You MUST output in the exact JSON format specified (next_worker + reasoning)
3. Consider historical context - if similar incidents were solved a certain way, follow that pattern
4. Avoid calling the same specialist more than 2-3 times unless they're making clear progress
5. Keep your reasoning brief (1-2 sentences max)
6. "Unable to determine root cause" is a VALID investigation outcome when evidence is ambiguous

**Response Format:**
You MUST respond with ONLY the structured format (next_worker and reasoning).
Do NOT provide plain text analysis - leave that to the specialists.
"""


def supervisor_node(state: AlertTeamState) -> dict[str, Any]:
    """
    Supervisor Agent - Routes tasks to specialized workers.

    Uses Pydantic structured outputs to enforce strict routing format.
    The LLM must respond with a SupervisorDecision object.

    Enforces per-agent consultation budgets to prevent diminishing returns.
    Maximum 3 consultations per agent type before forcing FINISH.

    Args:
        state: Current AlertTeamState containing alert_info and messages

    Returns:
        dict: Updated state with next_worker routing decision and reasoning message
    """
    logger.info("=== Supervisor Agent: Analyzing Situation ===")

    # Get context
    alert_info = state.get("alert_info", {})
    historical_context = state.get("historical_context", "")
    messages = state.get("messages", [])
    agent_counts = state.get("agent_consultation_count", {"log_expert": 0, "infra_expert": 0})

    service = alert_info.get("service", "unknown")
    status_code = alert_info.get("status_code", 0)
    error_message = alert_info.get("error_message", "Unknown error")

    # Check agent consultation budgets (max 3 per agent)
    MAX_AGENT_CONSULTATIONS = 3
    log_expert_budget_exceeded = agent_counts.get("log_expert", 0) >= MAX_AGENT_CONSULTATIONS
    infra_expert_budget_exceeded = agent_counts.get("infra_expert", 0) >= MAX_AGENT_CONSULTATIONS

    logger.info(
        f"Agent consultations - log_expert: {agent_counts.get('log_expert', 0)}/{MAX_AGENT_CONSULTATIONS}, "
        f"infra_expert: {agent_counts.get('infra_expert', 0)}/{MAX_AGENT_CONSULTATIONS}"
    )

    # Force FINISH if both agents have exceeded budget
    if log_expert_budget_exceeded and infra_expert_budget_exceeded:
        logger.warning("Both agents have exceeded consultation budget. Forcing FINISH.")

        budget_exhausted_message = HumanMessage(
            content=f"**Supervisor Decision:**\n\n"
            f"Next: FINISH\n"
            f"Reasoning: Investigation budget exhausted (log_expert: {agent_counts['log_expert']}, "
            f"infra_expert: {agent_counts['infra_expert']}). Proceeding to Human-in-the-Loop with "
            f"findings gathered so far.",
            name="supervisor",
        )

        return {"next_worker": "FINISH", "messages": [budget_exhausted_message]}

    # Build context for supervisor
    investigation_summary = (
        "\n\n".join(
            [
                f"[{msg.name}]: {msg.content[:300]}..."
                if hasattr(msg, "name") and len(msg.content) > 300
                else f"[{msg.name}]: {msg.content}"
                if hasattr(msg, "name")
                else str(msg.content)[:300]
                for msg in messages[-3:]  # Last 3 messages for context
            ]
        )
        if messages
        else "No investigation started yet."
    )

    logger.info(f"Current status - Workers consulted: {len([m for m in messages if hasattr(m, 'name')])}")

    # Build budget status string
    budget_status = f"""
**Agent Consultation Budget:**
- log_expert: {agent_counts.get('log_expert', 0)}/{MAX_AGENT_CONSULTATIONS} consultations used{' (BUDGET EXCEEDED)' if log_expert_budget_exceeded else ''}
- infra_expert: {agent_counts.get('infra_expert', 0)}/{MAX_AGENT_CONSULTATIONS} consultations used{' (BUDGET EXCEEDED)' if infra_expert_budget_exceeded else ''}

Note: If an agent's budget is exceeded, you cannot route to it. Consider FINISH if evidence has plateaued.
"""

    # Create prompt
    prompt_content = f"""**Current Alert:**
Service: {service}
Status Code: {status_code}
Error: {error_message}

**Historical Context:**
{historical_context if historical_context else "No similar past incidents found."}

{budget_status}

**Investigation So Far:**
{investigation_summary}

**Decision Needed:**
Based on the alert and investigation so far, which specialist should investigate next?
Or is the investigation complete (FINISH)?

Choose: log_expert, infra_expert, or FINISH
"""

    # Initialize LLM with structured output
    llm = get_llm()
    structured_llm = llm.with_structured_output(SupervisorDecision)  # type: ignore[union-attr]

    # Create messages
    supervisor_messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT), HumanMessage(content=prompt_content)]

    try:
        # Get structured decision from LLM
        decision: Any = structured_llm.invoke(supervisor_messages)

        logger.info(f"Supervisor decision: {decision.next_worker}")
        logger.info(f"Reasoning: {decision.reasoning}")

        # Validate decision against budget constraints
        final_decision = decision.next_worker
        final_reasoning = decision.reasoning

        if decision.next_worker == "log_expert" and log_expert_budget_exceeded:
            logger.warning("LLM tried to route to log_expert but budget exceeded. Forcing FINISH.")
            final_decision = "FINISH"
            final_reasoning = f"{decision.reasoning} However, log_expert budget exhausted. Concluding investigation with current findings."

        elif decision.next_worker == "infra_expert" and infra_expert_budget_exceeded:
            logger.warning("LLM tried to route to infra_expert but budget exceeded. Forcing FINISH.")
            final_decision = "FINISH"
            final_reasoning = f"{decision.reasoning} However, infra_expert budget exhausted. Concluding investigation with current findings."

        # Create reasoning message for history
        reasoning_message = HumanMessage(
            content=f"**Supervisor Routing Decision:**\n\n" f"Next: {final_decision}\n" f"Reasoning: {final_reasoning}",
            name="supervisor",
        )

        return {"next_worker": final_decision, "messages": [reasoning_message]}

    except Exception as e:
        logger.error(f"Supervisor encountered error: {str(e)}")

        # Fallback: route to log_expert as default
        logger.warning("Falling back to default route: log_expert")

        fallback_message = HumanMessage(
            content=f"**Supervisor Error:**\n\nEncountered error during routing: {str(e)}\n"
            f"Defaulting to log_expert for initial investigation.",
            name="supervisor",
        )

        return {"next_worker": "log_expert", "messages": [fallback_message]}
