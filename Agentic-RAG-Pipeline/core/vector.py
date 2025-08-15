import os
import glob
from typing import List, Tuple, Dict, Any
import numpy as np
import faiss

from core.llm import embed_text

def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    return vectors / norms

def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Simple char-based chunker. Production systems should use token-aware splitters.
    """
    text = text.replace("\r\n", "\n")
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + chunk_size, n)
        chunks.append(text[i:end])
        i = end - overlap
        if i <= 0:
            i = end
    return [c.strip() for c in chunks if c.strip()]

class FAISSIndex:
    """
    Inner-product FAISS index with unit-length vectors. Stores tuples of:
    (doc_id, chunk_id, text, meta)
    """
    def __init__(self, dim=768):
        self.index = faiss.IndexFlatIP(dim)
        self._vecs = np.zeros((0, dim), dtype="float32")
        self.docs: List[Tuple[str, str, str, Dict[str, Any]]] = []
        self.dim = dim

    def _add_vectors(self, vecs: np.ndarray):
        if vecs.dtype != np.float32:
            vecs = vecs.astype("float32")
        self._vecs = np.vstack([self._vecs, vecs]) if self._vecs.size else vecs
        self.index.add(vecs)

    def add(self, chunks: List[Tuple[str, str, str, Dict[str, Any]]]):
        """
        chunks: list of (doc_id, chunk_id, text, meta)
        """
        self.docs.extend(chunks)
        embeddings = []
        for _, _, txt, _ in chunks:
            emb = embed_text(txt, task_type="retrieval_document")
            embeddings.append(emb)
        mat = _normalize(np.array(embeddings, dtype="float32"))
        self._add_vectors(mat)

    def search(self, query: str, k: int = 8) -> List[Dict[str, Any]]:
        qvec = embed_text(query, task_type="retrieval_query")
        qv = _normalize(np.array([qvec], dtype="float32"))
        sims, ids = self.index.search(qv, min(k, len(self.docs) or 1))
        results: List[Dict[str, Any]] = []
        for idx in ids[0]:
            if idx == -1 or idx >= len(self.docs):
                continue
            doc = self.docs[idx]
            results.append({
                "doc_id": doc[0],
                "chunk_id": doc[1],
                "text": doc[2],
                "meta": doc[3]
            })
        return results

def ingest_corpus(index: FAISSIndex, path: str) -> int:
    """
    Ingests .txt/.md files under path into the FAISS index.
    Returns number of chunks added.
    """
    added = 0
    files = sorted(glob.glob(os.path.join(path, "**", "*.*"), recursive=True))
    support_ext = {".txt", ".md"}
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        if ext not in support_ext:
            continue
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        chunks = _chunk_text(text)
        bundle = []
        for i, ch in enumerate(chunks):
            meta = {"uri": fp, "title": os.path.basename(fp)}
            bundle.append((fp, f"{i}", ch, meta))
        if bundle:
            index.add(bundle)
            added += len(bundle)
    return added
