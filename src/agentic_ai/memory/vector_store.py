from __future__ import annotations
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

class VectorStore:
    def __init__(self, persist_dir: str = ".chroma", name: str = "knowledge_base"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=name, embedding_function=embedding_functions.DefaultEmbeddingFunction()
        )

    def add_doc(self, doc_id: str, text: str, metadata: dict | None = None):
        self.collection.add(ids=[doc_id], documents=[text], metadatas=[metadata or {}])

    def search(self, query: str, k: int = 5) -> list[dict]:
        res = self.collection.query(query_texts=[query], n_results=k)
        out = []
        for i, doc in enumerate(res.get("documents", [[]])[0]):
            out.append({
                "id": res["ids"][0][i],
                "text": doc,
                "metadata": (res.get("metadatas") or [[{}]])[0][i]
            })
        return out
