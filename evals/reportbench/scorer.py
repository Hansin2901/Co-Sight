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

from typing import Dict


def evaluate_report_quality(report: str) -> Dict:
    """
    Evaluate the quality of a generated academic report.
    
    Args:
        report: Generated report text
        
    Returns:
        Dictionary containing quality metrics
    """
    # Basic metrics
    word_count = len(report.split())
    char_count = len(report)
    
    # Citation analysis
    citation_brackets = report.count('[')
    et_al_count = report.count('et al.')
    year_pattern_count = sum(1 for i in range(2000, 2026) if str(i) in report)
    
    # Structure analysis
    h1_headers = report.count('\n# ')
    h2_headers = report.count('\n## ')
    h3_headers = report.count('\n### ')
    total_headers = h1_headers + h2_headers + h3_headers
    
    # Quality assessment
    has_introduction = 'introduction' in report.lower() or '## 1.' in report
    has_conclusion = 'conclusion' in report.lower()
    has_sufficient_length = word_count >= 1000
    has_citations = et_al_count > 0 or citation_brackets > 3
    has_structure = total_headers >= 3
    
    quality_score = sum([
        has_introduction,
        has_conclusion,
        has_sufficient_length,
        has_citations,
        has_structure
    ]) / 5.0
    
    return {
        "word_count": word_count,
        "char_count": char_count,
        "citation_brackets": citation_brackets,
        "et_al_citations": et_al_count,
        "year_mentions": year_pattern_count,
        "h1_headers": h1_headers,
        "h2_headers": h2_headers,
        "h3_headers": h3_headers,
        "total_headers": total_headers,
        "has_introduction": has_introduction,
        "has_conclusion": has_conclusion,
        "has_sufficient_length": has_sufficient_length,
        "has_citations": has_citations,
        "has_structure": has_structure,
        "quality_score": quality_score
    }
