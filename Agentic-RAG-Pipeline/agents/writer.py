import json
from agents.base import Agent
from core.llm import call_gemini
from core.structs import AgentResult, Evidence

WRITE_SYS = """You are a grounded writer.
Only use the provided evidence array.
If evidence is insufficient, say so and list what's missing.
Cite like [#1], [#2] where #N maps to the evidence index in the provided array.

Return ONLY JSON:
{"status":"ok"|"needs_more",
 "draft":"final answer or partial",
 "missing":["missing items if any"]}"""

class WriterAgent(Agent):
    name: str = "writer"
    system_prompt: str = WRITE_SYS

    def run(self, question: str, evidence: list) -> AgentResult:
        # Build a compact JSON evidence view
        ev_serialized = []
        for i, e in enumerate(evidence, start=1):
            ev_serialized.append({
                "id": i,
                "title": e.get("meta", {}).get("title") or e.get("meta", {}).get("uri") or "local",
                "uri": e.get("meta", {}).get("uri") or "local",
                "text": e.get("text", "")[:1500]
            })
        prompt = f"Question: {question}\nEvidence:\n{json.dumps(ev_serialized, ensure_ascii=False)}"
        txt = call_gemini(self.system_prompt, prompt, temperature=0.2, max_output_tokens=1200)
        # Parse JSON
        try:
            data = json.loads(txt)
        except Exception:
            data = {"status":"ok","draft":txt.strip() or "No answer.","missing":[]}
        return AgentResult(output=data)
