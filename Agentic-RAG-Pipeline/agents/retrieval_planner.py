from core.llm import call_gemini, safe_json_loads
from core.structs import AgentResult
from agents.base import Agent

RETR_PLAN_SYS = """Given a sub-goal, write 3-8 diverse search queries.
Return ONLY JSON: {"queries":["..."], "k": 8}"""

class RetrievalPlannerAgent(Agent):
    name: str = "retrieval_planner"
    system_prompt: str = RETR_PLAN_SYS

    def run(self, subgoal: str) -> AgentResult:
        txt = call_gemini(self.system_prompt, subgoal, temperature=0.2, max_output_tokens=256)
        data = safe_json_loads(txt) or {"queries":[subgoal], "k": 6}
        # enforce bounds
        if not isinstance(data.get("queries"), list) or not data["queries"]:
            data["queries"] = [subgoal]
        data["k"] = max(4, min(12, int(data.get("k", 6))))
        return AgentResult(output=data)
