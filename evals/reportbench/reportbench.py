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

import datetime
import os
import traceback
from pathlib import Path
from typing import Any, Callable, List, Optional

from .dataset import reportbench_dataset
from .scorer import evaluate_report_quality


def reportbench(
    process_message: Callable,
    limit: Optional[int] = None,
    start_idx: int = 0,
    task_id: Optional[List[str]] = None,
    postcall: Optional[Callable] = None
) -> List[dict]:
    """
    Run ReportBench evaluation.
    
    Args:
        process_message: Function to process each task (takes prompt, output_format, returns report)
        limit: Maximum number of tasks to process
        start_idx: Starting index in dataset
        task_id: List of specific arxiv_ids to evaluate
        postcall: Optional callback function called after each task
        
    Returns:
        List of evaluation results
    """
    # Load dataset
    dataset = reportbench_dataset(
        limit=limit,
        start_idx=start_idx,
        task_id=task_id
    )
    
    results = []
    work_space_location = Path(os.environ['WORKSPACE_PATH'])
    
    for i, data in enumerate(dataset):
        arxiv_id = data['task_id']
        prompt = data['prompt']
        output_format = data['output_format']
        
        # Create task-specific workspace
        task_work_space = work_space_location / arxiv_id
        os.makedirs(task_work_space, exist_ok=True)
        os.environ['WORKSPACE_PATH'] = task_work_space.as_posix()
        
        timestr = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        start_time = datetime.datetime.today()
        print(f'\n{timestr} Starting task {i+1}/{len(dataset)}: {arxiv_id}')
        print(f'Title: {data["title"]}')
        
        report = None
        error_result = None
        
        try:
            # Execute the task
            report = process_message(prompt, output_format)
            print(f'Report generated successfully')
        except Exception as e:
            error_result = f'Process question failed: {e}'
            print(f'Error: {error_result}')
            print(traceback.format_exc())
        
        end_time = datetime.datetime.today()
        time_diff = end_time - start_time
        timestr = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        print(f'{timestr} Completed task {arxiv_id}, Duration: {time_diff}')
        
        # Evaluate report quality
        if report:
            eval_metrics = evaluate_report_quality(report)
            
            # Save report to file
            report_file = task_work_space / f"{arxiv_id}_report.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"# Report for: {data['title']}\n\n")
                f.write(f"**ArXiv ID:** {arxiv_id}\n\n")
                f.write(f"**Original Prompt:** {prompt}\n\n")
                f.write("---\n\n")
                f.write(report)
            print(f'Report saved to: {report_file}')
        else:
            eval_metrics = {
                "quality_score": 0.0,
                "word_count": 0,
                "et_al_citations": 0
            }
        
        result = {
            "task_id": arxiv_id,
            "arxiv_id": arxiv_id,
            "title": data["title"],
            "prompt": prompt,
            "report": report if report else "",
            "model_answer": report if report else "",  # For compatibility
            "duration_seconds": time_diff.total_seconds(),
            "success": report is not None,
            "error": error_result,
            "score": eval_metrics["quality_score"],  # For compatibility with save_results
            **eval_metrics
        }
        
        results.append(result)
        
        # Call postcall if provided
        if postcall:
            try:
                postcall(results, task_work_space / f'interim_results.json')
            except Exception as e:
                print(f'Postcall error: {e}')
    
    return results
