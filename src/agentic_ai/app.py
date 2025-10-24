from __future__ import annotations
import os, uuid, json, asyncio, io
from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse
from pathlib import Path
import sys
from typing import Optional
from .graph import run_chat
from .layers import memory as mem
from .infra.rate_limit import allow
from .infra.logging import logger
from .tools.webtools import WebFetch

app = FastAPI(title="Agentic Multi-Stage Bot")

# Initialize social media services on startup
from .social_media_api import router as social_media_router, init_social_media_services

app.include_router(social_media_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        init_social_media_services()
        logger.info("Social media services initialized")
    except Exception as e:
        logger.error(f"Failed to initialize social media services: {e}")

# ---------- Static ----------
@app.get("/", response_class=HTMLResponse)
def index():
    # Prefer root web/ if present; otherwise fall back to src/web
    root_web = Path(__file__).resolve().parents[2] / "web" / "index.html"
    src_web = Path(__file__).resolve().parents[1] / "web" / "index.html"
    fp = root_web if root_web.exists() else src_web
    with open(fp, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/app.js", response_class=PlainTextResponse)
def js():
    root_js = Path(__file__).resolve().parents[2] / "web" / "app.js"
    src_js = Path(__file__).resolve().parents[1] / "web" / "app.js"
    fp = root_js if root_js.exists() else src_js
    with open(fp, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read(), media_type="application/javascript")

@app.get("/styles.css", response_class=PlainTextResponse)
def css():
    root_css = Path(__file__).resolve().parents[2] / "web" / "styles.css"
    src_css = Path(__file__).resolve().parents[1] / "web" / "styles.css"
    fp = root_css if root_css.exists() else src_css
    with open(fp, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read(), media_type="text/css")

# ---------- Social Media Automation UI ----------
@app.get("/social_media.html", response_class=HTMLResponse)
def social_media_ui():
    root_html = Path(__file__).resolve().parents[2] / "web" / "social_media.html"
    src_html = Path(__file__).resolve().parents[1] / "web" / "social_media.html"
    fp = root_html if root_html.exists() else src_html
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Social Media UI not found")
    with open(fp, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# ---------- Agentic Coding Pipeline UI ----------

def _acp_ui_root() -> Path:
    # Locate monorepo root, then Agentic-Coding-Pipeline/ui
    return Path(__file__).resolve().parents[2] / "Agentic-Coding-Pipeline" / "ui"


@app.get("/coding", response_class=HTMLResponse)
def coding_index():
    fp = _acp_ui_root() / "index.html"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Coding UI not found")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


@app.get("/coding/app.js", response_class=PlainTextResponse)
def coding_js():
    fp = _acp_ui_root() / "app.js"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/coding/app.js not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/coding/styles.css", response_class=PlainTextResponse)
def coding_css():
    fp = _acp_ui_root() / "styles.css"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/coding/styles.css not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="text/css")

# ---------- Chat ----------
@app.get("/api/new_chat")
def new_chat():
    return {"chat_id": str(uuid.uuid4())}

@app.post("/api/chat")
async def api_chat(payload: dict = Body(...)):
    chat_id = payload.get("chat_id") or str(uuid.uuid4())
    message = payload.get("message","").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    if not allow(chat_id):
        raise HTTPException(status_code=429, detail="rate limited")
    async def gen():
        async for chunk in run_chat(chat_id, message):
            yield {"event": "token", "data": chunk}
        yield {"event": "done", "data": json.dumps({"chat_id": chat_id})}
    return EventSourceResponse(gen())

# ---------- KB Ingestion ----------
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
            out = []
            for p in rdr.pages:
                out.append(p.extract_text() or "")
            return "\n".join(out)
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
            from PIL import Image
            import pytesseract
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
        import io
        text = _extract_text_from_upload(filename, data)
        if not text:
            raise HTTPException(status_code=415, detail="unsupported file type or missing optional deps")
        doc_id = form.get("id") or f"file:{filename}:{uuid.uuid4()}"
        tags_s = form.get("tags") or ""
        meta = {"filename": filename, "tags": [t.strip() for t in str(tags_s).split(",") if t.strip()]}
        mem.kb_add(doc_id, text, meta)
        return {"ok": True, "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Feedback ----------
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

# ---------- Agentic Coding Pipeline API ----------

try:
    # Local import; exists within monorepo
    from Agentic_Coding_Pipeline_services import run_pipeline_stream  # type: ignore
except Exception:
    # Fallback relative import using path adjustments
    root = Path(__file__).resolve().parents[2]
    sys.path.append(str(root / "Agentic-Coding-Pipeline"))
    try:  # noqa: SIM105
        from services import run_pipeline_stream  # type: ignore
    except Exception as e:  # pragma: no cover - if import fails at runtime
        run_pipeline_stream = None  # type: ignore


@app.post("/api/coding/run")
def api_coding_run(payload: dict = Body(...)):
    if run_pipeline_stream is None:
        raise HTTPException(status_code=500, detail="Pipeline services unavailable")
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
    if run_pipeline_stream is None:
        raise HTTPException(status_code=500, detail="Pipeline services unavailable")
    repo = payload.get("repo")
    jira = payload.get("jira")
    github = payload.get("github")
    text = payload.get("task")

    def gen():
        for ev, data in run_pipeline_stream(repo_input=repo, jira=jira, github=github, text=text):
            yield {"event": ev, "data": data}

    return EventSourceResponse(gen())

# ---------- Agentic RAG Pipeline UI + API ----------

def _rag_ui_root() -> Path:
    return Path(__file__).resolve().parents[2] / "Agentic-RAG-Pipeline" / "ui"


@app.get("/rag", response_class=HTMLResponse)
def rag_index():
    fp = _rag_ui_root() / "index.html"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="RAG UI not found")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


@app.get("/rag/app.js", response_class=PlainTextResponse)
def rag_js():
    fp = _rag_ui_root() / "app.js"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/rag/app.js not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/rag/styles.css", response_class=PlainTextResponse)
def rag_css():
    fp = _rag_ui_root() / "styles.css"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/rag/styles.css not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="text/css")


def _import_rag_services():
    root = Path(__file__).resolve().parents[2]
    sys.path.append(str(root / "Agentic-RAG-Pipeline"))
    from services import new_session as rag_new_session, run_rag_stream, ingest_text as rag_ingest_text, ingest_url as rag_ingest_url, ingest_file as rag_ingest_file  # type: ignore
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

# ---------- Agentic Data Pipeline UI + API ----------

def _data_ui_root() -> Path:
    return Path(__file__).resolve().parents[2] / "Agentic-Data-Pipeline" / "ui"


@app.get("/data", response_class=HTMLResponse)
def data_index():
    fp = _data_ui_root() / "index.html"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Data UI not found")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


@app.get("/data/app.js", response_class=PlainTextResponse)
def data_js():
    fp = _data_ui_root() / "app.js"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/data/app.js not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/data/styles.css", response_class=PlainTextResponse)
def data_css():
    fp = _data_ui_root() / "styles.css"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="/data/styles.css not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"), media_type="text/css")


def _import_data_services():
    root = Path(__file__).resolve().parents[2]
    sys.path.append(str(root / "Agentic-Data-Pipeline"))
    from services import run_data_stream  # type: ignore
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
