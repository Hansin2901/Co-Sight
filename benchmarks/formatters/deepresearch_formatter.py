"""
Formatter for DeepResearch Bench output format

Expected output format:
{
    "id": "task_id",
    "prompt": "original_question",
    "article": "research_article_with_citations"
}
"""

import re
from app.common.logger_util import logger


def format_deepresearch_output(task_id, question, cosight_result):
    """Format Co-Sight output for DeepResearch Bench evaluation

    Args:
        task_id: Task identifier
        question: Original question/prompt
        cosight_result: Result from CoSight.execute()

    Returns:
        Dict in DeepResearch Bench format
    """
    # Extract the article/report from CoSight result
    # The result should be the final report from finalize_plan
    article = extract_article(cosight_result)

    return {
        "id": task_id,
        "prompt": question,
        "article": article
    }


def extract_article(cosight_result):
    """Extract the research article from CoSight result

    CoSight's execute() returns the result from finalize_plan(),
    which should be the final research report.
    """
    if isinstance(cosight_result, str):
        # If result is already a string, use it directly
        return cosight_result

    elif isinstance(cosight_result, dict):
        # If it's a dict, try to extract the report
        # Common keys: 'report', 'result', 'content', 'output'
        for key in ['report', 'result', 'content', 'output', 'final_report']:
            if key in cosight_result:
                return str(cosight_result[key])

        # If no known key, return the whole dict as string
        logger.warning(f"Could not find standard report key in result: {list(cosight_result.keys())}")
        return str(cosight_result)

    else:
        # For other types, convert to string
        return str(cosight_result)


def validate_citations(article):
    """Check if article contains citations (optional quality check)

    DeepResearch Bench expects citations in the article.
    This is a simple validation to check for citation markers.

    Returns:
        bool: True if citations found
    """
    # Common citation patterns
    citation_patterns = [
        r'\[\d+\]',  # [1], [2], etc.
        r'\(\d{4}\)',  # (2024), etc.
        r'https?://',  # URLs
        r'\[.*?\]\(.*?\)',  # Markdown links
    ]

    for pattern in citation_patterns:
        if re.search(pattern, article):
            return True

    return False


def add_citation_warning(article):
    """Add a warning if no citations were detected (optional)"""
    if not validate_citations(article):
        warning = "\n\n[WARNING: No citations detected in this article. DeepResearch Bench evaluation may be affected.]\n"
        logger.warning(f"No citations detected in article")
        return article + warning
    return article
