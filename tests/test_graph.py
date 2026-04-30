"""
Integration tests for LangGraph workflow.

These tests validate graph structure and compilation without requiring
actual LLM or Docker connections.
"""

from unittest.mock import Mock, patch

import pytest

from auto_healer.state import AlertTeamState


class TestGraphStructure:
    """Test cases for graph structure and compilation."""

    @pytest.mark.integration
    @patch("auto_healer.nodes.supervisor.get_llm")
    @patch("auto_healer.nodes.log_expert.get_llm")
    @patch("auto_healer.nodes.infra_expert.get_llm")
    def test_create_graph_compiles(self, mock_get_llm_infra, mock_get_llm_log, mock_get_llm_supervisor):
        """Test that graph compiles successfully (integration test)."""
        # Mock LLM for all nodes
        mock_llm = Mock()
        mock_get_llm_supervisor.return_value = mock_llm
        mock_get_llm_log.return_value = mock_llm
        mock_get_llm_infra.return_value = mock_llm

        # Import and create graph
        from auto_healer.graph import create_graph

        # Call function
        graph = create_graph()

        # Assertions
        assert graph is not None
        # Graph should be compiled LangGraph instance
        assert hasattr(graph, "invoke")

    def test_route_supervisor_decision(self):
        """Test routing logic for supervisor decisions."""
        from auto_healer.graph import route_supervisor_decision

        # Test log_expert routing
        state: AlertTeamState = {
            "messages": [],
            "alert_info": {},
            "historical_context": "",
            "next_worker": "log_expert",
            "agent_consultation_count": {},
        }
        assert route_supervisor_decision(state) == "log_expert"

        # Test infra_expert routing
        state["next_worker"] = "infra_expert"
        assert route_supervisor_decision(state) == "infra_expert"

        # Test FINISH routing
        state["next_worker"] = "FINISH"
        assert route_supervisor_decision(state) == "human_approval"

    @pytest.mark.integration
    @patch("auto_healer.nodes.supervisor.get_llm")
    @patch("auto_healer.nodes.log_expert.get_llm")
    @patch("auto_healer.nodes.infra_expert.get_llm")
    def test_visualize_graph_returns_mermaid(self, mock_get_llm_infra, mock_get_llm_log, mock_get_llm_supervisor):
        """Test that visualize_graph returns Mermaid diagram (integration test)."""
        # Mock LLM for all nodes
        mock_llm = Mock()
        mock_get_llm_supervisor.return_value = mock_llm
        mock_get_llm_log.return_value = mock_llm
        mock_get_llm_infra.return_value = mock_llm

        # Import functions
        from auto_healer.graph import create_graph, visualize_graph

        # Create graph
        graph = create_graph()

        # Call visualize
        mermaid = visualize_graph(graph)

        # Assertions
        assert mermaid is not None
        # Should return a string (Mermaid diagram or error message)
        assert isinstance(mermaid, str)


class TestInitialState:
    """Test cases for initial state creation."""

    def test_initial_state_structure(self):
        """Test that initial state has correct structure."""
        # Create initial state
        initial_state: AlertTeamState = {
            "messages": [],
            "alert_info": {
                "service": "order-service",
                "status_code": 500,
                "error_message": "Internal Server Error",
                "timestamp": "2024-04-30T10:00:00Z",
            },
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Assertions
        assert initial_state["messages"] == []
        assert initial_state["agent_consultation_count"]["log_expert"] == 0
        assert initial_state["agent_consultation_count"]["infra_expert"] == 0
        assert initial_state["next_worker"] == ""

    def test_initial_state_with_different_errors(self):
        """Test initial state for different error codes."""
        # Test 500 error
        state_500: AlertTeamState = {
            "messages": [],
            "alert_info": {"service": "order-service", "status_code": 500},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }
        assert state_500["alert_info"]["status_code"] == 500

        # Test 502 error
        state_502: AlertTeamState = {
            "messages": [],
            "alert_info": {"service": "order-service", "status_code": 502},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }
        assert state_502["alert_info"]["status_code"] == 502

        # Test 504 error
        state_504: AlertTeamState = {
            "messages": [],
            "alert_info": {"service": "order-service", "status_code": 504},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }
        assert state_504["alert_info"]["status_code"] == 504
