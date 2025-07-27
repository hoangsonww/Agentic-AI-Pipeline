from __future__ import annotations
from langchain.tools import BaseTool
import json, math, pathlib


class Calculator(BaseTool):
    name = "calculator"
    description = "Evaluate a safe math expression using Python math. Input: expression string. Output: result string."

    def _run(self, expression: str) -> str:
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed["__builtins__"] = {}
        try:
            return str(eval(expression, allowed, {}))
        except Exception as e:
            return f"ERROR: {e}"


class FileWrite(BaseTool):
    name = "file_write"
    description = "Write content to a relative path under ./data/agent_output. Input JSON {path, content}. Output: absolute path."
    base = pathlib.Path("data/agent_output").absolute()

    def _run(self, spec: str) -> str:
        obj = json.loads(spec)
        p = self.base / obj["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(obj["content"], encoding="utf-8")
        return str(p)


class Emailer(BaseTool):
    name = "emailer"
    description = "Draft + queue an email (mock). Input JSON {to, subject, body}. Output: stored .eml path."
    out = pathlib.Path("data/emails").absolute()

    def _run(self, spec: str) -> str:
        self.out.mkdir(parents=True, exist_ok=True)
        obj = json.loads(spec)
        fn = (obj.get("subject", "email").strip().replace(" ", "_"))[:60] + ".eml"
        p = self.out / fn
        p.write_text(f"To: {obj[to]}\nSubject: {obj[subject]}\n\n{obj[body]}", encoding="utf-8")
        return str(p)
