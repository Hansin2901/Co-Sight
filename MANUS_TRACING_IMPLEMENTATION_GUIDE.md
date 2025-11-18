# Manus Tracing Implementation Guide: Langfuse + OpenTelemetry

## Executive Summary

This document provides a comprehensive, step-by-step guide to implementing distributed tracing in the **Manus** agent system using **Langfuse** and **OpenTelemetry**. The implementation enables monitoring of LLM calls, tool executions, parallel agent operations, and plan execution while maintaining proper session context across concurrent threads.

**Key Achievement**: Each research task executed through Manus is tracked as a single unified trace/session, with all LLM calls, tool executions, planning steps, and parallel actor operations properly nested and contextualized.

---

## Table of Contents

1. [Manus Architecture Overview](#manus-architecture-overview)
2. [Core Dependencies](#core-dependencies)
3. [Configuration System](#configuration-system)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Step-by-Step Implementation](#step-by-step-implementation)
6. [Code Examples](#code-examples)
7. [Testing & Validation](#testing--validation)
8. [Troubleshooting](#troubleshooting)

---

## 1. Manus Architecture Overview

### 1.1 Current Manus Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    Evaluation Entry Point                   │
│                 (cosight_evals*.py files)                   │
│                                                             │
│  1. Load .env configuration                                │
│  2. Initialize LLMs (llm.py)                               │
│  3. Create Manus instance                                  │
│  4. Execute research tasks                                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      Manus Class                            │
│                 (app/manus/manus.py)                        │
│                                                             │
│  def __init__(plan_llm, act_llm, tool_llm, vision_llm):   │
│    - Create Plan with unique plan_id                       │
│    - Initialize TaskPlannerAgent                           │
│    - Store LLM references                                  │
│                                                             │
│  def execute(question, output_format):                     │
│    - Create plan via TaskPlannerAgent                      │
│    - Execute steps in parallel (execute_steps)             │
│    - Re-plan when needed                                   │
│    - Finalize and return result                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├──────────────────┬────────────────────┐
                  ▼                  ▼                    ▼
        ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
        │  TaskPlanner     │ │  TaskActor   │ │  TaskActor       │
        │  Agent           │ │  Agent       │ │  Agent           │
        │                  │ │  (Thread 1)  │ │  (Thread 2)      │
        │  - plan_llm      │ │  - act_llm   │ │  - act_llm       │
        │  - create_plan() │ │  - tool_llm  │ │  - tool_llm      │
        │  - re_plan()     │ │  - vision    │ │  - vision        │
        │  - finalize()    │ │  - act()     │ │  - act()         │
        └────────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
                 │                  │                   │
                 ▼                  ▼                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │              ChatLLM (LLM Wrapper)                     │
        │           (app/manus/llm/chat_llm.py)                  │
        │                                                         │
        │  def create_with_tools(messages, tools):               │
        │    - Calls OpenAI client                               │
        │    - Handles retries                                   │
        │    - Returns message with tool calls                   │
        │                                                         │
        │  def chat_to_llm(messages):                            │
        │    - Simple chat completion                            │
        │    - Returns text response                             │
        └─────────────────────────────────────────────────────────┘
```

### 1.2 Key Components in Manus

| Component | File Location | Purpose |
|-----------|---------------|---------|
| **Manus** | `app/manus/manus.py` | Main orchestrator, manages plan execution and parallel steps |
| **Plan** | `app/manus/task/todolist.py` | Task plan with steps, dependencies, statuses |
| **ChatLLM** | `app/manus/llm/chat_llm.py` | LLM wrapper for OpenAI client |
| **LLM Config** | `llm.py` (root) | Creates LLM instances for plan/act/tool/vision |
| **TaskPlannerAgent** | `app/manus/agent/planner/task_plannr_agent.py` | Creates and modifies plans |
| **TaskActorAgent** | `app/manus/agent/actor/task_actor_agent.py` | Executes individual plan steps with tools |
| **Evaluation Scripts** | `cosight_evals*.py` | Entry points for benchmarking |

### 1.3 Execution Flow

```
User Question
    ↓
Manus.execute()
    ↓
TaskPlannerAgent.create_plan() → [Step 0, Step 1, Step 2, ...]
    ↓
Loop: Get ready steps
    ↓
execute_steps([step_0, step_1]) → Parallel threads
    ↓                                ↓
TaskActorAgent.act(step_0)    TaskActorAgent.act(step_1)
    ↓                                ↓
LLM calls with tools           LLM calls with tools
    ↓                                ↓
Tool executions                Tool executions
    ↓                                ↓
Mark step complete             Mark step complete
    ↓
TaskPlannerAgent.re_plan() → Update plan or add steps
    ↓
Loop continues until all steps done
    ↓
TaskPlannerAgent.finalize_plan() → Final result
```

---

## 2. Core Dependencies

### 2.1 Required Packages

Add to `requirements.txt` in the root directory:

```text
langfuse
opentelemetry-instrumentation-threading
```

### 2.2 Installation

```bash
pip install langfuse opentelemetry-instrumentation-threading
```

Or if using `uv`:

```bash
uv add langfuse opentelemetry-instrumentation-threading
```

### 2.3 Dependency Explanation

- **`langfuse`**: Official Langfuse Python SDK
  - Provides `@observe` decorator for tracing functions
  - Wraps OpenAI client for automatic LLM call tracking
  - Manages trace context and span hierarchy
  - Tracks token usage, costs, latency automatically

- **`opentelemetry-instrumentation-threading`**: OpenTelemetry Threading Instrumentation
  - **CRITICAL** for Manus: Enables trace context propagation to child threads
  - Without this, parallel `TaskActorAgent` instances in `execute_steps()` would lose session context
  - Automatically instruments Python's `threading` module
  - Maintains parent-child span relationships across thread boundaries

---

## 3. Configuration System

### 3.1 Environment Variables

Update `.env` file in the root directory:

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

### 3.2 Configuration Validation

Add validation in your evaluation scripts:

```python
# In cosight_evals*.py (at the beginning)
import os
from dotenv import load_dotenv

load_dotenv()

# Check Langfuse configuration
langfuse_enabled = os.getenv('ENABLE_LANGFUSE', 'false').lower() == 'true'
if langfuse_enabled:
    print("✓ ENABLE_LANGFUSE = true")
    print(f"✓ LANGFUSE_HOST = {os.getenv('LANGFUSE_HOST')}")
    print(f"✓ LANGFUSE_PUBLIC_KEY = {os.getenv('LANGFUSE_PUBLIC_KEY')[:10]}...")
else:
    print("ℹ ENABLE_LANGFUSE = false (tracing disabled)")
```

---

## 4. Implementation Roadmap

### Phase 1: Core Infrastructure
1. Create `langfuse_config.py` module
2. Update `ChatLLM` to wrap OpenAI client
3. Add session management to `Plan` class

### Phase 2: Manus Integration
4. Add tracing to `Manus.execute()`
5. Propagate session_id to all LLM instances
6. Add tracing to `execute_steps()`

### Phase 3: Agent Tracing
7. Add tracing to `TaskPlannerAgent`
8. Add tracing to `TaskActorAgent`
9. Add tool execution tracing

### Phase 4: Evaluation Scripts
10. Update evaluation entry points
11. Add shutdown handlers

### Phase 5: Testing
12. Validate with ENABLE_LANGFUSE=false
13. Validate with ENABLE_LANGFUSE=true
14. Verify session grouping in Langfuse dashboard

---

## 5. Step-by-Step Implementation

### Step 1: Create Langfuse Configuration Module

**File**: `app/manus/llm/langfuse_config.py`

```python
# Copyright 2025 ZTE Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Langfuse Configuration Module

This module provides centralized configuration for Langfuse observability:
- Initializes Langfuse client with credentials
- Sets up ThreadingInstrumentor for parallel execution context propagation
- Provides observe decorator and client access
- Handles graceful degradation when Langfuse is disabled
"""

import os
import logging

logger = logging.getLogger(__name__)

# Global Langfuse client instance
_langfuse_client = None

# Track if Langfuse is available and enabled
LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    logger.warning("[LangFuse] ⚠️  langfuse package not installed")


def is_langfuse_enabled() -> bool:
    """
    Check if LangFuse is enabled via ENABLE_LANGFUSE environment variable.

    Returns:
        bool: True if enabled, False otherwise
    """
    enabled = os.getenv('ENABLE_LANGFUSE', 'false').lower() == 'true'
    return enabled and LANGFUSE_AVAILABLE


def initialize_langfuse():
    """
    Initialize LangFuse client and ThreadingInstrumentor.

    This function should be called once at application startup.

    Returns:
        Langfuse client instance or None if disabled/failed
    """
    global _langfuse_client

    if not is_langfuse_enabled():
        logger.info("[LangFuse] ℹ️  Tracing disabled (ENABLE_LANGFUSE=false)")
        return None

    try:
        # Step 1: Initialize ThreadingInstrumentor for parallel execution
        try:
            from opentelemetry.instrumentation.threading import ThreadingInstrumentor
            ThreadingInstrumentor().instrument()
            logger.info("[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads")
        except ImportError:
            logger.warning("[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed")
            logger.warning("[LangFuse] Threading context propagation may not work correctly")
            logger.warning("[LangFuse] Install with: pip install opentelemetry-instrumentation-threading")

        # Step 2: Initialize Langfuse client
        from langfuse import Langfuse

        host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')
        release = os.getenv('LANGFUSE_RELEASE')
        environment = os.getenv('LANGFUSE_ENVIRONMENT', 'development')

        if not public_key or not secret_key:
            logger.error("[LangFuse] ❌ Missing API keys (LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY)")
            return None

        _langfuse_client = Langfuse(
            host=host,
            public_key=public_key,
            secret_key=secret_key,
            release=release,
            environment=environment
        )

        logger.info(f"[LangFuse] ✅ Initialized successfully")
        logger.info(f"[LangFuse]    Host: {host}")
        logger.info(f"[LangFuse]    Environment: {environment}")
        if release:
            logger.info(f"[LangFuse]    Release: {release}")

        return _langfuse_client

    except Exception as e:
        logger.error(f"[LangFuse] ❌ Initialization failed: {e}", exc_info=True)
        return None


def get_langfuse_client():
    """
    Get the initialized LangFuse client instance.

    Returns:
        Langfuse client or None if not initialized
    """
    return _langfuse_client


def shutdown_langfuse():
    """
    Flush pending traces and shutdown LangFuse client.

    This should be called before application exit to ensure all traces are uploaded.
    """
    global _langfuse_client

    if _langfuse_client:
        try:
            logger.info("[LangFuse] 📤 Flushing pending traces...")
            _langfuse_client.flush()
            logger.info("[LangFuse] ✅ Shutdown complete")
        except Exception as e:
            logger.error(f"[LangFuse] ❌ Shutdown error: {e}")


def observe_fallback(*args, **kwargs):
    """
    Fallback no-op decorator when LangFuse is disabled or unavailable.

    This allows code to use @observe decorator without ImportError.
    """
    def decorator(func):
        return func

    # Handle both @observe and @observe(...) syntax
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return decorator


# Export observe decorator
if LANGFUSE_AVAILABLE and is_langfuse_enabled():
    from langfuse import observe
else:
    observe = observe_fallback
```

**Key Points**:
- Singleton pattern for Langfuse client
- ThreadingInstrumentor setup is critical for Manus parallel execution
- Graceful fallback when disabled or unavailable
- Clear logging for debugging

---

### Step 2: Update ChatLLM to Support Tracing

**File**: `app/manus/llm/chat_llm.py`

**Modifications**:

```python
# Add imports at the top
from app.manus.llm.langfuse_config import is_langfuse_enabled, observe, get_langfuse_client

# Add these imports for Langfuse OpenAI wrapper
try:
    from langfuse.openai import openai as langfuse_openai
    LANGFUSE_OPENAI_AVAILABLE = True
except ImportError:
    LANGFUSE_OPENAI_AVAILABLE = False


class ChatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, client: OpenAI, max_tokens: int = 4096,
                 temperature: float = 0.0, stream: bool = False, tools: List[Any] = None):
        self.tools = tools or []
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.max_tokens = max_tokens

        # NEW: Add session_id for tracing
        self.session_id = None

        # NEW: Wrap OpenAI client with Langfuse instrumentation
        if is_langfuse_enabled() and LANGFUSE_OPENAI_AVAILABLE:
            try:
                # Wrap the client for automatic LLM call tracking
                self.client = langfuse_openai.OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    http_client=client._client  # Reuse existing http_client
                )
                print(f"[LangFuse] ✅ ChatLLM using instrumented OpenAI client")
            except Exception as e:
                print(f"[LangFuse] ⚠️  Failed to wrap OpenAI client: {e}")
                self.client = client
        else:
            self.client = client

    # ... existing clean_none_values method ...

    # NEW: Add observe decorator
    @observe(name="llm_create_with_tools")
    @time_record
    def create_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict]):
        """
        Create a chat completion with support for function/tool calls
        """
        import time
        import json

        # NEW: Update trace with session_id and metadata
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

                # CRITICAL: Add session_id at trace level
                if self.session_id:
                    trace_params["session_id"] = self.session_id

                get_langfuse_client().update_current_trace(**trace_params)
            except Exception as e:
                print(f"[LangFuse] Failed to update trace: {e}")

        # 清洗提示词，去除None
        messages = ChatLLM.clean_none_values(messages)
        print(f'create_with_tools messages:{messages}')

        max_retries = 2
        for attempt in range(max_retries):
            model_name = self.model
            try:
                if attempt == 1:
                    model_name = 'anthropic/claude-sonnet-4'
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=self.temperature
                )
                print(f"LLM with tools chat completions response{attempt + 1} is {response}")
                break
            except Exception as e:
                print(f"JSON decode error: {e} on attempt {attempt + 1}, retrying...")
                if attempt == max_retries:
                    print(f"Failed to create after {max_retries + 1} attempts.")
                    raise
                time.sleep(3)

        # 去除think标签
        content = response.choices[0].message.content
        if content is not None and '</think>' in content:
            response.choices[0].message.content = content.split('</think>')[-1].strip('\n')

        return response.choices[0].message

    # NEW: Add observe decorator
    @observe(name="llm_chat_to_llm")
    @time_record
    def chat_to_llm(self, messages: List[Dict[str, Any]]):
        import time
        import json

        # NEW: Update trace with session_id and metadata
        if is_langfuse_enabled():
            try:
                trace_params = {
                    "metadata": {
                        "model": self.model,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "base_url": self.base_url
                    }
                }

                # CRITICAL: Add session_id at trace level
                if self.session_id:
                    trace_params["session_id"] = self.session_id

                get_langfuse_client().update_current_trace(**trace_params)
            except Exception as e:
                print(f"[LangFuse] Failed to update trace: {e}")

        # 清洗提示词，去除None
        messages = ChatLLM.clean_none_values(messages)
        print(f'chat_to_llm messages:{messages}')

        max_retries = 2
        for attempt in range(max_retries):
            model_name = self.model
            try:
                if attempt == 1:
                    model_name = 'anthropic/claude-sonnet-4'
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                print(f"LLM with tools chat completions response{attempt + 1} is {response}")
                break
            except Exception as e:
                print(f"JSON decode error: {e} on attempt {attempt + 1}, retrying...")
                if attempt == max_retries:
                    print(f"Failed to create after {max_retries + 1} attempts.")
                    raise
                time.sleep(3)

        # 去除think标签
        content = response.choices[0].message.content
        if content is not None and '</think>' in content:
            response.choices[0].message.content = content.split('</think>')[-1].strip('\n')

        return response.choices[0].message.content
```

**Key Changes**:
1. Added `session_id` attribute
2. Wrapped OpenAI client with `langfuse_openai.OpenAI()`
3. Added `@observe` decorators to both LLM methods
4. Update trace with `session_id` and metadata

---

### Step 3: Add Session Management to Plan Class

**File**: `app/manus/task/todolist.py`

**Modifications**:

```python
class Plan:
    """Represents a single plan with steps, statuses, and execution details as a DAG."""

    def __init__(self, title: str = "", steps: List[str] = None, dependencies: Dict[int, List[int]] = None):
        self.title = title
        self.steps = steps if steps else []
        # 使用步骤内容（中文）作为key存储状态、备注和详细信息
        self.step_statuses = {step: "not_started" for step in self.steps}
        self.step_notes = {step: "" for step in self.steps}
        self.step_details = {step: "" for step in self.steps}
        self.step_files = {step: "" for step in self.steps}
        # 新增：步骤执行工具记录
        self.step_tools = {step: [] for step in self.steps}
        self.facts = ""
        # 使用邻接表表示依赖关系
        if dependencies:
            self.dependencies = dependencies
        else:
            self.dependencies = {i: [i - 1] for i in range(1, len(self.steps))} if len(self.steps) > 1 else {}
        self.result = ""

        # NEW: Add session_id for tracing
        # Each Plan instance gets a unique session ID
        self.session_id = f"manus-task-{id(self)}"

    # ... rest of the class remains the same ...
```

**Key Changes**:
1. Added `session_id` attribute using object ID for uniqueness

---

### Step 4: Add Tracing to Manus Class

**File**: `app/manus/manus.py`

**Modifications**:

```python
# Add import at top
from app.manus.llm.langfuse_config import is_langfuse_enabled, observe, get_langfuse_client

class Manus:
    def __init__(self, plan_llm, act_llm, tool_llm, vision_llm):
        self.plan_id = f"plan_{int(time.time())}"
        self.plan = Plan()
        TaskManager.set_plan(self.plan_id, self.plan)
        self.task_planner_agent = TaskPlannerAgent(create_planner_instance("task_planner_agent"), plan_llm,
                                                   self.plan_id)
        self.act_llm = act_llm  # Store llm for later use
        self.tool_llm = tool_llm
        self.vision_llm = vision_llm

        # NEW: Propagate session_id to all LLM instances
        if is_langfuse_enabled():
            try:
                # Set session_id on all LLM instances
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

    # NEW: Add observe decorator
    @observe(name="manus_execute")
    @time_record
    def execute(self, question, output_format=""):
        """Execute a research task - each task is tracked as one LangFuse session"""

        # NEW: Set session metadata at trace level
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

        create_task = question
        retry_count = 0
        self.task_planner_agent.create_fact(question)

        while not self.plan.get_ready_steps() and retry_count < 3:
            create_result = self.task_planner_agent.create_plan(create_task, output_format)
            create_task += f"\nThe plan creation result is: {create_result}\nCreation failed, please carefully review the plan creation rules and select the create_plan tool to create the plan"
            retry_count += 1

        while True:
            ready_steps = self.plan.get_ready_steps()
            if not ready_steps:
                print("No more ready steps to execute")
                break
            print(f"Found {ready_steps} ready steps to execute")

            results = self.execute_steps(question, ready_steps)
            print(f"All steps completed with results: {results}")
            plan_report_event_manager.publish("plan_process", self.plan)
            # 可配置是否只在堵塞的时候再重规划，提高效率
            # todo 这里没有实时上报
            plan_report_event_manager.publish("plan_process", self.plan)
            re_plan_result = self.task_planner_agent.re_plan(question, output_format)
            print(f"re-plan_result is {re_plan_result}")

        return self.task_planner_agent.finalize_plan(question, output_format)

    # NEW: Add observe decorator
    @observe(name="manus_execute_actor")
    @time_record
    def execute_actor(self, question):
        task_actor_agent = TaskActorAgent(create_actor_instance(f"actor_for_step_{0}"), self.act_llm,
                                          self.vision_llm, self.tool_llm, self.plan_id)
        result = task_actor_agent.single_act(question)
        print(f"Completed execution of step {0} with result: {result}")
        return result

    # NEW: Add observe decorator
    @observe(name="manus_execute_steps_parallel")
    def execute_steps(self, question, ready_steps):
        """
        Execute multiple steps in parallel using threads.
        ThreadingInstrumentor ensures trace context propagates to child threads.
        """
        from threading import Thread, Semaphore
        from queue import Queue

        results = {}
        result_queue = Queue()
        semaphore = Semaphore(min(5, len(ready_steps)))

        def execute_step(step_index):
            semaphore.acquire()
            try:
                print(f"Starting execution of step {step_index}")

                # NEW: Add span metadata for this step
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

                # 每个线程创建独立的TaskActorAgent实例
                task_actor_agent = TaskActorAgent(create_actor_instance(f"actor_for_step_{step_index}"), self.act_llm,
                                                  self.vision_llm, self.tool_llm, self.plan_id)
                result = task_actor_agent.act(question=question, step_index=step_index)
                print(f"Completed execution of step {step_index} with result: {result}")
                result_queue.put((step_index, result))
            finally:
                semaphore.release()

        # 为每个ready_step创建并执行线程
        # ThreadingInstrumentor automatically propagates trace context
        threads = []
        for step_index in ready_steps:
            thread = Thread(target=execute_step, args=(step_index,))
            thread.start()
            threads.append(thread)

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 收集结果
        while not result_queue.empty():
            step_index, result = result_queue.get()
            results[step_index] = result

        return results
```

**Key Changes**:
1. Session ID propagated to all LLM instances in `__init__`
2. `@observe` decorator on `execute()`, `execute_actor()`, `execute_steps()`
3. Trace metadata set with session_id, question, plan_id
4. Step-level metadata in parallel execution

---

### Step 5: Update Evaluation Scripts

**Files**: `cosight_evals.py`, `cosight_evals_ChineseSimpleQA.py`, `cosight_evals_hle.py`

**Add to the beginning of each file**:

```python
# Add imports at top
import atexit
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse

# ... existing imports ...

# At the beginning of if __name__ == '__main__':
if __name__ == '__main__':

    # NEW: Initialize Langfuse observability
    print("\n=== Langfuse Observability Setup ===")
    initialize_langfuse()
    print("=== Langfuse Setup Complete ===\n")

    # NEW: Register shutdown handler to flush traces
    atexit.register(shutdown_langfuse)

    # ... rest of existing code ...
```

**Example for `cosight_evals.py`**:

```python
if __name__ == '__main__':

    # NEW: Initialize Langfuse observability
    print("\n=== Langfuse Observability Setup ===")
    initialize_langfuse()
    print("=== Langfuse Setup Complete ===\n")

    # NEW: Register shutdown handler
    atexit.register(shutdown_langfuse)

    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = WORKSPACE_PATH.as_posix()
    os.environ['RESULTS_PATH'] = WORKSPACE_PATH.as_posix()

    manus = manus()

    results = gaia_level1(process_message=manus,
                          task_id=[
                              "55aeb0ce-9170-4959-befb-59f6116887a4"
                          ],
                          split='test',
                          postcall=save_results
                          )

    datestr = datetime.datetime.today().strftime('%Y%m%d%H%M%S')
    save_results(results, (WORKSPACE_PATH / f'result_{datestr}.json').as_posix())

    # 移动文件
    try:
        shutil.move("logs/console.log", WORKSPACE_PATH)
        print(f"文件已移动到 {WORKSPACE_PATH}")
    except FileNotFoundError:
        print("❌ 文件不存在，请检查路径！")
    except Exception as e:
        print(f"发生错误：{e}")
```

---

## 6. Code Examples

### 6.1 Complete Minimal Example

Here's a minimal working example showing the core pattern:

```python
# test_manus_tracing.py
import os
import atexit
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Initialize Langfuse
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
initialize_langfuse()
atexit.register(shutdown_langfuse)

# Import Manus and LLMs
from app.manus.manus import Manus
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision

# Setup workspace
WORKSPACE_PATH = "./test_workspace"
os.makedirs(WORKSPACE_PATH, exist_ok=True)
os.environ['WORKSPACE_PATH'] = WORKSPACE_PATH

# Create and execute Manus
manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
result = manus.execute("Write a simple analysis of Python programming language")
print(f"Final result: {result}")
```

### 6.2 Multi-Route Example (HLE Pattern)

```python
# cosight_evals_hle.py example with tracing
import atexit
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse, observe

if __name__ == '__main__':

    # Initialize Langfuse
    initialize_langfuse()
    atexit.register(shutdown_langfuse)

    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = WORKSPACE_PATH.as_posix()

    # Create two Manus instances with different LLMs
    manus_route1 = manus_route1()  # Radical expert
    manus_route2 = manus_route2()  # Conservative expert

    # Each manus instance will have its own session_id
    # Both will be traced independently

    for task_id in task_ids:
        # Route 1 execution
        result1, analysis1 = hle(process_message=manus_route1, task_id=task_id)

        # Route 2 execution
        result2, analysis2 = hle(process_message=manus_route2, task_id=task_id)

        # Post-judgment
        final_answer = post_judge_hle(manus_route2, question, answer1, answer2, analysis1, analysis2)
```

---

## 7. Testing & Validation

### 7.1 Test with Tracing Disabled

```bash
# Set in .env
ENABLE_LANGFUSE=false

# Run evaluation
python cosight_evals.py
```

**Expected**:
- No Langfuse initialization messages
- Application runs normally
- No performance overhead
- No errors related to Langfuse

### 7.2 Test with Tracing Enabled

```bash
# Set in .env
ENABLE_LANGFUSE=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Run evaluation
python cosight_evals.py
```

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

### 7.3 Validation Checklist

Go to Langfuse dashboard (https://cloud.langfuse.com) and verify:

- [ ] **Traces appear**: You see new traces in the dashboard
- [ ] **Session grouping works**: All traces for one Manus execution share same session_id
- [ ] **Span hierarchy correct**:
  - Root: `manus_execute`
  - Children: `llm_create_with_tools`, `execute_steps_parallel`, etc.
- [ ] **Parallel steps nested**: Multiple `execute_step_X` spans under `execute_steps_parallel`
- [ ] **LLM calls tracked**: Token counts, model names, latencies visible
- [ ] **Metadata captured**: Question, plan_id, step descriptions present
- [ ] **No orphaned traces**: All spans properly nested

### 7.4 Performance Testing

```python
import time

# Test without tracing
os.environ['ENABLE_LANGFUSE'] = 'false'
start = time.time()
result1 = manus.execute("Test question")
time_without_tracing = time.time() - start

# Test with tracing
os.environ['ENABLE_LANGFUSE'] = 'true'
start = time.time()
result2 = manus.execute("Test question")
time_with_tracing = time.time() - start

overhead = ((time_with_tracing - time_without_tracing) / time_without_tracing) * 100
print(f"Tracing overhead: {overhead:.2f}%")
```

**Expected**: < 5% overhead

---

## 8. Troubleshooting

### 8.1 Common Issues

#### Issue: "ThreadingInstrumentor not installed" warning

**Symptom**:
```
[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed
```

**Solution**:
```bash
pip install opentelemetry-instrumentation-threading
```

#### Issue: Parallel steps create separate root traces

**Symptoms**:
- Each `execute_step_X` appears as separate root trace
- No parent-child relationship
- Different session_ids

**Diagnosis**:
1. Check ThreadingInstrumentor is initialized:
   ```python
   # In langfuse_config.py
   ThreadingInstrumentor().instrument()  # This line must be executed
   ```

2. Verify initialization happens **before** creating threads

**Solution**:
- Ensure `initialize_langfuse()` is called at the very beginning of your script
- Ensure `opentelemetry-instrumentation-threading` is installed

#### Issue: Session ID not grouping traces

**Symptoms**:
- Traces appear but not grouped
- Session filter shows no results

**Diagnosis**:
1. Check session_id is set on Plan:
   ```python
   print(f"Plan session_id: {manus.plan.session_id}")
   ```

2. Check session_id propagated to LLMs:
   ```python
   print(f"LLM session_id: {manus.act_llm.session_id}")
   ```

3. Verify `update_current_trace()` is called with session_id:
   ```python
   get_langfuse_client().update_current_trace(session_id=self.plan.session_id)
   ```

**Solution**:
- Always use `update_current_trace(session_id=...)`, not `update_current_span()`
- Set session_id **before** making any LLM calls
- Ensure session_id is the same string across all calls

#### Issue: No traces appearing in dashboard

**Diagnosis**:
1. Check credentials:
   ```python
   # Test connection
   from langfuse import Langfuse
   client = Langfuse(
       host=os.getenv('LANGFUSE_HOST'),
       public_key=os.getenv('LANGFUSE_PUBLIC_KEY'),
       secret_key=os.getenv('LANGFUSE_SECRET_KEY')
   )
   client.auth_check()  # Should not raise exception
   ```

2. Ensure `shutdown_langfuse()` is called:
   ```python
   import atexit
   atexit.register(shutdown_langfuse)
   ```

3. Check for errors in output

**Solution**:
- Verify credentials are correct
- Ensure application exits cleanly (not killed)
- Check network connectivity to Langfuse host

### 8.2 Debugging Tips

**Enable Debug Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In langfuse_config.py
logger.setLevel(logging.DEBUG)
```

**Verify Trace Context in Thread**:
```python
from opentelemetry import trace

def execute_step(step_index):
    # Check if context exists
    current_span = trace.get_current_span()
    if current_span.is_recording():
        print(f"✅ Step {step_index} has trace context")
    else:
        print(f"❌ Step {step_index} missing trace context")

    # ... rest of step execution
```

**Manual Trace Inspection**:
```python
# After execution, check trace
if is_langfuse_enabled():
    client = get_langfuse_client()
    # Flush to ensure upload
    client.flush()
    print("Check dashboard for traces")
```

---

## 9. Summary

### 9.1 What You've Implemented

1. **Core Infrastructure**: `langfuse_config.py` with ThreadingInstrumentor
2. **LLM Tracing**: ChatLLM wrapped with Langfuse instrumentation
3. **Session Management**: Plan-based session IDs
4. **Manus Tracing**: Full execution flow traced
5. **Parallel Execution**: Thread context propagation working
6. **Graceful Degradation**: Works with tracing disabled

### 9.2 Key Benefits

- **Unified Sessions**: Each Manus task = one session, all operations grouped
- **Parallel Visibility**: See all parallel steps and their relationships
- **LLM Insights**: Token usage, costs, latencies automatically tracked
- **Tool Tracking**: Future extension point for tool execution tracing
- **Zero Overhead When Disabled**: No performance impact when ENABLE_LANGFUSE=false

### 9.3 Next Steps

1. **Tool Execution Tracing**: Add `@observe` decorators to tool execution in TaskActorAgent
2. **Custom Metrics**: Add business-specific metadata (e.g., plan success rate)
3. **Alerts**: Set up Langfuse alerts for high-cost queries or failures
4. **Sampling**: Implement sampling for high-volume production use
5. **Dashboard**: Create custom Langfuse dashboard for Manus metrics

---

## Appendix A: File Modification Checklist

- [ ] Create `app/manus/llm/langfuse_config.py`
- [ ] Modify `app/manus/llm/chat_llm.py`
- [ ] Modify `app/manus/task/todolist.py`
- [ ] Modify `app/manus/manus.py`
- [ ] Modify `cosight_evals.py`
- [ ] Modify `cosight_evals_ChineseSimpleQA.py`
- [ ] Modify `cosight_evals_hle.py`
- [ ] Update `requirements.txt`
- [ ] Update `.env` with Langfuse credentials
- [ ] Test with ENABLE_LANGFUSE=false
- [ ] Test with ENABLE_LANGFUSE=true
- [ ] Verify traces in Langfuse dashboard

---

## Appendix B: Quick Reference

### Environment Variables
```bash
ENABLE_LANGFUSE=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

### Key Functions
```python
# Initialize (once at startup)
initialize_langfuse()

# Register shutdown (once at startup)
atexit.register(shutdown_langfuse)

# Get client
client = get_langfuse_client()

# Decorate functions
@observe(name="function_name")
def my_function():
    pass

# Set session on trace
client.update_current_trace(session_id="my-session")

# Add metadata to span
client.update_current_span(metadata={"key": "value"})
```

### Validation Commands
```bash
# Test tracing disabled
ENABLE_LANGFUSE=false python cosight_evals.py

# Test tracing enabled
ENABLE_LANGFUSE=true python cosight_evals.py

# Check traces
# Go to: https://cloud.langfuse.com
```

---

**End of Guide**

This guide provides everything you need to implement tracing in the Manus system. Follow the steps in order, test thoroughly, and refer to the troubleshooting section if you encounter issues. Happy tracing!
