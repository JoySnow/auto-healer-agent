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
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

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

    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", LOG_EXPERT_SYSTEM_PROMPT),
        ("human", """Alert Information:
Service: {service}
Status Code: {status_code}
Error Message: {error_message}

Historical Context:
{historical_context}

Task: Analyze the logs for this service and identify the root cause of the error.
Use the fetch_service_logs tool to retrieve recent logs."""),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,  # Limit iterations for safety
        handle_parsing_errors=True  # Enable reflection on parsing errors
    )

    # Prepare input
    agent_input = {
        "service": service,
        "status_code": status_code,
        "error_message": alert_info.get("error_message", "Unknown error"),
        "historical_context": historical_context if historical_context else "No similar past incidents found."
    }

    try:
        # Execute agent
        result = agent_executor.invoke(agent_input)

        logger.info("Log Expert analysis complete")
        logger.debug(f"Result: {result.get('output', '')[:200]}...")

        # Create response message
        response_message = AIMessage(
            content=f"**Log Expert Analysis:**\n\n{result.get('output', 'No analysis available')}",
            name="log_expert"
        )

        return {"messages": [response_message]}

    except Exception as e:
        logger.error(f"Log Expert encountered error: {str(e)}")

        # Return error message for reflection
        error_message = AIMessage(
            content=f"**Log Expert Error:**\n\nEncountered an error during analysis: {str(e)}\n\nPlease route to another specialist or retry.",
            name="log_expert"
        )

        return {"messages": [error_message]}
