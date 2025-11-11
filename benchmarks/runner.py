#!/usr/bin/env python3
"""
Simple benchmark runner for Co-Sight
Reads prompts from CSV and outputs results in benchmark-specific formats
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import CoSight
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Initialize LangFuse Observability (must be done before importing CoSight)
from app.common.logger_util import logger
logger.info("\n=== LangFuse Observability Setup ===")
from app.cosight.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
initialize_langfuse()
logger.info("=== LangFuse Setup Complete ===\n")

from CoSight import CoSight
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision
from formatters.deepresearch_formatter import format_deepresearch_output


def load_prompts_from_csv(csv_path):
    """Load prompts from CSV file

    Expected CSV format:
    task_id,question,attachments (optional)
    """
    prompts = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prompts.append({
                'task_id': row['task_id'],
                'question': row['question'],
                'attachments': row.get('attachments', '').split(';') if row.get('attachments') else []
            })
    return prompts


def save_result(result, output_file):
    """Save a single result to JSONL file"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')


def run_benchmark(input_csv, output_file, start_idx=0, end_idx=None, resume=False):
    """Run benchmark on prompts from CSV

    Args:
        input_csv: Path to CSV file with prompts
        output_file: Path to output JSONL file
        start_idx: Start index (inclusive)
        end_idx: End index (exclusive), None for all
        resume: If True, skip already processed task_ids
    """
    # Load prompts
    prompts = load_prompts_from_csv(input_csv)
    prompts = prompts[start_idx:end_idx]

    # Check which tasks are already done (if resuming)
    completed_ids = set()
    if resume and os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    result = json.loads(line)
                    completed_ids.add(result['id'])
        logger.info(f"Resuming: {len(completed_ids)} tasks already completed")

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    # Process each prompt
    total = len(prompts)
    for idx, prompt in enumerate(prompts):
        task_id = prompt['task_id']

        # Skip if already processed
        if task_id in completed_ids:
            logger.info(f"[{idx+1}/{total}] Skipping {task_id} (already completed)")
            continue

        logger.info(f"\n{'='*80}")
        logger.info(f"[{idx+1}/{total}] Processing task: {task_id}")
        logger.info(f"Question: {prompt['question'][:100]}...")
        logger.info(f"{'='*80}\n")

        try:
            # Create workspace for this task
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            work_space_path = os.path.join(
                os.path.dirname(__file__),
                'work_space',
                f'task_{task_id}_{timestamp}'
            )
            os.makedirs(work_space_path, exist_ok=True)

            # Initialize CoSight
            cosight = CoSight(
                llm_for_plan,
                llm_for_act,
                llm_for_tool,
                llm_for_vision,
                work_space_path=work_space_path,
                message_uuid=task_id
            )

            # Run CoSight
            logger.info(f"Starting CoSight execution for {task_id}...")
            result = cosight.execute(prompt['question'])
            logger.info(f"CoSight execution completed for {task_id}")

            # Format output for DeepResearch Bench
            formatted_result = format_deepresearch_output(
                task_id=task_id,
                question=prompt['question'],
                cosight_result=result
            )

            # Save result incrementally
            save_result(formatted_result, output_file)
            logger.info(f"✓ Result saved for {task_id}")

        except Exception as e:
            logger.error(f"✗ Error processing {task_id}: {str(e)}", exc_info=True)
            # Save error result
            error_result = {
                'id': task_id,
                'prompt': prompt['question'],
                'article': f"[ERROR] Task failed: {str(e)}"
            }
            save_result(error_result, output_file)

    logger.info(f"\n{'='*80}")
    logger.info(f"Benchmark completed! Results saved to: {output_file}")
    logger.info(f"{'='*80}\n")

    # Flush LangFuse traces before exit
    shutdown_langfuse()


def main():
    parser = argparse.ArgumentParser(
        description='Run Co-Sight benchmark from CSV prompts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Run all prompts from CSV
  python runner.py --input prompts.csv --output results.jsonl

  # Run specific range
  python runner.py --input prompts.csv --output results.jsonl --start 0 --end 10

  # Resume from checkpoint
  python runner.py --input prompts.csv --output results.jsonl --resume
        """
    )

    parser.add_argument(
        '--input',
        required=True,
        help='Input CSV file with prompts (columns: task_id, question, attachments)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output JSONL file for results'
    )
    parser.add_argument(
        '--start',
        type=int,
        default=0,
        help='Start index (default: 0)'
    )
    parser.add_argument(
        '--end',
        type=int,
        default=None,
        help='End index (default: None, process all)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoint, skip already processed tasks'
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    run_benchmark(
        input_csv=args.input,
        output_file=args.output,
        start_idx=args.start,
        end_idx=args.end,
        resume=args.resume
    )


if __name__ == '__main__':
    main()
