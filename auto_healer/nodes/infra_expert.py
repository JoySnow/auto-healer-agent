"""
Infrastructure Expert Agent Node

This agent specializes in diagnosing infrastructure-level issues like container
crashes, OOM kills, resource exhaustion, and network problems. It uses the
check_container_health tool to inspect container state and resource usage.

System Prompt Focus: "You are a DevOps and Kubernetes Specialist."
"""
from typing import Dict, Any
import logging
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from auto_healer.state import AlertTeamState
from auto_healer.tools.docker_tools import check_container_health
from auto_healer.llm_config import get_llm

logger = logging.getLogger(__name__)

# System prompt for Infra Expert
INFRA_EXPERT_SYSTEM_PROMPT = """You are a DevOps and Infrastructure Specialist with deep expertise in containerized applications.

Your specialty is diagnosing infrastructure-level issues that cause 502/504 errors and service failures.

**Your Tools:**
- check_container_health: Inspects container state, resource usage, and health status

**Your Mission:**
When you receive an alert about a service error, you must:

1. **Check container health** using check_container_health
2. **Analyze infrastructure state:**
   - Is the container running or crashed?
   - Any OOM (Out of Memory) kills? (check oom_killed flag)
   - What's the exit code? (137 = OOM, 1 = error, 0 = normal)
   - How many times has it restarted?
   - Memory usage vs. limit - approaching limit?
   - Container status: running, exited, restarting, paused?

3. **Identify infrastructure root cause:**
   - Container crashes or restarts
   - Memory exhaustion (OOM kills)
   - Resource limits hit (CPU throttling, memory limits)
   - Container not running (deployment issues)
   - Network connectivity problems

4. **Provide a clear summary** including:
   - Container health status
   - Resource utilization (memory, CPU if available)
   - Any infrastructure red flags (OOM, crashes, restarts)
   - Root cause explanation (infrastructure perspective)
   - Recommended fix (increase memory, fix deployment, etc.)

**Important:**
- Focus ONLY on infrastructure-level issues (containers, resources, networking)
- If infrastructure looks healthy, say so clearly - the issue may be at the application level
- Always include specific metrics (memory usage, exit codes, restart counts)
- Be concise but thorough

**Response Format:**
Provide your analysis as a structured summary that the Supervisor can use.
"""


def infra_expert_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Infrastructure Expert Agent - Diagnoses container and infrastructure issues.

    This node creates a tool-calling agent that can use check_container_health
    to inspect Docker container state and resource usage.

    Args:
        state: Current AlertTeamState containing alert_info and messages

    Returns:
        dict: Updated state with new messages containing infrastructure analysis
    """
    logger.info("=== Infrastructure Expert Agent Activated ===")

    # Get alert information
    alert_info = state.get("alert_info", {})
    service = alert_info.get("service", "unknown")
    status_code = alert_info.get("status_code", 0)
    historical_context = state.get("historical_context", "")

    logger.info(f"Analyzing infrastructure for service: {service}, status: {status_code}")

    # Initialize LLM with tools
    llm = get_llm()
    tools = [check_container_health]

    # Create ReAct agent with system message
    system_message = f"""{INFRA_EXPERT_SYSTEM_PROMPT}

Alert Information:
Service: {service}
Status Code: {status_code}
Error Message: {alert_info.get("error_message", "Unknown error")}

Historical Context:
{historical_context if historical_context else "No similar past incidents found."}

Task: Check the infrastructure health for this service and identify any resource or container issues.
Use the check_container_health tool to inspect the container state."""

    # Create ReAct agent
    agent = create_react_agent(llm, tools, prompt=system_message)

    try:
        # Execute agent - prepare initial messages
        agent_input = {
            "messages": [
                HumanMessage(content=f"Investigate infrastructure issues for {service} ({status_code} error)")
            ]
        }

        # Execute with recursion limit
        result = agent.invoke(agent_input, {"recursion_limit": 10})

        logger.info("Infrastructure Expert analysis complete")

        # Extract final message
        if result and "messages" in result:
            final_message = result["messages"][-1]
            analysis_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            logger.debug(f"Result: {analysis_content[:200]}...")

            # Create response message
            response_message = AIMessage(
                content=f"**Infrastructure Expert Analysis:**\n\n{analysis_content}",
                name="infra_expert"
            )

            return {"messages": [response_message]}
        else:
            logger.warning("No messages in result")
            return {"messages": [AIMessage(content="**Infrastructure Expert**: No analysis generated", name="infra_expert")]}

    except Exception as e:
        logger.error(f"Infrastructure Expert encountered error: {str(e)}")

        # Return error message for reflection
        error_message = AIMessage(
            content=f"**Infrastructure Expert Error:**\n\nEncountered an error during analysis: {str(e)}\n\nPlease route to another specialist or conclude investigation.",
            name="infra_expert"
        )

        return {"messages": [error_message]}
