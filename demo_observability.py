#!/usr/bin/env python3
"""
Simple end-to-end demonstration of the observability system.
"""

import os
import sys
from pathlib import Path

# Set dummy API key BEFORE any imports
os.environ.setdefault("OPENAI_API_KEY", "dummy-key-for-demo")

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncio

from agentic_ai.graph import run_chat
from agentic_ai.memory.trace_store import get_trace_store
from agentic_ai.cli import replay_command


async def main():
    """Run a simple end-to-end demonstration."""
    print("🚀 Agentic AI Observability Demo")
    print("=" * 50)
    
    try:
        # 1. Show tracing initialization
        print("✅ Initializing tracing system...")
        from agentic_ai.infra.tracing import init_tracing
        tracer = init_tracing()
        print(f"   Tracer initialized: {tracer}")
        
        # 2. Show trace store
        print("\n✅ Setting up trace storage...")
        trace_store = get_trace_store()
        print(f"   Trace store initialized: {trace_store.base_dir}")
        
        # 3. Show existing traces
        print("\n📋 Existing traces:")
        traces = trace_store.list_traces()
        if traces:
            for trace_id in traces:
                events = trace_store.get_trace(trace_id)
                llm_count = len(list(trace_store.get_llm_outputs(trace_id)))
                print(f"   - {trace_id}: {len(events)} events, {llm_count} LLM interactions")
        else:
            print("   No existing traces found")
        
        # 4. Create a mock trace for demonstration
        print("\n✅ Creating demonstration trace...")
        demo_chat_id = "demo_observability_test"
        
        # Record a simple interaction
        trace_store.record_node_enter(demo_chat_id, "plan", trace_id="trace1", span_id="span1")
        trace_store.record_llm_prompt(
            demo_chat_id, 
            "Plan how to research Tesla Inc.", 
            trace_id="trace1", 
            span_id="span1"
        )
        trace_store.record_llm_output(
            demo_chat_id,
            "I'll search for Tesla information, analyze the results, and create a briefing.",
            trace_id="trace1",
            span_id="span1"
        )
        trace_store.record_node_exit(demo_chat_id, "plan", trace_id="trace1", span_id="span1")
        
        trace_store.record_node_enter(demo_chat_id, "act", trace_id="trace1", span_id="span2")
        trace_store.record_tool_call(
            demo_chat_id,
            "web_search",
            "Tesla Inc electric vehicle company",
            trace_id="trace1",
            span_id="span2"
        )
        trace_store.record_tool_result(
            demo_chat_id,
            "web_search", 
            "Tesla, Inc. is an American electric vehicle and clean energy company...",
            trace_id="trace1",
            span_id="span2"
        )
        trace_store.record_node_exit(demo_chat_id, "act", trace_id="trace1", span_id="span2")
        
        print(f"   Demo trace created: {demo_chat_id}")
        
        # 5. Show replay functionality
        print("\n🔄 Testing replay functionality...")
        replay_command(demo_chat_id, html_report=True)
        
        # 6. Show CLI commands available
        print("\n🛠️  Available CLI commands:")
        print("   python -m agentic_ai.cli list-traces")
        print("   python -m agentic_ai.cli replay --chat-id <id>")
        print("   make eval  # Run regression tests")
        
        # 7. Show evaluation tasks
        print("\n📊 Evaluation framework:")
        from tests.evals.runner import EvaluationRunner
        runner = EvaluationRunner()
        tasks = runner.load_tasks()
        print(f"   Loaded {len(tasks)} golden evaluation tasks")
        for task in tasks[:3]:  # Show first 3
            print(f"   - {task['id']}: {task['description']}")
        if len(tasks) > 3:
            print(f"   ... and {len(tasks) - 3} more tasks")
        
        print("\n✅ Observability system demonstration complete!")
        print("\n📖 Key capabilities:")
        print("   • OpenTelemetry tracing with automatic instrumentation")  
        print("   • Deterministic replay of agent conversations")
        print("   • Comprehensive regression evaluation framework")
        print("   • Jaeger integration for trace visualization")
        print("   • CI/CD integration with GitHub Actions")
        
        print(f"\n📁 Generated files:")
        print(f"   • Traces: {trace_store.base_dir}")
        if (trace_store.base_dir / f"{demo_chat_id}_report.html").exists():
            print(f"   • HTML Report: {trace_store.base_dir / f'{demo_chat_id}_report.html'}")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))