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
ReportBench Evaluation Script for Manus Agent.

This script evaluates the Manus agent's ability to generate comprehensive academic 
survey reports with inline citations using the ReportBench dataset.

Usage:
    python cosight_evals_reportbench.py [--limit N] [--start-idx N]
"""

import atexit
import datetime
import json
import os
import traceback
import argparse
from pathlib import Path
from typing import List, Dict, Optional
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
    """Load ReportBench dataset from JSONL file.
    
    Args:
        dataset_path: Path to the ReportBench JSONL file
        limit: Maximum number of entries to load (None for all)
        start_idx: Starting index for loading entries
        
    Returns:
        List of dataset entries
    """
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
    
    print(f"Loaded {len(entries)} entries from ReportBench dataset")
    return entries


def evaluate_report_quality(report: str, metadata: Dict) -> Dict:
    """Evaluate the quality of a generated report.
    
    Args:
        report: The generated report text
        metadata: Original dataset entry metadata
        
    Returns:
        Dictionary with evaluation metrics
    """
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
    has_sufficient_length = word_count >= 1000  # Reduced threshold for initial tests
    has_citations = et_al_count > 0 or citation_brackets > 3
    has_structure = total_headers >= 3
    
    quality_score = sum([
        has_introduction,
        has_conclusion,
        has_sufficient_length,
        has_citations,
        has_structure
    ]) / 5.0  # Normalized to 0-1
    
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
    """Create a Manus execution wrapper with specified output format.
    
    Args:
        output_format: The output format instructions to use
        
    Returns:
        Execution function
    """
    def execute(question):
        manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
        result = manus.execute(question, output_format=output_format)
        print(f"Manus result length: {len(result)} chars, {len(result.split())} words")
        return result
    return execute


def process_reportbench_entry(entry: Dict, execute_fn, workspace_base: Path) -> Dict:
    """Process a single ReportBench entry.
    
    Args:
        entry: Dataset entry
        execute_fn: Manus execution function
        workspace_base: Base workspace directory
        
    Returns:
        Result dictionary with evaluation metrics
    """
    arxiv_id = entry["arxiv_id"]
    prompt = entry["prompt"]
    
    print("\n" + "="*100)
    print(f"Processing: {arxiv_id}")
    print(f"Title: {entry.get('title', 'N/A')}")
    print(f"Prompt: {prompt[:200]}...")
    print("="*100 + "\n")
    
    # Create workspace for this entry
    entry_workspace = workspace_base / arxiv_id
    entry_workspace.mkdir(parents=True, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = entry_workspace.as_posix()
    os.environ['RESULTS_PATH'] = entry_workspace.as_posix()
    
    start_time = datetime.datetime.now()
    
    try:
        # Execute Manus
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
        
        print(f"\n✅ Success! Duration: {duration:.2f}s, Words: {eval_metrics['word_count']}, Quality: {eval_metrics['quality_score']:.2%}")
        
    except Exception as e:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        print(traceback.format_exc())
        
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
    """Save evaluation results to JSON file.
    
    Args:
        results: List of result dictionaries
        results_path: Path to save results
    """
    try:
        # Calculate aggregate statistics
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
        
        print(f"\n✅ Results saved to: {results_path}")
        print(f"Summary: {len(successful)}/{len(results)} successful, Avg Quality: {avg_quality:.2%}")
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")
        print(traceback.format_exc())


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Evaluate Manus on ReportBench dataset")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries to process")
    parser.add_argument("--start-idx", type=int, default=0, help="Starting index in dataset")
    args = parser.parse_args()
    
    print("\n" + "="*100)
    print("ReportBench Evaluation for Manus Agent")
    print("="*100 + "\n")
    
    # Initialize Langfuse
    print("=== Initializing Langfuse ===")
    initialize_langfuse()
    print("=== Langfuse Setup Complete ===\n")
    atexit.register(shutdown_langfuse)
    
    # Setup directories
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.mkdir(parents=True, exist_ok=True)
    
    # Load dataset
    print(f"Loading ReportBench dataset from: {REPORTBENCH_DATASET_PATH}")
    entries = load_reportbench_dataset(
        REPORTBENCH_DATASET_PATH, 
        limit=args.limit, 
        start_idx=args.start_idx
    )
    
    if not entries:
        print("❌ No entries to process!")
        return
    
    print(f"\nProcessing {len(entries)} entries (starting from index {args.start_idx})")
    print(f"Workspace: {WORKSPACE_PATH}\n")
    
    # Create Manus wrapper
    execute_fn = manus_wrapper(REPORT_OUTPUT_FORMAT)
    
    # Process entries
    results = []
    for i, entry in enumerate(entries):
        print(f"\n{'='*100}")
        print(f"Entry {i+1}/{len(entries)} (Index {args.start_idx + i})")
        print(f"{'='*100}")
        
        result = process_reportbench_entry(entry, execute_fn, WORKSPACE_PATH)
        results.append(result)
        
        # Save incremental results
        interim_results_path = RESULTS_PATH / f"reportbench_interim_{TIMESTAMP}.json"
        save_results(results, interim_results_path)
    
    # Save final results
    final_results_path = RESULTS_PATH / f"reportbench_final_{TIMESTAMP}.json"
    save_results(results, final_results_path)
    
    print("\n" + "="*100)
    print("Evaluation Complete!")
    print("="*100)
    print(f"Final results: {final_results_path}")
    print(f"Workspace: {WORKSPACE_PATH}")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()
