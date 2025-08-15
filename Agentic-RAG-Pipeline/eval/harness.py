# Optional lightweight eval harness
# Run: python -m eval.harness
import os
from core.vector import FAISSIndex, ingest_corpus
from core.memory import SessionMemory
from core.tools import WebSearch
from graph.orchestrator import Orchestrator

def run():
    v = FAISSIndex()
    if os.path.isdir("corpus"):
        ingest_corpus(v, "corpus")
    web = None
    if os.getenv("CSE_API_KEY") and os.getenv("CSE_ENGINE_ID"):
        web = WebSearch(os.getenv("CSE_API_KEY"), os.getenv("CSE_ENGINE_ID"))
    orc = Orchestrator(v, web, SessionMemory())
    qs = [
        "Summarize what the corpus is about.",
        "What are the key points across the docs?",
        "Plan steps to achieve the goals described in the corpus."
    ]
    for q in qs:
        out = orc.answer("eval", q)
        print("\nQ:", q)
        print("A:", out["answer"][:500], "...")
        print("Citations:", len(out["citations"]))

if __name__ == "__main__":
    run()
