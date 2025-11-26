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
Complete ReportBench Evaluation Pipeline
Runs Co-Sight report generation + ReportBench evaluation in one command.

Usage:
    python run_full_evaluation.py
    python run_full_evaluation.py --config my_config.json
    python run_full_evaluation.py --skip-generation  # Only run evaluation
    python run_full_evaluation.py --skip-evaluation  # Only generate reports
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_command(cmd: list, description: str) -> bool:
    """
    Run a command and return success status.
    
    Args:
        cmd: Command to run as list of strings
        description: Human-readable description of what's being run
    
    Returns:
        True if command succeeded, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*80}\n")
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=False  # Show output in real-time
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: Command failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a required file exists."""
    if not Path(file_path).exists():
        print(f"❌ Required file not found: {description}")
        print(f"   Path: {file_path}")
        return False
    return True


def display_results_summary(eval_dir: Path):
    """Display a summary of evaluation results if available."""
    print(f"\n{'='*80}")
    print(" " * 25 + "RESULTS SUMMARY")
    print(f"{'='*80}\n")
    
    # Check for aggregate metrics
    aggregate_file = eval_dir / "statement-results" / "aggregate_metrics.csv"
    summary_file = eval_dir / "statement-results" / "summary.csv"
    related_work_file = eval_dir / "related-work-results" / "evaluation_results.csv"
    
    if aggregate_file.exists():
        print("📊 Aggregate Metrics:")
        print(f"   File: {aggregate_file}")
        try:
            with open(aggregate_file, 'r', encoding='utf-8') as f:
                # Show first few lines
                lines = f.readlines()[:5]
                for line in lines:
                    print(f"   {line.rstrip()}")
        except Exception as e:
            print(f"   (Unable to read file: {e})")
    
    print(f"\n📁 Full results available in: {eval_dir.absolute()}")
    print("\nKey files:")
    if aggregate_file.exists():
        print(f"  • {aggregate_file.relative_to(eval_dir.parent)}")
    if summary_file.exists():
        print(f"  • {summary_file.relative_to(eval_dir.parent)}")
    if related_work_file.exists():
        print(f"  • {related_work_file.relative_to(eval_dir.parent)}")
    
    print(f"\n{'='*80}\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Complete ReportBench evaluation pipeline: Generate reports + Run evaluation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="reportbench_config.json",
        help="Path to configuration JSON file (default: reportbench_config.json)"
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip report generation, only run evaluation on existing outputs"
    )
    parser.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="Skip evaluation, only generate reports"
    )
    args = parser.parse_args()
    
    # Load configuration
    print(f"\n{'='*80}")
    print(" " * 20 + "ReportBench Full Evaluation Pipeline")
    print(f"{'='*80}")
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Config: {args.config}\n")
    
    config = load_config(args.config)
    
    # Get project root and script locations
    script_dir = Path(__file__).parent
    
    # Validate required scripts exist
    generation_script = script_dir / "run_cosight_reportbench.py"
    evaluation_script = script_dir / "evaluate_with_reportbench.sh"
    
    if not args.skip_generation:
        if not check_file_exists(str(generation_script), "Report generation script"):
            sys.exit(1)
    
    if not args.skip_evaluation:
        if not check_file_exists(str(evaluation_script), "Evaluation script"):
            sys.exit(1)
        
        # Check if evaluation script is executable
        if not evaluation_script.stat().st_mode & 0o111:
            print("⚠️  Making evaluation script executable...")
            evaluation_script.chmod(evaluation_script.stat().st_mode | 0o111)
    
    # Extract paths from config
    output_dir = Path(config['output_dir'])
    eval_dir = Path(config['evaluation_dir'])
    gt_dir = config['reportbench_gt_dir']
    
    success = True
    
    # ===========================================================================
    # Step 1: Generate Reports
    # ===========================================================================
    if not args.skip_generation:
        print("\n" + "="*80)
        print("PHASE 1: Report Generation")
        print("="*80)
        
        generation_cmd = [
            sys.executable,  # Use same Python interpreter
            str(generation_script),
            "--config", args.config
        ]
        
        if not run_command(generation_cmd, "Co-Sight Report Generation"):
            print("\n❌ Report generation failed!")
            success = False
            if not args.skip_evaluation:
                print("⚠️  Evaluation will be skipped due to generation failure.")
                args.skip_evaluation = True
        else:
            print("\n✅ Report generation completed successfully")
            
            # Show count of generated reports
            if output_dir.exists():
                json_files = list(output_dir.glob("*.json"))
                # Exclude summary files
                report_files = [f for f in json_files if not f.name.endswith("_summary.json")]
                print(f"   Generated {len(report_files)} report(s)")
    else:
        print("\n⏭️  Skipping report generation (--skip-generation flag set)")
        
        # Verify outputs exist
        if not output_dir.exists():
            print(f"❌ Output directory not found: {output_dir}")
            print("   Cannot run evaluation without generated reports.")
            sys.exit(1)
        
        json_files = list(output_dir.glob("*.json"))
        report_files = [f for f in json_files if not f.name.endswith("_summary.json")]
        if len(report_files) == 0:
            print(f"❌ No report files found in: {output_dir}")
            print("   Cannot run evaluation without reports.")
            sys.exit(1)
        
        print(f"✓ Found {len(report_files)} existing report(s) in: {output_dir}")
    
    # ===========================================================================
    # Step 2: Run Evaluation
    # ===========================================================================
    if not args.skip_evaluation:
        print("\n" + "="*80)
        print("PHASE 2: ReportBench Evaluation")
        print("="*80)
        
        evaluation_cmd = [
            str(evaluation_script),
            str(output_dir),
            gt_dir,
            str(eval_dir)
        ]
        
        if not run_command(evaluation_cmd, "ReportBench Evaluation Pipeline"):
            print("\n❌ Evaluation failed!")
            success = False
        else:
            print("\n✅ Evaluation completed successfully")
            
            # Display results summary
            if eval_dir.exists():
                display_results_summary(eval_dir)
    else:
        print("\n⏭️  Skipping evaluation (--skip-evaluation flag set)")
    
    # ===========================================================================
    # Final Summary
    # ===========================================================================
    print("\n" + "="*80)
    print(" " * 30 + "FINAL STATUS")
    print("="*80)
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\n✅ All phases completed successfully!")
        
        if not args.skip_generation:
            print(f"\n📝 Reports saved to: {output_dir.absolute()}")
        
        if not args.skip_evaluation:
            print(f"📊 Evaluation results saved to: {eval_dir.absolute()}")
            print("\nTo view aggregate metrics:")
            print(f"   cat {eval_dir}/statement-results/aggregate_metrics.csv")
    else:
        print("\n❌ Pipeline completed with errors")
        print("   Please check the output above for details")
        sys.exit(1)
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
