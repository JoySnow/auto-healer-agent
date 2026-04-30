"""
Docker SDK Tools for Agent Perception

This module provides tools for the AI agents to interact with Docker containers,
fetching logs and checking container health. These tools are the agent's "eyes"
into the infrastructure.

CRITICAL: All tools MUST have comprehensive docstrings with type hints.
The LLM relies 100% on these docstrings to understand how to use the tools.
"""

import logging
from typing import Any

try:
    import docker
    from docker.errors import APIError, DockerException, NotFound

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logging.warning("Docker SDK not installed. Tools will return error messages.")


logger = logging.getLogger(__name__)

# Podman compatibility: If using podman, set DOCKER_HOST to podman socket
# For podman-machine on macOS: export DOCKER_HOST="unix:///Users/<user>/.local/share/containers/podman/machine/podman.sock"
# Or use: podman system connection default
# The docker Python SDK will work with podman's docker-compatible API


def fetch_service_logs(service_name: str, tail_lines: int = 100) -> str:
    """
    Fetch the last N lines of logs from a Docker container.

    Use this tool when you need to examine application logs to identify errors,
    stack traces, or exceptions in a failing service. This is your primary tool
    for investigating 500 errors caused by application code bugs.

    Args:
        service_name (str): The name of the Docker container to fetch logs from.
                          Examples: "order-service", "payment-service", "inventory-service"
        tail_lines (int): Number of log lines to retrieve from the end of the log.
                         Default is 100. Increase if you need more context.

    Returns:
        str: The last N lines of container logs as a string. Logs are in JSON format
             with timestamps, log levels, and messages. Look for:
             - Python tracebacks (ZeroDivisionError, KeyError, etc.)
             - HTTP error codes (500, 502, 504)
             - "error", "exception", "failed" keywords

    Example:
        >>> logs = fetch_service_logs("order-service", tail_lines=50)
        >>> # Logs contain: {"timestamp": "...", "level": "ERROR", "message": "ZeroDivisionError..."}
    """
    if not DOCKER_AVAILABLE:
        return "ERROR: Docker SDK not installed. Cannot fetch logs."

    try:
        # Initialize Docker client
        client = docker.from_env()

        # Get container
        container = client.containers.get(service_name)

        # Fetch logs (tail last N lines)
        logs_bytes = container.logs(tail=tail_lines, timestamps=True)
        logs: str = logs_bytes.decode("utf-8")

        logger.info(f"Successfully fetched {tail_lines} log lines from {service_name}")

        if not logs.strip():
            return f"No logs found for service '{service_name}' (empty log output)"

        return logs

    except NotFound:
        error_msg = f"Container '{service_name}' not found. Check if the service is running."
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

    except APIError as e:
        error_msg = f"Docker API error while fetching logs: {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

    except DockerException as e:
        error_msg = f"Docker daemon error: {str(e)}. Is Docker running?"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

    except Exception as e:
        error_msg = f"Unexpected error fetching logs: {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"


def check_container_health(service_name: str) -> dict[str, Any]:
    """
    Check the health status and resource usage of a Docker container.

    Use this tool when you need to investigate infrastructure-level issues like:
    - Container crashes or restarts
    - Out-of-memory (OOM) kills
    - CPU throttling
    - Container not running (exited state)

    This is your primary tool for investigating 502/504 errors caused by
    infrastructure problems rather than application code bugs.

    Args:
        service_name (str): The name of the Docker container to check.
                          Examples: "order-service", "payment-service", "inventory-service"

    Returns:
        dict: Container health information with the following keys:
            - status (str): Container state ("running", "exited", "restarting", "paused")
            - exit_code (int|None): Exit code if container stopped (0 = normal, non-zero = error)
            - started_at (str): Timestamp when container started
            - finished_at (str|None): Timestamp when container stopped (if applicable)
            - restart_count (int): Number of times container has restarted
            - oom_killed (bool): True if killed due to out-of-memory
            - memory_usage (str): Current memory usage (e.g., "256MB")
            - memory_limit (str): Memory limit (e.g., "512MB")
            - cpu_usage (str): Current CPU usage percentage

    Example:
        >>> health = check_container_health("order-service")
        >>> # Returns: {"status": "exited", "exit_code": 137, "oom_killed": True, ...}
    """
    if not DOCKER_AVAILABLE:
        return {"error": "Docker SDK not installed. Cannot check container health."}

    try:
        # Initialize Docker client
        client = docker.from_env()

        # Get container
        container = client.containers.get(service_name)

        # Get container state
        container.reload()  # Refresh container data
        state = container.attrs["State"]

        # Get restart count
        restart_count = container.attrs["RestartCount"]

        # Basic health info
        health_info = {
            "status": state["Status"],
            "exit_code": state.get("ExitCode"),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "restart_count": restart_count,
            "oom_killed": state.get("OOMKilled", False),
        }

        # Get resource stats if container is running
        if state["Status"] == "running":
            try:
                stats = container.stats(stream=False)

                # Calculate memory usage
                memory_usage = stats["memory_stats"].get("usage", 0)
                memory_limit = stats["memory_stats"].get("limit", 0)

                health_info.update(
                    {
                        "memory_usage": f"{memory_usage / (1024**2):.2f}MB",
                        "memory_limit": f"{memory_limit / (1024**2):.2f}MB",
                        "cpu_usage": "N/A",  # CPU calculation is complex, simplified for MVP
                    }
                )

            except Exception as e:
                logger.warning(f"Could not fetch stats for {service_name}: {e}")
                health_info.update({"memory_usage": "N/A", "memory_limit": "N/A", "cpu_usage": "N/A"})
        else:
            health_info.update({"memory_usage": "N/A (not running)", "memory_limit": "N/A", "cpu_usage": "N/A"})

        logger.info(f"Successfully checked health for {service_name}: status={health_info['status']}")

        return health_info

    except NotFound:
        error_msg = f"Container '{service_name}' not found. Check if the service exists."
        logger.error(error_msg)
        return {"error": error_msg}

    except APIError as e:
        error_msg = f"Docker API error: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

    except DockerException as e:
        error_msg = f"Docker daemon error: {str(e)}. Is Docker running?"
        logger.error(error_msg)
        return {"error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
