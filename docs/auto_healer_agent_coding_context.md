# System Prompt & Coding Context for AI Agents

**Target Audience**: This document is for AI coding assistants (like Gemini/Copilot) assisting in the development of the Auto-Healer repository. When generating code for this project, adhere strictly to the following constraints and context.

## 1. Hardware & Environment Context
* **Target Hardware**: Apple Silicon Mac (M3 Pro, 36GB RAM).
* **Model Engine**: Ollama.
* **LLM Constraint**: `qwen2.5:14b`. Because local models can hallucinate tool inputs more easily than GPT-4, all tool code and Graph orchestration MUST incorporate aggressive error handling and structured outputs.

## 2. Strict Implementation Rules

### 2.1 The Context Window Rule (CRITICAL)
* When initializing `ChatOllama` via LangChain, you **MUST** set `num_ctx=16384` (or higher).
* *Reason*: The agent analyzes application tracebacks. The default 2048 token limit will truncate logs and cause silent reasoning failures.

### 2.2 Structured Outputs for Supervisor Routing
* The Supervisor node **MUST NEVER** output plain text.
* Use `pydantic.BaseModel` to define a strict API Contract for the Supervisor's decision.
* Use `llm.with_structured_output(SupervisorDecision)` to force the local model to only output routing commands (e.g., `{"next_worker": "log_expert", "reasoning": "..."}`).

### 2.3 Tool Design & Documentation
* LLMs rely entirely on Python docstrings to understand how to use tools. 
* Every `@tool` decorated function **MUST** have a comprehensive, highly descriptive docstring explaining *when* to use it and *what* each parameter means. Type hints are mandatory.

### 2.4 The Reflection / Self-Correction Pattern
* Do not allow the graph to crash on a `JSONDecodeError` or a Python Exception during tool execution.
* If a tool fails (e.g., missing parameter), catch the exception, format it as a `SystemMessage` or `ToolMessage`, and send it back to the active Agent Node with a prompt like: *"Tool execution failed with error: {error}. Please reflect on your parameters and try again."*

### 2.5 LangGraph Circuit Breakers
* Local models can get stuck in infinite loops (e.g., Supervisor calling Worker A, Worker A returning nothing, Supervisor calling Worker A again).
* When calling `app.invoke()` or `app.stream()`, **ALWAYS** provide a `config={"recursion_limit": 15}` to act as a circuit breaker.

### 2.6 State Management
* Define the global state (`AlertTeamState`) using `TypedDict` and `Annotated` with `operator.add` for messages. 
* Ensure the State can hold `historical_context` (for the RAG/ChromaDB memory layer) and the `alert_info`.

## 3. Tech Stack Requirements
* **Python**: 3.11+ (managed by `uv` or `poetry`).
* **Frameworks**: `langchain`, `langgraph`, `langchain-ollama`.
* **API/Mocking**: `fastapi`, `uvicorn`, `httpx`.
* **Database**: `chromadb` (pure Python mode).
* **Container Interaction**: `docker` (Python SDK for fetching logs without Elasticsearch).
