"""
LangGraph Orchestration - Multi-Agent Workflow

This module wires together all agent nodes into a state machine graph using LangGraph.
The graph implements the Supervisor-Worker pattern with memory recall/commit and HITL.

Workflow:
Alert → Memory Recall → Supervisor → Workers (Log/Infra) → Supervisor → HITL → Memory Commit
"""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from auto_healer.state import AlertTeamState
from auto_healer.nodes.supervisor import supervisor_node
from auto_healer.nodes.log_expert import log_expert_node
from auto_healer.nodes.infra_expert import infra_expert_node
from auto_healer.nodes.hitl import (
    human_approval_node,
    memory_recall_node,
    memory_commit_node
)

logger = logging.getLogger(__name__)


def route_supervisor_decision(state: AlertTeamState) -> Literal["log_expert", "infra_expert", "human_approval"]:
    """
    Conditional edge function for routing from Supervisor.

    Reads the next_worker field from state and routes accordingly.

    Args:
        state: Current AlertTeamState with next_worker decision

    Returns:
        str: Name of next node to execute
    """
    next_worker = state.get("next_worker", "FINISH")

    logger.info(f"Routing from Supervisor: {next_worker}")

    if next_worker == "FINISH":
        return "human_approval"
    elif next_worker == "log_expert":
        return "log_expert"
    elif next_worker == "infra_expert":
        return "infra_expert"
    else:
        logger.warning(f"Unknown next_worker: {next_worker}, defaulting to human_approval")
        return "human_approval"


def route_after_hitl(state: AlertTeamState) -> Literal["memory_commit", END]:
    """
    Conditional edge function for routing after Human Approval.

    If needs_revision is True, could route back to supervisor for another round.
    For now, we proceed to memory commit or end.

    Args:
        state: Current AlertTeamState with approval decision

    Returns:
        str: Name of next node or END
    """
    needs_revision = state.get("needs_revision", False)

    if needs_revision:
        # Could route back to supervisor here for iteration
        # For MVP, we'll just end - user can re-run
        logger.info("Human requested revisions - ending graph (re-run to retry)")
        return END

    # Always go to memory commit (it will check approval flag internally)
    return "memory_commit"


def create_graph() -> StateGraph:
    """
    Create and compile the LangGraph workflow.

    Returns:
        CompiledGraph: Compiled LangGraph ready for execution

    Graph Structure:
        START
          ↓
        memory_recall (Query ChromaDB)
          ↓
        supervisor (Analyze & Route)
          ↓ ↙ ↘
        log_expert  infra_expert
          ↓           ↓
        supervisor (Re-analyze)
          ↓
        human_approval (HITL)
          ↓
        memory_commit (Save to ChromaDB)
          ↓
        END
    """
    logger.info("Creating LangGraph workflow...")

    # Create graph with state schema
    workflow = StateGraph(AlertTeamState)

    # Add nodes
    workflow.add_node("memory_recall", memory_recall_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("log_expert", log_expert_node)
    workflow.add_node("infra_expert", infra_expert_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("memory_commit", memory_commit_node)

    # Set entry point
    workflow.set_entry_point("memory_recall")

    # Add edges
    # Memory Recall → Supervisor
    workflow.add_edge("memory_recall", "supervisor")

    # Supervisor → Conditional routing to workers or HITL
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor_decision,
        {
            "log_expert": "log_expert",
            "infra_expert": "infra_expert",
            "human_approval": "human_approval"
        }
    )

    # Workers → Back to Supervisor for next decision
    workflow.add_edge("log_expert", "supervisor")
    workflow.add_edge("infra_expert", "supervisor")

    # Human Approval → Conditional routing
    workflow.add_conditional_edges(
        "human_approval",
        route_after_hitl,
        {
            "memory_commit": "memory_commit",
            END: END
        }
    )

    # Memory Commit → END
    workflow.add_edge("memory_commit", END)

    # Compile with checkpointer for state persistence
    # Note: MemorySaver is in-memory only, useful for development
    memory = MemorySaver()

    compiled_graph = workflow.compile(checkpointer=memory)

    logger.info("LangGraph workflow compiled successfully")

    return compiled_graph


def visualize_graph(graph: StateGraph, output_path: str = "graph.png"):
    """
    Generate a visual representation of the graph.

    Args:
        graph: Compiled LangGraph
        output_path: Path to save the visualization

    Note:
        Requires graphviz to be installed:
        brew install graphviz
        pip install pygraphviz
    """
    try:
        from langchain_core.runnables.graph import MermaidDrawMethod

        # Get mermaid diagram
        mermaid_diagram = graph.get_graph().draw_mermaid()

        logger.info("Graph Mermaid diagram:")
        print("\n" + mermaid_diagram + "\n")

        return mermaid_diagram

    except ImportError:
        logger.warning("Could not visualize graph - missing dependencies")
        logger.info("Install with: pip install pygraphviz")
        return None
    except Exception as e:
        logger.error(f"Error visualizing graph: {str(e)}")
        return None
