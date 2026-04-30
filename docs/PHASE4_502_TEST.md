# Phase 4: Test 2 - 502 Bad Gateway Scenario

## Summary

**Status**: ⚠️ Circuit Breaker Triggered  
**Date**: 2026-04-30  
**Test Type**: Multi-Agent Collaboration & Circuit Breaker Validation

---

## Test Scenario

**Alert**: `examples/alerts/alert_502_bad_gateway.json`  
**Service**: order-service  
**Error Type**: 502 Bad Gateway  
**Root Cause**: Simulated upstream service failure (HTTPException)

```python
# From dummy_services/order/app.py:102
raise HTTPException(status_code=502, detail="Bad Gateway - Upstream service failure")
```

---

## Test Results

### ✅ Multi-Agent Collaboration Validated

**Workflow Execution:**

| Iteration | Agent | Finding |
|-----------|-------|---------|
| 1 | Supervisor | Routed to `infra_expert` (502 = infrastructure issue) |
| 2 | Infra Expert | Container health: running, no OOM, no restarts |
| 3 | Supervisor | Routed to `log_expert` (check for connection errors) |
| 4 | Log Expert | Found chaos trigger log, no Python traceback |
| 5 | Supervisor | Routed to `log_expert` again (verify exception) |
| 6 | Log Expert | Re-fetched logs, confirmed HTTPException |
| 7 | Supervisor | Routed to `infra_expert` (502 typically = infra) |
| 8 | Infra Expert | Re-checked health, still running normally |
| 9-13 | Multiple | Continued alternating between agents |
| **14** | **Circuit Breaker** | **Recursion limit reached (15 iterations)** |

**Workers Consulted**: 13  
**Total Duration**: ~6 minutes  
**LLM Calls**: 14+  
**Tool Calls**: 8+ (fetch_service_logs, check_container_health)

---

## Key Findings

### ✅ Circuit Breaker Working Perfectly

```
❌ Error: Graph exceeded maximum iterations (15)
The agent may be stuck in a loop. Try increasing --max-iterations or check logs.
```

**Why this is good:**
- Prevented infinite loop
- Controlled failure with clear error message
- Exit code 1 (graceful shutdown)
- No resource exhaustion or hanging process

### ✅ Multi-Agent Collaboration Demonstrated

The Supervisor correctly:
- Routed to **infra_expert first** (502 errors typically = infrastructure)
- Routed to **log_expert second** (check for application-level evidence)
- **Alternated between both agents** seeking conclusive evidence
- Made reasoned decisions at each step (see reasoning logs)

**Sample Supervisor Decisions:**
```
[17:35:08] Supervisor decision: infra_expert
Reasoning: 502 Bad Gateway typically indicates an issue with upstream services or infrastructure.

[17:35:43] Supervisor decision: log_expert  
Reasoning: Initial infrastructure check shows no immediate issues; further analysis of logs for connection errors is needed.

[17:40:40] Supervisor decision: infra_expert
Reasoning: Initial analysis suggests a code-level issue, but 502 errors typically indicate infrastructure problems. Need to check for upstream service issues first.
```

### ⚠️ Supervisor Indecision Issue

**Root Cause of Looping:**

The 502 chaos scenario presents **ambiguous evidence**:

| Evidence Type | What Agents Found | Decision Impact |
|---------------|-------------------|-----------------|
| **Container Health** | ✅ Status: running<br>✅ No OOM kills<br>✅ No restarts | Infra Expert: "No immediate issues" |
| **Application Logs** | ⚠️ Chaos trigger logged<br>❌ No Python traceback<br>❌ No stack trace | Log Expert: "HTTPException raised, but no code-level bug" |
| **Error Classification** | 502 = infrastructure<br>But: HTTPException = code-level | Supervisor: Conflicting signals |

**Why the Supervisor couldn't decide FINISH:**

Unlike the 500 ZeroDivisionError test where:
- ✅ Clear Python traceback with file:line
- ✅ Obvious code bug (`1 / 0`)
- ✅ Definitive root cause → FINISH

The 502 HTTPException scenario shows:
- ⚠️ No stack trace (handled exception)
- ⚠️ Healthy container (no infra red flags)
- ⚠️ Intentional error (chaos injection, not a real bug)
- ❓ **No actionable fix identified**

The LLM kept seeking more evidence because it couldn't form a conclusive RCA.

---

## Architecture Insights

### Pattern: Reflection Without Resolution

This test demonstrates a **known limitation** in agentic systems:

> **When evidence is ambiguous or contradictory, ReAct agents may loop seeking conclusive data.**

The Supervisor's reasoning shows intelligent reflection:
1. "Infrastructure typically causes 502" → check infra
2. "Infra looks healthy" → check logs
3. "Logs show exception but no bug" → re-check infra
4. "Still healthy" → re-check logs
5. *...continues until circuit breaker*

**This is working as designed** - the circuit breaker prevents runaway costs/time.

### Solution Approaches

**Option 1: Lower FINISH threshold**
- Update Supervisor prompt: "If both agents find no critical issues, FINISH with 'Unable to determine root cause' RCA"
- Pro: Completes investigation faster
- Con: May produce less actionable RCAs

**Option 2: Add confidence scoring**
- Agents return confidence level (0-100)
- Supervisor triggers FINISH when confidence > threshold OR iterations > limit
- Pro: More nuanced decision-making
- Con: Adds complexity to state schema

**Option 3: Iteration budget per agent**
- Track per-agent consultations (e.g., max 3 log_expert calls)
- Force FINISH if budget exhausted
- Pro: Prevents single-agent spam
- Con: May cut off valid investigations

**Option 4: Human-in-the-Loop earlier**
- Trigger HITL at iteration 10 with "Investigation inconclusive - need human input"
- Pro: Leverages human judgment for edge cases
- Con: More user interruptions

**Recommendation**: Implement Option 1 + Option 3 combination:
- Allow max 3 consultations per agent type
- Update Supervisor to accept "inconclusive" as valid FINISH state

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Execution Time** | ~6 minutes | Until circuit breaker |
| **LLM Inference Calls** | 14+ | Supervisor + Agents |
| **Tool Executions** | 8+ | fetch_logs ×6, check_health ×2 |
| **Recursion Depth** | 14 / 15 limit | Hit circuit breaker |
| **Worker Consultations** | 13 | Alternating between agents |
| **Outcome** | Circuit breaker triggered | Controlled failure |

---

## What Worked ✅

1. **Circuit Breaker**: Prevented infinite loop, graceful shutdown
2. **Multi-Agent Routing**: Supervisor correctly identified both agents could contribute
3. **Tool Calling**: All 8+ tool calls succeeded (no errors)
4. **Reasoning Quality**: Supervisor explanations were logical and domain-appropriate
5. **Structured Outputs**: No routing hallucinations (always valid agent names)
6. **Context Window**: 16K context handled multiple iterations without truncation

---

## What Needs Improvement ⚠️

1. **FINISH Decision Logic**
   - Supervisor needs guidance for ambiguous scenarios
   - Should recognize when evidence plateaus
   - Missing "inconclusive investigation" pathway

2. **Agent Consultation Budget**
   - No limit on per-agent calls
   - Log Expert was called 6 times with diminishing returns
   - Should cap consultations per agent type

3. **Evidence Synthesis**
   - Agents don't cross-reference each other's findings explicitly
   - Supervisor doesn't summarize cumulative evidence
   - Missing "We've checked X, Y, Z and found nothing" logic

4. **Error Type Classification**
   - 502 errors have different patterns (infra vs code-generated)
   - Could benefit from pre-routing heuristics
   - Simple HTTPException ≠ real upstream failure

---

## Comparison: 500 vs 502 Tests

| Aspect | Test 1: 500 Error | Test 2: 502 Error |
|--------|-------------------|-------------------|
| **Root Cause** | ZeroDivisionError | HTTPException (chaos) |
| **Log Evidence** | ✅ Full Python traceback | ❌ No traceback |
| **Infra Evidence** | ✅ Container running | ✅ Container running |
| **Agents Used** | log_expert only | Both agents |
| **Iterations** | 4 / 15 | 14 / 15 |
| **Outcome** | ✅ FINISH → HITL | ❌ Circuit breaker |
| **RCA Quality** | Excellent (file:line) | N/A (no RCA generated) |
| **Duration** | ~60 seconds | ~6 minutes |

**Key Takeaway**: Agent performs excellently on **clear failures** (stack traces, OOM kills, crashes) but struggles with **ambiguous errors** (handled exceptions, chaos injection).

---

## Next Steps

### Immediate:
- [ ] Implement per-agent consultation budget (max 3 calls)
- [ ] Update Supervisor prompt to handle "inconclusive" cases
- [ ] Add HITL trigger at iteration 10 for user guidance

### Testing:
- [ ] Test 504 Gateway Timeout (different pattern from 502)
- [ ] Test memory recall (run same alert twice)
- [ ] Test with real upstream service down (not chaos injection)

### Documentation:
- [ ] Add "Agent Limitations" section to README
- [ ] Document circuit breaker behavior
- [ ] Create troubleshooting guide for loops

---

## Conclusion

✅ **Phase 4 Test 2 Successfully Validated Critical Behaviors:**

1. **Multi-Agent Collaboration**: Supervisor successfully orchestrated both specialists
2. **Circuit Breaker**: Prevented infinite loops with graceful failure
3. **Tool Calling**: All tool executions succeeded without errors
4. **Reasoning Quality**: Supervisor made intelligent routing decisions

⚠️ **Identified Improvement Opportunities:**

1. **Ambiguous Evidence Handling**: Need better "inconclusive investigation" logic
2. **Consultation Budgets**: Prevent excessive agent calls with diminishing returns
3. **FINISH Threshold**: Define when "enough investigation" is enough

**Overall Assessment**: The multi-agent architecture is sound. The looping behavior is a **feature** (thorough investigation) that needs **guardrails** (consultation budgets, inconclusive pathways) to prevent over-investigation.

**System Status**: Ready for supervisor prompt tuning and budget implementation.
