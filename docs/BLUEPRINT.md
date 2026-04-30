# Auto-Healer Agent: Project Blueprint & Execution Plan

## 1. Project Overview
**Concept**: A local, autonomous DevOps/SRE AI Agent designed to automatically troubleshoot and perform Root Cause Analysis (RCA) on microservice 5xx errors (500, 502, 504).
**Target Audience**: Backend Engineers, SREs, and developers learning Agentic Design Patterns.
**Deployment**: Pure local execution for data privacy and zero API costs, packaged as an open-source GitHub repository.

## 2. Tech Stack & Hardware
* **Hardware Target**: Apple Silicon (M3 Pro + 36GB Unified Memory).
* **LLM Engine**: Ollama running locally.
* **Primary Model**: `qwen2.5:14b` (High coding/tool-calling capability, ~9GB RAM, leaving space for 16K context window).
* **Agent Framework**: LangGraph (Graph-based state machine orchestration).
* **Mock Infrastructure**: FastAPI + Docker Compose (Dummy microservices with chaos injection).
* **Memory Layer**: ChromaDB (Local vector database).

## 3. Applied Agentic Design Patterns
This project implements several advanced patterns from *Agentic Design Patterns*:
1.  **Multi-Agent Collaboration (Supervisor-Worker)**: A central Supervisor Agent routes tasks to specialized Worker Agents (Log Expert, Infra Expert).
2.  **Tool Use / Function Calling**: Agents use tools like `fetch_service_logs` (Docker SDK) and `check_container_health`.
3.  **ReAct (Reason + Act)**: Workers iteratively think and use tools to gather localized information.
4.  **Long-Term Memory (RAG)**: Uses ChromaDB to recall past incidents before debugging and commits new RCA reports after successful resolution.
5.  **Reflection / Self-Correction**: Captures Python/JSON parsing errors during tool calls and forces the LLM to fix its own formatting.
6.  **Human-in-the-Loop (HITL)**: Requires human approval before finalizing the RCA or saving it to long-term memory.

## 4. Multi-Agent Workflow (The Graph)
1.  **Alert Received**: Supervisor Agent receives 5xx JSON alert.
2.  **Memory Recall Node**: Queries ChromaDB for historical solutions to similar alerts.
3.  **Supervisor Node**: Analyzes context and uses **Structured Outputs** to route the task to:
    * `Log Expert Agent`: Checks application logs (e.g., Python tracebacks).
    * `Infra Expert Agent`: Checks infrastructure state (e.g., Container OOM, network status).
4.  **Worker Nodes**: Execute specific tools and report summaries back to the Supervisor.
5.  **Supervisor Synthesis**: Compiles a comprehensive RCA report.
6.  **HITL Node**: Pauses execution to ask the user to approve the report.
7.  **Memory Commit Node**: Embeds and saves the approved RCA to ChromaDB.

---

## 5. Execution Plan (Milestones)

### Phase 1: Infrastructure & Chaos Mock (The Target Environment) ✅
* [x] 1.1 Project Initialization (uv/poetry, standard directory structure).
* [x] 1.2 Build Dummy Services (FastAPI: Order, Payment, Inventory).
* [x] 1.3 Inject Chaos Endpoints (Simulate 500 ZeroDivision, 504 Timeout, 502 Bad Gateway).
* [x] 1.4 Container Orchestration (Dockerfile & `docker-compose.yml` for 1-click spin-up).

### Phase 2: Perception, Tools & Memory Layer ✅
* [x] 2.1 Define LangGraph Global State (`AlertTeamState`).
* [x] 2.2 Implement Tools (Docker SDK logs fetcher, Health check API).
* [x] 2.3 Setup Memory Layer (ChromaDB initialization, implement Recall/Commit functions).
* [x] 2.4 Local LLM Binding (Configure `qwen2.5:14b` via `langchain_ollama` with 16K context).

### Phase 3: Core Orchestration (LangGraph) ✅
* [x] 3.1 Build Worker Nodes (Log Expert & Infra Expert with internal ReAct loops).
* [x] 3.2 Build Supervisor Node (Strict JSON routing via Pydantic Structured Output).
* [x] 3.3 Wire the Graph (Add conditional edges, compile with recursion limits/circuit breakers).
* [x] 3.4 Implement Reflection (Error handling nodes for tool execution failures).

### Phase 4: Integration & Human-in-the-Loop ✅
* [x] 4.1 Mock Webhook Trigger (Entry point script for the Graph).
* [x] 4.2 Add HITL Node (Terminal `y/n` input intercept before memory commit).
* [x] 4.3 End-to-End Testing (Fire 500, 502, 504 chaos endpoints and verify Agent trajectories).

### Phase 5: Open Source Polish ✅
* [x] 5.1 Terminal UI Beautification (Use `rich` library for hacker-style execution logs).
* [x] 5.2 Documentation (Mermaid diagrams for LangGraph, detailed README).
* [x] 5.3 Code Quality (mypy strict type hints, pytest setup with 41 passing tests, ruff formatting, pre-commit hooks).
