# AI Coding Assistant Guidelines (AGENT.md)

## 1. Project Context
This is `auto-healer-agent`, an autonomous SRE/DevOps troubleshooting agent. It uses a LangGraph-based Multi-Agent Supervisor architecture to analyze microservice 5xx errors. The target environment is entirely local (Apple Silicon M3 Pro, 36GB RAM).

**Your Role**: Act as a Senior AI Application Architect and Senior Backend Engineer. Write production-grade, highly robust Python code.

## 2. Tech Stack
- **Language**: Python 3.11+
- **Agent Framework**: `langgraph`, `langchain-core`
- **LLM Integration**: `langchain-ollama` (Strictly local models)
- **API/Mock Target**: `fastapi`, `uvicorn`, `httpx`
- **Vector DB**: `chromadb` (pure Python/SQLite mode)
- **Container SDK**: `docker` (Python SDK)
- **Dependency Management**: `uv` (or `poetry`)

## 3. Strict Coding Rules

### 3.1 LLM & LangGraph Constraints
- **Model**: Default to `qwen2.5:14b` via Ollama.
- **Context Window**: YOU MUST initialize `ChatOllama` with `num_ctx=16384` to handle massive log dumps. Do not use the default context size.
- **Structured Outputs**: The Supervisor Node MUST use `llm.with_structured_output(pydantic_model)` to enforce routing decisions. Do not let the Supervisor output plain text.
- **Circuit Breakers**: Always include `config={"recursion_limit": 15}` (or similar limits) when invoking or streaming a LangGraph app to prevent infinite loops.
- **Reflection**: If a `@tool` function might fail (e.g., JSON parse error, missing kwargs), write a LangGraph node to catch the error and feed it back to the LLM for self-correction. Do not let the graph crash.

### 3.2 Tool Definition (Function Calling)
- Every `@tool` MUST have a comprehensive docstring and PEP 484 type hints. 
- The LLM relies 100% on docstrings to format inputs. Document *what* the tool does, *when* to use it, and *what* each argument means.

### 3.3 Code Style & Formatting
- Use explicit type hints (`str`, `dict`, `List[str]`, `TypedDict`, `Annotated`) everywhere.
- Use `logging` or `rich` for console outputs. Avoid raw `print()` for production logic.
- Keep FastAPI endpoints async (`async def`). 
- When interacting with the Docker SDK, ensure graceful fallback if the Docker daemon is unreachable.

## 4. Development Commands
- **Run Mock Infrastructure**: `docker-compose up -d` (starts Order, Payment, and Inventory dummy services).
- **Run Agent Entrypoint**: `python -m agent.main` (or similar entrypoint).

## 5. File Structure Mental Model
- `/dummy_services`: The "target range" (FastAPI apps with chaos injection).
- `/agent/state.py`: Defines the `AlertTeamState` (Graph State).
- `/agent/tools.py`: Docker SDK log fetchers and container probes.
- `/agent/graph.py`: The LangGraph orchestration (Supervisor, Workers, Conditional Edges).
- `/agent/memory.py`: ChromaDB RAG implementation for long-term memory.