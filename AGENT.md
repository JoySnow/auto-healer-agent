# AI Coding Assistant Guidelines (AGENT.md)

This file provides guidance to AI coding assistants (Claude Code, Cursor, Copilot, etc.) when working with code in this repository.

## 1. Project Context

`auto-healer-agent` is a local, autonomous DevOps/SRE AI system that automatically troubleshoots and performs Root Cause Analysis (RCA) on microservice 5xx errors (500, 502, 504). The project demonstrates advanced agentic design patterns while maintaining complete data privacy through local execution.

**Your Role**: Act as a Senior AI Application Architect and Senior Backend Engineer. Write production-grade, highly robust Python code.

**Key Goals:**
- Automate initial troubleshooting of production incidents
- Implement multi-agent collaboration patterns using LangGraph
- Run entirely locally with zero API costs and no data privacy concerns

## 2. Architecture

### Multi-Agent System Design

The system uses a **Supervisor-Worker** pattern orchestrated by LangGraph:

1. **Supervisor Agent**: Central router that analyzes alerts and delegates to specialized workers
2. **Log Expert Agent**: Analyzes application logs and stack traces
3. **Infra Expert Agent**: Checks container health, resource limits, and infrastructure state
4. **Memory Layer**: ChromaDB for RAG-based recall of past incidents

**Workflow Graph:**
```
Alert → Memory Recall → Supervisor → Workers (Log/Infra) → Supervisor Synthesis → HITL → Memory Commit
```

### Applied Agentic Patterns

1. **Multi-Agent Collaboration**: Supervisor-Worker with specialized agents
2. **Tool Use / Function Calling**: Docker SDK, health checks, log fetchers
3. **ReAct (Reason + Act)**: Iterative thinking and tool usage
4. **Long-Term Memory (RAG)**: ChromaDB for incident history
5. **Reflection / Self-Correction**: Error handling and LLM self-repair
6. **Human-in-the-Loop**: Approval gates before committing RCA reports

## 3. Tech Stack & Hardware Constraints

- **Target Hardware**: Apple Silicon (M3 Pro + 36GB Unified Memory)
- **Language**: Python 3.11+
- **LLM Engine**: Ollama running locally with `qwen2.5:14b` model (~9GB RAM)
- **Agent Framework**: `langgraph`, `langchain-core`, `langchain-ollama` (strictly local models)
- **Mock Infrastructure**: `fastapi`, `uvicorn`, `httpx`
- **Vector DB**: `chromadb` (pure Python/SQLite mode)
- **Container SDK**: `docker` (Python SDK for log fetching)
- **Dependency Management**: `uv` (or `poetry`)

**Key Dependencies:**
- `langchain` + `langgraph` + `langchain-ollama`: Agent framework
- `fastapi` + `uvicorn`: Mock services
- `chromadb`: Local vector database
- `docker`: Python SDK for container log fetching
- `pydantic`: Structured outputs and validation
- `httpx`: Async HTTP client for service calls
- `rich`: Terminal UI for execution logs

## 4. Critical Implementation Rules

### 4.1 Context Window Configuration (CRITICAL)

When initializing `ChatOllama`, **MUST** set `num_ctx=16384` minimum:
```python
llm = ChatOllama(model="qwen2.5:14b", num_ctx=16384)
```
**Why**: Default 2048 tokens will truncate application logs and cause silent reasoning failures. The agent analyzes massive stack traces and log dumps.

### 4.2 Structured Outputs for Supervisor Routing

The Supervisor node **MUST NEVER** output plain text. Always use Pydantic models:
```python
class SupervisorDecision(BaseModel):
    next_worker: str
    reasoning: str

llm.with_structured_output(SupervisorDecision)
```
**Why**: Local models like qwen2.5:14b are prone to hallucinating tool inputs. Structured outputs enforce strict API contracts for routing decisions.

### 4.3 Circuit Breakers

Local models can loop infinitely. Always provide recursion limits:
```python
app.invoke(state, config={"recursion_limit": 15})
```
**Why**: Prevents infinite loops where Supervisor calls Worker A, Worker A returns nothing, Supervisor calls Worker A again indefinitely.

### 4.4 Error Handling & Reflection

- Never allow graph crashes on `JSONDecodeError` or tool exceptions
- Catch errors, format as `SystemMessage` or `ToolMessage`
- Return to agent with prompt: "Tool execution failed with error: {error}. Reflect on your parameters and retry."

**Why**: Local models can make parameter mistakes. The Reflection pattern allows the LLM to self-correct rather than crashing the entire graph.

### 4.5 Tool Definition (Function Calling)

Every `@tool` function **MUST** have:
1. Comprehensive docstring explaining:
   - When to use the tool
   - What each parameter means
   - Expected return format
2. PEP 484 type hints for all parameters and return values

**Why**: The LLM relies 100% on docstrings to understand how to format tool inputs. Poor documentation leads to tool hallucination.

### 4.6 State Management

Global state (`AlertTeamState`) must include:
- `messages`: Annotated with `operator.add` for message accumulation
- `historical_context`: For RAG/ChromaDB memory layer
- `alert_info`: Current incident details

Example:
```python
from typing import TypedDict, Annotated
import operator

class AlertTeamState(TypedDict):
    messages: Annotated[list, operator.add]
    alert_info: dict
    historical_context: str
```

### 4.7 Code Style & Formatting

- Use explicit type hints (`str`, `dict`, `List[str]`, `TypedDict`, `Annotated`) everywhere
- Use `logging` or `rich` for console outputs. Avoid raw `print()` for production logic
- Keep FastAPI endpoints async (`async def`)
- When interacting with the Docker SDK, ensure graceful fallback if the Docker daemon is unreachable

## 5. Development Commands

### Testing Infrastructure
```bash
# Start mock microservices with chaos endpoints
docker-compose up -d

# Trigger chaos scenarios for testing
curl "http://localhost:8001/order?chaos_type=500_zerodivision"
curl "http://localhost:8001/order?chaos_type=504_gateway_timeout"
curl "http://localhost:8001/order?chaos_type=502_bad_gateway"
```

### Running the Agent
```bash
# Start Ollama (ensure qwen2.5:14b is pulled)
ollama serve

# Pull the model if not already available
ollama pull qwen2.5:14b

# Run agent with sample alert
python -m auto_healer.main --alert alert.json
```

### Development Workflow
```bash
# Install dependencies (when using uv)
uv pip install -e .

# Type checking
mypy auto_healer/

# Run tests
pytest tests/
```

## 6. File Structure Mental Model

- `/dummy_services/`: The "target range" (FastAPI apps with chaos injection endpoints)
- `/agent/state.py`: Defines the `AlertTeamState` (LangGraph global state)
- `/agent/tools.py`: Docker SDK log fetchers and container health probes
- `/agent/graph.py`: The LangGraph orchestration (Supervisor, Workers, Conditional Edges)
- `/agent/memory.py`: ChromaDB RAG implementation for long-term incident memory
- `/agent/nodes/`: Individual agent nodes (Supervisor, Log Expert, Infra Expert)

## 7. Documentation Structure

The project has comprehensive documentation organized by purpose:

### Core Documentation (`/docs/`)
- **ARCHITECTURE.md**: Architectural decisions and design rationale
- **AGENT_SPEC.md**: Agent personas and system prompts
- **BLUEPRINT.md**: Project execution plan and milestones

### Development Documentation (`/docs/development/`)
- **PROGRESS.md**: Development progress tracking
- **SUPERVISOR_IMPROVEMENTS.md**: Supervisor agent enhancements

### Testing Documentation (`/docs/testing/`)
- **TESTING.md**: Infrastructure testing results
- **PHASE4_RESULTS.md**: Phase 4 integration test results
- **PHASE4_502_TEST.md**: Specific 502 error test case

### Educational Tutorials (`/tutorials/`)
- **README.md**: Complete learning path overview (16-24 hours)
- **LESSON_PHASE1.md**: Phase 1 - Infrastructure & Testing Environment
- **LESSON_PHASE2.md**: Phase 2 - Perception, Tools & Memory
- **LESSON_PHASE3.md**: Phase 3 - Multi-Agent Orchestration
- **LESSON_PHASE4.md**: Phase 4 - Integration Testing & HITL
- **LESSON_PHASE5.md**: Phase 5 - Production Polish
- **SUMMARY.md**: Key architectural decisions & trade-offs

**When to reference tutorials**:
- User asks "how was this built?" → Point to `/tutorials/README.md`
- User asks about specific pattern → Reference relevant lesson phase
- User asks about design decisions → Reference `/tutorials/SUMMARY.md`

## 8. Project Development Phases

- **Phase 1**: Infrastructure (dummy microservices, chaos injection, Docker setup)
- **Phase 2**: Tools & Memory (Docker SDK log fetcher, ChromaDB initialization)
- **Phase 3**: Core Orchestration (Worker nodes with ReAct, Supervisor with routing)
- **Phase 4**: Integration (HITL gates, end-to-end testing)
- **Phase 5**: Polish (Rich CLI, documentation, type hints)

**Status**: All phases complete ✅

## 9. Security & Privacy

All execution is local. Application logs (which may contain PII or proprietary business logic) never leave the local machine. This is a core design constraint - **do not introduce cloud API dependencies** for the agent's core reasoning or memory storage.
