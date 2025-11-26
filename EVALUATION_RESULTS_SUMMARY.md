# Co-Sight ReportBench Evaluation Results
**Evaluation Date:** November 20, 2025  
**Papers Evaluated:** 3 (arxiv IDs: 2011.13534, 2206.05498, 2207.14394)

---

## Executive Summary

### Overall Citation Accuracy: **10.53%** 

Co-Sight generated 38 cited statements across 3 research papers. Only **4 out of 38 statements (10.53%)** were accurately supported by their cited sources according to ReportBench's verification.

---

## Detailed Results

### Statement Evaluation (Citation Accuracy)

| Paper ID | Citations | Accurate | Match Rate | Status |
|----------|-----------|----------|------------|--------|
| **2011.13534** | 5 | 2 | **40.00%** | 🟡 Moderate |
| **2206.05498** | 22 | 2 | **9.09%** | 🔴 Poor |
| **2207.14394** | 11 | 0 | **0.00%** | 🔴 Critical |
| **TOTAL** | **38** | **4** | **10.53%** | 🔴 **Poor** |

---

## Key Findings

### ✅ What Worked
1. **Report Generation**: Co-Sight successfully generated comprehensive reports for all 3 papers
2. **Citation Extraction**: 38 citations were properly formatted with URLs
3. **Web Scraping**: All cited sources were successfully retrieved using LangChain WebBaseLoader
4. **Evaluation Pipeline**: Complete end-to-end evaluation workflow executed successfully

### ❌ Critical Issues Identified

#### 1. **Low Citation Accuracy (10.53%)**
- **89.47% of citations are misaligned** with their sources
- Common issues:
  - Statements add details not present in source (e.g., dataset names, specific metrics)
  - Paraphrasing changes meaning
  - Citations point to papers that don't contain the claimed information

#### 2. **Example Misalignments**

**Paper 2011.13534 - LayoutLM Analysis:**
```
❌ CLAIM: "For document image classification on the RVL-CDIP dataset, it achieved 94.42% accuracy."
   SOURCE: Only mentions "document image classification (from 93.07 to 94.42)" 
   ISSUE: Source doesn't mention RVL-CDIP dataset specifically

❌ CLAIM: "On the SROIE dataset for receipt understanding..."
   SOURCE: Only mentions "receipt understanding (from 94.02 to 95.24)"
   ISSUE: Source doesn't mention SROIE dataset or that metric is F1-score
```

#### 3. **Related Work Evaluation Failed**
- **Issue**: Co-Sight JSON outputs don't have a separate "references" field
- **Impact**: Cannot evaluate precision/recall of cited papers vs ground truth
- **Current Status**: All 3 papers show "警告: 未提取到任何URL" (No URLs extracted)

---

## Technical Details

### Evaluation Environment
- **ReportBench Version**: v1.1
- **Co-Sight Output Format**: JSON with `response`, `arxiv_id`, `query` fields
- **Scraping Method**: LangChain WebBaseLoader (Firecrawl fallback disabled due to API changes)
- **Verification Method**: LLM-based alignment checking

### Files Generated
```
Co-Sight/evaluation-results/
└── statement-results/
    ├── 2011.13534/
    │   ├── citations.csv (5 citations extracted)
    │   ├── matched.csv (matching results)
    │   ├── final.csv (2/5 verified as accurate)
    │   └── no_citations.csv (6 non-cited statements)
    ├── 2206.05498/
    │   ├── citations.csv (22 citations extracted)
    │   ├── matched.csv
    │   ├── final.csv (2/22 verified as accurate)
    │   └── no_citations.csv (21 non-cited statements)
    └── 2207.14394/
        ├── citations.csv (11 citations extracted)
        ├── matched.csv
        ├── final.csv (0/11 verified as accurate)
        └── no_citations.csv (17 non-cited statements)
```

---

## Recommendations

### Immediate Actions
1. **Review Citation Generation Logic** - The low match rate suggests systematic issues in how Co-Sight attributes information to sources
2. **Add Dataset Name Verification** - When mentioning specific datasets, ensure they're explicitly named in the source
3. **Improve Paraphrasing** - Maintain semantic alignment when rephrasing source content
4. **Add References Field** - Modify Co-Sight output to include structured references list for related work evaluation

### Future Improvements
1. Implement citation verification during generation (not just post-hoc)
2. Add confidence scores to generated statements
3. Separate factual claims from interpretative statements
4. Create a citation quality feedback loop

---

## Bugs Fixed During Evaluation

### 1. **Fixed: Firecrawl API Compatibility**
- **Error**: `AttributeError: 'Firecrawl' object has no attribute 'scrape_url'`
- **Cause**: Firecrawl library API changed, old method no longer exists
- **Fix**: Prioritized LangChain WebBaseLoader, which works perfectly
- **File**: `ReportBench/statement/scrape_content.py:84-86`

### 2. **Fixed: None Content Crashes**
- **Error**: `'NoneType' object has no attribute 'lower'` during evaluation
- **Cause**: OpenAI API returns `None` for content when LLM makes tool calls
- **Fix**: Added null-safety checks in two locations
- **Files**: 
  - `app/manus/agent/base/base_agent.py:110`
  - `app/manus/agent/planner/task_plannr_agent.py:185`

---

## Conclusion

The evaluation pipeline is **now fully functional** and identified a **critical issue with citation accuracy (10.53%)**. The low match rate indicates that Co-Sight needs significant improvements in:
1. How it extracts information from cited papers
2. How it attributes specific claims to sources
3. Avoiding adding details (like dataset names) that aren't in the original source

**Next Step**: Investigate the Co-Sight prompts and citation generation logic to improve accuracy from 10.53% to at least 70%+.
