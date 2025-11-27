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
from app.manus.utils.citation_matcher import inject_citation_urls, format_citation_report
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

COSIGHT_OUTPUTS_PATH = (
        Path(__file__).parent / "Co-Sight-outputs"
)


def manus_executor():
    """Create Manus executor function with citation URL injection."""
    def execute(question, output_format=""):
        manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
        result = manus.execute(question, output_format=output_format)
        print(f"Final result length: {len(result) if result else 0} characters")
        
        # Post-process: Inject URLs into citations
        if result:
            search_results = manus.get_search_results()
            print(f"\n[Citation Injection] Found {len(search_results)} search results for URL matching")
            
            if search_results:
                try:
                    enhanced_report, citation_metadata = inject_citation_urls(
                        report_text=result,
                        search_results=search_results,
                        confidence_threshold=0.5  # Lower threshold for better recall
                    )
                    
                    # Log citation matching statistics
                    print(f"[Citation Injection] Results:")
                    print(f"  - Total citations found: {citation_metadata.get('total_citations', 0)}")
                    print(f"  - Successfully matched: {citation_metadata.get('matched_count', 0)}")
                    print(f"  - Unmatched: {citation_metadata.get('unmatched_count', 0)}")
                    print(f"  - Match rate: {citation_metadata.get('match_rate', 0):.1%}")
                    
                    # Store citation metadata for later analysis
                    # This will be available if we need to add it to the output
                    execute.last_citation_metadata = citation_metadata
                    
                    # Print detailed report if there were matches
                    if citation_metadata.get('matched_count', 0) > 0:
                        print(format_citation_report(citation_metadata))
                    
                    result = enhanced_report
                    print(f"[Citation Injection] Enhanced report length: {len(result)} characters")
                except Exception as e:
                    print(f"[Citation Injection] Error during URL injection: {e}")
                    traceback.print_exc()
            else:
                print("[Citation Injection] No search results available - skipping URL injection")
        
        return result

    # Initialize metadata storage
    execute.last_citation_metadata = None
    return execute


def save_to_cosight_outputs(results: list):
    """Save results to Co-Sight-outputs directory for ReportBench evaluation."""
    os.makedirs(COSIGHT_OUTPUTS_PATH, exist_ok=True)
    
    for result in results:
        if not result.get("success") or not result.get("report"):
            continue
            
        arxiv_id = result.get("arxiv_id", "unknown")
        output_file = COSIGHT_OUTPUTS_PATH / f"{arxiv_id}.json"
        
        output_data = {
            "response": result["report"],
            "arxiv_id": arxiv_id,
            "query": result.get("prompt", ""),
            "references": []
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved to Co-Sight-outputs: {output_file}")
        except Exception as e:
            print(f"❌ Error saving to Co-Sight-outputs: {e}")


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

        # Calculate citation URL injection statistics
        with_citation_metadata = [r for r in successful if r.get("citation_metadata")]
        if with_citation_metadata:
            avg_citation_match_rate = sum(
                r["citation_metadata"].get("match_rate", 0) for r in with_citation_metadata
            ) / len(with_citation_metadata)
            avg_matched_citations = sum(
                r["citation_metadata"].get("matched_count", 0) for r in with_citation_metadata
            ) / len(with_citation_metadata)
            avg_search_results = sum(
                r["citation_metadata"].get("search_results_count", 0) for r in with_citation_metadata
            ) / len(with_citation_metadata)
        else:
            avg_citation_match_rate = avg_matched_citations = avg_search_results = 0

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
                # Citation URL injection stats
                "citation_injection_stats": {
                    "tasks_with_citation_data": len(with_citation_metadata),
                    "avg_citation_match_rate": avg_citation_match_rate,
                    "avg_matched_citations_per_report": avg_matched_citations,
                    "avg_search_results_per_report": avg_search_results,
                }
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
            "2206.05498",
            "2207.14394"  # Radar data representation in autonomous driving
            # Add more arxiv_ids here or remove task_id to run all
        ],
        postcall=save_results
    )

    # Save final results
    datestr = datetime.datetime.today().strftime('%Y%m%d%H%M%S')
    final_results_path = RESULTS_PATH / f'reportbench_final_{datestr}.json'
    save_results(results, final_results_path.as_posix())
    
    # Also save to Co-Sight-outputs for ReportBench evaluation
    save_to_cosight_outputs(results)

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
        
        # Citation URL injection stats
        with_citation_metadata = [r for r in successful if r.get("citation_metadata")]
        if with_citation_metadata:
            avg_match_rate = sum(
                r["citation_metadata"].get("match_rate", 0) for r in with_citation_metadata
            ) / len(with_citation_metadata)
            avg_matched = sum(
                r["citation_metadata"].get("matched_count", 0) for r in with_citation_metadata
            ) / len(with_citation_metadata)
            print(f"\n--- Citation URL Injection ---")
            print(f"Reports with URLs:  {len(with_citation_metadata)}")
            print(f"Avg Match Rate:     {avg_match_rate*100:.0f}%")
            print(f"Avg URLs Injected:  {avg_matched:.1f}")
    
    print("="*80 + "\n")
