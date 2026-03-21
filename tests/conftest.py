import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Ensure src/ is on PYTHONPATH so `agentic_ai` and `mcp` packages are importable
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default env vars for tests (avoid hitting real APIs)
os.environ.setdefault("MODEL_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("CHROMA_DIR", str(ROOT / ".chroma"))
os.environ.setdefault("SQLITE_PATH", str(ROOT / ".sqlite" / "agent.test.db"))
