#!/bin/bash

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

#
# ReportBench Evaluation Script
# Runs official ReportBench evaluation pipeline on Co-Sight generated reports
#
# Usage:
#   ./evaluate_with_reportbench.sh <outputs_dir> <ground_truth_dir> <evaluation_results_dir>
#
# Example:
#   ./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results
#

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
OUTPUTS_DIR="${1:-Co-Sight-outputs}"
GT_DIR="${2:-../ReportBench/ReportBench_v1.1_GT}"
EVAL_DIR="${3:-evaluation-results}"

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COSIGHT_ROOT="$SCRIPT_DIR"
REPORTBENCH_DIR="$SCRIPT_DIR/../ReportBench"

# Convert to absolute paths
OUTPUTS_DIR="$COSIGHT_ROOT/$OUTPUTS_DIR"
EVAL_DIR="$COSIGHT_ROOT/$EVAL_DIR"

echo ""
echo "================================================================================"
echo "                    ReportBench Evaluation Pipeline"
echo "================================================================================"
echo ""
echo "Configuration:"
echo "  Co-Sight outputs:  $OUTPUTS_DIR"
echo "  Ground truth:      $GT_DIR"
echo "  Results output:    $EVAL_DIR"
echo "  ReportBench dir:   $REPORTBENCH_DIR"
echo ""

# Check if directories exist
if [ ! -d "$OUTPUTS_DIR" ]; then
    echo -e "${RED}❌ Error: Outputs directory not found: $OUTPUTS_DIR${NC}"
    echo "   Please run run_cosight_reportbench.py first to generate reports."
    exit 1
fi

if [ ! -d "$REPORTBENCH_DIR" ]; then
    echo -e "${RED}❌ Error: ReportBench directory not found: $REPORTBENCH_DIR${NC}"
    echo "   Please ensure ReportBench is cloned at: $REPORTBENCH_DIR"
    exit 1
fi

if [ ! -d "$GT_DIR" ]; then
    echo -e "${RED}❌ Error: Ground truth directory not found: $GT_DIR${NC}"
    exit 1
fi

# Count JSON files
NUM_FILES=$(find "$OUTPUTS_DIR" -maxdepth 1 -name "*.json" ! -name "*_summary.json" | wc -l | tr -d ' ')
if [ "$NUM_FILES" -eq 0 ]; then
    echo -e "${RED}❌ Error: No JSON output files found in: $OUTPUTS_DIR${NC}"
    echo "   Please run run_cosight_reportbench.py first to generate reports."
    exit 1
fi

echo -e "${GREEN}✓ Found $NUM_FILES report file(s) to evaluate${NC}"
echo ""

# Create evaluation results directory
mkdir -p "$EVAL_DIR"

# Change to ReportBench directory (required for their scripts)
cd "$REPORTBENCH_DIR"
echo -e "${BLUE}→ Changed to ReportBench directory: $(pwd)${NC}"
echo ""

# Define output subdirectories (relative to EVAL_DIR)
STAT_RESULTS_DIR="$EVAL_DIR/statement-results"
RELATED_WORK_DIR="$EVAL_DIR/related-work-results"

# ==============================================================================
# Step 1: Statement Evaluator (Citation alignment + fact-checking)
# ==============================================================================
echo "================================================================================"
echo "Step 1: Running Statement Evaluator (Citation Alignment + Fact-Checking)"
echo "================================================================================"
echo ""
echo "This evaluates:"
echo "  - Citation match rate (% of citations with correct content)"
echo "  - Non-cited accuracy (fact-checking without citations)"
echo ""

python3 statement_evaluator.py "$OUTPUTS_DIR" --output-dir "$STAT_RESULTS_DIR"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: statement_evaluator.py failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Statement evaluation completed${NC}"
echo -e "  Results saved to: $STAT_RESULTS_DIR"
echo ""

# ==============================================================================
# Step 2: Related Work Evaluator (Precision/Recall vs ground truth)
# ==============================================================================
echo "================================================================================"
echo "Step 2: Running Related Work Evaluator (Precision/Recall vs Ground Truth)"
echo "================================================================================"
echo ""
echo "This evaluates:"
echo "  - Precision (% of cited papers that are in ground truth)"
echo "  - Recall (% of ground truth papers that were cited)"
echo ""

python3 related_work_evaluator.py \
    --survey-dir "$OUTPUTS_DIR" \
    --ground-truth-dir "$GT_DIR" \
    --result-dir "$RELATED_WORK_DIR"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: related_work_evaluator.py failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Related work evaluation completed${NC}"
echo -e "  Results saved to: $RELATED_WORK_DIR"
echo ""

# ==============================================================================
# Step 3: Metrics Calculator (Aggregate final metrics)
# ==============================================================================
echo "================================================================================"
echo "Step 3: Running Metrics Calculator (Aggregating Final Metrics)"
echo "================================================================================"
echo ""

python3 metrics_calculator.py "$STAT_RESULTS_DIR"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: metrics_calculator.py failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Metrics calculation completed${NC}"
echo ""

# ==============================================================================
# Summary
# ==============================================================================
echo "================================================================================"
echo "                           Evaluation Complete!"
echo "================================================================================"
echo ""
echo "Results are saved in: $EVAL_DIR"
echo ""
echo "Key output files:"
echo "  1. Statement results:     $STAT_RESULTS_DIR/"
echo "     - citations.csv        (citation-level analysis)"
echo "     - no_citations.csv     (non-cited statements analysis)"
echo "     - summary.csv          (per-paper summary)"
echo ""
echo "  2. Related work results:  $RELATED_WORK_DIR/"
echo "     - evaluation_results.csv (precision/recall metrics)"
echo ""
echo "  3. Aggregated metrics:    $STAT_RESULTS_DIR/"
echo "     - aggregate_metrics.csv (overall performance summary)"
echo ""
echo "To view aggregate metrics:"
echo "  cat $STAT_RESULTS_DIR/aggregate_metrics.csv"
echo ""
echo "================================================================================"

# Return to Co-Sight directory
cd "$COSIGHT_ROOT"
