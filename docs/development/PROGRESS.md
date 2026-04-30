# Auto-Healer Agent - Development Progress

## Project Status: ALL PHASES COMPLETE ✅

**Total Code**: ~2,000 lines of Python
**Last Updated**: 2026-04-30
**Production Ready**: Yes 🚀

---

## ✅ Phase 1: Infrastructure & Chaos Mock (COMPLETE)

**Goal**: Build a realistic testing environment with dummy microservices that can simulate 5xx errors.

### Completed:
- ✅ **Project Initialization**
  - Created directory structure
  - Configured `pyproject.toml` with all dependencies
  - Set up Python 3.12 environment

- ✅ **Dummy Microservices** (3 FastAPI services)
  - Order Service (port 8001) - orchestrates payment and inventory
  - Payment Service (port 8002) - processes payments
  - Inventory Service (port 8003) - checks stock availability
  - All services with health checks and structured JSON logging

- ✅ **Chaos Injection** (3 error scenarios)
  - `500_zerodivision`: Triggers ZeroDivisionError with traceback
  - `502_bad_gateway`: Simulates upstream service failure
  - `504_gateway_timeout`: 60-second sleep causing timeout

- ✅ **Container Orchestration**
  - Dockerfiles for all services (Python 3.12-slim)
  - `docker-compose.yml` with service dependencies
  - Successfully tested with podman-compose
  - All services running and responding to chaos endpoints

### Verification:
```bash
✓ All 3 containers running
✓ Health checks passing
✓ Normal order flow working (service-to-service communication)
✓ All chaos scenarios generating expected errors
✓ Structured JSON logs for agent parsing
```

---

## ✅ Phase 2: Perception, Tools & Memory Layer (COMPLETE)

**Goal**: Build the agent's sensory and memory systems.

### Completed:
- ✅ **LangGraph Global State** (`state.py`)
  - Defined `AlertTeamState` TypedDict
  - Fields: messages, alert_info, historical_context, next_worker

- ✅ **Docker Tools** (`tools/docker_tools.py`)
  - `fetch_service_logs()`: Retrieve container logs via Docker SDK
  - `check_container_health()`: Inspect container state and resources
  - Comprehensive docstrings (LLM depends 100% on these)
  - Graceful error handling with reflection pattern
  - Podman compatibility notes

- ✅ **ChromaDB Memory Layer** (`memory.py`)
  - `initialize_chromadb()`: Setup persistent vector database
  - `query_past_incidents()`: Semantic search for similar errors (RAG)
  - `save_incident()`: Store human-approved RCA reports
  - Local persistence in `.chromadb/` directory

- ✅ **LLM Configuration** (`llm_config.py`)
  - `get_llm()`: Initialize ChatOllama with qwen2.5:14b
  - **CRITICAL**: Enforces `num_ctx=16384` minimum
  - Safety checks prevent context window truncation
  - Model recommendations for different use cases

### Verification:
```python
✓ Tools have comprehensive docstrings
✓ Error handling returns messages (no crashes)
✓ Memory initialized successfully
✓ LLM config enforces 16K context window
```

---

## ✅ Phase 3: Core Orchestration (LangGraph) (COMPLETE)

**Goal**: Build the multi-agent graph with Supervisor-Worker pattern.

### Completed:

#### 🤖 Agent Nodes:

1. **Supervisor Agent** (`nodes/supervisor.py`)
   - Central router using Pydantic `SupervisorDecision` model
   - **Structured outputs prevent LLM hallucination**
   - Routes to: `log_expert`, `infra_expert`, or `FINISH`
   - Considers historical context and agent reports
   - Fallback routing on errors

2. **Log Expert Agent** (`nodes/log_expert.py`)
   - Specializes in application logs and stack traces
   - Uses `fetch_service_logs` tool via ReAct loop
   - Identifies code-level root causes (500 errors)
   - System prompt: "Senior Backend Software Engineer"
   - Max 5 iterations with error reflection

3. **Infrastructure Expert Agent** (`nodes/infra_expert.py`)
   - Specializes in container health and resources
   - Uses `check_container_health` tool via ReAct loop
   - Identifies OOM kills, crashes, resource exhaustion
   - System prompt: "DevOps and Infrastructure Specialist"
   - Max 5 iterations with error reflection

4. **HITL & Memory Nodes** (`nodes/hitl.py`)
   - `memory_recall_node()`: Queries ChromaDB at graph entry
   - `human_approval_node()`: Pauses for approval with y/n/edit
   - `memory_commit_node()`: Saves approved RCA to ChromaDB
   - Full Human-in-the-Loop workflow

#### 🔗 Graph Wiring:

**Graph Orchestration** (`graph.py`):
```
Alert → Memory Recall → Supervisor → Workers (Log/Infra) → Supervisor → HITL → Memory Commit → END
```

Features:
- StateGraph with conditional routing
- `route_supervisor_decision()`: Routes based on next_worker
- `route_after_hitl()`: Handles approval/rejection
- Workers loop back to Supervisor for next decision
- MemorySaver checkpoint for state persistence
- Circuit breaker: `recursion_limit=15` default
- Optional Mermaid diagram visualization

#### 🚀 Main Entry Point:

**CLI Application** (`main.py`):
- Rich terminal UI with colored output
- Progress spinners during execution
- Formatted panels for alerts and results
- Arguments:
  - `--alert <path>`: Load alert JSON file
  - `--debug`: Enable debug logging
  - `--visualize-only`: Show graph structure
  - `--max-iterations <n>`: Set recursion limit
- Proper error handling and exit codes
- KeyboardInterrupt handling

### Architecture Highlights:

**Critical Implementation Patterns:**

1. **Structured Outputs** (Supervisor)
   ```python
   class SupervisorDecision(BaseModel):
       next_worker: Literal["log_expert", "infra_expert", "FINISH"]
       reasoning: str
   ```
   Prevents local LLM from hallucinating plain text

2. **ReAct Pattern** (Workers)
   ```python
   agent_executor = AgentExecutor(
       agent=agent,
       tools=tools,
       max_iterations=5,
       handle_parsing_errors=True  # Reflection!
   )
   ```

3. **Circuit Breaker** (Graph Execution)
   ```python
   graph.invoke(state, config={"recursion_limit": 15})
   ```

4. **Reflection on Errors**
   ```python
   except Exception as e:
       error_message = AIMessage(
           content=f"Error: {e}. Please reflect and retry."
       )
   ```

### Verification:
```
✓ All agent nodes implemented with comprehensive system prompts
✓ Graph wiring with conditional routing
✓ Circuit breakers configured
✓ Reflection pattern on tool errors
✓ HITL pause for human approval
✓ Memory integration at entry and exit
✓ Rich CLI with proper error handling
```

---

## ✅ Phase 4: Integration & Human-in-the-Loop (COMPLETE)

**Goal**: End-to-end testing and integration validation.

### Completed:

- ✅ **Integration Testing**
  - All Python dependencies installed and working
  - Ollama connectivity verified (qwen2.5:14b)
  - End-to-end testing with all error scenarios
  - Memory recall validated (similar incidents retrieved)
  - HITL approval/rejection flows tested
  - Agent trajectory verified (Supervisor → Workers → HITL)

- ✅ **Test Results**
  - 500 Error (ZeroDivisionError): Perfect RCA in 60s, 4 iterations
  - 502 Error (Bad Gateway): Clean FINISH in ~5min, 7 iterations
  - 504 Error (Timeout): Successfully diagnosed
  - Circuit breaker behavior validated
  - RCA reports coherent and actionable

- ✅ **Supervisor Improvements**
  - Agent consultation budgets (max 3 per agent)
  - Evidence plateau recognition
  - Budget overflow protection
  - Better FINISH criteria in system prompt

See [PHASE4_RESULTS.md](../testing/PHASE4_RESULTS.md) for detailed test results and metrics.

---

## ✅ Phase 5: Open Source Polish (COMPLETE)

**Goal**: Professional documentation and code quality.

### Completed:

- ✅ **Type Safety**
  - mypy strict mode with 0 errors
  - Comprehensive type hints across all modules
  - Generic type arguments (Dict[str, Any])
  - Strategic type: ignore comments for LangGraph compatibility
  - Fixed potential None indexing issues

- ✅ **Testing**
  - pytest unit tests (41 tests, all passing)
  - Tests for tool execution, state transitions, memory operations
  - Integration tests for graph routing
  - Mock Docker SDK and ChromaDB for isolated testing

- ✅ **Code Quality**
  - ruff formatter and linter configured
  - Pre-commit hooks enforcing quality checks
  - Consistent code style across project
  - Auto-formatting on every commit

- ✅ **Documentation**
  - Comprehensive README with badges
  - Mermaid diagrams for architecture
  - Detailed ARCHITECTURE.md
  - Educational lesson series (5 phases planned)
  - API documentation with docstrings

- ✅ **Terminal UI**
  - Rich library integration
  - Colored output and panels
  - Progress spinners
  - Professional user experience

---

## Project Statistics

| Metric | Value |
|--------|-------|
| **Total Lines of Code** | ~2,000 |
| **Python Modules** | 13 |
| **Agent Nodes** | 6 (Supervisor, Log Expert, Infra Expert, HITL, Memory×2) |
| **Tools** | 2 (fetch_service_logs, check_container_health) |
| **Dummy Services** | 3 (Order, Payment, Inventory) |
| **Chaos Scenarios** | 3 (500, 502, 504) |
| **Dependencies** | 12 core packages |
| **Unit Tests** | 41 (all passing) |
| **Type Safety** | mypy strict mode (0 errors) |
| **Code Quality** | ruff + pre-commit hooks |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     AUTO-HEALER AGENT                        │
│                                                              │
│  Alert → Memory Recall → Supervisor → Workers → HITL → Save │
│                                                              │
│  ┌──────────────┐     ┌────────────┐    ┌─────────────┐   │
│  │  Supervisor  │────▶│ Log Expert │    │   Memory    │   │
│  │   (Router)   │     └────────────┘    │  (ChromaDB) │   │
│  └──────────────┘            │          └─────────────┘   │
│         │                    ▼                              │
│         │            ┌────────────┐                         │
│         └───────────▶│Infra Expert│                         │
│                      └────────────┘                         │
│                                                              │
│  Agentic Patterns:                                          │
│  • Multi-Agent Collaboration (Supervisor-Worker)            │
│  • Tool Use / Function Calling (Docker SDK)                 │
│  • ReAct (Reason + Act iterative loops)                     │
│  • Long-Term Memory (RAG with ChromaDB)                     │
│  • Reflection / Self-Correction (error feedback)            │
│  • Human-in-the-Loop (approval gates)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Getting Started

All phases are complete! The project is production-ready. To run the auto-healer agent:

1. **Install dependencies**:
   ```bash
   uv pip install -e .
   ```

2. **Start Ollama**:
   ```bash
   ollama serve
   ollama pull qwen2.5:14b
   ```

3. **Start services**:
   ```bash
   podman-compose up -d --build
   ```

4. **Run an investigation**:
   ```bash
   # Example: Diagnose a 500 error
   python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json

   # Visualize the workflow graph
   python -m auto_healer.main --visualize-only

   # Run with debug logging
   python -m auto_healer.main --alert examples/alerts/alert_502_bad_gateway.json --debug
   ```

5. **Development workflow**:
   ```bash
   # Run tests
   pytest tests/

   # Type checking
   mypy auto_healer/

   # Code formatting
   ruff format auto_healer/
   ruff check auto_healer/
   ```

---

## Known Limitations

1. **Docker SDK Compatibility**: Requires `DOCKER_HOST` env var for podman
2. **Local LLM Only**: No cloud API fallback (by design for privacy)
3. **Simple Memory**: ChromaDB uses default embeddings (can upgrade to Ollama embeddings)
4. **Single Iteration HITL**: Revision requests end graph (need to re-run)
5. **No Async**: Graph execution is synchronous (OK for MVP)

---

## Contributing

See [BLUEPRINT.md](../BLUEPRINT.md) for the complete development plan.

For questions or issues: Check the implementation plan in `.claude/plans/`
