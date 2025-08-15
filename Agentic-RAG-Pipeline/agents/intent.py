from core.llm import call_gemini, safe_json_loads, GEMINI_FLASH
from core.structs import AgentResult
from agents.base import Agent

INTENT_SYS = """You classify the user's request.
Return ONLY valid minified JSON with keys:
{"intents":["answer|summarize|troubleshoot|plan|code|search_only|tool_only"],
 "safety":["pii_policy"?],
 "urgency":"low|medium|high",
 "notes":"short note"}"""

class IntentAgent(Agent):
    name: str = "intent"
    system_prompt: str = INTENT_SYS

    def run(self, user_msg: str) -> AgentResult:
        txt = call_gemini(self.system_prompt, user_msg, model_name=GEMINI_FLASH, temperature=0.1, max_output_tokens=256)
        data = safe_json_loads(txt) or {"intents": ["answer"], "safety": [], "urgency": "low", "notes": ""}
        return AgentResult(output=data)
