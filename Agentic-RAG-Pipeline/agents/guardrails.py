import re
from agents.base import Agent
from core.structs import AgentResult

class GuardrailsAgent(Agent):
    name: str = "guardrails"

    def run(self, text: str) -> AgentResult:
        # Minimal PII masker (email, phone)
        out = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
        out = re.sub(r"\+?\d[\d\-\s]{7,}\d", "[redacted-phone]", out)
        return AgentResult(output=out)
