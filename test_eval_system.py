#!/usr/bin/env python3
"""
Test the evaluation system without requiring API keys.
"""

import sys
sys.path.insert(0, 'src')

from evals.runner import GoldenTaskRunner
from evals.scorer import TaskScorer, generate_scorecard
from pathlib import Path
import yaml
import asyncio

def test_task_loading():
    """Test that tasks can be loaded from YAML files"""
    runner = GoldenTaskRunner()
    tasks = runner.load_tasks()
    
    print(f"✓ Loaded {len(tasks)} golden tasks:")
    for task in tasks:
        print(f"  - {task.id}: {task.description}")
        print(f"    {len(task.assertions)} assertions, {len(task.tags)} tags")
    
    assert len(tasks) >= 3, "Should have at least 3 golden tasks"
    return tasks

def test_scorer_logic():
    """Test scorer logic with mock data"""
    from evals.runner import TaskResult, GoldenTask, TaskAssertion
    from agentic_ai.infra.trace import TraceEvent
    
    scorer = TaskScorer()
    
    # Create a mock task
    task = GoldenTask(
        id="test-task",
        description="Test task",
        prompt="Test prompt", 
        timeout_seconds=60,
        expected_behavior="test",
        assertions=[
            TaskAssertion(type="must_include", value=["hello", "test"], description="Should include greeting"),
            TaskAssertion(type="max_tokens", value=100, description="Should be concise"),
            TaskAssertion(type="tool_used", value="calculator", description="Should use calculator")
        ],
        tags=["test"]
    )
    
    # Create mock trace events
    trace_events = [
        TraceEvent(
            event_type="tool_request",
            timestamp=0.0,
            node_name="tools",
            event_id="test1",
            chat_id="test",
            run_id="test", 
            data={"tool_name": "calculator", "args": {"expression": "2+2"}}
        ),
        TraceEvent(
            event_type="tool_response", 
            timestamp=0.1,
            node_name="tools",
            event_id="test2",
            chat_id="test",
            run_id="test",
            data={"tool_name": "calculator", "result": "4"},
            duration_ms=100.0
        )
    ]
    
    # Create mock result
    result = TaskResult(
        task_id="test-task",
        chat_id="test", 
        run_id="test",
        success=True,
        response="Hello! I used the test calculator to compute 2+2=4.",
        duration_seconds=1.5,
        trace_events=trace_events,
        assertion_results={},
        error=None
    )
    
    # Score the task
    score = scorer.score_task(task, result)
    
    print(f"✓ Scorer test results:")
    print(f"  Overall score: {score['overall_score']:.2f}")
    print(f"  Passed: {score['passed']}")
    print(f"  Assertions: {score['passed_assertions']}/{score['total_assertions']}")
    
    # Check individual assertions
    for key, assertion_result in score['assertion_results'].items():
        status = "✓" if assertion_result['passed'] else "✗"
        print(f"    {status} {assertion_result['description']}")
    
    assert score['overall_score'] > 0.5, "Should have reasonable score"
    return score

def test_scorecard_generation():
    """Test scorecard generation"""
    # Mock task scores
    task_scores = [
        {'task_id': 'task1', 'passed': True, 'overall_score': 1.0},
        {'task_id': 'task2', 'passed': True, 'overall_score': 0.8},
        {'task_id': 'task3', 'passed': False, 'overall_score': 0.4},
    ]
    
    scorecard = generate_scorecard(task_scores)
    
    print(f"✓ Scorecard test:")
    print(f"  Pass rate: {scorecard['overall_pass_rate']:.1%}")
    print(f"  Total tasks: {scorecard['total_tasks']}")
    print(f"  Passed: {scorecard['passed_tasks']}")
    print(f"  Failed: {scorecard['failed_tasks']}")
    print(f"  Average score: {scorecard['average_score']:.2f}")
    
    assert scorecard['overall_pass_rate'] == 2/3, "Pass rate should be 2/3"
    assert scorecard['total_tasks'] == 3, "Should have 3 tasks"
    
    return scorecard

def main():
    """Run all tests"""
    print("Testing evaluation system components...")
    print("=" * 50)
    
    try:
        tasks = test_task_loading()
        print()
        
        score = test_scorer_logic() 
        print()
        
        scorecard = test_scorecard_generation()
        print()
        
        print("✅ All evaluation system tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)