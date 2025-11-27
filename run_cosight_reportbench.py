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
Co-Sight ReportBench Runner
Generates academic survey reports in ReportBench-compatible format.

Usage:
    python run_cosight_reportbench.py
    python run_cosight_reportbench.py --config my_config.json
    python run_cosight_reportbench.py --arxiv-ids 2312.04861 2308.06419
"""

import atexit
import argparse
import datetime
import json
import os
import re
import sys
import time
import traceback
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional

import requests

from app.manus.manus import Manus
from app.manus.llm.langfuse_config import initialize_langfuse, shutdown_langfuse
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision

# Report output format template
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
1. **Citations**: Include inline citations for ALL claims using this EXACT format:
   - Use [FirstAuthorLastName et al., Year] format for all citations
   - Example: "Recent work by [Smith et al., 2024] demonstrates..."
   - Example: "The LayoutLM model [Xu et al., 2020] introduced..."
   - IMPORTANT: Only cite papers from the "AVAILABLE SOURCES FOR CITATIONS" list provided above
   - DO NOT cite papers from your training data that you didn't actually search for
   - Match the exact author names and years from the sources list
2. **Length**: Target 3000-5000 words for comprehensive coverage
3. **Structure**: Use clear markdown headers (##, ###) for organization
4. **Synthesis**: Don't just list papers - synthesize and compare approaches
5. **Technical depth**: Include technical details appropriate for academic audience
6. **Multiple sources**: Draw information from multiple papers, comparing and contrasting

Remember: You have access to paper titles, authors, publication dates, and summaries from your research steps.
Use ONLY the papers from the "AVAILABLE SOURCES FOR CITATIONS" list when creating citations.
"""


def load_config(config_path: str = "reportbench_config.json") -> Dict:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_reportbench_dataset(dataset_path: str) -> Dict[str, Dict]:
    """Load ReportBench dataset and return as dict keyed by arxiv_id."""
    dataset_file = Path(dataset_path)
    if not dataset_file.exists():
        print(f"❌ Dataset file not found: {dataset_path}")
        sys.exit(1)
    
    dataset = {}
    with open(dataset_file, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line.strip())
            dataset[entry['arxiv_id']] = entry
    
    return dataset


def fetch_arxiv_metadata(arxiv_id: str) -> Optional[Dict]:
    """
    Fetch paper metadata from ArXiv API.
    
    Returns dict with: id, url, title, authors, year
    """
    try:
        # Clean arxiv_id (remove version if present)
        clean_id = arxiv_id.split('v')[0]
        
        api_url = f"http://export.arxiv.org/api/query?id_list={clean_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entry = root.find('atom:entry', ns)
        if entry is None:
            return None
        
        # Extract metadata
        title = entry.find('atom:title', ns)
        title_text = "Unknown Title"
        if title is not None and title.text:
            title_text = title.text.strip().replace('\n', ' ')
        
        # Get authors
        authors = []
        for author in entry.findall('atom:author', ns):
            name = author.find('atom:name', ns)
            if name is not None and name.text:
                authors.append(name.text.strip())
        
        # Get publication year from published date
        published = entry.find('atom:published', ns)
        year = None
        if published is not None and published.text:
            year_match = re.search(r'(\d{4})', published.text)
            if year_match:
                year = int(year_match.group(1))
        
        return {
            "id": clean_id,
            "url": f"https://arxiv.org/abs/{clean_id}",
            "title": title_text,
            "authors": authors,
            "year": year
        }
        
    except Exception as e:
        print(f"Warning: Failed to fetch ArXiv metadata for {arxiv_id}: {e}")
        return None


def fetch_semantic_scholar_metadata(url: str) -> Optional[Dict]:
    """
    Fetch paper metadata from Semantic Scholar API.
    
    Returns dict with: id, url, title, authors, year
    """
    try:
        # Try to extract DOI or paper ID from URL
        api_url = f"https://api.semanticscholar.org/graph/v1/paper/URL:{url}"
        params = {"fields": "title,authors,year,externalIds"}
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract metadata
        title = data.get('title', 'Unknown Title')
        authors = [author.get('name', '') for author in data.get('authors', [])]
        year = data.get('year')
        
        # Generate ID from external IDs or URL
        external_ids = data.get('externalIds', {})
        ref_id = external_ids.get('DOI') or external_ids.get('ArXiv') or url.split('/')[-1]
        
        return {
            "id": ref_id,
            "url": url,
            "title": title,
            "authors": authors,
            "year": year
        }
        
    except Exception as e:
        print(f"Warning: Failed to fetch Semantic Scholar metadata for {url}: {e}")
        return None


def extract_references_from_markdown(report: str) -> List[Dict]:
    """
    Extract references from markdown report text.
    
    Looks for URLs in the text and fetches metadata from ArXiv/Semantic Scholar APIs.
    
    Returns list of reference dicts with format:
    {
        "id": "2011.13534" or "Smith2020" or fallback ID,
        "url": "https://arxiv.org/abs/2011.13534",
        "title": "Paper Title",
        "authors": ["Author 1", "Author 2"],
        "year": 2020
    }
    """
    references = []
    seen_urls = set()
    
    # Pattern 1: Markdown links [text](url)
    markdown_links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', report)
    
    # Pattern 2: Plain URLs
    plain_urls = re.findall(r'https?://[^\s\)\]]+', report)
    
    # Combine all URLs
    all_urls = []
    for text, url in markdown_links:
        all_urls.append(url)
    all_urls.extend(plain_urls)
    
    print(f"   Found {len(all_urls)} URLs in report")
    
    for url in all_urls:
        # Skip duplicates
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        # Clean URL (remove trailing punctuation)
        url = url.rstrip('.,;:!?)')
        
        # Try to fetch metadata
        metadata = None
        
        # Check if ArXiv URL
        arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            metadata = fetch_arxiv_metadata(arxiv_id)
            
            # Add a small delay to respect API rate limits
            time.sleep(0.5)
        
        # If not ArXiv or failed, try Semantic Scholar
        if metadata is None:
            metadata = fetch_semantic_scholar_metadata(url)
            time.sleep(0.5)
        
        # If still no metadata, create minimal reference
        if metadata is None:
            # Try to generate ID from URL
            url_parts = urllib.parse.urlparse(url)
            ref_id = url_parts.path.split('/')[-1] or f"ref_{len(references)+1}"
            
            metadata = {
                "id": ref_id,
                "url": url,
                "title": "Unknown Title",
                "authors": [],
                "year": None
            }
        
        references.append(metadata)
    
    print(f"   Extracted {len(references)} unique references")
    return references


def save_reportbench_output(output_dir: Path, arxiv_id: str, report: str, query: str) -> None:
    """Save report in ReportBench-compatible JSON format."""
    output_file = output_dir / f"{arxiv_id}.json"
    
    # Extract references from report
    print(f"   Extracting references...")
    references = extract_references_from_markdown(report)
    
    output_data = {
        "response": report,  # Pure markdown report
        "arxiv_id": arxiv_id,
        "query": query,
        "references": references  # Add references field
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved: {output_file} (with {len(references)} references)")


def generate_reports(
    arxiv_ids: List[str],
    dataset: Dict[str, Dict],
    output_dir: Path,
    manus_executor
) -> Dict[str, List]:
    """
    Generate reports for specified arxiv_ids.
    
    Returns dict with 'successful' and 'failed' lists.
    """
    results = {
        "successful": [],
        "failed": []
    }
    
    total = len(arxiv_ids)
    
    for i, arxiv_id in enumerate(arxiv_ids, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{total}] Processing: {arxiv_id}")
        
        # Check if arxiv_id exists in dataset
        if arxiv_id not in dataset:
            error_msg = f"ArXiv ID not found in dataset: {arxiv_id}"
            print(f"❌ {error_msg}")
            results["failed"].append({
                "arxiv_id": arxiv_id,
                "error": error_msg
            })
            continue
        
        entry = dataset[arxiv_id]
        query = entry.get('prompt', '')
        title = entry.get('title', 'N/A')
        
        # Truncate long titles for display
        if len(title) > 70:
            title_display = title[:67] + "..."
        else:
            title_display = title
        
        print(f"Title: {title_display}")
        print(f"Status: Generating report... ⏳")
        
        start_time = datetime.datetime.now()
        
        try:
            # Generate report with Co-Sight
            report = manus_executor(query, REPORT_OUTPUT_FORMAT)
            
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Format duration
            if duration < 60:
                dur_str = f"{duration:.0f}s"
            elif duration < 3600:
                dur_str = f"{int(duration/60)}m {int(duration%60)}s"
            else:
                dur_str = f"{int(duration/3600)}h {int((duration%3600)/60)}m"
            
            # Save in ReportBench format
            save_reportbench_output(output_dir, arxiv_id, report, query)
            
            results["successful"].append({
                "arxiv_id": arxiv_id,
                "title": title,
                "duration": duration
            })
            
            # Calculate report stats
            word_count = len(report.split())
            citation_count = report.count('[') + report.count('et al.')
            
            print(f"✅ Completed in {dur_str}")
            print(f"   Words: {word_count:,} | Citations: {citation_count}")
            
        except Exception as e:
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = str(e)
            print(f"❌ Failed after {duration:.1f}s: {error_msg}")
            print(f"   Traceback: {traceback.format_exc()}")
            
            results["failed"].append({
                "arxiv_id": arxiv_id,
                "title": title,
                "error": error_msg,
                "duration": duration
            })
            
            # Continue to next paper
            continue
    
    return results


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate academic survey reports with Co-Sight for ReportBench evaluation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="reportbench_config.json",
        help="Path to configuration JSON file (default: reportbench_config.json)"
    )
    parser.add_argument(
        "--arxiv-ids",
        nargs='+',
        help="Override config and specify arxiv IDs directly (e.g., 2312.04861 2308.06419)"
    )
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print(" "*20 + "Co-Sight ReportBench Runner")
    print("="*80)
    
    # Initialize Langfuse observability
    print("\n[Langfuse] Initializing observability...")
    initialize_langfuse()
    atexit.register(shutdown_langfuse)
    
    # Load configuration
    print(f"\n[Config] Loading from: {args.config}")
    config = load_config(args.config)
    
    # Override arxiv_ids if provided via CLI
    if args.arxiv_ids:
        arxiv_ids = args.arxiv_ids
        print(f"[Config] Using CLI arxiv_ids: {arxiv_ids}")
    else:
        arxiv_ids = config['arxiv_ids']
        print(f"[Config] Using config arxiv_ids: {arxiv_ids}")
    
    # Setup paths
    dataset_path = Path(config['reportbench_dataset'])
    output_dir = Path(config['output_dir'])
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Output] Directory: {output_dir.absolute()}")
    
    # Load ReportBench dataset
    print(f"\n[Dataset] Loading from: {dataset_path}")
    dataset = load_reportbench_dataset(str(dataset_path))
    print(f"[Dataset] Total entries: {len(dataset)}")
    print(f"[Dataset] Processing: {len(arxiv_ids)} papers")
    
    # Create Manus executor
    print("\n[Manus] Initializing executor...")
    def manus_executor(question: str, output_format: str) -> str:
        manus = Manus(llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision)
        result = manus.execute(question, output_format=output_format)
        return result
    
    # Generate reports
    print(f"\n[Generation] Starting report generation...")
    print(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = generate_reports(arxiv_ids, dataset, output_dir, manus_executor)
    
    # Print summary
    print("\n" + "="*80)
    print(" "*30 + "SUMMARY")
    print("="*80)
    print(f"\nTotal Papers:     {len(arxiv_ids)}")
    print(f"✅ Successful:    {len(results['successful'])} ({len(results['successful'])/len(arxiv_ids)*100:.0f}%)")
    print(f"❌ Failed:        {len(results['failed'])} ({len(results['failed'])/len(arxiv_ids)*100:.0f}%)")
    
    if results['successful']:
        avg_duration = sum(r['duration'] for r in results['successful']) / len(results['successful'])
        print(f"\nAvg Duration:     {avg_duration:.1f}s per paper")
    
    if results['failed']:
        print(f"\n❌ Failed Papers:")
        for failed in results['failed']:
            print(f"   - {failed['arxiv_id']}: {failed['error'][:50]}...")
    
    print(f"\nOutputs saved to: {output_dir.absolute()}")
    print("="*80 + "\n")
    
    # Save run summary
    summary_file = output_dir / "generation_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total": len(arxiv_ids),
            "successful": len(results['successful']),
            "failed": len(results['failed']),
            "arxiv_ids_processed": arxiv_ids,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"Run summary saved to: {summary_file}")


if __name__ == '__main__':
    main()
