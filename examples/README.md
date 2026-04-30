# Examples

This directory contains sample data for testing the Auto-Healer Agent.

## Alert Files

Alert JSON files simulate webhook payloads from monitoring systems (e.g., Prometheus, Datadog, PagerDuty).

### Available Alerts

**`alerts/alert_500_zerodivision.json`**
- Simulates a 500 Internal Server Error caused by a ZeroDivisionError
- Used to test the Log Expert agent's ability to parse Python tracebacks
- Trigger with: `curl 'http://localhost:8001/order?chaos_type=500_zerodivision'`

**`alerts/alert_502_bad_gateway.json`**
- Simulates a 502 Bad Gateway error from upstream service failure
- Tests the agent's ability to diagnose service communication issues
- Trigger with: `curl 'http://localhost:8001/order?chaos_type=502_bad_gateway'`

**`alerts/alert_504_timeout.json`**
- Simulates a 504 Gateway Timeout from a long-running request
- Tests infrastructure diagnostics (container health, resource limits)
- Trigger with: `curl 'http://localhost:8001/order?chaos_type=504_gateway_timeout'`

## Usage

Run the agent with a sample alert:

```bash
python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json
```

The agent will:
1. Read the alert metadata
2. Query ChromaDB for similar past incidents
3. Route to appropriate specialist agents (Log Expert, Infra Expert)
4. Generate a Root Cause Analysis report
5. Ask for human approval before committing to memory

## Alert Schema

All alert files follow this structure:

```json
{
  "service": "order-service",          // Container name
  "status_code": 500,                  // HTTP status code
  "timestamp": "2024-04-30T10:30:00Z", // ISO 8601 timestamp
  "error_message": "Internal Server Error",
  "chaos_type": "500_zerodivision"     // Optional: chaos scenario
}
```

## Creating Custom Alerts

To create your own test alerts:

1. Copy an existing alert file
2. Modify the fields as needed
3. Ensure the `service` field matches a running container name
4. Run the agent with your custom alert

Example:
```bash
cp alerts/alert_500_zerodivision.json alerts/my_custom_alert.json
# Edit my_custom_alert.json
python -m auto_healer.main --alert examples/alerts/my_custom_alert.json
```

## Future Examples

Planned additions:
- Multi-service failure scenarios
- OOM (Out of Memory) kill examples
- Database connection pool exhaustion
- Rate limiting scenarios
- Complex cascading failures
