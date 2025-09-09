"""
Pytest integration for golden task evaluation.
"""
import asyncio
import pytest
from pathlib import Path

from evals.runner import GoldenTaskRunner
from evals.scorer import generate_scorecard


class TestGoldenTasks:
    """Test suite for golden task evaluation"""
    
    @pytest.fixture(scope="class")
    def runner(self):
        """Create task runner fixture"""
        return GoldenTaskRunner()
    
    @pytest.fixture(scope="class")
    def task_results(self, runner):
        """Run all golden tasks and return results"""
        async def run_tasks():
            return await runner.run_all_tasks()
        
        return asyncio.run(run_tasks())
    
    @pytest.fixture(scope="class") 
    def scorecard(self, runner, task_results):
        """Generate scorecard from task results"""
        task_scores = []
        tasks = runner.load_tasks()
        
        for result in task_results:
            task = next((t for t in tasks if t.id == result.task_id), None)
            if task:
                task_score = runner.scorer.score_task(task, result)
                task_scores.append(task_score)
                
        return generate_scorecard(task_scores)
    
    def test_overall_pass_rate(self, scorecard):
        """Test that overall pass rate meets minimum threshold"""
        minimum_pass_rate = 0.6  # 60% pass rate required
        
        assert scorecard['overall_pass_rate'] >= minimum_pass_rate, (
            f"Overall pass rate {scorecard['overall_pass_rate']:.1%} is below minimum "
            f"{minimum_pass_rate:.1%}. Failed tasks: {scorecard['failed_tasks']}"
        )
    
    def test_basic_greeting_task(self, task_results):
        """Test that basic greeting task passes"""
        greeting_result = next(
            (r for r in task_results if r.task_id == "basic-greeting"), 
            None
        )
        
        assert greeting_result is not None, "Basic greeting task not found"
        assert greeting_result.success, f"Basic greeting failed: {greeting_result.error}"
        assert len(greeting_result.response) > 0, "Empty response"
    
    def test_calculation_task(self, task_results):
        """Test that calculation task uses tools correctly"""
        calc_result = next(
            (r for r in task_results if r.task_id == "simple-calculation"),
            None
        )
        
        assert calc_result is not None, "Calculation task not found"
        
        # Check if calculator tool was used
        tool_events = [
            e for e in calc_result.trace_events 
            if e.event_type == 'tool_request' and e.data.get('tool_name') == 'calculator'
        ]
        
        assert len(tool_events) > 0, "Calculator tool was not used"
        assert calc_result.success, f"Calculation task failed: {calc_result.error}"
    
    def test_no_task_timeouts(self, task_results):
        """Test that no tasks timed out"""
        timeout_results = [r for r in task_results if r.error and "timed out" in r.error]
        
        assert len(timeout_results) == 0, (
            f"Tasks timed out: {[r.task_id for r in timeout_results]}"
        )
    
    def test_trace_generation(self, task_results):
        """Test that all tasks generated traces"""
        for result in task_results:
            if result.success:  # Only check successful tasks
                assert len(result.trace_events) > 0, (
                    f"Task {result.task_id} generated no trace events"
                )
                
                # Check for essential events
                event_types = {e.event_type for e in result.trace_events}
                assert 'run_start' in event_types, f"Task {result.task_id} missing run_start event"
                assert 'run_end' in event_types, f"Task {result.task_id} missing run_end event"
    
    def test_print_scorecard(self, scorecard, task_results):
        """Print detailed scorecard for debugging"""
        print(f"\n{'='*50}")
        print("GOLDEN TASK EVALUATION SCORECARD")
        print(f"{'='*50}")
        print(f"Overall Pass Rate: {scorecard['overall_pass_rate']:.1%}")
        print(f"Tasks Passed: {scorecard['passed_tasks']}/{scorecard['total_tasks']}")
        print(f"Average Score: {scorecard['average_score']:.2f}")
        
        print(f"\nTask Details:")
        print("-" * 50)
        
        for result in task_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {result.task_id}")
            print(f"  Duration: {result.duration_seconds:.1f}s")
            print(f"  Response length: {len(result.response)} chars")
            print(f"  Trace events: {len(result.trace_events)}")
            
            if result.error:
                print(f"  Error: {result.error}")
            else:
                # Show assertion results
                passed_assertions = sum(
                    1 for r in result.assertion_results.values() 
                    if r.get('passed', False)
                )
                total_assertions = len(result.assertion_results)
                print(f"  Assertions: {passed_assertions}/{total_assertions} passed")
                
                for assertion_key, assertion_result in result.assertion_results.items():
                    assertion_status = "✓" if assertion_result.get('passed', False) else "✗"
                    description = assertion_result.get('description', 'Unknown assertion')
                    print(f"    {assertion_status} {description}")
            
            print()
        
        # This test always passes - it's just for printing
        assert True


# Standalone function for CLI usage
def run_golden_tests():
    """Run golden tests from CLI"""
    pytest.main([__file__, '-v', '-s'])


if __name__ == "__main__":
    run_golden_tests()