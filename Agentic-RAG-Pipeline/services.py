"""Runtime services for Agentic-RAG-Pipeline (UI + API integration).

Exposes a shared FAISS index, session memory, optional web search tool, and an
Orchestrator instance. Provides helpers for querying and for multimodal
ingestion (text, URL, and common file types).
"""

from __future__ import annotations

import io
import os
import json
import uuid
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from core.vector import FAISSIndex
from core.memory import SessionMemory
from core.tools import WebSearch, fetch_page_text
from graph.orchestrator import Orchestrator

_vindex: Optional[FAISSIndex] = None
_memory: Optional[SessionMemory] = None
_web: Optional[WebSearch] = None
_orc: Optional[Orchestrator] = None


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
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


def init() -> None:
    global _vindex, _memory, _web, _orc
    if _vindex is not None:
        return
    # Init vector index
    _vindex = FAISSIndex(dim=768)
    # Optional corpus ingest
    corpus_dir = os.getenv("CORPUS_DIR", str(Path(__file__).resolve().parent / "corpus"))
    try:
        from core.vector import ingest_corpus
        if os.path.isdir(corpus_dir):
            ingest_corpus(_vindex, corpus_dir)
    except Exception:
        pass
    # Optional web search
    cse_key = os.getenv("CSE_API_KEY")
    cse_engine = os.getenv("CSE_ENGINE_ID")
    _web = WebSearch(api_key=cse_key, engine_id=cse_engine) if cse_key and cse_engine else None
    # Memory + Orchestrator
    _memory = SessionMemory()
    _orc = Orchestrator(vector_idx=_vindex, web_tool=_web, memory=_memory)


def new_session() -> str:
    if _orc is None:
        init()
    return str(uuid.uuid4())


def ask(session_id: str, query: str) -> Dict[str, object]:
    if _orc is None:
        init()
    assert _orc is not None
    return _orc.answer(session_id=session_id, user_msg=query)


def run_rag_stream(session_id: str, query: str) -> Iterator[Tuple[str, str]]:
    """SSE-friendly generator for RAG queries.

    Emits:
    - ("log", ...): progress updates
    - ("answer", <markdown>): final synthesized answer
    - ("sources", <json>): JSON array of citations (deduped)
    - ("done", <json>): summary of run
    """
    yield ("log", "Planning and retrieving evidence...\n")
    result = ask(session_id, query)
    answer = str(result.get("answer", "")).strip()
    cites = result.get("citations") or []
    yield ("answer", answer)
    yield ("sources", json.dumps(cites))
    payload = {"ok": True, "session_id": session_id}
    yield ("done", json.dumps(payload))


# ---------------------- Ingestion (multimodal) ---------------------


def _index_chunks(doc_id: str, text: str, title: Optional[str] = None, tags: Optional[List[str]] = None) -> int:
    if _vindex is None:
        init()
    assert _vindex is not None
    title = title or doc_id
    chunks = _chunk_text(text)
    bundle = []
    for i, ch in enumerate(chunks):
        meta = {"uri": doc_id, "title": title}
        if tags:
            meta["tags"] = tags
        bundle.append((doc_id, str(i), ch, meta))
    if bundle:
        _vindex.add(bundle)
    return len(bundle)


def ingest_text(text: str, doc_id: Optional[str] = None, title: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, object]:
    doc_id = doc_id or f"doc:{uuid.uuid4()}"
    added = _index_chunks(doc_id, text, title, tags)
    return {"ok": True, "id": doc_id, "chunks": added}


def ingest_url(url: str, title: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, object]:
    text = fetch_page_text(url) or ""
    if not text:
        return {"ok": False, "error": "Failed to fetch URL"}
    added = _index_chunks(url, text, title, tags)
    return {"ok": True, "id": url, "chunks": added}


def _extract_text_from_pdf(data: bytes) -> Optional[str]:  # pragma: no cover - optional deps
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        out = []
        for page in reader.pages:
            out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception:
        try:
            # pdfminer.six
            from pdfminer.high_level import extract_text
            return extract_text(io.BytesIO(data))
        except Exception:
            return None


def _extract_text_from_docx(data: bytes) -> Optional[str]:  # pragma: no cover - optional deps
    try:
        import docx
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return None


def _extract_text_from_image(data: bytes) -> Optional[str]:  # pragma: no cover - optional deps
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img)
    except Exception:
        return None


def ingest_file(filename: str, data: bytes, title: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, object]:
    ext = Path(filename).suffix.lower()
    text: Optional[str] = None
    if ext in {".txt", ".md", ".csv", ".log"}:
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = data.decode("latin-1", errors="ignore")
    elif ext == ".pdf":
        text = _extract_text_from_pdf(data)
        if text is None:
            return {"ok": False, "error": "PDF extraction requires pypdf or pdfminer.six"}
    elif ext == ".docx":
        text = _extract_text_from_docx(data)
        if text is None:
            return {"ok": False, "error": "DOCX extraction requires python-docx"}
    elif ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        text = _extract_text_from_image(data)
        if text is None:
            return {"ok": False, "error": "Image OCR requires pillow + pytesseract"}
    else:
        return {"ok": False, "error": f"Unsupported file type: {ext}"}

    if not text or not text.strip():
        return {"ok": False, "error": "No extractable text found"}
    doc_id = f"file:{filename}:{uuid.uuid4()}"
    added = _index_chunks(doc_id, text, title or filename, tags)
    return {"ok": True, "id": doc_id, "chunks": added}

