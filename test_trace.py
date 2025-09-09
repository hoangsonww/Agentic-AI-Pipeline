#!/usr/bin/env python3
"""
Simple test script to verify tracing functionality works.
"""

import os
import sys
sys.path.insert(0, 'src')

from agentic_ai.infra.trace import trace_run, read_trace
from pathlib import Path
import time

def test_basic_tracing():
    """Test basic tracing functionality"""
    print("Testing basic tracing functionality...")
    
    # Enable tracing temporarily
    os.environ['ENABLE_TRACING'] = 'true'
    
    chat_id = "test_chat_001"
    
    with trace_run(chat_id, "test_run_001") as tracer:
        if tracer:
            print(f"✓ Tracer created: {tracer.trace_file}")
            
            # Simulate some agent operations
            tracer.log_node_start("planner", {"user_input": "Hello world"})
            time.sleep(0.1)
            tracer.log_node_end("planner", {"plan": "Simple greeting"}, 100.0)
            
            tracer.log_node_start("decide", {"plan": "Simple greeting"})
            time.sleep(0.05)
            tracer.log_node_end("decide", {"next_action": "finalize"}, 50.0)
            
            tracer.log_tool_request("calculator", {"expression": "2+2"})
            time.sleep(0.02)
            tracer.log_tool_response("calculator", "4", 20.0)
            
            tracer.log_state_transition("decide", "finalize", {"reason": "completed"})
    
    # Verify trace file was created
    trace_file = Path(f"data/traces/{chat_id}/test_run_001.jsonl")
    if trace_file.exists():
        print(f"✓ Trace file created: {trace_file}")
        
        # Read and display events
        events = read_trace(trace_file)
        print(f"✓ Read {len(events)} events from trace")
        
        print("\nTrace events:")
        for event in events:
            print(f"  {event.timestamp:.3f} [{event.node_name}] {event.event_type}")
            if event.duration_ms:
                print(f"    Duration: {event.duration_ms:.1f}ms")
        
        print("\n✓ Basic tracing test passed!")
        return True
    else:
        print(f"✗ Trace file not found: {trace_file}")
        return False

if __name__ == "__main__":
    success = test_basic_tracing()
    exit(0 if success else 1)