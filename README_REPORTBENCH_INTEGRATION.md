# Co-Sight ReportBench Integration

Complete integration guide for evaluating Co-Sight's academic survey reports using the official ReportBench benchmark.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Understanding Results](#understanding-results)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This integration allows you to:

- **Generate** academic survey reports using Co-Sight
- **Evaluate** reports using ReportBench's official metrics:
  - **Citation Match Rate**: % of citations with semantically correct content
  - **Non-Cited Accuracy**: Fact-checking for statements without citations
  - **Precision/Recall**: Coverage vs ground truth reference lists

**Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Report Generation (Co-Sight)                            │
│    run_cosight_reportbench.py                              │
│    ├── Reads: ReportBench_v1.1.jsonl (queries)            │
│    └── Outputs: Co-Sight-outputs/{arxiv_id}.json          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Evaluation (ReportBench Official Pipeline)              │
│    evaluate_with_reportbench.sh                            │
│    ├── statement_evaluator.py  (citation + fact-checking) │
│    ├── related_work_evaluator.py  (precision/recall)      │
│    └── metrics_calculator.py  (aggregate metrics)         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Results                                                  │
│    evaluation-results/                                      │
│    ├── statement-results/aggregate_metrics.csv            │
│    └── related-work-results/evaluation_results.csv        │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. ReportBench Repository

Clone ReportBench alongside Co-Sight:

```bash
cd /path/to/projects/
git clone https://github.com/ByteDance-BandAI/ReportBench.git
```

**Expected directory structure**:
```
projects/
├── Co-Sight/              # This repository
└── ReportBench/           # Official ReportBench repo
    ├── ReportBench_v1.1.jsonl
    ├── ReportBench_v1.1_GT/
    ├── statement_evaluator.py
    ├── related_work_evaluator.py
    └── metrics_calculator.py
```

### 2. Python Dependencies

**Co-Sight** (already installed if Co-Sight works):
```bash
cd Co-Sight/
pip install -r requirements.txt
```

**ReportBench** (required for evaluation):
```bash
cd ../ReportBench/
pip install -r requirements.txt
```

### 3. API Keys

ReportBench evaluation requires API keys for:
- **Firecrawl** (web scraping for fact-checking)
- **OpenAI** or compatible LLM (semantic matching)

---

## Setup

### Step 1: Configure Environment Variables

Copy the example environment file:

```bash
cd Co-Sight/
cp .env.reportbench.example .env
```

**Edit `.env` and add your keys**:

```bash
# ReportBench Evaluation Keys (REQUIRED for evaluation)
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Co-Sight Keys (REQUIRED for generation)
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxx
LANGFUSE_PUBLIC_KEY=pk-xxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-xxxxxxxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Where to get keys**:
- **Firecrawl**: https://www.firecrawl.dev/ (free tier available)
- **OpenAI**: https://platform.openai.com/api-keys
- **Google**: https://aistudio.google.com/apikey (for Gemini)
- **Langfuse**: https://cloud.langfuse.com/ (observability, optional)

### Step 2: Update ReportBench Configuration

The ReportBench scripts need to load environment variables. Add to `ReportBench/.env`:

```bash
cd ../ReportBench/
cat > .env << 'EOF'
# Load from Co-Sight .env (adjust path if needed)
source ../Co-Sight/.env
EOF
```

Or copy keys directly:
```bash
cp ../Co-Sight/.env ./
```

### Step 3: Verify Setup

Check that all required files exist:

```bash
cd Co-Sight/

# Co-Sight scripts
ls -l run_cosight_reportbench.py
ls -l evaluate_with_reportbench.sh
ls -l run_full_evaluation.py
ls -l reportbench_config.json

# ReportBench data
ls -l ../ReportBench/ReportBench_v1.1.jsonl
ls -l ../ReportBench/ReportBench_v1.1_GT/
```

---

## Quick Start

### Option 1: Run Everything (Recommended)

Generate reports + run evaluation in one command:

```bash
cd Co-Sight/
python run_full_evaluation.py
```

This will:
1. Generate reports for all papers in `reportbench_config.json`
2. Run ReportBench evaluation
3. Display aggregate metrics

### Option 2: Step-by-Step

**Step 1: Generate reports**
```bash
python run_cosight_reportbench.py
```

**Step 2: Run evaluation**
```bash
./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results
```

**Step 3: View results**
```bash
cat evaluation-results/statement-results/aggregate_metrics.csv
```

---

## Configuration

### Main Config: `reportbench_config.json`

This file controls which papers to evaluate:

```json
{
  "arxiv_ids": [
    "2312.04861",    // Add/remove arxiv IDs here
    "2308.06419",
    "2308.15985"
  ],
  "reportbench_dataset": "../ReportBench/ReportBench_v1.1.jsonl",
  "reportbench_gt_dir": "../ReportBench/ReportBench_v1.1_GT",
  "output_dir": "Co-Sight-outputs",
  "evaluation_dir": "evaluation-results"
}
```

**Finding ArXiv IDs**:

View all available papers:
```bash
cat ../ReportBench/ReportBench_v1.1.jsonl | jq -r '.arxiv_id + " - " + .title'
```

Or list just the IDs:
```bash
cat ../ReportBench/ReportBench_v1.1.jsonl | jq -r '.arxiv_id'
```

**Configuration Tips**:

- **Small test**: Start with 1-3 papers (faster iteration)
  ```json
  "arxiv_ids": ["2312.04861"]
  ```

- **Full benchmark**: Use all papers from the dataset
  ```bash
  # Generate full list
  cat ../ReportBench/ReportBench_v1.1.jsonl | jq -r '.arxiv_id' | jq -R -s -c 'split("\n")[:-1]'
  ```

- **By topic**: Filter papers by title/field
  ```bash
  # Find computer vision papers
  cat ../ReportBench/ReportBench_v1.1.jsonl | jq -r 'select(.title | contains("vision")) | .arxiv_id'
  ```

---

## Usage

### Basic Commands

#### 1. Generate Reports Only
```bash
python run_cosight_reportbench.py
```

**Options**:
```bash
# Use custom config
python run_cosight_reportbench.py --config my_config.json

# Override arxiv IDs from command line
python run_cosight_reportbench.py --arxiv-ids 2312.04861 2308.06419
```

#### 2. Evaluate Existing Reports
```bash
./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results
```

#### 3. Full Pipeline
```bash
python run_full_evaluation.py
```

**Options**:
```bash
# Custom config
python run_full_evaluation.py --config my_config.json

# Skip generation (evaluate only)
python run_full_evaluation.py --skip-generation

# Skip evaluation (generate only)
python run_full_evaluation.py --skip-evaluation
```

### Advanced Workflows

#### A. Iterative Development

Generate once, evaluate multiple times (useful when tuning ReportBench params):

```bash
# Step 1: Generate reports (slow, run once)
python run_cosight_reportbench.py

# Step 2: Evaluate (fast, can repeat)
./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results-v1
./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results-v2
```

#### B. Batch Processing

Process papers in batches:

```bash
# Batch 1: Papers 1-5
cat > batch1_config.json << 'EOF'
{
  "arxiv_ids": ["2312.04861", "2308.06419", "2308.15985", "2311.12345", "2310.67890"],
  "reportbench_dataset": "../ReportBench/ReportBench_v1.1.jsonl",
  "reportbench_gt_dir": "../ReportBench/ReportBench_v1.1_GT",
  "output_dir": "outputs-batch1",
  "evaluation_dir": "eval-batch1"
}
EOF

python run_full_evaluation.py --config batch1_config.json
```

#### C. Parallel Evaluation

Evaluate multiple Co-Sight variants:

```bash
# Run different Co-Sight versions
python run_cosight_reportbench.py --config config_v1.json
python run_cosight_reportbench.py --config config_v2.json

# Evaluate both
./evaluate_with_reportbench.sh outputs-v1 ../ReportBench/ReportBench_v1.1_GT eval-v1
./evaluate_with_reportbench.sh outputs-v2 ../ReportBench/ReportBench_v1.1_GT eval-v2

# Compare
diff eval-v1/statement-results/aggregate_metrics.csv eval-v2/statement-results/aggregate_metrics.csv
```

---

## Understanding Results

### Output Structure

After running evaluation, you'll get:

```
evaluation-results/
├── statement-results/
│   ├── 2312.04861/
│   │   ├── citations.csv           # Per-citation analysis
│   │   ├── no_citations.csv        # Non-cited statements
│   │   ├── scraped_content.csv     # Fetched web content
│   │   ├── verified_citations.csv  # Semantic matching results
│   │   └── verified_no_citations.csv
│   ├── aggregate_metrics.csv       # 📊 MAIN METRICS (all papers)
│   └── summary.csv                 # Per-paper summaries
│
└── related-work-results/
    ├── evaluation_results.csv      # 📊 Precision/Recall metrics
    ├── 2312.04861_ground_truth_urls.csv
    └── 2312.04861_survey_urls.csv
```

### Key Metrics Files

#### 1. `aggregate_metrics.csv` - Overall Performance

**Main metrics** (averaged across all papers):

| Metric | Description | Good Score |
|--------|-------------|------------|
| `match_rate` | % of cited statements that match source content | > 0.80 |
| `non_cited_accuracy` | % of non-cited statements verified as factual | > 0.75 |
| `total_citations` | Total citation statements extracted | Varies |
| `total_no_citations` | Total non-cited statements extracted | Varies |
| `avg_matched_citations` | Average citations matched per paper | Higher is better |

**Example**:
```csv
arxiv_id,total_citations,matched_citations,match_rate,non_cited_accuracy
aggregate,127,98,0.77,0.82
```

**Interpretation**:
- **77% match rate**: 77% of citations have semantically correct content
- **82% non-cited accuracy**: 82% of non-cited claims are factually accurate

#### 2. `evaluation_results.csv` - Precision/Recall

**Metrics**:

| Metric | Formula | Description | Good Score |
|--------|---------|-------------|------------|
| `precision` | `TP / (TP + FP)` | % of cited papers in ground truth | > 0.70 |
| `recall` | `TP / (TP + FN)` | % of ground truth papers cited | > 0.60 |
| `f1_score` | `2 * (P * R) / (P + R)` | Harmonic mean | > 0.65 |
| `ground_truth_count` | `TP + FN` | Number of papers in ground truth | Reference |
| `extracted_url_count` | `TP + FP` | Number of papers cited by Co-Sight | Reference |

**Example**:
```csv
arxiv_id,precision,recall,f1_score,ground_truth_count,extracted_url_count
2312.04861,0.75,0.68,0.71,50,45
```

**Interpretation**:
- **75% precision**: 75% of cited papers are in ground truth (low false positives)
- **68% recall**: Co-Sight found 68% of ground truth papers (missed 32%)
- **F1 = 0.71**: Balanced trade-off between precision and recall

#### 3. Per-Paper Details

**`citations.csv`** - Citation-level analysis:
```csv
arxiv_id,citation_text,matched,match_score,scraped_url,match_reason
2312.04861,"Recent work [Smith et al., 2024] shows...",true,0.89,https://arxiv.org/...,Semantic match
2312.04861,"According to [Jones, 2023]...",false,0.45,https://...,Content mismatch
```

**`no_citations.csv`** - Non-cited statement verification:
```csv
arxiv_id,statement_text,verified,verification_score,reason
2312.04861,"Deep learning has transformed computer vision",true,0.92,Common knowledge verified
2312.04861,"AlexNet achieved 99% accuracy on ImageNet",false,0.23,Factually incorrect
```

### Interpreting Scores

#### Citation Match Rate

| Score | Interpretation |
|-------|----------------|
| **> 0.85** | Excellent - Citations are highly accurate |
| **0.70 - 0.85** | Good - Most citations are reliable |
| **0.50 - 0.70** | Fair - Some citation issues |
| **< 0.50** | Poor - Many inaccurate citations |

**Common issues**:
- **Low score**: Co-Sight may be citing papers without reading full content
- **High score**: Strong retrieval + summarization pipeline

#### Non-Cited Accuracy

| Score | Interpretation |
|-------|----------------|
| **> 0.80** | Excellent - Claims are well-grounded |
| **0.65 - 0.80** | Good - Mostly accurate statements |
| **0.50 - 0.65** | Fair - Some unsupported claims |
| **< 0.50** | Poor - Many unverified statements |

**Common issues**:
- **Low score**: May indicate hallucination or overgeneralization
- **High score**: Conservative writing with verifiable claims

#### Precision vs Recall Trade-off

| Scenario | Precision | Recall | Interpretation |
|----------|-----------|--------|----------------|
| **High P, Low R** | 0.85 | 0.45 | Conservative: Only cites highly relevant papers (misses some) |
| **Low P, High R** | 0.55 | 0.90 | Aggressive: Cites many papers (includes irrelevant ones) |
| **Balanced** | 0.70 | 0.70 | Good balance between coverage and relevance |
| **Both Low** | 0.40 | 0.45 | Poor retrieval or matching |
| **Both High** | 0.85 | 0.85 | Excellent retrieval and filtering |

---

## Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError: No module named 'pandas'"

**Solution**: Install ReportBench dependencies
```bash
cd ../ReportBench/
pip install -r requirements.txt
```

#### 2. "FIRECRAWL_API_KEY not set"

**Solution**: Add key to `.env` file
```bash
echo "FIRECRAWL_API_KEY=fc-your-key-here" >> .env
```

Get a free key at: https://www.firecrawl.dev/

#### 3. "No JSON output files found"

**Cause**: Report generation failed or wasn't run

**Solution**: Run generation first
```bash
python run_cosight_reportbench.py
```

Check for errors in output. Common issues:
- Missing `GOOGLE_API_KEY` for Gemini
- Co-Sight dependencies not installed

#### 4. "Ground truth directory not found"

**Cause**: ReportBench not cloned or wrong path

**Solution**: Clone ReportBench
```bash
cd ..
git clone https://github.com/ByteDance-BandAI/ReportBench.git
```

Update path in `reportbench_config.json`:
```json
"reportbench_gt_dir": "../ReportBench/ReportBench_v1.1_GT"
```

#### 5. Evaluation takes too long

**Cause**: Firecrawl scraping is slow for many papers

**Solutions**:
- **Start small**: Test with 1-3 papers first
- **Use caching**: ReportBench caches scraped content (rerun is faster)
- **Parallel batches**: Split papers across multiple runs

#### 6. Low citation match rates

**Possible causes**:
- **Co-Sight hallucination**: LLM generating fake citations
- **Wrong URLs**: Citations pointing to incorrect papers
- **Scraping failures**: Firecrawl couldn't fetch content

**Debug**:
```bash
# Check scraped content
cat evaluation-results/statement-results/2312.04861/scraped_content.csv

# Check failed citations
cat evaluation-results/statement-results/2312.04861/citations.csv | grep ",false,"
```

**Fixes**:
- Improve prompt to emphasize citation accuracy
- Add citation verification step in Co-Sight pipeline
- Use more reliable sources (arXiv PDFs vs web pages)

---

## Performance Benchmarks

### Expected Runtime

| Phase | Papers | Time | Notes |
|-------|--------|------|-------|
| **Generation** | 1 paper | 5-15 min | Depends on Co-Sight LLM speed |
| **Generation** | 10 papers | 1-3 hours | Parallelizable with batches |
| **Evaluation** | 1 paper | 2-5 min | Depends on Firecrawl scraping |
| **Evaluation** | 10 papers | 20-50 min | Cached on reruns |

### Cost Estimates

**Co-Sight Generation** (per paper):
- **Gemini API**: $0.50 - $2.00 (depends on model and paper complexity)
- **Langfuse**: Free tier sufficient for testing

**ReportBench Evaluation** (per paper):
- **Firecrawl**: ~100-200 scrapes → $0.50 - $1.00 (free tier: 500/month)
- **OpenAI**: ~50-100 LLM calls → $0.10 - $0.30 (semantic matching)

**Total per paper**: ~$1 - $4 depending on complexity

---

## Advanced Topics

### Custom Evaluation Metrics

Extend ReportBench metrics by modifying the evaluation scripts:

```bash
cd ../ReportBench/
# Edit metrics_calculator.py to add custom metrics
```

### Using Different LLMs

**For Co-Sight generation**: Edit `llm.py` to use different models

**For ReportBench evaluation**: Edit `ReportBench/config.py`:
```python
LLM_PROVIDER = "openai"  # or "gemini", "claude", etc.
```

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Run ReportBench Evaluation
  run: |
    cd Co-Sight/
    python run_full_evaluation.py
    
- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: reportbench-results
    path: Co-Sight/evaluation-results/
```

---

## References

- **ReportBench Paper**: [arXiv:2XXX.XXXXX](https://arxiv.org)
- **ReportBench GitHub**: https://github.com/ByteDance-BandAI/ReportBench
- **Co-Sight Repository**: [Your repo URL]
- **Firecrawl Docs**: https://docs.firecrawl.dev/

---

## Support

**Questions or Issues?**

1. Check [Troubleshooting](#troubleshooting) section
2. Review ReportBench documentation
3. Open an issue in Co-Sight repository

**Contributing**: Pull requests welcome for improvements to the integration!
