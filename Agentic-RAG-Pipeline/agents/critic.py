import json
from agents.base import Agent
from core.llm import call_gemini, safe_json_loads
from core.structs import AgentResult

CRITIC_SYS = """Critique the draft vs provided evidence.
Find unsupported claims, contradictions, or missing coverage.
Return ONLY JSON:
{"ok": bool,
 "issues": ["..."],
 "followup_queries": ["short, targeted queries to fill gaps"]}"""

class CriticAgent(Agent):
    name: str = "critic"
    system_prompt: str = CRITIC_SYS

    def run(self, draft: str, evidence: list) -> AgentResult:
        ev = [{"uri": e.get("meta",{}).get("uri","local"), "text": e.get("text","")[:1000]} for e in evidence[:18]]
        prompt = f"Draft:\n{draft}\n\nEvidence:\n{json.dumps(ev, ensure_ascii=False)}"
        txt = call_gemini(self.system_prompt, prompt, temperature=0.1, max_output_tokens=512)
        data = safe_json_loads(txt) or {"ok": True, "issues": [], "followup_queries": []}
        return AgentResult(output=data)
