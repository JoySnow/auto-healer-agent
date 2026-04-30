"""
Human-in-the-Loop (HITL) Node

This node pauses the graph execution and asks a human to approve the RCA report
before committing it to long-term memory. This implements the HITL pattern,
ensuring the agent doesn't act autonomously without human oversight.
"""
from typing import Dict, Any
import logging
from langchain_core.messages import HumanMessage

from auto_healer.state import AlertTeamState

logger = logging.getLogger(__name__)


def human_approval_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Human-in-the-Loop Node - Pauses execution for human approval.

    Extracts the RCA report from the conversation history, displays it to
    the user, and asks for approval before proceeding.

    Args:
        state: Current AlertTeamState containing messages with RCA

    Returns:
        dict: Updated state with approval flag and optional feedback message
    """
    logger.info("=== Human-in-the-Loop: Approval Required ===")

    # Extract investigation summary from messages
    messages = state.get("messages", [])

    # Build RCA report from agent messages
    rca_sections = []
    alert_info = state.get("alert_info", {})

    rca_sections.append("=" * 80)
    rca_sections.append("ROOT CAUSE ANALYSIS REPORT")
    rca_sections.append("=" * 80)
    rca_sections.append("")

    # Alert information
    rca_sections.append("**ALERT INFORMATION:**")
    rca_sections.append(f"  Service: {alert_info.get('service', 'unknown')}")
    rca_sections.append(f"  Status Code: {alert_info.get('status_code', 0)}")
    rca_sections.append(f"  Error: {alert_info.get('error_message', 'Unknown')}")
    rca_sections.append(f"  Timestamp: {alert_info.get('timestamp', 'Unknown')}")
    rca_sections.append("")

    # Historical context
    historical_context = state.get("historical_context", "")
    if historical_context:
        rca_sections.append("**HISTORICAL CONTEXT:**")
        rca_sections.append(historical_context)
        rca_sections.append("")

    # Agent findings
    rca_sections.append("**INVESTIGATION FINDINGS:**")
    rca_sections.append("")

    for msg in messages:
        if hasattr(msg, 'name') and msg.name in ['log_expert', 'infra_expert', 'supervisor']:
            rca_sections.append(msg.content)
            rca_sections.append("")

    rca_sections.append("=" * 80)

    # Combine report
    rca_report = "\n".join(rca_sections)

    # Display to user
    print("\n" + rca_report)

    # Ask for approval
    while True:
        try:
            approval_input = input("\n🔍 Approve this RCA and save to memory? (y/n/edit): ").strip().lower()

            if approval_input in ['y', 'yes']:
                logger.info("Human approved RCA report")

                approval_message = HumanMessage(
                    content="**Human Approval:** RCA approved and will be committed to memory.",
                    name="human"
                )

                return {
                    "approved": True,
                    "rca_report": rca_report,
                    "messages": [approval_message]
                }

            elif approval_input in ['n', 'no']:
                logger.info("Human rejected RCA report")

                rejection_message = HumanMessage(
                    content="**Human Rejection:** RCA rejected. Will not be saved to memory.",
                    name="human"
                )

                return {
                    "approved": False,
                    "rca_report": rca_report,
                    "messages": [rejection_message]
                }

            elif approval_input == 'edit':
                print("\nProvide feedback or corrections:")
                feedback = input("> ").strip()

                if feedback:
                    logger.info(f"Human provided feedback: {feedback[:100]}...")

                    feedback_message = HumanMessage(
                        content=f"**Human Feedback:** {feedback}\n\nPlease revise the analysis based on this feedback.",
                        name="human"
                    )

                    return {
                        "approved": False,
                        "needs_revision": True,
                        "rca_report": rca_report,
                        "messages": [feedback_message]
                    }
            else:
                print("Invalid input. Please enter 'y', 'n', or 'edit'.")

        except KeyboardInterrupt:
            logger.warning("HITL interrupted by user")
            print("\n\nInterrupted. Treating as rejection.")

            interruption_message = HumanMessage(
                content="**Human Interruption:** Investigation interrupted. RCA not saved.",
                name="human"
            )

            return {
                "approved": False,
                "rca_report": rca_report,
                "messages": [interruption_message]
            }


def memory_recall_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Memory Recall Node - Queries ChromaDB for similar past incidents.

    This runs at the beginning of the graph to provide historical context
    to the agents.

    Args:
        state: Current AlertTeamState containing alert_info

    Returns:
        dict: Updated state with historical_context from ChromaDB
    """
    from auto_healer.memory import query_past_incidents, initialize_chromadb

    logger.info("=== Memory Recall: Searching for Similar Incidents ===")

    # Initialize ChromaDB if not already done
    initialize_chromadb()

    # Query for similar incidents
    alert_info = state.get("alert_info", {})
    historical_context = query_past_incidents(alert_info, top_k=3)

    if historical_context:
        logger.info(f"Found historical context ({len(historical_context)} chars)")
    else:
        logger.info("No similar past incidents found")
        historical_context = ""

    # Create info message
    if historical_context:
        recall_message = HumanMessage(
            content=f"**Memory Recall:**\n\n{historical_context}",
            name="memory"
        )
        return {
            "historical_context": historical_context,
            "messages": [recall_message]
        }
    else:
        recall_message = HumanMessage(
            content="**Memory Recall:** No similar past incidents found in memory.",
            name="memory"
        )
        return {
            "historical_context": "",
            "messages": [recall_message]
        }


def memory_commit_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Memory Commit Node - Saves approved RCA to ChromaDB.

    Only executes if the human approved the RCA in the HITL node.

    Args:
        state: Current AlertTeamState with approved RCA

    Returns:
        dict: Updated state with commit confirmation message
    """
    from auto_healer.memory import save_incident

    logger.info("=== Memory Commit: Saving RCA to Long-Term Memory ===")

    # Check if approved
    approved = state.get("approved", False)

    if not approved:
        logger.info("RCA not approved, skipping memory commit")

        skip_message = HumanMessage(
            content="**Memory Commit:** Skipped (RCA not approved)",
            name="memory"
        )

        return {"messages": [skip_message]}

    # Get RCA and alert info
    rca_report = state.get("rca_report", "")
    alert_info = state.get("alert_info", {})

    if not rca_report:
        logger.warning("No RCA report to save")

        error_message = HumanMessage(
            content="**Memory Commit:** Error - No RCA report available",
            name="memory"
        )

        return {"messages": [error_message]}

    # Save to ChromaDB
    success = save_incident(rca_report, alert_info)

    if success:
        logger.info("Successfully saved RCA to memory")

        success_message = HumanMessage(
            content="**Memory Commit:** ✅ RCA successfully saved to long-term memory. "
                    "This incident will be recalled for future similar alerts.",
            name="memory"
        )

        return {"messages": [success_message]}
    else:
        logger.error("Failed to save RCA to memory")

        failure_message = HumanMessage(
            content="**Memory Commit:** ❌ Failed to save RCA to memory. Check logs for details.",
            name="memory"
        )

        return {"messages": [failure_message]}
