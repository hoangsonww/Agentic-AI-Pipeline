"""
Golden task runner - executes evaluation tasks against the agent.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

import yaml
# Import graph dynamically to avoid API key issues during import
from agentic_ai.infra.trace import trace_run, read_trace, TraceEvent
from agentic_ai.config import settings
from .scorer import TaskScorer, generate_scorecard


@dataclass
class TaskAssertion:
    """Single assertion in a task"""
    type: str
    value: Any
    description: str


@dataclass 
class GoldenTask:
    """Golden task definition"""
    id: str
    description: str
    prompt: str
    timeout_seconds: int
    expected_behavior: str
    assertions: List[TaskAssertion]
    tags: List[str]


@dataclass
class TaskResult:
    """Result of executing a task"""
    task_id: str
    chat_id: str
    run_id: str
    success: bool
    response: str
    duration_seconds: float
    trace_events: List[TraceEvent]
    assertion_results: Dict[str, Dict[str, Any]]
    error: Optional[str] = None


class GoldenTaskRunner:
    """Executes golden tasks and collects results"""
    
    def __init__(self, tasks_dir: Path = Path("evals/golden")):
        self.tasks_dir = tasks_dir
        self.results: List[TaskResult] = []
        self.scorer = TaskScorer()
        
    def load_tasks(self, task_filter: Optional[str] = None) -> List[GoldenTask]:
        """Load golden tasks from YAML files"""
        tasks = []
        
        for yaml_file in self.tasks_dir.glob("*.yaml"):
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Skip if filter provided and doesn't match
            if task_filter and task_filter not in data.get('id', ''):
                continue
                
            # Parse assertions
            assertions = []
            for assertion_data in data.get('assertions', []):
                assertions.append(TaskAssertion(
                    type=assertion_data['type'],
                    value=assertion_data['value'],
                    description=assertion_data['description']
                ))
            
            task = GoldenTask(
                id=data['id'],
                description=data['description'],
                prompt=data['prompt'],
                timeout_seconds=data.get('timeout_seconds', 60),
                expected_behavior=data.get('expected_behavior', 'default'),
                assertions=assertions,
                tags=data.get('tags', [])
            )
            tasks.append(task)
            
        return sorted(tasks, key=lambda t: t.id)
    
    async def run_task(self, task: GoldenTask) -> TaskResult:
        """Execute a single golden task"""
        chat_id = f"eval_{task.id}_{int(time.time())}"
        run_id = str(uuid.uuid4())[:8]
        
        # Enable tracing for evaluation runs
        original_trace_setting = settings.ENABLE_TRACING
        settings.ENABLE_TRACING = True
        
        start_time = time.time()
        response_chunks = []
        trace_events = []
        error = None
        
        try:
            # Import here to avoid API key issues during module import
            from agentic_ai.graph import run_chat
            
            # Run the task with tracing
            with trace_run(chat_id, run_id) as tracer:
                async def collect_response():
                    async for chunk in run_chat(chat_id, task.prompt):
                        response_chunks.append(chunk)
                        
                # Run with timeout
                await asyncio.wait_for(
                    collect_response(), 
                    timeout=task.timeout_seconds
                )
                
                # Read the trace
                if tracer:
                    trace_events = read_trace(tracer.trace_file)
                    
        except asyncio.TimeoutError:
            error = f"Task timed out after {task.timeout_seconds} seconds"
        except Exception as e:
            error = f"Task failed with error: {str(e)}"
        finally:
            # Restore original tracing setting
            settings.ENABLE_TRACING = original_trace_setting
            
        duration_seconds = time.time() - start_time
        response = ''.join(response_chunks)
        
        # Score the task result
        task_score = self.scorer.score_task(task, TaskResult(
            task_id=task.id,
            chat_id=chat_id, 
            run_id=run_id,
            success=error is None,
            response=response,
            duration_seconds=duration_seconds,
            trace_events=trace_events,
            assertion_results={},
            error=error
        ))
        
        result = TaskResult(
            task_id=task.id,
            chat_id=chat_id,
            run_id=run_id,
            success=(error is None) and task_score['passed'],
            response=response,
            duration_seconds=duration_seconds,
            trace_events=trace_events,
            assertion_results=task_score['assertion_results'],
            error=error
        )
        
        self.results.append(result)
        return result
    
    async def run_all_tasks(self, task_filter: Optional[str] = None, parallel: bool = False) -> List[TaskResult]:
        """Run all golden tasks"""
        tasks = self.load_tasks(task_filter)
        
        if not tasks:
            print(f"No tasks found in {self.tasks_dir}")
            return []
            
        print(f"Running {len(tasks)} golden tasks...")
        
        if parallel:
            # Run tasks in parallel (be careful with rate limits)
            results = await asyncio.gather(
                *[self.run_task(task) for task in tasks],
                return_exceptions=True
            )
            # Convert exceptions to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(TaskResult(
                        task_id=tasks[i].id,
                        chat_id="",
                        run_id="",
                        success=False,
                        response="",
                        duration_seconds=0.0,
                        trace_events=[],
                        assertion_results={},
                        error=str(result)
                    ))
                else:
                    processed_results.append(result)
            return processed_results
        else:
            # Run tasks sequentially
            results = []
            for i, task in enumerate(tasks, 1):
                print(f"  [{i}/{len(tasks)}] Running task: {task.id}")
                result = await self.run_task(task)
                results.append(result)
                status = "✓" if result.success else "✗"
                print(f"  {status} Completed in {result.duration_seconds:.1f}s")
                
                if result.error:
                    print(f"    Error: {result.error}")
                    
            return results
    
    def save_results(self, output_path: Path):
        """Save results to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert results to dict format (excluding trace_events for size)
        results_data = []
        for result in self.results:
            result_dict = asdict(result)
            # Store trace file path instead of events
            result_dict['trace_file'] = f"data/traces/{result.chat_id}/{result.run_id}.jsonl"
            result_dict['trace_event_count'] = len(result.trace_events)
            del result_dict['trace_events']  # Remove large event data
            results_data.append(result_dict)
        
        with open(output_path, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'total_tasks': len(self.results),
                'successful_tasks': sum(1 for r in self.results if r.success),
                'results': results_data
            }, f, indent=2)
            
        print(f"Results saved to: {output_path}")


def main():
    """CLI entry point for running golden tasks"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run golden evaluation tasks")
    parser.add_argument('--filter', help="Filter tasks by ID substring")
    parser.add_argument('--parallel', action='store_true', help="Run tasks in parallel")
    parser.add_argument('--output', help="Output file for results", 
                       default="evals/results/run_results.json")
    
    args = parser.parse_args()
    
    async def run():
        runner = GoldenTaskRunner()
        results = await runner.run_all_tasks(
            task_filter=args.filter,
            parallel=args.parallel
        )
        
        runner.save_results(Path(args.output))
        
        # Generate scorecard
        task_scores = []
        for result in results:
            task = next((t for t in runner.load_tasks() if t.id == result.task_id), None)
            if task:
                task_score = runner.scorer.score_task(task, result)
                task_scores.append(task_score)
        
        scorecard = generate_scorecard(task_scores)
        
        # Print summary
        print(f"\nEvaluation Scorecard:")
        print(f"===================")
        print(f"Overall Pass Rate: {scorecard['overall_pass_rate']:.1%}")
        print(f"Tasks Passed: {scorecard['passed_tasks']}/{scorecard['total_tasks']}")
        print(f"Average Score: {scorecard['average_score']:.2f}")
        
        print(f"\nTask Details:")
        for result in results:
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.task_id}: {result.duration_seconds:.1f}s")
            if result.error:
                print(f"    Error: {result.error}")
            else:
                # Show assertion summary
                passed = sum(1 for r in result.assertion_results.values() if r.get('passed', False))
                total = len(result.assertion_results)
                print(f"    Assertions: {passed}/{total} passed")
    
    asyncio.run(run())


if __name__ == "__main__":
    main()