# COMPREHENSIVE COMPARISON: MANUS vs COSIGHT AGENT IMPLEMENTATIONS

## EXECUTIVE SUMMARY

**Status**: Manus is a fully implemented planner-actor agent system. Cosight is NOT a standalone agent implementation but rather a minimal resource directory containing only a font file (simhei.ttf).

---

## 1. DIRECTORY STRUCTURE COMPARISON

### 1.1 Manus Directory Structure

```
/home/user/Co-Sight/app/manus/
├── agent/                          # Core agent implementations
│   ├── base/
│   │   ├── base_agent.py          # Foundational agent logic (242 lines)
│   │   ├── common_skill.py         # Shared skill utilities
│   │   └── skill_to_tool.py        # Converts skills to LLM tools
│   ├── planner/                    # Planning agent
│   │   ├── instance/
│   │   │   ├── planner_agent_instance.py
│   │   │   └── planner_agent_skill.py
│   │   ├── prompt/
│   │   │   └── planner_prompt.py
│   │   └── task_plannr_agent.py    # Planner implementation (85 lines)
│   └── actor/                      # Execution agent
│       ├── instance/
│       │   ├── actor_agent_instance.py
│       │   ├── actor_agent_skill.py
│       │   └── paper_releated_skill.py
│       ├── prompt/
│       │   └── actor_prompt.py
│       └── task_actor_agent.py     # Actor implementation (135 lines)
├── llm/
│   ├── __init__.py
│   └── chat_llm.py                # LLM integration layer
├── task/                           # Task and plan management
│   ├── __init__.py
│   ├── plan_report_manager.py      # Event-based reporting
│   ├── task_manager.py
│   ├── time_record_util.py         # Performance tracking
│   └── todolist.py                 # Plan data structure (325 lines)
├── gate/                           # Format validation & control
│   ├── __init__.py
│   ├── step_gate.py                # Stub for step gating
│   └── format_gate.py              # Type checking decorator (200 lines)
├── memory/                         # Memory system (stub)
│   └── __init__.py
├── context/                        # Context management (stub)
│   └── __init__.py
├── record/                         # Example results & records
│   ├── core.csv
│   └── gdp_demo/
│       ├── core.csv
│       ├── core_visualization.png
│       └── gdp_report.pdf
├── tool/                           # Extensive toolkit (8,624 lines, 22 files)
│   ├── act_toolkit.py              # Step marking & execution
│   ├── plan_toolkit.py             # Plan creation/updates
│   ├── search_toolkit.py            # Web & wiki search
│   ├── file_toolkit.py              # File operations
│   ├── code_toolkit.py              # Code execution
│   ├── image_analysis_toolkit.py    # Vision analysis
│   ├── video_analysis_toolkit.py    # Video processing
│   ├── audio_toolkit.py             # Audio processing
│   ├── document_processing_toolkit.py # Doc extraction
│   ├── arxiv_toolkit.py             # Research paper handling
│   ├── excel_toolkit.py             # Excel processing
│   ├── pptx_toolkit.py              # PowerPoint handling
│   ├── scrape_website_toolkit.py    # Web scraping
│   ├── fetch_website_content.py     # Content retrieval
│   ├── browser_simulation.py        # Browser automation
│   ├── terminate_toolkit.py         # Task termination
│   ├── deep_search/                 # Advanced search
│   │   ├── deep_search.py
│   │   ├── actions/
│   │   ├── common/
│   │   ├── model/
│   │   └── services/
│   └── interpreters/                # Code execution backends
│       ├── base.py
│       ├── subprocess_interpreter.py
│       └── internal_python_interpreter.py
├── manus.py                        # Main orchestrator (188 lines)
├── __init__.py
└── requirements.txt
```

**Total Lines of Code in Core Agent**: 650 lines (base + planner + actor + main)
**Total Lines of Code in Toolkits**: 8,624 lines

### 1.2 Cosight Directory Structure

```
/home/user/Co-Sight/app/cosight/
└── tool/
    └── simhei.ttf                 # Chinese font file (9.75 MB)
```

**Conclusion**: Cosight is NOT a separate agent implementation. It only contains a shared font resource.

### 1.3 Agent Dispatcher Directory Structure

```
/home/user/Co-Sight/app/agent_dispatcher/
├── domain/
│   └── plan/
│       └── action/
│           └── skill/
│               └── mcp/                    # Model Context Protocol integration
│                   ├── const.py
│                   ├── engine.py
│                   └── server.py
├── infrastructure/
│   ├── entity/
│   │   ├── AgentInstance.py               # Agent instance definition
│   │   ├── AgentTemplate.py               # Agent template definition
│   │   ├── Skill.py                       # Skill definition
│   │   └── SkillFunction.py               # Skill function wrapper
│   └── util/
│       ├── constants.py
│       ├── count_token.py
│       ├── regex_util.py
│       ├── time_util.py
│       └── setup_util_for_ci_coverage.py
└── __init__.py
```

**Purpose**: Infrastructure framework for agent definition, skill management, and MCP integration.

---

## 2. AGENT ARCHITECTURE DIFFERENCES

### 2.1 Manus: Planner-Actor Pattern

**Architecture Overview**:
```
Question/Task
    ↓
[TaskPlannerAgent] ← Creates plan with steps & dependencies (DAG)
    ↓
[Plan Data Structure] ← Maintains state: steps, status, dependencies
    ↓
[TaskActorAgent] ← Executes ready steps in parallel
    ↓
[Tool Execution] ← Runs actual tasks via toolkits
    ↓
Results & Reports
```

#### 2.1.1 Planner Agent (`/home/user/Co-Sight/app/manus/agent/planner/task_plannr_agent.py`)

**Key Methods**:
- `create_fact()` - Extract facts from user question
- `create_plan()` - Generate initial plan with steps and dependencies
- `re_plan()` - Adjust plan based on execution progress
- `finalize_plan()` - Extract final answer from plan results

**Planner Workflow**:
```python
# From manus.py (lines 72-95)
def execute(self, question, output_format=""):
    # 1. Create initial facts
    self.task_planner_agent.create_fact(question)
    
    # 2. Create plan with retries
    while not self.plan.get_ready_steps() and retry_count < 3:
        create_result = self.task_planner_agent.create_plan(create_task, output_format)
        retry_count += 1
    
    # 3. Execute steps in parallel
    while True:
        ready_steps = self.plan.get_ready_steps()
        if not ready_steps:
            break
        results = self.execute_steps(question, ready_steps)
        
        # 4. Re-plan based on execution results
        re_plan_result = self.task_planner_agent.re_plan(question, output_format)
    
    # 5. Finalize and extract answer
    return self.task_planner_agent.finalize_plan(question, output_format)
```

**Skills** (2 tools):
- `create_plan`: Creates plan with title, steps, dependencies
- `update_plan`: Updates existing plan while preserving completed steps

#### 2.1.2 Actor Agent (`/home/user/Co-Sight/app/manus/agent/actor/task_actor_agent.py`)

**Key Methods**:
- `act()` - Execute a single step
- `single_act()` - Single task execution without step context
- `update_fact()` - Update facts based on execution results

**Actor Execution Pattern**:
```python
# Parallel execution of multiple ready steps (lines 107-144)
def execute_steps(self, question, ready_steps):
    results = {}
    semaphore = Semaphore(min(5, len(ready_steps)))  # Max 5 concurrent
    
    for step_index in ready_steps:
        # Each step gets its own TaskActorAgent instance
        task_actor_agent = TaskActorAgent(create_actor_instance(...), 
                                         self.act_llm, self.vision_llm, 
                                         self.tool_llm, self.plan_id)
        # Execute in parallel threads
        result = task_actor_agent.act(question=question, step_index=step_index)
```

**Skills** (18 tools):
- `execute_code` - Python code execution
- `search_google`, `search_wiki` - Web search
- `browser_use` - Browser automation
- `mark_step` - Step completion marking
- `file_saver`, `file_read`, `file_str_replace`, `file_find_in_content` - File operations
- `audio_recognition` - Speech-to-text
- `ask_question_about_image` - Image analysis
- `ask_question_about_video` - Video analysis
- `ask_question_by_extract_document_content` - Document processing
- `fetch_website_content` - Web content extraction
- `search_papers`, `download_papers` - ArXiv integration
- `download_file` - File downloads
- Plus MCP tools (registered dynamically)

### 2.2 Base Agent Logic (`base_agent.py`)

**Core Execution Loop**:
```python
# Lines 52-72
def execute(self, messages: List[Dict[str, Any]], step_index=None, plan: Plan = None, max_iteration=20):
    for i in range(max_iteration):
        # 1. Call LLM with tools
        response = self.llm.create_with_tools(messages, self.tools)
        
        # 2. Process response and execute tool calls
        result = self._process_response(response, messages, step_index, plan)
        if result:  # Termination condition met
            return result
    
    # 3. Handle max iterations exceeded
    return self._handle_max_iteration(messages, step_index)
```

**Tool Execution Features**:
- **Parallel execution** of multiple tool calls via ThreadPoolExecutor
- **Tool result recording** in plan for step execution history
- **MCP tool support** for external model context protocol tools
- **Async function support** via asyncio for async tools

### 2.3 Unique Manus Components

#### 2.3.1 Plan Data Structure (`todolist.py` - 325 lines)

**Features**:
- DAG-based step dependencies: `{step_index: [dependent_indices]}`
- Step status tracking: not_started, in_progress, completed, blocked
- Tool execution history per step
- Fact management
- Progress tracking

**Key Methods**:
```python
get_ready_steps()           # Returns steps ready for execution
mark_step()                 # Update step status & notes
record_tool_execution()     # Log tool calls & results
get_step_execution_history() # Retrieve tool execution history
format()                    # Display plan with progress
```

#### 2.3.2 Format Gate (`format_gate.py` - 200 lines)

**Purpose**: Input/output type validation decorator
**Features**:
- Automatic type conversion (str↔dict, str↔list, str↔int, etc.)
- Async function support
- Docstring-based type parsing
- Error messages with conversion suggestions

**Usage**:
```python
@format_check(input_types={'step_index': int, 'step_status': str}, output_type=str)
def mark_step(self, step_index: int, step_status: str) -> str:
    ...
```

#### 2.3.3 Plan Report Manager (`plan_report_manager.py`)

**Purpose**: Event-based plan state reporting
**Events**: plan_created, plan_process, plan_result
**Implementation**: ThreadPoolExecutor-based async callbacks

#### 2.3.4 Record Directory (`record/`)

**Contents**:
- Example results demonstrating output format
- GDP demo: CSV data, visualization PNG, PDF report
- Used for validation and testing

### 2.4 Cosight vs Manus

| Aspect | Manus | Cosight |
|--------|-------|---------|
| **Agent Implementation** | Full planner-actor system | NOT an agent implementation |
| **Directory Purpose** | Core agent logic | Shared resources (font only) |
| **Files** | ~40+ Python files | 1 font file |
| **LOC** | 650 (core) + 8,624 (tools) | N/A |
| **Planning** | TaskPlannerAgent | N/A |
| **Execution** | TaskActorAgent | N/A |
| **Tool Count** | 18 native + MCP tools | N/A |

---

## 3. OUTPUT FORMAT DIFFERENCES

### 3.1 Manus Output Generation

**Plan Result Format**:
```python
# From task_plannr_agent.py (lines 64-72)
def finalize_plan(self, question, output_format=""):
    raw_result = self.execute(self.history, max_iteration=1)
    result = self.extract_pattern(raw_result, "final_answer")
    self.plan.set_plan_result(result)
    plan_report_event_manager.publish("plan_result", self.plan)
    return result
```

**Output Extraction** (lines 74-85):
- Uses regex pattern matching: `<final_answer>...</final_answer>`
- Fallback to raw result if pattern not found
- Publishes to event system for report generation

**Plan Display Format** (`todolist.py`):
```
Plan: [Title]
Progress: X/Y steps completed (Z%)
Status: X completed, Y in progress, Z blocked, W not started

Steps:
Step0:[✓] Step description
   Tool Execution History:
     -Tool: tool_name (args: {...}) (timestamp): result
   Notes: execution notes
Step1:[→] Next step
...
```

**Reporting Events**:
- `plan_created` - Initial plan created
- `plan_process` - After step execution
- `plan_result` - Final result ready

### 3.2 Tool Execution Recording

**Recorded Information** (lines 162-186 of todolist.py):
```python
self.step_tools[step].append({
    "tool_id": f"{tool_name}:{json.dumps(tool_args)}",
    "tool": tool_name,
    "args": tool_args,           # Input parameters
    "result": result,             # Tool output
    "timestamp": datetime.now().isoformat()
})
```

### 3.3 File Path Processing

**Path Replacement** (lines 263-303 of todolist.py):
- Converts absolute paths to workspace-relative paths
- Supports Windows and POSIX paths
- Handles Chinese book-quote syntax: `《filename.ext》`
- Extracts file references from step notes

---

## 4. KEY IMPLEMENTATION FILES

### 4.1 Main Entry Point

**File**: `/home/user/Co-Sight/app/manus/manus.py` (188 lines)

**Manus Class**:
```python
class Manus:
    def __init__(self, plan_llm, act_llm, tool_llm, vision_llm):
        # Initialize planner & actors
        self.plan_id = f"plan_{int(time.time())}"
        self.plan = Plan()
        self.task_planner_agent = TaskPlannerAgent(...)
    
    def execute(self, question, output_format="") -> str:
        # Orchestrates planning → execution → finalization
        ...
    
    def execute_steps(self, question, ready_steps) -> dict:
        # Parallel step execution with semaphore control
        ...
```

**Entry Usage** (lines 178-188):
```python
if __name__ == '__main__':
    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
    result = manus.execute("帮我写一篇中兴通讯的分析报告")
    print(f"final result is {result}")
```

### 4.2 Initialization and Configuration Files

**LLM Configuration** (`/home/user/Co-Sight/llm.py`):
- Creates ChatLLM instances for plan, act, tool, and vision tasks
- Configurable via environment variables or API keys

**Agent Instance Factories**:
- `planner_agent_instance.py`: Creates TaskPlannerAgent with 2 skills
- `actor_agent_instance.py`: Creates TaskActorAgent with 18 skills + MCP tools

### 4.3 Task Management

**TaskManager** (`task_manager.py`):
- Singleton pattern for plan storage: `TaskManager.set_plan(plan_id, plan)`
- Retrieval: `TaskManager.get_plan(plan_id)`

---

## 5. FEATURE DIFFERENCES

### 5.1 Unique Manus Features

| Feature | Purpose | Location |
|---------|---------|----------|
| **Planner Agent** | Task decomposition into steps | agent/planner/ |
| **Actor Agent** | Step execution | agent/actor/ |
| **DAG Dependencies** | Sequential/parallel step execution | task/todolist.py |
| **Format Gate** | Type validation & conversion | gate/format_gate.py |
| **Plan Events** | Real-time progress reporting | task/plan_report_manager.py |
| **Tool History** | Record all tool calls & results | task/todolist.py |
| **Parallel Execution** | Up to 5 concurrent step execution | manus.py lines 113 |
| **Code Execution** | Python + subprocess interpreters | tool/interpreters/ |
| **Deep Search** | Multi-step research with Tavily | tool/deep_search/ |
| **MCP Integration** | Extensible tool system | agent_dispatcher/domain/plan/action/skill/mcp/ |
| **Async Support** | Native async function support | agent/base/base_agent.py |
| **Vision Models** | Dedicated vision LLM path | agent/actor/ (separate llm param) |
| **Browser Automation** | Selenium-based web interaction | tool/browser_simulation.py |

### 5.2 Memory Module (Stub)

**File**: `/home/user/Co-Sight/app/manus/memory/__init__.py`
**Status**: Empty (1 line)
**Purpose**: Reserved for future memory system implementation

### 5.3 Context Module (Stub)

**File**: `/home/user/Co-Sight/app/manus/context/__init__.py`
**Status**: Empty (1 line)
**Purpose**: Reserved for context management implementation

### 5.4 Gate Module (Partial)

**File**: `/home/user/Co-Sight/app/manus/gate/step_gate.py`
```python
def fuse_gate():
    pass
```
**Status**: Stub function for future step fusion/gating logic

---

## 6. TOOL INTEGRATION ARCHITECTURE

### 6.1 Tool Conversion Pipeline

**Flow**:
```
Skill Definition (agent/*/instance/*_skill.py)
    ↓
convert_skill_to_tool() (agent/base/skill_to_tool.py)
    ↓
OpenAI Tool Format (for LLM tool_choice)
    ↓
BaseAgent.execute() executes selected tools
```

**Skill Definition Example** (actor_agent_skill.py):
```python
def execute_code_skill():
    return {
        'skill_name': 'execute_code',
        'skill_type': LOCAL_SKILL,
        'description_en': 'Execute Python code',
        'function': {
            'name': 'execute_code',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string', 'description': 'Python code'},
                    'step_index': {'type': 'integer'}
                }
            }
        }
    }
```

### 6.2 Toolkit Architecture

**22 Toolkit Files** covering:
- **Web Operations**: search_toolkit, scrape_website_toolkit, web_util
- **File Management**: file_toolkit, excel_toolkit, pptx_toolkit, pdf handling
- **Code Execution**: code_toolkit with subprocess & internal interpreters
- **Media Processing**: image_analysis_toolkit, video_analysis_toolkit, audio_toolkit
- **Research**: arxiv_toolkit, deep_search
- **Planning**: plan_toolkit, act_toolkit
- **Control**: terminate_toolkit

---

## 7. PROMPT ENGINEERING COMPARISON

### 7.1 Planner Prompt (`planner_prompt.py`)

**System Prompt Key Points**:
- Role: "planning assistant"
- Creates DAG-structured plans with step dependencies
- Supports re-planning when steps are blocked
- Preserves completed steps during replanning
- Handles up to 5 steps (constraint enforced in prompt)

**Key Prompt Sections**:
1. **Plan Creation Rules**: High-level steps, clear dependencies
2. **Replanning Rules**: Preserve status, handle blocked steps
3. **Finalization Rules**: Extract key factors, provide failure analysis

### 7.2 Actor Prompt (`actor_prompt.py`)

**System Prompt Key Points**:
- Role: "assistant helping complete complex tasks"
- Emphasis on careful planning before tool use
- Comprehensive tips for problem-solving strategies
- Environment awareness (OS, workspace, proxy)
- Language: English with Chinese tips

**Tips Include**:
- Image/video processing priority
- Wikipedia-first for fact verification
- Cross-checking answers via multiple methods
- Error handling and debugging guidance
- Token usage awareness

### 7.3 Prompt Differences

| Aspect | Planner | Actor |
|--------|---------|-------|
| **Scope** | Task decomposition | Task execution |
| **Tools** | create_plan, update_plan | 18+ execution tools |
| **Output** | Plan structure with DAG | Results & file paths |
| **Iteration** | Re-planning loops | Tool iteration loops |
| **Language Tips** | Limited | Extensive |

---

## 8. EXECUTION FLOW COMPARISON

### 8.1 Manus Execution Flow

```
1. User Input
   ↓
2. Manus.__init__() - Initialize with 4 LLMs
   ↓
3. manus.execute(question)
   ├─ TaskPlannerAgent.create_fact()
   │  └─ Extract facts via LLM
   │
   ├─ TaskPlannerAgent.create_plan() [Retry ×3]
   │  └─ LLM generates plan with steps & dependencies
   │
   ├─ WHILE loop: Get ready steps
   │  ├─ Plan.get_ready_steps() - Filter executable steps
   │  │
   │  ├─ execute_steps() [Parallel]
   │  │  ├─ Semaphore (max 5 concurrent)
   │  │  ├─ Create TaskActorAgent per step
   │  │  └─ task_actor_agent.act(question, step_index)
   │  │      ├─ BaseAgent.execute(messages, step_index, plan)
   │  │      │  ├─ LLM.create_with_tools(messages, tools)
   │  │      │  ├─ _process_response()
   │  │      │  │  ├─ No tool calls → return content
   │  │      │  │  └─ Tool calls → execute_tool_calls()
   │  │      │  │     ├─ ThreadPoolExecutor (parallel)
   │  │      │  │     ├─ _execute_tool_call(function_name, args)
   │  │      │  │     │  └─ Invoke toolkit function
   │  │      │  │     └─ plan.record_tool_execution() ← Records in plan
   │  │      │  └─ Check termination (mark_step or terminate)
   │  │      └─ ActToolkit.mark_step() updates plan status
   │  │
   │  ├─ Publish plan_process event
   │  │
   │  └─ TaskPlannerAgent.re_plan()
   │     └─ LLM adjusts plan based on progress
   │
   └─ TaskPlannerAgent.finalize_plan()
      ├─ Extract <final_answer>...</final_answer>
      ├─ Publish plan_result event
      └─ RETURN result
```

### 8.2 Key Differences from Typical Agent Patterns

**vs Standard ReAct Loop**:
- **Planning Phase**: Separate explicit planning before action
- **DAG Structure**: Dependencies enable partial parallelization
- **Plan Evolution**: Re-planning based on execution results
- **Tool History**: Complete execution trace per step
- **Multi-LLM**: Different LLMs for planning vs acting vs tools vs vision

---

## 9. SUMMARY TABLE

| Aspect | Manus | Cosight | Agent Dispatcher |
|--------|-------|---------|-----------------|
| **Type** | Agent Implementation | Resource Directory | Infrastructure Framework |
| **Lines of Code** | 650 + 8,624 toolkit | 0 (1 font file) | ~500 |
| **Agent Architecture** | Planner + Actor | N/A | Template/Instance framework |
| **Planning Logic** | TaskPlannerAgent | N/A | Task/Skill entities |
| **Execution Logic** | TaskActorAgent | N/A | AgentInstance |
| **Tool Count** | 18 + MCP | N/A | Configurable |
| **Parallelization** | Up to 5 steps | N/A | MCP-based |
| **Output Format** | Plan + results | N/A | Skill responses |
| **Reporting** | Event-based | N/A | Entity-based |
| **Memory** | Stub | N/A | Not applicable |
| **Context** | Stub | N/A | Not applicable |
| **Gate** | Format checker | N/A | Not applicable |
| **Record** | Example outputs | N/A | Not applicable |

---

## 10. CONCLUSIONS

### What Manus Has That Cosight Doesn't

1. **Complete Agent Implementation**: Planner-actor architecture
2. **Step-based Planning**: DAG with dependencies for complex tasks
3. **Parallel Execution**: Up to 5 concurrent steps
4. **Comprehensive Toolkits**: 22 toolkit modules, 8,600+ LOC
5. **Tool History Recording**: Complete execution trace
6. **Event-Based Reporting**: Real-time plan updates
7. **Format Validation**: Type checking & conversion via decorators
8. **Multi-LLM Support**: Separate models for plan/act/tool/vision
9. **Code Execution**: Python interpreter with sandbox support
10. **Browser Automation**: Selenium-based web interaction

### What Cosight Provides

**Only a Chinese font file** (simhei.ttf) used for visualization/reporting in HTML or image outputs.

### Agent Dispatcher's Role

Infrastructure layer providing:
- **Agent Templating**: Reusable agent definitions
- **Skill Management**: Standardized skill format
- **MCP Integration**: Extensible tool system via Model Context Protocol
- **Entity Framework**: AgentInstance, AgentTemplate, Skill definitions

---

