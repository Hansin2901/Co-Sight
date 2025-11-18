# Manus Tracing Implementation Plan

## Overview

This document outlines the detailed implementation plan for integrating Langfuse + OpenTelemetry tracing into the Manus agent system. The implementation will enable distributed tracing of LLM calls, tool executions, parallel agent operations, and plan execution while maintaining proper session context across concurrent threads.

**Source Document**: `MANUS_TRACING_IMPLEMENTATION_GUIDE.md`
**Branch**: `claude/manus-implementation-plan-01YJuJti1s89Eo4zpQ5RByqp`
**Base Branch**: `claude/organize-eval-files-01U8zinrTDdpFD8FZxBAYMyj`

---

## Implementation Phases

### Phase 1: Setup and Dependencies

#### Task 1.1: Add Dependencies to requirements.txt
**File**: `requirements.txt`
**Action**: Add the following packages:
```text
langfuse
opentelemetry-instrumentation-threading
```

**Purpose**:
- `langfuse`: Official Langfuse Python SDK for tracing
- `opentelemetry-instrumentation-threading`: Enables trace context propagation to child threads (CRITICAL for parallel execution)

#### Task 1.2: Update .env Template
**File**: `.env` (or `.env.example`)
**Action**: Add Langfuse configuration section:
```bash
# ===== LangFuse Observability Configuration =====
# Enable/disable tracing (set to 'true' to enable)
ENABLE_LANGFUSE=false

# LangFuse Cloud Setup (required if ENABLE_LANGFUSE=true)
# Sign up at: https://cloud.langfuse.com to get your API keys
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Optional: Custom trace settings
LANGFUSE_RELEASE=v1.0.0
LANGFUSE_ENVIRONMENT=development
```

---

### Phase 2: Core Infrastructure

#### Task 2.1: Create Langfuse Configuration Module
**File**: `app/manus/llm/langfuse_config.py`
**Action**: Create new file with complete implementation from guide

**Key Components**:
1. **Global client management**: Singleton pattern for Langfuse client
2. **Initialization function**: `initialize_langfuse()` with ThreadingInstrumentor setup
3. **Utility functions**:
   - `is_langfuse_enabled()`: Check if tracing is enabled
   - `get_langfuse_client()`: Get client instance
   - `shutdown_langfuse()`: Flush and cleanup
4. **Fallback decorator**: `observe_fallback()` for when Langfuse is disabled
5. **Export observe**: Conditional import of `@observe` decorator

**Critical Features**:
- ThreadingInstrumentor initialization for context propagation
- Graceful degradation when disabled
- Clear logging for debugging
- Error handling for missing credentials

---

### Phase 3: LLM Integration

#### Task 3.1: Modify ChatLLM - Add Session Support
**File**: `app/manus/llm/chat_llm.py`

**Changes in `__init__`**:
1. Add imports:
```python
from app.manus.llm.langfuse_config import is_langfuse_enabled, observe, get_langfuse_client
try:
    from langfuse.openai import openai as langfuse_openai
    LANGFUSE_OPENAI_AVAILABLE = True
except ImportError:
    LANGFUSE_OPENAI_AVAILABLE = False
```

2. Add `session_id` attribute:
```python
self.session_id = None
```

3. Wrap OpenAI client with Langfuse instrumentation:
```python
if is_langfuse_enabled() and LANGFUSE_OPENAI_AVAILABLE:
    try:
        self.client = langfuse_openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=client._client
        )
        print(f"[LangFuse] ✅ ChatLLM using instrumented OpenAI client")
    except Exception as e:
        print(f"[LangFuse] ⚠️  Failed to wrap OpenAI client: {e}")
        self.client = client
else:
    self.client = client
```

#### Task 3.2: Add Tracing Decorators to LLM Methods
**File**: `app/manus/llm/chat_llm.py`

**Changes to `create_with_tools()`**:
1. Add `@observe(name="llm_create_with_tools")` decorator
2. Add trace update at beginning of method:
```python
if is_langfuse_enabled():
    try:
        trace_params = {
            "metadata": {
                "model": self.model,
                "temperature": self.temperature,
                "tools_count": len(tools),
                "base_url": self.base_url
            }
        }
        if self.session_id:
            trace_params["session_id"] = self.session_id
        get_langfuse_client().update_current_trace(**trace_params)
    except Exception as e:
        print(f"[LangFuse] Failed to update trace: {e}")
```

**Changes to `chat_to_llm()`**:
1. Add `@observe(name="llm_chat_to_llm")` decorator
2. Add similar trace update logic with appropriate metadata

---

### Phase 4: Plan Management

#### Task 4.1: Add Session ID to Plan Class
**File**: `app/manus/task/todolist.py`

**Changes in `Plan.__init__`**:
Add session_id generation:
```python
# NEW: Add session_id for tracing
# Each Plan instance gets a unique session ID
self.session_id = f"manus-task-{id(self)}"
```

**Purpose**: Each Plan instance gets a unique session ID that will group all related traces together

---

### Phase 5: Manus Core Integration

#### Task 5.1: Propagate Session ID in Manus.__init__
**File**: `app/manus/manus.py`

**Add import**:
```python
from app.manus.llm.langfuse_config import is_langfuse_enabled, observe, get_langfuse_client
```

**Changes in `__init__`**:
After LLM initialization, add:
```python
# NEW: Propagate session_id to all LLM instances
if is_langfuse_enabled():
    try:
        if hasattr(plan_llm, 'session_id'):
            plan_llm.session_id = self.plan.session_id
        if hasattr(act_llm, 'session_id'):
            act_llm.session_id = self.plan.session_id
        if hasattr(tool_llm, 'session_id'):
            tool_llm.session_id = self.plan.session_id
        if hasattr(vision_llm, 'session_id'):
            vision_llm.session_id = self.plan.session_id
        print(f"[LangFuse] 📊 Session ID set for Manus: {self.plan.session_id}")
    except Exception as e:
        print(f"[LangFuse] Warning: Failed to set session_id: {e}")
```

#### Task 5.2: Add Tracing to Manus.execute()
**File**: `app/manus/manus.py`

**Changes**:
1. Add `@observe(name="manus_execute")` decorator
2. Add trace initialization at beginning:
```python
if is_langfuse_enabled():
    try:
        get_langfuse_client().update_current_trace(
            session_id=self.plan.session_id,
            name=f"Manus: {question[:60]}...",
            metadata={
                "question": question,
                "output_format": output_format,
                "plan_id": self.plan_id,
                "task_type": "research"
            },
            tags=["manus-task", "session-start"]
        )
        print(f"[LangFuse] 📊 Manus execution started: {self.plan.session_id}")
    except Exception as e:
        print(f"[LangFuse] Failed to set session: {e}")
```

#### Task 5.3: Add Tracing to Manus.execute_actor()
**File**: `app/manus/manus.py`

**Changes**:
Add `@observe(name="manus_execute_actor")` decorator to method

#### Task 5.4: Add Tracing to Manus.execute_steps()
**File**: `app/manus/manus.py`

**Changes**:
1. Add `@observe(name="manus_execute_steps_parallel")` decorator
2. Inside `execute_step()` inner function, add span metadata:
```python
if is_langfuse_enabled():
    try:
        get_langfuse_client().update_current_span(
            name=f"execute_step_{step_index}",
            metadata={
                "step_index": step_index,
                "step_description": self.plan.steps[step_index] if step_index < len(self.plan.steps) else "unknown"
            }
        )
    except Exception as e:
        print(f"[LangFuse] Failed to update step span: {e}")
```

**Purpose**: This enables proper tracing of parallel step execution with context propagation via ThreadingInstrumentor

---

### Phase 6: Agent Tracing

#### Task 6.1: Add Tracing to TaskPlannerAgent
**File**: `app/manus/agent/planner/task_plannr_agent.py`

**Changes**:
1. Add import: `from app.manus.llm.langfuse_config import observe`
2. Add `@observe` decorator to:
   - `create_plan()` → `@observe(name="planner_create_plan")`
   - `re_plan()` → `@observe(name="planner_re_plan")`
   - `finalize_plan()` → `@observe(name="planner_finalize")`
   - `create_fact()` → `@observe(name="planner_create_fact")` (if present)

#### Task 6.2: Add Tracing to TaskActorAgent
**File**: `app/manus/agent/actor/task_actor_agent.py`

**Changes**:
1. Add import: `from app.manus.llm.langfuse_config import observe`
2. Add `@observe` decorator to:
   - `act()` → `@observe(name="actor_act")`
   - `single_act()` → `@observe(name="actor_single_act")`

**Optional Enhancement**: Add tool execution tracing by decorating tool call methods

---

### Phase 7: Evaluation Scripts Integration

#### Task 7.1: Update cosight_evals.py
**File**: `cosight_evals.py`

**Changes**:
1. Add imports at top:
```python
import atexit
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
```

2. Add initialization in `if __name__ == '__main__':` section:
```python
# NEW: Initialize Langfuse observability
print("\n=== Langfuse Observability Setup ===")
initialize_langfuse()
print("=== Langfuse Setup Complete ===\n")

# NEW: Register shutdown handler to flush traces
atexit.register(shutdown_langfuse)
```

#### Task 7.2: Update cosight_evals_ChineseSimpleQA.py
**File**: `cosight_evals_ChineseSimpleQA.py`

**Changes**: Same as Task 7.1 - add initialization and shutdown handlers

#### Task 7.3: Update cosight_evals_hle.py
**File**: `cosight_evals_hle.py`

**Changes**: Same as Task 7.1 - add initialization and shutdown handlers

---

### Phase 8: Testing and Validation

#### Task 8.1: Test with Tracing Disabled
**Environment**: `ENABLE_LANGFUSE=false` in `.env`

**Testing Steps**:
1. Run `python cosight_evals.py` (or other eval scripts)
2. Verify:
   - ✅ No Langfuse initialization messages appear
   - ✅ Application runs normally without errors
   - ✅ No performance degradation
   - ✅ No ImportError or AttributeError related to Langfuse

**Expected Output**:
```
[LangFuse] ℹ️  Tracing disabled (ENABLE_LANGFUSE=false)
```

#### Task 8.2: Test with Tracing Enabled
**Environment**: `ENABLE_LANGFUSE=true` + valid credentials in `.env`

**Testing Steps**:
1. Set up Langfuse credentials in `.env`
2. Run `python cosight_evals.py`
3. Verify console output shows:
   - ✅ ThreadingInstrumentor initialization
   - ✅ Langfuse client initialization
   - ✅ ChatLLM instrumentation messages
   - ✅ Session ID assignment messages
   - ✅ Trace upload and flush messages

**Expected Output**:
```
=== Langfuse Observability Setup ===
[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads
[LangFuse] ✅ Initialized successfully
[LangFuse]    Host: https://cloud.langfuse.com
[LangFuse]    Environment: development
=== Langfuse Setup Complete ===

[LangFuse] ✅ ChatLLM using instrumented OpenAI client
[LangFuse] 📊 Session ID set for Manus: manus-task-140234567890123
[LangFuse] 📊 Manus execution started: manus-task-140234567890123
...
[LangFuse] 📤 Flushing pending traces...
[LangFuse] ✅ Shutdown complete
```

#### Task 8.3: Verify in Langfuse Dashboard
**Location**: https://cloud.langfuse.com

**Validation Checklist**:
- [ ] Traces appear in dashboard
- [ ] Session grouping works (all traces share same session_id)
- [ ] Span hierarchy is correct:
  - Root: `manus_execute`
  - Children: `planner_create_plan`, `execute_steps_parallel`, etc.
  - Parallel steps: Multiple `execute_step_X` under `execute_steps_parallel`
- [ ] LLM calls tracked with:
  - Token counts
  - Model names
  - Latencies
  - Costs (if available)
- [ ] Metadata captured:
  - Question text
  - Plan ID
  - Step descriptions
- [ ] No orphaned traces (all spans properly nested)
- [ ] Thread context propagation working (parallel steps nested under parent)

---

### Phase 9: Documentation

#### Task 9.1: Create Implementation Summary
**File**: `MANUS_IMPLEMENTATION_SUMMARY.md`

**Contents**:
1. **Overview**: What was implemented
2. **Files Modified**: List with brief description of changes
3. **Files Created**: New files with purpose
4. **Testing Results**:
   - Test with ENABLE_LANGFUSE=false
   - Test with ENABLE_LANGFUSE=true
   - Dashboard validation results
5. **Usage Instructions**: How to enable/disable tracing
6. **Troubleshooting**: Common issues and solutions
7. **Next Steps**: Potential enhancements (tool tracing, custom metrics, alerts)

---

## Implementation Order

Execute tasks in this specific order to minimize integration issues:

1. **Phase 1** (Setup): Tasks 1.1, 1.2
2. **Phase 2** (Core Infrastructure): Task 2.1
3. **Phase 4** (Plan Management): Task 4.1 *(before Phase 3 to have session_id available)*
4. **Phase 3** (LLM Integration): Tasks 3.1, 3.2
5. **Phase 5** (Manus Core): Tasks 5.1, 5.2, 5.3, 5.4
6. **Phase 6** (Agent Tracing): Tasks 6.1, 6.2
7. **Phase 7** (Evaluation Scripts): Tasks 7.1, 7.2, 7.3
8. **Phase 8** (Testing): Tasks 8.1, 8.2, 8.3
9. **Phase 9** (Documentation): Task 9.1

---

## Key Success Criteria

### Functional Requirements
✅ Tracing works when enabled
✅ No errors when disabled
✅ Session grouping groups all operations for one task
✅ Parallel execution maintains trace hierarchy
✅ LLM calls automatically tracked
✅ Graceful degradation if Langfuse unavailable

### Performance Requirements
✅ < 5% overhead when tracing enabled
✅ Zero overhead when tracing disabled
✅ No blocking on trace upload (async flushing)

### Observability Requirements
✅ Each Manus.execute() = one session
✅ All LLM calls, steps, and agents nested under session
✅ Token usage and costs tracked
✅ Step-level visibility
✅ Parallel thread visibility

---

## Troubleshooting Quick Reference

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| ThreadingInstrumentor warning | Package not installed | `pip install opentelemetry-instrumentation-threading` |
| Parallel steps not nested | ThreadingInstrumentor not initialized | Call `initialize_langfuse()` before creating threads |
| Session grouping not working | session_id not set on trace | Use `update_current_trace(session_id=...)` |
| No traces in dashboard | Credentials invalid or flush not called | Check credentials, ensure `shutdown_langfuse()` called |
| ImportError for langfuse | Package not installed | `pip install langfuse` |

---

## Files to Modify/Create

### New Files (1)
- `app/manus/llm/langfuse_config.py`

### Modified Files (9)
1. `requirements.txt`
2. `.env` (template)
3. `app/manus/llm/chat_llm.py`
4. `app/manus/task/todolist.py`
5. `app/manus/manus.py`
6. `app/manus/agent/planner/task_plannr_agent.py`
7. `app/manus/agent/actor/task_actor_agent.py`
8. `cosight_evals.py`
9. `cosight_evals_ChineseSimpleQA.py`
10. `cosight_evals_hle.py`

### Documentation Files (1)
- `MANUS_IMPLEMENTATION_SUMMARY.md` (to be created)

---

## Timeline Estimate

- **Phase 1**: 15 minutes
- **Phase 2**: 30 minutes
- **Phase 3**: 45 minutes
- **Phase 4**: 10 minutes
- **Phase 5**: 60 minutes
- **Phase 6**: 30 minutes
- **Phase 7**: 20 minutes
- **Phase 8**: 60 minutes (including dashboard verification)
- **Phase 9**: 30 minutes

**Total Estimated Time**: ~5 hours

---

## Next Steps After Implementation

1. **Tool Execution Tracing**: Add `@observe` decorators to individual tool executions
2. **Custom Metrics**: Track plan success rates, step retry counts, etc.
3. **Alerts**: Set up Langfuse alerts for:
   - High-cost queries (> threshold)
   - Failed executions
   - Slow responses (> latency threshold)
4. **Sampling**: Implement sampling for production (e.g., trace 10% of requests)
5. **Dashboard**: Create custom Langfuse dashboard for Manus-specific metrics
6. **Cost Optimization**: Analyze token usage patterns and optimize prompts

---

**End of Implementation Plan**

This plan provides a clear roadmap for implementing comprehensive tracing in the Manus system. Follow the phases in order, test thoroughly at each stage, and refer to the original guide for detailed code examples.
