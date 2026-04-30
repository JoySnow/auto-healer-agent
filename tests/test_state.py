"""
Unit tests for AlertTeamState TypedDict.

These tests validate the structure and behavior of the global state.
"""

from langchain_core.messages import AIMessage, HumanMessage

from auto_healer.state import AlertTeamState


class TestAlertTeamState:
    """Test cases for AlertTeamState TypedDict structure."""

    def test_state_structure(self):
        """Test that state can be created with all required fields."""
        # Create a valid state
        state: AlertTeamState = {
            "messages": [],
            "alert_info": {"service": "order-service", "status_code": 500},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Assertions
        assert isinstance(state["messages"], list)
        assert isinstance(state["alert_info"], dict)
        assert isinstance(state["historical_context"], str)
        assert isinstance(state["next_worker"], str)
        assert isinstance(state["agent_consultation_count"], dict)

    def test_state_with_messages(self):
        """Test state with message history."""
        # Create state with messages
        state: AlertTeamState = {
            "messages": [HumanMessage(content="Investigate 500 error"), AIMessage(content="Analyzing logs...")],
            "alert_info": {"service": "order-service", "status_code": 500},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Assertions
        assert len(state["messages"]) == 2
        assert state["messages"][0].content == "Investigate 500 error"
        assert state["messages"][1].content == "Analyzing logs..."

    def test_state_with_alert_info(self):
        """Test state with comprehensive alert information."""
        # Create state with detailed alert info
        alert_info = {
            "service": "order-service",
            "status_code": 500,
            "error_message": "Internal Server Error",
            "timestamp": "2024-04-30T10:00:00Z",
            "chaos_type": "500_zerodivision",
        }

        state: AlertTeamState = {
            "messages": [],
            "alert_info": alert_info,
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Assertions
        assert state["alert_info"]["service"] == "order-service"
        assert state["alert_info"]["status_code"] == 500
        assert state["alert_info"]["error_message"] == "Internal Server Error"

    def test_state_routing_decisions(self):
        """Test state with different routing decisions."""
        # Test log_expert routing
        state: AlertTeamState = {
            "messages": [],
            "alert_info": {},
            "historical_context": "",
            "next_worker": "log_expert",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }
        assert state["next_worker"] == "log_expert"

        # Test infra_expert routing
        state["next_worker"] = "infra_expert"
        assert state["next_worker"] == "infra_expert"

        # Test FINISH routing
        state["next_worker"] = "FINISH"
        assert state["next_worker"] == "FINISH"

    def test_state_agent_consultation_tracking(self):
        """Test agent consultation count tracking."""
        # Create state and simulate consultations
        state: AlertTeamState = {
            "messages": [],
            "alert_info": {},
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Simulate agent consultations
        state["agent_consultation_count"]["log_expert"] = 2
        state["agent_consultation_count"]["infra_expert"] = 1

        # Assertions
        assert state["agent_consultation_count"]["log_expert"] == 2
        assert state["agent_consultation_count"]["infra_expert"] == 1

    def test_state_with_historical_context(self):
        """Test state with historical context from RAG."""
        # Create state with historical context
        historical_context = """Similar past incidents:
        1) [2024-04-29] order-service 500 - Root cause: ZeroDivisionError
        2) [2024-04-28] order-service 502 - Root cause: Payment timeout
        """

        state: AlertTeamState = {
            "messages": [],
            "alert_info": {},
            "historical_context": historical_context,
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
        }

        # Assertions
        assert "ZeroDivisionError" in state["historical_context"]
        assert "Payment timeout" in state["historical_context"]
