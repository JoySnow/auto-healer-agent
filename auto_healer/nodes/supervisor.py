"""
Supervisor Agent Node

The Supervisor is the central router that analyzes alerts and delegates tasks
to specialized worker agents (Log Expert, Infra Expert). It NEVER attempts to
fix issues itself - only routes to the appropriate specialist.

CRITICAL: Uses Pydantic Structured Outputs to enforce strict routing format.
This prevents the local LLM from hallucinating or outputting plain text.
"""
from typing import Dict, Any, Literal
import logging
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from auto_healer.state import AlertTeamState
from auto_healer.llm_config import get_llm

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
    reasoning: str = Field(
        description="Brief explanation (1-2 sentences) of why you chose this route"
    )


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
- After both specialists have reported their findings
- When you have enough information for a complete RCA
- When the root cause is clearly identified

**CRITICAL RULES:**
1. You NEVER investigate yourself - you only route to specialists
2. You MUST output in the exact JSON format specified (next_worker + reasoning)
3. Consider historical context - if similar incidents were solved a certain way, follow that pattern
4. You can call the same specialist multiple times if needed
5. Keep your reasoning brief (1-2 sentences max)

**Response Format:**
You MUST respond with ONLY the structured format (next_worker and reasoning).
Do NOT provide plain text analysis - leave that to the specialists.
"""


def supervisor_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Supervisor Agent - Routes tasks to specialized workers.

    Uses Pydantic structured outputs to enforce strict routing format.
    The LLM must respond with a SupervisorDecision object.

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

    service = alert_info.get("service", "unknown")
    status_code = alert_info.get("status_code", 0)
    error_message = alert_info.get("error_message", "Unknown error")

    # Build context for supervisor
    investigation_summary = "\n\n".join([
        f"[{msg.name}]: {msg.content[:300]}..." if hasattr(msg, 'name') and len(msg.content) > 300
        else f"[{msg.name}]: {msg.content}" if hasattr(msg, 'name')
        else str(msg.content)[:300]
        for msg in messages[-3:]  # Last 3 messages for context
    ]) if messages else "No investigation started yet."

    logger.info(f"Current status - Workers consulted: {len([m for m in messages if hasattr(m, 'name')])}")

    # Create prompt
    prompt_content = f"""**Current Alert:**
Service: {service}
Status Code: {status_code}
Error: {error_message}

**Historical Context:**
{historical_context if historical_context else "No similar past incidents found."}

**Investigation So Far:**
{investigation_summary}

**Decision Needed:**
Based on the alert and investigation so far, which specialist should investigate next?
Or is the investigation complete (FINISH)?

Choose: log_expert, infra_expert, or FINISH
"""

    # Initialize LLM with structured output
    llm = get_llm()
    structured_llm = llm.with_structured_output(SupervisorDecision)

    # Create messages
    supervisor_messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt_content)
    ]

    try:
        # Get structured decision from LLM
        decision: SupervisorDecision = structured_llm.invoke(supervisor_messages)

        logger.info(f"Supervisor decision: {decision.next_worker}")
        logger.info(f"Reasoning: {decision.reasoning}")

        # Create reasoning message for history
        reasoning_message = HumanMessage(
            content=f"**Supervisor Routing Decision:**\n\n"
                    f"Next: {decision.next_worker}\n"
                    f"Reasoning: {decision.reasoning}",
            name="supervisor"
        )

        return {
            "next_worker": decision.next_worker,
            "messages": [reasoning_message]
        }

    except Exception as e:
        logger.error(f"Supervisor encountered error: {str(e)}")

        # Fallback: route to log_expert as default
        logger.warning("Falling back to default route: log_expert")

        fallback_message = HumanMessage(
            content=f"**Supervisor Error:**\n\nEncountered error during routing: {str(e)}\n"
                    f"Defaulting to log_expert for initial investigation.",
            name="supervisor"
        )

        return {
            "next_worker": "log_expert",
            "messages": [fallback_message]
        }
