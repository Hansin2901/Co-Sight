# Quick Start Guide

## TL;DR - Run DeepResearch Bench in 3 Steps

### 0. Enable LangFuse Observability (Optional but Recommended)

To track all LLM calls, tool executions, and benchmark runs:

```bash
# Edit your .env file
ENABLE_LANGFUSE=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Each research task will be traced as a single trace with all parallel executions properly tracked!

### 1. Convert Official Prompts to CSV

```bash
cd /home/user/Co-Sight/benchmarks

# All 100 prompts
python convert_deepresearch_to_csv.py

# Only English (50 prompts)
python convert_deepresearch_to_csv.py --language en

# Only Chinese (50 prompts)
python convert_deepresearch_to_csv.py --language zh

# First 5 for testing
python convert_deepresearch_to_csv.py --start 0 --end 5
```

### 2. Run Benchmark

```bash
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/cosight_results.jsonl
```

### 3. Evaluate with Official Scripts

```bash
# Copy results to eval location
cp results/cosight_results.jsonl eval_scripts/data/test_data/raw_data/cosight.jsonl

# Run evaluation (requires GEMINI_API_KEY)
cd eval_scripts
export GEMINI_API_KEY="your_key_here"
python deepresearch_bench_race.py --model_name cosight

# Check results
cat results/race/cosight/race_result.txt
```

## Using Your Own Prompts

Create a CSV file:
```csv
task_id,question,attachments
my_001,"Research the history of quantum computing",
my_002,"Analyze trends in renewable energy",
```

Then run:
```bash
python runner.py --input my_prompts.csv --output my_results.jsonl
```

## Resume Interrupted Runs

```bash
python runner.py \
  --input data/deepresearch_prompts.csv \
  --output results/cosight_results.jsonl \
  --resume
```

## Run Specific Range

```bash
# Tasks 0-10
python runner.py --input prompts.csv --output results.jsonl --start 0 --end 10

# Tasks 10-20
python runner.py --input prompts.csv --output results.jsonl --start 10 --end 20
```

## Test Installation

```bash
./test_runner.sh
```

This will run 1 task to verify everything works.

## Output Format

Results are in JSONL format (one JSON per line):
```json
{"id": "dr_001", "prompt": "question...", "article": "research report with citations"}
```

This format is compatible with DeepResearch Bench evaluation scripts.

## Troubleshooting

**No .env file?**
- Copy `.env_template` to `.env` in Co-Sight root
- Fill in your API keys

**Import errors?**
- Run from benchmarks directory: `cd /home/user/Co-Sight/benchmarks`

**Evaluation fails?**
- Set `GEMINI_API_KEY` environment variable
- Install eval dependencies: `cd eval_scripts && pip install -r requirements.txt`

## What Gets Created

```
benchmarks/
├── data/deepresearch_prompts.csv     # Your input prompts
├── results/cosight_results.jsonl     # Your results
└── work_space/task_*/                # Working directories (one per task)
```

## Next Steps

- See `README.md` for detailed documentation
- Check `eval_scripts/README.md` for evaluation details
- Compare your results with the leaderboard at https://huggingface.co/spaces/Ayanami0730/DeepResearch-Leaderboard
