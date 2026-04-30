# Auto-Healer Agent Specifications (AGENT.md)

This document serves as the central registry and specification for the AI agents operating within the Auto-Healer system. It defines the multi-agent topology, individual personas, tool access, and state management mechanisms.

## 1. Multi-Agent Topology
The system utilizes a **Supervisor-Worker** topology built on LangGraph.
* **Central Control**: The Supervisor agent receives the initial alert and makes routing decisions based on context.
* **Decoupled Execution**: Worker agents (Log Expert, Infra Expert) perform specialized tasks in isolation and report back to the Supervisor.
* **State Machine**: All interactions are tracked in a shared global graph state (`AlertTeamState`).

## 2. Agent Personas & Responsibilities

### 2.1 The Supervisor Agent (`supervisor_node`)
* **Role**: Triage commander and routing engine.
* **LLM Configuration**: `qwen2.5:14b` with **Structured Outputs** forced via Pydantic.
* **System Prompt Focus**: "You are an elite SRE Incident Commander. You do not fix the issue yourself. Your job is to read the alert, evaluate the context, and route the task to the most appropriate specialist. You must output your decision strictly in the defined JSON format."
* **Allowed Actions**: Route to `log_expert`, route to `infra_expert`, or conclude with `FINISH`.

### 2.2 The Log Expert Agent (`log_expert_node`)
* **Role**: Application code and traceback analyzer.
* **LLM Configuration**: `qwen2.5:14b` with a 16K context window (`num_ctx=16384`) to handle massive log dumps.
* **System Prompt Focus**: "You are a Senior Backend Software Engineer. Your expertise is in reading Python and Java stack traces, identifying the exact line of failure, and explaining the code-level root cause of 500/504 errors."
* **Tools Granted**: `fetch_service_logs`.

### 2.3 The Infrastructure Expert Agent (`infra_expert_node`)
* **Role**: Container and network diagnostician.
* **LLM Configuration**: `qwen2.5:14b`.
* **System Prompt Focus**: "You are a DevOps and Kubernetes Specialist. Your expertise lies in diagnosing OOM kills, network partitions, gateway timeouts, and container health states."
* **Tools Granted**: `check_container_health`.

## 3. Tool Registry

All tools must provide extensive docstrings and type hints to ensure reliable function calling by the local LLM.

| Tool Name | Assigned Agent | Description | Under the Hood |
| :--- | :--- | :--- | :--- |
| `fetch_service_logs` | Log Expert | Fetches the last N lines of stdout/stderr for a given service. | Uses Docker Python SDK (`docker.logs`). |
| `check_container_health`| Infra Expert | Checks if a container is running, exited, or restarting. | Uses Docker Python SDK (`docker.containers.get`). |
| `query_past_incidents` | (Pre-Graph Node)| Searches vector DB for similar past 5xx errors to provide context. | Uses ChromaDB semantic search. |
| `save_resolved_incident`| (Post-Graph Node)| Commits the finalized RCA report into long-term memory. | Uses ChromaDB document insertion. |

## 4. State & Memory Definitions

### 4.1 Global Graph State (`AlertTeamState`)
The LangGraph state object passed between all nodes:
```python
class AlertTeamState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    alert_info: dict            # Parsed JSON webhook payload
    historical_context: str     # RAG context injected from ChromaDB
    next_worker: str            # Routing pointer set by Supervisor
```

### 4.2 Long-Term Memory (LTM) Architecture
* **Engine**: ChromaDB (Local SQLite-based persistence).
* **Embedding Model**: Run locally via Ollama (e.g., `nomic-embed-text` or `bge-m3`).
* **Trigger Condition**: Memory is only committed *after* the Human-in-the-Loop (HITL) node approves the final Root Cause Analysis (RCA).

## 5. Execution Flow (The ReAct Loop)
1.  **Awaken**: Webhook hits FastAPI, generating `alert_info`.
2.  **Recall**: Query ChromaDB for `historical_context`.
3.  **Triage**: Supervisor evaluates `alert_info` + `historical_context` -> calls Worker.
4.  **Investigate**: Worker uses Tools -> parses output -> generates localized summary.
5.  **Synthesize**: Supervisor reads Worker summary -> decides to call another Worker or `FINISH`.
6.  **Approve**: Graph pauses. Human user approves RCA via terminal `y/n`.
7.  **Commit**: Save RCA to ChromaDB. End.
