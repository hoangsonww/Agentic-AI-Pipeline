from __future__ import annotations

import io
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from maping import Recorder
from maping.asgi import MapingMiddleware
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .graph import run_chat
from .infra.logging import logger
from .infra.rate_limit import allow
from .layers import memory as mem
from .tools.webtools import WebFetch

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WEB_DIR = _PROJECT_ROOT / "web"


def _resolve_static(directory: Path, filename: str) -> Path:
    """Resolve a static file; raise 404 if missing."""
    fp = directory / filename
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return fp


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
recorder = Recorder(service="agentic_ai_pipeline")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    # --- startup ---
    await recorder.start()
    try:
        from .social_media_api import init_social_media_services

        init_social_media_services()
        logger.info("Social media services initialized")
    except Exception as exc:
        logger.warning("Social media services unavailable (non-fatal): %s", exc)
    logger.info("Agentic AI server started on %s:%s", settings.APP_HOST, settings.APP_PORT)
    yield
    # --- shutdown ---
    await recorder.shutdown()
    logger.info("Agentic AI server shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Agentic Multi-Stage Bot",
    version="0.4.0",
    lifespan=lifespan,
)

# Include social media router
try:
    from .social_media_api import router as social_media_router

    app.include_router(social_media_router)
except Exception as exc:
    logger.warning("Social media router unavailable: %s", exc)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", response_class=JSONResponse)
def health():
    """Lightweight health probe for load balancers and container orchestrators."""
    return {"status": "ok", "version": "0.4.0"}


# ---------------------------------------------------------------------------
# Static UI routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    fp = _resolve_static(_WEB_DIR, "index.html")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


@app.get("/app.js", response_class=PlainTextResponse)
def js():
    fp = _resolve_static(_WEB_DIR, "app.js")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/styles.css", response_class=PlainTextResponse)
def css():
    fp = _resolve_static(_WEB_DIR, "styles.css")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="text/css")


@app.get("/social_media.html", response_class=HTMLResponse)
def social_media_ui():
    fp = _resolve_static(_WEB_DIR, "social_media.html")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


# ---- Agentic Coding Pipeline UI ----
_ACP_UI = _PROJECT_ROOT / "Agentic-Coding-Pipeline" / "ui"


@app.get("/coding", response_class=HTMLResponse)
def coding_index():
    return HTMLResponse(_resolve_static(_ACP_UI, "index.html").read_text(encoding="utf-8"))


@app.get("/coding/app.js", response_class=PlainTextResponse)
def coding_js():
    return PlainTextResponse(
        _resolve_static(_ACP_UI, "app.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.get("/coding/styles.css", response_class=PlainTextResponse)
def coding_css():
    return PlainTextResponse(
        _resolve_static(_ACP_UI, "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


# ---- Agentic RAG Pipeline UI ----
_RAG_UI = _PROJECT_ROOT / "Agentic-RAG-Pipeline" / "ui"


@app.get("/rag", response_class=HTMLResponse)
def rag_index():
    return HTMLResponse(_resolve_static(_RAG_UI, "index.html").read_text(encoding="utf-8"))


@app.get("/rag/app.js", response_class=PlainTextResponse)
def rag_js():
    return PlainTextResponse(
        _resolve_static(_RAG_UI, "app.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.get("/rag/styles.css", response_class=PlainTextResponse)
def rag_css():
    return PlainTextResponse(
        _resolve_static(_RAG_UI, "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


# ---- Agentic Data Pipeline UI ----
_DATA_UI = _PROJECT_ROOT / "Agentic-Data-Pipeline" / "ui"


@app.get("/data", response_class=HTMLResponse)
def data_index():
    return HTMLResponse(_resolve_static(_DATA_UI, "index.html").read_text(encoding="utf-8"))


@app.get("/data/app.js", response_class=PlainTextResponse)
def data_js():
    return PlainTextResponse(
        _resolve_static(_DATA_UI, "app.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.get("/data/styles.css", response_class=PlainTextResponse)
def data_css():
    return PlainTextResponse(
        _resolve_static(_DATA_UI, "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


# ---------------------------------------------------------------------------
# Core Chat API
# ---------------------------------------------------------------------------
@app.get("/api/new_chat")
def new_chat():
    return {"chat_id": str(uuid.uuid4())}


@app.post("/api/chat")
async def api_chat(payload: dict = Body(...)):
    chat_id = payload.get("chat_id") or str(uuid.uuid4())
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    if not allow(chat_id):
        raise HTTPException(status_code=429, detail="rate limited")

    async def gen():
        async for chunk in run_chat(chat_id, message):
            yield {"event": "token", "data": chunk}
        yield {"event": "done", "data": json.dumps({"chat_id": chat_id})}

    return EventSourceResponse(gen())


# ---------------------------------------------------------------------------
# KB Ingestion
# ---------------------------------------------------------------------------
@app.post("/api/ingest")
def ingest(payload: dict = Body(...)):
    doc_id = payload.get("id") or str(uuid.uuid4())
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    meta = payload.get("metadata") or {}
    mem.kb_add(doc_id, text, meta)
    return {"ok": True, "id": doc_id}


@app.post("/api/ingest_url")
def ingest_url(payload: dict = Body(...)):
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    try:
        fetch = WebFetch()
        text = fetch._run(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"fetch failed: {e}")
    if not text:
        raise HTTPException(status_code=400, detail="no text extracted")
    doc_id = payload.get("id") or url
    meta = payload.get("metadata") or {"source": url}
    mem.kb_add(doc_id, text, meta)
    return {"ok": True, "id": doc_id}


def _extract_text_from_upload(filename: str, data: bytes) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md", ".csv", ".log"}:
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("latin-1", errors="ignore")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            rdr = PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in rdr.pages)
        except Exception:
            try:
                from pdfminer.high_level import extract_text

                return extract_text(io.BytesIO(data))
            except Exception:
                return None
    if ext == ".docx":
        try:
            import docx

            d = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in d.paragraphs)
        except Exception:
            return None
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            return pytesseract.image_to_string(img)
        except Exception:
            return None
    return None


@app.post("/api/ingest_file")
async def ingest_file(request: Request):
    try:
        form = await request.form()
        f = form.get("file")
        if not f:
            raise HTTPException(status_code=400, detail="file required")
        filename = getattr(f, "filename", "upload")
        data = await f.read()
        text = _extract_text_from_upload(filename, data)
        if not text:
            raise HTTPException(
                status_code=415, detail="unsupported file type or missing optional deps"
            )
        doc_id = form.get("id") or f"file:{filename}:{uuid.uuid4()}"
        tags_s = form.get("tags") or ""
        meta = {
            "filename": filename,
            "tags": [t.strip() for t in str(tags_s).split(",") if t.strip()],
        }
        mem.kb_add(doc_id, text, meta)
        return {"ok": True, "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
@app.post("/api/feedback")
def feedback(payload: dict = Body(...)):
    chat_id = payload.get("chat_id")
    rating = int(payload.get("rating", 0))
    comment = payload.get("comment")
    msg_id = payload.get("message_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id required")
    mem.add_feedback(chat_id, msg_id, rating, comment)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Agentic Coding Pipeline API
# ---------------------------------------------------------------------------
def _import_coding_services():
    """Lazy-import coding pipeline services."""
    pipeline_dir = _PROJECT_ROOT / "Agentic-Coding-Pipeline"
    if str(pipeline_dir) not in sys.path:
        sys.path.append(str(pipeline_dir))
    try:
        from services import run_pipeline_stream  # type: ignore[import-untyped]

        return run_pipeline_stream
    except Exception:
        return None


@app.post("/api/coding/run")
def api_coding_run(payload: dict = Body(...)):
    run_pipeline_stream = _import_coding_services()
    if run_pipeline_stream is None:
        raise HTTPException(status_code=503, detail="Coding pipeline services unavailable")
    repo = payload.get("repo")
    jira = payload.get("jira")
    github = payload.get("github")
    text = payload.get("task")
    final = {}
    for ev, data in run_pipeline_stream(repo_input=repo, jira=jira, github=github, text=text):
        if ev == "done":
            try:
                final = json.loads(data)
            except Exception:
                final = {"status": "unknown"}
            break
    return final


@app.post("/api/coding/stream")
async def api_coding_stream(payload: dict = Body(...)):
    run_pipeline_stream = _import_coding_services()
    if run_pipeline_stream is None:
        raise HTTPException(status_code=503, detail="Coding pipeline services unavailable")
    repo = payload.get("repo")
    jira = payload.get("jira")
    github = payload.get("github")
    text = payload.get("task")

    def gen():
        for ev, data in run_pipeline_stream(repo_input=repo, jira=jira, github=github, text=text):
            yield {"event": ev, "data": data}

    return EventSourceResponse(gen())


# ---------------------------------------------------------------------------
# Agentic RAG Pipeline API
# ---------------------------------------------------------------------------
def _import_rag_services():
    """Lazy-import RAG pipeline services."""
    pipeline_dir = _PROJECT_ROOT / "Agentic-RAG-Pipeline"
    if str(pipeline_dir) not in sys.path:
        sys.path.append(str(pipeline_dir))
    from services import (  # type: ignore[import-untyped]
        ingest_file as rag_ingest_file,
    )
    from services import (
        ingest_text as rag_ingest_text,
    )
    from services import (
        ingest_url as rag_ingest_url,
    )
    from services import (
        new_session as rag_new_session,
    )
    from services import (
        run_rag_stream,
    )

    return rag_new_session, run_rag_stream, rag_ingest_text, rag_ingest_url, rag_ingest_file


@app.get("/api/rag/new_session")
def api_rag_new_session():
    rag_new_session, *_ = _import_rag_services()
    return {"session_id": rag_new_session()}


@app.post("/api/rag/ask")
async def api_rag_ask(payload: dict = Body(...)):
    _, rag_stream, *_ = _import_rag_services()
    session_id = payload.get("session_id") or str(uuid.uuid4())
    q = (payload.get("question") or payload.get("query") or payload.get("q") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="question required")

    def gen():
        for ev, data in rag_stream(session_id, q):
            yield {"event": ev, "data": data}

    return EventSourceResponse(gen())


@app.post("/api/rag/ingest_text")
def api_rag_ingest_text(payload: dict = Body(...)):
    *_, rag_ingest_text, rag_ingest_url, _ = _import_rag_services()
    text = (payload.get("text") or "").strip()
    url = (payload.get("url") or "").strip()
    title = payload.get("title")
    tags = payload.get("tags") or []
    if url:
        return rag_ingest_url(url, title=title, tags=tags)
    if not text:
        raise HTTPException(status_code=400, detail="text or url required")
    return rag_ingest_text(text, doc_id=payload.get("id"), title=title, tags=tags)


@app.post("/api/rag/ingest_file")
async def api_rag_ingest_file(request: Request):
    *_, rag_ingest_file = _import_rag_services()
    form = await request.form()
    f = form.get("file")
    if not f:
        raise HTTPException(status_code=400, detail="file required")
    filename = getattr(f, "filename", "upload")
    data = await f.read()
    title = form.get("title")
    tags_s = form.get("tags") or ""
    tags = [t.strip() for t in str(tags_s).split(",") if t.strip()]
    return rag_ingest_file(filename=filename, data=data, title=title, tags=tags)


# ---------------------------------------------------------------------------
# Agentic Data Pipeline API
# ---------------------------------------------------------------------------
def _import_data_services():
    """Lazy-import data pipeline services."""
    pipeline_dir = _PROJECT_ROOT / "Agentic-Data-Pipeline"
    if str(pipeline_dir) not in sys.path:
        sys.path.append(str(pipeline_dir))
    from services import run_data_stream  # type: ignore[import-untyped]

    return run_data_stream


@app.post("/api/data/stream")
async def api_data_stream(payload: dict = Body(...)):
    run_data_stream = _import_data_services()
    source = (payload.get("source") or "text").strip()
    dataset = payload.get("dataset") or ""
    task = payload.get("task")
    if not dataset:
        raise HTTPException(status_code=400, detail="dataset required")

    def gen():
        for ev, data in run_data_stream(source=source, dataset=dataset, task=task):
            yield {"event": ev, "data": data}

    return EventSourceResponse(gen())


@app.post("/api/data/run")
def api_data_run(payload: dict = Body(...)):
    run_data_stream = _import_data_services()
    source = (payload.get("source") or "text").strip()
    dataset = payload.get("dataset") or ""
    task = payload.get("task")
    if not dataset:
        raise HTTPException(status_code=400, detail="dataset required")
    final_report = None
    for ev, data in run_data_stream(source=source, dataset=dataset, task=task):
        if ev == "report":
            final_report = data
    return {"report": final_report or "", "ok": True}


if os.environ.get("MAPING_KEY"):
    app = MapingMiddleware(app, recorder=recorder)
