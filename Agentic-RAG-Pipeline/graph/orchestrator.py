import json
from typing import List, Dict, Any

from agents.intent import IntentAgent
from agents.planner import PlannerAgent
from agents.retrieval_planner import RetrievalPlannerAgent
from agents.retrievers import VectorRetriever, WebRetriever
from agents.writer import WriterAgent
from agents.critic import CriticAgent
from agents.guardrails import GuardrailsAgent

from core.memory import SessionMemory
from core.vector import FAISSIndex

def _dedupe_evidence(ev: List[Dict[str, Any]], max_len: int = 40) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for e in ev:
        key = (e.get("meta", {}).get("uri") or e.get("doc_id"), e.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= max_len:
            break
    return out

class Orchestrator:
    def __init__(self, vector_idx: FAISSIndex, web_tool, memory: SessionMemory):
        self.intent = IntentAgent()
        self.planner = PlannerAgent()
        self.ret_planner = RetrievalPlannerAgent()
        self.vec = VectorRetriever(vector_idx)
        self.web = WebRetriever(web_tool) if web_tool else None
        self.writer = WriterAgent()
        self.critic = CriticAgent()
        self.guard = GuardrailsAgent()
        self.memory = memory

    def answer(self, session_id: str, user_msg: str):
        # Memory
        self.memory.append(session_id, "user", user_msg)

        # Intent & Plan
        intent = self.intent.run(user_msg=user_msg).output
        plan = self.planner.run(user_msg=user_msg, intent_json=intent).output

        all_evidence: List[Dict[str, Any]] = []

        # Execute each subtask (serial for determinism)
        for st in plan:
            rp = self.ret_planner.run(subgoal=st["goal"]).output
            queries, k = rp["queries"], rp.get("k", 6)

            local: List[Dict[str, Any]] = []
            for q in queries:
                # Vector search
                v = self.vec.run(q, k=max(2, k // 2))
                local.extend([e.dict() for e in v.evidence])

                # Web search if available
                if self.web:
                    w = self.web.run(q, k=max(2, k - max(2, k // 2)))
                    local.extend([e.dict() for e in w.evidence])

            # Dedupe per subtask
            local = _dedupe_evidence(local, max_len=20)
            all_evidence.extend(local)

        # Global dedupe and cap
        all_evidence = _dedupe_evidence(all_evidence, max_len=50)

        # Writer
        writer = self.writer.run(question=user_msg, evidence=all_evidence)
        draft = writer.output  # dict with status/draft/missing

        # Critic pass if needed or if writer requested more
        need_more = draft.get("status") != "ok"
        if not need_more:
            # Still run a lightweight critic to catch missing cites
            critic = self.critic.run(draft=draft.get("draft",""), evidence=all_evidence).output
            if not critic.get("ok") and critic.get("followup_queries"):
                need_more = True
                followups = critic.get("followup_queries")[:4]
                for q in followups:
                    v = self.vec.run(q, k=4)
                    all_evidence.extend([e.dict() for e in v.evidence])
                    if self.web:
                        w = self.web.run(q, k=4)
                        all_evidence.extend([e.dict() for e in w.evidence])
                all_evidence = _dedupe_evidence(all_evidence, max_len=60)
                writer = self.writer.run(question=user_msg, evidence=all_evidence)
                draft = writer.output

        # Guard
        final = self.guard.run(text=draft.get("draft", "")).output
        self.memory.append(session_id, "assistant", final)

        return {"answer": final, "citations": all_evidence}
