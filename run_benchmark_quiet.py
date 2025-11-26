#!/usr/bin/env python3
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
Clean ReportBench Evaluation Runner - Shows only high-level metrics.
Suppresses verbose output and shows dashboard-style progress.

Usage:
    python run_benchmark_quiet.py --limit 3
"""

import sys
import os
import io
import contextlib
import atexit
import datetime
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Suppress verbose imports
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from app.manus.manus import Manus
    from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
    from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision

# Paths
REPORTBENCH_DATASET_PATH = Path(__file__).parent.parent / "ReportBench" / "ReportBench_v1.1.jsonl"
TIMESTAMP = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
WORKSPACE_PATH = Path(__file__).parent / "workspace" / f"reportbench_{TIMESTAMP}"
LOG_PATH = Path(__file__).parent / "logs"
RESULTS_PATH = Path(__file__).parent / "results" / "ReportBench"

# Output format for academic survey reports
REPORT_OUTPUT_FORMAT = """
Generate a comprehensive academic survey report in markdown format with the following structure:

# [Topic Title]

## 1. Introduction
- Background and motivation (2-3 paragraphs)
- Research scope and objectives
- Brief overview of what will be covered

## 2. Main Body
Organize findings by themes/categories with clear subsections:

### 2.1 [Theme/Category 1]
- Key papers and their contributions
- Methods and approaches used
- Important findings and results
- Technical details where relevant

### 2.2 [Theme/Category 2]
[Continue with additional themes as appropriate...]

## 3. Challenges and Future Directions
- Current limitations and open problems
- Potential research directions
- Emerging trends

## 4. Conclusion
- Summary of key findings across all themes
- Overall assessment of the field's progress

**CRITICAL REQUIREMENTS:**
1. **Citations**: Include inline citations for ALL claims using format: [Author et al., Year] or [Paper Title, Year]
   - Example: "Recent work by [Smith et al., 2024] demonstrates..."
   - Example: "As shown in [Deep Learning for Autonomous Vehicles, 2023]..."
2. **Length**: Target 3000-5000 words for comprehensive coverage
3. **Structure**: Use clear markdown headers (##, ###) for organization
4. **Synthesis**: Don't just list papers - synthesize and compare approaches
5. **Technical depth**: Include technical details appropriate for academic audience
6. **Multiple sources**: Draw information from multiple papers, comparing and contrasting

Remember: You have access to paper titles, authors, publication dates, and summaries from your research steps. 
Use this information to create properly formatted citations throughout the report.
"""


def load_reportbench_dataset(dataset_path: Path, limit: Optional[int] = None, start_idx: int = 0) -> List[Dict]:
    """Load ReportBench dataset from JSONL file."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"ReportBench dataset not found at: {dataset_path}")
    
    entries = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < start_idx:
                continue
            if limit and len(entries) >= limit:
                break
            entry = json.loads(line.strip())
            entries.append(entry)
    
    return entries


def evaluate_report_quality(report: str, metadata: Dict) -> Dict:
    """Evaluate the quality of a generated report."""
    # Basic metrics
    word_count = len(report.split())
    char_count = len(report)
    
    # Citation analysis
    citation_brackets = report.count('[')
    et_al_count = report.count('et al.')
    year_pattern_count = sum(1 for i in range(2000, 2026) if str(i) in report)
    
    # Structure analysis
    h1_headers = report.count('\n# ')
    h2_headers = report.count('\n## ')
    h3_headers = report.count('\n### ')
    total_headers = h1_headers + h2_headers + h3_headers
    
    # Quality assessment
    has_introduction = 'introduction' in report.lower() or '## 1.' in report
    has_conclusion = 'conclusion' in report.lower()
    has_sufficient_length = word_count >= 1000
    has_citations = et_al_count > 0 or citation_brackets > 3
    has_structure = total_headers >= 3
    
    quality_score = sum([
        has_introduction,
        has_conclusion,
        has_sufficient_length,
        has_citations,
        has_structure
    ]) / 5.0
    
    return {
        "word_count": word_count,
        "char_count": char_count,
        "citation_brackets": citation_brackets,
        "et_al_citations": et_al_count,
        "year_mentions": year_pattern_count,
        "h1_headers": h1_headers,
        "h2_headers": h2_headers,
        "h3_headers": h3_headers,
        "total_headers": total_headers,
        "has_introduction": has_introduction,
        "has_conclusion": has_conclusion,
        "has_sufficient_length": has_sufficient_length,
        "has_citations": has_citations,
        "has_structure": has_structure,
        "quality_score": quality_score
    }


def manus_wrapper(output_format: str):
    """Create a Manus execution wrapper with specified output format."""
    def execute(question):
        # Suppress verbose output during Manus execution
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
            result = manus.execute(question, output_format=output_format)
        return result
    return execute


def process_reportbench_entry(entry: Dict, execute_fn, workspace_base: Path, entry_num: int, total_entries: int) -> Dict:
    """Process a single ReportBench entry with clean output."""
    arxiv_id = entry["arxiv_id"]
    prompt = entry["prompt"]
    title = entry.get('title', 'N/A')
    
    # Truncate long titles
    if len(title) > 70:
        title = title[:67] + "..."
    
    print(f"\n{'─'*80}")
    print(f"[{entry_num}/{total_entries}] Processing: {arxiv_id}")
    print(f"    Title: {title}")
    print(f"    Status: Generating report... ⏳", flush=True)
    
    # Create workspace for this entry
    entry_workspace = workspace_base / arxiv_id
    entry_workspace.mkdir(parents=True, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = entry_workspace.as_posix()
    os.environ['RESULTS_PATH'] = entry_workspace.as_posix()
    
    start_time = datetime.datetime.now()
    
    try:
        # Execute Manus (with output suppressed)
        report = execute_fn(prompt)
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Evaluate report quality
        eval_metrics = evaluate_report_quality(report, entry)
        
        # Save report
        report_file = entry_workspace / f"{arxiv_id}_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# Report for: {entry.get('title', 'N/A')}\n\n")
            f.write(f"**ArXiv ID:** {arxiv_id}\n\n")
            f.write(f"**Original Prompt:** {prompt}\n\n")
            f.write("---\n\n")
            f.write(report)
        
        result = {
            "arxiv_id": arxiv_id,
            "title": entry.get("title", "N/A"),
            "prompt": prompt,
            "report": report,
            "duration_seconds": duration,
            "success": True,
            "error": None,
            **eval_metrics
        }
        
        # Format duration
        if duration < 60:
            dur_str = f"{duration:.0f}s"
        elif duration < 3600:
            dur_str = f"{int(duration/60)}m {int(duration%60)}s"
        else:
            dur_str = f"{int(duration/3600)}h {int((duration%3600)/60)}m"
        
        print(f"    ✅ Completed in {dur_str}")
        print(f"    • Words: {eval_metrics['word_count']:,} | Citations: {eval_metrics['et_al_citations']} | Quality: {eval_metrics['quality_score']*100:.0f}%")
        
    except Exception as e:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        error_msg = str(e)
        print(f"    ❌ Failed: {error_msg}")
        
        result = {
            "arxiv_id": arxiv_id,
            "title": entry.get("title", "N/A"),
            "prompt": prompt,
            "report": None,
            "duration_seconds": duration,
            "success": False,
            "error": error_msg,
            "quality_score": 0.0
        }
    
    return result


def save_results(results: List[Dict], results_path: Path):
    """Save evaluation results to JSON file."""
    successful = [r for r in results if r["success"]]
    
    if successful:
        avg_quality = sum(r["quality_score"] for r in successful) / len(successful)
        avg_word_count = sum(r["word_count"] for r in successful) / len(successful)
        avg_citations = sum(r["et_al_citations"] for r in successful) / len(successful)
        avg_duration = sum(r["duration_seconds"] for r in results) / len(results)
    else:
        avg_quality = avg_word_count = avg_citations = avg_duration = 0
    
    summary = {
        "eval": {
            "model": os.environ.get("MODEL_NAME", "unknown"),
            "dataset": "ReportBench_v1.1",
            "total_entries": len(results),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "success_rate": len(successful) / len(results) if results else 0,
            "avg_quality_score": avg_quality,
            "avg_word_count": avg_word_count,
            "avg_citations": avg_citations,
            "avg_duration_seconds": avg_duration,
            "date": datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
        },
        "detail": results
    }
    
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Evaluate Manus on ReportBench dataset (quiet mode)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries to process")
    parser.add_argument("--start-idx", type=int, default=0, help="Starting index in dataset")
    args = parser.parse_args()
    
    print("\n" + "═"*80)
    print(" "*20 + "ReportBench Evaluation - Dashboard View")
    print("═"*80)
    
    # Initialize Langfuse quietly
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        initialize_langfuse()
    atexit.register(shutdown_langfuse)
    
    # Setup directories
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.mkdir(parents=True, exist_ok=True)
    
    # Load dataset
    print(f"\nDataset: ReportBench_v1.1")
    entries = load_reportbench_dataset(
        REPORTBENCH_DATASET_PATH, 
        limit=args.limit, 
        start_idx=args.start_idx
    )
    
    if not entries:
        print("❌ No entries to process!")
        return
    
    print(f"Entries to process: {len(entries)}")
    print(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Workspace: {WORKSPACE_PATH.name}")
    
    # Create Manus wrapper
    execute_fn = manus_wrapper(REPORT_OUTPUT_FORMAT)
    
    # Process entries
    results = []
    for i, entry in enumerate(entries):
        result = process_reportbench_entry(entry, execute_fn, WORKSPACE_PATH, i+1, len(entries))
        results.append(result)
        
        # Save incremental results
        interim_results_path = RESULTS_PATH / f"reportbench_interim_{TIMESTAMP}.json"
        save_results(results, interim_results_path)
    
    # Save final results
    final_results_path = RESULTS_PATH / f"reportbench_final_{TIMESTAMP}.json"
    save_results(results, final_results_path)
    
    # Print final summary
    successful = [r for r in results if r["success"]]
    avg_quality = sum(r["quality_score"] for r in successful) / len(successful) if successful else 0
    avg_word_count = sum(r["word_count"] for r in successful) / len(successful) if successful else 0
    avg_citations = sum(r["et_al_citations"] for r in successful) / len(successful) if successful else 0
    total_duration = sum(r["duration_seconds"] for r in results)
    
    if total_duration < 60:
        dur_str = f"{total_duration:.0f}s"
    elif total_duration < 3600:
        dur_str = f"{int(total_duration/60)}m {int(total_duration%60)}s"
    else:
        dur_str = f"{int(total_duration/3600)}h {int((total_duration%3600)/60)}m"
    
    print("\n" + "═"*80)
    print(" "*30 + "FINAL SUMMARY")
    print("═"*80)
    print(f"\nTotal Entries:       {len(results)}")
    print(f"Successful:          {len(successful)} ({len(successful)/len(results)*100:.0f}%)")
    print(f"Failed:              {len(results) - len(successful)}")
    print(f"\nTotal Duration:      {dur_str}")
    print(f"Avg Word Count:      {avg_word_count:,.0f}")
    print(f"Avg Citations:       {avg_citations:.0f}")
    print(f"Avg Quality Score:   {avg_quality*100:.0f}%")
    print(f"\nResults saved to: {final_results_path}")
    print("═"*80 + "\n")


if __name__ == '__main__':
    main()
