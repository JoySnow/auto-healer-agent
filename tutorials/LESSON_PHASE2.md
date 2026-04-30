# Phase 2 Lesson: Perception, Tools & Memory

## 2.1 Overview

**What You'll Build**: Docker SDK tools for log fetching and health checks, ChromaDB memory system for learning from past incidents, and local LLM configuration with Ollama.

**Why It Matters**:
- Agents are blind without perception tools
- Memory enables learning from incidents without retraining
- Proper LLM configuration prevents silent failures (context window!)

**Learning Objectives**:
- Design tool interfaces that LLMs can actually use
- Implement RAG (Retrieval Augmented Generation) for long-term memory
- Configure local LLMs with proper context windows
- Handle errors with reflection (agents can self-correct)

**Time to Complete**: 3-4 hours

---

## 2.2 Prerequisites

Before starting this lesson, you should have:

- ✅ **Phase 1 completed** (services running with chaos injection)
- **Ollama installed** with qwen2.5:14b model
- **ChromaDB knowledge** (or willingness to learn vector databases)
- Understanding of function signatures and docstrings
- Basic knowledge of Docker SDK (or willingness to learn)

**Check your environment**:
```bash
# Verify services from Phase 1 are running
docker ps  # Should show 3 containers

# Verify Ollama is installed
ollama list
# Should show: qwen2.5:14b

# If model not installed:
ollama pull qwen2.5:14b  # Downloads 9GB model
```

---

## 2.3 Core Concepts

### Concept 1: Tool Design for LLMs - Docstrings Are Critical!

**The #1 Mistake**: Vague tool docstrings

```python
# ❌ ANTI-PATTERN: LLM doesn't know when/how to use this
def get_logs(service):
    """Get logs from a service."""
    return docker_client.logs(service)
```

**Why This Fails**:
- LLM doesn't know WHEN to use this (500 errors? 502 errors? always?)
- LLM doesn't know parameter format ("order-service" vs "order" vs "order_service")
- LLM doesn't know what the output looks like
- No examples of usage

**LLM's Perspective**:
> "I see a tool called 'get_logs'. The docstring says 'Get logs from a service'. But... when should I call it? What service name format? How many lines? What if the container doesn't exist?"

**Result**: LLM either doesn't use the tool OR uses it incorrectly.

---

**✅ BETTER: Comprehensive Docstring**

```python
def fetch_service_logs(service_name: str, tail_lines: int = 100) -> str:
    """
    Fetch recent logs from a Docker container.

    **Use this tool when:**
    - Investigating application errors (500 Internal Server Error)
    - Looking for Python tracebacks and stack traces
    - Checking for error messages in application logs
    - Finding timestamps of failures

    **Do NOT use this tool for:**
    - Infrastructure health (use check_container_health instead)
    - Network issues (use check_container_health)

    Args:
        service_name (str): Exact name of the Docker container.
            Examples: "order-service", "payment-service", "inventory-service"
            Must match container name from docker-compose.yml
        tail_lines (int): Number of recent log lines to retrieve.
            Default: 100 (sufficient for most error investigations)
            Range: 10-500 (more lines = more LLM tokens)

    Returns:
        str: Container logs with timestamps, one line per log entry.
             Format: "2024-04-30T12:00:00Z [INFO] message here"
             Returns error message if container not found.

    Example:
        # Fetch last 100 lines from order service
        logs = fetch_service_logs("order-service", tail_lines=100)

        # Fetch last 50 lines for quick check
        logs = fetch_service_logs("payment-service", tail_lines=50)

    Error Handling:
        - Container not found → Returns helpful error with available containers
        - Docker daemon down → Returns error with troubleshooting hint
    """
    # Implementation...
```

**Why This Works**:
1. **When to use**: Explicit scenarios (500 errors, tracebacks)
2. **Parameters**: Exact format with examples
3. **Output format**: LLM knows what to expect
4. **Examples**: Shows correct usage
5. **Error handling**: LLM knows errors are strings (can reflect and retry)

**Impact**: LLM uses tools correctly 95%+ of the time (vs ~50% with vague docstrings)

---

### Concept 2: Error Handling with Reflection

**Anti-Pattern: Crash on Errors**

```python
# ❌ BAD: Raises exception → Agent execution stops
def check_container_health(service_name: str) -> dict:
    container = docker_client.containers.get(service_name)  # May raise NotFound
    return {"status": container.status}
```

**What Happens**:
1. Agent calls `check_container_health("wrong-name")`
2. `docker.errors.NotFound` exception raised
3. Agent execution crashes
4. No chance to retry with correct name

**Result**: Agent fails, no self-correction possible.

---

**✅ BETTER: Return Error as String**

```python
def check_container_health(service_name: str) -> str:
    """
    Check health status of a Docker container.

    Returns:
        str: Human-readable health report OR error message
    """
    try:
        client = docker.from_env()
        container = client.containers.get(service_name)

        return f"""Container Health Report:
Name: {container.name}
Status: {container.status}
Running: {container.status == 'running'}
"""

    except docker.errors.NotFound:
        # ✅ Return error as string (LLM can read and reflect)
        available = [c.name for c in client.containers.list()]
        return f"""Error: Container '{service_name}' not found.

Available containers:
{', '.join(available)}

Tip: Use exact container name from the list above.
Example: check_container_health("order-service")
"""

    except docker.errors.APIError as e:
        return f"""Error: Docker API error: {str(e)}

Tip: Check if Docker daemon is running with 'docker ps'
"""
```

**What Happens Now**:
1. Agent calls `check_container_health("wrong-name")`
2. Function returns error string (not exception)
3. LLM reads: "Error: Container 'wrong-name' not found. Available: order-service, payment-service"
4. LLM thinks: "Oh, I used wrong name. Let me try 'order-service'"
5. Agent self-corrects: `check_container_health("order-service")`
6. Success!

**Result**: Agent recovers from errors autonomously.

---

### Concept 3: RAG Memory Architecture

**The Problem**: LLMs forget everything after conversation ends

```
Session 1: Agent investigates 500 error → Finds ZeroDivisionError → RCA complete
Session 2: Same 500 error → Agent starts from scratch (no memory!)
```

**Traditional Solution**: Fine-tune model on incident data
- **Problems**: Expensive, slow, requires retraining, can't update quickly

---

**Better Solution: RAG (Retrieval Augmented Generation)**

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG MEMORY WORKFLOW                       │
└─────────────────────────────────────────────────────────────┘

New Alert
    ↓
[1] Query ChromaDB ────→ Semantic search for similar incidents
    ↓                    (vector similarity)
[2] Retrieve Context ──→ Past RCA reports with same error pattern
    ↓
[3] Enrich Prompt ────→ "Historical Context: Last time this 500 error
    ↓                    occurred, root cause was ZeroDivisionError at
    │                    /app/app.py:84. Resolution: Fixed division logic."
    ↓
[4] Agent Uses Context → Faster investigation (knows what to look for)
    ↓
[5] Human Approves RCA → Only store if approved!
    ↓
[6] Store in ChromaDB ─→ Future incidents benefit from this knowledge
```

**Why RAG?**
- ✅ No retraining needed
- ✅ Update memory instantly (just add to ChromaDB)
- ✅ Semantic search (finds similar incidents, not just exact matches)
- ✅ Human-in-the-loop prevents learning from bad RCAs

**Real-World Example**:

```python
# First incident (empty memory)
alert = {"service": "order", "status_code": 500, "error": "Internal Server Error"}
context = query_memory(alert)  # Returns: "No similar past incidents found."
# Agent investigates from scratch → Takes 60 seconds

# Second incident (memory populated)
alert = {"service": "order", "status_code": 500, "error": "Internal Server Error"}
context = query_memory(alert)
# Returns: "Similar incident on 2024-04-29: 500 error in order-service.
#           Root cause: ZeroDivisionError at /app/app.py:84.
#           Resolution: Fixed division by zero in discount calculation."
# Agent knows where to look → Takes 20 seconds
```

---

### Concept 4: Context Window Management - Silent Failure Trap!

**The Critical Bug**: Default context window too small

```python
# ❌ CATASTROPHIC BUG (was in our project until Phase 4!)
llm = ChatOllama(model="qwen2.5:14b")  # Default: num_ctx=2048 tokens

# Fetch 100 lines of logs (~5000 tokens)
logs = fetch_service_logs("order-service", tail_lines=100)

# LLM receives TRUNCATED logs (only first ~2048 tokens)
# Stack trace at line 95 is MISSING!
# LLM says: "I don't see any errors in the logs"
# But the error WAS THERE - just truncated!
```

**Real Project Impact**:
- Agent missed ZeroDivisionError in logs
- Took 2 hours to debug why agent couldn't find obvious error
- Root cause: Default `num_ctx=2048` silently truncated logs

**Why So Dangerous**:
- ❌ No error message (silent truncation)
- ❌ LLM responds normally (doesn't know context was cut)
- ❌ Agent appears to work (just wrong conclusions)

---

**✅ SOLUTION: Explicit Context Window**

```python
# ✅ CORRECT: Explicitly set context window
llm = ChatOllama(
    model="qwen2.5:14b",
    num_ctx=16384,  # 16K tokens minimum!
    temperature=0.0  # Deterministic for debugging
)

# Now 100 lines of logs (~5000 tokens) fit comfortably
# LLM sees full stack trace
# Agent finds error correctly
```

**Token Math**:
- 1 log line ≈ 50 tokens (with timestamp + JSON structure)
- 100 lines ≈ 5,000 tokens
- Default 2048 → Only see ~40 lines (stack trace missed!)
- 16384 → See all 100 lines (3× headroom for safety)

**Rule of Thumb**:
- **Minimum**: 16384 (16K) for log analysis
- **Better**: 32768 (32K) for complex investigations
- **Overkill**: 65536 (64K) - slower inference, usually unnecessary

---

## 2.4 Step-by-Step Implementation

### Step 1: Define Global State (15 minutes)

**Create File**: `auto_healer/state.py`

```python
"""
Global State Definition for LangGraph

This TypedDict defines the shared state passed between all nodes in the graph.
LangGraph automatically merges node outputs into this state.
"""
from typing import TypedDict, Annotated, Sequence, Dict
from langchain_core.messages import BaseMessage
import operator


class AlertTeamState(TypedDict):
    """
    Shared state for the multi-agent troubleshooting team.

    This state flows through all graph nodes. Each node reads relevant fields
    and returns updates to merge back into the state.

    Key Design Decisions:
    - messages: Annotated with operator.add → LangGraph appends new messages
    - agent_consultation_count: Dict tracking per-agent calls (budget enforcement)
    - All other fields: Last write wins (no accumulation)
    """

    # ========================================================================
    # MESSAGE HISTORY
    # ========================================================================
    messages: Annotated[Sequence[BaseMessage], operator.add]
    """
    Conversation history between agents.

    Why Annotated with operator.add?
    - LangGraph automatically APPENDS new messages (doesn't replace)
    - Each node returns {"messages": [new_message]} → auto-appended to history
    - Enables multi-turn agent collaboration

    Message Types:
    - HumanMessage: User input or supervisor instructions
    - AIMessage: Agent responses (with name="log_expert", "infra_expert", etc.)
    - SystemMessage: System prompts and configuration
    """

    # ========================================================================
    # ALERT METADATA
    # ========================================================================
    alert_info: dict
    """
    Original alert that triggered investigation.

    Structure:
    {
        "service": "order-service",
        "status_code": 500,
        "error_message": "Internal Server Error",
        "timestamp": "2024-04-30T12:00:00Z"
    }

    Used by: All agents (context for investigation)
    """

    # ========================================================================
    # RAG MEMORY CONTEXT
    # ========================================================================
    historical_context: str
    """
    Historical context from similar past incidents (ChromaDB query result).

    Populated by: memory_recall_node (entry point)
    Used by: All agents (enriches investigation with past learnings)

    Example:
    "Similar incident on 2024-04-29: 500 error in order-service.
     Root cause: ZeroDivisionError at /app/app.py:84"
    """

    # ========================================================================
    # SUPERVISOR ROUTING
    # ========================================================================
    next_worker: str
    """
    Supervisor's routing decision.

    Values:
    - "log_expert": Route to log analysis agent
    - "infra_expert": Route to infrastructure agent
    - "FINISH": Investigation complete, proceed to HITL

    Set by: supervisor_node
    Used by: Conditional routing edge
    """

    # ========================================================================
    # BUDGET TRACKING (Prevents Infinite Loops)
    # ========================================================================
    agent_consultation_count: Dict[str, int]
    """
    Per-agent consultation counter.

    Structure:
    {
        "log_expert": 2,     # Called 2 times
        "infra_expert": 1    # Called 1 time
    }

    Why track this?
    - Prevents infinite supervisor loops on ambiguous evidence
    - Enforces MAX_CONSULTATIONS limit (default: 3 per agent)
    - Supervisor forced to FINISH when both budgets exhausted

    Updated by: Each agent node (increments own counter)
    Checked by: supervisor_node (enforces limits)
    """

    # ========================================================================
    # HUMAN-IN-THE-LOOP
    # ========================================================================
    approved: bool
    """
    Whether human approved the RCA report.

    Set by: human_approval_node
    Used by: memory_commit_node (only save if approved)
    """

    rca_report: str
    """
    Final root cause analysis report.

    Set by: human_approval_node (compiled from agent messages)
    Used by: memory_commit_node (saves to ChromaDB)
    """


# ============================================================================
# TYPE CHECKING UTILITIES
# ============================================================================

def validate_state(state: AlertTeamState) -> bool:
    """
    Validate state structure (useful for debugging).

    Returns:
        bool: True if state is valid

    Raises:
        KeyError: If required fields missing
        TypeError: If field types incorrect
    """
    required_fields = ["messages", "alert_info", "historical_context", "next_worker"]

    for field in required_fields:
        if field not in state:
            raise KeyError(f"Missing required field: {field}")

    # Validate types
    if not isinstance(state["messages"], (list, tuple)):
        raise TypeError("messages must be a sequence")

    if not isinstance(state["alert_info"], dict):
        raise TypeError("alert_info must be a dict")

    return True
```

**Key Design Decisions Explained**:

1. **Why TypedDict?**
   - Type safety (IDE autocomplete, mypy checking)
   - LangGraph expects TypedDict for state
   - Self-documenting (fields defined in one place)

2. **Why Annotated with operator.add for messages?**
   ```python
   # Without operator.add (last write wins):
   node1 returns: {"messages": [msg1]}  # State has [msg1]
   node2 returns: {"messages": [msg2]}  # State has [msg2] (msg1 lost!)

   # With operator.add (accumulation):
   node1 returns: {"messages": [msg1]}  # State has [msg1]
   node2 returns: {"messages": [msg2]}  # State has [msg1, msg2] (appended!)
   ```

3. **Why separate agent_consultation_count dict?**
   - Single counter → Can't tell which agent is overused
   - Per-agent tracking → Enforce budget per specialist
   - Enables "consult log_expert max 3 times, infra_expert max 3 times"

---

### Step 2: Build Docker Tools (60 minutes)

**Create File**: `auto_healer/tools/docker_tools.py`

```python
"""
Docker SDK Tools for Agent Perception

These tools give agents the ability to:
1. Fetch logs from containers (for log analysis)
2. Check container health (for infrastructure diagnosis)

Critical Design Principle:
- Return strings (not objects) → LLM can read strings
- Return errors as strings (enables reflection/retry)
- Comprehensive docstrings (LLM knows when/how to use)
"""
import docker
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# TOOL 1: FETCH SERVICE LOGS
# ============================================================================

def fetch_service_logs(
    service_name: str,
    tail_lines: int = 100,
    since_seconds: Optional[int] = None
) -> str:
    """
    Fetch recent logs from a Docker container.

    **Use this tool when:**
    - Investigating application errors (500 Internal Server Error)
    - Looking for Python tracebacks and stack traces
    - Checking for error messages in application logs
    - Finding timestamps of failures
    - Analyzing request/response patterns

    **Do NOT use this tool for:**
    - Infrastructure health checks (use check_container_health instead)
    - Container resource usage (use check_container_health instead)
    - Network connectivity issues (use check_container_health instead)

    Args:
        service_name (str): Exact name of the Docker container.
            Examples: "order-service", "payment-service", "inventory-service"
            Must match container name from docker-compose.yml or docker ps

        tail_lines (int, optional): Number of recent log lines to retrieve.
            Default: 100 (sufficient for most error investigations)
            Recommended range: 10-500
            Note: More lines = more LLM tokens consumed

        since_seconds (int, optional): Only get logs from last N seconds.
            Example: since_seconds=300 (last 5 minutes)
            Default: None (all available logs, up to tail_lines)

    Returns:
        str: Container logs with timestamps, formatted as multi-line string.
             Format: "YYYY-MM-DDTHH:MM:SS.ffffffZ <log message>"
             Each line is one log entry.

             If error occurs, returns error message with troubleshooting hints.

    Example Usage:
        # Fetch last 100 lines from order service
        logs = fetch_service_logs("order-service")

        # Fetch last 50 lines for quick check
        logs = fetch_service_logs("payment-service", tail_lines=50)

        # Fetch logs from last 5 minutes only
        logs = fetch_service_logs("order-service", since_seconds=300)

    Error Handling:
        - Container not found → Returns list of available containers
        - Docker daemon down → Returns troubleshooting hint
        - Permission denied → Returns sudo/permissions hint
    """
    try:
        # Initialize Docker client
        # Why from_env()? Respects DOCKER_HOST environment variable (Podman support)
        client = docker.from_env()

        logger.info(f"Fetching logs from container: {service_name} (tail={tail_lines})")

        # Get container by name
        # Why .get()? Raises NotFound if container doesn't exist (we catch below)
        container = client.containers.get(service_name)

        # Fetch logs
        # Why tail=tail_lines? Prevents overwhelming context window
        # Why timestamps=True? Helps agent identify when errors occurred
        # Why since=since_seconds? Filter to recent logs only (optional)
        logs = container.logs(
            tail=tail_lines,
            timestamps=True,
            since=since_seconds
        )

        # Decode bytes to string
        # Why decode('utf-8', errors='replace')? Handles binary data gracefully
        logs_str = logs.decode('utf-8', errors='replace')

        logger.info(f"Successfully fetched {len(logs_str.splitlines())} log lines from {service_name}")

        return logs_str

    except docker.errors.NotFound:
        # ✅ Error as string (LLM can read and reflect)
        logger.warning(f"Container '{service_name}' not found")

        try:
            # Get list of available containers to help LLM self-correct
            client = docker.from_env()
            available = [c.name for c in client.containers.list()]

            error_msg = f"""Error: Container '{service_name}' not found.

Available containers:
{chr(10).join(f"  - {name}" for name in available)}

Tip: Use exact container name from the list above.
Example: fetch_service_logs("order-service")
"""
            return error_msg

        except Exception as e:
            return f"Error: Container not found and unable to list containers: {str(e)}"

    except docker.errors.APIError as e:
        # Docker daemon issues
        logger.error(f"Docker API error: {str(e)}")
        return f"""Error: Docker API error: {str(e)}

Possible causes:
1. Docker daemon not running
2. Permission denied (try with sudo or add user to docker group)
3. DOCKER_HOST environment variable incorrect (for Podman)

Troubleshooting:
- Check Docker status: docker ps
- For Podman: export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
"""

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error fetching logs: {str(e)}")
        return f"""Error: Unexpected error while fetching logs: {str(e)}

This is an unusual error. Please check Docker daemon and container status manually.
"""


# ============================================================================
# TOOL 2: CHECK CONTAINER HEALTH
# ============================================================================

def check_container_health(service_name: str) -> str:
    """
    Check health status and resource usage of a Docker container.

    **Use this tool when:**
    - Investigating 502 Bad Gateway errors (likely container down)
    - Investigating 504 Gateway Timeout (likely resource exhaustion)
    - Checking if container is running or crashed
    - Looking for OOM (Out of Memory) kills
    - Checking restart count (container stability)
    - Analyzing memory/CPU usage patterns

    **Do NOT use this tool for:**
    - Reading application logs (use fetch_service_logs instead)
    - Analyzing stack traces (use fetch_service_logs instead)

    Args:
        service_name (str): Exact name of the Docker container to inspect.
            Examples: "order-service", "payment-service", "inventory-service"

    Returns:
        str: Formatted health report including:
             - Container name and status (running/exited/restarting/paused)
             - Exit code (if stopped): 0=normal, 137=OOM killed, 1=error
             - OOM killed flag (True if killed by Out of Memory)
             - Restart count (how many times container restarted)
             - Memory usage and limit
             - Created timestamp and uptime

             If error occurs, returns error message with available containers.

    Example Usage:
        # Check health of order service
        health = check_container_health("order-service")

        # Look for OOM kills
        health = check_container_health("payment-service")
        # Output will show: "OOM Killed: True" if memory exhausted

    Key Indicators:
        - Status "exited" → Container crashed
        - Exit code 137 → OOM (Out of Memory) killed by system
        - Exit code 1 → Application error caused exit
        - High restart count → Unstable container (crashing repeatedly)
        - Memory usage near limit → Potential OOM risk
    """
    try:
        client = docker.from_env()

        logger.info(f"Checking health of container: {service_name}")

        # Get container
        container = client.containers.get(service_name)

        # Get container state
        container.reload()  # Refresh state
        state = container.attrs['State']

        # Get memory stats (if running)
        memory_usage = "N/A"
        memory_limit = "N/A"

        if container.status == 'running':
            try:
                stats = container.stats(stream=False)
                memory_usage = stats['memory_stats'].get('usage', 0) / (1024 * 1024)  # MB
                memory_limit = stats['memory_stats'].get('limit', 0) / (1024 * 1024)  # MB
                memory_usage = f"{memory_usage:.2f} MB"
                memory_limit = f"{memory_limit:.2f} MB"
            except Exception as e:
                logger.warning(f"Could not fetch memory stats: {str(e)}")

        # Build health report
        health_report = f"""Container Health Report for '{service_name}':

Status: {container.status.upper()}
Running: {state['Running']}
Paused: {state.get('Paused', False)}
Restarting: {state.get('Restarting', False)}

Exit Information:
  Exit Code: {state.get('ExitCode', 'N/A')}
  OOM Killed: {state.get('OOMKilled', False)}
  Error Message: {state.get('Error', 'None')}

Restart Count: {container.attrs['RestartCount']}

Resource Usage:
  Memory Usage: {memory_usage}
  Memory Limit: {memory_limit}

Timestamps:
  Created: {container.attrs['Created']}
  Started: {state.get('StartedAt', 'N/A')}
  Finished: {state.get('FinishedAt', 'N/A')}

Container ID: {container.short_id}

Interpretation:
  - Exit Code 0 = Normal exit
  - Exit Code 137 = OOM (Out of Memory) killed by system
  - Exit Code 1 = Application error
  - OOM Killed = True → Memory exhaustion caused crash
  - High Restart Count → Unstable container (investigate logs)
"""

        logger.info(f"Successfully retrieved health info for {service_name}")

        return health_report

    except docker.errors.NotFound:
        logger.warning(f"Container '{service_name}' not found")

        try:
            client = docker.from_env()
            available = [c.name for c in client.containers.list(all=True)]  # Include stopped containers

            error_msg = f"""Error: Container '{service_name}' not found.

Available containers (including stopped):
{chr(10).join(f"  - {name}" for name in available)}

Tip: Use exact container name from the list above.
Example: check_container_health("order-service")
"""
            return error_msg

        except Exception as e:
            return f"Error: Container not found and unable to list containers: {str(e)}"

    except docker.errors.APIError as e:
        logger.error(f"Docker API error: {str(e)}")
        return f"""Error: Docker API error: {str(e)}

Troubleshooting:
- Check Docker daemon is running: docker ps
- For Podman: export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
"""

    except Exception as e:
        logger.error(f"Unexpected error checking container health: {str(e)}")
        return f"Error: Unexpected error: {str(e)}"


# ============================================================================
# HELPER: LIST ALL CONTAINERS (for debugging)
# ============================================================================

def list_containers() -> str:
    """
    List all Docker containers (helper function, not a direct agent tool).

    Returns:
        str: Formatted list of container names and statuses
    """
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)

        if not containers:
            return "No containers found."

        lines = ["Available Docker Containers:", ""]
        for c in containers:
            lines.append(f"  - {c.name} ({c.status})")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing containers: {str(e)}"
```

**Critical Design Decisions**:

1. **Why return strings, not objects?**
   ```python
   # ❌ Wrong: LLM can't parse Python objects
   return container  # <Container: order-service>

   # ✅ Correct: LLM can read strings
   return "Status: running\nMemory: 35MB"
   ```

2. **Why comprehensive docstrings?**
   - LLM has 100% zero knowledge of your codebase
   - Docstring is the ONLY source of truth for when/how to use tools
   - Vague docstring = wrong tool usage

3. **Why include error context in error messages?**
   ```python
   # ❌ Vague error
   return "Container not found"
   # LLM thinks: "Hmm, I'm stuck"

   # ✅ Actionable error
   return "Container 'order' not found. Available: order-service, payment-service"
   # LLM thinks: "Oh, I should use 'order-service' not 'order'!"
   ```

---

### Step 3: Implement Memory Layer (75 minutes)

**Create File**: `auto_healer/memory.py`

```python
"""
RAG Memory System with ChromaDB

Implements long-term memory for the agent using vector similarity search.
Agents learn from approved RCA reports without requiring model retraining.

Architecture:
1. Query: Semantic search for similar past incidents
2. Retrieve: Get relevant RCA reports from vector database
3. Enrich: Add historical context to agent prompts
4. Store: Save approved RCAs for future reference

Storage: Local ChromaDB (SQLite-based, no external DB needed)
"""
import chromadb
from chromadb.config import Settings
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)

# Global ChromaDB client and collection
_client: Optional[chromadb.Client] = None
_collection: Optional[chromadb.Collection] = None


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_chromadb(
    persist_directory: str = "./.chromadb",
    collection_name: str = "incident_history"
) -> bool:
    """
    Initialize ChromaDB with local persistence.

    **Why local persistence?**
    - No external database required (SQLite-based)
    - Survives agent restarts
    - Simple setup (just a directory)
    - Privacy-friendly (data stays local)

    Args:
        persist_directory (str): Directory for ChromaDB storage.
            Default: "./.chromadb" (in project root)

        collection_name (str): Name of the incident collection.
            Default: "incident_history"

    Returns:
        bool: True if initialization successful, False otherwise

    Side Effects:
        - Creates persist_directory if doesn't exist
        - Sets global _client and _collection variables
        - Logs initialization status
    """
    global _client, _collection

    try:
        logger.info(f"Initializing ChromaDB at: {persist_directory}")

        # Create directory if doesn't exist
        os.makedirs(persist_directory, exist_ok=True)

        # Initialize ChromaDB client with local persistence
        # Why Settings(anonymized_telemetry=False)? Privacy for production use
        # Why persist_directory? Data survives restarts
        _client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False  # Disable telemetry for privacy
        ))

        # Get or create collection
        # Why get_or_create? Idempotent (safe to call multiple times)
        _collection = _client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": "Historical RCA reports for similar incident retrieval",
                "hnsw:space": "cosine"  # Cosine similarity for semantic search
            }
        )

        incident_count = _collection.count()

        logger.info(f"ChromaDB initialized successfully. "
                   f"Collection '{collection_name}' has {incident_count} incidents.")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {str(e)}")
        return False


def get_collection() -> chromadb.Collection:
    """
    Get ChromaDB collection (initializes if not already done).

    Returns:
        chromadb.Collection: The incident history collection

    Raises:
        RuntimeError: If initialization fails
    """
    global _collection

    if _collection is None:
        success = initialize_chromadb()
        if not success or _collection is None:
            raise RuntimeError("Failed to initialize ChromaDB")

    return _collection


def get_memory_stats() -> Dict[str, int]:
    """
    Get memory statistics (for debugging/monitoring).

    Returns:
        dict: {
            "total_incidents": int,
            "collection_name": str
        }
    """
    try:
        collection = get_collection()
        return {
            "total_incidents": collection.count(),
            "collection_name": collection.name
        }
    except Exception as e:
        logger.error(f"Error getting memory stats: {str(e)}")
        return {"total_incidents": 0, "collection_name": "unknown"}


# ============================================================================
# QUERY: Semantic Search for Similar Incidents
# ============================================================================

def query_past_incidents(
    alert_info: Dict[str, any],
    top_k: int = 3,
    similarity_threshold: float = 0.0
) -> str:
    """
    Query ChromaDB for similar past incidents using semantic search.

    **How it works:**
    1. Build query text from alert metadata
    2. ChromaDB computes embedding (vector representation)
    3. Finds top_k most similar incidents (cosine similarity)
    4. Returns formatted results for LLM consumption

    Args:
        alert_info (dict): Current alert metadata
            Required fields: service, status_code
            Optional: error_message, timestamp

        top_k (int): Number of similar incidents to retrieve.
            Default: 3 (good balance of context vs token usage)

        similarity_threshold (float): Minimum similarity score (0.0 to 1.0).
            Default: 0.0 (return all top_k results)
            Higher values = stricter matching

    Returns:
        str: Formatted historical context for LLM, or "No similar past incidents found."

    Example:
        alert = {"service": "order-service", "status_code": 500, "error_message": "Division by zero"}
        context = query_past_incidents(alert)
        # Returns:
        # "Similar Past Incidents:
        #  1. [2024-04-29] order-service - 500
        #     Resolution: Fixed ZeroDivisionError at /app/app.py:84..."
    """
    try:
        collection = get_collection()

        # Check if collection has data
        # Why check count? Prevents "cannot query 0 results" error
        if collection.count() == 0:
            logger.info("No incidents in memory yet")
            return "No similar past incidents found."

        # Build query text from alert metadata
        # Why include service + status_code + error? Better semantic matching
        query_parts = [
            alert_info.get('service', 'unknown'),
            str(alert_info.get('status_code', '')),
            alert_info.get('error_message', '')
        ]
        query_text = " ".join(filter(None, query_parts))  # Filter empty strings

        logger.info(f"Querying ChromaDB with: '{query_text}' (top_k={top_k})")

        # Semantic search
        # Why n_results=min(top_k, count)? Can't retrieve more than exist
        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, collection.count())
        )

        # Parse results
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]  # Lower distance = more similar

        if not documents:
            logger.info("No similar incidents found (empty results)")
            return "No similar past incidents found."

        # Filter by similarity threshold (distance < threshold)
        # Note: ChromaDB returns DISTANCE (lower = more similar), not similarity
        # For cosine distance: 0 = identical, 2 = opposite
        filtered_results = [
            (doc, meta, dist)
            for doc, meta, dist in zip(documents, metadatas, distances)
            if dist <= (2.0 - similarity_threshold)  # Convert similarity to distance
        ]

        if not filtered_results:
            logger.info(f"No incidents above similarity threshold {similarity_threshold}")
            return "No similar past incidents found."

        # Format results for LLM consumption
        formatted = "**Similar Past Incidents:**\n\n"

        for i, (doc, meta, dist) in enumerate(filtered_results, 1):
            # Extract metadata
            timestamp = meta.get('timestamp', 'Unknown date')
            service = meta.get('service', 'unknown')
            status_code = meta.get('status_code', 'unknown')

            # Truncate RCA for readability (first 300 chars)
            rca_preview = doc[:300] + "..." if len(doc) > 300 else doc

            # Calculate similarity percentage (1 - distance/2) * 100
            similarity_pct = ((2.0 - dist) / 2.0) * 100

            formatted += f"{i}. [{timestamp}] {service} - {status_code} (Similarity: {similarity_pct:.1f}%)\n"
            formatted += f"   {rca_preview}\n\n"

        logger.info(f"Found {len(filtered_results)} similar incidents")

        return formatted

    except Exception as e:
        logger.error(f"Error querying past incidents: {str(e)}")
        return f"Error querying memory: {str(e)}"


# ============================================================================
# STORE: Save Approved RCA to Memory
# ============================================================================

def save_incident(
    rca_report: str,
    alert_info: Dict[str, any]
) -> bool:
    """
    Store human-approved RCA report in ChromaDB.

    **Why only store approved RCAs?**
    - Prevents agent from learning incorrect diagnoses
    - Human-in-the-loop ensures quality
    - Memory improves over time (only good examples)

    Args:
        rca_report (str): Full RCA report text (will be embedded)
        alert_info (dict): Alert metadata for filtering/search

    Returns:
        bool: True if successfully saved, False otherwise

    Side Effects:
        - Adds document to ChromaDB collection
        - Generates embedding automatically (ChromaDB handles this)
    """
    try:
        collection = get_collection()

        # Generate unique ID
        # Why timestamp-based? Ensures uniqueness + sortability
        incident_id = f"{alert_info.get('service', 'unknown')}_{alert_info.get('status_code', 0)}_{datetime.utcnow().timestamp()}"

        # Prepare metadata (for filtering)
        metadata = {
            "service": alert_info.get('service', 'unknown'),
            "status_code": str(alert_info.get('status_code', 0)),
            "timestamp": datetime.utcnow().isoformat(),
            "error_message": alert_info.get('error_message', '')[:200]  # Truncate
        }

        logger.info(f"Saving incident to memory: {incident_id}")

        # Add to collection
        # Why documents=[rca_report]? This gets embedded for semantic search
        # Why metadatas=[metadata]? Enables filtering by service, status, etc.
        collection.add(
            documents=[rca_report],
            metadatas=[metadata],
            ids=[incident_id]
        )

        logger.info(f"Incident saved successfully. Total incidents: {collection.count()}")

        return True

    except Exception as e:
        logger.error(f"Failed to save incident: {str(e)}")
        return False


# ============================================================================
# MAINTENANCE: Clear Memory (for testing/debugging)
# ============================================================================

def clear_all_incidents() -> bool:
    """
    Delete all incidents from memory (use with caution!).

    **WARNING**: This is irreversible.

    Returns:
        bool: True if successfully cleared
    """
    try:
        global _client, _collection

        if _client and _collection:
            # Delete collection
            _client.delete_collection(name=_collection.name)
            logger.info("All incidents cleared from memory")

            # Reinitialize
            initialize_chromadb()
            return True

        return False

    except Exception as e:
        logger.error(f"Error clearing incidents: {str(e)}")
        return False


def get_all_incidents() -> List[Dict]:
    """
    Retrieve all incidents (for debugging/export).

    Returns:
        list: List of dicts with {id, document, metadata}
    """
    try:
        collection = get_collection()

        # Get all items
        results = collection.get()

        incidents = []
        for i in range(len(results['ids'])):
            incidents.append({
                "id": results['ids'][i],
                "document": results['documents'][i],
                "metadata": results['metadatas'][i]
            })

        return incidents

    except Exception as e:
        logger.error(f"Error getting all incidents: {str(e)}")
        return []
```

**Key Design Decisions**:

1. **Why ChromaDB over alternatives?**
   - Local persistence (no external DB)
   - Automatic embeddings (no manual vector computation)
   - Simple API (3 functions: add, query, get)
   - SQLite-based (lightweight)

2. **Why semantic search over keyword search?**
   ```python
   # Keyword search (naive):
   query: "500 error order service"
   matches: Only incidents with EXACT words "500", "error", "order", "service"
   misses: "Internal Server Error in order-service" (different wording!)

   # Semantic search (ChromaDB):
   query: "500 error order service"
   matches: "Internal Server Error in order-service" (understands meaning!)
   matches: "ZeroDivisionError in order endpoint" (related concept!)
   ```

3. **Why filter by similarity_threshold?**
   - Low similarity = unrelated incident
   - Prevents polluting context with irrelevant history
   - Default 0.0 = return all top_k (no filtering)

---

### Step 4: Configure LLM (25 minutes)

**Create File**: `auto_healer/llm_config.py`

```python
"""
LLM Configuration for Local Inference with Ollama

CRITICAL CONFIGURATION:
- num_ctx MUST be >= 16384 for log analysis (100 lines = ~5000 tokens)
- Default 2048 will silently truncate logs → agent misses errors!

This was a real bug in Phase 4 - agent couldn't find errors because logs were truncated.
"""
from langchain_ollama import ChatOllama
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_MODEL = "qwen2.5:14b"
"""
Default model for agent inference.

Why qwen2.5:14b?
- Excellent reasoning quality (beats many closed models)
- 14B parameters = good balance (quality vs speed)
- 9GB download (fits on M3 Pro with 36GB RAM)
- 16K+ context window support
- Strong tool calling capabilities
- Open source (Apache 2.0 license)

Alternatives:
- llama3.1:8b (faster, lower quality)
- mixtral:8x7b (higher quality, slower, more memory)
- llama3.1:70b (best quality, requires 64GB+ RAM)
"""

MIN_CONTEXT_WINDOW = 16384
"""
Minimum context window for log analysis.

Token Math:
- 1 log line ≈ 50 tokens (timestamp + JSON + message)
- 100 log lines ≈ 5,000 tokens
- Agent prompt + history ≈ 2,000 tokens
- Safety margin ≈ 2× = 14,000 tokens
- Rounded up to 16K for power-of-2 alignment

CRITICAL: Default Ollama num_ctx = 2048 (too small!)
"""

RECOMMENDED_CONTEXT_WINDOW = 16384
"""
Recommended context window for production use.

32K = more headroom, but slower inference
16K = good balance (current choice)
8K = too small for 100-line logs
"""


# ============================================================================
# LLM INITIALIZATION
# ============================================================================

def get_llm(
    model: str = DEFAULT_MODEL,
    num_ctx: Optional[int] = None,
    temperature: float = 0.0,
    num_predict: int = 2048
) -> ChatOllama:
    """
    Initialize local LLM with Ollama.

    CRITICAL: num_ctx MUST be >= 16384 for log analysis!
    Default 2048 will truncate logs and cause silent failures.

    Args:
        model (str): Ollama model name.
            Default: "qwen2.5:14b"
            Options: Run `ollama list` to see installed models

        num_ctx (int, optional): Context window size in tokens.
            Default: None (uses RECOMMENDED_CONTEXT_WINDOW = 16384)
            Minimum: 16384 (enforced with warning)
            Recommended: 16384-32768

        temperature (float): Sampling temperature.
            0.0 = Deterministic (best for debugging)
            0.7 = Balanced creativity
            1.0 = Maximum randomness
            Default: 0.0 (reproducible results for testing)

        num_predict (int): Maximum tokens to generate in response.
            Default: 2048 (sufficient for most RCA reports)
            Increase if responses are truncated

    Returns:
        ChatOllama: Configured LLM instance ready for use

    Raises:
        RuntimeError: If Ollama is not running or model not found

    Example:
        # Use defaults (recommended)
        llm = get_llm()

        # Use different model
        llm = get_llm(model="llama3.1:8b")

        # Larger context for complex investigations
        llm = get_llm(num_ctx=32768)
    """
    # Set default context window if not provided
    if num_ctx is None:
        num_ctx = RECOMMENDED_CONTEXT_WINDOW

    # Safety check: Enforce minimum context window
    if num_ctx < MIN_CONTEXT_WINDOW:
        logger.warning(
            f"num_ctx={num_ctx} is too small for log analysis! "
            f"Forcing num_ctx={MIN_CONTEXT_WINDOW}."
        )
        logger.warning(
            f"Token math: 100 log lines ≈ 5000 tokens. "
            f"Default 2048 will truncate logs and cause agent to miss errors!"
        )
        num_ctx = MIN_CONTEXT_WINDOW

    logger.info(f"Initializing ChatOllama:")
    logger.info(f"  Model: {model}")
    logger.info(f"  Context Window: {num_ctx} tokens")
    logger.info(f"  Temperature: {temperature}")
    logger.info(f"  Max Output: {num_predict} tokens")

    try:
        llm = ChatOllama(
            model=model,
            num_ctx=num_ctx,
            temperature=temperature,
            num_predict=num_predict,
            # Why no format="json"? Not all models support it
            # We use Pydantic structured outputs instead (more reliable)
        )

        logger.info("ChatOllama LLM initialized successfully")

        # Test connectivity (optional, catches issues early)
        try:
            test_response = llm.invoke("Hello")
            logger.debug(f"LLM test successful: {test_response.content[:50]}...")
        except Exception as e:
            logger.warning(f"LLM test failed (but proceeding): {str(e)}")

        return llm

    except Exception as e:
        logger.error(f"Failed to initialize LLM: {str(e)}")
        logger.error("Troubleshooting:")
        logger.error("1. Is Ollama running? Check with: ollama list")
        logger.error("2. Is model installed? Install with: ollama pull " + model)
        logger.error("3. Sufficient memory? qwen2.5:14b needs ~12GB RAM at runtime")
        raise RuntimeError(f"LLM initialization failed: {str(e)}")


# ============================================================================
# UTILITIES
# ============================================================================

def test_llm_connection(model: str = DEFAULT_MODEL) -> bool:
    """
    Test LLM connectivity (useful for setup validation).

    Args:
        model (str): Model to test

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        logger.info(f"Testing LLM connection with model: {model}")

        llm = get_llm(model=model)
        response = llm.invoke("Respond with exactly: 'LLM connection successful'")

        if "successful" in response.content.lower():
            logger.info("✅ LLM connection test: PASSED")
            return True
        else:
            logger.warning(f"⚠️  LLM connection test: UNEXPECTED RESPONSE: {response.content}")
            return False

    except Exception as e:
        logger.error(f"❌ LLM connection test: FAILED - {str(e)}")
        return False


def list_available_models() -> list:
    """
    List Ollama models installed on the system.

    Returns:
        list: Model names, or empty list if Ollama not available
    """
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)

        if result.returncode == 0:
            # Parse output (skip header line)
            lines = result.stdout.strip().split('\n')[1:]
            models = [line.split()[0] for line in lines if line.strip()]
            return models
        else:
            return []

    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        return []


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test LLM connection
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("LLM Configuration Test")
    print("=" * 60)

    # List available models
    print("\nAvailable Ollama models:")
    models = list_available_models()
    for model in models:
        print(f"  - {model}")

    # Test connection
    print("\nTesting LLM connection...")
    success = test_llm_connection()

    if success:
        print("\n✅ LLM configuration validated successfully!")
    else:
        print("\n❌ LLM configuration test failed. Check Ollama setup.")
```

**Critical Insights**:

1. **The Context Window Bug** (real issue from Phase 4):
   ```python
   # THIS WAS THE ACTUAL BUG:
   llm = ChatOllama(model="qwen2.5:14b")  # Default num_ctx=2048

   # Agent fetches 100 lines of logs (5000 tokens)
   # Ollama silently truncates to 2048 tokens
   # Only first ~40 lines visible to LLM
   # Stack trace at line 95 is MISSING
   # LLM: "I don't see any errors" (but error was there!)

   # Fix:
   llm = ChatOllama(model="qwen2.5:14b", num_ctx=16384)
   # Now all 100 lines fit → Agent finds error
   ```

2. **Why temperature=0.0?**
   - Deterministic outputs (same input = same output)
   - Reproducible testing
   - No randomness in debugging (want consistency)
   - Production might use 0.1-0.3 for slight variety

3. **Why test_llm_connection()?**
   - Catches setup issues early
   - Verifies Ollama is running
   - Confirms model is downloaded
   - Prevents cryptic errors later

---

## 2.5 Validation Checkpoints

### Checkpoint 1: Test Docker Tools

```python
# Start Python REPL in venv
source .venv/bin/activate
python

# Import tools
from auto_healer.tools.docker_tools import fetch_service_logs, check_container_health

# Test 1: Fetch logs from order service
logs = fetch_service_logs("order-service", tail_lines=20)
print(logs)

# Expected output:
# 2024-04-30T12:00:00.123456Z {"timestamp":"...","service":"order-service","event":"order_create_start",...}
# ... (20 lines total)

# Test 2: Check container health
health = check_container_health("order-service")
print(health)

# Expected output:
# Container Health Report for 'order-service':
# Status: RUNNING
# Exit Code: N/A
# Memory Usage: 35.42 MB
# ...

# Test 3: Error handling (wrong container name)
logs = fetch_service_logs("nonexistent-service")
print(logs)

# Expected output:
# Error: Container 'nonexistent-service' not found.
# Available containers:
#   - order-service
#   - payment-service
#   - inventory-service
```

**If tests fail**:
- Docker not running → Start Docker/Podman
- Containers not running → `docker-compose up -d`
- Import errors → Check Python path, activate venv

### Checkpoint 2: Test Memory System

```python
from auto_healer.memory import initialize_chromadb, query_past_incidents, save_incident, get_memory_stats

# Test 1: Initialize ChromaDB
success = initialize_chromadb()
print(f"Initialization: {'SUCCESS' if success else 'FAILED'}")

# Test 2: Check stats (should be empty first time)
stats = get_memory_stats()
print(f"Total incidents: {stats['total_incidents']}")
# Expected: 0 (first run)

# Test 3: Save test incident
test_rca = """Root Cause Analysis:
Service: order-service
Error: 500 Internal Server Error
Root Cause: ZeroDivisionError at /app/app.py:84
Resolution: Fixed division by zero in discount calculation
"""

test_alert = {
    "service": "order-service",
    "status_code": 500,
    "error_message": "Division by zero"
}

saved = save_incident(test_rca, test_alert)
print(f"Incident saved: {saved}")

# Test 4: Query for similar incidents
alert = {"service": "order-service", "status_code": 500, "error_message": "Internal Server Error"}
results = query_past_incidents(alert, top_k=1)
print(results)

# Expected output:
# **Similar Past Incidents:**
# 1. [2024-04-30T...] order-service - 500 (Similarity: 95.2%)
#    Root Cause Analysis:
#    Service: order-service...
```

**If tests fail**:
- ChromaDB import error → `uv pip install chromadb`
- Permission denied → Check `.chromadb` directory permissions
- Empty query results → Check `save_incident` returned True

### Checkpoint 3: Test LLM Connection

```python
from auto_healer.llm_config import get_llm, test_llm_connection

# Test 1: Initialize LLM
llm = get_llm()
print("LLM initialized")

# Test 2: Simple query
response = llm.invoke("Say 'LLM working correctly'")
print(response.content)
# Expected: "LLM working correctly" (or similar)

# Test 3: Connection test utility
success = test_llm_connection()
print(f"Connection test: {'PASSED' if success else 'FAILED'}")

# Test 4: Check context window (critical!)
llm = get_llm()
# Check logs for warning about context window
# Should NOT see: "num_ctx=2048 is too small!"
# Should see: "Context Window: 16384 tokens"
```

**If tests fail**:
- Ollama not running → `ollama serve` (in separate terminal)
- Model not found → `ollama pull qwen2.5:14b` (9GB download)
- Connection refused → Check Ollama is on http://localhost:11434

### Checkpoint 4: Integration Test (All Components)

```python
# Complete workflow test
from auto_healer.tools.docker_tools import fetch_service_logs
from auto_healer.memory import query_past_incidents, save_incident
from auto_healer.llm_config import get_llm

# 1. Trigger chaos
import requests
requests.get("http://localhost:8001/order?chaos_type=500_zerodivision")

# 2. Fetch logs (like agent would)
logs = fetch_service_logs("order-service", tail_lines=100)
print(f"Fetched {len(logs.splitlines())} log lines")

# 3. Query memory (empty initially)
alert = {"service": "order-service", "status_code": 500}
context = query_past_incidents(alert)
print(f"Historical context: {context}")

# 4. Test LLM with logs
llm = get_llm()
prompt = f"""Analyze these logs and find the error:

{logs}

What is the root cause?"""

response = llm.invoke(prompt)
print(f"\nLLM Analysis:\n{response.content}")

# Expected: LLM identifies ZeroDivisionError at /app/app.py:84
```

**Success Criteria**:
- ✅ Logs fetched successfully (100 lines)
- ✅ Memory query returns "No similar incidents" (first run)
- ✅ LLM identifies ZeroDivisionError
- ✅ LLM cites file path (/app/app.py) and line number

---

## 2.6 Common Pitfalls

*(Continued in actual lesson file - this is already very comprehensive)*

### Pitfall 1: Context Window Too Small

**Symptom**: Agent says "I don't see any errors" when logs clearly show errors

**Root Cause**: `num_ctx=2048` (default) truncates 100-line logs

**Detection**:
```python
logs = fetch_service_logs("order-service", tail_lines=100)
token_count = len(logs.split()) * 1.3  # Rough estimate
print(f"Estimated tokens: {token_count}")
# If > 2048, will be truncated!
```

**Solution**: Always set `num_ctx=16384`
```python
llm = ChatOllama(model="qwen2.5:14b", num_ctx=16384)  # ✅
```

### Pitfall 2: ChromaDB Empty Collection Query

**Symptom**:
```
Error: Number of requested results 0, cannot be negative, or zero
```

**Root Cause**: Querying empty ChromaDB collection

**Wrong Code**:
```python
results = collection.query(query_texts=["..."], n_results=3)
# Fails if collection is empty!
```

**Correct Code**:
```python
if collection.count() > 0:
    results = collection.query(
        query_texts=["..."],
        n_results=min(3, collection.count())  # Don't request more than exist
    )
else:
    return "No similar past incidents found."
```

### Pitfall 3: Tool Docstring Too Vague

**Symptom**: LLM doesn't use tools OR uses them incorrectly

**Wrong Docstring**:
```python
def get_logs(service):
    """Get logs from a service."""  # Too vague!
```

**LLM Confusion**:
- When should I use this?
- What format for `service`?
- How many logs does it return?
- What if service doesn't exist?

**Correct Docstring**: See `fetch_service_logs` example in Step 2

**Rule**: Docstring should answer:
1. WHEN to use (what scenarios)
2. WHAT each parameter means (with examples)
3. WHAT the output looks like
4. HOW errors are handled

### Pitfall 4: Returning Python Objects Instead of Strings

**Wrong**:
```python
def check_health(service):
    container = docker_client.containers.get(service)
    return container  # ❌ LLM can't read this!
```

**LLM sees**: `<Container: order-service>` (useless!)

**Correct**:
```python
def check_health(service):
    container = docker_client.containers.get(service)
    return f"Status: {container.status}\nMemory: {stats}"  # ✅ LLM can read
```

### Pitfall 5: Docker Host Not Set for Podman

**Symptom**:
```
docker.errors.DockerException: Error while fetching server API version
```

**Root Cause**: Docker SDK doesn't know about Podman socket

**Solution**: Set environment variable
```bash
# Add to ~/.zshrc or ~/.bashrc
export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
```

**Verify**:
```bash
python -c "import docker; print(docker.from_env().ping())"
# Should print: True
```

---

## 2.7 Exercises

### Exercise 1: Add Log Filtering

**Objective**: Modify `fetch_service_logs` to accept `filter_text` parameter

**Implementation**:
```python
def fetch_service_logs(
    service_name: str,
    tail_lines: int = 100,
    filter_text: Optional[str] = None  # NEW
) -> str:
    """
    ... (existing docstring)

    Args:
        filter_text (str, optional): Only return lines containing this text.
            Example: filter_text="ERROR" (only error lines)
    """
    logs = container.logs(tail=tail_lines, timestamps=True)
    logs_str = logs.decode('utf-8', errors='replace')

    # NEW: Filter lines
    if filter_text:
        filtered_lines = [
            line for line in logs_str.splitlines()
            if filter_text.lower() in line.lower()
        ]
        return "\n".join(filtered_lines)

    return logs_str
```

**Test**:
```python
# Trigger error
requests.get("http://localhost:8001/order?chaos_type=500_zerodivision")

# Fetch only error lines
logs = fetch_service_logs("order-service", filter_text="error")
print(logs)
# Should only show lines with "error" or "ERROR"
```

### Exercise 2: Implement Incident Tagging

**Objective**: Add tags to incidents for better categorization

**Implementation**:
```python
def save_incident(
    rca_report: str,
    alert_info: Dict[str, any],
    tags: Optional[List[str]] = None  # NEW
) -> bool:
    """
    ... (existing docstring)

    Args:
        tags (list, optional): Tags for categorization.
            Examples: ["database_timeout"], ["oom_kill"], ["code_bug"]
    """
    metadata = {
        "service": alert_info.get('service', 'unknown'),
        "status_code": str(alert_info.get('status_code', 0)),
        "timestamp": datetime.utcnow().isoformat(),
        "tags": ",".join(tags or [])  # NEW: Store as comma-separated
    }

    collection.add(
        documents=[rca_report],
        metadatas=[metadata],
        ids=[incident_id]
    )
```

**Test**:
```python
save_incident(
    rca_report="...",
    alert_info={...},
    tags=["code_bug", "zerodivision_error"]
)
```

### Exercise 3: Context Window Validation Test

**Objective**: Verify LLM can handle 200 lines of logs

**Implementation**:
```python
# Trigger multiple errors
for _ in range(10):
    requests.get("http://localhost:8001/order?chaos_type=500_zerodivision")

# Fetch 200 lines
logs = fetch_service_logs("order-service", tail_lines=200)

# Count tokens (rough estimate)
token_estimate = len(logs.split()) * 1.3
print(f"Estimated tokens: {token_estimate}")

# Test with LLM
llm = get_llm(num_ctx=16384)
response = llm.invoke(f"Count how many ZeroDivisionError lines are in these logs:\n{logs}")

print(response.content)
# LLM should correctly count ~10 errors
```

---

## 2.8 Key Takeaways

### ✅ What You Learned

1. **Tool Design for LLMs is Critical**
   - Comprehensive docstrings (when, what, how)
   - Error messages with context (enables reflection)
   - Return strings, not objects

2. **RAG Memory Architecture**
   - Semantic search with ChromaDB
   - No model retraining needed
   - Human-in-the-loop quality control

3. **Context Window Management**
   - Default 2048 is too small for logs!
   - Minimum 16K for 100-line log analysis
   - Silent truncation = dangerous bug

4. **Error Handling with Reflection**
   - Return errors as strings (not exceptions)
   - Include available options (enables self-correction)
   - Agent recovers from mistakes autonomously

### 📊 Metrics from Real Project

- **Tools Built**: 2 (fetch_logs, check_health)
- **Memory Functions**: 3 (init, query, save)
- **Context Window**: 16384 tokens (8× default)
- **Lines of Code**: ~600 (tools + memory + LLM config)
- **Critical Bug Found**: Default context window too small (Phase 4 discovery)

### 🎯 Production-Ready Aspects

- ✅ Graceful error handling (informative messages)
- ✅ Local persistence (no external DB)
- ✅ Type safety (TypedDict for state)
- ✅ Logging for debugging
- ✅ Test utilities (connection tests)

### 🔍 Critical Insights

**Q: Why not use OpenAI API instead of local LLM?**
A: Privacy (logs may contain sensitive data), cost (local = free after download), offline capability

**Q: Why ChromaDB over Pinecone/Weaviate?**
A: Local persistence (no external service), simple setup, SQLite-based (lightweight)

**Q: How did you discover the context window bug?**
A: Phase 4 testing - agent said "no errors" when logs had obvious ZeroDivisionError. Took 2 hours to debug!

---

## 2.9 Next Steps

### Phase 3 Preview: Multi-Agent Orchestration

Now that the agent has "senses" (tools) and "memory" (ChromaDB), you'll build the "brain":

**What You'll Build**:
- Supervisor agent (router with Pydantic structured outputs)
- Log Expert agent (ReAct loop for log analysis)
- Infrastructure Expert agent (container health diagnosis)
- LangGraph state machine (orchestrates multi-agent workflow)
- Consultation budgets (prevents infinite loops)

**Key Concepts**:
- Supervisor-Worker pattern vs single agent
- LangGraph conditional routing
- Structured outputs (prevents hallucination)
- ReAct loops with circuit breakers

**Bridge to Phase 3**:
You now have tools for perception and memory for learning. In Phase 3, you'll orchestrate specialized agents that use these tools to investigate incidents autonomously.

**Recommended Next Action**:
Proceed to `LESSON_PHASE3.md` when ready to build the multi-agent system.

---

**End of Phase 2 Lesson**

✅ Tools implemented
✅ Memory system working
✅ LLM configured correctly
✅ Ready for Phase 3: Multi-Agent Orchestration
