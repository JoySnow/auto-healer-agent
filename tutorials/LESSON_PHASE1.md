# Phase 1 Lesson: Infrastructure & Testing Environment

## 1.1 Overview

**What You'll Build**: Three FastAPI microservices (order, payment, inventory) with chaos injection endpoints, containerized with Docker.

**Why It Matters**:
- Agents need realistic targets to demonstrate value (can't hallucinate Docker SDK responses)
- Controllable chaos injection enables deterministic testing
- Proves agent can work with real-world containers, not just mocks

**Learning Objectives**:
- Understand why dummy services beat mocking for agent testing
- Learn chaos engineering basics for agent validation
- Master Docker containerization for reproducible environments
- Build FastAPI services with structured logging

**Time to Complete**: 2-3 hours for first-time learners

---

## 1.2 Prerequisites

Before starting this lesson, you should have:

- **Python 3.12+** installed (`python --version`)
- **Docker or Podman** installed and running
- **uv** package manager installed (`pip install uv`)
- Basic FastAPI knowledge (async/await, route handlers)
- Understanding of HTTP status codes (500, 502, 504)
- Basic Docker/containerization concepts

**Check your environment**:
```bash
python --version  # Should be 3.12+
docker --version  # or podman --version
uv --version      # Python package manager
```

---

## 1.3 Core Concepts

### Concept 1: Why Dummy Services Over Mocks?

**The Problem with Mocking**:
```python
# Anti-pattern: Mocking Docker SDK
@patch('docker.from_env')
def test_agent(mock_docker):
    mock_docker.return_value.containers.get.return_value.logs.return_value = b"Fake logs"
    # Problem: Agent never tests real Docker SDK interaction!
```

**Why This Fails**:
- Agent can't learn Docker SDK parameter names/types
- Missing real error scenarios (container not found, API errors)
- Can't validate JSON log parsing on real output
- No guarantee agent works in production

**Better Approach: Real Services**:
```python
# Real Docker container with chaos injection
response = requests.get("http://localhost:8001/order?chaos_type=500_zerodivision")
# → Triggers real 500 error with real Python traceback
# → Agent fetches real logs via Docker SDK
# → Agent parses real stack trace
```

**Benefits**:
- Tests end-to-end workflow (HTTP → Docker → Log Parsing → RCA)
- Validates tool calling with real Docker SDK
- Proves agent handles production-like scenarios
- Controllable via query parameters (deterministic testing)

### Concept 2: Chaos Injection Patterns

**Anti-Pattern: Random Chaos**
```python
# BAD: Non-deterministic testing
import random

@app.get("/order")
def create_order():
    if random.random() < 0.1:  # 10% chance
        raise Exception("Random failure")  # What kind? Who knows!
    return {"status": "success"}
```

**Problems**:
- Tests are flaky (sometimes pass, sometimes fail)
- Can't reproduce specific scenarios
- No control over error types
- Debugging is impossible

**Better: Controlled Chaos via Query Parameters**
```python
# GOOD: Deterministic, controllable chaos
@app.get("/order")
def create_order(chaos_type: Optional[str] = None):
    if chaos_type == "500_zerodivision":
        result = 1 / 0  # Specific error, reproducible
    elif chaos_type == "502_bad_gateway":
        raise HTTPException(502, "Upstream service down")
    elif chaos_type == "504_gateway_timeout":
        time.sleep(60)  # Simulate timeout

    # Normal path
    return {"order_id": str(uuid.uuid4()), "status": "success"}
```

**Benefits**:
- Reproducible: Same `chaos_type` = same error
- Targeted: Test specific agent capabilities per scenario
- Documented: Query parameters are self-documenting
- Easy to automate: `curl "http://localhost:8001/order?chaos_type=500_zerodivision"`

### Concept 3: Structured Logging for Agent Parsing

**Anti-Pattern: Print Statements**
```python
# BAD: Unstructured, hard to parse
@app.get("/order")
def create_order(order_id: str):
    print(f"Order received: {order_id}")  # Not JSON, no timestamp
    print("Processing...")  # Vague, no context
    return {"status": "success"}
```

**Problems**:
- Agent can't extract structured data (order ID, timestamp)
- Mixing informational logs with errors
- No machine-readable format

**Better: Structured JSON Logging**
```python
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@app.get("/order")
def create_order(order_id: str):
    logger.info(json.dumps({
        "event": "order_received",
        "order_id": order_id,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "order-service"
    }))

    # Agent can now parse:
    # - What happened (order_received)
    # - Which order (order_id)
    # - When (ISO timestamp)
    # - Where (service name)
```

**Why JSON Logs?**
- Agent can extract specific fields with log parsing
- Timestamps help identify when errors occurred
- Consistent structure across all services
- Easy to aggregate and search in production

### Concept 4: Docker Networking for Microservices

**Key Insight**: Containers in the same Docker network can communicate by service name.

```yaml
# docker-compose.yml
services:
  order-service:
    environment:
      - PAYMENT_URL=http://payment-service:8002  # Not localhost!
      - INVENTORY_URL=http://inventory-service:8003

  payment-service:
    ports:
      - "8002:8002"
```

**Why Service Names, Not localhost?**
- `localhost` inside a container = the container itself
- Service names resolve via Docker's internal DNS
- Enables inter-service communication

**Example**:
```python
# In order-service container
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-service:8002")
response = httpx.post(f"{PAYMENT_URL}/payment")  # Works!
```

---

## 1.4 Step-by-Step Implementation

### Step 1: Project Initialization (10 minutes)

**Create Project Structure**:
```bash
mkdir -p auto-healer-agent/{auto_healer,dummy_services/{order,payment,inventory},tests,examples/alerts}
cd auto-healer-agent
```

**Initialize uv Project**:
```bash
uv init --name auto-healer-agent
```

**Why uv?**
- Faster than pip (10-100x speedup)
- Better dependency resolution (avoids conflicts)
- Creates `uv.lock` for reproducible installs
- Modern Python packaging (PEP 517/518)

**Expected Output**:
```
Initialized project "auto-healer-agent"
Created pyproject.toml
```

**Verify Structure**:
```bash
tree -L 2
# Should show:
# .
# ├── auto_healer/
# ├── dummy_services/
# │   ├── order/
# │   ├── payment/
# │   └── inventory/
# ├── examples/
# │   └── alerts/
# ├── tests/
# └── pyproject.toml
```

### Step 2: Build Order Service (30 minutes)

**Create File**: `dummy_services/order/app.py`

```python
"""
Order Service - Demo microservice for agent testing.

This service simulates order processing with configurable chaos injection.
It depends on Payment and Inventory services (realistic microservice pattern).
"""
import os
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Why JSON logging? Agents need structured data to parse
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # We'll format as JSON ourselves
)
logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE DEPENDENCIES
# ============================================================================

# Why environment variables?
# - Docker Compose injects these
# - Different values for dev vs production
# - Service discovery via Docker network DNS
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-service:8002")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory-service:8003")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Order Service",
    description="E-commerce order processing with chaos injection",
    version="1.0.0"
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class OrderRequest(BaseModel):
    """Request body for creating an order."""
    item_id: str
    quantity: int = 1
    customer_id: str

class OrderResponse(BaseModel):
    """Response after order creation."""
    order_id: str
    status: str
    payment_status: Optional[str] = None
    inventory_status: Optional[str] = None
    timestamp: str

# ============================================================================
# HELPER: STRUCTURED LOGGING
# ============================================================================

def log_event(event: str, **kwargs):
    """
    Log structured JSON event.

    Why this helper?
    - Consistent log format across all events
    - Easy to add timestamp/service name
    - Agent can parse JSON logs reliably
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "order-service",
        "event": event,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Why this matters:
    - Kubernetes/Docker health probes
    - Infrastructure Expert agent checks this
    - Proves service is responsive
    """
    return {
        "status": "healthy",
        "service": "order-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/order")
def create_order(
    chaos_type: Optional[str] = Query(None, description="Chaos injection trigger")
):
    """
    Create a new order.

    CHAOS INJECTION:
    Controlled via `chaos_type` query parameter for deterministic testing.

    Available chaos types:
    - 500_zerodivision: Python ZeroDivisionError
    - 502_bad_gateway: Simulates upstream service failure
    - 504_gateway_timeout: Simulates slow dependency

    Args:
        chaos_type: Optional chaos scenario to trigger

    Returns:
        OrderResponse with order details

    Raises:
        HTTPException: For 502/504 scenarios
        ZeroDivisionError: For 500 scenario
    """
    order_id = str(uuid.uuid4())

    log_event("order_create_start", order_id=order_id, chaos_type=chaos_type)

    # ========================================================================
    # CHAOS INJECTION: 500 Internal Server Error
    # ========================================================================
    if chaos_type == "500_zerodivision":
        log_event("chaos_triggered", order_id=order_id, type="500_zerodivision")
        # This will raise ZeroDivisionError → 500 response
        # Agent's Log Expert should find this in traceback!
        result = 1 / 0

    # ========================================================================
    # CHAOS INJECTION: 502 Bad Gateway
    # ========================================================================
    if chaos_type == "502_bad_gateway":
        log_event("chaos_triggered", order_id=order_id, type="502_bad_gateway")
        # Simulate upstream service down
        # Agent's Infra Expert should check container health!
        raise HTTPException(status_code=502, detail="Payment service unavailable")

    # ========================================================================
    # CHAOS INJECTION: 504 Gateway Timeout
    # ========================================================================
    if chaos_type == "504_gateway_timeout":
        log_event("chaos_triggered", order_id=order_id, type="504_gateway_timeout")
        # Simulate slow dependency
        # Agent should see timeout in logs
        time.sleep(30)  # Simulates 30s delay
        raise HTTPException(status_code=504, detail="Request timeout")

    # ========================================================================
    # NORMAL PATH: Call Payment Service
    # ========================================================================
    try:
        log_event("payment_call_start", order_id=order_id, url=PAYMENT_URL)

        # Why httpx? Async support, better than requests
        with httpx.Client() as client:
            payment_response = client.post(
                f"{PAYMENT_URL}/payment",
                json={"order_id": order_id, "amount": 99.99},
                timeout=5.0
            )
            payment_status = payment_response.json().get("status", "unknown")

        log_event("payment_call_success", order_id=order_id, status=payment_status)

    except Exception as e:
        log_event("payment_call_failed", order_id=order_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Payment service error: {str(e)}")

    # ========================================================================
    # NORMAL PATH: Call Inventory Service
    # ========================================================================
    try:
        log_event("inventory_call_start", order_id=order_id, url=INVENTORY_URL)

        with httpx.Client() as client:
            inventory_response = client.post(
                f"{INVENTORY_URL}/reserve",
                json={"order_id": order_id, "item_id": "ITEM-001", "quantity": 1},
                timeout=5.0
            )
            inventory_status = inventory_response.json().get("status", "unknown")

        log_event("inventory_call_success", order_id=order_id, status=inventory_status)

    except Exception as e:
        log_event("inventory_call_failed", order_id=order_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Inventory service error: {str(e)}")

    # ========================================================================
    # SUCCESS RESPONSE
    # ========================================================================
    log_event("order_create_success", order_id=order_id)

    return OrderResponse(
        order_id=order_id,
        status="completed",
        payment_status=payment_status,
        inventory_status=inventory_status,
        timestamp=datetime.utcnow().isoformat()
    )

# ============================================================================
# MAIN (for local testing)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

**Key Design Decisions Explained**:

1. **Why JSON Logging?**
   - Structured format → Agent can extract order_id, timestamps
   - Machine-readable → No regex parsing needed
   - Consistent → Same format across all events

2. **Why Service Dependencies?**
   - Realistic microservice architecture
   - Tests distributed failure scenarios
   - Agent must diagnose cascade failures

3. **Why Query Parameters for Chaos?**
   - Deterministic (same param = same error)
   - Self-documenting (shows available scenarios)
   - Easy to test: `curl "http://localhost:8001/order?chaos_type=500_zerodivision"`

4. **Why httpx Over requests?**
   - Better async support (Python 3.11+)
   - Modern HTTP client
   - Cleaner timeout handling

### Step 3: Build Payment Service (15 minutes)

**Create File**: `dummy_services/payment/app.py`

```python
"""
Payment Service - Simulates payment processing.

Simpler than Order Service (no dependencies), but same logging patterns.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Service", version="1.0.0")

class PaymentRequest(BaseModel):
    order_id: str
    amount: float

class PaymentResponse(BaseModel):
    payment_id: str
    order_id: str
    status: str
    timestamp: str

def log_event(event: str, **kwargs):
    """Log structured JSON event."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "payment-service",
        "event": event,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "payment-service"}

@app.post("/payment")
def process_payment(
    request: PaymentRequest,
    chaos_type: Optional[str] = Query(None)
):
    """Process payment for an order."""
    payment_id = str(uuid.uuid4())

    log_event("payment_start", payment_id=payment_id, order_id=request.order_id, amount=request.amount)

    # Chaos injection (optional)
    if chaos_type == "500_payment_failure":
        log_event("chaos_triggered", payment_id=payment_id, type="500_payment_failure")
        result = 1 / 0  # ZeroDivisionError

    # Normal path
    log_event("payment_success", payment_id=payment_id, order_id=request.order_id)

    return PaymentResponse(
        payment_id=payment_id,
        order_id=request.order_id,
        status="approved",
        timestamp=datetime.utcnow().isoformat()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

### Step 4: Build Inventory Service (15 minutes)

**Create File**: `dummy_services/inventory/app.py`

```python
"""
Inventory Service - Simulates inventory reservation.

Similar structure to Payment Service.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Inventory Service", version="1.0.0")

class ReservationRequest(BaseModel):
    order_id: str
    item_id: str
    quantity: int

class ReservationResponse(BaseModel):
    reservation_id: str
    order_id: str
    status: str
    timestamp: str

def log_event(event: str, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "inventory-service",
        "event": event,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "inventory-service"}

@app.post("/reserve")
def reserve_inventory(
    request: ReservationRequest,
    chaos_type: Optional[str] = Query(None)
):
    """Reserve inventory for an order."""
    reservation_id = str(uuid.uuid4())

    log_event("reservation_start", reservation_id=reservation_id, order_id=request.order_id, item_id=request.item_id)

    # Chaos injection (optional)
    if chaos_type == "500_inventory_error":
        log_event("chaos_triggered", reservation_id=reservation_id, type="500_inventory_error")
        result = 1 / 0

    # Normal path
    log_event("reservation_success", reservation_id=reservation_id, order_id=request.order_id)

    return ReservationResponse(
        reservation_id=reservation_id,
        order_id=request.order_id,
        status="reserved",
        timestamp=datetime.utcnow().isoformat()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
```

### Step 5: Dockerize Services (20 minutes)

**Create File**: `dummy_services/order/Dockerfile`

```dockerfile
# Use Python 3.12 slim (matches local development)
FROM python:3.12-slim

# Why WORKDIR? Sets working directory for subsequent commands
WORKDIR /app

# Copy application code
COPY app.py .

# Install dependencies
# Why --no-cache-dir? Reduces image size
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

# Expose port (documentation, not enforcement)
EXPOSE 8001

# Run FastAPI with uvicorn
# Why --host 0.0.0.0? Listen on all interfaces (not just localhost)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Key Decisions**:
- `python:3.12-slim`: Matches local Python version (avoid dependency conflicts)
- `--host 0.0.0.0`: Required for Docker networking (localhost won't work)
- `--no-cache-dir`: Smaller image size

**Copy for Payment and Inventory**:

`dummy_services/payment/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir fastapi uvicorn pydantic
EXPOSE 8002
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
```

`dummy_services/inventory/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir fastapi uvicorn pydantic
EXPOSE 8003
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8003"]
```

### Step 6: Docker Compose Orchestration (15 minutes)

**Create File**: `docker-compose.yml` (in project root)

```yaml
# Docker Compose v2 (no version field needed)

services:
  # ========================================================================
  # ORDER SERVICE (depends on payment + inventory)
  # ========================================================================
  order-service:
    build:
      context: ./dummy_services/order
      dockerfile: Dockerfile
    container_name: order-service
    ports:
      - "8001:8001"  # host:container
    environment:
      # Service discovery via Docker network DNS
      - PAYMENT_URL=http://payment-service:8002
      - INVENTORY_URL=http://inventory-service:8003
    depends_on:
      - payment-service
      - inventory-service
    networks:
      - app-network
    restart: unless-stopped  # Auto-restart on failure

  # ========================================================================
  # PAYMENT SERVICE (no dependencies)
  # ========================================================================
  payment-service:
    build:
      context: ./dummy_services/payment
      dockerfile: Dockerfile
    container_name: payment-service
    ports:
      - "8002:8002"
    networks:
      - app-network
    restart: unless-stopped

  # ========================================================================
  # INVENTORY SERVICE (no dependencies)
  # ========================================================================
  inventory-service:
    build:
      context: ./dummy_services/inventory
      dockerfile: Dockerfile
    container_name: inventory-service
    ports:
      - "8003:8003"
    networks:
      - app-network
    restart: unless-stopped

# ========================================================================
# NETWORK (implicit creation)
# ========================================================================
networks:
  app-network:
    driver: bridge  # Default driver for Docker networking
```

**Key Configuration Explained**:

1. **Service Dependencies** (`depends_on`):
   - Order starts AFTER payment + inventory
   - Ensures dependencies are ready
   - (Note: doesn't wait for health, just container start)

2. **Environment Variables**:
   - `PAYMENT_URL=http://payment-service:8002`
   - Uses service name (Docker DNS resolution)
   - Not `localhost` (won't work in containers)

3. **Port Mapping**:
   - `"8001:8001"` = host port : container port
   - Access from host: `curl http://localhost:8001/health`
   - Access between containers: `http://order-service:8001/health`

4. **Networks**:
   - All services in `app-network`
   - Enables inter-service communication
   - Isolated from other Docker networks

5. **Restart Policy**:
   - `unless-stopped`: Auto-restart on crash
   - Helps test agent handling of container restarts

---

## 1.5 Validation Checkpoints

### Checkpoint 1: Services Start Successfully

```bash
# Build and start all services
docker-compose up -d --build

# Expected output:
# [+] Building ...
# [+] Running 3/3
#  ✔ Container payment-service    Started
#  ✔ Container inventory-service  Started
#  ✔ Container order-service      Started
```

**Verify containers are running**:
```bash
docker ps

# Expected output (3 containers):
# CONTAINER ID   IMAGE                  STATUS         PORTS
# abc123         order-service          Up 10 seconds  0.0.0.0:8001->8001/tcp
# def456         payment-service        Up 11 seconds  0.0.0.0:8002->8002/tcp
# ghi789         inventory-service      Up 11 seconds  0.0.0.0:8003->8003/tcp
```

**If services don't start**:
```bash
# Check logs for errors
docker-compose logs order-service
docker-compose logs payment-service
docker-compose logs inventory-service

# Common issues:
# - Port already in use → Change ports in docker-compose.yml
# - Build errors → Check Dockerfile syntax
# - Import errors → Verify pip install commands
```

### Checkpoint 2: Health Checks Pass

```bash
# Test each service health endpoint
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"order-service","timestamp":"..."}

curl http://localhost:8002/health
# Expected: {"status":"healthy","service":"payment-service"}

curl http://localhost:8003/health
# Expected: {"status":"healthy","service":"inventory-service"}
```

**If health checks fail**:
- Container not running? → Check `docker ps`
- Wrong port? → Verify `docker-compose.yml` port mapping
- Service crashed? → Check logs with `docker logs <container-name>`

### Checkpoint 3: Normal Order Flow Works

```bash
# Create order (no chaos)
curl http://localhost:8001/order

# Expected response:
# {
#   "order_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "status": "completed",
#   "payment_status": "approved",
#   "inventory_status": "reserved",
#   "timestamp": "2024-04-30T12:00:00.000000"
# }
```

**Verify structured logs**:
```bash
docker logs order-service --tail 20

# Expected JSON logs:
# {"timestamp":"...","service":"order-service","event":"order_create_start","order_id":"..."}
# {"timestamp":"...","service":"order-service","event":"payment_call_start","order_id":"..."}
# {"timestamp":"...","service":"order-service","event":"payment_call_success","order_id":"..."}
# {"timestamp":"...","service":"order-service","event":"inventory_call_start","order_id":"..."}
# {"timestamp":"...","service":"order-service","event":"inventory_call_success","order_id":"..."}
# {"timestamp":"...","service":"order-service","event":"order_create_success","order_id":"..."}
```

### Checkpoint 4: Chaos Injection Works

**Test 500 Error**:
```bash
curl "http://localhost:8001/order?chaos_type=500_zerodivision"

# Expected: 500 Internal Server Error
# Response: {"detail":"Internal Server Error"}
```

**Verify Python traceback in logs**:
```bash
docker logs order-service --tail 30

# Expected: Full Python traceback with:
# Traceback (most recent call last):
#   File "/app/app.py", line 84, in create_order
#     result = 1 / 0
# ZeroDivisionError: division by zero
```

**Test 502 Error**:
```bash
curl "http://localhost:8001/order?chaos_type=502_bad_gateway"

# Expected: 502 Bad Gateway
# Response: {"detail":"Payment service unavailable"}
```

**Test 504 Error** (warning: takes 30 seconds):
```bash
curl "http://localhost:8001/order?chaos_type=504_gateway_timeout"

# Expected: 504 Gateway Timeout after ~30s
```

### Checkpoint 5: Inter-Service Communication Works

**Verify Order → Payment → Inventory chain**:

```bash
# Trigger normal order
curl http://localhost:8001/order

# Check order service called payment
docker logs payment-service --tail 10
# Expected: {"event":"payment_start","order_id":"...","amount":99.99}

# Check order service called inventory
docker logs inventory-service --tail 10
# Expected: {"event":"reservation_start","order_id":"...","item_id":"ITEM-001"}
```

**If inter-service communication fails**:
- Check environment variables in `docker-compose.yml`
- Verify service names (not `localhost`)
- Check Docker network: `docker network inspect auto-healer-agent_app-network`

---

## 1.6 Common Pitfalls

### Pitfall 1: Python Version Mismatch

**Symptom**:
```
ERROR: Could not find a version that satisfies the requirement pydantic>=2.0
```

**Root Cause**: Dockerfile uses Python 3.10, local is Python 3.12

**Solution**: Match versions exactly
```dockerfile
# Use same version as local development
FROM python:3.12-slim  # Not 3.10!
```

**Prevention**: Always check `python --version` before writing Dockerfile

### Pitfall 2: Podman vs Docker Socket

**Symptom**:
```
docker.errors.DockerException: Error while fetching server API version:
('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

**Root Cause**: Python Docker SDK expects `/var/run/docker.sock`, but Podman uses different path

**Solution**: Set `DOCKER_HOST` environment variable
```bash
# For Podman on macOS/Linux
export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock

# Verify
docker context show
```

**Alternative**: Use `podman-compose` instead of `docker-compose`
```bash
podman-compose up -d --build
```

### Pitfall 3: Using `localhost` in Containers

**Symptom**: Order service can't reach payment service
```
ERROR: httpx.ConnectError: [Errno 111] Connection refused (http://localhost:8002/payment)
```

**Root Cause**: `localhost` inside container = the container itself, not other containers

**Wrong Code**:
```python
PAYMENT_URL = "http://localhost:8002"  # ❌ Won't work
```

**Correct Code**:
```python
# Use service name from docker-compose.yml
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-service:8002")  # ✅
```

**Docker DNS**: Service names resolve to container IPs automatically

### Pitfall 4: Port Already in Use

**Symptom**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:8001: bind: address already in use
```

**Root Cause**: Another process is using port 8001

**Solution 1**: Kill the process
```bash
# Find process using port 8001
lsof -i :8001
# Output: python  12345 user  ... (LISTEN)

# Kill it
kill -9 12345
```

**Solution 2**: Change port in `docker-compose.yml`
```yaml
ports:
  - "8011:8001"  # Map to different host port
```

### Pitfall 5: Mixed Log Formats

**Problem**: Some logs are JSON, some are plain text

**Wrong**:
```python
logger.info("Order received")  # Plain text
logger.info(json.dumps({"event": "payment_call"}))  # JSON
```

**Why This Breaks Agents**:
- Agent has to handle two formats
- Plain text logs hard to parse
- Inconsistent timestamps

**Solution**: Always use structured logging
```python
# Create helper function
def log_event(event: str, **kwargs):
    logger.info(json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "service": "order-service",
        "event": event,
        **kwargs
    }))

# Use everywhere
log_event("order_received", order_id=order_id)
log_event("payment_call", url=payment_url)
```

### Pitfall 6: Forgetting to Rebuild After Code Changes

**Symptom**: Code changes don't appear in container

**Root Cause**: Docker image not rebuilt after editing `app.py`

**Solution**: Always rebuild when code changes
```bash
# Stop containers
docker-compose down

# Rebuild images and start
docker-compose up -d --build  # --build is critical!
```

**Tip**: Use volume mounts for development (hot reload)
```yaml
# In docker-compose.yml (for development only)
services:
  order-service:
    volumes:
      - ./dummy_services/order:/app  # Mount local code
    command: uvicorn app:app --host 0.0.0.0 --port 8001 --reload  # Auto-reload
```

---

## 1.7 Exercises

### Exercise 1: Add New Chaos Type

**Objective**: Add `503_service_unavailable` chaos type to all services

**Steps**:
1. Edit `dummy_services/order/app.py`:
   ```python
   if chaos_type == "503_service_unavailable":
       log_event("chaos_triggered", order_id=order_id, type="503_service_unavailable")
       raise HTTPException(status_code=503, detail="Service temporarily unavailable")
   ```

2. Add same to `payment/app.py` and `inventory/app.py`

3. Rebuild and test:
   ```bash
   docker-compose up -d --build
   curl "http://localhost:8001/order?chaos_type=503_service_unavailable"
   ```

4. Verify logs show distinctive message

**Expected Result**: 503 error with structured log entry

### Exercise 2: Add Metrics Endpoint

**Objective**: Track request count and error count per service

**Steps**:
1. Add global counters:
   ```python
   request_count = 0
   error_count = 0
   ```

2. Increment in endpoints:
   ```python
   @app.get("/order")
   def create_order(...):
       global request_count
       request_count += 1

       try:
           # ... order logic
       except Exception:
           global error_count
           error_count += 1
           raise
   ```

3. Create metrics endpoint:
   ```python
   @app.get("/metrics")
   def metrics():
       return {
           "requests_total": request_count,
           "errors_total": error_count,
           "error_rate": error_count / request_count if request_count > 0 else 0
       }
   ```

4. Test:
   ```bash
   curl http://localhost:8001/metrics
   ```

**Expected Result**: JSON with request and error counts

### Exercise 3: Service Dependency Failure

**Objective**: Make Payment service return 500 when receiving `chaos_type=payment_failure`

**Steps**:
1. Edit `dummy_services/payment/app.py`:
   ```python
   @app.post("/payment")
   def process_payment(request: PaymentRequest, chaos_type: Optional[str] = Query(None)):
       if chaos_type == "payment_failure":
           result = 1 / 0  # Trigger 500
   ```

2. Edit `dummy_services/order/app.py` to forward chaos parameter:
   ```python
   payment_response = client.post(
       f"{PAYMENT_URL}/payment?chaos_type={chaos_type}",  # Forward chaos
       json={"order_id": order_id, "amount": 99.99}
   )
   ```

3. Test cascade failure:
   ```bash
   curl "http://localhost:8001/order?chaos_type=payment_failure"
   ```

4. Check logs show cascade:
   ```bash
   docker logs order-service --tail 20
   docker logs payment-service --tail 20
   ```

**Expected Result**:
- Payment service logs show ZeroDivisionError
- Order service logs show "Payment service error"

---

## 1.8 Key Takeaways

### ✅ What You Learned

1. **Dummy Services > Mocks for Agent Testing**
   - Agents need real perception targets (Docker SDK, HTTP APIs)
   - Mocks don't catch integration issues
   - Real services prove agent works in production

2. **Chaos Engineering Enables Deterministic Testing**
   - Query parameters control chaos (reproducible)
   - Each chaos type tests different agent capabilities
   - Better than random failures (flaky tests)

3. **Structured Logging for Machine Parsing**
   - JSON logs with timestamps and event types
   - Agent can extract specific fields
   - Consistent format across all services

4. **Docker Networking Fundamentals**
   - Service names resolve via Docker DNS
   - Environment variables for configuration
   - Port mapping for host access

5. **FastAPI for Rapid Microservice Development**
   - Automatic OpenAPI docs
   - Pydantic validation
   - Async support (httpx)

### 📊 Metrics from Real Project

- **Services Built**: 3 (order, payment, inventory)
- **Chaos Types**: 3 (500, 502, 504) per service
- **Lines of Code**: ~300 per service (~900 total)
- **Time to Build**: 2-3 hours for first-time learners
- **Container Size**: ~150MB per service (slim Python image)

### 🎯 Production-Ready Aspects

Even though these are "dummy" services, they demonstrate production patterns:

- ✅ Health check endpoints (Kubernetes probes)
- ✅ Graceful error handling (HTTPException)
- ✅ Environment-based configuration (12-factor app)
- ✅ Structured logging (observability)
- ✅ Inter-service communication (microservices)
- ✅ Restart policies (fault tolerance)

### 🔍 Why This Architecture?

**Q: Why not just mock Docker logs?**
A: Agent can't learn real Docker SDK usage, real error formats, or real JSON parsing

**Q: Why 3 services instead of 1?**
A: Tests distributed failures (cascade errors), service dependencies, realistic debugging

**Q: Why Docker Compose instead of plain Docker?**
A: Orchestrates multiple services, manages networks, defines dependencies

**Q: Why FastAPI instead of Flask?**
A: Async support (better for microservices), automatic docs, Pydantic validation

---

## 1.9 Next Steps

### Phase 2 Preview: Building the Agent's "Senses"

Now that you have realistic target services with controllable chaos, the next phase builds the agent's perception layer:

**What You'll Build**:
- Docker SDK tools to read logs from containers
- Container health inspection tools
- RAG memory system (ChromaDB) for learning from past incidents
- Local LLM configuration (Ollama)

**Key Questions**:
- How does the agent "see" these services? → Docker SDK tools
- How does the agent remember past incidents? → ChromaDB vector database
- How does the agent think? → Local LLM with proper context window

**Bridge to Phase 2**:
You now have services that produce real logs and real errors. In Phase 2, you'll give the agent the tools to perceive and analyze these services - the foundation for autonomous troubleshooting.

**Recommended Next Action**:
Proceed to `LESSON_PHASE2.md` when you're ready to build the perception layer.

---

**End of Phase 1 Lesson**

✅ Infrastructure complete
✅ Services containerized
✅ Chaos injection working
✅ Ready for Phase 2: Perception & Memory
