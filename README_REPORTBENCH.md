# ReportBench Integration with Co-Sight

## Overview
ReportBench evaluation has been integrated into Co-Sight similar to the GAIA, HLE, and ChineseSimpleQA benchmarks.

## Files Created

### 1. Evaluation Module (`evals/reportbench/`)
- **`dataset.py`**: Loads and standardizes ReportBench dataset from JSONL format
- **`scorer.py`**: Evaluates report quality (citations, structure, length, etc.)
- **`reportbench.py`**: Main evaluation loop function
- **`__init__.py`**: Module exports

### 2. Entry Point Script
- **`cosight_evals_reportbench_new.py`**: Main script to run ReportBench evaluation
  - Similar structure to `cosight_evals.py` (GAIA), `cosight_evals_hle.py`, etc.
  - Includes Langfuse observability
  - Saves results to `results/ReportBench/`

## Usage

### Basic Usage
```bash
# Activate virtual environment
source .venv/bin/activate

# Run on specific tasks
python cosight_evals_reportbench_new.py
```

### Customization

Edit `cosight_evals_reportbench_new.py` to customize:

```python
# Run on specific arxiv_ids
results = reportbench(
    process_message=execute_fn,
    task_id=["2312.04861", "2308.06419"],  # Specific papers
    postcall=save_results
)

# Run on all tasks
results = reportbench(
    process_message=execute_fn,
    # No task_id parameter = run all
    postcall=save_results
)

# Limit number of tasks
results = reportbench(
    process_message=execute_fn,
    limit=10,  # Only first 10 tasks
    postcall=save_results
)

# Start from specific index
results = reportbench(
    process_message=execute_fn,
    start_idx=20,  # Skip first 20 tasks
    limit=10,      # Process 10 tasks
    postcall=save_results
)
```

## Output

### Results Location
- **Workspace**: `workspace/reportbench_YYYYMMDD_HHMMSS/`
- **Results JSON**: `results/ReportBench/reportbench_final_YYYYMMDD_HHMMSS.json`
- **Individual Reports**: `workspace/reportbench_YYYYMMDD_HHMMSS/{arxiv_id}/{arxiv_id}_report.md`

### Result Format
```json
{
  "eval": {
    "model": "gemini-2.5-flash",
    "dataset": "ReportBench_v1.1",
    "total_entries": 3,
    "successful": 3,
    "failed": 0,
    "success_rate": 1.0,
    "avg_quality_score": 1.0,
    "avg_word_count": 3227.3,
    "avg_citations": 29.0,
    "avg_duration_seconds": 528.0,
    "date": "2025-11-20 06:27:02"
  },
  "detail": [...]
}
```

### Quality Metrics
Each report is evaluated on:
- **Word count**: Target 3000-5000 words
- **Citations**: Number of `[Author et al., Year]` citations
- **Structure**: Headers (H1, H2, H3)
- **Content**: Introduction, Conclusion sections
- **Quality Score**: 0-100% based on above criteria

## Integration Pattern

The integration follows the same pattern as other Co-Sight evaluations:

1. **Module in `evals/`**: Contains dataset loader, scorer, and main function
2. **Entry script**: `cosight_evals_*.py` at project root
3. **Manus executor**: Wraps Manus with output format support
4. **Langfuse observability**: Automatic tracing and logging
5. **Results saving**: Structured JSON with metrics

## Comparison with Other Benchmarks

| Benchmark | Module | Entry Script | Key Difference |
|-----------|--------|--------------|----------------|
| GAIA | `evals/gaia/` | `cosight_evals.py` | Question-answering with file attachments |
| HLE | `evals/gaia/hle.py` | `cosight_evals_hle.py` | Long-horizon evaluation |
| ChineseSimpleQA | `evals/gaia/ChineseSimpleQA.py` | `cosight_evals_ChineseSimpleQA.py` | Chinese language QA |
| **ReportBench** | **`evals/reportbench/`** | **`cosight_evals_reportbench_new.py`** | **Academic survey reports** |

## Dataset Location

The script looks for `ReportBench_v1.1.jsonl` in:
1. `../ReportBench/ReportBench_v1.1.jsonl` (parent directory)
2. `./ReportBench_v1.1.jsonl` (Co-Sight root)

Current location: `/Users/HansinPatwa/hansin/Projects/teleport/ReportBench/`
