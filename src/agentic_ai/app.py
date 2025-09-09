from __future__ import annotations
import os, uuid, json, asyncio
from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse
from .graph import run_chat
from .layers import memory as mem
from .infra.rate_limit import allow
from .infra.logging import logger
from .infra.tracing import init_tracing, instrument_fastapi, current_trace_id

# Initialize tracing
init_tracing()

app = FastAPI(title="Agentic Multi-Stage Bot")

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

@app.middleware("http")
async def add_trace_context(request: Request, call_next):
    """Add trace context to request and response headers."""
    response = await call_next(request)
    
    # Add trace ID to response headers for client visibility
    trace_id = current_trace_id()
    if trace_id:
        response.headers["X-Trace-ID"] = trace_id
    
    return response

# ---------- Static ----------
@app.get("/", response_class=HTMLResponse)
def index():
    fp = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    with open(fp, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/app.js", response_class=PlainTextResponse)
def js():
    fp = os.path.join(os.path.dirname(__file__), "..", "web", "app.js")
    with open(fp, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read(), media_type="application/javascript")

@app.get("/styles.css", response_class=PlainTextResponse)
def css():
    fp = os.path.join(os.path.dirname(__file__), "..", "web", "styles.css")
    with open(fp, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read(), media_type="text/css")

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
