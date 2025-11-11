# Co-Sight Benchmark Runner

Simple benchmark runner for evaluating Co-Sight on research benchmarks like DeepResearch Bench.

## Overview

This tool allows you to:
1. Input prompts via CSV (or convert from benchmark datasets)
2. Run them through Co-Sight
3. Output results in benchmark-specific formats
4. Evaluate using official benchmark scripts

## Quick Start

### 1. Setup

```bash
# Install DeepResearch Bench evaluation dependencies
cd benchmarks/eval_scripts
pip install -r requirements.txt
cd ../..

# Set up environment variables for evaluation (if using DeepResearch evaluation)
export GEMINI_API_KEY="your_gemini_api_key_here"
export JINA_API_KEY="your_jina_api_key_here"  # Optional, for FACT evaluation
```

### LangFuse Observability (Optional but Recommended)

The benchmark runner automatically integrates with LangFuse to trace all LLM calls and tool executions. To enable:

```bash
# In your .env file
ENABLE_LANGFUSE=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com  # or your self-hosted instance
```

**Benefits:**
- 📊 **Single trace per research task** - All parallel thread executions grouped together
- 🔍 **Detailed observability** - Track every LLM call, tool execution, and decision
- 💰 **Cost tracking** - Monitor API costs across benchmark runs
- ⚡ **Performance metrics** - Analyze execution time and bottlenecks
- 🐛 **Debugging** - Inspect failed tasks with full context

The runner will automatically:
1. Initialize LangFuse at startup
2. Create one trace per research task
3. Propagate context to all parallel threads (via OpenTelemetry)
4. Flush all traces on completion

View your traces at: https://cloud.langfuse.com (or your configured host)

### 2. Prepare Prompts

**Option A: Use your own CSV**

Create a CSV file with this format:
```csv
task_id,question,attachments
test_001,"Research the current state of LLMs in 2024...",
test_002,"Analyze climate change impact on food security...",
```

**Option B: Convert DeepResearch Bench official prompts**

```bash
cd benchmarks

# Convert all prompts
python convert_deepresearch_to_csv.py

# Convert only English prompts
python convert_deepresearch_to_csv.py --language en

# Convert only Chinese prompts
python convert_deepresearch_to_csv.py --language zh

# Convert first 10 prompts
python convert_deepresearch_to_csv.py --start 0 --end 10
```

This will create `data/deepresearch_prompts.csv`

### 3. Run Benchmark

```bash
cd benchmarks

# Run on your CSV
python runner.py \
  --input data/example_prompts.csv \
  --output results/my_results.jsonl

# Run on official DeepResearch prompts
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/deepresearch_results.jsonl

# Run specific range
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/deepresearch_results.jsonl \
  --start 0 \
  --end 5

# Resume from checkpoint (skip already completed tasks)
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/deepresearch_results.jsonl \
  --resume
```

### 4. Evaluate Results

The runner outputs results in DeepResearch Bench format (JSONL):
```json
{"id": "dr_001", "prompt": "Research question...", "article": "Research report with citations..."}
```

**Move results to evaluation directory:**
```bash
# Copy results to DeepResearch eval location
mkdir -p eval_scripts/data/test_data/raw_data
cp results/deepresearch_results.jsonl eval_scripts/data/test_data/raw_data/cosight.jsonl

# Run official evaluation
cd eval_scripts
python deepresearch_bench_race.py --model_name cosight

# Results will be in:
# - results/race/cosight/race_result.txt (RACE scores)
# - results/fact/cosight/fact_result.txt (FACT scores, if enabled)
```

## Directory Structure

```
benchmarks/
├── runner.py                           # Main benchmark runner
├── convert_deepresearch_to_csv.py      # Convert official prompts to CSV
├── formatters/                         # Output formatters
│   ├── __init__.py
│   └── deepresearch_formatter.py       # DeepResearch format
├── data/                               # Input data
│   ├── example_prompts.csv             # Example CSV
│   └── deepresearch_prompts.csv        # Converted official prompts
├── results/                            # Output results
│   └── *.jsonl                         # Benchmark results
├── work_space/                         # Co-Sight working directories
│   └── task_*/                         # Per-task workspaces
└── eval_scripts/                       # Official DeepResearch Bench repo
    ├── deepresearch_bench_race.py      # RACE evaluation script
    ├── data/
    │   ├── prompt_data/
    │   │   └── query.jsonl             # Official 100 prompts
    │   └── test_data/
    │       └── raw_data/
    │           └── <model_name>.jsonl  # Place your results here
    └── results/
        ├── race/<model_name>/          # RACE evaluation results
        └── fact/<model_name>/          # FACT evaluation results
```

## CSV Input Format

Your input CSV should have these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `task_id` | Yes | Unique identifier for the task |
| `question` | Yes | The research question/prompt |
| `attachments` | No | Semicolon-separated file paths (e.g., `file1.pdf;file2.png`) |

Example:
```csv
task_id,question,attachments
dr_001,"Research the history of AI",
dr_002,"Analyze this data",/path/to/data.csv
dr_003,"Review these documents",/path/doc1.pdf;/path/doc2.pdf
```

## Output Format

Results are saved as JSONL (one JSON object per line) in DeepResearch Bench format:

```json
{"id": "dr_001", "prompt": "Research question", "article": "Full research report with citations"}
{"id": "dr_002", "prompt": "Another question", "article": "Another research report..."}
```

## Advanced Usage

### Resume from Checkpoint

If your benchmark run is interrupted, use `--resume` to skip already completed tasks:

```bash
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/deepresearch_results.jsonl \
  --resume
```

The runner will:
- Check which task_ids are already in the output file
- Skip those tasks
- Continue with remaining tasks

### Process Specific Tasks

```bash
# First 10 tasks
python runner.py --input prompts.csv --output results.jsonl --start 0 --end 10

# Tasks 10-20
python runner.py --input prompts.csv --output results.jsonl --start 10 --end 20

# Last 10 tasks (if you have 100 total)
python runner.py --input prompts.csv --output results.jsonl --start 90
```

## Troubleshooting

### Common Issues

**Issue: ModuleNotFoundError**
```bash
# Make sure you're running from the benchmarks directory
cd /home/user/Co-Sight/benchmarks
python runner.py ...
```

**Issue: Environment variables not set**
```bash
# Check your .env file in the root Co-Sight directory
# Make sure API_KEY, API_BASE_URL, MODEL_NAME are set
cat ../.env
```

**Issue: Evaluation fails**
```bash
# Make sure you set evaluation API keys
export GEMINI_API_KEY="your_key_here"

# Check the results file format
head -1 results/deepresearch_results.jsonl
# Should output: {"id": "...", "prompt": "...", "article": "..."}
```

## Evaluation Metrics

### RACE Framework
Evaluates research report quality across:
- **Comprehensiveness**: Coverage breadth and depth
- **Insight/Depth**: Quality of analysis
- **Instruction-Following**: Adherence to requirements
- **Readability**: Clarity and organization

### FACT Framework
Evaluates information retrieval:
- **Citation Accuracy**: % of correctly supported citations
- **Effective Citations**: Average verified citations per task

## Notes

- Results are saved incrementally (after each task completes)
- Each task gets its own workspace directory under `work_space/`
- Co-Sight execution logs are in the main Co-Sight log files
- Failed tasks will have `[ERROR]` in the article field but won't stop the run

## Example Workflow

```bash
# 1. Convert first 5 English prompts from DeepResearch
cd benchmarks
python convert_deepresearch_to_csv.py --language en --start 0 --end 5

# 2. Run benchmark
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/cosight_test.jsonl

# 3. Move to eval directory
cp results/cosight_test.jsonl eval_scripts/data/test_data/raw_data/cosight_test.jsonl

# 4. Evaluate
cd eval_scripts
export GEMINI_API_KEY="your_key"
python deepresearch_bench_race.py --model_name cosight_test

# 5. Check results
cat results/race/cosight_test/race_result.txt
```

## Contributing

To add support for other benchmarks (e.g., GAIA):
1. Create a formatter in `formatters/<benchmark>_formatter.py`
2. Update `runner.py` to use the appropriate formatter
3. Add conversion script if needed
4. Document the format in this README
