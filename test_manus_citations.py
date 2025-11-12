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
Test script to verify Manus citation tracking for ReportBench integration.
This script runs a simple question through Manus and checks if URLs are captured.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from app.manus.manus import Manus
from app.cosight.task.task_manager import TaskManager
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision
from app.common.logger_util import logger
import json
import ast

def main():
    # Setup test workspace
    test_workspace = Path("workspace/test_manus_citations")
    test_workspace.mkdir(parents=True, exist_ok=True)
    os.environ['WORKSPACE_PATH'] = str(test_workspace)

    # Simple test question (should trigger web search)
    question = "What are the latest advances in transformer neural networks in 2024?"

    logger.info("="*80)
    logger.info("MANUS CITATION TRACKING TEST")
    logger.info("="*80)
    logger.info(f"Question: {question}")
    logger.info("")

    # Run Manus
    logger.info("Starting Manus execution...")
    manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)

    try:
        result = manus.execute(question)

        logger.info("\n" + "="*80)
        logger.info("EXECUTION COMPLETED")
        logger.info("="*80)
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result length: {len(str(result))} characters")
        logger.info(f"Result preview (first 300 chars):\n{str(result)[:300]}")
        logger.info("")

    except Exception as e:
        logger.error(f"Manus execution failed: {e}", exc_info=True)
        return

    # Get the plan
    try:
        plan = TaskManager.get_plan(manus.plan_id)
        logger.info(f"Retrieved plan ID: {manus.plan_id}")
    except Exception as e:
        logger.error(f"Failed to get plan: {e}", exc_info=True)
        return

    # Analyze step_tools
    logger.info("\n" + "="*80)
    logger.info("CITATION TRACKING ANALYSIS")
    logger.info("="*80)

    total_urls = []
    total_tools = 0

    if not hasattr(plan, 'step_tools'):
        logger.error("❌ Plan does not have 'step_tools' attribute!")
        return

    if not plan.step_tools:
        logger.warning("⚠️  step_tools is empty - no tools were recorded!")

    for step, tool_records in plan.step_tools.items():
        logger.info(f"\n--- Step: {step} ---")
        logger.info(f"Number of tool calls: {len(tool_records)}")

        for idx, record in enumerate(tool_records, 1):
            total_tools += 1
            tool_name = record.get('tool', 'unknown')
            result_str = record.get('result', '')

            logger.info(f"\n  Tool #{idx}: {tool_name}")
            logger.info(f"    Result type: {type(result_str)}")
            logger.info(f"    Result length: {len(str(result_str))} characters")
            logger.info(f"    Result preview: {str(result_str)[:150]}...")

            # Try to extract URLs
            if tool_name in ['tavily_search', 'search_google', 'search_wiki']:
                try:
                    # Parse string result back to data structure
                    result_data = ast.literal_eval(result_str)

                    logger.info(f"    Parsed result type: {type(result_data)}")

                    if isinstance(result_data, list):
                        logger.info(f"    Found list with {len(result_data)} items")

                        for item_idx, item in enumerate(result_data):
                            if isinstance(item, dict):
                                url = item.get('url')
                                title = item.get('title', 'No title')

                                if url:
                                    total_urls.append({
                                        'url': url,
                                        'title': title,
                                        'step': step,
                                        'tool': tool_name
                                    })
                                    logger.info(f"      ✓ URL #{item_idx+1}: {url}")
                                    logger.info(f"        Title: {title[:80]}...")

                    elif isinstance(result_data, dict):
                        logger.info(f"    Found dict with keys: {list(result_data.keys())}")

                except SyntaxError as e:
                    logger.warning(f"    ⚠️  SyntaxError parsing result: {e}")
                except ValueError as e:
                    logger.warning(f"    ⚠️  ValueError parsing result: {e}")
                except Exception as e:
                    logger.warning(f"    ⚠️  Failed to parse result: {e}")

            elif tool_name == 'scrape_website':
                # For scrape_website, URL is in args
                args = record.get('args', {})
                url = args.get('url')
                if url:
                    total_urls.append({
                        'url': url,
                        'title': 'Scraped website',
                        'step': step,
                        'tool': tool_name
                    })
                    logger.info(f"    ✓ Scraped URL: {url}")

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    logger.info(f"Total steps: {len(plan.step_tools)}")
    logger.info(f"Total tool calls: {total_tools}")
    logger.info(f"Total unique URLs found: {len(total_urls)}")
    logger.info("")

    if total_urls:
        logger.info("📋 EXTRACTED CITATIONS:")
        for i, cite in enumerate(total_urls[:20], 1):  # Show first 20
            logger.info(f"  {i}. {cite['url']}")
            logger.info(f"     Title: {cite['title'][:80]}")
            logger.info(f"     From: {cite['step']} (via {cite['tool']})")
            logger.info("")

        if len(total_urls) > 20:
            logger.info(f"  ... and {len(total_urls) - 20} more citations")

    # Verdict
    logger.info("\n" + "="*80)
    logger.info("VERDICT")
    logger.info("="*80)

    if total_urls > 0:
        logger.info("✅ SUCCESS: Citation tracking is working!")
        logger.info(f"   Found {len(total_urls)} citations that can be used for ReportBench")
    else:
        logger.warning("⚠️  WARNING: No citations found!")
        logger.warning("   This could mean:")
        logger.warning("   1. No search tools were called")
        logger.warning("   2. Tool results are not being recorded")
        logger.warning("   3. Tool result format is different than expected")

    logger.info("="*80)
    logger.info("")

if __name__ == '__main__':
    main()
