"""Check functions for evaluating task outputs."""

from __future__ import annotations

import re
from typing import List, Dict, Any
from urllib.parse import urlparse


def contains_facts(output: str, required_facts: List[str]) -> tuple[bool, str]:
    """Check if output contains all required facts (case insensitive).
    
    Returns:
        (success, reason)
    """
    output_lower = output.lower()
    missing_facts = []
    
    for fact in required_facts:
        if fact.lower() not in output_lower:
            missing_facts.append(fact)
    
    if missing_facts:
        return False, f"Missing facts: {', '.join(missing_facts)}"
    
    return True, "All required facts present"


def has_citations(output: str) -> tuple[bool, str]:
    """Check if output contains valid URLs as citations."""
    # Look for URLs in the text
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, output)
    
    if not urls:
        return False, "No URLs found in output"
    
    # Validate URLs
    valid_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                valid_urls.append(url)
        except Exception:
            continue
    
    if not valid_urls:
        return False, "No valid URLs found"
    
    return True, f"Found {len(valid_urls)} valid citations"


def min_length(output: str, min_chars: int) -> tuple[bool, str]:
    """Check if output meets minimum length requirement."""
    actual_length = len(output.strip())
    
    if actual_length < min_chars:
        return False, f"Output too short: {actual_length} chars (minimum: {min_chars})"
    
    return True, f"Length requirement met: {actual_length} chars"


def contains_email_structure(output: str) -> tuple[bool, str]:
    """Check if output contains basic email structure."""
    output_lower = output.lower()
    
    # Look for email indicators
    email_indicators = [
        "subject:",
        "dear",
        "hi",
        "hello",
        "regards",
        "sincerely",
        "best",
        "thank you"
    ]
    
    found_indicators = [ind for ind in email_indicators if ind in output_lower]
    
    if len(found_indicators) < 2:
        return False, f"Missing email structure elements. Found: {found_indicators}"
    
    return True, f"Email structure detected with elements: {found_indicators}"


def professional_tone(output: str) -> tuple[bool, str]:
    """Check if output maintains a professional tone."""
    output_lower = output.lower()
    
    # Professional indicators
    professional_words = [
        "professional", "services", "expertise", "experience", 
        "solutions", "consultation", "pleased", "opportunity"
    ]
    
    # Unprofessional indicators
    unprofessional_words = [
        "awesome", "cool", "hey", "sup", "lol", "omg", "gonna", "wanna"
    ]
    
    professional_count = sum(1 for word in professional_words if word in output_lower)
    unprofessional_count = sum(1 for word in unprofessional_words if word in output_lower)
    
    if unprofessional_count > 0:
        return False, f"Contains unprofessional language: {unprofessional_count} instances"
    
    if professional_count == 0:
        return False, "No professional language indicators found"
    
    return True, f"Professional tone maintained with {professional_count} indicators"


def has_calculation(output: str) -> tuple[bool, str]:
    """Check if output contains numerical calculations."""
    # Look for calculation patterns
    calc_patterns = [
        r'\d+\s*[×x*]\s*\d+',  # multiplication
        r'\d+\s*[+]\s*\d+',    # addition
        r'\d+\s*[-]\s*\d+',    # subtraction
        r'\d+\s*[/÷]\s*\d+',   # division
        r'=\s*\$?\d+',         # equals result
        r'total[:\s]*\$?\d+',  # total calculation
    ]
    
    for pattern in calc_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return True, f"Calculation found matching pattern: {pattern}"
    
    return False, "No calculation patterns found"


def contains_currency(output: str) -> tuple[bool, str]:
    """Check if output contains currency amounts."""
    # Look for currency patterns
    currency_patterns = [
        r'\$\d+',              # $100
        r'\d+\s*dollars?',     # 100 dollars
        r'\d+\s*USD',          # 100 USD
        r'price[:\s]*\$?\d+',  # price: $100
    ]
    
    for pattern in currency_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return True, f"Currency amount found"
    
    return False, "No currency amounts found"


def uses_kb_search(output: str, trace_events: List[Dict] = None) -> tuple[bool, str]:
    """Check if knowledge base search was used (requires trace data)."""
    if not trace_events:
        # Fallback: look for KB-related content
        kb_indicators = ["knowledge base", "internal", "database", "stored"]
        for indicator in kb_indicators:
            if indicator.lower() in output.lower():
                return True, "KB usage inferred from content"
        return False, "No trace data and no KB indicators in content"
    
    # Check trace events for KB search
    for event in trace_events:
        if event.get("tool") == "kb_search":
            return True, "KB search tool used"
    
    return False, "No KB search found in trace"


def multi_step_plan(output: str, trace_events: List[Dict] = None) -> tuple[bool, str]:
    """Check if output shows evidence of multi-step planning."""
    if trace_events:
        # Count unique nodes executed
        nodes = set()
        for event in trace_events:
            if event.get("node"):
                nodes.add(event["node"])
        
        if len(nodes) >= 4:  # plan, decide, act, reflect minimum
            return True, f"Multi-step execution with {len(nodes)} nodes"
    
    # Fallback: look for planning language
    plan_indicators = [
        "first", "then", "next", "finally", "step", "approach", 
        "strategy", "plan", "process", "workflow"
    ]
    
    found_indicators = sum(1 for indicator in plan_indicators 
                          if indicator.lower() in output.lower())
    
    if found_indicators >= 3:
        return True, f"Planning language detected: {found_indicators} indicators"
    
    return False, "No evidence of multi-step planning"


def comparative_structure(output: str) -> tuple[bool, str]:
    """Check if output has comparative analysis structure."""
    comparative_words = [
        "compared to", "versus", "vs", "while", "whereas", 
        "on the other hand", "in contrast", "however", 
        "difference", "similar", "unlike", "both"
    ]
    
    found_comparative = [word for word in comparative_words 
                        if word.lower() in output.lower()]
    
    if len(found_comparative) < 2:
        return False, f"Insufficient comparative structure. Found: {found_comparative}"
    
    return True, f"Comparative structure detected: {found_comparative}"


# Registry of all available checks
CHECK_FUNCTIONS = {
    'contains_facts': contains_facts,
    'has_citations': has_citations,
    'min_length': min_length,
    'contains_email_structure': contains_email_structure,
    'professional_tone': professional_tone,
    'has_calculation': has_calculation,
    'contains_currency': contains_currency,
    'uses_kb_search': uses_kb_search,
    'multi_step_plan': multi_step_plan,
    'comparative_structure': comparative_structure,
}