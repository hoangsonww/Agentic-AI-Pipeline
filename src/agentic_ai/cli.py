"""
CLI interface for the Agentic AI system.
Supports chat interactions and trace replay functionality.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from .infra.trace import read_trace
from .config import settings

app = typer.Typer(name="agentic-ai", help="Agentic AI Pipeline CLI")


@app.command()
def chat(
    message: Annotated[str, typer.Argument(help="Message to send to the agent")],
    chat_id: Annotated[Optional[str], typer.Option(help="Chat ID to use")] = None,
    enable_trace: Annotated[bool, typer.Option("--trace", help="Enable tracing for this run")] = False
):
    """Send a message to the AI agent"""
    # Import graph module here to avoid API key issues for other commands
    from .graph import run_chat
    import uuid
    
    if chat_id is None:
        chat_id = str(uuid.uuid4())[:8]
    
    # Temporarily enable tracing if requested
    original_trace_setting = settings.ENABLE_TRACING
    if enable_trace:
        settings.ENABLE_TRACING = True
    
    try:
        async def run():
            print(f"Chat ID: {chat_id}")
            if enable_trace:
                print(f"Tracing enabled. Trace will be saved to: data/traces/{chat_id}/")
            
            print(f"\nUser: {message}")
            print("Assistant: ", end="", flush=True)
            
            async for chunk in run_chat(chat_id, message):
                print(chunk, end="", flush=True)
            print("\n")
        
        asyncio.run(run())
        
    finally:
        # Restore original tracing setting
        settings.ENABLE_TRACING = original_trace_setting


@app.command()
def replay(
    trace_path: Annotated[Path, typer.Argument(help="Path to trace file")],
    show_events: Annotated[bool, typer.Option("--show-events", help="Show trace events")] = False
):
    """Replay a trace file (mock implementation for now)"""
    if not trace_path.exists():
        typer.echo(f"Error: Trace file {trace_path} not found", err=True)
        raise typer.Exit(1)
    
    try:
        events = read_trace(trace_path)
        typer.echo(f"Loaded {len(events)} events from trace: {trace_path}")
        
        if show_events:
            typer.echo("\nTrace Events:")
            typer.echo("-" * 50)
            for event in events:
                typer.echo(f"[{event.timestamp:.3f}] {event.node_name}:{event.event_type}")
                if event.duration_ms:
                    typer.echo(f"  Duration: {event.duration_ms:.1f}ms")
                if event.data:
                    for key, value in event.data.items():
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        typer.echo(f"  {key}: {value}")
                typer.echo()
        
        typer.echo("Note: Full replay with tool mocking not yet implemented")
        
    except Exception as e:
        typer.echo(f"Error reading trace: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list_traces(
    chat_id: Annotated[Optional[str], typer.Option(help="Filter by chat ID")] = None
):
    """List available trace files"""
    traces_dir = Path("data/traces")
    
    if not traces_dir.exists():
        typer.echo("No traces directory found")
        return
    
    trace_files = []
    for chat_dir in traces_dir.iterdir():
        if chat_dir.is_dir() and (chat_id is None or chat_dir.name == chat_id):
            for trace_file in chat_dir.glob("*.jsonl"):
                trace_files.append((chat_dir.name, trace_file.name, trace_file))
    
    if not trace_files:
        typer.echo("No trace files found")
        return
    
    typer.echo("Available traces:")
    typer.echo("-" * 60)
    typer.echo(f"{'Chat ID':<12} {'Run ID':<12} {'File Size':<10} Path")
    typer.echo("-" * 60)
    
    for chat_id, run_file, full_path in sorted(trace_files):
        run_id = run_file.replace('.jsonl', '')
        size = full_path.stat().st_size
        size_str = f"{size}B"
        if size > 1024:
            size_str = f"{size//1024}KB"
        
        typer.echo(f"{chat_id:<12} {run_id:<12} {size_str:<10} {full_path}")


def main():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    main()