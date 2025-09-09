"""CLI module for agentic AI pipeline."""

from __future__ import annotations

import argparse
import sys
import asyncio
from typing import Optional
from pathlib import Path

from .memory.trace_store import get_trace_store
from .llm.replay_llm import ReplayLLM
from .graph import run_chat
from .infra.logging import logger


def replay_command(chat_id: str, html_report: bool = False) -> None:
    """Replay a chat session deterministically.
    
    Args:
        chat_id: The chat ID to replay
        html_report: Whether to generate an HTML report
    """
    trace_store = get_trace_store()
    
    if not trace_store.trace_exists(chat_id):
        print(f"Error: No trace found for chat ID: {chat_id}")
        return
    
    # Load trace events
    events = trace_store.get_trace(chat_id)
    if not events:
        print(f"Error: Empty trace for chat ID: {chat_id}")
        return
    
    print(f"Replaying chat {chat_id} with {len(events)} events...")
    
    # Display trace summary
    print("\n=== Trace Summary ===")
    node_counts = {}
    tool_counts = {}
    
    for event in events:
        if event.event_type.value in ["node_enter", "node_exit"]:
            node = event.node or "unknown"
            node_counts[node] = node_counts.get(node, 0) + 1
        elif event.event_type.value == "tool_call":
            tool = event.tool or "unknown"
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
    
    print(f"Nodes executed: {', '.join(f'{k}({v//2})' for k, v in node_counts.items())}")
    if tool_counts:
        print(f"Tools used: {', '.join(f'{k}({v})' for k, v in tool_counts.items())}")
    
    # Display LLM interactions
    llm_outputs = list(trace_store.get_llm_outputs(chat_id))
    print(f"LLM interactions: {len(llm_outputs)}")
    
    print("\n=== LLM Interactions ===")
    for i, (prompt, output) in enumerate(llm_outputs):
        print(f"\n--- Interaction {i+1} ---")
        print(f"Prompt: {prompt[:200]}...")
        print(f"Output: {output[:200]}...")
    
    if html_report:
        generate_html_report(chat_id, events, llm_outputs)
    
    print(f"\nReplay completed for chat {chat_id}")


def generate_html_report(chat_id: str, events, llm_outputs) -> None:
    """Generate an HTML report for the trace."""
    report_path = Path(f"data/traces/{chat_id}_report.html")
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trace Report - {chat_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .event {{ margin: 10px 0; padding: 10px; border: 1px solid #ccc; border-radius: 5px; }}
        .node_enter {{ background-color: #e7f5e7; }}
        .node_exit {{ background-color: #f5e7e7; }}
        .tool_call {{ background-color: #e7e7f5; }}
        .llm_prompt {{ background-color: #f5f5e7; }}
        .timestamp {{ font-size: 0.8em; color: #666; }}
        .metadata {{ font-size: 0.9em; color: #444; }}
    </style>
</head>
<body>
    <h1>Trace Report: {chat_id}</h1>
    
    <h2>Summary</h2>
    <p>Total events: {len(events)}</p>
    <p>LLM interactions: {len(llm_outputs)}</p>
    
    <h2>Timeline</h2>
"""
    
    for event in events:
        event_class = event.event_type.value.replace('_', '')
        html += f"""
    <div class="event {event_class}">
        <strong>{event.event_type.value.replace('_', ' ').title()}</strong>
        <span class="timestamp">({event.timestamp})</span>
        <br>
"""
        
        if event.node:
            html += f"Node: {event.node}<br>"
        if event.tool:
            html += f"Tool: {event.tool}<br>"
        if event.prompt:
            html += f"Prompt: {event.prompt[:300]}...<br>"
        if event.output:
            html += f"Output: {event.output[:300]}...<br>"
        if event.metadata:
            html += f'<div class="metadata">Metadata: {event.metadata}</div>'
        
        html += "</div>"
    
    html += """
</body>
</html>
"""
    
    with report_path.open('w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML report generated: {report_path}")


def ingest_command(path: str) -> None:
    """Ingest documents into knowledge base."""
    # This would be implemented based on existing ingestion logic
    print(f"Ingesting documents from: {path}")
    # For now, just a placeholder
    print("Ingest command not yet implemented")


def demo_command(query: str) -> None:
    """Run a demo query."""
    print(f"Demo query: {query}")
    
    async def run_demo():
        chat_id = "demo_" + str(hash(query))[:8]
        print(f"Chat ID: {chat_id}")
        
        async for chunk in run_chat(chat_id, query):
            print(chunk, end="", flush=True)
        print("\n")
    
    asyncio.run(run_demo())


def list_traces_command() -> None:
    """List all available traces."""
    trace_store = get_trace_store()
    traces = trace_store.list_traces()
    
    if not traces:
        print("No traces found.")
        return
    
    print(f"Found {len(traces)} traces:")
    for chat_id in traces:
        events = trace_store.get_trace(chat_id)
        llm_count = len(list(trace_store.get_llm_outputs(chat_id)))
        print(f"  {chat_id}: {len(events)} events, {llm_count} LLM interactions")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Agentic AI Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a chat session")
    replay_parser.add_argument("--chat-id", required=True, help="Chat ID to replay")
    replay_parser.add_argument("--html-report", action="store_true", help="Generate HTML report")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
    ingest_parser.add_argument("path", help="Path to documents to ingest")
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run a demo query")
    demo_parser.add_argument("query", help="Query to run")
    
    # List traces command
    list_parser = subparsers.add_parser("list-traces", help="List all traces")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "replay":
            replay_command(args.chat_id, args.html_report)
        elif args.command == "ingest":
            ingest_command(args.path)
        elif args.command == "demo":
            demo_command(args.query)
        elif args.command == "list-traces":
            list_traces_command()
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"CLI command failed: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()