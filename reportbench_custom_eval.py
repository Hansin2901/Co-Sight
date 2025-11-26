#!/usr/bin/env python3
"""
ReportBench Custom Evaluation Pipeline
=======================================

This script provides a complete pipeline to:
1. Load custom research tasks from JSON
2. Generate survey reports using Manus
3. Evaluate them with ReportBench metrics

Usage:
    python reportbench_custom_eval.py --tasks tasks.json [--eval-only]
"""

import argparse
import atexit
import datetime
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.manus.manus import Manus
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision

# Paths
TIMESTAMP = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
WORKSPACE_PATH = Path(__file__).parent / "workspace" / f"reportbench_custom_{TIMESTAMP}"
EVAL_INPUT_PATH = WORKSPACE_PATH / "eval_input"
EVAL_RESULTS_PATH = WORKSPACE_PATH / "eval_results"
REPORTBENCH_DIR = Path(__file__).parent.parent / "ReportBench"

# Report output format
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
2. **Length**: Target 2500-4000 words for comprehensive coverage
3. **Structure**: Use clear markdown headers (##, ###) for organization
4. **Synthesis**: Don't just list papers - synthesize and compare approaches
5. **Technical depth**: Include technical details appropriate for academic audience
6. **Multiple sources**: Draw information from multiple papers, comparing and contrasting

Remember: You have access to paper titles, authors, publication dates, and summaries from your research steps. 
Use this information to create properly formatted citations throughout the report.
"""


def load_tasks(tasks_file: Path) -> List[Dict]:
    """Load tasks from JSON file.
    
    Args:
        tasks_file: Path to tasks JSON file
        
    Returns:
        List of task dictionaries
    """
    if not tasks_file.exists():
        raise FileNotFoundError(f"Tasks file not found: {tasks_file}")
    
    with open(tasks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = data.get('tasks', [])
    print(f"✓ Loaded {len(tasks)} tasks from {tasks_file}")
    return tasks


def generate_report_with_manus(task: Dict, workspace: Path) -> Dict:
    """Generate a survey report using Manus agent.
    
    Args:
        task: Task dictionary with 'id', 'query', and optional 'constraints'
        workspace: Workspace directory for this task
        
    Returns:
        Result dictionary with report and metadata
    """
    task_id = task['id']
    query = task['query']
    constraints = task.get('constraints', '')
    
    # Construct full prompt
    full_query = query
    if constraints:
        full_query += f"\n\nAdditional constraints:\n{constraints}"
    
    print(f"\n{'='*100}")
    print(f"Task ID: {task_id}")
    print(f"Query: {query[:150]}...")
    if constraints:
        print(f"Constraints: {constraints[:100]}...")
    print(f"{'='*100}\n")
    
    # Setup workspace
    task_workspace = workspace / task_id
    task_workspace.mkdir(parents=True, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = task_workspace.as_posix()
    os.environ['RESULTS_PATH'] = task_workspace.as_posix()
    
    start_time = datetime.datetime.now()
    
    try:
        # Execute Manus
        print("→ Starting Manus agent...")
        manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
        report = manus.execute(full_query, output_format=REPORT_OUTPUT_FORMAT)
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Save report
        report_file = task_workspace / f"{task_id}_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# Survey Report: {task_id}\n\n")
            f.write(f"**Query:** {query}\n\n")
            if constraints:
                f.write(f"**Constraints:** {constraints}\n\n")
            f.write("---\n\n")
            f.write(report)
        
        # Basic metrics
        word_count = len(report.split())
        citation_count = report.count('et al.')
        
        print(f"✓ Report generated: {word_count} words, {citation_count} citations, {duration:.1f}s")
        
        return {
            "task_id": task_id,
            "query": query,
            "constraints": constraints,
            "report": report,
            "report_file": str(report_file),
            "duration_seconds": duration,
            "word_count": word_count,
            "citation_count": citation_count,
            "success": True,
            "error": None
        }
        
    except Exception as e:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        error_msg = str(e)
        print(f"✗ Error generating report: {error_msg}")
        print(traceback.format_exc())
        
        return {
            "task_id": task_id,
            "query": query,
            "constraints": constraints,
            "report": None,
            "report_file": None,
            "duration_seconds": duration,
            "word_count": 0,
            "citation_count": 0,
            "success": False,
            "error": error_msg
        }


def prepare_for_evaluation(results: List[Dict], eval_input_path: Path):
    """Prepare generated reports for ReportBench evaluation.
    
    Args:
        results: List of result dictionaries from Manus
        eval_input_path: Directory to save evaluation input files
    """
    eval_input_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*100}")
    print("Preparing reports for ReportBench evaluation...")
    print(f"{'='*100}\n")
    
    prepared_count = 0
    for result in results:
        if not result['success']:
            print(f"✗ Skipping {result['task_id']} (generation failed)")
            continue
        
        task_id = result['task_id']
        report = result['report']
        
        # Create ReportBench-compatible JSON
        eval_data = {
            "arxiv_id": task_id,  # Use task_id as arxiv_id
            "query": result['query'],
            "constraints": result.get('constraints', ''),
            "response": report,
            "metadata": {
                "word_count": result['word_count'],
                "citation_count": result['citation_count'],
                "duration_seconds": result['duration_seconds']
            }
        }
        
        # Save to eval input directory
        eval_file = eval_input_path / f"{task_id}.json"
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(eval_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Prepared {task_id} → {eval_file.name}")
        prepared_count += 1
    
    print(f"\n✓ Prepared {prepared_count}/{len(results)} reports for evaluation")
    return prepared_count


def run_reportbench_evaluation(eval_input_path: Path, eval_results_path: Path):
    """Run ReportBench statement evaluator on generated reports.
    
    Args:
        eval_input_path: Directory with report JSON files
        eval_results_path: Directory to save evaluation results
    """
    print(f"\n{'='*100}")
    print("Running ReportBench Evaluation...")
    print(f"{'='*100}\n")
    
    eval_results_path.mkdir(parents=True, exist_ok=True)
    
    # Check if ReportBench directory exists
    if not REPORTBENCH_DIR.exists():
        print(f"✗ ReportBench directory not found: {REPORTBENCH_DIR}")
        print("  Please ensure ReportBench is cloned at: ../ReportBench/")
        return False
    
    # Run statement_evaluator.py
    cmd = [
        sys.executable,
        str(REPORTBENCH_DIR / "statement_evaluator.py"),
        str(eval_input_path),
        "--output-dir", str(eval_results_path)
    ]
    
    print(f"→ Running: {' '.join(cmd)}\n")
    
    try:
        # Activate venv and run
        venv_python = Path(__file__).parent / ".venv" / "bin" / "python"
        if venv_python.exists():
            cmd[0] = str(venv_python)
        
        result = subprocess.run(
            cmd,
            cwd=str(REPORTBENCH_DIR),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"\n✓ ReportBench evaluation completed successfully")
            print(f"  Results saved to: {eval_results_path}")
            return True
        else:
            print(f"\n✗ ReportBench evaluation failed with code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("\n✗ ReportBench evaluation timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"\n✗ Error running ReportBench evaluation: {e}")
        print(traceback.format_exc())
        return False


def summarize_results(eval_results_path: Path, generation_results: List[Dict]):
    """Summarize evaluation results.
    
    Args:
        eval_results_path: Path to evaluation results
        generation_results: List of generation result dictionaries
    """
    print(f"\n{'='*100}")
    print("EVALUATION SUMMARY")
    print(f"{'='*100}\n")
    
    # Generation summary
    successful = [r for r in generation_results if r['success']]
    print(f"Generation Results:")
    print(f"  Total tasks: {len(generation_results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(generation_results) - len(successful)}")
    
    if successful:
        avg_words = sum(r['word_count'] for r in successful) / len(successful)
        avg_citations = sum(r['citation_count'] for r in successful) / len(successful)
        avg_duration = sum(r['duration_seconds'] for r in successful) / len(successful)
        
        print(f"\n  Averages:")
        print(f"    Words: {avg_words:.0f}")
        print(f"    Citations: {avg_citations:.1f}")
        print(f"    Duration: {avg_duration:.1f}s")
    
    # Check for evaluation results
    print(f"\nEvaluation Results:")
    eval_dirs = list(eval_results_path.glob("*"))
    if eval_dirs:
        print(f"  Result directories: {len(eval_dirs)}")
        for eval_dir in eval_dirs:
            citations_file = eval_dir / "citations.csv"
            if citations_file.exists():
                with open(citations_file, 'r') as f:
                    citation_count = sum(1 for line in f) - 1  # Exclude header
                print(f"    {eval_dir.name}: {citation_count} citations extracted")
    else:
        print(f"  No evaluation results found in {eval_results_path}")
    
    print(f"\n{'='*100}\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="ReportBench Custom Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--tasks", 
        type=Path, 
        required=True,
        help="Path to tasks JSON file"
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Skip generation, only run evaluation on existing reports"
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Only generate reports, skip ReportBench evaluation"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*100)
    print("ReportBench Custom Evaluation Pipeline")
    print("="*100 + "\n")
    
    # Setup directories
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
    
    # Initialize Langfuse
    if not args.eval_only:
        print("Initializing Langfuse...")
        initialize_langfuse()
        atexit.register(shutdown_langfuse)
        print("✓ Langfuse initialized\n")
    
    generation_results = []
    
    # Step 1: Generate reports (unless eval-only)
    if not args.eval_only:
        print("STEP 1: Generate Reports with Manus")
        print("="*100 + "\n")
        
        # Load tasks
        tasks = load_tasks(args.tasks)
        
        # Generate reports
        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}] Processing task: {task['id']}")
            result = generate_report_with_manus(task, WORKSPACE_PATH)
            generation_results.append(result)
        
        # Save generation results
        gen_results_file = WORKSPACE_PATH / "generation_results.json"
        with open(gen_results_file, 'w', encoding='utf-8') as f:
            json.dump(generation_results, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Generation results saved: {gen_results_file}")
    
    else:
        # Load existing generation results
        gen_results_file = WORKSPACE_PATH / "generation_results.json"
        if gen_results_file.exists():
            with open(gen_results_file, 'r', encoding='utf-8') as f:
                generation_results = json.load(f)
            print(f"✓ Loaded existing generation results: {gen_results_file}")
        else:
            print(f"✗ No generation results found at: {gen_results_file}")
            return 1
    
    # Step 2: Prepare for evaluation
    if not args.skip_eval:
        print(f"\n\nSTEP 2: Prepare for Evaluation")
        print("="*100)
        prepared = prepare_for_evaluation(generation_results, EVAL_INPUT_PATH)
        
        if prepared == 0:
            print("\n✗ No reports to evaluate!")
            return 1
        
        # Step 3: Run ReportBench evaluation
        print(f"\n\nSTEP 3: Run ReportBench Evaluation")
        print("="*100)
        success = run_reportbench_evaluation(EVAL_INPUT_PATH, EVAL_RESULTS_PATH)
        
        if not success:
            print("\n⚠ ReportBench evaluation encountered issues")
    
    # Step 4: Summarize
    summarize_results(EVAL_RESULTS_PATH, generation_results)
    
    print(f"✓ Complete! Results in: {WORKSPACE_PATH}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
