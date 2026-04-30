"""
Unit tests for ChromaDB memory functions.

These tests mock ChromaDB to test memory operations without requiring
an actual database instance.
"""

from unittest.mock import Mock, patch

from auto_healer.memory import get_memory_stats, initialize_chromadb, query_past_incidents, save_incident


class TestInitializeChromaDB:
    """Test cases for initialize_chromadb function."""

    @patch("auto_healer.memory.chromadb")
    def test_initialize_success(self, mock_chromadb):
        """Test successful ChromaDB initialization."""
        # Mock ChromaDB client
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 0

        mock_chromadb.Client.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Call function
        result = initialize_chromadb()

        # Assertions
        assert result is True
        mock_chromadb.Client.assert_called_once()
        mock_client.get_or_create_collection.assert_called_once()

    @patch("auto_healer.memory.chromadb")
    def test_initialize_existing_collection(self, mock_chromadb):
        """Test initialization with existing incidents in collection."""
        # Mock ChromaDB client
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 42  # Existing incidents

        mock_chromadb.Client.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Call function
        result = initialize_chromadb()

        # Assertions
        assert result is True
        mock_collection.count.assert_called_once()

    @patch("auto_healer.memory.chromadb")
    def test_initialize_failure(self, mock_chromadb):
        """Test handling of ChromaDB initialization failure."""
        # Mock ChromaDB client to raise exception
        mock_chromadb.Client.side_effect = Exception("Connection failed")

        # Call function
        result = initialize_chromadb()

        # Assertions
        assert result is False


class TestQueryPastIncidents:
    """Test cases for query_past_incidents function."""

    @patch("auto_healer.memory._collection")
    def test_query_with_results(self, mock_collection):
        """Test querying with matching past incidents."""
        # Mock query results
        mock_collection.query.return_value = {
            "documents": [
                [
                    "Root cause: ZeroDivisionError in order calculation at line 42",
                    "Root cause: Payment gateway timeout after 30 seconds",
                ]
            ],
            "metadatas": [
                [
                    {"service": "order-service", "status_code": 500, "timestamp": "2024-04-30T10:00:00Z"},
                    {"service": "order-service", "status_code": 502, "timestamp": "2024-04-29T15:00:00Z"},
                ]
            ],
        }
        mock_collection.count.return_value = 10

        # Call function
        alert_info = {"service": "order-service", "status_code": 500, "error_message": "Internal Server Error"}
        result = query_past_incidents(alert_info, top_k=2)

        # Assertions
        assert "Similar past incidents:" in result
        assert "ZeroDivisionError" in result
        assert "Payment gateway timeout" in result
        assert "2024-04-30" in result
        mock_collection.query.assert_called_once()

    @patch("auto_healer.memory._collection")
    def test_query_no_results(self, mock_collection):
        """Test querying with no matching incidents."""
        # Mock empty query results
        mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]]}
        mock_collection.count.return_value = 0

        # Call function
        alert_info = {"service": "order-service", "status_code": 500}
        result = query_past_incidents(alert_info)

        # Assertions
        assert result == ""  # Empty string when no results

    @patch("auto_healer.memory._collection", None)
    def test_query_not_initialized(self):
        """Test querying when ChromaDB not initialized."""
        # Call function with None collection
        alert_info = {"service": "order-service", "status_code": 500}
        result = query_past_incidents(alert_info)

        # Assertions
        assert result == ""

    @patch("auto_healer.memory._collection")
    def test_query_respects_top_k(self, mock_collection):
        """Test that top_k parameter limits results."""
        # Mock collection count
        mock_collection.count.return_value = 10

        # Mock query results
        mock_collection.query.return_value = {
            "documents": [["incident1", "incident2", "incident3"]],
            "metadatas": [
                [
                    {"service": "order", "status_code": 500, "timestamp": "2024-01-01"},
                    {"service": "order", "status_code": 500, "timestamp": "2024-01-02"},
                    {"service": "order", "status_code": 500, "timestamp": "2024-01-03"},
                ]
            ],
        }

        # Call function with top_k=3
        alert_info = {"service": "order-service", "status_code": 500}
        query_past_incidents(alert_info, top_k=3)

        # Assertions
        mock_collection.query.assert_called_once()
        call_args = mock_collection.query.call_args
        assert call_args[1]["n_results"] == 3


class TestSaveIncident:
    """Test cases for save_incident function."""

    @patch("auto_healer.memory._collection")
    def test_save_success(self, mock_collection):
        """Test successfully saving an incident."""
        # Mock collection
        mock_collection.add = Mock()

        # Call function
        rca_report = "Root cause: ZeroDivisionError at line 42"
        alert_info = {
            "service": "order-service",
            "status_code": 500,
            "timestamp": "2024-04-30T10:00:00Z",
            "chaos_type": "500_zerodivision",
        }

        result = save_incident(rca_report, alert_info)

        # Assertions
        assert result is True
        mock_collection.add.assert_called_once()

        # Verify call args
        call_args = mock_collection.add.call_args
        assert call_args[1]["documents"] == [rca_report]
        assert call_args[1]["metadatas"][0]["service"] == "order-service"
        assert call_args[1]["metadatas"][0]["status_code"] == 500

    @patch("auto_healer.memory._collection", None)
    def test_save_not_initialized(self):
        """Test saving when ChromaDB not initialized."""
        # Call function with None collection
        rca_report = "Root cause: Test error"
        alert_info = {"service": "order-service", "status_code": 500}

        result = save_incident(rca_report, alert_info)

        # Assertions
        assert result is False

    @patch("auto_healer.memory._collection")
    def test_save_failure(self, mock_collection):
        """Test handling of save failure."""
        # Mock collection to raise exception
        mock_collection.add.side_effect = Exception("Database error")

        # Call function
        rca_report = "Root cause: Test error"
        alert_info = {"service": "order-service", "status_code": 500}

        result = save_incident(rca_report, alert_info)

        # Assertions
        assert result is False


class TestGetMemoryStats:
    """Test cases for get_memory_stats function."""

    @patch("auto_healer.memory._collection")
    def test_get_stats_success(self, mock_collection):
        """Test successfully getting memory stats."""
        # Mock collection
        mock_collection.count.return_value = 42

        # Call function
        result = get_memory_stats()

        # Assertions
        assert result["total_incidents"] == 42
        assert result["collection_name"] == "incident_history"
        assert result["persist_directory"] == ".chromadb"

    @patch("auto_healer.memory._collection", None)
    def test_get_stats_not_initialized(self):
        """Test getting stats when ChromaDB not initialized."""
        # Call function with None collection
        result = get_memory_stats()

        # Assertions
        assert "error" in result
        assert "not initialized" in result["error"].lower()
