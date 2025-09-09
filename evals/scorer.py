"""
Task scorer - evaluates task results against assertions.
"""
from __future__ import annotations

import sys
from pathlib import Path
import re
from typing import Dict, Any, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentic_ai.infra.trace import TraceEvent

# Forward declarations to avoid circular imports
class TaskResult:
    pass

class GoldenTask:
    pass

class TaskAssertion:
    pass


class TaskScorer:
    """Evaluates task results against golden task assertions"""
    
    def __init__(self):
        self.assertion_handlers = {
            'must_include': self._check_must_include,
            'must_not_include': self._check_must_not_include,
            'max_tokens': self._check_max_tokens,
            'min_tokens': self._check_min_tokens,
            'tool_used': self._check_tool_used,
            'has_structure': self._check_has_structure,
            'no_fabrication': self._check_no_fabrication,
            'node_sequence': self._check_node_sequence,
        }
    
    def score_task(self, task: GoldenTask, result: TaskResult) -> Dict[str, Any]:
        """Score a task result against its assertions"""
        assertion_results = {}
        total_score = 0.0
        max_score = len(task.assertions)
        
        for assertion in task.assertions:
            assertion_result = self._evaluate_assertion(assertion, result)
            assertion_results[f"{assertion.type}_{hash(assertion.description)}"] = assertion_result
            
            if assertion_result['passed']:
                total_score += 1.0
                
        return {
            'task_id': task.id,
            'overall_score': total_score / max_score if max_score > 0 else 1.0,
            'passed_assertions': int(total_score),
            'total_assertions': max_score,
            'passed': total_score == max_score,
            'assertion_results': assertion_results
        }
    
    def _evaluate_assertion(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Evaluate a single assertion"""
        handler = self.assertion_handlers.get(assertion.type)
        if not handler:
            return {
                'passed': False,
                'error': f"Unknown assertion type: {assertion.type}",
                'description': assertion.description
            }
        
        try:
            return handler(assertion, result)
        except Exception as e:
            return {
                'passed': False,
                'error': f"Assertion evaluation failed: {str(e)}",
                'description': assertion.description
            }
    
    def _check_must_include(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if response includes required terms"""
        required_terms = assertion.value if isinstance(assertion.value, list) else [assertion.value]
        response_lower = result.response.lower()
        
        found_terms = []
        missing_terms = []
        
        for term in required_terms:
            if term.lower() in response_lower:
                found_terms.append(term)
            else:
                missing_terms.append(term)
        
        # Pass if at least one term is found
        passed = len(found_terms) > 0
        
        return {
            'passed': passed,
            'found_terms': found_terms,
            'missing_terms': missing_terms,
            'description': assertion.description
        }
    
    def _check_must_not_include(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if response excludes forbidden terms"""
        forbidden_terms = assertion.value if isinstance(assertion.value, list) else [assertion.value]
        response_lower = result.response.lower()
        
        found_forbidden = []
        for term in forbidden_terms:
            if term.lower() in response_lower:
                found_forbidden.append(term)
        
        passed = len(found_forbidden) == 0
        
        return {
            'passed': passed,
            'found_forbidden': found_forbidden,
            'description': assertion.description
        }
    
    def _check_max_tokens(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if response is within max token limit"""
        # Rough token estimation: ~4 chars per token
        estimated_tokens = len(result.response) // 4
        max_tokens = int(assertion.value)
        
        passed = estimated_tokens <= max_tokens
        
        return {
            'passed': passed,
            'estimated_tokens': estimated_tokens,
            'max_tokens': max_tokens,
            'description': assertion.description
        }
    
    def _check_min_tokens(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if response meets minimum token requirement"""
        # Rough token estimation: ~4 chars per token
        estimated_tokens = len(result.response) // 4
        min_tokens = int(assertion.value)
        
        passed = estimated_tokens >= min_tokens
        
        return {
            'passed': passed,
            'estimated_tokens': estimated_tokens,
            'min_tokens': min_tokens,
            'description': assertion.description
        }
    
    def _check_tool_used(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if a specific tool was used"""
        expected_tool = assertion.value
        used_tools = set()
        
        # Extract tool usage from trace events
        for event in result.trace_events:
            if event.event_type == 'tool_request':
                tool_name = event.data.get('tool_name')
                if tool_name:
                    used_tools.add(tool_name)
        
        passed = expected_tool in used_tools
        
        return {
            'passed': passed,
            'expected_tool': expected_tool,
            'used_tools': list(used_tools),
            'description': assertion.description
        }
    
    def _check_has_structure(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if response has structural elements (lists, sections, etc.)"""
        response = result.response
        
        # Look for structural indicators
        structure_indicators = [
            r'\n\s*[-*]\s+',  # Bullet points
            r'\n\s*\d+\.\s+',  # Numbered lists
            r'\n#{1,3}\s+',    # Headers
            r'\n\s*\w+:\s*\n', # Section labels
            r'\n\n',           # Paragraph breaks
        ]
        
        found_structures = []
        for pattern in structure_indicators:
            if re.search(pattern, response):
                found_structures.append(pattern)
        
        # Pass if at least 2 structural elements found
        passed = len(found_structures) >= 2
        
        return {
            'passed': passed,
            'structure_count': len(found_structures),
            'found_structures': found_structures,
            'description': assertion.description
        }
    
    def _check_no_fabrication(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check for common fabrication patterns"""
        response = result.response.lower()
        
        # Common fabrication indicators
        fabrication_patterns = [
            r'here.s the result: \d+',  # Making up specific numbers
            r'according to.*sources?',   # Fake citations
            r'studies? show',           # Vague authority claims
            r'http[s]?://[^\s]+',       # URLs (likely fabricated if not from web search)
        ]
        
        fabrication_matches = []
        for pattern in fabrication_patterns:
            matches = re.findall(pattern, response)
            if matches:
                fabrication_matches.extend(matches)
        
        # For math errors, check if tool returned error but response claims success
        tool_errors = []
        for event in result.trace_events:
            if event.event_type == 'tool_response' and event.data.get('error'):
                tool_errors.append(event.data['error'])
        
        # If tool had error but response doesn't acknowledge it, likely fabrication
        has_tool_error = len(tool_errors) > 0
        acknowledges_error = any(keyword in response for keyword in ['error', 'cannot', 'unable', 'failed'])
        
        fabrication_likely = (len(fabrication_matches) > 0) or (has_tool_error and not acknowledges_error)
        
        passed = not fabrication_likely
        
        return {
            'passed': passed,
            'fabrication_patterns_found': fabrication_matches,
            'tool_errors': tool_errors,
            'acknowledges_error': acknowledges_error,
            'description': assertion.description
        }
    
    def _check_node_sequence(self, assertion: TaskAssertion, result: TaskResult) -> Dict[str, Any]:
        """Check if specific nodes were executed in sequence"""
        expected_sequence = assertion.value
        actual_sequence = []
        
        # Extract node sequence from trace events
        for event in result.trace_events:
            if event.event_type == 'node_start':
                actual_sequence.append(event.node_name)
        
        # Check if expected sequence appears in actual sequence
        sequence_found = False
        if len(expected_sequence) <= len(actual_sequence):
            for i in range(len(actual_sequence) - len(expected_sequence) + 1):
                if actual_sequence[i:i+len(expected_sequence)] == expected_sequence:
                    sequence_found = True
                    break
        
        return {
            'passed': sequence_found,
            'expected_sequence': expected_sequence,
            'actual_sequence': actual_sequence,
            'description': assertion.description
        }


def generate_scorecard(task_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate overall scorecard from task scores"""
    if not task_scores:
        return {
            'overall_pass_rate': 0.0,
            'total_tasks': 0,
            'passed_tasks': 0,
            'failed_tasks': 0,
            'task_details': []
        }
    
    passed_tasks = [score for score in task_scores if score['passed']]
    failed_tasks = [score for score in task_scores if not score['passed']]
    
    return {
        'overall_pass_rate': len(passed_tasks) / len(task_scores),
        'total_tasks': len(task_scores),
        'passed_tasks': len(passed_tasks),
        'failed_tasks': len(failed_tasks),
        'average_score': sum(score['overall_score'] for score in task_scores) / len(task_scores),
        'task_details': task_scores
    }