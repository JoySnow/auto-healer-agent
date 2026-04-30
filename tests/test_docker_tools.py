"""
Unit tests for Docker SDK tools.

These tests mock the Docker SDK to test the tool functions without requiring
actual Docker containers to be running.
"""

from unittest.mock import Mock, patch

from auto_healer.tools.docker_tools import check_container_health, fetch_service_logs


class TestFetchServiceLogs:
    """Test cases for fetch_service_logs function."""

    @patch("auto_healer.tools.docker_tools.docker")
    def test_fetch_logs_success(self, mock_docker):
        """Test successfully fetching logs from a running container."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.logs.return_value = (
            b"2024-04-30T10:00:00Z ERROR: Test error\n2024-04-30T10:00:01Z INFO: Processing order"
        )

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function
        result = fetch_service_logs("order-service", tail_lines=50)

        # Assertions
        assert "ERROR: Test error" in result
        assert "INFO: Processing order" in result
        mock_container.logs.assert_called_once_with(tail=50, timestamps=True)

    @patch("auto_healer.tools.docker_tools.docker")
    def test_fetch_logs_container_not_found(self, mock_docker):
        """Test handling of non-existent container."""
        # Mock Docker client to raise NotFound
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors.NotFound = Exception

        mock_client.containers.get.side_effect = Exception("Container not found")

        # Call function
        result = fetch_service_logs("nonexistent-service")

        # Assertions
        assert "ERROR" in result
        assert "not found" in result.lower()

    @patch("auto_healer.tools.docker_tools.docker")
    def test_fetch_logs_empty_output(self, mock_docker):
        """Test handling of container with no logs."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.logs.return_value = b""  # Empty logs

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function
        result = fetch_service_logs("order-service")

        # Assertions
        assert "No logs found" in result or "empty" in result.lower()

    @patch("auto_healer.tools.docker_tools.docker")
    def test_fetch_logs_default_tail(self, mock_docker):
        """Test that default tail_lines parameter is 100."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.logs.return_value = b"Test log"

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function without tail_lines
        fetch_service_logs("order-service")

        # Assertions
        mock_container.logs.assert_called_once_with(tail=100, timestamps=True)


class TestCheckContainerHealth:
    """Test cases for check_container_health function."""

    @patch("auto_healer.tools.docker_tools.docker")
    def test_check_health_running_container(self, mock_docker):
        """Test checking health of a running container."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()

        # Mock container attributes
        mock_container.attrs = {
            "State": {
                "Status": "running",
                "StartedAt": "2024-04-30T10:00:00Z",
                "ExitCode": None,
                "FinishedAt": None,
                "OOMKilled": False,
            },
            "RestartCount": 0,
        }

        # Mock container stats
        mock_container.stats.return_value = {
            "memory_stats": {
                "usage": 256 * 1024 * 1024,  # 256MB
                "limit": 512 * 1024 * 1024,  # 512MB
            }
        }

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function
        result = check_container_health("order-service")

        # Assertions
        assert result["status"] == "running"
        assert result["restart_count"] == 0
        assert result["oom_killed"] is False
        assert "256" in result["memory_usage"]  # Should show 256MB
        mock_container.reload.assert_called_once()

    @patch("auto_healer.tools.docker_tools.docker")
    def test_check_health_exited_container(self, mock_docker):
        """Test checking health of an exited container."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()

        # Mock container attributes for exited state
        mock_container.attrs = {
            "State": {
                "Status": "exited",
                "StartedAt": "2024-04-30T10:00:00Z",
                "ExitCode": 137,  # OOM kill
                "FinishedAt": "2024-04-30T10:05:00Z",
                "OOMKilled": True,
            },
            "RestartCount": 5,
        }

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function
        result = check_container_health("order-service")

        # Assertions
        assert result["status"] == "exited"
        assert result["exit_code"] == 137
        assert result["oom_killed"] is True
        assert result["restart_count"] == 5

    @patch("auto_healer.tools.docker_tools.docker")
    def test_check_health_container_not_found(self, mock_docker):
        """Test handling of non-existent container."""
        # Mock Docker client to raise NotFound
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors.NotFound = Exception

        mock_client.containers.get.side_effect = Exception("Container not found")

        # Call function
        result = check_container_health("nonexistent-service")

        # Assertions
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("auto_healer.tools.docker_tools.docker")
    def test_check_health_stats_unavailable(self, mock_docker):
        """Test handling when stats API fails."""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()

        # Mock container attributes
        mock_container.attrs = {
            "State": {
                "Status": "running",
                "StartedAt": "2024-04-30T10:00:00Z",
                "ExitCode": None,
                "FinishedAt": None,
                "OOMKilled": False,
            },
            "RestartCount": 0,
        }

        # Mock stats to raise exception
        mock_container.stats.side_effect = Exception("Stats unavailable")

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Call function
        result = check_container_health("order-service")

        # Assertions
        assert result["status"] == "running"
        assert result["memory_usage"] == "N/A"  # Should fallback gracefully
