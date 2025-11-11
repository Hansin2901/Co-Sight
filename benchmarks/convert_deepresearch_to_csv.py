#!/usr/bin/env python3
"""
Convert DeepResearch Bench query.jsonl to CSV format for the runner

Usage:
    python convert_deepresearch_to_csv.py
    python convert_deepresearch_to_csv.py --language en
    python convert_deepresearch_to_csv.py --start 0 --end 10
"""

import json
import csv
import argparse


def convert_jsonl_to_csv(input_jsonl, output_csv, language=None, start=0, end=None):
    """Convert DeepResearch query.jsonl to CSV format

    Args:
        input_jsonl: Path to query.jsonl file
        output_csv: Output CSV path
        language: Filter by language ('en', 'zh', or None for all)
        start: Start index
        end: End index (None for all)
    """
    tasks = []

    # Read JSONL
    with open(input_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                task = json.loads(line)

                # Filter by language if specified
                if language and task.get('language') != language:
                    continue

                tasks.append({
                    'task_id': f"dr_{task['id']:03d}",
                    'question': task['prompt'],
                    'attachments': '',  # DeepResearch doesn't have attachments
                    'topic': task.get('topic', ''),
                    'language': task.get('language', '')
                })

    # Apply start/end slicing
    tasks = tasks[start:end]

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['task_id', 'question', 'attachments']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for task in tasks:
            writer.writerow({
                'task_id': task['task_id'],
                'question': task['question'],
                'attachments': task['attachments']
            })

    print(f"✓ Converted {len(tasks)} tasks to {output_csv}")
    print(f"  Language filter: {language or 'all'}")
    print(f"  Range: {start} to {end or 'end'}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert DeepResearch Bench query.jsonl to CSV format'
    )

    parser.add_argument(
        '--input',
        default='eval_scripts/data/prompt_data/query.jsonl',
        help='Input JSONL file (default: eval_scripts/data/prompt_data/query.jsonl)'
    )
    parser.add_argument(
        '--output',
        default='data/deepresearch_prompts.csv',
        help='Output CSV file (default: data/deepresearch_prompts.csv)'
    )
    parser.add_argument(
        '--language',
        choices=['en', 'zh'],
        default=None,
        help='Filter by language (en/zh, default: all)'
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
        help='End index (default: None, all remaining)'
    )

    args = parser.parse_args()

    convert_jsonl_to_csv(
        args.input,
        args.output,
        language=args.language,
        start=args.start,
        end=args.end
    )


if __name__ == '__main__':
    main()
