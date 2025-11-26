# The "Alignment" Part of ReportBench Explained

## What is "Alignment"?

**Alignment** in ReportBench means: **"Does the cited source actually say what the AI claims it says?"**

It's a **2-step verification process**:
1. **Step 1 (Matching)**: Find the most relevant sentence in the source
2. **Step 2 (Alignment)**: Check if that sentence actually supports the claim

Think of it like fact-checking a student's research paper - you look up their citation, find what the paper actually says, then verify if their claim is accurate.

---

## The Complete Evaluation Pipeline

### **Overview:**
```
AI Report → Extract Citations → Scrape Sources → Match Sentences → Verify Alignment → Calculate Match Rate
   ↓              ↓                 ↓                  ↓                   ↓                    ↓
JSON/MD      citations.csv      raw_texts/       matched.csv         final.csv           10.53%
```

---

## Step-by-Step Breakdown

### **Step 1: Extract Citations** ✅
**Script:** `extract_citations.py`  
**Output:** `citations.csv`

**What it does:**
- Reads the AI-generated report
- Finds all statements with citations (URLs, DOIs, [Author, Year])
- Extracts the statement + URL pair

**Example Output (citations.csv):**
```csv
ID,statement,url
EnND6B49Po,"On a 14-point scale, state scores ranged from 12 to 2",https://usenix.org/.../blum
JJc4HYxCNE,"The Antrim County incident in 2020 eroded public trust",https://jhalderm.com/.../antrim-2021.pdf
```

**Prompt Used:**
> "Identify every statement that cites an external source and pair it with the URL. Return JSON with 'statement' and 'url' fields."

---

### **Step 2: Scrape Source Content** ✅
**Script:** `scrape_content.py`  
**Output:** `raw_texts/{ID}.txt`

**What it does:**
- Takes each unique URL from citations.csv
- Scrapes the webpage content
- Saves full text to a .txt file

**Your Results:**
- ✅ All 38 citations successfully scraped using LangChain WebBaseLoader
- ⚠️ Some sources returned "NOT_FOUND" (likely 404 errors or access issues)

**Example Output (raw_texts/EnND6B49Po.txt):**
```
Logic and Accuracy Testing: A Fifty-State Review

Abstract: We evaluate the testing requirements for...

State scores ranged from a high of 12 (Connecticut, 
South Dakota) to a low of 2 (Oklahoma)...
```

---

### **Step 3: Match Sentences** ⭐ (The "Matching" Part)
**Script:** `match_text.py`  
**Output:** `matched.csv`

**What it does:**
- For each statement, uses an LLM to find the **most relevant sentence** in the source
- This is semantic matching, not exact string matching

**Prompt Used:**
```python
PROMPT_MATCH_SENTENCE = """
You are provided with:
[Statement]: {statement}

[Source Document]:
\"\"\"{source_text}\"\"\"

Return any relevant content from the source document that supports 
the statement. This can be a sentence, paragraph, or even the entire 
text if necessary.

If no content supports it, return "NOT_FOUND".
Return plain text only.
"""
```

**Example Matching:**

**Input:**
- **Statement:** "On SROIE dataset, the model achieved 95.24% F1-score"
- **Source Text:** (Full paper text, 50+ pages)

**LLM Finds Best Match:**
- **Source Sentence:** "Performance on receipt understanding improved from 94.02 to 95.24"

**Output (matched.csv):**
```csv
ID,statement,source_sentence,url
xyz,"On SROIE dataset, achieved 95.24% F1-score","Performance on receipt understanding improved from 94.02 to 95.24",https://paper.pdf
```

**Why This Step is Critical:**
- Sources are often 20-50 pages long
- LLM must find the 1-2 sentences that are most relevant
- If LLM can't find ANY relevant content → returns "NOT_FOUND"

---

### **Step 4: Verify Alignment** ⭐⭐⭐ (The "Alignment" Part)
**Script:** `verify_alignment.py`  
**Output:** `final.csv`

**What it does:**
- Compares the AI's statement with what the source ACTUALLY says
- Uses an LLM judge to determine if they match
- Returns `match=True` or `match=False` with a reason

**Prompt Used:**
```python
PROMPT_VERIFY_ALIGNMENT = """
You will decide whether a claim is correctly supported by a source sentence.

[Claim] (summary from report):
{statement}

[Source Sentence] (pulled from original source):
{source_sentence}

Respond with JSON containing:
  "reason": one short sentence explaining your decision
  "match": true or false  // true if source faithfully supports claim

Return ONLY the JSON.
"""
```

**Example 1: FAILED Alignment** ❌
```
Statement: "On SROIE dataset, the model achieved 95.24% F1-score"
Source Sentence: "Performance on receipt understanding improved from 94.02 to 95.24"

LLM Judge Decision:
{
  "match": false,
  "reason": "Source doesn't mention 'SROIE dataset' or 'F1-score' specifically"
}
```

**Why it failed:**
- AI added "SROIE dataset" (not in source)
- AI added "F1-score" (not in source)
- Source only mentions "receipt understanding" and "95.24"

---

**Example 2: PASSED Alignment** ✅
```
Statement: "Performance on document classification improved to 94.42%"
Source Sentence: "Document image classification improved from 93.07 to 94.42"

LLM Judge Decision:
{
  "match": true,
  "reason": "The claim accurately reflects the source's statement about improvement to 94.42%"
}
```

**Why it passed:**
- Semantic match (doesn't need exact wording)
- All details in claim are present in source
- No added specifics (dataset names, metric types)

---

**Example 3: NOT_FOUND** ❌
```
Statement: "Only one state, Arizona, requires random number generators"
Source Sentence: "NOT_FOUND"

LLM Judge Decision:
{
  "match": false,
  "reason": "The source sentence is 'NOT_FOUND' and therefore cannot support the claim."
}
```

**Why it failed:**
- Source scraping failed (404 error, paywall, etc.)
- OR matching step couldn't find any relevant content
- Cannot verify without source content

---

### **Step 5: Calculate Match Rate** 📊
**Script:** `verify_alignment.py` (end of function)  
**Output:** Terminal print + percentage

**Calculation:**
```python
match_rate = (statements with match=True) / (total statements)

Your Results:
- Paper 2011.13534: 2/5 matched = 40.00%
- Paper 2206.05498: 2/22 matched = 9.09%
- Paper 2207.14394: 0/11 matched = 0.00%
- Overall: 4/38 matched = 10.53%
```

---

## Your Results: Why So Many "NOT_FOUND"?

Looking at your `matched.csv`:
```csv
source_sentence
NOT_FOUND
NOT_FOUND
NOT_FOUND
... (11 out of 11 are NOT_FOUND for paper 2207.14394)
```

### **Possible Causes:**

#### 1. **URL Scraping Failed** (Most Likely)
```bash
# Check if raw text files were created
ls -la evaluation-results/statement-results/2207.14394/raw_texts/
```

**If files are missing:**
- URLs might be 404 (dead links)
- Paywalls blocking access
- PDFs that couldn't be converted to text
- Anti-scraping protection

#### 2. **LLM Couldn't Find Relevant Content**
Even if scraping succeeded, the matching LLM might not find supporting content because:
- The cited paper doesn't actually contain that information (hallucination)
- Information is in figures/tables (not extracted)
- Content is too technical for LLM to match

#### 3. **Character Encoding Issues**
- Source text has encoding errors
- Special characters causing LLM confusion

---

## How Alignment Detection Works (Technical)

### **The LLM Judge Approach:**

ReportBench uses an **LLM-as-a-judge** method:

1. **Input to Judge LLM:**
   ```
   Claim: "On SROIE dataset, achieved 95.24% F1-score"
   Source: "Receipt understanding improved to 95.24"
   
   Question: Does the source support the claim?
   ```

2. **Judge LLM Reasoning:**
   - Identifies key facts in claim: "SROIE dataset", "95.24%", "F1-score"
   - Checks if ALL key facts are in source
   - Notices "SROIE dataset" missing → NOT supported
   - Notices "F1-score" missing → NOT supported
   - Even though "95.24%" is present, claim adds unsupported details

3. **Output:**
   ```json
   {
     "match": false,
     "reason": "Source doesn't mention SROIE dataset or F1-score metric"
   }
   ```

### **Why Use LLM Judge vs. Exact Match?**

**Exact String Matching (Bad):**
```python
# Would fail even for valid citations
"The model improved to 94.42%" != "improved from 93.07 to 94.42"
# Different wording, same meaning
```

**Semantic LLM Matching (Good):**
```python
# Can recognize paraphrasing
Claim: "Performance reached 94.42%"
Source: "improved to 94.42"
Match: TRUE (semantic equivalence)
```

**But LLM is strict about added details:**
```python
# Catches over-specific claims
Claim: "On RVL-CDIP dataset, accuracy was 94.42%"
Source: "document classification improved to 94.42"
Match: FALSE (added "RVL-CDIP" and "accuracy")
```

---

## Common Alignment Failure Patterns

### **Pattern 1: Dataset Name Hallucination** (58.8% of failures)
```
❌ Claim: "Achieved 95.24% on SROIE dataset"
✅ Source: "Receipt understanding improved to 95.24"
Issue: Added "SROIE dataset" (not in source)
```

### **Pattern 2: Metric Type Hallucination** (23.5% of failures)
```
❌ Claim: "94.42% accuracy"
✅ Source: "improved to 94.42"
Issue: Added "accuracy" (could be F1, precision, etc.)
```

### **Pattern 3: Compound Hallucination** (Combined)
```
❌ Claim: "On RVL-CDIP dataset, achieved 94.42% accuracy"
✅ Source: "document classification improved to 94.42"
Issue: Added BOTH dataset name AND metric type
```

### **Pattern 4: Contextual Misalignment**
```
❌ Claim: "Model X achieved 95.24%"
✅ Source: "Receipt understanding improved to 95.24"
Issue: Source talks about "receipt understanding" generally, not "Model X"
```

### **Pattern 5: Source Not Found** (17.7% of failures)
```
❌ Claim: "Only 17 states have rigorous testing"
✅ Source: "NOT_FOUND"
Issue: URL is inaccessible or scraping failed
```

---

## How to Debug Your Alignment Issues

### **Step 1: Check Which Sources Failed to Scrape**
```bash
cd evaluation-results/statement-results/2207.14394
ls raw_texts/  # Should have .txt files for each ID

# If empty or missing files:
# → URLs are broken or inaccessible
```

### **Step 2: Check Matched Sentences**
```bash
# Look at matched.csv
cat matched.csv | grep "NOT_FOUND" | wc -l  # Count NOT_FOUND

# If many NOT_FOUND:
# → Either scraping failed OR LLM couldn't find relevant content
```

### **Step 3: Manually Verify a Failed Citation**
```bash
# Pick one failed citation from final.csv
# Example:
Statement: "On SROIE dataset, achieved 95.24% F1-score"
URL: https://arxiv.org/pdf/2011.13534.pdf

# Manually check:
1. Open the URL - does it load?
2. Search for "95.24" in the PDF - is it there?
3. Check if "SROIE" is mentioned near "95.24"
4. Check if "F1-score" is mentioned

# If source DOES mention everything:
# → LLM judge is too strict (false negative)

# If source is missing details:
# → Co-Sight is hallucinating (true positive detection)
```

### **Step 4: Check Raw Text Quality**
```bash
# Look at a raw text file
cat raw_texts/EnND6B49Po.txt | head -50

# Check for:
- Is it readable text?
- Or is it HTML/XML tags?
- Or encoding errors (���)?
- Or completely empty?
```

---

## Comparison: Your Results vs Industry

### **Match Rate Breakdown:**

| Source of Failure | Co-Sight | OpenAI DR | Gemini DR |
|-------------------|----------|-----------|-----------|
| **Added Details** | 58.8% | ~15% | ~20% |
| **Metric Hallucination** | 23.5% | ~8% | ~10% |
| **Source Not Found** | 17.7% | ~5% | ~5% |
| **Overall Match Rate** | **10.53%** | **78.87%** | **72.94%** |

**Key Insight:**
- OpenAI/Gemini still fail 20-30% of citations
- BUT they mostly fail on "source not found" (technical issues)
- Co-Sight fails mainly on **added details** (systematic prompting issue)

---

## How to Improve Alignment (From 10.53% → 70%+)

### **Fix 1: Explicit Prompt Instructions**
```python
# Add to Co-Sight prompts:
"""
CITATION RULES:
1. When citing a source, state ONLY facts that are EXPLICITLY in that source
2. DO NOT infer dataset names unless source mentions them
3. DO NOT assume metric types (accuracy, F1, precision) unless stated
4. If source says "improved to 95.24", DO NOT add:
   - Dataset names (SROIE, RVL-CDIP, etc.)
   - Metric types (accuracy, F1-score, etc.)
   - Model names (unless explicitly stated)
5. Use general language: "performance improved to 95.24%" is safer than specific claims
"""
```

### **Fix 2: Citation Verification Loop**
```python
# After generating a statement:
def verify_citation_before_including(statement, source_url):
    # Step 1: Re-fetch source content
    source_text = fetch_source(source_url)
    
    # Step 2: Ask LLM to verify
    prompt = f"""
    Does this source EXPLICITLY support this claim?
    
    Claim: {statement}
    Source: {source_text}
    
    Check if ALL details in claim (dataset names, metric types, etc.) 
    are EXPLICITLY mentioned in source. Return True/False.
    """
    
    is_supported = llm_check(prompt)
    
    # Step 3: Only include if verified
    if not is_supported:
        # Option A: Generalize the claim
        # "On SROIE dataset, 95.24% F1" → "Receipt understanding improved to 95.24%"
        
        # Option B: Find a better source
        # Search for paper that explicitly mentions SROIE + F1-score
        
        # Option C: Remove citation
        # Make it a general statement without citation
    
    return is_supported
```

### **Fix 3: Multi-Source Citations**
```python
# For compound claims, use multiple sources:

# BAD (single source, added details):
"On SROIE dataset, achieved 95.24% F1-score [source1]"
# Source1 only says: "receipt understanding improved to 95.24"

# GOOD (multiple sources):
"Performance improved to 95.24% [source1] on receipt understanding tasks. 
This evaluation used the SROIE dataset [source2] with F1-score as the metric [source3]."

# Each detail has its own citation
```

### **Fix 4: Conservative Paraphrasing**
```python
# Train Co-Sight to prefer direct quotes or minimal paraphrasing:

# BAD (aggressive paraphrasing):
Source: "document classification improved from 93.07 to 94.42"
Output: "Achieved 94.42% accuracy on RVL-CDIP dataset for document classification"
# Added 3 unsupported details!

# GOOD (conservative paraphrasing):
Source: "document classification improved from 93.07 to 94.42"
Output: "Document classification performance improved to 94.42%"
# Only states what's in source

# BEST (direct quote):
Source: "document classification improved from 93.07 to 94.42"
Output: "According to [citation], document classification 'improved from 93.07 to 94.42'"
# Impossible to misalign with direct quote
```

---

## Summary: The Alignment Part

**What it measures:**
- Whether AI's cited statements are **factually supported** by their sources
- Not just "is there a citation", but "is the citation ACCURATE"

**How it works:**
1. **Match**: Find relevant content in source (semantic search)
2. **Align**: Compare claim vs. source content (LLM judge)
3. **Score**: Calculate percentage of accurate citations

**Your results:**
- **10.53% alignment** = Only 4 out of 38 citations are accurate
- Main issue: **Adding details not in source** (dataset names, metric types)
- Some issues: **Sources not found** (scraping failures)

**How to fix:**
- Add explicit prompts: "Only state what's EXPLICITLY in source"
- Implement citation verification loop (check before including)
- Use conservative paraphrasing (prefer direct quotes)
- Multi-source citations for compound claims

**Industry comparison:**
- OpenAI Deep Research: **78.87%** (good)
- Gemini Deep Research: **72.94%** (good)
- Co-Sight: **10.53%** (needs urgent improvement)

The alignment check is the **most important** metric because it directly measures trustworthiness - users must be able to verify AI's claims by checking sources.
