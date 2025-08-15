from core.llm import call_gemini, safe_json_loads
from core.structs import AgentResult
from agents.base import Agent

PLAN_SYS = """Decompose the task into ordered sub-goals.
Reply ONLY valid minified JSON list. Each item must be:
{"id":"s1","goal":"...", "inputs":[],"outputs":["evidence"],"sources":["vector","web","db","tools"],
 "done_test":"what must be proven or retrieved"}"""

class PlannerAgent(Agent):
    name: str = "planner"
    system_prompt: str = PLAN_SYS

    def run(self, user_msg: str, intent_json: dict) -> AgentResult:
        prompt = f"User: {user_msg}\nIntent: {intent_json}"
        txt = call_gemini(self.system_prompt, prompt, temperature=0.2, max_output_tokens=512)
        data = safe_json_loads(txt) or [{"id":"s1","goal":user_msg,"inputs":[],"outputs":["answer"],"sources":["vector","web"],"done_test":"enough evidence to answer"}]
        return AgentResult(output=data)
