"""
Evaluation harness for golden tasks.
"""

from .runner import GoldenTaskRunner, TaskResult, GoldenTask
from .scorer import TaskScorer, generate_scorecard

__all__ = [
    'GoldenTaskRunner',
    'TaskResult',
    'GoldenTask', 
    'TaskScorer',
    'generate_scorecard'
]