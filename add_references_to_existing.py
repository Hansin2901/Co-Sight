#!/usr/bin/env python3
"""
Add references field to existing Co-Sight reports.
This script reads existing JSON reports and adds the references field without regenerating.
"""

import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional

import requests


def fetch_arxiv_metadata(arxiv_id: str) -> Optional[Dict]:
    """Fetch paper metadata from ArXiv API."""
    try:
        clean_id = arxiv_id.split('v')[0]
        api_url = f"http://export.arxiv.org/api/query?id_list={clean_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entry = root.find('atom:entry', ns)
        if entry is None:
            return None
        
        title = entry.find('atom:title', ns)
        title_text = "Unknown Title"
        if title is not None and title.text:
            title_text = title.text.strip().replace('\n', ' ')
        
        authors = []
        for author in entry.findall('atom:author', ns):
            name = author.find('atom:name', ns)
            if name is not None and name.text:
                authors.append(name.text.strip())
        
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
        print(f"      Warning: Failed to fetch ArXiv metadata for {arxiv_id}: {e}")
        return None


def fetch_semantic_scholar_metadata(url: str) -> Optional[Dict]:
    """Fetch paper metadata from Semantic Scholar API."""
    try:
        api_url = f"https://api.semanticscholar.org/graph/v1/paper/URL:{url}"
        params = {"fields": "title,authors,year,externalIds"}
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        title = data.get('title', 'Unknown Title')
        authors = [author.get('name', '') for author in data.get('authors', [])]
        year = data.get('year')
        
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
        print(f"      Warning: Failed to fetch Semantic Scholar metadata for {url}: {e}")
        return None


def extract_references_from_markdown(report: str) -> List[Dict]:
    """Extract references from markdown report text."""
    references = []
    seen_urls = set()
    
    markdown_links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', report)
    plain_urls = re.findall(r'https?://[^\s\)\]]+', report)
    
    all_urls = []
    for text, url in markdown_links:
        all_urls.append(url)
    all_urls.extend(plain_urls)
    
    print(f"      Found {len(all_urls)} URLs in report")
    
    for url in all_urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        url = url.rstrip('.,;:!?)')
        
        metadata = None
        
        arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            metadata = fetch_arxiv_metadata(arxiv_id)
            time.sleep(0.5)
        
        if metadata is None:
            metadata = fetch_semantic_scholar_metadata(url)
            time.sleep(0.5)
        
        if metadata is None:
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
    
    print(f"      Extracted {len(references)} unique references")
    return references


def process_report_file(file_path: Path) -> bool:
    """Process a single report file and add references field."""
    try:
        print(f"\n   Processing: {file_path.name}")
        
        # Load existing report
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if references already exist
        if 'references' in data:
            print(f"      ✓ Already has references field ({len(data['references'])} refs)")
            return True
        
        # Extract references
        report = data.get('response', '')
        references = extract_references_from_markdown(report)
        
        # NOTE: Co-Sight reports don't contain URLs, only inline citations like [Xu et al., 2020]
        # This means we can't automatically build a reference list without additional processing
        # For now, we add an empty list to prevent errors in the evaluator
        if len(references) == 0:
            print(f"      ℹ️  No URLs found (Co-Sight uses inline citations only)")
            print(f"      ℹ️  Adding empty references list (related work eval won't work)")
        
        # Add references field
        data['references'] = references
        
        # Save updated report
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"      ✅ Added references field ({len(references)} refs)")
        return True
        
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return False


def main():
    """Main execution function."""
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    else:
        output_dir = Path("Co-Sight-outputs")
    
    if not output_dir.exists():
        print(f"❌ Directory not found: {output_dir}")
        sys.exit(1)
    
    print("="*80)
    print(" "*20 + "Add References to Existing Reports")
    print("="*80)
    print(f"\nDirectory: {output_dir.absolute()}")
    
    # Find all JSON files
    json_files = list(output_dir.glob("*.json"))
    # Exclude summary files
    json_files = [f for f in json_files if not f.name.startswith("generation_summary")]
    
    print(f"Found: {len(json_files)} report files")
    
    if len(json_files) == 0:
        print("❌ No report files found")
        sys.exit(1)
    
    # Process each file
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(json_files, 1):
        print(f"\n[{i}/{len(json_files)}]", end=" ")
        if process_report_file(file_path):
            successful += 1
        else:
            failed += 1
    
    # Print summary
    print("\n" + "="*80)
    print(" "*30 + "SUMMARY")
    print("="*80)
    print(f"\nTotal Files:      {len(json_files)}")
    print(f"✅ Successful:    {successful}")
    print(f"❌ Failed:        {failed}")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
