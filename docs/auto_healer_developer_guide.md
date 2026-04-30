# Auto-Healer Agent: Developer Architecture & Rationale Guide

## 1. Project Purpose & Vision
The Auto-Healer Agent is an open-source, locally run AI system designed to autonomously troubleshoot microservice 5xx errors (500, 502, 504). For developers, this project serves two main goals:
1. **Practical Application**: Solve the real-world pain point of waking up to P0 alerts by automating initial log fetching and root cause analysis (RCA).
2. **Learning from Practice**: Serve as a tangible implementation of concepts from *"Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems" by Antonio Gulli*.

## 2. Key Architectural Choices & Rationale

### 2.1 Domain Choice: SRE / DevOps Troubleshooting
* **Why**: As backend engineers transitioning to AI, we possess deep domain knowledge in system architecture and debugging. This allows us to write highly effective System Prompts and design precise Tools (e.g., log fetchers, health probes), which are the foundation of a successful agent.
* **MVP Scope**: Focused strictly on API 5xx errors. 5xx errors have deterministic debugging paths (Gateway -> App Logs -> Upstream Status), making it the perfect testbed for Agent workflows.

### 2.2 LLM Engine: Local Ollama vs. Cloud API (GPT-4o)
* **Choice**: Local Ollama running `qwen2.5:14b` on an Apple M3 Pro (36GB Unified Memory).
* **Why**: 
  * **Data Privacy**: Application logs often contain sensitive PII or proprietary business logic. Sending them to public cloud APIs during incident response is a security risk.
  * **Hardware Match**: The Mac M3 Pro's 36GB unified memory allows the entire 14B parameter model and a massive KV cache to reside in VRAM, eliminating inference bottlenecks.
  * **Cost**: Zero API costs during heavy ReAct loop testing.

### 2.3 Orchestration Pattern: Multi-Agent Supervisor-Worker
* **Choice**: A LangGraph-based central Supervisor Agent routing tasks to Specialized Workers (Log Analyst, Infra Analyst).
* **Why not Single Agent?**: A single agent given all tools suffers from "Prompt Bloat" and tool hallucination.
* **Why not Sequential Pipeline?**: Supervisor pattern acts like an API Gateway. It prevents infinite loops by keeping control at the center and makes adding new agents (e.g., a DBA agent) trivial without rewriting existing agent flows.

### 2.4 Memory Layer: ChromaDB
* **Choice**: ChromaDB running locally via Python package.
* **Why**: To implement Long-Term Memory (RAG). It allows the agent to recall past resolved incidents to avoid repeating debugging mistakes. We chose ChromaDB over PGVector to keep the repo lightweight and "out-of-the-box" friendly for open-source users (no heavy DB containers required).

### 2.5 Testing Environment: Dummy Microservices with Chaos Injection
* **Choice**: FastAPI + Docker Compose.
* **Why**: Instead of mocking logs purely in memory, we build a real (but miniature) microservice topology (Order -> Payment/Inventory). We inject chaos via API endpoints (e.g., `?chaos_type=504_gateway_timeout`). This provides a real "target range" for the Agent to fetch logs via the Docker SDK, proving its real-world viability.

---
## 3. Project Roadmap (Summary)
* **Phase 1**: Infrastructure (Dummy services, Docker compose, Chaos endpoints).
* **Phase 2**: Tooling & Perception (Docker SDK log fetcher, ChromaDB setup).
* **Phase 3**: Orchestration (LangGraph Supervisor, ReAct Workers).
* **Phase 4**: Human-in-the-Loop & E2E Testing.
* **Phase 5**: Open Source Polish (Rich CLI, Docs, Type hinting).
