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

import atexit
import datetime
import json
import os
import traceback
from pathlib import Path

from app.manus.manus import Manus
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
from evals.reportbench import reportbench
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision

reportbench_timestamp = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
WORKSPACE_PATH = (
        Path(__file__).parent / "workspace" / f"reportbench_{reportbench_timestamp}"
)

LOG_PATH = (
        Path(__file__).parent / "logs"
)

RESULTS_PATH = (
        Path(__file__).parent / "results" / "ReportBench"
)


def manus_executor():
    """Create Manus executor function."""
    def execute(question, output_format=""):
        manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
        result = manus.execute(question, output_format=output_format)
        print(f"Final result length: {len(result) if result else 0} characters")
        return result

    return execute


def save_results(results: list, results_path: str):
    """Save evaluation results to JSON file."""
    try:
        successful = [r for r in results if r["success"]]
        
        if successful:
            avg_quality = sum(r["quality_score"] for r in successful) / len(successful)
            avg_word_count = sum(r["word_count"] for r in successful) / len(successful)
            avg_citations = sum(r["et_al_citations"] for r in successful) / len(successful)
            avg_duration = sum(r["duration_seconds"] for r in results) / len(results)
        else:
            avg_quality = avg_word_count = avg_citations = avg_duration = 0

        data = {
            "eval": {
                "model": os.environ.get("MODEL_NAME"),
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
        
        with open(results_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        print(f"✅ Results saved to {results_path}")
    except Exception as e:
        print(f"❌ Error saving results to {results_path}: {e}")
        print(traceback.format_exc())


if __name__ == '__main__':
    # Initialize Langfuse observability
    print("\n=== Langfuse Observability Setup ===")
    initialize_langfuse()
    print("=== Langfuse Setup Complete ===\n")

    # Register shutdown handler to flush traces
    atexit.register(shutdown_langfuse)

    # Setup directories
    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)
    os.makedirs(RESULTS_PATH, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = WORKSPACE_PATH.as_posix()
    os.environ['RESULTS_PATH'] = WORKSPACE_PATH.as_posix()

    # Create executor
    execute_fn = manus_executor()

    print("\n" + "="*80)
    print("                    ReportBench Evaluation with Co-Sight")
    print("="*80)
    print(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Workspace: {WORKSPACE_PATH}")
    print(f"Results: {RESULTS_PATH}")
    print("="*80 + "\n")

    # Run evaluation on specific tasks (or all tasks)
    # To run on all tasks, remove the task_id parameter
    # To limit number of tasks, add limit parameter: limit=5
    results = reportbench(
        process_message=execute_fn,
        task_id=[
            "2312.04861",  # Radar data representation in autonomous driving
            # Add more arxiv_ids here or remove task_id to run all
        ],
        postcall=save_results
    )

    # Save final results
    datestr = datetime.datetime.today().strftime('%Y%m%d%H%M%S')
    final_results_path = RESULTS_PATH / f'reportbench_final_{datestr}.json'
    save_results(results, final_results_path.as_posix())

    # Print summary
    successful = [r for r in results if r["success"]]
    print("\n" + "="*80)
    print("                           FINAL SUMMARY")
    print("="*80)
    print(f"Total Tasks:        {len(results)}")
    print(f"Successful:         {len(successful)} ({len(successful)/len(results)*100:.0f}%)")
    print(f"Failed:             {len(results) - len(successful)}")
    
    if successful:
        avg_quality = sum(r["quality_score"] for r in successful) / len(successful)
        avg_word_count = sum(r["word_count"] for r in successful) / len(successful)
        avg_citations = sum(r["et_al_citations"] for r in successful) / len(successful)
        print(f"Avg Quality Score:  {avg_quality*100:.0f}%")
        print(f"Avg Word Count:     {avg_word_count:,.0f}")
        print(f"Avg Citations:      {avg_citations:.0f}")
    
    print("="*80 + "\n")
