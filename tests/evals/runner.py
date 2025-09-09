"""Evaluation runner for regression testing."""

from __future__ import annotations

import asyncio
import time
import yaml
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
import xml.etree.ElementTree as ET

from .checks import CHECK_FUNCTIONS
from agentic_ai.graph import run_chat
from agentic_ai.memory.trace_store import get_trace_store
from agentic_ai.llm.replay_llm import ReplayLLM
from agentic_ai.infra.logging import logger


@dataclass
class TaskResult:
    """Result of evaluating a single task."""
    task_id: str
    prompt: str
    output: str
    passed: bool
    check_results: Dict[str, tuple[bool, str]]
    duration_seconds: float
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Overall evaluation report."""
    total_tasks: int
    passed_tasks: int
    failed_tasks: int
    pass_rate: float
    duration_seconds: float
    results: List[TaskResult]
    
    @property
    def summary(self) -> str:
        return f"{self.passed_tasks}/{self.total_tasks} tasks passed ({self.pass_rate:.1%})"


class EvaluationRunner:
    """Runs evaluation tasks and generates reports."""
    
    def __init__(
        self, 
        tasks_file: str = "tests/evals/tasks.yaml",
        use_replay: bool = False,
        replay_chat_prefix: str = "eval_"
    ):
        self.tasks_file = Path(tasks_file)
        self.use_replay = use_replay
        self.replay_chat_prefix = replay_chat_prefix
        self.trace_store = get_trace_store()
    
    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load tasks from YAML file."""
        with self.tasks_file.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return data.get('tasks', [])
    
    async def run_task(self, task: Dict[str, Any]) -> TaskResult:
        """Run a single evaluation task."""
        task_id = task['id']
        prompt = task['prompt']
        timeout = task.get('timeout_seconds', 60)
        
        logger.info(f"Running eval task: {task_id}")
        
        start_time = time.time()
        
        try:
            # Generate chat ID
            if self.use_replay:
                chat_id = f"{self.replay_chat_prefix}{task_id}"
            else:
                chat_id = f"eval_{task_id}_{int(start_time)}"
            
            # Run the chat
            output_chunks = []
            try:
                async with asyncio.timeout(timeout):
                    async for chunk in run_chat(chat_id, prompt):
                        output_chunks.append(chunk)
            except asyncio.TimeoutError:
                raise Exception(f"Task timed out after {timeout} seconds")
            
            output = "".join(output_chunks)
            duration = time.time() - start_time
            
            # Get trace events for advanced checks
            trace_events = []
            if self.trace_store.trace_exists(chat_id):
                trace_events = [event.to_dict() for event in self.trace_store.get_trace(chat_id)]
            
            # Run checks
            check_results = {}
            all_passed = True
            
            for check_name, check_config in task.get('expected_checks', {}).items():
                if check_name not in CHECK_FUNCTIONS:
                    logger.warning(f"Unknown check function: {check_name}")
                    continue
                
                check_fn = CHECK_FUNCTIONS[check_name]
                
                try:
                    # Call check function with appropriate arguments
                    if check_name in ['uses_kb_search', 'multi_step_plan']:
                        # These checks can use trace events
                        if isinstance(check_config, bool) and check_config:
                            result = check_fn(output, trace_events)
                        else:
                            result = check_fn(output, trace_events)
                    elif isinstance(check_config, list):
                        # Check functions that take a list parameter
                        result = check_fn(output, check_config)
                    elif isinstance(check_config, (int, float)):
                        # Check functions that take a numeric parameter
                        result = check_fn(output, check_config)
                    elif isinstance(check_config, bool) and check_config:
                        # Boolean checks
                        result = check_fn(output)
                    else:
                        # Default case
                        result = check_fn(output)
                    
                    check_results[check_name] = result
                    if not result[0]:
                        all_passed = False
                        
                except Exception as e:
                    logger.error(f"Check {check_name} failed with error: {e}")
                    check_results[check_name] = (False, f"Check error: {e}")
                    all_passed = False
            
            return TaskResult(
                task_id=task_id,
                prompt=prompt,
                output=output,
                passed=all_passed,
                check_results=check_results,
                duration_seconds=duration
            )
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Task {task_id} failed: {e}")
            return TaskResult(
                task_id=task_id,
                prompt=prompt,
                output="",
                passed=False,
                check_results={},
                duration_seconds=duration,
                error=str(e)
            )
    
    async def run_all_tasks(self) -> EvalReport:
        """Run all evaluation tasks."""
        tasks = self.load_tasks()
        logger.info(f"Running {len(tasks)} evaluation tasks")
        
        start_time = time.time()
        
        # Run tasks sequentially to avoid overwhelming the system
        results = []
        for task in tasks:
            result = await self.run_task(task)
            results.append(result)
        
        duration = time.time() - start_time
        
        # Calculate summary statistics
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        pass_rate = passed_count / len(results) if results else 0.0
        
        return EvalReport(
            total_tasks=len(results),
            passed_tasks=passed_count,
            failed_tasks=failed_count,
            pass_rate=pass_rate,
            duration_seconds=duration,
            results=results
        )
    
    def generate_junit_xml(self, report: EvalReport, output_file: str = "eval_results.xml"):
        """Generate JUnit XML report."""
        testsuites = ET.Element("testsuites")
        testsuites.set("name", "Agentic AI Evaluation")
        testsuites.set("tests", str(report.total_tasks))
        testsuites.set("failures", str(report.failed_tasks))
        testsuites.set("time", f"{report.duration_seconds:.2f}")
        
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", "EvaluationTasks")
        testsuite.set("tests", str(report.total_tasks))
        testsuite.set("failures", str(report.failed_tasks))
        testsuite.set("time", f"{report.duration_seconds:.2f}")
        
        for result in report.results:
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("classname", "EvaluationTasks")
            testcase.set("name", result.task_id)
            testcase.set("time", f"{result.duration_seconds:.2f}")
            
            if not result.passed:
                failure = ET.SubElement(testcase, "failure")
                if result.error:
                    failure.set("message", result.error)
                    failure.text = result.error
                else:
                    failed_checks = [
                        f"{check}: {reason}" 
                        for check, (passed, reason) in result.check_results.items() 
                        if not passed
                    ]
                    failure.set("message", "Check failures")
                    failure.text = "\n".join(failed_checks)
        
        # Write XML file
        tree = ET.ElementTree(testsuites)
        ET.indent(tree, space="  ", level=0)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        logger.info(f"JUnit XML report written to: {output_file}")
    
    def print_summary_table(self, report: EvalReport):
        """Print a summary table to console."""
        print(f"\n{'='*80}")
        print(f"EVALUATION RESULTS SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tasks: {report.total_tasks}")
        print(f"Passed: {report.passed_tasks}")
        print(f"Failed: {report.failed_tasks}")
        print(f"Pass Rate: {report.pass_rate:.1%}")
        print(f"Duration: {report.duration_seconds:.1f}s")
        print(f"{'='*80}")
        
        # Detailed results table
        print(f"\n{'Task ID':<25} {'Status':<10} {'Duration':<10} {'Checks'}")
        print(f"{'-'*80}")
        
        for result in report.results:
            status = "PASS" if result.passed else "FAIL"
            duration = f"{result.duration_seconds:.1f}s"
            
            if result.error:
                checks_summary = f"ERROR: {result.error[:30]}"
            else:
                passed_checks = sum(1 for passed, _ in result.check_results.values() if passed)
                total_checks = len(result.check_results)
                checks_summary = f"{passed_checks}/{total_checks}"
            
            print(f"{result.task_id:<25} {status:<10} {duration:<10} {checks_summary}")
        
        # Failed checks details
        failed_results = [r for r in report.results if not r.passed and not r.error]
        if failed_results:
            print(f"\nFAILED CHECKS DETAILS:")
            print(f"{'-'*80}")
            for result in failed_results:
                print(f"\n{result.task_id}:")
                for check, (passed, reason) in result.check_results.items():
                    if not passed:
                        print(f"  ❌ {check}: {reason}")


async def main():
    """Main evaluation runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run evaluation tasks")
    parser.add_argument("--use-replay", action="store_true", help="Use replay mode")
    parser.add_argument("--tasks-file", default="tests/evals/tasks.yaml", help="Tasks file")
    parser.add_argument("--output", default="eval_results.xml", help="Output XML file")
    
    args = parser.parse_args()
    
    runner = EvaluationRunner(
        tasks_file=args.tasks_file,
        use_replay=args.use_replay
    )
    
    report = await runner.run_all_tasks()
    
    # Generate outputs
    runner.generate_junit_xml(report, args.output)
    runner.print_summary_table(report)
    
    # Exit with error code if any tests failed
    if report.failed_tasks > 0:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())