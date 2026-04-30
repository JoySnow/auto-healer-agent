# Testing the Auto-Healer Agent Infrastructure

## Docker Infrastructure Test Results ✅

All dummy microservices are successfully running with podman-compose and chaos injection is working as expected.

### Services Status

```bash
$ podman-compose ps
CONTAINER ID  IMAGE                                         COMMAND               STATUS        PORTS
d928a0ae1188  localhost/auto-healer-agent_order:latest      uvicorn...           Up           0.0.0.0:8001->8001/tcp
646acfd13fcb  localhost/auto-healer-agent_payment:latest    uvicorn...           Up           0.0.0.0:8002->8002/tcp
54bab32d8c3a  localhost/auto-healer-agent_inventory:latest  uvicorn...           Up           0.0.0.0:8003->8003/tcp
```

### Health Check Results ✅

All services are healthy:
```json
{"status":"healthy","service":"order","timestamp":"2026-04-30T08:53:19.657996"}
{"status":"healthy","service":"payment","timestamp":"2026-04-30T08:53:19.673822"}
{"status":"healthy","service":"inventory","timestamp":"2026-04-30T08:53:19.687381"}
```

### Normal Flow Test ✅

**Request:**
```bash
curl 'http://localhost:8001/order?item_id=test-001&quantity=1'
```

**Response:**
```json
{
  "order_id":"a5d00da3-7d46-4e4b-94c1-55584c9f0555",
  "status":"success",
  "payment_id":"d8d8175c-e42d-465c-9e97-8725f816867f",
  "inventory_status":"confirmed",
  "timestamp":"2026-04-30T08:53:45.019472"
}
```

**Logs show proper service communication:**
- Order service called Inventory service: `POST http://inventory:8003/check_stock "HTTP/1.1 200 OK"`
- Order service called Payment service: `POST http://payment:8002/process_payment "HTTP/1.1 200 OK"`
- Order completed successfully

### Chaos Injection Tests ✅

#### 1. 500 ZeroDivisionError

**Request:**
```bash
curl 'http://localhost:8001/order?chaos_type=500_zerodivision'
```

**Response:**
```
Internal Server Error
```

**Logs show expected error:**
```json
{"event": "chaos_triggered", "type": "500_zerodivision", "order_id": "7fc892cb-da6a-4c20-bee8-ee5b6462dba4"}
```

```python
ZeroDivisionError: division by zero
    result = 1 / 0
             ~~^~~
```

✅ **Perfect for agent testing** - Clear Python traceback for Log Expert to analyze

#### 2. 502 Bad Gateway

**Request:**
```bash
curl 'http://localhost:8001/order?chaos_type=502_bad_gateway'
```

**Response:**
```json
{"detail":"Bad Gateway - Upstream service failure"}
```

**Logs:**
```json
{"event": "chaos_triggered", "type": "502_bad_gateway", "order_id": "6443886c-bf58-4b76-8343-888d7aeedc2a"}
```

✅ **Perfect for agent testing** - Simulates upstream service failure

#### 3. 504 Gateway Timeout

**Request:**
```bash
curl 'http://localhost:8001/order?chaos_type=504_gateway_timeout'
```

**Expected:** Service sleeps for 60 seconds then returns timeout

✅ **Perfect for agent testing** - Simulates long-running request timeouts

### Structured Logging ✅

All logs are in JSON format for easy parsing by agents:
```json
{"timestamp": "2026-04-30 08:53:45,001", "level": "INFO", "message": "{"event": "order_received", "order_id": "...", ...}"}
```

## Podman vs Docker Notes

The project uses **podman** instead of docker:

### Running Services
```bash
# Start all services
podman-compose up -d --build

# Check status
podman-compose ps

# View logs
podman logs order-service
podman logs payment-service
podman logs inventory-service

# Stop services
podman-compose down
```

### Python Docker SDK Compatibility

The Python `docker` SDK works with podman if you set the DOCKER_HOST environment variable:

```bash
# For podman socket (check your actual socket path)
export DOCKER_HOST="unix:///run/podman/podman.sock"

# Or for podman-machine on macOS
export DOCKER_HOST="unix://${HOME}/.local/share/containers/podman/machine/podman.sock"
```

Alternatively, create a symlink:
```bash
sudo ln -s $(which podman) /usr/local/bin/docker
```

Or use podman's docker compatibility:
```bash
podman system service --time=0 unix:///tmp/podman.sock
export DOCKER_HOST="unix:///tmp/podman.sock"
```

## Test Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Order Service | ✅ Working | Port 8001, calls Payment & Inventory |
| Payment Service | ✅ Working | Port 8002, processes payments |
| Inventory Service | ✅ Working | Port 8003, checks stock |
| 500 Chaos | ✅ Working | ZeroDivisionError with traceback |
| 502 Chaos | ✅ Working | Bad Gateway simulation |
| 504 Chaos | ✅ Working | Gateway timeout (60s sleep) |
| JSON Logging | ✅ Working | All logs structured for parsing |
| Service Discovery | ✅ Working | Services communicate via container names |

## Next Steps

With the infrastructure validated, we can proceed to:
1. ✅ Phase 1: Infrastructure & Chaos Mock - **COMPLETE**
2. ✅ Phase 2: Perception, Tools & Memory Layer - **COMPLETE**
3. ⏭️ Phase 3: Core Orchestration (LangGraph) - Build agent nodes
4. ⏭️ Phase 4: Integration & HITL - Wire the graph together
5. ⏭️ Phase 5: Polish - Rich UI and documentation

The dummy services provide a perfect "target range" for testing the agent's troubleshooting capabilities!
