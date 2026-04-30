"""
Log Expert Agent Node

This agent specializes in analyzing application logs and stack traces to identify
code-level root causes of 500 errors. It uses the fetch_service_logs tool to
retrieve container logs and parse Python tracebacks.

System Prompt Focus: "You are a Senior Backend Software Engineer analyzing logs."
"""
from typing import Dict, Any
import logging
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from auto_healer.state import AlertTeamState
from auto_healer.tools.docker_tools import fetch_service_logs
from auto_healer.llm_config import get_llm

logger = logging.getLogger(__name__)

# System prompt for Log Expert
LOG_EXPERT_SYSTEM_PROMPT = """You are a Senior Backend Software Engineer with expertise in debugging production issues.

Your specialty is analyzing application logs and stack traces to identify the root cause of 500-series errors.

**Your Tools:**
- fetch_service_logs: Retrieves container logs from Docker

**Your Mission:**
When you receive an alert about a service error, you must:

1. **Fetch the logs** for the failing service using fetch_service_logs
2. **Analyze the logs** for:
   - Python tracebacks (look for file paths, line numbers, exception types)
   - Error messages and stack traces
   - Timestamps to identify when the error occurred
   - Any patterns or repeated errors

3. **Identify the root cause:**
   - What exact line of code is failing?
   - What is the exception type? (ZeroDivisionError, KeyError, etc.)
   - What was the input that caused the error?
   - Is this a code bug, data validation issue, or configuration problem?

4. **Provide a clear summary** including:
   - Service name and error type
   - Exact file and line number of the failure
   - Root cause explanation (in plain English)
   - Whether this requires code fix, data fix, or config change

**Important:**
- Focus ONLY on application-level issues (code bugs, exceptions)
- If you don't see relevant errors in the logs, say so clearly
- Always include specific file paths and line numbers from tracebacks
- Be concise but thorough

**Response Format:**
Provide your analysis as a structured summary that the Supervisor can use.
"""


def log_expert_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Log Expert Agent - Analyzes application logs and stack traces.

    This node creates a tool-calling agent that can use fetch_service_logs
    to retrieve and analyze container logs for debugging.

    Args:
        state: Current AlertTeamState containing alert_info and messages

    Returns:
        dict: Updated state with new messages containing log analysis
    """
    logger.info("=== Log Expert Agent Activated ===")

    # Get alert information
    alert_info = state.get("alert_info", {})
    service = alert_info.get("service", "unknown")
    status_code = alert_info.get("status_code", 0)
    historical_context = state.get("historical_context", "")

    logger.info(f"Analyzing logs for service: {service}, status: {status_code}")

    # Initialize LLM with tools
    llm = get_llm()
    tools = [fetch_service_logs]

    # Create ReAct agent with system message
    system_message = f"""{LOG_EXPERT_SYSTEM_PROMPT}

Alert Information:
Service: {service}
Status Code: {status_code}
Error Message: {alert_info.get("error_message", "Unknown error")}

Historical Context:
{historical_context if historical_context else "No similar past incidents found."}

Task: Analyze the logs for this service and identify the root cause of the error.
Use the fetch_service_logs tool to retrieve recent logs."""

    # Create ReAct agent
    agent = create_react_agent(llm, tools, prompt=system_message)

    try:
        # Execute agent - prepare initial messages
        agent_input = {
            "messages": [
                HumanMessage(content=f"Investigate the {status_code} error in {service}")
            ]
        }

        # Execute with recursion limit
        result = agent.invoke(agent_input, {"recursion_limit": 10})

        logger.info("Log Expert analysis complete")

        # Extract final message
        if result and "messages" in result:
            final_message = result["messages"][-1]
            analysis_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            logger.debug(f"Result: {analysis_content[:200]}...")

            # Create response message
            response_message = AIMessage(
                content=f"**Log Expert Analysis:**\n\n{analysis_content}",
                name="log_expert"
            )

            return {"messages": [response_message]}
        else:
            logger.warning("No messages in result")
            return {"messages": [AIMessage(content="**Log Expert**: No analysis generated", name="log_expert")]}

    except Exception as e:
        logger.error(f"Log Expert encountered error: {str(e)}")

        # Return error message for reflection
        error_message = AIMessage(
            content=f"**Log Expert Error:**\n\nEncountered an error during analysis: {str(e)}\n\nPlease route to another specialist or retry.",
            name="log_expert"
        )

        return {"messages": [error_message]}
