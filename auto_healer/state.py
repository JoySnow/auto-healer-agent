"""
LangGraph Global State Definition

This module defines the AlertTeamState TypedDict that is passed between all nodes
in the LangGraph workflow. It tracks the conversation history, alert information,
historical context from ChromaDB, and routing decisions.
"""

import operator
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage


class AlertTeamState(TypedDict):
    """
    Global state passed between all LangGraph nodes.

    Attributes:
        messages: Sequence of messages exchanged between agents.
                  Annotated with operator.add to accumulate messages.
        alert_info: Dictionary containing the incident alert metadata.
                   Example: {"service": "order-service", "status_code": 500, ...}
        historical_context: String containing RAG results from ChromaDB.
                          Populated by the memory_recall node with similar past incidents.
        next_worker: Routing decision from Supervisor.
                    Values: "log_expert", "infra_expert", or "FINISH"
        agent_consultation_count: Dictionary tracking how many times each agent has been consulted.
                                 Keys: "log_expert", "infra_expert"
                                 Values: integer count
                                 Used to enforce per-agent budgets and prevent diminishing returns.
    """

    messages: Annotated[Sequence[BaseMessage], operator.add]
    alert_info: dict[str, Any]
    historical_context: str
    next_worker: str
    agent_consultation_count: dict[str, int]
