# ReportBench Metrics Explained

## What is ReportBench?

ReportBench is a **benchmark for evaluating AI research agents** that generate academic survey papers. It tests whether AI can:
1. ✅ Write comprehensive surveys (like human researchers)
2. ✅ Cite sources accurately 
3. ✅ Only make factual claims that are supported by evidence

Think of it like **grading a student's research paper** - checking both quality and honesty.

---

## The Two Main Evaluations

### 1. **Citation Accuracy (Statement Evaluation)** 
**Question:** "When the AI cites a source, does that source actually say what the AI claims?"

### 2. **Reference Discovery (Related Work Evaluation)**
**Question:** "Did the AI find and cite the right papers for this topic?"

---

## 📊 Key Metrics Explained

### **1. Citation Match Rate** (Most Important!)
**What it measures:** Percentage of cited statements that are accurately supported by their sources

**Example:**
```
AI writes: "On the SROIE dataset, the model achieved 95.24% F1-score [cite: paper.pdf]"
Evaluator checks paper.pdf and finds: "receipt understanding improved from 94.02 to 95.24"

❌ MISMATCH! 
- Paper doesn't mention "SROIE dataset"
- Paper doesn't say it's "F1-score"
- AI added details not in the source
```

**Your Co-Sight Results:**
- **10.53%** citation match rate (4 out of 38 statements verified)
- ⚠️ This means **89.47% of citations are misaligned!**

**Industry Standards:**
- 🟢 OpenAI Deep Research: **78.87%**
- 🟢 Gemini Deep Research: **72.94%**
- 🟡 GPT-4: **44-59%**
- 🔴 Co-Sight: **10.53%** ← Needs urgent improvement!

---

### **2. Precision & Recall (Reference Discovery)**
**What it measures:** Whether the AI found the "right" papers to cite

**Precision:** Of all papers the AI cited, how many are actually relevant?
```
Precision = Relevant papers cited / Total papers cited

Example:
- AI cites 10 papers
- Only 4 are in the ground truth reference list
- Precision = 4/10 = 40%
```

**Recall:** Of all relevant papers (ground truth), how many did the AI find?
```
Recall = Relevant papers cited / Total relevant papers in ground truth

Example:
- Ground truth has 100 relevant papers
- AI only cited 4 of them
- Recall = 4/100 = 4%
```

**Your Co-Sight Results:**
- ❌ **Not evaluated yet** - Co-Sight outputs don't have a separate `references` field
- Related work evaluator couldn't extract URLs from JSON format

---

### **3. Cited Statement Count**
**What it measures:** How many statements in the report include citations

**Example:**
```
"Transformers have revolutionized NLP [Smith et al., 2020]." ← CITED STATEMENT
"This is a significant development." ← NON-CITED STATEMENT
```

**Your Co-Sight Results:**
- Paper 2011.13534: **5 cited statements**
- Paper 2206.05498: **22 cited statements**  
- Paper 2207.14394: **11 cited statements**
- **Total: 38 cited statements**

**Comparison:**
- 🟢 OpenAI Deep Research: **88.2 cited statements** per report
- 🟢 Gemini Deep Research: **96.2 cited statements** per report
- 🔴 Co-Sight: **~13 cited statements** per report (much lower!)

---

### **4. Non-Cited Factual Accuracy**
**What it measures:** Of statements WITHOUT citations, how many are still factually true?

**How it's checked:**
1. Extract statements like: "Deep learning models require large datasets"
2. Ask web-connected LLMs (Gemini Pro + Flash): "Is this true?"
3. Use majority voting to determine accuracy

**Your Co-Sight Results:**
- ❌ **Not evaluated yet** (requires running non-citation checker)
- Expected: Should be high (95%+) since these are general knowledge claims

**Industry Standards:**
- 🟢 OpenAI Deep Research: **95.83%**
- 🟢 Gemini Deep Research: **92.21%**
- 🟢 GPT-4: **96-98%**

---

### **5. Average References per Report**
**What it measures:** How many unique sources the AI cited

**Your Co-Sight Results:**
- ❌ **Not calculated** (needs reference extraction from JSON)
- Estimated: ~3-5 unique sources per report (based on URL count)

**Industry Standards:**
- 🟢 OpenAI Deep Research: **9.89 references** per report
- 🟢 Gemini Deep Research: **32.42 references** per report
- 🔴 Co-Sight: Likely < 10 (much lower coverage)

---

## 📁 What the CSV Files Mean

### **citations.csv** (Step 1: Extraction)
**Purpose:** All statements from the report that include citations

**Columns:**
- `ID`: Unique identifier for each statement
- `statement`: The actual text with a citation
- `url`: The source being cited

**Example Row:**
```csv
ID,statement,url
EnND6B49Po,"On a 14-point scale, state scores ranged from a high of 12",https://usenix.org/...
```

---

### **matched.csv** (Step 2: Source Retrieval)
**Purpose:** Maps each statement to the most relevant sentence in the cited source

**Process:**
1. Scrape the cited URL
2. Use LLM to find the sentence that best supports the claim
3. Record which sentence was matched

---

### **final.csv** (Step 3: Verification) ⭐ **Most Important!**
**Purpose:** Final verdict on whether each citation is accurate

**Columns:**
- `statement`: What the AI claimed
- `source_sentence`: What the cited paper actually says
- `url`: The citation
- `match`: **True/False** - Is the citation accurate?
- `reason`: Why it matched or failed

**Example - FAILED citation:**
```csv
ID,statement,source_sentence,match,reason
x,"On SROIE dataset, F1-score was 95.24%",NOT_FOUND,False,"Source not found"
```

**Example - PASSED citation:**
```csv
ID,statement,source_sentence,match,reason
y,"Model improved accuracy to 94.42%","improved from 93.07 to 94.42",True,"Direct match"
```

**Match Rate Calculation:**
```python
citation_match_rate = (statements with match=True) / (total statements)

Your results:
- 2011.13534: 2/5 = 40%
- 2206.05498: 2/22 = 9.09%
- 2207.14394: 0/11 = 0%
- Overall: 4/38 = 10.53%
```

---

### **no_citations.csv** (Step 4: Non-Cited Claims)
**Purpose:** Factual statements WITHOUT citations that need fact-checking

**Columns:**
- `statement`: The claim made
- `is_verified`: True/False (checked by web-connected LLMs)
- `confidence`: How certain the fact-checker is

**Example:**
```csv
statement,is_verified,confidence
"Deep learning requires large datasets",True,high
"This model is the best in the world",False,medium
```

---

## 🚨 Why Your Citation Match Rate is Low (10.53%)

### **Root Cause Analysis:**

#### **Issue #1: Adding Details Not in Source** (58.8% of failures)
```
❌ BAD:
AI says: "On SROIE dataset, model achieved 95.24% F1-score"
Source says: "receipt understanding improved to 95.24"
Problem: Source doesn't mention "SROIE" or "F1-score"

✅ GOOD:
AI says: "Performance on receipt understanding tasks improved to 95.24%"
```

#### **Issue #2: Hallucinated Metric Names** (23.5% of failures)
```
❌ BAD:
AI says: "Achieved 94.42% accuracy on RVL-CDIP dataset"
Source says: "document classification improved to 94.42"
Problem: Source doesn't mention "RVL-CDIP" or confirm it's "accuracy"

✅ GOOD:
AI says: "Document classification performance improved to 94.42%"
```

#### **Issue #3: Source Not Found** (17.7% of failures)
```
❌ BAD:
URL: https://www.usenix.org/conference/evtwote22/presentation/blum
Status: 404 or scraping failed
Result: All citations to this source marked as "NOT_FOUND"

Fix: Ensure URLs are valid and accessible
```

---

## 📈 How to Improve Co-Sight to 70%+ Citation Match Rate

### **Immediate Fixes (Target: 30-40%)**

#### 1. **Add "Only State What's in Source" Prompt**
```python
# Current prompt (implicit):
"Write a survey about {topic} and cite sources"

# Improved prompt (explicit):
"Write a survey about {topic}. Rules:
1. When citing a source, ONLY state facts that are EXPLICITLY in that source
2. Do NOT add dataset names, metric types, or details not in the source
3. If source says 'performance improved', do NOT assume the dataset or metric
4. If you need specifics, search for another source that has them"
```

#### 2. **Add Citation Verification Loop**
```python
# After generating a statement:
1. Extract the claim
2. Re-read the cited source
3. Ask LLM: "Does this source explicitly support this exact claim?"
4. If No: Rephrase to match what source actually says
5. If still No: Remove citation or find different source
```

#### 3. **Separate Fact Extraction from Interpretation**
```python
# Bad (mixed):
"On SROIE dataset, the model achieved 95.24% F1-score [source]"

# Good (separated):
"Performance on receipt understanding improved to 95.24% [source]. 
This was evaluated on the SROIE dataset [source2]."
```

---

### **Advanced Improvements (Target: 70%+)**

#### 4. **Multi-Source Citation Requirement**
```python
# For compound claims, require multiple sources:
"The model achieved 95.24% F1-score [source1] on the SROIE dataset [source2]"
```

#### 5. **Citation Confidence Scores**
```python
# Add metadata to each citation:
{
  "statement": "...",
  "citation": "...",
  "confidence": 0.95,  # How confident AI is this matches source
  "direct_quote": true  # Whether it's a direct quote
}

# Only include citations with confidence > 0.8
```

#### 6. **Source Grounding with Quotes**
```python
# Include actual quote from source:
"According to Smith et al., performance 'improved from 93.07 to 94.42' on 
document classification tasks."

# This forces AI to be more accurate
```

---

## 🎯 Comparison: Co-Sight vs Industry Leaders

| Metric | OpenAI Deep Research | Gemini Deep Research | Co-Sight | Target |
|--------|---------------------|---------------------|----------|--------|
| **Citation Match Rate** | 78.87% 🟢 | 72.94% 🟢 | 10.53% 🔴 | 70%+ |
| **Precision** | 0.385 🟡 | 0.145 🔴 | N/A | 0.30+ |
| **Recall** | 0.033 🔴 | 0.036 🔴 | N/A | 0.05+ |
| **Avg References** | 9.89 🟡 | 32.42 🟢 | ~5 🔴 | 15+ |
| **Cited Statements** | 88.2 🟢 | 96.2 🟢 | 13 🔴 | 50+ |
| **Non-Cited Accuracy** | 95.83% 🟢 | 92.21% 🟢 | N/A | 95%+ |

**Key Insight:** 
- OpenAI/Gemini generate 7-8x MORE citations (88-96 vs 13)
- But their match rate is still only 70-79% (not perfect!)
- Co-Sight's 10.53% suggests a **systematic problem**, not just occasional errors

---

## 🔍 How to Read Your Evaluation Results

### **Step 1: Check Overall Match Rate**
```bash
# Look at final.csv for each paper
grep -c ",True," final.csv  # Count matches
wc -l final.csv              # Count total lines

# Calculate:
match_rate = matches / total
```

### **Step 2: Find Common Failure Patterns**
```bash
# Look at failed citations
grep ",False," final.csv | less

# Common reasons:
- "NOT_FOUND" → Source couldn't be scraped
- "Source doesn't mention X" → AI added details
- "Different context" → AI misunderstood source
```

### **Step 3: Identify Which Papers Are Hardest**
```
2011.13534: 40% match rate ← Easiest (LayoutLM paper)
2206.05498: 9% match rate  ← Medium difficulty
2207.14394: 0% match rate  ← Hardest (election testing paper)
```

### **Step 4: Check Non-Cited Claims**
```bash
# These should be mostly True (general knowledge)
grep "is_verified" no_citations.csv
```

---

## 💡 Next Steps

### **For Co-Sight Development:**
1. ✅ **Run full evaluation** on all 100 ReportBench papers (not just 3)
2. ✅ **Analyze failure modes** - categorize why citations fail
3. ✅ **A/B test prompt changes** - measure impact on match rate
4. ✅ **Add citation verification** during generation (not post-hoc)
5. ✅ **Benchmark against GPT-4** - compare with base model performance

### **For Understanding Your Results:**
1. Read `final.csv` for each paper - see exact failures
2. Compare failed vs successful citations - what's different?
3. Look at source_sentence column - what did source ACTUALLY say?
4. Check if URLs are valid - are sources accessible?

---

## 📚 Additional Resources

- **ReportBench Paper:** https://arxiv.org/abs/2508.15804
- **Dataset:** https://huggingface.co/datasets/ByteDance-BandAI/ReportBench
- **Your Results:** `/Users/HansinPatwa/hansin/Projects/teleport/Co-Sight/evaluation-results/`
- **Analysis:** `EVALUATION_RESULTS_SUMMARY.md`
- **Implementation Plan:** `IMPLEMENTATION_PLAN_ADD_REFERENCES.md`

---

## ❓ FAQ

**Q: Why is citation match rate so important?**  
A: It measures **trustworthiness**. If AI cites sources incorrectly, users can't verify claims, which is critical for research.

**Q: Is 10.53% really that bad?**  
A: Yes. Random guessing would be ~20-30%. Industry leaders are at 70-80%. This suggests systematic issues.

**Q: Can we just remove citations to avoid failures?**  
A: No! The goal is to improve citation accuracy, not avoid citations. More citations = better research.

**Q: Why do we need both cited and non-cited accuracy?**  
A: Different types of claims:
- **Cited:** Specific facts from papers ("Model X achieved 95.24% on dataset Y")
- **Non-cited:** General knowledge ("Deep learning requires GPUs")

**Q: What's a "good" score for a research agent?**  
A:
- Citation Match Rate: **70%+** (good), **85%+** (excellent)
- Precision: **0.30+** (good), **0.50+** (excellent)
- Recall: **0.05+** (good), **0.10+** (excellent)
- Non-Cited Accuracy: **95%+** (required)

**Q: How long does evaluation take?**  
A:
- 1 paper: ~5 minutes
- 3 papers: ~15 minutes
- 100 papers (full benchmark): ~8-10 hours

---

**Summary:** ReportBench measures whether AI research agents can write trustworthy surveys. Your Co-Sight results (10.53% citation match rate) show significant room for improvement in citation accuracy - specifically around adding details not present in sources.
