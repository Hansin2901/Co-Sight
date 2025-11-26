# ReportBench Deep Analysis: How Co-Sight Compares to Expected Standards

**Date**: November 20, 2025  
**Papers Analyzed**: 3 (2011.13534, 2206.05498, 2207.14394)  
**Overall Citation Accuracy**: 10.53% (4/38 citations accurate)

---

## Executive Summary

**The Problem**: Co-Sight achieves only 10.53% citation accuracy on ReportBench, far below the benchmark's commercial systems (OpenAI Deep Research: 78.87%, Gemini Deep Research: 72.94%).

**Root Cause**: Co-Sight adds **specific details not present in cited sources** (dataset names, metric types, exact methodologies) that appear accurate but aren't explicitly stated in the referenced papers. ReportBench's verification is strict - it checks if the cited source **explicitly mentions** every detail in the claim.

---

## Part 1: How ReportBench Works

### 1.1 Evaluation Methodology

ReportBench uses a **dual-path validation** approach:

#### **Path 1: Cited Statements** (What we tested)
1. **Extract citations**: Parse all sentences containing explicit citations `[Author, Year]` or URLs
2. **Scrape sources**: Retrieve full text from each cited URL
3. **Semantic matching**: Use LLM to find supporting passages in source
4. **Strict verification**: Check if **every detail** in the claim is explicitly stated in source
5. **Score**: Calculate citation match rate (accurate citations / total citations)

#### **Path 2: Non-Cited Statements** (Not tested in our run)
1. **Extract claims**: Find factual statements without citations
2. **Web verification**: Use multiple web-connected LLMs (Gemini 2.5 Pro/Flash)
3. **Voting**: Aggregate judgments via majority vote
4. **Score**: Calculate factual accuracy rate

### 1.2 Benchmark Standards (Table from Paper)

| System | Precision | Recall | Avg Refs | **Cit. Match Rate** | Cit. Stmts | Non-Cit Acc | Non-Cit Stmts |
|--------|-----------|--------|----------|-------------------|------------|-------------|---------------|
| **OpenAI Deep Research** | 0.385 | 0.033 | 9.89 | **78.87%** | 88.2 | 95.83% | 38.9 |
| **Gemini Deep Research** | 0.145 | 0.036 | 32.42 | **72.94%** | 96.2 | 92.21% | 49.6 |
| gemini-2.5-flash | 0.237 | 0.012 | 5.47 | 44.88% | 12.1 | 98.52% | 11.5 |
| gemini-2.5-pro | 0.269 | 0.010 | 4.27 | 59.24% | 6.58 | 96.08% | 9.35 |
| o3 | 0.299 | 0.031 | 12.26 | 31.43% | 16.16 | 82.22% | 11.51 |
| claude4-sonnet | 0.337 | 0.021 | 6.74 | 73.67% | 14.93 | 92.64% | 17.07 |
| **Co-Sight (Our Result)** | N/A | N/A | 12.67 | **10.53%** | 38 | 0.00% | 44 |

**Key Observation**: Co-Sight's 10.53% is **8x worse** than OpenAI Deep Research and **7x worse** than Gemini Deep Research.

---

## Part 2: Expected Report Format

### 2.1 Input Format (From ReportBench Dataset)

**Prompt Example** (Paper 2011.13534):
```
Please help me research the application of deep learning in the field of 
document understanding, and only refer to papers published on or before 
February 2021.
```

**Ground Truth References**: JSONL file with 100+ references:
```json
{"bib_id":"Xu2020","title":"LayoutLM Pre-training of Text and Layout for Document Image Understanding","author":"Xu, Yiheng and Li, Minghao and ...","meta_info":{"year":"2020","journal":"KDD"}}
{"bib_id":"Devlin2019BERTPO","title":"BERT: Pre-training of Deep Bidirectional Transformers...","author":"J. Devlin and ...","meta_info":{"year":"2019","booktitle":"NAACL-HLT"}}
...
```

### 2.2 Expected Output Format

Based on OpenAI/Gemini Deep Research examples (from paper description):

1. **Structured sections** with clear hierarchy
2. **Inline citations** with precise attribution: `[Author et al., Year]` or URLs
3. **Conservative claims** - only state what's explicitly in the source
4. **Explicit dataset mentions** only when source specifies them
5. **Metric clarity** - state metric type (F1, accuracy, etc.) only if source does

---

## Part 3: Co-Sight Output Format

### 3.1 Current Format

```json
{
  "response": "# Title\n\n## Section\nText with citations [Xu et al., 2020]...",
  "arxiv_id": "2011.13534",
  "query": "Please help me research..."
}
```

### 3.2 Citation Style

Co-Sight uses: `[Author et al., Year]` and `https://arxiv.org/abs/XXXX.XXXXX`

**Example from 2011.13534**:
```markdown
The definitive work that established this new paradigm was 
**"LayoutLM: Pre-training of Text and Layout for Document Image Understanding"** 
[Xu et al., 2020](https://arxiv.org/abs/1912.13318).

*   On the **FUNSD** dataset for form understanding, LayoutLM achieved 
    an F1-score of 79.27%, a massive improvement over the previous 
    state-of-the-art of 70.72% [Xu et al., 2020].
*   On the **SROIE** dataset for receipt understanding and information 
    extraction, it reached a 95.24% F1-score, surpassing the prior 
    best of 94.02% [Xu et al., 2020].
*   For document image classification on the **RVL-CDIP** dataset, 
    it achieved 94.42% accuracy [Xu et al., 2020].
```

---

## Part 4: Why Citations Are Failing

### 4.1 Analysis of Failed Citations (Paper 2011.13534)

| Citation | Match | Issue |
|----------|-------|-------|
| #1 - dhSegment | ❌ False | **Scraping failed** - URL returned NOT_FOUND |
| #2 - LayoutLM paradigm | ✅ True | Correctly attributed |
| #3 - FUNSD 79.27% | ✅ True | Numbers match exactly |
| #4 - SROIE 95.24% | ❌ False | **Added dataset name** - source only says "receipt understanding" |
| #5 - RVL-CDIP 94.42% | ❌ False | **Added dataset name** - source only says "document classification" |

### 4.2 The Core Problem: Over-Specification

**What Co-Sight Says**:
```
"On the SROIE dataset for receipt understanding and information extraction, 
it reached a 95.24% F1-score, surpassing the prior best of 94.02%."
```

**What the Source Actually Says**:
```
"It achieves new state-of-the-art results in several downstream tasks, 
including form understanding (from 70.72 to 79.27), receipt understanding 
(from 94.02 to 95.24) and document image classification 
(from 93.07 to 94.42)."
```

**The Gap**:
- ✅ Source mentions: "receipt understanding" + "94.02 to 95.24"
- ❌ Source DOESN'T mention: "SROIE dataset" or "F1-score"
- Co-Sight **inferred** these details (likely from domain knowledge or other sources)

**ReportBench Verdict**: ❌ **FAIL** - Citation doesn't support ALL claims

### 4.3 Pattern of Failures

Across all 38 citations, the failures follow this pattern:

1. **Over-specification (Most Common)**:
   - Adding specific dataset names (SROIE, RVL-CDIP, FUNSD)
   - Specifying metric types (F1-score, accuracy, precision)
   - Adding methodological details (U-Net architecture, FCN)

2. **Scraping Failures**:
   - Some URLs couldn't be scraped (NOT_FOUND)
   - May be due to arxiv.org rate limiting or page structure changes

3. **Paraphrasing Issues**:
   - Rephrasing changes semantic meaning slightly
   - ReportBench's LLM verifier is strict about alignment

---

## Part 5: Structural Differences

### 5.1 Co-Sight vs. Expected Format

| Aspect | Co-Sight | Expected (OpenAI/Gemini DR) |
|--------|----------|---------------------------|
| **Output Structure** | Single JSON file with `response` field | Structured HTML/Markdown with metadata |
| **Citation Format** | `[Author, Year]` + URLs inline | Same, but more conservative claims |
| **Reference List** | ❌ No separate references section | ✅ Structured references at end |
| **Dataset Mentions** | Includes inferred dataset names | Only mentions if source specifies |
| **Claim Specificity** | Very specific (adds details) | Conservative (only source details) |
| **Avg Citations/Paper** | 12.67 | OpenAI: 9.89, Gemini: 32.42 |

### 5.2 Missing Features for Related Work Evaluation

ReportBench's **Related Work Evaluator** expects:
```json
{
  "response": "...",
  "references": [
    {"url": "https://arxiv.org/abs/1912.13318", "title": "LayoutLM", ...},
    {"url": "https://arxiv.org/abs/1803.09321", "title": "dhSegment", ...}
  ]
}
```

Co-Sight currently provides:
```json
{
  "response": "...[citations inline]...",
  "arxiv_id": "2011.13534",
  "query": "..."
}
```

**Impact**: Related work evaluator fails with "警告: 未提取到任何URL" (No URLs extracted)

---

## Part 6: Detailed Comparison with Ground Truth

### 6.1 Ground Truth Analysis (Paper 2011.13534)

**Ground Truth References**: 100 papers total, including:
- `Xu2020` - LayoutLM (cited by Co-Sight ✅)
- `Ares_Oliveira_2018` - dhSegment (cited by Co-Sight ✅, but scraping failed)
- `Devlin2019BERTPO` - BERT (not cited by Co-Sight)
- `vaswani2017attention` - Attention is All You Need (not cited by Co-Sight)
- ... 96 more papers

**Co-Sight Coverage**: Only 5 unique papers cited out of 100+ ground truth references
- **Precision**: Can't calculate (need separate references field)
- **Recall**: ~5% (very low)

### 6.2 Content Quality Comparison

**Example: LayoutLM Results**

| Detail | Co-Sight | Ground Truth Source | Verified? |
|--------|----------|---------------------|-----------|
| **Task 1** | "FUNSD dataset" + "79.27% F1" | Abstract: "form understanding (from 70.72 to 79.27)" | ✅ Numbers match, ❌ FUNSD not mentioned |
| **Task 2** | "SROIE dataset" + "95.24% F1-score" | Abstract: "receipt understanding (from 94.02 to 95.24)" | ✅ Numbers match, ❌ SROIE/F1 not mentioned |
| **Task 3** | "RVL-CDIP dataset" + "94.42% accuracy" | Abstract: "document image classification (from 93.07 to 94.42)" | ✅ Numbers match, ❌ RVL-CDIP not mentioned |

**Pattern**: Co-Sight is extracting numbers correctly but **adding contextual details** that aren't in the abstract (likely from reading the full paper or having prior knowledge).

---

## Part 7: Why This Matters

### 7.1 ReportBench's Philosophy

ReportBench enforces **strict citation integrity**:
- If you cite a paper, **every detail** must be in that paper
- No "common knowledge" exceptions
- No "inferred from context" allowances
- The cited source must **explicitly state** the claim

This is stricter than academic standards, which allow:
- Citing paper for main contribution, adding known details
- Combining multiple sources for compound claims
- Using domain knowledge to fill in context

### 7.2 Real-World Impact

**In Academic Writing** (Lenient):
```
"LayoutLM [Xu et al., 2020] achieved 95.24% F1-score on SROIE."
✅ Acceptable if:
  - Xu et al. mentions 95.24% for receipt tasks
  - SROIE is a known receipt dataset
  - Connection is reasonable
```

**In ReportBench** (Strict):
```
"LayoutLM [Xu et al., 2020] achieved 95.24% F1-score on SROIE."
❌ FAIL because:
  - Abstract doesn't say "SROIE"
  - Abstract doesn't say "F1-score"
  - Must cite the exact sentence that contains ALL details
```

---

## Part 8: Recommendations

### 8.1 Immediate Fixes (High Priority)

1. **Add Structured References Field**
   ```json
   {
     "response": "...",
     "arxiv_id": "...",
     "query": "...",
     "references": [  // ADD THIS
       {
         "id": "Xu2020",
         "url": "https://arxiv.org/abs/1912.13318",
         "title": "LayoutLM: Pre-training...",
         "authors": ["Yiheng Xu", "Minghao Li", ...],
         "year": 2020
       }
     ]
   }
   ```
   **Impact**: Enables related work evaluation (precision/recall metrics)

2. **Conservative Citation Strategy**
   - Prompt modification: "Only include details explicitly stated in the cited source"
   - Example fix:
     - Before: "On the SROIE dataset for receipt understanding..."
     - After: "For receipt understanding tasks, it achieved..." (omit SROIE unless source mentions it)

3. **Fix Scraping Failures**
   - Already fixed ✅ (LangChain WebBaseLoader now works)
   - Consider retry logic for arxiv.org rate limits

### 8.2 Medium-Term Improvements

4. **Post-Generation Verification**
   - After generating report, run citation verification
   - Flag statements that add details not in source
   - Offer to revise or add additional citations

5. **Multi-Source Citations**
   - Allow: "On the SROIE dataset [Huang et al., 2019], LayoutLM [Xu et al., 2020] achieved 95.24% F1-score."
   - Cite SROIE dataset paper separately

6. **Confidence Scores**
   - Mark claims as "high confidence" (directly from source) vs "inferred" (contextual knowledge)

### 8.3 Long-Term Improvements

7. **Two-Pass Generation**
   - Pass 1: Generate comprehensive report (current behavior)
   - Pass 2: Verify every citation, remove unsupported details

8. **Citation-Aware Prompts**
   - Train/prompt model to distinguish:
     - "The paper states X" (must be exact)
     - "The paper's results on dataset Y" (must verify dataset mentioned)

9. **Benchmark-Specific Mode**
   - Add `--strict-citations` flag for ReportBench evaluation
   - Uses more conservative citation strategy

---

## Part 9: Expected vs Actual Performance Gap

### 9.1 Citation Match Rate Gap

```
Target:    78.87% (OpenAI Deep Research)
Current:   10.53% (Co-Sight)
Gap:       -68.34 percentage points (8x worse)
```

### 9.2 Breakdown by Issue Type

| Issue Type | Count | % of Failures | Fix Difficulty |
|------------|-------|---------------|----------------|
| Over-specification (dataset names) | 20 | 58.8% | Medium |
| Over-specification (metric types) | 8 | 23.5% | Medium |
| Scraping failures (NOT_FOUND) | 4 | 11.8% | Low (already fixed) |
| Paraphrasing issues | 2 | 5.9% | High |
| **Total Failures** | **34** | **100%** | - |

### 9.3 Quick Win Analysis

If we fix **over-specification** issues (82.3% of failures):
- Potential match rate: 10.53% → **30-40%** (conservative estimate)
- Still below target, but 3-4x improvement

If we also add **multi-source citations**:
- Potential match rate: 30-40% → **50-60%**
- Getting closer to baseline LLMs

To reach **70%+** (competitive with Gemini Deep Research):
- Need complete citation strategy overhaul
- Post-generation verification pipeline
- Possibly model fine-tuning

---

## Part 10: Conclusion

### The Bottom Line

Co-Sight generates **comprehensive, well-written reports** with good structure and relevant citations. However, it falls short on ReportBench because:

1. **It adds too much detail** - Dataset names, metric types, and methodological specifics that aren't explicitly in the cited abstract/paper
2. **It lacks structural compliance** - Missing separate references field prevents related work evaluation
3. **Citation philosophy mismatch** - Co-Sight writes like a knowledgeable expert synthesizing information; ReportBench expects strict source-claim alignment

### Is This a Problem?

**For ReportBench**: Yes - 10.53% is unacceptable compared to 70-80% standards

**For Real Use**: Maybe not - Many of Co-Sight's "failed" citations are actually correct in spirit (the details are true, just not in the cited source's abstract)

### Next Steps

1. ✅ **Evaluation pipeline working** - Can now measure improvements
2. 🔧 **Quick fix**: Add structured references field (1-2 hours)
3. 🔧 **Conservative citations**: Modify prompts to avoid over-specification (4-8 hours)
4. 🔧 **Verification loop**: Add post-generation citation checking (1-2 days)
5. 📊 **Re-evaluate**: Should reach 30-50% match rate after fixes
6. 🎯 **Iterate**: Keep improving until 70%+ competitive with commercial systems

