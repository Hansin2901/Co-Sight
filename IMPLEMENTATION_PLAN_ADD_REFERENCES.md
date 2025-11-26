# Implementation Plan: Add `references` Field to Co-Sight Output

**Goal**: Add structured `references` field to Co-Sight JSON output to enable ReportBench's Related Work evaluation.

**Current Status**: 
- ❌ Related work evaluation fails: "警告: 未提取到任何URL" (No URLs extracted)
- ✅ Citation extraction works (URLs found in report text via regex)
- ❌ Missing structured references list prevents precision/recall calculation

---

## Understanding the Problem

### Current Output Format
```json
{
  "response": "# Report\n\nText with [Author, 2020](https://arxiv.org/abs/1912.13318)...",
  "arxiv_id": "2011.13534",
  "query": "Please help me research..."
}
```

### Expected Format for Full Evaluation
```json
{
  "response": "...",
  "arxiv_id": "2011.13534",
  "query": "...",
  "references": [
    {
      "id": "Xu2020",
      "url": "https://arxiv.org/abs/1912.13318",
      "title": "LayoutLM: Pre-training of Text and Layout for Document Image Understanding",
      "authors": ["Yiheng Xu", "Minghao Li", "Lei Cui", "Shaohan Huang", "Furu Wei", "Ming Zhou"],
      "year": 2020,
      "venue": "KDD"
    }
  ]
}
```

---

## Implementation Strategy

### Option 1: Post-Processing (RECOMMENDED - Fastest)
**Extract references from generated markdown after report is created**

**Pros:**
- ✅ No changes to Manus agent logic
- ✅ Fast to implement (1-2 hours)
- ✅ Can be done in `run_cosight_reportbench.py` only

**Cons:**
- ⚠️ Metadata quality depends on what's scraped/available
- ⚠️ May not get full author lists, venue info

**Implementation Steps:**
1. Add `extract_references_from_markdown()` function
2. Parse URLs from markdown using regex
3. For each URL, try to fetch paper metadata:
   - Use arxiv API for arxiv.org URLs
   - Use Semantic Scholar API for other academic papers
   - Fallback: minimal info (just URL + title from scraping)
4. Add to output JSON before saving

**Code Location:**
- File: `run_cosight_reportbench.py`
- Function to modify: `save_reportbench_output()`
- Add new function: `extract_references_from_markdown()`

---

### Option 2: During Generation (More Complex)
**Have Manus agent track and output references as it generates**

**Pros:**
- ✅ Higher quality metadata (agent knows what papers it used)
- ✅ Can track ALL papers accessed, not just cited

**Cons:**
- ❌ Requires modifying Manus agent internals
- ❌ Needs to track state during generation
- ❌ More complex, 1-2 days implementation

**Not recommended for quick fix**

---

## Detailed Implementation Plan (Option 1)

### Step 1: Create Reference Extraction Function

**Location**: `run_cosight_reportbench.py`

```python
import re
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse

def extract_references_from_markdown(markdown_text: str) -> List[Dict]:
    """
    Extract all unique URLs from markdown and enrich with metadata.
    
    Returns list of reference dicts with: url, title, authors, year, venue, id
    """
    # Pattern 1: [Author, Year](URL)
    # Pattern 2: Bare URLs: https://...
    # Pattern 3: [Text](URL)
    
    url_pattern = r'(https?://[^\s\)\]\"\'>]+)'
    urls = re.findall(url_pattern, markdown_text)
    
    # Deduplicate while preserving order
    unique_urls = list(dict.fromkeys(urls))
    
    references = []
    for url in unique_urls:
        ref = extract_paper_metadata(url)
        if ref:
            references.append(ref)
    
    return references


def extract_paper_metadata(url: str) -> Optional[Dict]:
    """
    Fetch paper metadata from URL using various APIs.
    
    Priority:
    1. ArXiv API (for arxiv.org URLs)
    2. Semantic Scholar API (for other papers)
    3. Fallback: Basic info from URL
    """
    parsed = urlparse(url)
    
    # ArXiv URLs
    if 'arxiv.org' in parsed.netloc:
        return fetch_arxiv_metadata(url)
    
    # Semantic Scholar API for other papers
    return fetch_semantic_scholar_metadata(url)


def fetch_arxiv_metadata(url: str) -> Optional[Dict]:
    """
    Fetch paper metadata from ArXiv API.
    
    Example URL: https://arxiv.org/abs/1912.13318
    API: http://export.arxiv.org/api/query?id_list=1912.13318
    """
    # Extract arxiv ID from URL
    match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', url)
    if not match:
        return None
    
    arxiv_id = match.group(1)
    
    try:
        api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            # Parse XML response (arxiv API returns XML)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            # Find the entry element
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entry = root.find('atom:entry', ns)
            
            if entry is not None:
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns).text.strip()
                    authors.append(name)
                
                # Get publication year from published date
                published = entry.find('atom:published', ns).text
                year = int(published.split('-')[0])
                
                # Generate ID (simple: first author + year)
                first_author = authors[0].split()[-1] if authors else "Unknown"
                ref_id = f"{first_author}{year}"
                
                return {
                    "id": ref_id,
                    "url": url,
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "venue": "arXiv",
                    "arxiv_id": arxiv_id
                }
    except Exception as e:
        print(f"⚠️  Failed to fetch arxiv metadata for {url}: {e}")
    
    # Fallback: minimal info
    return {
        "id": f"arxiv_{arxiv_id}",
        "url": url,
        "title": f"ArXiv Paper {arxiv_id}",
        "authors": [],
        "year": None,
        "venue": "arXiv"
    }


def fetch_semantic_scholar_metadata(url: str) -> Optional[Dict]:
    """
    Fetch paper metadata from Semantic Scholar API.
    
    API: https://api.semanticscholar.org/v1/paper/{url}
    """
    try:
        api_url = f"https://api.semanticscholar.org/v1/paper/{url}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            authors = [author['name'] for author in data.get('authors', [])]
            year = data.get('year')
            title = data.get('title', '')
            venue = data.get('venue', 'Unknown')
            
            first_author = authors[0].split()[-1] if authors else "Unknown"
            ref_id = f"{first_author}{year}" if year else first_author
            
            return {
                "id": ref_id,
                "url": url,
                "title": title,
                "authors": authors,
                "year": year,
                "venue": venue
            }
    except Exception as e:
        print(f"⚠️  Failed to fetch Semantic Scholar metadata for {url}: {e}")
    
    # Fallback: minimal info from URL
    return {
        "id": url.split('/')[-1][:10],  # Use last part of URL as ID
        "url": url,
        "title": "Unknown Paper",
        "authors": [],
        "year": None,
        "venue": "Unknown"
    }
```

### Step 2: Modify `save_reportbench_output()` Function

**Before**:
```python
def save_reportbench_output(output_dir: Path, arxiv_id: str, report: str, query: str) -> None:
    """Save report in ReportBench-compatible JSON format."""
    output_file = output_dir / f"{arxiv_id}.json"
    
    output_data = {
        "response": report,
        "arxiv_id": arxiv_id,
        "query": query
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved: {output_file}")
```

**After**:
```python
def save_reportbench_output(output_dir: Path, arxiv_id: str, report: str, query: str) -> None:
    """Save report in ReportBench-compatible JSON format with references."""
    output_file = output_dir / f"{arxiv_id}.json"
    
    # Extract references from markdown
    print("  Extracting references from report...")
    references = extract_references_from_markdown(report)
    print(f"  Found {len(references)} unique references")
    
    output_data = {
        "response": report,
        "arxiv_id": arxiv_id,
        "query": query,
        "references": references  # ADD THIS
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved: {output_file} (with {len(references)} references)")
```

### Step 3: Add Import Statements

At the top of `run_cosight_reportbench.py`, add:
```python
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
```

### Step 4: Add Rate Limiting (Optional but Recommended)

```python
import time
from functools import wraps

def rate_limit(calls_per_second=2):
    """Rate limiting decorator for API calls."""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

# Apply to fetch functions
@rate_limit(calls_per_second=2)
def fetch_arxiv_metadata(url: str) -> Optional[Dict]:
    # ... existing code ...
```

---

## Testing Plan

### Test 1: Verify Reference Extraction
```bash
cd /Users/HansinPatwa/hansin/Projects/teleport/Co-Sight
source .venv/bin/activate

# Run on one paper
python run_cosight_reportbench.py --arxiv-ids 2011.13534

# Check output
cat Co-Sight-outputs/2011.13534.json | python -m json.tool | grep -A 20 '"references"'
```

**Expected**:
```json
"references": [
  {
    "id": "Xu2020",
    "url": "https://arxiv.org/abs/1912.13318",
    "title": "LayoutLM: Pre-training of Text and Layout...",
    "authors": ["Yiheng Xu", "Minghao Li", ...],
    "year": 2020,
    "venue": "arXiv"
  },
  ...
]
```

### Test 2: Verify Related Work Evaluation Works
```bash
cd /Users/HansinPatwa/hansin/Projects/teleport/Co-Sight
./evaluate_with_reportbench.sh Co-Sight-outputs ../ReportBench/ReportBench_v1.1_GT evaluation-results
```

**Expected**:
- ✅ No more "警告: 未提取到任何URL" errors
- ✅ Precision/Recall metrics calculated
- ✅ Related work results in `evaluation-results/related-work-results/`

### Test 3: Compare Before/After
```bash
# Before (current)
grep -c "references" Co-Sight-outputs/2011.13534.json
# Output: 0

# After (with fix)
grep -c "references" Co-Sight-outputs/2011.13534.json
# Output: 1
```

---

## Expected Impact

### Before Implementation:
```
Related Work Evaluation:
  Status: ❌ Failed
  Error: "警告: 未提取到任何URL"
  Precision: N/A
  Recall: N/A
```

### After Implementation:
```
Related Work Evaluation:
  Status: ✅ Success
  Precision: ~0.15-0.25 (estimated - depends on coverage)
  Recall: ~0.05-0.10 (estimated - Co-Sight cites ~5 of 100 ground truth papers)
  Avg Refs: 12.67
```

**Note**: Precision/Recall will still be low because Co-Sight only cites ~5 unique papers per report vs ~100 in ground truth. This is a content issue, not a format issue. The fix enables **measurement** of these metrics.

---

## Timeline

### Immediate (1-2 hours):
- ✅ Add reference extraction functions
- ✅ Modify save function
- ✅ Test on 1 paper

### Next Day:
- ✅ Test on all 3 papers
- ✅ Run full evaluation
- ✅ Verify metrics appear

### Week 1:
- 🎯 Focus on improving citation accuracy (10.53% → 30-50%)
- 🎯 Prompt engineering for conservative citations

---

## Alternative: Minimal Implementation

If you just want to **unblock the related work evaluator** without fetching metadata:

```python
def extract_references_from_markdown(markdown_text: str) -> List[Dict]:
    """Minimal version: just extract URLs."""
    url_pattern = r'(https?://[^\s\)\]\"\'>]+)'
    urls = re.findall(url_pattern, markdown_text)
    unique_urls = list(dict.fromkeys(urls))
    
    references = []
    for i, url in enumerate(unique_urls):
        references.append({
            "id": f"ref_{i+1}",
            "url": url,
            "title": "",
            "authors": [],
            "year": None,
            "venue": ""
        })
    
    return references
```

**Pros**: 5 minutes to implement
**Cons**: No metadata, but evaluator will still work

---

## Files to Modify

1. **`run_cosight_reportbench.py`** (Primary)
   - Add: `extract_references_from_markdown()`
   - Add: `fetch_arxiv_metadata()`
   - Add: `fetch_semantic_scholar_metadata()` (optional)
   - Modify: `save_reportbench_output()`
   - Add imports: `re`, `requests`, `xml.etree.ElementTree`, `urllib.parse`

2. **No other files need changes** ✅

---

## Success Criteria

✅ **Format compliance**: JSON has `references` field with list of dicts  
✅ **Related work evaluation runs**: No more "未提取到任何URL" error  
✅ **Precision/Recall calculated**: Values appear in results (even if low)  
✅ **Valid references**: Each reference has at minimum `url` and `id`  
✅ **Metadata quality**: At least arxiv papers have title, authors, year  

---

## Next Steps After This Fix

1. ✅ **Measure baseline**: Get precision/recall numbers (likely ~0.15-0.25 / 0.05-0.10)
2. 🎯 **Improve coverage**: Make Co-Sight cite more relevant papers (increase recall)
3. 🎯 **Improve citation accuracy**: Fix over-specification issue (increase match rate)
4. 🎯 **Iterate**: Re-evaluate and track improvements

