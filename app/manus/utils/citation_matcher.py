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
Citation Matcher Utility

Post-processes generated reports to inject URLs into citations by fuzzy matching
citation text (e.g., "[Xu et al., 2020]") to actual search results collected
during report generation.

Usage:
    from app.manus.utils.citation_matcher import inject_citation_urls
    
    # search_results comes from plan.get_search_results()
    enhanced_report, citation_metadata = inject_citation_urls(
        report_text=report,
        search_results=search_results,
        confidence_threshold=0.6
    )
"""

import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher


def extract_citations(text: str) -> List[Dict]:
    """
    Extract all citations from the report text.
    
    Matches patterns like:
        [Author et al., 2020]
        [Author et al., Year]
        [Author, 2020]
        [Paper Title, 2020]
        [Author and Author, 2020]
    
    Returns:
        List of dicts with:
            - full_match: The complete citation string including brackets
            - authors: Extracted author portion
            - year: Extracted year (as int if found)
            - position: Start position in text
    """
    citations = []
    
    # Pattern for various citation formats
    # Key insight: capture author part (non-digits, non-brackets) then year (4 digits)
    citation_patterns = [
        # [Author et al., 2020] or [Author and Author, 2020] - most common academic format
        r'\[([^\]\d]+?)\s*,?\s*(\d{4})[a-z]?\]',
    ]
    
    seen_matches = set()
    
    for pattern in citation_patterns:
        for match in re.finditer(pattern, text):
            full_match = match.group(0)
            
            # Skip if we've already captured this citation
            if full_match in seen_matches:
                continue
            seen_matches.add(full_match)
            
            inner_text = match.group(1).strip() if match.group(1) else ""
            year_str = match.group(2) if len(match.groups()) >= 2 else None
            
            # Extract author portion (everything before the year/comma)
            authors = inner_text.strip().rstrip(',').strip()
            
            citation = {
                'full_match': full_match,
                'authors': authors,
                'year': int(year_str) if year_str else None,
                'position': match.start(),
                'inner_text': f"{authors}, {year_str}" if year_str else authors
            }
            citations.append(citation)
    
    # Sort by position to maintain order
    citations.sort(key=lambda x: x['position'])
    
    return citations


def _normalize_author_name(name: str) -> str:
    """Normalize author name for comparison."""
    # Remove common suffixes
    name = re.sub(r'\s+et\s+al\.?$', '', name, flags=re.IGNORECASE)
    # Remove special characters
    name = re.sub(r'[^\w\s]', '', name)
    # Lowercase and strip
    return name.lower().strip()


def _extract_first_author_lastname(authors: List[str]) -> str:
    """Extract the last name of the first author."""
    if not authors:
        return ""
    
    first_author = authors[0]
    # Common formats: "John Smith", "Smith, John", "J. Smith"
    
    # If comma-separated, first part is last name
    if ',' in first_author:
        return first_author.split(',')[0].strip().lower()
    
    # Otherwise, last word is usually the last name
    parts = first_author.strip().split()
    if parts:
        return parts[-1].lower()
    
    return first_author.lower()


def _extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """Extract ArXiv ID from a URL if present."""
    if not url:
        return None
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
    if arxiv_match:
        return arxiv_match.group(1)
    return None


def _similarity(s1: str, s2: str) -> float:
    """Calculate string similarity using SequenceMatcher."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def match_citation_to_source(citation: Dict, search_results: List[Dict]) -> Tuple[Optional[Dict], float]:
    """
    Match a citation to the most likely source from search results.
    
    Uses fuzzy matching on:
        - Author last name similarity
        - Year exact match
        - Title similarity (for paper title citations)
        - ArXiv ID matching
    
    Args:
        citation: Dict with 'authors', 'year', 'inner_text'
        search_results: List of search result dicts
        
    Returns:
        (best_match, confidence_score)
    """
    if not search_results:
        return None, 0.0
    
    # === EXACT FORMAT MATCH (for citations generated from our source list) ===
    citation_text_normalized = citation.get('inner_text', '').strip()
    citation_year = citation.get('year')
    citation_authors_raw = citation.get('authors', '').strip()
    
    for result in search_results:
        result_authors = result.get('authors', [])
        result_year = result.get('year')
        
        if not result_authors or not result_year:
            continue
        
        # Build expected citation formats from result
        first_author = result_authors[0]
        first_author_last = first_author.split()[-1] if first_author else ""
        
        # Expected formats the LLM should generate:
        # "[Xu et al., 2020]" -> inner_text = "Xu et al., 2020"
        expected_formats = [
            f"{first_author_last} et al., {result_year}",      # "Xu et al., 2020"
            f"{first_author_last} et al. {result_year}",       # "Xu et al. 2020" (no comma)
            f"{first_author_last}, {result_year}",             # "Xu, 2020" (single author style)
            f"{first_author_last} {result_year}",              # "Xu 2020" (no comma)
        ]
        
        # Also try lowercase comparison
        citation_text_lower = citation_text_normalized.lower()
        
        for expected in expected_formats:
            if citation_text_normalized == expected or citation_text_lower == expected.lower():
                # Perfect match!
                result_copy = result.copy()
                result_copy['match_score'] = 1.0
                result_copy['match_components'] = {'exact_format_match': 1.0}
                print(f"[Citation Match] EXACT MATCH: '{citation_text_normalized}' -> '{result.get('title', 'N/A')[:50]}...'")
                return result_copy, 1.0
        
        # Also check if just the author last name matches (case-insensitive)
        if citation_authors_raw.lower().startswith(first_author_last.lower()) and citation_year == result_year:
            result_copy = result.copy()
            result_copy['match_score'] = 0.95
            result_copy['match_components'] = {'author_year_match': 0.95}
            print(f"[Citation Match] AUTHOR+YEAR MATCH: '{citation_text_normalized}' -> '{result.get('title', 'N/A')[:50]}...'")
            return result_copy, 0.95
    
    # === FALLBACK TO FUZZY MATCHING ===
    citation_authors = _normalize_author_name(citation.get('authors', ''))
    citation_text = citation.get('inner_text', '').lower()
    
    best_match = None
    best_score = 0.0
    
    for result in search_results:
        score = 0.0
        score_components = {}
        
        result_title = (result.get('title') or '').lower()
        result_authors = result.get('authors', [])
        result_year = result.get('year')
        result_url = result.get('url', '')
        result_arxiv_id = result.get('arxiv_id') or _extract_arxiv_id_from_url(result_url)
        
        # 1. Year matching (exact match is strong signal)
        if citation_year and result_year:
            if citation_year == result_year:
                score += 0.3  # Strong boost for year match
                score_components['year_match'] = 0.3
        
        # 2. Author matching
        if citation_authors and result_authors:
            first_author_lastname = _extract_first_author_lastname(result_authors)
            author_sim = _similarity(citation_authors, first_author_lastname)
            
            # Check if citation contains any author's last name
            for author in result_authors:
                lastname = author.split()[-1].lower() if author else ""
                if lastname and lastname in citation_authors.lower():
                    author_sim = max(author_sim, 0.8)
                    break
            
            score += author_sim * 0.4
            score_components['author_sim'] = author_sim * 0.4
        
        # 3. Title matching (for paper title citations)
        if result_title and len(citation_text) > 15:
            # Check if citation text is similar to title
            title_sim = _similarity(citation_text, result_title)
            # Also check if key words from citation appear in title
            citation_words = set(citation_text.split())
            title_words = set(result_title.split())
            word_overlap = len(citation_words & title_words) / max(len(citation_words), 1)
            
            title_score = max(title_sim, word_overlap) * 0.3
            score += title_score
            score_components['title_match'] = title_score
        
        # 4. ArXiv ID matching (perfect match)
        if result_arxiv_id and result_arxiv_id in citation_text:
            score = 1.0  # Perfect match
            score_components['arxiv_id_match'] = 1.0
        
        # 5. URL in citation (rare but possible)
        if result_url and ('arxiv' in citation_text or 'http' in citation_text):
            if result_arxiv_id and result_arxiv_id in citation_text:
                score = 1.0
                score_components['url_match'] = 1.0
        
        if score > best_score:
            best_score = score
            best_match = result.copy()
            best_match['match_score'] = score
            best_match['match_components'] = score_components
    
    return best_match, best_score


def inject_citation_urls(
    report_text: str,
    search_results: List[Dict],
    confidence_threshold: float = 0.6
) -> Tuple[str, Dict]:
    """
    Post-process a report to inject URLs into citations.
    
    Converts:
        [Xu et al., 2020]
    To:
        [Xu et al., 2020](https://arxiv.org/abs/2006.14799)
    
    Args:
        report_text: The generated report markdown text
        search_results: List of search results from plan.get_search_results()
        confidence_threshold: Minimum confidence to inject URL (0.0-1.0)
        
    Returns:
        (enhanced_report, citation_metadata)
        
        citation_metadata contains:
            - matched_citations: List of {citation, url, confidence, source}
            - unmatched_citations: List of citations that couldn't be matched
            - unused_sources: List of search results not cited
            - total_citations: Total number of citations found
            - match_rate: Percentage of citations successfully matched
    """
    if not report_text:
        return report_text, {'error': 'Empty report text'}
    
    # Debug: Show sample of search results
    print(f"[Citation Debug] Total search results: {len(search_results)}")
    for i, sr in enumerate(search_results[:5]):
        print(f"[Citation Debug] Sample result {i}: title='{sr.get('title', 'N/A')[:40]}...', "
              f"authors={sr.get('authors', [])[:2]}, year={sr.get('year')}, "
              f"url={sr.get('url', 'N/A')[:40]}...")
    
    # Extract all citations from the report
    citations = extract_citations(report_text)
    
    if not citations:
        return report_text, {
            'matched_citations': [],
            'unmatched_citations': [],
            'unused_sources': search_results,
            'total_citations': 0,
            'match_rate': 0.0,
            'note': 'No citations found in report'
        }
    
    # Track matches and non-matches
    matched_citations = []
    unmatched_citations = []
    used_source_urls = set()
    
    # Create a mapping of citation -> replacement
    replacements = []
    
    for citation in citations:
        match, confidence = match_citation_to_source(citation, search_results)
        
        # Debug: Show matching attempt
        print(f"[Citation Debug] Matching: {citation['full_match']}")
        print(f"[Citation Debug]   Authors: '{citation.get('authors')}', Year: {citation.get('year')}")
        print(f"[Citation Debug]   Best match confidence: {confidence:.2f}")
        if match:
            print(f"[Citation Debug]   Best match: {match.get('title', 'N/A')[:50]}...")
            print(f"[Citation Debug]   Match authors: {match.get('authors', [])[:2]}, year: {match.get('year')}")
        
        if match and confidence >= confidence_threshold:
            url = match.get('url', '')
            if url:
                matched_citations.append({
                    'citation': citation['full_match'],
                    'url': url,
                    'confidence': confidence,
                    'source_title': match.get('title'),
                    'source_tool': match.get('source_tool'),
                    'match_components': match.get('match_components', {})
                })
                used_source_urls.add(url)
                
                # Create replacement: [Author et al., 2020] -> [Author et al., 2020](url)
                original = citation['full_match']
                # Check if it already has a URL (markdown link)
                if not re.search(r'\]\s*\(', original):
                    replacement = f"{original}({url})"
                    replacements.append((original, replacement))
        else:
            unmatched_citations.append({
                'citation': citation['full_match'],
                'authors': citation.get('authors'),
                'year': citation.get('year'),
                'best_match_confidence': confidence if match else 0.0,
                'best_match_title': match.get('title') if match else None
            })
    
    # Apply replacements (in reverse order to preserve positions)
    enhanced_report = report_text
    for original, replacement in reversed(replacements):
        # Only replace first occurrence to avoid double-replacements
        enhanced_report = enhanced_report.replace(original, replacement, 1)
    
    # Find unused sources
    unused_sources = [
        s for s in search_results 
        if s.get('url') not in used_source_urls
    ]
    
    # Calculate statistics
    total_citations = len(citations)
    matched_count = len(matched_citations)
    match_rate = matched_count / total_citations if total_citations > 0 else 0.0
    
    citation_metadata = {
        'matched_citations': matched_citations,
        'unmatched_citations': unmatched_citations,
        'unused_sources': unused_sources,
        'total_citations': total_citations,
        'matched_count': matched_count,
        'unmatched_count': len(unmatched_citations),
        'match_rate': match_rate,
        'confidence_threshold': confidence_threshold,
        'search_results_count': len(search_results)
    }
    
    return enhanced_report, citation_metadata


def format_citation_report(citation_metadata: Dict) -> str:
    """
    Format citation metadata as a human-readable report.
    
    Useful for debugging and evaluation.
    """
    lines = [
        "=" * 60,
        "CITATION MATCHING REPORT",
        "=" * 60,
        "",
        f"Total Citations Found: {citation_metadata.get('total_citations', 0)}",
        f"Successfully Matched:  {citation_metadata.get('matched_count', 0)}",
        f"Unmatched:            {citation_metadata.get('unmatched_count', 0)}",
        f"Match Rate:           {citation_metadata.get('match_rate', 0):.1%}",
        f"Confidence Threshold: {citation_metadata.get('confidence_threshold', 0.6)}",
        f"Search Results Used:  {citation_metadata.get('search_results_count', 0)}",
        "",
    ]
    
    # Matched citations
    if citation_metadata.get('matched_citations'):
        lines.append("-" * 40)
        lines.append("MATCHED CITATIONS:")
        lines.append("-" * 40)
        for i, match in enumerate(citation_metadata['matched_citations'], 1):
            lines.append(f"{i}. {match.get('citation')}")
            lines.append(f"   -> {match.get('url')}")
            lines.append(f"   Confidence: {match.get('confidence', 0):.2f}")
            lines.append(f"   Source: {match.get('source_title', 'N/A')[:50]}...")
            lines.append("")
    
    # Unmatched citations
    if citation_metadata.get('unmatched_citations'):
        lines.append("-" * 40)
        lines.append("UNMATCHED CITATIONS:")
        lines.append("-" * 40)
        for i, unmatch in enumerate(citation_metadata['unmatched_citations'], 1):
            lines.append(f"{i}. {unmatch.get('citation')}")
            lines.append(f"   Authors: {unmatch.get('authors', 'N/A')}")
            lines.append(f"   Year: {unmatch.get('year', 'N/A')}")
            best_conf = unmatch.get('best_match_confidence', 0)
            if best_conf > 0:
                lines.append(f"   Best Match: {unmatch.get('best_match_title', 'N/A')[:40]}... ({best_conf:.2f})")
            lines.append("")
    
    # Unused sources
    unused = citation_metadata.get('unused_sources', [])
    if unused:
        lines.append("-" * 40)
        lines.append(f"UNUSED SOURCES ({len(unused)}):")
        lines.append("-" * 40)
        for i, source in enumerate(unused[:10], 1):  # Limit to 10
            lines.append(f"{i}. {source.get('title', 'N/A')[:50]}...")
            lines.append(f"   URL: {source.get('url', 'N/A')[:60]}...")
        if len(unused) > 10:
            lines.append(f"   ... and {len(unused) - 10} more")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test the citation matcher
    test_report = """
    # Test Report
    
    The introduction of **LayoutLM** [Xu et al., 2020] was a watershed moment.
    
    **LayoutLMv2** [Xu et al., 2020] addressed this limitation.
    
    Papers like **TableNet** [Paliwal et al., 2020] and **CascadeTabNet** [Prasad et al., 2020] 
    adapted established computer vision architectures.
    
    The authors of [LayoutLM, 2020] explicitly noted the need for more data.
    """
    
    test_search_results = [
        {
            'url': 'https://arxiv.org/abs/2006.14799',
            'title': 'LayoutLMv2: Multi-modal Pre-training for Visually-Rich Document Understanding',
            'authors': ['Yang Xu', 'Yiheng Xu', 'Tengchao Lv'],
            'year': 2020,
            'arxiv_id': '2006.14799',
            'source_tool': 'search_papers'
        },
        {
            'url': 'https://arxiv.org/abs/1912.13318',
            'title': 'LayoutLM: Pre-training of Text and Layout for Document Image Understanding',
            'authors': ['Yiheng Xu', 'Minghao Li', 'Lei Cui'],
            'year': 2019,
            'arxiv_id': '1912.13318',
            'source_tool': 'search_papers'
        },
        {
            'url': 'https://arxiv.org/abs/2004.12629',
            'title': 'TableNet: Deep Learning model for end-to-end Table detection and Tabular data extraction',
            'authors': ['Shubham Paliwal', 'D. Vishwanath', 'Rohit Rahul'],
            'year': 2020,
            'source_tool': 'search_papers'
        },
        {
            'url': 'https://arxiv.org/abs/2004.12926',
            'title': 'CascadeTabNet: An approach for end to end table detection and structure recognition',
            'authors': ['Devashish Prasad', 'Ayan Gadpal', 'Kshitij Kapadni'],
            'year': 2020,
            'source_tool': 'search_papers'
        }
    ]
    
    enhanced_report, metadata = inject_citation_urls(
        test_report,
        test_search_results,
        confidence_threshold=0.5
    )
    
    print("ENHANCED REPORT:")
    print("-" * 40)
    print(enhanced_report)
    print()
    print(format_citation_report(metadata))
