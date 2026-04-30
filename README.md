# Auto-Healer Agent

> A local, autonomous DevOps/SRE AI agent for automatic troubleshooting of microservice 5xx errors

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Auto-Healer Agent is an open-source AI system that autonomously troubleshoots and performs Root Cause Analysis (RCA) on microservice 5xx errors (500, 502, 504). Built on LangGraph with local execution using Ollama, it ensures complete data privacy with zero API costs.

**Key Features:**
- 🤖 Multi-agent collaboration (Supervisor-Worker pattern)
- 🧠 Long-term memory using RAG (ChromaDB)
- 🛠️ Tool use for Docker log analysis and container health checks
- 🔄 ReAct pattern for iterative reasoning
- 🔍 Self-correction and reflection capabilities
- 👤 Human-in-the-loop approval gates
- 🔒 100% local execution (no data leaves your machine)

## Architecture

```
Alert → Memory Recall → Supervisor → Workers (Log/Infra) → Supervisor Synthesis → HITL → Memory Commit
```

**Agents:**
- **Supervisor Agent**: Central router for task delegation
- **Log Expert Agent**: Analyzes application logs and stack traces
- **Infra Expert Agent**: Checks container health and infrastructure state

**Tech Stack:**
- LangGraph for workflow orchestration
- Ollama with qwen2.5:14b (local LLM)
- ChromaDB for vector memory storage
- FastAPI for dummy microservices
- Docker/Podman for containerization

## Quick Start

### Prerequisites

1. **Ollama** (for local LLM)
   ```bash
   # Install Ollama: https://ollama.ai
   ollama pull qwen2.5:14b
   ollama serve
   ```

2. **Podman or Docker**
   ```bash
   # macOS: brew install podman
   # Linux: see https://podman.io/getting-started/installation
   ```

3. **Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/auto-healer-agent.git
cd auto-healer-agent

# Install dependencies (using uv)
uv pip install -e .

# Or with pip
pip install -e .
```

### Running the Agent

1. **Start the dummy microservices**
   ```bash
   podman-compose up -d --build
   # Or with docker: docker-compose up -d --build
   ```

2. **Verify services are running**
   ```bash
   podman-compose ps
   curl http://localhost:8001/health
   ```

3. **Run the agent with a sample alert**
   ```bash
   python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json
   ```

### Testing Chaos Scenarios

Trigger different error types for testing:

```bash
# 500 Internal Server Error (ZeroDivisionError)
curl 'http://localhost:8001/order?chaos_type=500_zerodivision'

# 502 Bad Gateway (upstream failure)
curl 'http://localhost:8001/order?chaos_type=502_bad_gateway'

# 504 Gateway Timeout (long-running request)
curl 'http://localhost:8001/order?chaos_type=504_gateway_timeout'
```

View logs to see the generated errors:
```bash
podman logs order-service
```

## Project Structure

```
auto-healer-agent/
├── auto_healer/           # Main agent package
│   ├── nodes/             # LangGraph agent nodes
│   │   ├── supervisor.py
│   │   ├── log_expert.py
│   │   └── infra_expert.py
│   ├── tools/             # Agent tools
│   │   └── docker_tools.py
│   ├── state.py           # Global state definition
│   ├── graph.py           # LangGraph orchestration
│   ├── memory.py          # ChromaDB integration
│   └── main.py            # Entry point
│
├── dummy_services/        # Mock microservices for testing
│   ├── order/
│   ├── payment/
│   └── inventory/
│
├── examples/              # Sample alerts and data
│   └── alerts/
│
├── docs/                  # Documentation
│   ├── BLUEPRINT.md
│   ├── ARCHITECTURE.md
│   └── TESTING.md
│
└── tests/                 # Unit tests
```

## Agentic Design Patterns

This project implements several advanced patterns from *"Agentic Design Patterns"*:

1. **Multi-Agent Collaboration**: Supervisor-Worker topology with specialized agents
2. **Tool Use / Function Calling**: Docker SDK for log fetching and health checks
3. **ReAct (Reason + Act)**: Iterative thinking and tool usage
4. **Long-Term Memory (RAG)**: ChromaDB for incident history recall
5. **Reflection / Self-Correction**: Error handling and LLM self-repair
6. **Human-in-the-Loop**: Approval gates before committing RCA reports

## Development

### Running Tests

```bash
# Unit tests
pytest tests/

# Type checking
mypy auto_healer/

# Linting
ruff check auto_healer/
```

### Development Workflow

See [docs/BLUEPRINT.md](docs/BLUEPRINT.md) for the complete development plan and milestones.

## Documentation

- [AGENT.md](AGENT.md) - AI coding assistant guidelines
- [docs/BLUEPRINT.md](docs/BLUEPRINT.md) - Project execution plan
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Architecture decisions and rationale
- [docs/AGENT_SPEC.md](docs/AGENT_SPEC.md) - Agent personas and specifications
- [docs/TESTING.md](docs/TESTING.md) - Infrastructure testing results

## Hardware Requirements

- **Recommended**: Apple Silicon M3 Pro (36GB RAM)
- **Minimum**: 16GB RAM, 20GB free disk space
- **LLM Model**: qwen2.5:14b (~9GB model size, 16K context window)

## Why Local?

**Data Privacy**: Application logs often contain sensitive PII or proprietary business logic. Running locally ensures no data leaves your machine.

**Cost**: Zero API costs during development and heavy ReAct loop testing.

**Performance**: Apple Silicon's unified memory allows the entire model and KV cache to reside in VRAM, eliminating inference bottlenecks.

## Contributing

This is a learning project demonstrating agentic design patterns. Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by *"Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems"* by Antonio Gulli
- Built with LangChain/LangGraph
- Local LLM powered by Ollama

## Status

🚧 **Work in Progress** 🚧

- ✅ Phase 1: Infrastructure & Chaos Mock - Complete
- ✅ Phase 2: Perception, Tools & Memory Layer - Complete
- ⏳ Phase 3: Core Orchestration (LangGraph) - In Progress
- ⏳ Phase 4: Integration & HITL - Pending
- ⏳ Phase 5: Polish & Documentation - Pending
