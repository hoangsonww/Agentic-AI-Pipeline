from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from typing import Any
from ..infra.logging import logger

class SQLStore:
    def __init__(self, sqlite_path: str):
        Path(Path(sqlite_path).parent).mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
        self.Session = sessionmaker(self.engine, future=True)
        self._init()

    def _init(self):
        with self.engine.begin() as conn:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chats (
              id TEXT PRIMARY KEY,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              title TEXT
            )"""))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id TEXT,
              role TEXT,
              content TEXT,
              tool_call TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedback (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id TEXT,
              message_id INTEGER,
              rating INTEGER,
              comment TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""))
        logger.info("SQLStore initialized.")

    def save_message(self, chat_id: str, role: str, content: str, tool_call: str | None = None):
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO messages(chat_id, role, content, tool_call) VALUES(:chat_id,:role,:content,:tool_call)"
            ), {"chat_id": chat_id, "role": role, "content": content, "tool_call": tool_call})

    def fetch_messages(self, chat_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT id, role, content FROM messages WHERE chat_id = :chat_id ORDER BY id ASC"
            ), {"chat_id": chat_id}).all()
        return [{"id": r[0], "role": r[1], "content": r[2]} for r in rows]

    def add_feedback(self, chat_id: str, message_id: int | None, rating: int, comment: str | None):
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO feedback(chat_id, message_id, rating, comment) VALUES(:chat_id,:message_id,:rating,:comment)"
            ), {"chat_id": chat_id, "message_id": message_id, "rating": rating, "comment": comment})
