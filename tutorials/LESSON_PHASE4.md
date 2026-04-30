# Phase 4 Lesson: Integration Testing & Human-in-the-Loop

## 4.1 Overview

**What You'll Build**: Complete HITL approval workflow, end-to-end test suite for all error scenarios, and supervisor improvements based on test findings.

**Why It Matters**:
- Testing finds edge cases that design misses
- HITL prevents autonomous mistakes (only store good RCAs)
- Real scenarios reveal optimization opportunities

**Learning Objectives**:
- Design integration tests for multi-agent systems
- Implement Human-in-the-Loop approval workflows
- Debug agent behavior with real error scenarios
- Improve supervisor decision logic based on test findings
- Measure and optimize agent performance

**Time to Complete**: 4-6 hours (including test runs)

---

## 4.2 Prerequisites

Before starting this lesson, you should have:

- ✅ **Phase 3 completed** (multi-agent graph working)
- ✅ **Services running** from Phase 1 (with chaos endpoints)
- Understanding of test-driven development
- Patience for test execution (some tests take 5-6 minutes)

**Verify Phase 3**:
```bash
# Test graph compiles
python -c "from auto_healer.graph import create_graph; create_graph(); print('Graph: OK')"

# Test services running
docker ps | grep -E "order|payment|inventory"
# Should show 3 containers
```

---

## 4.3 Core Concepts

### Concept 1: Why Human-in-the-Loop (HITL)?

**Without HITL** (Autonomous RCA):
```
Alert → Agent Investigation → Auto-Generate RCA → Auto-Save to Memory
                                      ↓
                            What if RCA is WRONG?
                            Agent learns from bad example!
                            Future incidents: Worse diagnoses!
```

**Real Risk**:
```
Incident 1: 500 error
→ Agent (incorrectly): "Root cause: Database timeout"
→ Auto-saved to memory

Incident 2: Same 500 error
→ Memory: "Last time this was database timeout"
→ Agent: "Following historical pattern: Database timeout"
→ Wrong again! (actual cause: ZeroDivisionError)

Result: Agent reinforces its own mistakes!
```

---

**With HITL** (Human Approval):
```
Alert → Agent Investigation → Generate RCA → PAUSE for Human
                                                  ↓
                                          Human Reviews:
                                          ✓ Approve → Save to memory
                                          ✗ Reject → Discard
                                          ✎ Edit → Fix then save
```

**Benefits**:
- ✅ Only accurate RCAs stored in memory
- ✅ Human catches agent mistakes
- ✅ Quality control on learning data
- ✅ Agent improves over time (learns from good examples only)

**Real-World Example**:
```
Incident: 502 Bad Gateway
Agent RCA: "Container healthy, no infrastructure issues. Unable to determine root cause."

Human Review: "Correct - this was chaos testing scenario. No real issue."
Action: ✓ Approve (agent correctly identified ambiguity)

Vs.

Agent RCA: "Root cause: OOM kill" (but container shows healthy, no OOM flag)

Human Review: "Incorrect - container is healthy. Agent hallucinated."
Action: ✗ Reject (don't save bad RCA)
```

---

### Concept 2: Test Scenarios Matrix

**Why Test Multiple Scenarios?**
- Different error types → Different agent behaviors
- Edge cases reveal bugs
- Performance varies by scenario

| Error Type | Status Code | Expected Routing | Expected Tools | Expected Finding |
|------------|-------------|------------------|----------------|------------------|
| **500 ZeroDivisionError** | 500 | log_expert | fetch_logs | File:line of crash |
| **502 Bad Gateway** | 502 | infra_expert → log_expert | check_health, fetch_logs | Ambiguous (chaos) |
| **504 Gateway Timeout** | 504 | infra_expert → log_expert | check_health, fetch_logs | Ambiguous (chaos) |

**Why "Ambiguous" for 502/504?**
- Healthy container (no crash)
- No Python traceback (chaos exception handled)
- Conflicting signals → Supervisor loops without budgets!

**Real Test Results** (before supervisor improvements):

| Scenario | Duration | Agent Calls | Outcome | Issue |
|----------|----------|-------------|---------|-------|
| 500 ZeroDivisionError | 60s | 4 | ✅ Success | None |
| 502 Bad Gateway | 6 min | 13 | ❌ Circuit breaker | Infinite loop |
| 504 Timeout | 9 min | 13 | ❌ Circuit breaker | Infinite loop |

**Discovery**: Supervisor can't decide when evidence is ambiguous!

---

### Concept 3: Validation Metrics

**What to Measure**:

1. **Accuracy**: Did agent find correct root cause?
   - Check RCA mentions specific error (ZeroDivisionError)
   - Check RCA cites file path (/app/app.py)
   - Check RCA cites line number (84)

2. **Efficiency**: How many resources consumed?
   - LLM calls (each costs tokens/money)
   - Agent consultations (each takes time)
   - Tool calls (Docker SDK operations)

3. **Termination**: Did agent finish within limits?
   - Recursion limit (default: 15 iterations)
   - Time limit (reasonable investigation duration)
   - Clean finish (HITL) vs error (circuit breaker)

4. **Output Quality**: Is RCA actionable?
   - Specific (not generic "server error")
   - File paths and line numbers
   - Recommended fix

**Example Metrics Collection**:
```python
metrics = {
    "duration_seconds": 60,
    "llm_calls": 4,
    "agent_consultations": {"log_expert": 1, "infra_expert": 0},
    "tool_calls": 1,
    "iterations": 4,
    "max_iterations": 15,
    "outcome": "FINISH",  # vs "CIRCUIT_BREAKER"
    "rca_quality": "specific"  # vs "generic" or "incomplete"
}
```

---

### Concept 4: Circuit Breaker Behavior

**Purpose**: Prevent infinite loops and runaway costs

**Mechanism**:
```python
graph.invoke(state, config={"recursion_limit": 15})

# If graph exceeds 15 iterations:
RecursionError: Recursion limit of 15 reached
```

**When It Triggers**:
- Supervisor loops between agents
- No progress toward FINISH
- Ambiguous evidence (agent can't decide)

**Real Scenario** (502 error before improvements):
```
Iteration 1: Supervisor → infra_expert
Iteration 2: Infra Expert: "Container healthy"
Iteration 3: Supervisor → log_expert
Iteration 4: Log Expert: "Chaos trigger, no traceback"
Iteration 5: Supervisor → infra_expert (REPEAT!)
Iteration 6: Infra Expert: "Still healthy" (same as #2)
Iteration 7: Supervisor → log_expert (REPEAT!)
...
Iteration 14: Supervisor → infra_expert
Iteration 15: Recursion limit exceeded → ERROR
```

**Problem**: Circuit breaker is safety net, but:
- Ends with error (not clean finish)
- No RCA generated (investigation wasted)
- Exit code 1 (failure)

**Better Solution**: Agent consultation budgets (prevents loop BEFORE hitting circuit breaker)

---

### Concept 5: Memory Recall Testing

**Test Workflow**:
```
Test Run 1 (Empty Memory):
→ Query memory: "No similar past incidents found"
→ Agent investigates from scratch
→ Human approves RCA
→ Save to ChromaDB

Test Run 2 (Memory Populated):
→ Query memory: Returns Run 1 RCA
→ Agent uses historical context
→ Faster investigation (knows what to look for)
```

**Why Test This?**
- Validates RAG memory works end-to-end
- Proves agent learns from past incidents
- Measures speed improvement (with vs without memory)

**Expected Behavior**:
- First run: ~60 seconds (thorough investigation)
- Second run: ~20-30 seconds (knows where to look)

---

## 4.4 Step-by-Step Implementation

### Step 1: Implement Complete HITL Node (45 minutes)

**Update File**: `auto_healer/nodes/hitl.py`

This file already has placeholders from Phase 3. Now implement full functionality:

```python
"""
Human-in-the-Loop (HITL) Nodes

These nodes implement human approval workflow:
1. Pause graph execution
2. Display RCA report
3. Wait for user input (y/n/edit)
4. Save approved RCA to memory
"""
from typing import Dict, Any
import logging
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from auto_healer.state import AlertTeamState
from auto_healer.memory import query_past_incidents, save_incident

logger = logging.getLogger(__name__)
console = Console()

# ============================================================================
# MEMORY RECALL NODE (Already implemented in Phase 3, kept here for completeness)
# ============================================================================

def memory_recall_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Query ChromaDB for similar past incidents.

    Runs at graph entry point (before supervisor).
    Enriches investigation with historical context.
    """
    logger.info("=" * 60)
    logger.info("=== MEMORY RECALL: Searching for Similar Incidents ===")
    logger.info("=" * 60)

    alert_info = state.get("alert_info", {})

    # Query ChromaDB (semantic search)
    historical_context = query_past_incidents(alert_info, top_k=3)

    if "No similar past incidents" in historical_context:
        logger.info("✓ No similar past incidents found (empty memory or no matches)")
    else:
        logger.info(f"✓ Found similar incidents (preview): {historical_context[:150]}...")

    return {"historical_context": historical_context}


# ============================================================================
# HUMAN APPROVAL NODE (HITL Pause Point)
# ============================================================================

def human_approval_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Pause graph execution for human approval of RCA report.

    Workflow:
    1. Compile RCA from agent findings
    2. Display formatted report with Rich UI
    3. Prompt user: Approve (y), Reject (n), or Edit (e)
    4. Return approval decision and RCA

    Args:
        state (AlertTeamState): Current graph state

    Returns:
        dict: {"approved": bool, "rca_report": str}
    """
    logger.info("=" * 60)
    logger.info("=== HUMAN-IN-THE-LOOP: Approval Required ===")
    logger.info("=" * 60)

    # ========================================================================
    # 1. COMPILE RCA REPORT FROM AGENT FINDINGS
    # ========================================================================

    rca_report = compile_rca_report(state)

    # ========================================================================
    # 2. DISPLAY RCA WITH RICH UI
    # ========================================================================

    console.print("\n" + "=" * 80)
    console.print(Panel(
        rca_report,
        title="[bold yellow]ROOT CAUSE ANALYSIS REPORT[/bold yellow]",
        border_style="yellow",
        padding=(1, 2)
    ))
    console.print("=" * 80 + "\n")

    # ========================================================================
    # 3. PROMPT USER FOR APPROVAL
    # ========================================================================

    console.print("[bold cyan]Review the RCA report above.[/bold cyan]")
    console.print("\nOptions:")
    console.print("  [green]y[/green] - Approve and save to memory")
    console.print("  [red]n[/red] - Reject (do not save)")
    console.print("  [yellow]e[/yellow] - Edit (future feature - for now, reject)")

    approval_input = Prompt.ask(
        "\n🔍 Approve this RCA?",
        choices=["y", "n", "e"],
        default="n"
    )

    # ========================================================================
    # 4. PROCESS USER DECISION
    # ========================================================================

    if approval_input == "y":
        logger.info("✓ RCA approved by human")
        console.print("\n[bold green]✓ RCA approved and will be saved to memory.[/bold green]\n")

        return {
            "approved": True,
            "rca_report": rca_report
        }

    elif approval_input == "n":
        logger.info("✗ RCA rejected by human")
        console.print("\n[bold red]✗ RCA rejected. Not saved to memory.[/bold red]\n")

        return {
            "approved": False,
            "rca_report": rca_report
        }

    else:  # "e" - Edit
        logger.info("✎ Human requested edits")
        console.print("\n[bold yellow]✎ Edit feature coming in future phase.[/bold yellow]")
        console.print("[dim]For now, RCA will be rejected. You can re-run investigation if needed.[/dim]\n")

        return {
            "approved": False,
            "rca_report": rca_report
        }


def compile_rca_report(state: AlertTeamState) -> str:
    """
    Build formatted RCA report from agent findings.

    Includes:
    - Alert metadata
    - Agent analyses (log_expert, infra_expert)
    - Recommended actions

    Args:
        state (AlertTeamState): Current graph state

    Returns:
        str: Formatted RCA report (Markdown)
    """
    alert_info = state["alert_info"]
    messages = state["messages"]

    # Extract agent analyses from messages
    log_analysis = [
        m.content for m in messages
        if hasattr(m, 'name') and m.name == 'log_expert'
    ]

    infra_analysis = [
        m.content for m in messages
        if hasattr(m, 'name') and m.name == 'infra_expert'
    ]

    supervisor_decisions = [
        m.content for m in messages
        if "Supervisor Decision" in m.content or "Next:" in m.content
    ]

    # ========================================================================
    # BUILD REPORT
    # ========================================================================

    report = f"""
## ALERT INFORMATION

**Service:** {alert_info.get('service', 'unknown')}
**Status Code:** {alert_info.get('status_code', 0)}
**Error Message:** {alert_info.get('error_message', 'Unknown error')}
**Timestamp:** {alert_info.get('timestamp', 'Unknown')}

---

## INVESTIGATION FINDINGS

"""

    # Add Log Expert analysis
    if log_analysis:
        report += "### Log Expert Analysis:\n\n"
        report += log_analysis[-1]  # Most recent
        report += "\n\n---\n\n"

    # Add Infrastructure Expert analysis
    if infra_analysis:
        report += "### Infrastructure Expert Analysis:\n\n"
        report += infra_analysis[-1]  # Most recent
        report += "\n\n---\n\n"

    # If no specialist findings
    if not log_analysis and not infra_analysis:
        report += "*No detailed findings from specialist agents.*\n\n"
        report += "This may indicate:\n"
        report += "- Investigation was inconclusive\n"
        report += "- Agents reached budget limits\n"
        report += "- Alert was for testing/chaos scenario\n\n"

    # Add supervisor decision summary
    if supervisor_decisions:
        report += "### Investigation Summary:\n\n"
        report += supervisor_decisions[-1]  # Final decision
        report += "\n"

    return report


# ============================================================================
# MEMORY COMMIT NODE
# ============================================================================

def memory_commit_node(state: AlertTeamState) -> Dict[str, Any]:
    """
    Save human-approved RCA to ChromaDB.

    Only executes if state["approved"] == True.
    Stores RCA for future incident retrieval (RAG).

    Args:
        state (AlertTeamState): Current graph state

    Returns:
        dict: Empty (end of graph)
    """
    if not state.get("approved", False):
        logger.info("⊘ Skipping memory commit (RCA not approved)")
        console.print("[dim]RCA not saved to memory (rejected).[/dim]\n")
        return {}

    logger.info("=" * 60)
    logger.info("=== MEMORY COMMIT: Saving RCA to Long-Term Memory ===")
    logger.info("=" * 60)

    rca_report = state.get("rca_report", "")
    alert_info = state["alert_info"]

    # Save to ChromaDB
    success = save_incident(rca_report, alert_info)

    if success:
        logger.info("✓ RCA committed to memory successfully")
        console.print("[bold green]✓ RCA saved to memory. Future incidents will benefit from this knowledge.[/bold green]\n")
    else:
        logger.error("✗ Failed to commit RCA to memory")
        console.print("[bold red]✗ Error saving RCA to memory. Check logs.[/bold red]\n")

    return {}
```

**Key Improvements**:

1. **Rich UI for HITL**:
   - Panel with yellow border (attention-grabbing)
   - Clear options (y/n/e)
   - `Prompt.ask()` with validation

2. **compile_rca_report()**:
   - Extracts findings from both specialists
   - Formats with Markdown
   - Handles case where no findings (budget exhausted)

3. **User Input Handling**:
   - `y` → Approve and save
   - `n` → Reject (don't save)
   - `e` → Edit (placeholder for future)

---

### Step 2: Create Alert Files for Testing (15 minutes)

**Create Directory**: `examples/alerts/`

**File 1**: `examples/alerts/alert_500_zerodivision.json`
```json
{
  "service": "order-service",
  "status_code": 500,
  "error_message": "Internal Server Error",
  "timestamp": "2024-04-30T10:30:00Z",
  "chaos_type": "500_zerodivision"
}
```

**File 2**: `examples/alerts/alert_502_bad_gateway.json`
```json
{
  "service": "order-service",
  "status_code": 502,
  "error_message": "Bad Gateway",
  "timestamp": "2024-04-30T10:32:00Z",
  "chaos_type": "502_bad_gateway"
}
```

**File 3**: `examples/alerts/alert_504_timeout.json`
```json
{
  "service": "order-service",
  "status_code": 504,
  "error_message": "Gateway Timeout",
  "timestamp": "2024-04-30T10:31:00Z",
  "chaos_type": "504_gateway_timeout"
}
```

---

### Step 3: Execute Test 1 - 500 ZeroDivisionError (30 minutes)

**Objective**: Validate happy path (clear error with traceback)

**Test Procedure**:

```bash
# Step 1: Trigger chaos
curl "http://localhost:8001/order?chaos_type=500_zerodivision"
# Expected: 500 Internal Server Error

# Step 2: Run agent
source .venv/bin/activate
python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json

# Step 3: Observe execution
# - Should route to log_expert
# - Should find ZeroDivisionError at /app/app.py:84
# - Should display RCA for approval
# - Type 'y' to approve

# Step 4: Check memory
python -c "from auto_healer.memory import get_memory_stats; print(get_memory_stats())"
# Expected: {"total_incidents": 1}
```

**Expected Results**:

| Metric | Expected Value |
|--------|---------------|
| **Duration** | ~60 seconds |
| **LLM Calls** | 4 (Memory recall, Supervisor×2, Log Expert) |
| **Tool Calls** | 1 (fetch_service_logs) |
| **Agent Consultations** | log_expert: 1, infra_expert: 0 |
| **Iterations** | 4/15 |
| **Outcome** | FINISH → HITL |
| **Exit Code** | 0 (success) |

**RCA Content Should Mention**:
- ✅ Exception type: `ZeroDivisionError`
- ✅ File path: `/app/app.py`
- ✅ Line number: `84` (or similar)
- ✅ Order ID: `c08526cb-...` (chaos trigger ID)
- ✅ Recommended fix: "Remove division by zero" or "Add validation"

**If Test Fails**:

- Agent didn't find error → Check context window (`num_ctx >= 16384`)
- Agent routed to wrong specialist → Check supervisor prompt
- No RCA displayed → Check HITL node implementation
- Memory not saved → Check ChromaDB initialization

---

### Step 4: Execute Test 2 - 502 Bad Gateway (BEFORE Improvements) (30 minutes)

**Objective**: Discover infinite loop issue with ambiguous scenarios

**Test Procedure**:

```bash
# Trigger chaos
curl "http://localhost:8001/order?chaos_type=502_bad_gateway"

# Run agent
python -m auto_healer.main --alert examples/alerts/alert_502_bad_gateway.json

# Observe looping behavior
# (This will take ~6 minutes and hit circuit breaker)
```

**Expected Results (Before Improvements)**:

| Metric | Value |
|--------|-------|
| **Duration** | ~6 minutes |
| **Agent Consultations** | log_expert: 6-7, infra_expert: 6-7 (total: 13) |
| **LLM Calls** | 14+ |
| **Iterations** | 14/15 (circuit breaker!) |
| **Outcome** | ❌ RecursionError |
| **Exit Code** | 1 (failure) |

**Observation Pattern**:
```
Iteration 1: Supervisor → infra_expert
Iteration 2: Infra Expert: "Container healthy"
Iteration 3: Supervisor → log_expert
Iteration 4: Log Expert: "Chaos trigger, no traceback"
Iteration 5: Supervisor → infra_expert (REPEAT!)
Iteration 6: Infra Expert: "Still healthy" (same as #2)
Iteration 7: Supervisor → log_expert (REPEAT!)
...
Iteration 14: Circuit breaker triggered
```

**Root Cause**: Supervisor doesn't recognize evidence plateau!
- Healthy container (no infrastructure issue)
- No Python traceback (chaos exception handled)
- Conflicting signals → Supervisor keeps asking for more evidence

---

### Step 5: Implement Supervisor Improvements (90 minutes)

**Problem Identified**: Supervisor loops on ambiguous scenarios

**Solution**: Add agent consultation budgets

**Update File**: `auto_healer/nodes/supervisor.py`

(This was already shown in Phase 3 lesson, but here's the critical section):

```python
# In supervisor_node function:

# Check budgets (prevents infinite loops)
MAX_AGENT_CONSULTATIONS = 3  # Each agent can be called max 3 times

log_expert_budget_exceeded = agent_counts.get("log_expert", 0) >= MAX_AGENT_CONSULTATIONS
infra_expert_budget_exceeded = agent_counts.get("infra_expert", 0) >= MAX_AGENT_CONSULTATIONS

# Force FINISH if both budgets exhausted
if log_expert_budget_exceeded and infra_expert_budget_exceeded:
    logger.warning("⚠️  Both agent budgets exhausted. Forcing FINISH.")

    budget_exhausted_message = HumanMessage(
        content=f"""Investigation budget exhausted:
- log_expert: {agent_counts.get('log_expert', 0)}/{MAX_AGENT_CONSULTATIONS} consultations
- infra_expert: {agent_counts.get('infra_expert', 0)}/{MAX_AGENT_CONSULTATIONS} consultations

Proceeding to Human-in-the-Loop with findings gathered so far."""
    )

    return {
        "next_worker": "FINISH",
        "messages": [budget_exhausted_message]
    }
```

**Also Enhance Supervisor Prompt** (add to `SUPERVISOR_SYSTEM_PROMPT`):

```python
**When to FINISH:**
1. Root cause clearly identified (file:line, OOM kill, etc.)
2. Both specialists have reported their findings
3. Evidence has plateaued (repeated consultations yield no new information)
4. Both agents consulted max times and evidence is ambiguous

**IMPORTANT - Recognizing Inconclusive Scenarios:**
- Healthy container + no stack traces + handled exceptions = likely chaos/testing scenario
- Repeated agent calls with no new findings = evidence plateaued
- If both agents find "no immediate issues", FINISH with inconclusive summary
- "Unable to determine root cause" is a VALID investigation outcome
```

---

### Step 6: Re-run Test 2 - 502 Bad Gateway (AFTER Improvements) (30 minutes)

**Test Procedure** (same as before):

```bash
curl "http://localhost:8001/order?chaos_type=502_bad_gateway"
python -m auto_healer.main --alert examples/alerts/alert_502_bad_gateway.json
```

**Expected Results (After Improvements)**:

| Metric | Before Budgets | After Budgets | Improvement |
|--------|---------------|---------------|-------------|
| **Duration** | ~6 min | ~5 min | 17% faster |
| **Agent Calls** | 13 | 7 | 46% reduction |
| **LLM Calls** | 14+ | 8 | 43% reduction |
| **Iterations** | 14/15 | 7/15 | 50% reduction |
| **Outcome** | Circuit breaker | FINISH → HITL | ✅ Success |
| **Exit Code** | 1 (error) | 0 (success) | ✅ Clean |

**Consultation Pattern (After)**:
```
Iteration 1: infra_expert #1 → "Container healthy"
Iteration 2: log_expert #1 → "Chaos trigger, no traceback"
Iteration 3: infra_expert #2 → "Still healthy"
Iteration 4: log_expert #2 → "ZeroDivisionError confirmed"
Iteration 5: infra_expert #3 → "No infra issues" (BUDGET LIMIT REACHED)
Iteration 6: log_expert #3 → "Code error identified" (BUDGET LIMIT REACHED)
Iteration 7: Supervisor → FORCED FINISH (both budgets exhausted)
```

**RCA Content**:
```
Root Cause Analysis:
Service: order-service
Error: 502 Bad Gateway

Log Expert Findings:
- Detected ZeroDivisionError at /app/app.py:84
- Chaos injection scenario (intentional error for testing)

Infrastructure Expert Findings:
- Container status: Running (healthy)
- Memory usage: 35.42 MB / 512.00 MB (6.9%)
- No OOM kills, no crashes, no restarts

Conclusion:
This appears to be a chaos/testing scenario. The 502 error was triggered by intentional chaos injection (chaos_type=502_bad_gateway), which causes a ZeroDivisionError that is handled at the application level.

Recommendation:
No action needed if this is testing. If production, investigate why chaos endpoint was triggered.
```

**Validation**: Type 'y' to approve RCA

---

### Step 7: Test Memory Recall (20 minutes)

**Objective**: Verify agent learns from past incidents

**Test Procedure**:

```bash
# Run same 500 error AGAIN (memory now populated from Step 3)
curl "http://localhost:8001/order?chaos_type=500_zerodivision"
python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json --debug

# Watch for memory recall in logs:
# "Memory Recall: Searching for Similar Incidents"
# "Found similar incidents (preview): ..."
```

**Expected Behavior**:

**Memory Recall Output**:
```
**Similar Past Incidents:**

1. [2024-04-30T12:00:00.000000] order-service - 500 (Similarity: 95.2%)
   Root Cause Analysis:
   Service: order-service
   Error: 500 Internal Server Error
   Root Cause: ZeroDivisionError at /app/app.py:84...
```

**Agent Benefits from Memory**:
- Knows to look for ZeroDivisionError
- Knows file path (/app/app.py)
- Knows line number (84)
- Faster investigation (~20-30s vs ~60s)

**Validation**: Check that RCA is similar to first run (agent learned!)

---

## 4.5 Validation Checkpoints

### Checkpoint 1: HITL Node Works

```python
# Test HITL node in isolation
from auto_healer.nodes.hitl import compile_rca_report

# Mock state
state = {
    "alert_info": {"service": "test", "status_code": 500},
    "messages": [
        AIMessage(content="Log analysis here", name="log_expert"),
        AIMessage(content="Infra analysis here", name="infra_expert")
    ]
}

rca = compile_rca_report(state)
print(rca)

# Expected: Formatted report with both analyses
```

### Checkpoint 2: Alert Files Valid

```bash
# Validate JSON
python -c "import json; print(json.load(open('examples/alerts/alert_500_zerodivision.json')))"

# Expected: No errors, displays alert dict
```

### Checkpoint 3: 500 Test Passes

```bash
python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json
# Expected:
# - Execution completes (~60s)
# - RCA displayed
# - Type 'y' to approve
# - Memory count increases to 1
```

### Checkpoint 4: Budget Enforcement Works

```python
# Check agent consultation counts during 502 test
# (Add debug logging to supervisor)

# Expected pattern:
# log_expert: 0 → 1 → 2 → 3 (LIMIT)
# infra_expert: 0 → 1 → 2 → 3 (LIMIT)
# Supervisor: FORCED FINISH
```

### Checkpoint 5: Memory Recall Works

```bash
# After approving RCA in previous test
python -c "from auto_healer.memory import get_memory_stats; print(get_memory_stats())"
# Expected: total_incidents >= 1

# Run same test again
python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json --debug
# Expected: Logs show "Found similar incidents"
```

---

## 4.6 Common Pitfalls

### Pitfall 1: Empty ChromaDB Query Error

**Symptom**:
```
ERROR: Number of requested results 0, cannot be negative, or zero
```

**Cause**: Querying empty ChromaDB collection

**Solution**: (Already handled in Phase 2 `memory.py`)
```python
if collection.count() > 0:
    results = collection.query(...)
else:
    return "No similar past incidents found."
```

### Pitfall 2: Budget Not Incrementing

**Symptom**: Agent loops forever despite budgets

**Cause**: Not copying dict before modifying

**Wrong**:
```python
# Modifies original dict (LangGraph may not detect change)
agent_counts["log_expert"] += 1
return {"agent_consultation_count": agent_counts}
```

**Correct**:
```python
# Create new dict (LangGraph detects change)
agent_counts = state.get("agent_consultation_count", {}).copy()
agent_counts["log_expert"] = agent_counts.get("log_expert", 0) + 1
return {"agent_consultation_count": agent_counts}
```

### Pitfall 3: HITL Blocking Event Loop

**Symptom**: `input()` blocks async operations

**Current Solution**: CLI uses terminal input (acceptable)

**Future**: For async HITL:
```python
# Use websockets for non-blocking HITL
# (Not implemented in this tutorial)
```

### Pitfall 4: RCA Format Inconsistency

**Problem**: Different agents format outputs differently

**Solution**: Standardize with `compile_rca_report()` function

### Pitfall 5: Test Flakiness (Chaos State)

**Symptom**: Tests fail randomly

**Cause**: Previous chaos injection still active in container

**Solution**: Restart services between tests
```bash
docker-compose restart order-service payment-service inventory-service
```

---

## 4.7 Exercises

### Exercise 1: Add Test Coverage Metrics

**Objective**: Track which agents were called, tools used

**Implementation**:
```python
def collect_test_metrics(final_state):
    return {
        "agent_consultations": final_state["agent_consultation_count"],
        "tools_used": [m.content for m in final_state["messages"] if "fetch_service_logs" in m.content or "check_container_health" in m.content],
        "rca_quality": "specific" if "/app/app.py" in final_state.get("rca_report", "") else "generic"
    }
```

### Exercise 2: Implement Edit Flow

**Objective**: When user types 'e', allow editing RCA

**Steps**:
1. Capture edited RCA from user (multiline input)
2. Re-submit edited RCA to memory
3. Test with intentionally wrong agent output

### Exercise 3: Add OOM Kill Scenario

**Objective**: Test infrastructure expert with memory issue

**Steps**:
1. Create new chaos type: `oom_kill` (allocate memory until crash)
2. Modify `check_container_health` to detect exit code 137
3. Run test, verify RCA mentions "OOM" and "memory exhaustion"

### Exercise 4: Memory Similarity Threshold

**Objective**: Only show past incidents above similarity threshold

**Implementation**:
```python
# In query_past_incidents:
filtered_results = [
    (doc, meta, dist) for doc, meta, dist in zip(documents, metadatas, distances)
    if dist <= (2.0 - similarity_threshold)  # e.g., threshold=0.7
]
```

---

## 4.8 Key Takeaways

### ✅ What You Learned

1. **End-to-End Testing for Multi-Agent Systems**
   - Test all error scenarios (500, 502, 504)
   - Measure accuracy, efficiency, termination
   - Discover edge cases through real execution

2. **Human-in-the-Loop Approval Workflows**
   - Prevents autonomous mistakes
   - Quality control on learning data
   - Only store good RCAs in memory

3. **Debugging Agent Behavior**
   - Observe execution patterns
   - Identify infinite loops
   - Measure performance metrics

4. **Iterative Improvement Based on Testing**
   - Discovered supervisor indecision on ambiguous scenarios
   - Implemented agent consultation budgets
   - Reduced agent calls by 46%, duration by 17%

5. **RAG Memory Validation**
   - Semantic search retrieves similar incidents
   - Agent benefits from historical context
   - Faster investigations with populated memory

### 📊 Test Results Summary

**Test 1 (500 ZeroDivisionError)**: ✅
- Duration: 60s
- LLM calls: 4
- Tool calls: 1
- Iterations: 4/15
- Outcome: Perfect RCA with exact file:line

**Test 2 (502 Bad Gateway, Before)**: ⚠️
- Duration: 6min
- LLM calls: 14+
- Agent consultations: 13
- Iterations: 14/15
- Outcome: Circuit breaker (error)

**Test 2 (502 Bad Gateway, After)**: ✅
- Duration: 5min
- LLM calls: 8
- Agent consultations: 7
- Iterations: 7/15
- Outcome: Clean FINISH → HITL

### 🎯 Production-Ready Aspects

- ✅ Comprehensive error coverage
- ✅ Budget enforcement prevents runaway costs
- ✅ HITL prevents autonomous mistakes
- ✅ Memory enables learning from incidents
- ✅ Rich terminal UI for professional UX
- ✅ Metrics collection for monitoring

### 🔍 Critical Insights

**Q: How did you discover the supervisor loop issue?**
A: Real testing - 502 test ran for 6 minutes and hit circuit breaker. Investigation revealed repeated consultations with no new findings.

**Q: Why is "inconclusive" a valid outcome?**
A: Some scenarios are genuinely ambiguous (healthy container + chaos testing). Agent should recognize this instead of looping forever.

**Q: What's the most important metric?**
A: Agent consultations (per-agent budget). Prevents diminishing returns when evidence plateaus.

---

## 4.9 Next Steps

### Phase 5 Preview: Production Polish

Now that the system works end-to-end, polish for open source release:

**What You'll Build**:
- Type checking (mypy)
- Unit tests (pytest)
- Code formatting (ruff/black)
- Comprehensive README
- Pre-commit hooks

**Why It Matters**:
- Production code needs maintainability
- Tests prevent regressions
- Documentation enables adoption

**Bridge to Phase 5**:
You've validated the system works. Now make it maintainable and shareable.

**Recommended Next Action**:
Proceed to `LESSON_PHASE5.md` for production polish.

---

**End of Phase 4 Lesson**

✅ End-to-end testing complete
✅ HITL approval workflow working
✅ Supervisor improvements implemented
✅ Memory recall validated
✅ Ready for Phase 5: Production Polish
