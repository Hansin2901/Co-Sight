# ReportBench Integration Instructions for Manus

## Executive Summary
This document provides complete instructions for integrating the Manus research system with the ReportBench evaluation benchmark. The goal is to adapt Manus's multi-step research workflow to produce citation-rich reports that can be evaluated by ReportBench's citation quality metrics.

---

## 1. Understanding ReportBench Requirements

### 1.1 What is ReportBench?
ReportBench is an academic benchmark that evaluates AI systems' ability to generate well-cited survey reports. It focuses on:
- **Citation Quality**: Are claims properly supported by cited sources?
- **Citation Placement**: Are citations placed immediately adjacent to the statements they support?
- **Citation Format**: Inline `[URL]` citations (not footnotes or bibliographies)

### 1.2 Input Format
ReportBench provides:
- **arXiv ID**: Unique identifier for each research task (e.g., `2301.00001`)
- **Task Description**: A research question or survey topic requiring comprehensive investigation

### 1.3 Expected Output Format
For each task, produce a JSON file named `{arxiv_id}.json` with structure:
```json
{
  "response": "The complete report text with inline citations [https://example.com/source1] placed immediately after supported claims [https://arxiv.org/abs/2024.12345]."
}
```

**Critical Citation Requirements:**
- Citations must be inline URLs: `[https://example.com/full/url/path]`
- Citations must be placed **immediately adjacent** to the claim they support
- Multiple citations for one claim should be consecutive: `[URL1] [URL2]`
- No spaces between citation and the claim it supports
- Citations should appear throughout the report, not just at the end

**Example of Good Citation Placement:**
```
Transformer models have revolutionized NLP [https://arxiv.org/abs/1706.03762].
Recent work has shown that scaling to larger models improves performance [https://arxiv.org/abs/2001.08361] [https://arxiv.org/abs/2005.14165].
```

**Example of Bad Citation Placement:**
```
Transformer models have revolutionized NLP. Recent work has shown improvements.

References:
[1] https://arxiv.org/abs/1706.03762
```

---

## 2. Understanding Manus Architecture

### 2.1 How Manus Works
Manus is an enhanced Co-Sight system with:
1. **Planning Phase**: Creates multi-step research plan
2. **Execution Phase**: Executes each step using various tools
3. **Tool Tracking**: Records all tool calls in `plan.step_tools`
4. **Finalization Phase**: Synthesizes findings into final report

### 2.2 Tool Recording Mechanism
Manus automatically records tool executions in the `Plan` object:

**Access Pattern:**
```python
from app.manus.task.task_manager import TaskManager

plan = TaskManager.get_plan(manus.plan_id)
tool_records = plan.step_tools  # Dictionary of tool calls by step
```

**Data Structure:**
```python
plan.step_tools = {
    "Step 1: Research transformer architectures": [
        {
            "tool": "search_google",
            "args": {"query": "transformer neural networks 2024"},
            "result": "[{'url': 'https://arxiv.org/abs/...', 'title': '...', 'snippet': '...'}, ...]"
        },
        {
            "tool": "search_wiki",
            "args": {"entity": "Transformer (machine learning)"},
            "result": "[{'url': 'https://en.wikipedia.org/wiki/...', 'content': '...'}]"
        }
    ],
    "Step 2: Investigate attention mechanisms": [
        {
            "tool": "search_google",
            "args": {"query": "attention mechanism improvements"},
            "result": "[{'url': 'https://example.com/...', ...}]"
        }
    ]
}
```

### 2.3 Tool Result Formats
Different search tools return URLs in their results:

**Google Search** (`search_google`):
```python
[
    {"url": "https://...", "title": "...", "snippet": "..."},
    {"url": "https://...", "title": "...", "snippet": "..."}
]
```

**Wikipedia Search** (`search_wiki`):
```python
[
    {"url": "https://en.wikipedia.org/wiki/...", "content": "...", "title": "..."}
]
```

**Tavily Search** (`tavily_search`):
```python
[
    {"url": "https://...", "title": "...", "content": "...", "score": 0.95}
]
```

**arXiv Search** (`search_arxiv`):
```python
[
    {"url": "https://arxiv.org/abs/...", "title": "...", "summary": "...", "authors": [...]}
]
```

### 2.4 Current Output Format
Manus's `execute()` method returns a plain text report without citations:
```python
result = manus.execute(question)
# Returns: "Transformers are a type of neural network architecture..."
```

---

## 3. Implementation Scope: What Needs to Be Built

### 3.1 Component Overview
We need to build **3 main components**:

1. **Citation Extractor**: Extract all URLs from `plan.step_tools`
2. **Citation Injector**: Use LLM to inject citations inline into final report
3. **ReportBench Entry Point**: Wrapper that runs Manus and formats output

### 3.2 Component 1: Citation Extractor

**Purpose**: Extract all source URLs that Manus used during research

**Input**: `plan.step_tools` dictionary from Manus execution

**Output**: List of citation objects with metadata

**Algorithm**:
```python
def extract_citations(plan):
    """
    Extract all URLs from plan.step_tools across all steps and tools

    Returns:
        List[Dict]: [
            {
                "url": "https://arxiv.org/abs/2024.12345",
                "title": "Transformer Advances",
                "snippet": "Brief description...",
                "step": "Step 1: Research transformers",
                "tool": "search_google",
                "context": "Search query: transformer neural networks 2024"
            },
            ...
        ]
    """
    citations = []

    for step_name, tool_records in plan.step_tools.items():
        for record in tool_records:
            tool_name = record.get('tool')
            tool_args = record.get('args', {})
            result_str = record.get('result', '')

            # Parse result string back to data structure
            try:
                result_data = ast.literal_eval(result_str)
            except:
                continue

            # Extract URLs based on tool type
            if tool_name in ['search_google', 'tavily_search', 'search_wiki', 'search_arxiv']:
                if isinstance(result_data, list):
                    for item in result_data:
                        if isinstance(item, dict) and 'url' in item:
                            citations.append({
                                'url': item['url'],
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet') or item.get('content', '')[:200],
                                'step': step_name,
                                'tool': tool_name,
                                'context': f"Search query: {tool_args.get('query', tool_args.get('entity', ''))}"
                            })

    return citations
```

**Edge Cases to Handle**:
- Tool results that are not lists
- Malformed JSON strings in results
- Missing URL fields
- Duplicate URLs (should we deduplicate?)
- Empty results from failed tool calls

### 3.3 Component 2: Citation Injector

**Purpose**: Take Manus's plain text report and inject inline citations using LLM intelligence

**Why Use LLM?**:
- The final report is synthesized by the LLM and doesn't directly quote sources
- We need intelligent matching between claims in the report and URLs from tool calls
- The LLM can determine which citations support which claims based on:
  - Search queries that led to the URL
  - Snippet/content from the URL
  - Context of the step that used the URL
  - Semantic similarity between report claims and source content

**Input**:
1. `original_report`: Plain text report from Manus (no citations)
2. `citations`: List of citation objects from extractor

**Output**: Report with inline `[URL]` citations properly placed

**Algorithm**:
```python
def inject_citations(original_report, citations, llm):
    """
    Use LLM to intelligently inject citations into the report

    The LLM analyzes:
    - Each claim/statement in the report
    - Available citations with their context
    - Which citations best support each claim
    - Optimal placement for each citation

    Returns:
        str: Report with inline [URL] citations
    """

    # Build citation context for LLM
    citation_context = ""
    for idx, cit in enumerate(citations):
        citation_context += f"\n[{idx+1}] {cit['url']}"
        citation_context += f"\n    Title: {cit['title']}"
        citation_context += f"\n    Context: {cit['context']}"
        citation_context += f"\n    Snippet: {cit['snippet'][:150]}..."
        citation_context += f"\n    Used in: {cit['step']}\n"

    # Create prompt for LLM
    prompt = f"""You are a research paper editor. Your task is to add inline citations to a research report.

REPORT TO CITE:
{original_report}

AVAILABLE CITATIONS:
{citation_context}

INSTRUCTIONS:
1. Read through the report and identify all factual claims that need citations
2. For each claim, determine which citation(s) from the list best support it
3. Add inline citations in the format [URL] immediately after the claim they support
4. Multiple citations for one claim should be consecutive: [URL1] [URL2]
5. Do not add citations to general statements that don't need support
6. Preserve the exact wording and structure of the original report
7. Output the complete report with citations added

CRITICAL CITATION RULES:
- Use ONLY URLs from the AVAILABLE CITATIONS list above
- Format: [https://full.url.here] (full URL in square brackets)
- Place citation immediately after the claim, before punctuation or after punctuation
- Do not add footnotes, superscripts, or bibliography sections
- Do not add any preamble or explanation, just output the cited report

OUTPUT THE CITED REPORT:"""

    # Call LLM to inject citations
    cited_report = llm.chat_to_llm([
        {"role": "user", "content": prompt}
    ])

    return cited_report
```

**Alternative Approach (Structured)**:
If the LLM approach is unreliable, we can use a more structured approach:

```python
def inject_citations_structured(original_report, citations, llm):
    """
    1. Split report into sentences
    2. For each sentence, ask LLM: "Which citations (if any) support this claim?"
    3. Inject citations after each sentence based on LLM response
    4. Reassemble report
    """
    import re

    sentences = re.split(r'([.!?]+)', original_report)
    cited_sentences = []

    for sentence in sentences:
        if sentence.strip() and not re.match(r'^[.!?]+$', sentence):
            # Ask LLM which citations support this sentence
            matching_citations = find_supporting_citations(sentence, citations, llm)

            # Add citations after sentence
            cited_sentence = sentence
            for cit in matching_citations:
                cited_sentence += f" [{cit['url']}]"

            cited_sentences.append(cited_sentence)
        else:
            cited_sentences.append(sentence)

    return ''.join(cited_sentences)
```

**Quality Considerations**:
- Should we validate that citations are relevant? (re-run LLM to check?)
- How many citations per claim is optimal?
- Should we prioritize certain source types (arXiv > Wikipedia > blog)?
- How to handle reports with 100+ potential citations?

### 3.4 Component 3: ReportBench Entry Point

**Purpose**: Provide a clean interface for running ReportBench evaluations

**Input**: ReportBench task (arXiv ID or task description)

**Output**: JSON file in ReportBench format

**Implementation**:
```python
# File: evals/reportbench/reportbench_runner.py

import json
import os
from app.manus.manus import Manus
from app.manus.task.task_manager import TaskManager
from llm import set_model, get_llm_config_for_plan, get_llm_config_for_act, get_llm_config_for_tool, get_llm_config_for_vision

def run_reportbench_task(arxiv_id, task_description, output_dir="evals/reportbench/outputs"):
    """
    Run a single ReportBench task using Manus

    Args:
        arxiv_id: Unique ID for this task (e.g., "2301.00001")
        task_description: Research question/topic
        output_dir: Where to save output JSON

    Returns:
        dict: {"response": "cited report text"}
    """

    # 1. Initialize Manus with LLM models
    llm_for_plan = set_model(get_llm_config_for_plan())
    llm_for_act = set_model(get_llm_config_for_act())
    llm_for_tool = set_model(get_llm_config_for_tool())
    llm_for_vision = set_model(get_llm_config_for_vision())

    manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)

    # 2. Execute Manus research workflow
    print(f"Running Manus for task {arxiv_id}: {task_description}")
    original_report = manus.execute(task_description)
    print(f"Generated report ({len(original_report)} chars)")

    # 3. Extract citations from tool calls
    plan = TaskManager.get_plan(manus.plan_id)
    citations = extract_citations(plan)
    print(f"Extracted {len(citations)} citations from {len(plan.step_tools)} steps")

    # 4. Inject citations into report using LLM
    cited_report = inject_citations(original_report, citations, llm_for_act)
    print(f"Injected citations into report")

    # 5. Format output for ReportBench
    output = {
        "response": cited_report
    }

    # 6. Save to file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{arxiv_id}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved output to {output_path}")
    return output


def run_reportbench_batch(tasks_file, output_dir="evals/reportbench/outputs"):
    """
    Run multiple ReportBench tasks from a file

    Args:
        tasks_file: JSON file with list of tasks
            [
                {"arxiv_id": "2301.00001", "question": "..."},
                {"arxiv_id": "2301.00002", "question": "..."}
            ]
    """
    with open(tasks_file, 'r') as f:
        tasks = json.load(f)

    results = []
    for task in tasks:
        try:
            result = run_reportbench_task(
                task['arxiv_id'],
                task['question'],
                output_dir
            )
            results.append({
                "arxiv_id": task['arxiv_id'],
                "status": "success"
            })
        except Exception as e:
            print(f"Error on task {task['arxiv_id']}: {e}")
            results.append({
                "arxiv_id": task['arxiv_id'],
                "status": "failed",
                "error": str(e)
            })

    return results


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 3:
        print("Usage: python reportbench_runner.py <arxiv_id> <task_description>")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    task_description = sys.argv[2]

    run_reportbench_task(arxiv_id, task_description)
```

### 3.5 File Structure
Create this directory structure:
```
evals/reportbench/
├── reportbench_runner.py       # Main entry point
├── citation_extractor.py       # Extract URLs from step_tools
├── citation_injector.py        # Inject citations using LLM
├── inputs/                     # ReportBench task files
│   └── tasks.json
├── outputs/                    # Generated JSON outputs
│   ├── 2301.00001.json
│   └── 2301.00002.json
└── README.md                   # Documentation
```

---

## 4. Testing Strategy

### 4.1 Unit Tests

**Test Citation Extractor**:
```python
def test_citation_extractor():
    # Mock plan.step_tools data
    mock_plan = create_mock_plan_with_tools()

    citations = extract_citations(mock_plan)

    assert len(citations) > 0
    assert all('url' in cit for cit in citations)
    assert all(cit['url'].startswith('http') for cit in citations)
```

**Test Citation Injector**:
```python
def test_citation_injector():
    report = "Transformers are widely used. They use attention mechanisms."
    citations = [
        {"url": "https://arxiv.org/abs/1706.03762", "title": "Attention Is All You Need"}
    ]

    cited_report = inject_citations(report, citations, mock_llm)

    assert "[https://arxiv.org/abs/1706.03762]" in cited_report
    assert len(cited_report) > len(report)  # Citations were added
```

### 4.2 Integration Test

**Test Full Pipeline**:
```python
def test_full_reportbench_pipeline():
    arxiv_id = "test_001"
    question = "What are the key features of transformer architectures?"

    output = run_reportbench_task(arxiv_id, question, output_dir="test_outputs")

    # Verify output format
    assert "response" in output
    assert len(output["response"]) > 100

    # Verify citations exist
    assert "[http" in output["response"]

    # Verify JSON file created
    assert os.path.exists(f"test_outputs/{arxiv_id}.json")
```

### 4.3 Manual Quality Check

Run the existing test script to verify:
```bash
uv run test_manus_citations.py
```

This should output:
- ✅ Citations extracted successfully
- ✅ Number of citations found (>0)
- ✅ Sample citation URLs

Then manually inspect a generated report to check:
- Are citations placed next to relevant claims?
- Are citation URLs valid and relevant?
- Is the citation format correct `[URL]`?
- Does the report read naturally with citations?

---

## 5. Configuration Requirements

### 5.1 Environment Variables
Ensure `.env` has:
```bash
# LLM Configuration
API_KEY=your_api_key_here
API_BASE_URL=https://api.provider.com/v1
MODEL_NAME=model-name
PROXY=http://proxy:80  # If needed for API but not search tools

# Search Tool APIs (optional but recommended)
GOOGLE_API_KEY=your_google_api_key
SEARCH_ENGINE_ID=your_search_engine_id
TAVILY_API_KEY=your_tavily_api_key
```

### 5.2 Language Settings
Already fixed in:
- `app/manus/agent/planner/prompt/planner_prompt.py:74` → `Language: English`
- `app/manus/agent/actor/prompt/actor_prompt.py:100` → `Language: English`

### 5.3 Proxy Settings
Already fixed in:
- `app/manus/tool/search_util.py:41` → `proxy = None`
- `app/manus/tool/google_search_util.py:38,88` → `proxy = None`
- `app/manus/tool/browser_simulation.py:76` → `proxy = ""`

This allows search tools to work directly without corporate proxy.

---

## 6. Known Challenges and Solutions

### 6.1 Challenge: Citation Relevance
**Problem**: LLM might inject irrelevant citations or miss important ones

**Solutions**:
- Use detailed citation context (query, snippet, step) in LLM prompt
- Implement two-pass approach: first inject, then validate
- Add citation scoring: ask LLM to rate relevance 1-10
- Manual review of first few outputs to tune prompt

### 6.2 Challenge: Citation Density
**Problem**: Too many or too few citations

**Solutions**:
- Add guidance in LLM prompt: "Aim for 1-2 citations per major claim"
- Count citations in output and re-run if density is off
- Analyze ReportBench gold standard examples for optimal density

### 6.3 Challenge: URL Format Validation
**Problem**: LLM might malform URLs or add extra text

**Solutions**:
- Post-process output to validate URL format with regex
- Extract all `[...]` patterns and verify they're valid URLs
- Fix common errors: missing https://, extra spaces, truncated URLs

```python
def validate_and_fix_citations(cited_report):
    import re

    # Find all citation patterns
    pattern = r'\[([^\]]+)\]'

    def fix_citation(match):
        content = match.group(1)
        # Ensure it's a URL
        if not content.startswith('http'):
            return match.group(0)  # Keep as-is if not URL
        # Clean up common issues
        content = content.strip()
        return f"[{content}]"

    return re.sub(pattern, fix_citation, cited_report)
```

### 6.4 Challenge: Long Execution Time
**Problem**: Manus can take 2-5 minutes per task

**Solutions**:
- Implement batch processing with parallel execution
- Cache intermediate results
- Add progress indicators
- Consider reducing max steps in Manus for faster execution

### 6.5 Challenge: Tool Call Failures
**Problem**: Search tools might fail, resulting in no citations

**Solutions**:
- Add retry logic in Manus tool execution
- Implement fallback to alternative search tools
- Detect when no citations are available and add warning to output
- Consider using pre-fetched sources as backup

---

## 7. Success Criteria

### 7.1 Functional Requirements
- ✅ System generates valid JSON output in ReportBench format
- ✅ Reports contain inline `[URL]` citations
- ✅ Citations are extracted from Manus tool calls
- ✅ Citations are relevant to the claims they support
- ✅ All URLs are valid and properly formatted

### 7.2 Quality Requirements
- ✅ At least 80% of major claims have supporting citations
- ✅ No hallucinated citations (all URLs come from tool calls)
- ✅ Citations placed immediately adjacent to claims
- ✅ Report remains readable and well-structured with citations
- ✅ Execution completes within reasonable time (<5 min per task)

### 7.3 Evaluation Metrics
After implementation, evaluate using:
1. **Citation Coverage**: % of claims that have citations
2. **Citation Accuracy**: % of citations that are relevant
3. **Format Compliance**: % of citations in correct `[URL]` format
4. **URL Validity**: % of URLs that are accessible and correct
5. **ReportBench Score**: Official benchmark score if available

---

## 8. Implementation Checklist

### Phase 1: Core Implementation
- [ ] Create `evals/reportbench/` directory structure
- [ ] Implement `citation_extractor.py` with URL extraction logic
- [ ] Implement `citation_injector.py` with LLM-based injection
- [ ] Implement `reportbench_runner.py` main entry point
- [ ] Add error handling and logging throughout

### Phase 2: Testing
- [ ] Write unit tests for citation extractor
- [ ] Write unit tests for citation injector
- [ ] Run full integration test with real Manus execution
- [ ] Manually review generated outputs for quality
- [ ] Fix any bugs or quality issues discovered

### Phase 3: Optimization
- [ ] Tune LLM prompts for better citation placement
- [ ] Add citation validation and post-processing
- [ ] Implement batch processing for multiple tasks
- [ ] Add configuration options (citation density, formats, etc.)
- [ ] Document all code with docstrings

### Phase 4: Deployment
- [ ] Create README.md with usage instructions
- [ ] Add example tasks and expected outputs
- [ ] Test with various Gemini API configurations
- [ ] Push all changes to git branch
- [ ] Create pull request with comprehensive description

---

## 9. Command Reference

### Running Single Task
```bash
cd /home/user/Co-Sight
uv run evals/reportbench/reportbench_runner.py "2301.00001" "What are recent advances in transformers?"
```

### Running Batch Tasks
```bash
uv run evals/reportbench/reportbench_runner.py --batch evals/reportbench/inputs/tasks.json
```

### Testing Citation Tracking
```bash
uv run test_manus_citations.py
```

### Validating Outputs
```bash
python evals/reportbench/validate_outputs.py evals/reportbench/outputs/
```

---

## 10. Next Steps After Reading This Document

1. **Verify Environment**: Ensure Gemini API is configured and working
2. **Run Citation Test**: Execute `test_manus_citations.py` to verify tool tracking works
3. **Implement Extractor**: Start with `citation_extractor.py` (simplest component)
4. **Test Extractor**: Run on real Manus output to verify URL extraction
5. **Implement Injector**: Create `citation_injector.py` with LLM prompt
6. **Test Injector**: Verify citations are placed correctly
7. **Build Entry Point**: Create `reportbench_runner.py` to tie it together
8. **Run Integration Test**: Execute full pipeline on sample task
9. **Iterate on Quality**: Tune prompts and logic based on output quality
10. **Document and Deploy**: Add README and push to repository

---

## 11. Questions to Resolve

Before starting implementation, clarify:

1. **LLM Choice**: Which model should be used for citation injection? (Gemini, same as Manus, different?)
2. **Citation Density**: How many citations per paragraph is ideal?
3. **Source Priority**: Should we prioritize certain sources (arXiv > Wikipedia)?
4. **Deduplication**: Should we deduplicate URLs that appear in multiple steps?
5. **Fallbacks**: What if no citations are found (tool failures)?
6. **Validation**: Should we implement citation relevance validation?
7. **Performance**: Is 5min per task acceptable or do we need optimization?
8. **Batch Size**: How many tasks do we need to process?

---

## Appendix A: Example Flow

**Input Task:**
```
arxiv_id: "2024.00001"
question: "What are the latest advances in transformer neural networks?"
```

**Manus Execution:**
1. Plans 3 steps: "Research transformers", "Investigate attention", "Analyze applications"
2. Executes search_google, search_arxiv, search_wiki tools
3. Records tool calls in plan.step_tools
4. Generates final report: "Transformers have evolved significantly..."

**Citation Extraction:**
```python
citations = [
    {
        "url": "https://arxiv.org/abs/1706.03762",
        "title": "Attention Is All You Need",
        "step": "Research transformers",
        "context": "Search: transformer architecture"
    },
    {
        "url": "https://arxiv.org/abs/2301.12345",
        "title": "Efficient Transformers",
        "step": "Investigate attention",
        "context": "Search: attention mechanisms 2024"
    }
]
```

**Citation Injection:**
```
Original: "Transformers have evolved significantly with new attention mechanisms."

Cited: "Transformers have evolved significantly [https://arxiv.org/abs/1706.03762] with new attention mechanisms [https://arxiv.org/abs/2301.12345]."
```

**Final Output (`2024.00001.json`):**
```json
{
  "response": "Transformers have evolved significantly [https://arxiv.org/abs/1706.03762] with new attention mechanisms [https://arxiv.org/abs/2301.12345] that improve efficiency and performance..."
}
```

---

## Document Version
- **Version**: 1.0
- **Created**: 2024-11-13
- **Last Updated**: 2024-11-13
- **Author**: Claude (Manus Integration Assistant)
