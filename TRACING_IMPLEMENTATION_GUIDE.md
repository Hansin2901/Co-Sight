# Tracing Implementation Guide: Langfuse + OpenTelemetry

## Executive Summary

This document provides a comprehensive guide to implementing distributed tracing in the CoSight application using **Langfuse** and **OpenTelemetry**. The implementation enables monitoring of LLM calls, tool executions, and parallel agent operations while maintaining proper session context across concurrent threads.

**Key Achievement**: Each research task is tracked as a single unified trace/session, with all LLM calls, tool executions, and parallel agent operations properly nested and contextualized.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Dependencies](#core-dependencies)
3. [Configuration System](#configuration-system)
4. [Langfuse Integration](#langfuse-integration)
5. [OpenTelemetry Integration](#opentelemetry-integration)
6. [Session Management](#session-management)
7. [Parallel Agent & Tool Call Handling](#parallel-agent--tool-call-handling)
8. [Implementation Checklist](#implementation-checklist)
9. [Code Examples](#code-examples)
10. [Troubleshooting](#troubleshooting)

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Entry Point                  │
│                  (cosight_server/deep_research/main.py)     │
│                                                             │
│  1. Load .env configuration                                │
│  2. Initialize Langfuse client (initialize_langfuse())     │
│  3. Register shutdown handler (atexit.register)            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      CoSight.py                             │
│                   (Main Orchestrator)                        │
│                                                             │
│  @observe(name="research_task")                            │
│  def execute(self, question):                              │
│    - Create unique session_id per research task            │
│    - Set session_id on all LLM instances                   │
│    - Manage parallel step execution                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├──────────────────┬────────────────────┐
                  ▼                  ▼                    ▼
        ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
        │  TaskPlanner     │ │  TaskActor   │ │  TaskActor       │
        │  Agent           │ │  Agent       │ │  Agent           │
        │                  │ │  (Thread 1)  │ │  (Thread 2)      │
        │  - ChatLLM       │ │  - ChatLLM   │ │  - ChatLLM       │
        │    (session_id)  │ │    (session) │ │    (session)     │
        └────────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
                 │                  │                   │
                 ▼                  ▼                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │              ChatLLM (Langfuse-wrapped)                │
        │                                                         │
        │  @observe(name="llm_create_with_tools")                │
        │  - Wraps OpenAI client with langfuse_openai.OpenAI()  │
        │  - Propagates session_id to traces                     │
        │  - Tracks token usage, costs, latency                  │
        └────────────────────┬────────────────────────────────────┘
                             │
                             ▼
        ┌─────────────────────────────────────────────────────────┐
        │              BaseAgent (Tool Executor)                 │
        │                                                         │
        │  @observe(name="tool_execution")                       │
        │  def _execute_tool_call():                             │
        │    - Executes tools with tracing metadata              │
        │    - ThreadPoolExecutor for parallel tool calls        │
        │    - Updates spans with results                        │
        └─────────────────────────────────────────────────────────┘
```

### 1.2 Key Components

| Component | Purpose | File Location |
|-----------|---------|---------------|
| **Langfuse Config** | Initialize Langfuse client, provide decorators | `app/cosight/llm/langfuse_config.py` |
| **ChatLLM** | Wrap OpenAI client with Langfuse instrumentation | `app/cosight/llm/chat_llm.py` |
| **BaseAgent** | Execute tools with tracing | `app/cosight/agent/base/base_agent.py` |
| **CoSight** | Orchestrate sessions and parallel execution | `CoSight.py` |
| **Plan** | Manage session IDs per research task | `app/cosight/task/todolist.py` |

---

## 2. Core Dependencies

### 2.1 Required Packages

Add to `requirements.txt`:

```text
langfuse
opentelemetry-instrumentation-threading
```

### 2.2 Dependency Explanation

- **`langfuse`**: Official Langfuse Python SDK
  - Provides `@observe` decorator for tracing
  - Wraps OpenAI client for automatic LLM call tracking
  - Manages trace context and span hierarchy

- **`opentelemetry-instrumentation-threading`**: OpenTelemetry Threading Instrumentation
  - **CRITICAL**: Enables trace context propagation to child threads
  - Without this, parallel tool calls would lose session context
  - Automatically instruments Python's `threading` module

### 2.3 Installation

```bash
pip install langfuse opentelemetry-instrumentation-threading
# or
uv add langfuse opentelemetry-instrumentation-threading
```

---

## 3. Configuration System

### 3.1 Environment Variables

Create or update `.env` file:

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

### 3.2 Configuration Checks

The application should validate configuration at startup:

```python
# In main.py (application entry point)
from dotenv import load_dotenv
load_dotenv()

# Check required environment variables
env_vars = ["ENABLE_LANGFUSE"]
for var in env_vars:
    value = os.getenv(var)
    if value:
        logger.info(f"✓ {var} = {value}")
    else:
        logger.info(f"ℹ {var} not set (optional)")
```

---

## 4. Langfuse Integration

### 4.1 Core Configuration Module

**File**: `app/cosight/llm/langfuse_config.py`

This module provides:
1. Centralized Langfuse client initialization
2. Feature toggle via environment variable
3. Graceful degradation if Langfuse unavailable
4. ThreadingInstrumentor setup for parallel context propagation

**Key Functions**:

```python
def is_langfuse_enabled() -> bool:
    """Check if LangFuse is enabled via ENABLE_LANGFUSE env var"""

def initialize_langfuse() -> Optional[any]:
    """Initialize LangFuse client with credentials and ThreadingInstrumentor"""

def get_langfuse_client():
    """Get the initialized LangFuse client instance"""

def shutdown_langfuse():
    """Flush pending traces before shutdown"""

def observe_fallback(*args, **kwargs):
    """Fallback no-op decorator when LangFuse is disabled"""
```

### 4.2 ThreadingInstrumentor Setup

**CRITICAL COMPONENT** for parallel execution:

```python
# In langfuse_config.py initialize_langfuse()
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

try:
    ThreadingInstrumentor().instrument()
    logger.info("[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads")
except ImportError:
    logger.warning("[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed")
    logger.warning("[LangFuse] Threading context propagation may not work correctly")
```

**Why This Matters**:
- Without ThreadingInstrumentor, child threads lose trace context
- Each parallel agent/tool would create separate unrelated traces
- Session grouping would fail
- Parent-child span relationships would break

### 4.3 Fallback Decorator Pattern

Ensures code works even without Langfuse:

```python
# Import pattern used throughout codebase
try:
    from langfuse import observe, get_client
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    observe = observe_fallback  # No-op decorator
    get_client = lambda: None
```

**Usage in code**:
```python
@observe(name="my_function")  # Works whether Langfuse is available or not
def my_function():
    pass
```

### 4.4 Application Lifecycle Integration

**Initialization** (in `main.py`):

```python
# Initialize LangFuse Observability
logger.info("\n=== LangFuse Observability Setup ===")
from app.cosight.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
initialize_langfuse()
logger.info("=== LangFuse Setup Complete ===\n")
```

**Shutdown** (in `main.py`):

```python
# Register shutdown handler for LangFuse
import atexit
atexit.register(shutdown_langfuse)

# Then start server
uvicorn.run(app=app, host="0.0.0.0", port=int(args.port))
```

---

## 5. OpenTelemetry Integration

### 5.1 Threading Context Propagation

OpenTelemetry's `ThreadingInstrumentor` automatically:
1. Captures trace context from parent thread
2. Propagates context to child threads
3. Maintains span hierarchy across thread boundaries

**How It Works**:

```python
# Parent thread has trace context
@observe(name="research_task")
def execute(self, question):
    # Trace context exists here

    # Create child thread
    thread = Thread(target=self._execute_single_step, args=(question, step_index))
    thread.start()  # ThreadingInstrumentor automatically propagates context

# Child thread receives context
def _execute_single_step(self, question, step_index):
    # Trace context is available here!
    # Tool calls will be nested under parent trace
    task_actor_agent.act(question=question, step_index=step_index)
```

### 5.2 Thread Pool Execution with Context

**In BaseAgent** (`base_agent.py`):

```python
def _execute_tool_calls(self, tool_calls, step_index):
    """Execute multiple tool calls in parallel while maintaining trace context"""
    results = []

    # ThreadPoolExecutor automatically propagates context via ThreadingInstrumentor
    with ThreadPoolExecutor() as executor:
        futures = []
        for tool_call in tool_calls:
            # Each submit() call automatically captures and propagates context
            futures.append(executor.submit(
                self._execute_tool_call,
                function_name=tool_call.function.name,
                function_args=tool_call.function.arguments,
                tool_call_id=tool_call.id,
                step_index=step_index
            ))

        # Collect results - all traces will be properly nested
        for future in futures:
            results.append(future.result())

    return results
```

**Key Point**: Without `ThreadingInstrumentor`, each `executor.submit()` would create a new root trace instead of a child span.

---

## 6. Session Management

### 6.1 Session ID Strategy

**One Session = One Research Task**

Each research task (user question) gets a unique session ID:

```python
# In Plan class (todolist.py)
class Plan:
    def __init__(self, title: str = "", steps: List[str] = None, ...):
        # Create unique session ID using object ID
        self.session_id = f"research-task-{id(self)}"
```

**Why Use Object ID**:
- Guaranteed unique per Plan instance
- No dependencies on external ID generators
- Fast and deterministic

### 6.2 Session Propagation Flow

```
┌──────────────────────────────────────────────────────┐
│  1. CoSight.execute() creates Plan with session_id  │
└─────────────────────┬────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────┐
│  2. Set session_id on trace (update_current_trace)  │
│     get_client().update_current_trace(              │
│         session_id=self.plan.session_id,            │
│         ...)                                        │
└─────────────────────┬────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────┐
│  3. Propagate session_id to all LLM instances       │
│     self.act_llm.session_id = self.plan.session_id  │
│     self.tool_llm.session_id = self.plan.session_id │
│     self.vision_llm.session_id = ...                │
└─────────────────────┬────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────┐
│  4. LLM instances set session_id on their traces    │
│     (in create_with_tools(), chat_to_llm())         │
│                                                     │
│     if self.session_id:                            │
│         trace_params["session_id"] = self.session_id│
│         get_client().update_current_trace(...)     │
└──────────────────────────────────────────────────────┘
```

### 6.3 Implementation in CoSight.execute()

**File**: `CoSight.py`

```python
@observe(name="research_task")
def execute(self, question, output_format=""):
    """Execute a research task - each task is tracked as one LangFuse session"""

    # Step 1: Initialize session for this research task
    if is_langfuse_enabled():
        try:
            # Set session ID and metadata at trace level
            get_client().update_current_trace(
                session_id=self.plan.session_id,  # Key: Use Plan's session_id
                name=f"Research: {question[:60]}...",
                metadata={
                    "question": question,
                    "output_format": output_format,
                    "plan_id": self.plan_id,
                    "task_type": "research"
                },
                tags=["research-task", "session-start"]
            )
            logger.info(f"[LangFuse] 📊 Session started: {self.plan.session_id}")

            # Step 2: Propagate session_id to all LLM instances
            if hasattr(self.act_llm, 'session_id'):
                self.act_llm.session_id = self.plan.session_id
            if hasattr(self.tool_llm, 'session_id'):
                self.tool_llm.session_id = self.plan.session_id
            if hasattr(self.vision_llm, 'session_id'):
                self.vision_llm.session_id = self.plan.session_id
            if hasattr(self.task_planner_agent.llm, 'session_id'):
                self.task_planner_agent.llm.session_id = self.plan.session_id

        except Exception as e:
            logger.debug(f"[LangFuse] Failed to set session: {e}")

    # Step 3: Execute plan steps (parallel threads will inherit context)
    # ... execution logic ...
```

### 6.4 Implementation in ChatLLM

**File**: `app/cosight/llm/chat_llm.py`

```python
class ChatLLM:
    def __init__(self, ...):
        # Add session_id attribute
        self.session_id = None  # Will be set by CoSight

        # Wrap OpenAI client with Langfuse instrumentation
        if is_langfuse_enabled() and LANGFUSE_AVAILABLE:
            try:
                from langfuse.openai import openai as langfuse_openai
                self.client = langfuse_openai.OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    http_client=http_client
                )
                logger.info(f"[LangFuse] ✅ Using instrumented OpenAI client")
            except Exception as e:
                logger.warning(f"[LangFuse] ⚠️  Failed to wrap client: {e}")
                self.client = client
        else:
            self.client = client

    @observe(name="llm_create_with_tools")
    def create_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict]):
        # Update trace with session_id if available
        if is_langfuse_enabled() and LANGFUSE_AVAILABLE:
            try:
                trace_params = {
                    "metadata": {
                        "model": self.model,
                        "temperature": self.temperature,
                        "tools_count": len(tools)
                    }
                }

                # CRITICAL: Add session_id at trace level
                if self.session_id:
                    trace_params["session_id"] = self.session_id

                get_client().update_current_trace(**trace_params)
            except Exception as e:
                logger.warning(f"[LangFuse] Failed to update trace: {e}")

        # Make LLM call (automatically traced by Langfuse-wrapped client)
        response = self.client.chat.completions.create(...)
        return response
```

**Key Points**:
1. `session_id` is stored as instance variable on ChatLLM
2. Session ID is set at **trace level**, not span level
3. Must use `update_current_trace()`, not `update_current_span()`
4. Session propagates to all spans within the trace automatically

---

## 7. Parallel Agent & Tool Call Handling

### 7.1 Parallel Step Execution

**In CoSight.execute()** - Managing parallel agent instances:

```python
# Continuous monitoring approach for parallel execution
active_threads = {}  # {step_index: thread}

while True:
    # Get steps ready to execute (dependencies satisfied)
    ready_steps = self.plan.get_ready_steps()

    # Start new threads for ready steps
    for step_index in ready_steps:
        if step_index not in active_threads:
            logger.info(f"Starting new step {step_index}")
            # Create daemon thread - context will propagate automatically
            thread = Thread(target=self._execute_single_step, args=(question, step_index))
            thread.daemon = True
            thread.start()
            active_threads[step_index] = thread

    # Check for completed threads
    completed_steps = [idx for idx, t in active_threads.items() if not t.is_alive()]
    for step_index in completed_steps:
        del active_threads[step_index]

    # Exit when no active threads and no ready steps
    if not active_threads and not ready_steps:
        break

    time.sleep(0.1)  # Avoid CPU spinning
```

**Key Principles**:
- Use `thread.daemon = True` for automatic cleanup
- ThreadingInstrumentor automatically propagates trace context to each thread
- All parallel agents share same session via context propagation

### 7.2 Parallel Tool Call Execution

**In BaseAgent._execute_tool_calls()** - Managing parallel tool calls:

```python
def _execute_tool_calls(self, tool_calls, step_index):
    """Execute tool calls in parallel using ThreadPoolExecutor"""
    results = []

    # ThreadPoolExecutor + ThreadingInstrumentor = automatic context propagation
    with ThreadPoolExecutor() as executor:
        futures = []

        # Submit all tool calls for parallel execution
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments

            if function_name in self.functions:
                # Regular tool
                futures.append(executor.submit(
                    self._execute_tool_call,
                    function_name=function_name,
                    function_args=function_args,
                    tool_call_id=tool_call.id,
                    step_index=step_index
                ))
            else:
                # MCP tool
                futures.append(executor.submit(
                    self._execute_mcp_tool_call,
                    function_name=function_name,
                    function_args=function_args,
                    tool_call_id=tool_call.id
                ))

        # Collect results as they complete
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Unhandled exception: {e}", exc_info=True)
                results.append({
                    "role": "tool",
                    "name": function_name,
                    "tool_call_id": tool_call.id,
                    "content": f"Execution error: {str(e)}"
                })

    return results
```

### 7.3 Tool Execution with Tracing

**In BaseAgent._execute_tool_call()** - Individual tool with tracing:

```python
@time_record
@observe(name="tool_execution")
def _execute_tool_call(self, function_name="", function_args="", tool_call_id="", step_index=None):
    start_time = time.time()

    # Add metadata to LangFuse trace
    if is_langfuse_enabled() and LANGFUSE_AVAILABLE:
        try:
            langfuse_client = get_client()
            langfuse_client.update_current_span(
                name=f"tool_{function_name}",
                metadata={
                    "tool_name": function_name,
                    "step_index": step_index,
                    "tool_call_id": tool_call_id
                },
                input={"args": function_args[:500]}  # Truncate long args
            )
        except Exception as e:
            logger.debug(f"[LangFuse] Failed to update tool observation: {e}")

    try:
        # Parse and execute tool
        args_dict = json.loads(function_args or "{}")
        function_to_call = self.functions[function_name]

        # Handle async vs sync functions
        if inspect.iscoroutinefunction(function_to_call):
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(function_to_call(**args_dict))
            finally:
                loop.close()
        else:
            result = function_to_call(**args_dict)

        duration = time.time() - start_time

        # Update LangFuse span with result
        if is_langfuse_enabled() and LANGFUSE_AVAILABLE:
            try:
                result_str = str(result)
                langfuse_client.update_current_span(
                    output={"result": result_str[:1000]},
                    metadata={
                        "duration": duration,
                        "success": True,
                        "result_length": len(result_str)
                    }
                )
            except Exception as e:
                logger.debug(f"[LangFuse] Failed to update tool result: {e}")

        return {
            "role": "tool",
            "name": function_name,
            "content": str(result),
            "tool_call_id": tool_call_id
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Tool execution error: {e}", exc_info=True)

        return {
            "role": "tool",
            "name": function_name,
            "tool_call_id": tool_call_id,
            "content": f"Execution error: {str(e)}"
        }
```

**Key Tracing Points**:
1. Use `update_current_span()` for span-level metadata (not `update_current_trace()`)
2. Add rich metadata: tool name, step index, arguments
3. Track duration and success status
4. Truncate large inputs/outputs to avoid bloating traces

### 7.4 MCP Tool Execution

Similar pattern for MCP tools:

```python
@observe(name="mcp_tool_execution")
def _execute_mcp_tool_call(self, function_name="", function_args="", tool_call_id=""):
    # Add metadata
    if is_langfuse_enabled() and LANGFUSE_AVAILABLE:
        try:
            get_client().update_current_span(
                name=f"mcp_tool_{function_name}",
                metadata={
                    "tool_name": function_name,
                    "tool_type": "mcp",
                    "tool_call_id": tool_call_id
                },
                input={"args": function_args[:500]}
            )
        except Exception as e:
            logger.debug(f"[LangFuse] Failed to update MCP tool observation: {e}")

    # Execute MCP tool
    # ... (similar pattern to regular tools)
```

---

## 8. Implementation Checklist

### 8.1 Dependencies & Configuration

- [ ] Add `langfuse` to `requirements.txt`
- [ ] Add `opentelemetry-instrumentation-threading` to `requirements.txt`
- [ ] Install dependencies: `pip install langfuse opentelemetry-instrumentation-threading`
- [ ] Add Langfuse configuration to `.env`:
  - [ ] `ENABLE_LANGFUSE=true` (or false to disable)
  - [ ] `LANGFUSE_HOST=https://cloud.langfuse.com`
  - [ ] `LANGFUSE_PUBLIC_KEY=pk-lf-...`
  - [ ] `LANGFUSE_SECRET_KEY=sk-lf-...`
  - [ ] Optional: `LANGFUSE_ENVIRONMENT`, `LANGFUSE_RELEASE`

### 8.2 Core Infrastructure

- [ ] Create `langfuse_config.py` module:
  - [ ] Implement `is_langfuse_enabled()`
  - [ ] Implement `initialize_langfuse()` with ThreadingInstrumentor
  - [ ] Implement `get_langfuse_client()`
  - [ ] Implement `shutdown_langfuse()`
  - [ ] Implement `observe_fallback()` decorator
  - [ ] Add global client singleton

- [ ] Update application entry point (main.py):
  - [ ] Call `initialize_langfuse()` at startup
  - [ ] Register `atexit.register(shutdown_langfuse)`
  - [ ] Add configuration validation logging

### 8.3 Session Management

- [ ] Update `Plan` class (or equivalent):
  - [ ] Add `session_id` attribute: `self.session_id = f"research-task-{id(self)}"`
  - [ ] Ensure unique session per task/plan

- [ ] Update main orchestrator (CoSight or equivalent):
  - [ ] Add `@observe(name="research_task")` decorator to main execute method
  - [ ] Set session on trace: `get_client().update_current_trace(session_id=...)`
  - [ ] Propagate session_id to all LLM instances:
    ```python
    self.act_llm.session_id = self.plan.session_id
    self.tool_llm.session_id = self.plan.session_id
    self.vision_llm.session_id = self.plan.session_id
    ```

### 8.4 LLM Instrumentation

- [ ] Update ChatLLM (or equivalent LLM wrapper):
  - [ ] Add `session_id` instance variable
  - [ ] Wrap OpenAI client with `langfuse_openai.OpenAI()`
  - [ ] Add `@observe(name="llm_create_with_tools")` decorator
  - [ ] Update trace with session_id in traced methods:
    ```python
    if self.session_id:
        trace_params["session_id"] = self.session_id
    get_client().update_current_trace(**trace_params)
    ```
  - [ ] Add fallback handling if Langfuse unavailable

### 8.5 Tool Execution Tracing

- [ ] Update BaseAgent (or equivalent tool executor):
  - [ ] Add `@observe(name="tool_execution")` to tool execution method
  - [ ] Update span with tool metadata:
    ```python
    get_client().update_current_span(
        name=f"tool_{function_name}",
        metadata={"tool_name": function_name, "step_index": step_index},
        input={"args": function_args}
    )
    ```
  - [ ] Update span with results and duration
  - [ ] Handle async vs sync tool functions
  - [ ] Add error handling and logging

### 8.6 Parallel Execution

- [ ] Verify ThreadingInstrumentor is initialized (in `initialize_langfuse()`)
- [ ] Update parallel step execution:
  - [ ] Use `Thread(target=...)` for parallel agents
  - [ ] Set `thread.daemon = True`
  - [ ] Trust ThreadingInstrumentor to propagate context
- [ ] Update parallel tool execution:
  - [ ] Use `ThreadPoolExecutor` for concurrent tool calls
  - [ ] Trust ThreadingInstrumentor to propagate context to executor threads
  - [ ] Handle exceptions in futures properly

### 8.7 Testing & Validation

- [ ] Test with `ENABLE_LANGFUSE=false` (ensure graceful degradation)
- [ ] Test with `ENABLE_LANGFUSE=true`:
  - [ ] Verify traces appear in Langfuse dashboard
  - [ ] Verify session grouping works (all calls in one session)
  - [ ] Verify parallel tool calls are properly nested
  - [ ] Verify parallel agent calls maintain session context
  - [ ] Check span hierarchy is correct
  - [ ] Verify metadata is captured (model, tokens, duration, etc.)
- [ ] Test error scenarios:
  - [ ] Invalid Langfuse credentials
  - [ ] Network issues
  - [ ] Tool execution failures
- [ ] Performance testing:
  - [ ] Measure overhead of tracing
  - [ ] Verify no blocking on trace uploads

---

## 9. Code Examples

### 9.1 Minimal Implementation Example

This is a simplified example showing the core pattern:

```python
# 1. langfuse_config.py
import os
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

_langfuse_client = None

def is_langfuse_enabled():
    return os.getenv('ENABLE_LANGFUSE', 'false').lower() == 'true'

def initialize_langfuse():
    global _langfuse_client
    if not is_langfuse_enabled():
        return None

    try:
        # Initialize ThreadingInstrumentor
        ThreadingInstrumentor().instrument()

        # Initialize Langfuse client
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            host=os.getenv('LANGFUSE_HOST'),
            public_key=os.getenv('LANGFUSE_PUBLIC_KEY'),
            secret_key=os.getenv('LANGFUSE_SECRET_KEY')
        )
        return _langfuse_client
    except Exception as e:
        print(f"Failed to initialize Langfuse: {e}")
        return None

def get_langfuse_client():
    return _langfuse_client

# 2. chat_llm.py
from langfuse import observe, get_client
from langfuse.openai import openai as langfuse_openai

class ChatLLM:
    def __init__(self, api_key, base_url, model):
        self.session_id = None

        # Wrap OpenAI client
        if is_langfuse_enabled():
            self.client = langfuse_openai.OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

        self.model = model

    @observe(name="llm_call")
    def create(self, messages):
        # Set session_id on trace
        if self.session_id and is_langfuse_enabled():
            get_client().update_current_trace(session_id=self.session_id)

        # Make LLM call
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response

# 3. orchestrator.py
from langfuse import observe, get_client
from threading import Thread

class Orchestrator:
    def __init__(self, llm):
        self.llm = llm
        self.session_id = f"session-{id(self)}"

    @observe(name="research_task")
    def execute(self, question):
        # Set session on trace
        if is_langfuse_enabled():
            get_client().update_current_trace(
                session_id=self.session_id,
                name=f"Research: {question}"
            )

        # Propagate session to LLM
        self.llm.session_id = self.session_id

        # Execute in parallel threads (context propagates automatically)
        threads = []
        for i in range(3):
            t = Thread(target=self._execute_step, args=(question, i))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def _execute_step(self, question, step_index):
        # This runs in child thread, but has trace context!
        result = self.llm.create([{"role": "user", "content": question}])
        return result

# 4. main.py
import atexit
from langfuse_config import initialize_langfuse, shutdown_langfuse

# Initialize at startup
initialize_langfuse()
atexit.register(shutdown_langfuse)

# Run application
orchestrator = Orchestrator(llm=ChatLLM(...))
orchestrator.execute("What is the capital of France?")
```

### 9.2 Error Handling Example

```python
@observe(name="tool_execution")
def execute_tool(tool_name, tool_args):
    try:
        # Update span with metadata
        if is_langfuse_enabled():
            get_client().update_current_span(
                name=f"tool_{tool_name}",
                metadata={"tool_name": tool_name},
                input={"args": tool_args}
            )

        # Execute tool
        result = run_tool(tool_name, tool_args)

        # Update span with success
        if is_langfuse_enabled():
            get_client().update_current_span(
                output={"result": str(result)},
                metadata={"success": True}
            )

        return result

    except Exception as e:
        # Update span with error
        if is_langfuse_enabled():
            get_client().update_current_span(
                metadata={"success": False, "error": str(e)}
            )

        logger.error(f"Tool execution failed: {e}")
        raise
```

---

## 10. Troubleshooting

### 10.1 Common Issues

#### Issue: Traces Not Appearing in Langfuse Dashboard

**Symptoms**:
- No traces visible in Langfuse UI
- No errors in logs

**Diagnosis**:
1. Check `ENABLE_LANGFUSE` is set to `true` in `.env`
2. Verify credentials are correct:
   ```python
   # In langfuse_config.py initialize_langfuse()
   _langfuse_client.auth_check()  # This should not raise an exception
   ```
3. Check network connectivity to Langfuse host
4. Ensure `shutdown_langfuse()` is called before app exits (uses `atexit`)

**Solution**:
- Double-check `.env` configuration
- Test credentials with minimal script
- Add debug logging to `initialize_langfuse()`

#### Issue: Parallel Tool Calls Not Nested Under Parent Trace

**Symptoms**:
- Each parallel tool call creates separate root trace
- Session grouping broken
- No parent-child relationship in spans

**Diagnosis**:
1. Check if `opentelemetry-instrumentation-threading` is installed:
   ```bash
   pip list | grep opentelemetry
   ```
2. Verify ThreadingInstrumentor is initialized:
   ```python
   # In langfuse_config.py
   ThreadingInstrumentor().instrument()
   ```
3. Check logs for ThreadingInstrumentor warnings

**Solution**:
- Install missing dependency: `pip install opentelemetry-instrumentation-threading`
- Ensure `initialize_langfuse()` is called **before** creating any threads
- Verify ThreadingInstrumentor initialization doesn't raise exceptions

#### Issue: Session ID Not Grouping Traces

**Symptoms**:
- Traces appear but not grouped under same session
- Session filter in Langfuse shows no results

**Diagnosis**:
1. Verify session_id is being set:
   ```python
   logger.info(f"Session ID: {self.plan.session_id}")
   ```
2. Check session_id is passed to `update_current_trace()`:
   ```python
   get_client().update_current_trace(session_id=self.session_id)
   ```
3. Ensure session_id is set at **trace level**, not span level
4. Verify session_id is propagated to all LLM instances

**Solution**:
- Always use `update_current_trace(session_id=...)`, not `update_current_span()`
- Set session_id on LLM instances: `llm.session_id = session_id`
- Ensure session_id is set **before** making any traced calls

#### Issue: Missing Metadata in Traces

**Symptoms**:
- Traces appear but missing tool names, durations, etc.

**Diagnosis**:
1. Check if metadata updates are wrapped in try-except
2. Verify `LANGFUSE_AVAILABLE` flag is True
3. Check for errors in logs related to span updates

**Solution**:
- Ensure `get_client().update_current_span()` calls are not silently failing
- Add debug logging to metadata update blocks
- Verify metadata is JSON-serializable

#### Issue: Performance Degradation

**Symptoms**:
- Application slower with tracing enabled
- High CPU usage

**Diagnosis**:
1. Check if traces are being uploaded synchronously
2. Look for blocking operations in tool execution
3. Monitor Langfuse SDK internal queue

**Solution**:
- Langfuse SDK uses async uploads by default - no action needed
- If issues persist, consider reducing sampling rate
- Use `shutdown_langfuse()` to flush traces at app exit, not during execution

### 10.2 Debugging Tips

**Enable Debug Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In langfuse_config.py
logger.setLevel(logging.DEBUG)
```

**Test Langfuse Connection**:
```python
from langfuse import Langfuse

client = Langfuse(
    host="https://cloud.langfuse.com",
    public_key="pk-lf-...",
    secret_key="sk-lf-..."
)

try:
    client.auth_check()
    print("✅ Langfuse connection successful")
except Exception as e:
    print(f"❌ Langfuse connection failed: {e}")
```

**Verify ThreadingInstrumentor**:
```python
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

try:
    ThreadingInstrumentor().instrument()
    print("✅ ThreadingInstrumentor initialized")
except Exception as e:
    print(f"❌ ThreadingInstrumentor failed: {e}")
```

**Check Trace Context in Thread**:
```python
from opentelemetry import trace

def thread_function():
    # Get current span - should exist if context propagated
    current_span = trace.get_current_span()
    if current_span.is_recording():
        print("✅ Trace context exists in thread")
    else:
        print("❌ No trace context in thread")
```

### 10.3 Validation Checklist

After implementation, verify:

- [ ] Traces appear in Langfuse dashboard
- [ ] All traces for one research task share same session_id
- [ ] Span hierarchy is correct (parent-child relationships)
- [ ] Parallel tool calls are nested under parent span
- [ ] Parallel agent calls maintain session context
- [ ] Metadata includes: model name, token counts, durations
- [ ] Tool names and arguments are captured
- [ ] Errors are captured in failed spans
- [ ] Application works correctly with `ENABLE_LANGFUSE=false`
- [ ] No performance degradation > 5%
- [ ] Traces flush on application shutdown

---

## Appendix A: Key File Locations

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Langfuse Config | `app/cosight/llm/langfuse_config.py` | Initialize client, provide decorators |
| LLM Wrapper | `app/cosight/llm/chat_llm.py` | Wrap OpenAI client, set session_id |
| Base Agent | `app/cosight/agent/base/base_agent.py` | Execute tools with tracing |
| Task Actor | `app/cosight/agent/actor/task_actor_agent.py` | Agent for executing plan steps |
| Task Planner | `app/cosight/agent/planner/task_plannr_agent.py` | Agent for creating plans |
| Orchestrator | `CoSight.py` | Main research task orchestrator |
| Plan/Session | `app/cosight/task/todolist.py` | Plan class with session_id |
| Entry Point | `cosight_server/deep_research/main.py` | Initialize Langfuse, start app |
| Environment | `.env` or `.env_template` | Langfuse configuration |
| Dependencies | `requirements.txt` | Langfuse and OpenTelemetry packages |

---

## Appendix B: Glossary

- **Trace**: A complete execution flow for a single request/task
- **Span**: A single operation within a trace (e.g., one LLM call, one tool execution)
- **Session**: A logical grouping of related traces (in CoSight: one research task)
- **Observation**: Generic term for trace, span, or event in Langfuse
- **Instrumentation**: Automatic tracing via wrapped libraries (e.g., `langfuse_openai.OpenAI`)
- **Context Propagation**: Passing trace context across thread/process boundaries
- **ThreadingInstrumentor**: OpenTelemetry component that enables context propagation to threads
- **Decorator**: Python `@observe` syntax for wrapping functions with tracing

---

## Appendix C: Architecture Decisions

### Why Langfuse?

1. **Native OpenAI Integration**: Automatic LLM call tracking via wrapped client
2. **Rich Metadata**: Captures tokens, costs, latencies automatically
3. **Session Management**: Built-in session grouping for related traces
4. **Python SDK**: First-class Python support with decorators
5. **Dashboard**: Excellent UI for exploring traces and sessions

### Why OpenTelemetry Threading Instrumentation?

1. **Context Propagation**: Without it, parallel threads lose trace context
2. **Standard**: OpenTelemetry is industry-standard observability framework
3. **Automatic**: No manual context passing required
4. **Compatibility**: Works seamlessly with Langfuse SDK

### Why Session ID Based on Object ID?

1. **Uniqueness**: Object ID is guaranteed unique per Plan instance
2. **Simplicity**: No external dependencies or ID generators needed
3. **Performance**: No I/O or locking overhead
4. **Deterministic**: Same plan instance always has same session ID

### Why Trace-Level Session ID?

- Langfuse requires session_id at trace level, not span level
- Ensures all spans within trace inherit session
- Allows querying all traces by session in Langfuse UI

---

## Appendix D: Performance Considerations

### Tracing Overhead

**Expected Overhead**: 1-3% of total execution time

**Breakdown**:
- OpenAI client wrapping: <1%
- Span creation/updates: 1-2%
- Metadata serialization: <1%
- Network uploads: 0% (async)

### Optimization Tips

1. **Truncate Large Inputs/Outputs**:
   ```python
   input={"args": function_args[:500]}  # Limit to 500 chars
   output={"result": result_str[:1000]}  # Limit to 1000 chars
   ```

2. **Disable in Production** (if needed):
   ```bash
   ENABLE_LANGFUSE=false
   ```

3. **Sample Traces** (for high-volume systems):
   ```bash
   LANGFUSE_SAMPLE_RATE=0.1  # Trace 10% of requests
   ```

4. **Batch Trace Uploads**:
   - Langfuse SDK batches uploads automatically
   - No manual configuration needed

### Memory Usage

- Each span: ~1-5 KB in memory (before upload)
- Spans uploaded asynchronously and cleared
- No long-term memory accumulation

---

## Appendix E: Advanced Topics

### Custom Metadata

Add custom metadata to traces:

```python
get_client().update_current_trace(
    metadata={
        "user_id": "user123",
        "experiment_id": "exp_456",
        "custom_field": "value"
    }
)
```

### Custom Tags

Add tags for filtering:

```python
get_client().update_current_trace(
    tags=["production", "research-task", "high-priority"]
)
```

### Manual Span Creation

For fine-grained control:

```python
from langfuse import get_client

with get_client().span(name="custom_operation") as span:
    # Do work
    result = expensive_operation()

    # Update span
    span.update(
        output={"result": result},
        metadata={"duration": 1.23}
    )
```

### Sampling

Implement custom sampling logic:

```python
import random

def should_trace():
    return random.random() < 0.1  # 10% sampling

@observe(name="my_function") if should_trace() else lambda f: f
def my_function():
    pass
```

---

## Appendix F: Migration Guide

### Migrating Existing Code to Add Tracing

**Step 1**: Install dependencies
```bash
pip install langfuse opentelemetry-instrumentation-threading
```

**Step 2**: Add configuration to `.env`
```bash
ENABLE_LANGFUSE=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

**Step 3**: Create `langfuse_config.py` (copy from reference implementation)

**Step 4**: Update `main.py`:
```python
from langfuse_config import initialize_langfuse, shutdown_langfuse
import atexit

# At startup
initialize_langfuse()
atexit.register(shutdown_langfuse)
```

**Step 5**: Update LLM wrapper class:
```python
# Add to __init__:
self.session_id = None

# Wrap client:
if is_langfuse_enabled():
    from langfuse.openai import openai as langfuse_openai
    self.client = langfuse_openai.OpenAI(...)
else:
    self.client = OpenAI(...)

# Add @observe to LLM methods:
@observe(name="llm_call")
def create(self, messages):
    if self.session_id:
        get_client().update_current_trace(session_id=self.session_id)
    # ... rest of implementation
```

**Step 6**: Update main orchestrator:
```python
# Add session_id to plan/task:
self.session_id = f"task-{id(self)}"

# Set session on trace:
@observe(name="research_task")
def execute(self, question):
    if is_langfuse_enabled():
        get_client().update_current_trace(session_id=self.session_id)

    # Propagate to LLMs:
    self.llm.session_id = self.session_id
    # ... rest of implementation
```

**Step 7**: Add tool tracing:
```python
@observe(name="tool_execution")
def execute_tool(self, tool_name, args):
    if is_langfuse_enabled():
        get_client().update_current_span(
            name=f"tool_{tool_name}",
            metadata={"tool_name": tool_name}
        )
    # ... rest of implementation
```

**Step 8**: Test
- Test with `ENABLE_LANGFUSE=false` (should work as before)
- Test with `ENABLE_LANGFUSE=true` (should see traces)

---

## Conclusion

This guide provides a complete blueprint for implementing distributed tracing using Langfuse and OpenTelemetry. The key innovations are:

1. **Unified Session Tracking**: Each research task = one session
2. **Automatic Context Propagation**: ThreadingInstrumentor enables seamless parallel execution
3. **Graceful Degradation**: Works perfectly with tracing disabled
4. **Rich Observability**: Captures LLM calls, tool executions, and metadata

Follow the implementation checklist step-by-step, and you'll have production-ready tracing that handles complex parallel agent workflows with ease.

---

**Document Version**: 1.0
**Last Updated**: 2025-01-XX
**Author**: Claude (based on CoSight with-profiling branch analysis)
