from __future__ import annotations
import time
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
from ..infra.tracing import get_tracer, current_trace_id, current_span_id
from ..infra.metrics import record_latency, record_tokens
from ..memory.trace_store import get_trace_store


# ---- State definition ----
class AgentState(TypedDict):
    messages: list
    plan: str
    next_action: str
    citations: list[str]
    done: bool
    chat_id: str  # Added for tracing


def _llm():
    if settings.MODEL_PROVIDER.lower() == "anthropic":
        return ChatAnthropic(model=settings.ANTHROPIC_MODEL_CHAT, temperature=0.2)
    return ChatOpenAI(model=settings.OPENAI_MODEL_CHAT, temperature=0.2)


def _traced_llm_invoke(llm, messages, chat_id: str, node_name: str):
    """Invoke LLM with tracing and recording."""
    tracer = get_tracer()
    trace_store = get_trace_store()
    
    # Create span for LLM call
    with tracer.start_as_current_span(f"llm.{node_name}") as span:
        start_time = time.time()
        
        # Record prompt
        prompt_text = str(messages)
        trace_store.record_llm_prompt(
            chat_id=chat_id,
            prompt=prompt_text,
            trace_id=current_trace_id(),
            span_id=current_span_id(),
            metadata={"node": node_name, "provider": settings.MODEL_PROVIDER}
        )
        
        # Add span attributes
        span.set_attribute("llm.provider", settings.MODEL_PROVIDER)
        span.set_attribute("llm.model", settings.OPENAI_MODEL_CHAT if settings.MODEL_PROVIDER.lower() != "anthropic" else settings.ANTHROPIC_MODEL_CHAT)
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("node", node_name)
        
        try:
            # Invoke LLM
            response = llm.invoke(messages)
            
            # Record timing
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("llm.latency_ms", duration_ms)
            record_latency(duration_ms, f"llm.{node_name}", settings.MODEL_PROVIDER)
            
            # Record output
            output_text = response.content if hasattr(response, 'content') else str(response)
            trace_store.record_llm_output(
                chat_id=chat_id,
                output=output_text,
                trace_id=current_trace_id(),
                span_id=current_span_id(),
                metadata={"node": node_name, "latency_ms": duration_ms}
            )
            
            # Record token usage if available
            if hasattr(response, 'response_metadata') and 'usage' in response.response_metadata:
                usage = response.response_metadata['usage']
                if 'prompt_tokens' in usage:
                    record_tokens(usage['prompt_tokens'], "input", settings.MODEL_PROVIDER, span.get_attribute("llm.model"))
                    span.set_attribute("llm.tokens_input", usage['prompt_tokens'])
                if 'completion_tokens' in usage:
                    record_tokens(usage['completion_tokens'], "output", settings.MODEL_PROVIDER, span.get_attribute("llm.model"))
                    span.set_attribute("llm.tokens_output", usage['completion_tokens'])
            
            span.set_attribute("llm.success", True)
            return response
            
        except Exception as e:
            span.set_attribute("llm.success", False)
            span.set_attribute("llm.error", str(e))
            logger.error(f"LLM call failed in {node_name}: {e}")
            raise


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


# ---- Nodes ----
def planner_node(state: AgentState) -> AgentState:
    """Create a short action plan and consider KB context."""
    tracer = get_tracer()
    trace_store = get_trace_store()
    chat_id = state.get("chat_id", "unknown")
    
    with tracer.start_as_current_span("agent.plan") as span:
        start_time = time.time()
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("node", "plan")
        
        # Record node entry
        trace_store.record_node_enter(
            chat_id=chat_id,
            node="plan",
            trace_id=current_trace_id(),
            span_id=current_span_id()
        )
        
        try:
            llm = _llm()
            # Retrieve recent KB passages for context (RAG pre-plan)
            user_text = state["messages"][-1].content if state["messages"] else ""
            kb_hits = mem.kb_search(user_text, k=5)
            kb_context = "\n\n".join(f"- {h['text'][:500]}" for h in kb_hits if 'text' in h)

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM),
                ("system", "Internal knowledge that may be relevant:\n{kb}"),
                ("human", "User request:\n{user}\n\nProduce a 3-6 step action plan. Identify tools to use. Do not execute.")
            ])
            messages = prompt.format_messages(user=user_text, kb=kb_context or "None")
            
            resp = _traced_llm_invoke(llm, messages, chat_id, "plan")
            plan = resp.content
            
            state["messages"].append(AIMessage(content=f"Plan:\n{plan}"))
            state["plan"] = plan
            state["next_action"] = "decide"
            
            # Record timing and success
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("latency_ms", duration_ms)
            span.set_attribute("success", True)
            span.set_attribute("kb_hits", len(kb_hits))
            record_latency(duration_ms, "agent.plan")
            
            # Record node exit
            trace_store.record_node_exit(
                chat_id=chat_id,
                node="plan",
                trace_id=current_trace_id(),
                span_id=current_span_id(),
                metadata={"latency_ms": duration_ms, "kb_hits": len(kb_hits)}
            )
            
            return state
            
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            logger.error(f"Error in planner_node: {e}")
            raise


def decide_node(state: AgentState) -> AgentState:
    """Choose next action label."""
    tracer = get_tracer()
    trace_store = get_trace_store()
    chat_id = state.get("chat_id", "unknown")
    
    with tracer.start_as_current_span("agent.decide") as span:
        start_time = time.time()
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("node", "decide")
        
        # Record node entry
        trace_store.record_node_enter(
            chat_id=chat_id,
            node="decide",
            trace_id=current_trace_id(),
            span_id=current_span_id()
        )
        
        try:
            llm = _llm()
            hist = "\n".join([getattr(m, "content", "") for m in state["messages"][-6:]])
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Decide the immediate next action based on the plan and recent messages."),
                ("human",
                 "Plan:\n{plan}\n\nRecent:\n{hist}\n\nChoose ONE token from: search, fetch, kb_search, calculate, write_file, draft_email, finalize.\nAnswer with the single token only.")
            ])
            messages = prompt.format_messages(plan=state.get("plan", ""), hist=hist)
            
            resp = _traced_llm_invoke(llm, messages, chat_id, "decide")
            next_action = resp.content.strip().lower()
            state["next_action"] = next_action
            
            # Record timing and success
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("latency_ms", duration_ms)
            span.set_attribute("success", True)
            span.set_attribute("next_action", next_action)
            record_latency(duration_ms, "agent.decide")
            
            # Record node exit
            trace_store.record_node_exit(
                chat_id=chat_id,
                node="decide",
                trace_id=current_trace_id(),
                span_id=current_span_id(),
                metadata={"latency_ms": duration_ms, "next_action": next_action}
            )
            
            return state
            
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            logger.error(f"Error in decide_node: {e}")
            raise


def act_node_builder(tools: List[BaseTool]):
    """Bind tools to LLM and cause a structured tool call for the chosen action."""
    llm = _llm().bind_tools(tools)

    def act_node(state: AgentState) -> AgentState:
        tracer = get_tracer()
        trace_store = get_trace_store()
        chat_id = state.get("chat_id", "unknown")
        
        with tracer.start_as_current_span("agent.act") as span:
            start_time = time.time()
            span.set_attribute("chat_id", chat_id)
            span.set_attribute("node", "act")
            
            # Record node entry
            trace_store.record_node_enter(
                chat_id=chat_id,
                node="act",
                trace_id=current_trace_id(),
                span_id=current_span_id()
            )
            
            try:
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
                
                span.set_attribute("action", action)
                span.set_attribute("tool_name", tool_name or "none")
                
                if not tool_name:
                    # If finalize or unknown, move to reflection
                    state["messages"].append(AIMessage(content="Reflecting on gathered info..."))
                    span.set_attribute("skipped", True)
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
                
                resp = _traced_llm_invoke(llm, prompt, chat_id, "act")
                # The ToolNode will execute based on tool_calls present in resp
                state["messages"].append(resp)
                
                # Record timing and success
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("success", True)
                record_latency(duration_ms, "agent.act")
                
                # Record node exit
                trace_store.record_node_exit(
                    chat_id=chat_id,
                    node="act",
                    trace_id=current_trace_id(),
                    span_id=current_span_id(),
                    metadata={"latency_ms": duration_ms, "action": action, "tool_name": tool_name}
                )
                
                return state
                
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error in act_node: {e}")
                raise

    return act_node


def reflect_node(state: AgentState) -> AgentState:
    tracer = get_tracer()
    trace_store = get_trace_store()
    chat_id = state.get("chat_id", "unknown")
    
    with tracer.start_as_current_span("agent.reflect") as span:
        start_time = time.time()
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("node", "reflect")
        
        # Record node entry
        trace_store.record_node_enter(
            chat_id=chat_id,
            node="reflect",
            trace_id=current_trace_id(),
            span_id=current_span_id()
        )
        
        try:
            llm = _llm()
            notes = "\n".join(m.content for m in state["messages"] if isinstance(m, AIMessage))
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "If enough information exists, write BRIEFING with bullet points and include citations as URLs at the end. Otherwise propose NEXT:<action>."),
                ("human", "Notes so far:\n{notes}")
            ])
            messages = prompt.format_messages(notes=notes[:6000])
            
            resp = _traced_llm_invoke(llm, messages, chat_id, "reflect")
            txt = resp.content.strip()
            
            if txt.startswith("BRIEFING"):
                state["messages"].append(AIMessage(content=txt))
                state["done"] = True
                span.set_attribute("decision", "finalize")
            else:
                next_action = txt.split(":", 1)[-1].strip().lower()
                state["next_action"] = next_action
                span.set_attribute("decision", "continue")
                span.set_attribute("next_action", next_action)
            
            # Record timing and success
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("latency_ms", duration_ms)
            span.set_attribute("success", True)
            record_latency(duration_ms, "agent.reflect")
            
            # Record node exit
            trace_store.record_node_exit(
                chat_id=chat_id,
                node="reflect",
                trace_id=current_trace_id(),
                span_id=current_span_id(),
                metadata={"latency_ms": duration_ms, "done": state.get("done", False)}
            )
            
            return state
            
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            logger.error(f"Error in reflect_node: {e}")
            raise


def finalize_node(state: AgentState) -> AgentState:
    tracer = get_tracer()
    trace_store = get_trace_store()
    chat_id = state.get("chat_id", "unknown")
    
    with tracer.start_as_current_span("agent.finalize") as span:
        start_time = time.time()
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("node", "finalize")
        
        # Record node entry
        trace_store.record_node_enter(
            chat_id=chat_id,
            node="finalize",
            trace_id=current_trace_id(),
            span_id=current_span_id()
        )
        
        state["done"] = True
        
        # Record timing
        duration_ms = (time.time() - start_time) * 1000
        span.set_attribute("latency_ms", duration_ms)
        span.set_attribute("success", True)
        record_latency(duration_ms, "agent.finalize")
        
        # Record node exit
        trace_store.record_node_exit(
            chat_id=chat_id,
            node="finalize",
            trace_id=current_trace_id(),
            span_id=current_span_id(),
            metadata={"latency_ms": duration_ms}
        )
        
        return state


# ---- Graph build ----
def build_graph(tools: List[BaseTool]):
    from ..layers.tools import TracedToolNode
    g = StateGraph(AgentState)

    g.add_node("plan", planner_node)
    g.add_node("decide", decide_node)
    g.add_node("act", act_node_builder(tools))
    g.add_node("tools", TracedToolNode(tools))  # Use traced tool node
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
