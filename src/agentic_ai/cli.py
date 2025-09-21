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
    enable_trace: Annotated[bool, typer.Option("--trace", help="Enable tracing for this run")] = False,
    seed: Annotated[Optional[str], typer.Option("--seed", help="Seed for reproducible runs")] = None
):
    """Send a message to the AI agent"""
    # Import graph module here to avoid API key issues for other commands
    from .graph import run_chat
    from .infra.trace import seed_randomness, create_reproducible_run_id
    import uuid
    
    if chat_id is None:
        chat_id = str(uuid.uuid4())[:8]
    
    # Seed randomness if requested
    if seed:
        seed_randomness(seed)
        # Use deterministic run ID for reproducible runs
        run_id = create_reproducible_run_id(chat_id, message, seed)
        typer.echo(f"Seeded run (seed={seed}, run_id={run_id})")
    
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
    show_events: Annotated[bool, typer.Option("--show-events", help="Show trace events")] = False,
    run_replay: Annotated[bool, typer.Option("--execute", help="Execute replay with mock tools")] = False,
    new_chat_id: Annotated[Optional[str], typer.Option("--chat-id", help="New chat ID for replay")] = None
):
    """Replay a trace file"""
    if not trace_path.exists():
        typer.echo(f"Error: Trace file {trace_path} not found", err=True)
        raise typer.Exit(1)
    
    try:
        if run_replay:
            # Execute the replay
            from .infra.replay import ReplayEngine
            import asyncio
            
            async def run_replay_async():
                engine = ReplayEngine(trace_path)
                info = engine.get_replay_info()
                
                typer.echo(f"Replaying trace: {trace_path}")
                typer.echo(f"Original chat: {info['original_chat_id']}")
                typer.echo(f"Original message: {info['original_message']}")
                typer.echo(f"Mock tools: {info['mock_tools']}")
                typer.echo()
                
                chat_id = new_chat_id or f"replay_{info['original_chat_id']}"
                typer.echo(f"Replay chat ID: {chat_id}")
                typer.echo("Assistant: ", end="")
                
                async for chunk in engine.replay_chat(chat_id):
                    typer.echo(chunk, nl=False)
                typer.echo()
            
            asyncio.run(run_replay_async())
        else:
            # Just show trace info
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
            
            if not run_replay:
                typer.echo("\nUse --execute to run replay with mock tools")
        
    except Exception as e:
        typer.echo(f"Error processing trace: {e}", err=True)
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


@app.command()
def compare_traces(
    original: Annotated[Path, typer.Argument(help="Original trace file")],
    replay: Annotated[Path, typer.Argument(help="Replay trace file")]
):
    """Compare original and replay traces for reproducibility"""
    if not original.exists():
        typer.echo(f"Error: Original trace {original} not found", err=True)
        raise typer.Exit(1)
    
    if not replay.exists():
        typer.echo(f"Error: Replay trace {replay} not found", err=True)
        raise typer.Exit(1)
    
    try:
        from .infra.replay import compare_traces
        
        comparison = compare_traces(original, replay)
        
        typer.echo("Trace Comparison Results:")
        typer.echo("=" * 30)
        typer.echo(f"Sequence Match: {'✓' if comparison['sequence_match'] else '✗'}")
        typer.echo(f"Tools Match: {'✓' if comparison['tools_match'] else '✗'}")
        typer.echo(f"Original Events: {comparison['original_events']}")
        typer.echo(f"Replay Events: {comparison['replay_events']}")
        
        typer.echo(f"\nTool Usage:")
        typer.echo(f"Original: {comparison['original_tools']}")
        typer.echo(f"Replay: {comparison['replay_tools']}")
        
        if comparison['differences']['missing_in_replay']:
            typer.echo(f"\nMissing in replay: {comparison['differences']['missing_in_replay']}")
        
        if comparison['differences']['extra_in_replay']:
            typer.echo(f"Extra in replay: {comparison['differences']['extra_in_replay']}")
            
    except Exception as e:
        typer.echo(f"Error comparing traces: {e}", err=True)
        raise typer.Exit(1)


def main():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    main()