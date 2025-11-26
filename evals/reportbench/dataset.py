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

import json
from pathlib import Path
from typing import List, Dict, Optional

# Output format for academic survey reports
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
2. **Length**: Target 3000-5000 words for comprehensive coverage
3. **Structure**: Use clear markdown headers (##, ###) for organization
4. **Synthesis**: Don't just list papers - synthesize and compare approaches
5. **Technical depth**: Include technical details appropriate for academic audience
6. **Multiple sources**: Draw information from multiple papers, comparing and contrasting

Remember: You have access to paper titles, authors, publication dates, and summaries from your research steps. 
Use this information to create properly formatted citations throughout the report.
"""


def reportbench_dataset(
    dataset_path: Optional[Path] = None,
    limit: Optional[int] = None,
    start_idx: int = 0,
    task_id: Optional[List[str]] = None
) -> List[Dict]:
    """
    Load ReportBench dataset from JSONL file.
    
    Args:
        dataset_path: Path to ReportBench_v1.1.jsonl file. If None, uses default location.
        limit: Maximum number of entries to load
        start_idx: Starting index in the dataset
        task_id: List of specific arxiv_ids to load. If provided, only these entries are loaded.
    
    Returns:
        List of dataset entries with standardized format
    """
    if dataset_path is None:
        # Default path: look for ReportBench in parent directory
        default_path = Path(__file__).parent.parent.parent.parent / "ReportBench" / "ReportBench_v1.1.jsonl"
        if not default_path.exists():
            # Try alternative location
            default_path = Path(__file__).parent.parent.parent / "ReportBench_v1.1.jsonl"
        dataset_path = default_path
    
    if not dataset_path.exists():
        raise FileNotFoundError(f"ReportBench dataset not found at: {dataset_path}")
    
    entries = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < start_idx:
                continue
            if limit and len(entries) >= limit:
                break
            
            entry = json.loads(line.strip())
            
            # Filter by task_id if specified
            if task_id and entry['arxiv_id'] not in task_id:
                continue
            
            # Standardize entry format
            standardized_entry = {
                'task_id': entry['arxiv_id'],
                'arxiv_id': entry['arxiv_id'],
                'title': entry.get('title', 'N/A'),
                'prompt': entry['prompt'],
                'output_format': REPORT_OUTPUT_FORMAT,
                'authors': entry.get('authors', ''),
                'abstract': entry.get('abstract', ''),
                'categories': entry.get('categories', ''),
                'submitter': entry.get('submitter', ''),
            }
            
            entries.append(standardized_entry)
    
    return entries
