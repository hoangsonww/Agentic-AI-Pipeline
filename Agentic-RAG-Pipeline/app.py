import os
import sys
from dotenv import load_dotenv

from core.vector import FAISSIndex, ingest_corpus
from core.memory import SessionMemory
from core.tools import WebSearch
from graph.orchestrator import Orchestrator

def ensure_env(var):
    val = os.getenv(var)
    if not val and var == "GOOGLE_API_KEY":
        raise RuntimeError("GOOGLE_API_KEY is required. Set it in your environment.")
    return val

def main():
    load_dotenv()

    # --- Keys / config ---
    ensure_env("GOOGLE_API_KEY")
    cse_key = os.getenv("CSE_API_KEY")
    cse_engine = os.getenv("CSE_ENGINE_ID")

    # --- Vector store (index corpus/) ---
    vindex = FAISSIndex(dim=768)  # Google text-embedding-004 is 768-dim
    corpus_dir = os.getenv("CORPUS_DIR", "corpus")
    if os.path.isdir(corpus_dir):
        print(f"[ingest] Loading corpus from: {corpus_dir}")
        added = ingest_corpus(vindex, corpus_dir)
        print(f"[ingest] Added {added} chunks.")
    else:
        print("[ingest] No corpus/ directory found. Running with empty vector store.")

    # --- Web search (optional) ---
    web = None
    if cse_key and cse_engine:
        web = WebSearch(api_key=cse_key, engine_id=cse_engine)
        print("[web] Google Programmable Search enabled.")
    else:
        print("[web] Web search disabled (set CSE_API_KEY & CSE_ENGINE_ID to enable).")

    # --- Memory ---
    memory = SessionMemory()  # in-process JSONL-style memory

    # --- Orchestrator ---
    orc = Orchestrator(vector_idx=vindex, web_tool=web, memory=memory)

    # --- CLI loop ---
    print("\nAgentic RAG (Gemini) — ask me something (Ctrl+C to exit)\n")
    session_id = "demo_session"

    while True:
        try:
            q = input(">>> ")
            if not q.strip():
                continue
            result = orc.answer(session_id=session_id, user_msg=q)
            print("\n--- Answer ---\n")
            print(result["answer"])
            # Show citations summary
            if result.get("citations"):
                print("\n--- Sources ---")
                seen = set()
                idx = 1
                for ev in result["citations"]:
                    uid = (ev.get("meta", {}).get("uri") or ev.get("meta", {}).get("title") or ev.get("text")[:80]).strip()
                    if uid in seen:
                        continue
                    seen.add(uid)
                    title = ev.get("meta", {}).get("title") or ev.get("meta", {}).get("uri") or "local chunk"
                    src = ev.get("meta", {}).get("uri") or "local"
                    print(f"[{idx}] {title} — {src}")
                    idx += 1
            print("\n")
        except KeyboardInterrupt:
            print("\nbye!")
            sys.exit(0)
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
