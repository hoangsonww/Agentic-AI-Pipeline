from __future__ import annotations
from typing import TypedDict, List, Any
from langgraph.graph import StateGraph, START
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool
from ..config import settings
from .composition import PROFILE
from . import memory as mem
from ..infra.logging import logger
from ..infra.trace import get_current_tracer
import time


# ---- State definition ----
class AgentState(TypedDict):
    messages: list
    plan: str
    next_action: str
    citations: list[str]
    done: bool


def _llm():
    if settings.MODEL_PROVIDER.lower() == "anthropic":
        return ChatAnthropic(model=settings.ANTHROPIC_MODEL_CHAT, temperature=0.2)
    return ChatOpenAI(model=settings.OPENAI_MODEL_CHAT, temperature=0.2)


SYSTEM = f"""
You are {PROFILE.name}: {PROFILE.persona}
Primary Objective: {PROFILE.objective}

General guidelines:
- Always think in steps. Keep internal notes concise.
- Prefer trustworthy sources. Keep a running list of citation URLs.
- When enough evidence is gathered, synthesize a compact briefing with bullets and explicit citations.
- If asked to send/draft email, use the emailer tool with a concise, professional tone.
- NEVER fabricate URLs or facts.
"""


def _trace_node(node_name: str):
    """Decorator to add tracing to node functions"""
    def decorator(node_func):
        def wrapped_node(state: AgentState) -> AgentState:
            tracer = get_current_tracer()
            start_time = time.time()
            
            if tracer:
                tracer.log_node_start(node_name, {
                    "state_keys": list(state.keys()),
                    "messages_count": len(state.get("messages", [])),
                    "current_action": state.get("next_action", ""),
                    "done": state.get("done", False)
                })
            
            try:
                result = node_func(state)
                duration_ms = (time.time() - start_time) * 1000
                
                if tracer:
                    tracer.log_node_end(node_name, {
                        "output_action": result.get("next_action", ""),
                        "plan_summary": result.get("plan", "")[:200] if result.get("plan") else "",
                        "done": result.get("done", False),
                        "messages_added": len(result.get("messages", [])) - len(state.get("messages", []))
                    }, duration_ms)
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                if tracer:
                    tracer.log_node_end(node_name, {"error": str(e)}, duration_ms)
                raise
                
        return wrapped_node
    return decorator


# ---- Nodes ----
@_trace_node("planner")
def planner_node(state: AgentState) -> AgentState:
    """Create a short action plan and consider KB context."""
    llm = _llm()
    # Retrieve recent KB passages for context (RAG pre-plan)
    user_text = state["messages"][-1].content if state["messages"] else ""
    kb_hits = mem.kb_search(user_text, k=5)
    kb_context = "\n\n".join(f"- {h['text'][:500]}" for h in kb_hits)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM),
        ("system", "Internal knowledge that may be relevant:\n{kb}"),
        ("human", "User request:\n{user}\n\nProduce a 3-6 step action plan. Identify tools to use. Do not execute.")
    ])
    resp = llm.invoke(prompt.format_messages(user=user_text, kb=kb_context or "None"))
    plan = resp.content
    state["messages"].append(AIMessage(content=f"Plan:\n{plan}"))
    state["plan"] = plan
    state["next_action"] = "decide"
    return state


@_trace_node("decide")
def decide_node(state: AgentState) -> AgentState:
    """Choose next action label."""
    llm = _llm()
    hist = "\n".join([getattr(m, "content", "") for m in state["messages"][-6:]])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Decide the immediate next action based on the plan and recent messages."),
        ("human",
         "Plan:\n{plan}\n\nRecent:\n{hist}\n\nChoose ONE token from: search, fetch, kb_search, calculate, write_file, draft_email, finalize.\nAnswer with the single token only.")
    ])
    resp = llm.invoke(prompt.format_messages(plan=state.get("plan", ""), hist=hist))
    state["next_action"] = resp.content.strip().lower()
    return state


def act_node_builder(tools: List[BaseTool]):
    """Bind tools to LLM and cause a structured tool call for the chosen action."""
    llm = _llm().bind_tools(tools)

    @_trace_node("act")
    def act_node(state: AgentState) -> AgentState:
        action = state.get("next_action", "")
        mapping = {
            "search": "web_search",
            "fetch": "web_fetch",
            "kb_search": "kb_search",
            "calculate": "calculator",
            "write_file": "file_write",
            "draft_email": "emailer",
        }
        tool_name = mapping.get(action)
        if not tool_name:
            # If finalize or unknown, move to reflection
            state["messages"].append(AIMessage(content="Reflecting on gathered info..."))
            return state
        # Instruct LLM to call the specific tool with precise input
        sys = "You MUST call exactly one tool matching the requested next_action.\nCarefully choose arguments."
        last_user = state["messages"][-1]
        plan = state.get("plan", "")
        prompt = [
            SystemMessage(content=sys),
            AIMessage(content=f"Next action: {action} -> tool `{tool_name}`. Plan:\n{plan}"),
            last_user
        ]
        resp = llm.invoke(prompt)
        # The ToolNode will execute based on tool_calls present in resp
        state["messages"].append(resp)
        return state

    return act_node


@_trace_node("reflect")
def reflect_node(state: AgentState) -> AgentState:
    llm = _llm()
    notes = "\n".join(m.content for m in state["messages"] if isinstance(m, AIMessage))
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "If enough information exists, write BRIEFING with bullet points and include citations as URLs at the end. Otherwise propose NEXT:<action>."),
        ("human", "Notes so far:\n{notes}")
    ])
    resp = llm.invoke(prompt.format_messages(notes=notes[:6000]))
    txt = resp.content.strip()
    if txt.startswith("BRIEFING"):
        state["messages"].append(AIMessage(content=txt))
        state["done"] = True
    else:
        state["next_action"] = txt.split(":", 1)[-1].strip().lower()
    return state


@_trace_node("finalize")
def finalize_node(state: AgentState) -> AgentState:
    state["done"] = True
    return state


# ---- Graph build ----
def build_graph(tools: List[BaseTool]):
    from langgraph.prebuilt import ToolNode
    
    # Create traced tool node
    def traced_tool_node(state: AgentState) -> AgentState:
        tracer = get_current_tracer()
        
        # Extract tool calls from the last AI message
        messages = state.get("messages", [])
        if not messages:
            return state
            
        last_msg = messages[-1]
        if not hasattr(last_msg, 'tool_calls') or not last_msg.tool_calls:
            return state
        
        # Execute each tool call with tracing
        for tool_call in last_msg.tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            
            if tracer:
                tracer.log_tool_request(tool_name, tool_args)
            
            start_time = time.time()
            try:
                # Use the original ToolNode for actual execution
                original_tool_node = ToolNode(tools)
                result_state = original_tool_node.invoke(state)
                duration_ms = (time.time() - start_time) * 1000
                
                # Try to extract the tool result from the updated state
                new_messages = result_state.get("messages", [])
                tool_result = None
                if len(new_messages) > len(messages):
                    # Assuming the new message contains the tool result
                    tool_msg = new_messages[-1]
                    if hasattr(tool_msg, 'content'):
                        tool_result = tool_msg.content
                
                if tracer:
                    tracer.log_tool_response(tool_name, tool_result, duration_ms)
                
                return result_state
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                if tracer:
                    tracer.log_tool_response(tool_name, None, duration_ms, str(e))
                raise
        
        # Fallback to original ToolNode if no tool calls found
        return ToolNode(tools).invoke(state)
    
    g = StateGraph(AgentState)

    g.add_node("plan", planner_node)
    g.add_node("decide", decide_node)
    g.add_node("act", act_node_builder(tools))
    g.add_node("tools", traced_tool_node)
    g.add_node("reflect", reflect_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "plan")
    g.add_edge("plan", "decide")

    def route_from_decide(state: AgentState):
        nxt = state.get("next_action", "")
        if nxt in {"search", "fetch", "kb_search", "calculate", "write_file", "draft_email"}:
            return "act"
        if nxt == "finalize":
            return "finalize"
        return "reflect"

    g.add_conditional_edges("decide", route_from_decide, {
        "act": "act", "reflect": "reflect", "finalize": "finalize"
    })

    # After act, execute tools; after tools, reflect
    g.add_edge("act", "tools")
    g.add_edge("tools", "reflect")

    # From reflect either finalize or re-decide
    def route_from_reflect(state: AgentState):
        return "finalize" if state.get("done") else "decide"

    g.add_conditional_edges("reflect", route_from_reflect, {
        "finalize": "finalize", "decide": "decide"
    })

    return g.compile()
