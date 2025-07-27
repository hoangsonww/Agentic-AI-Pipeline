from __future__ import annotations
from ..config import settings
from ..infra.logging import logger
from ..memory.sql_store import SQLStore
from ..memory.vector_store import VectorStore

sql = SQLStore(sqlite_path=settings.SQLITE_PATH)
vs = VectorStore(persist_dir=settings.CHROMA_DIR)


def save_turn(chat_id: str, role: str, content: str, tool_call: str | None = None):
    sql.save_message(chat_id, role, content, tool_call)


def history(chat_id: str) -> list[dict]:
    return sql.fetch_messages(chat_id)


def add_feedback(chat_id: str, message_id: int | None, rating: int, comment: str | None):
    sql.add_feedback(chat_id, message_id, rating, comment)


def kb_add(doc_id: str, text: str, metadata: dict | None = None):
    vs.add_doc(doc_id, text, metadata)


def kb_search(query: str, k: int = 5) -> list[dict]:
    return vs.search(query, k=k)
