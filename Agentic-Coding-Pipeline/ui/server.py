"""FastAPI app serving the Agentic Coding Pipeline chat UI."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .session import store

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Agentic Coding Pipeline UI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSessionRequest(BaseModel):
    task: str = Field(..., min_length=5, description="High level coding goal")


class FeedbackRequest(BaseModel):
    action: Literal["approve", "revise"]
    comment: str | None = Field(default=None, description="Optional feedback or review notes")


class AdvanceRequest(BaseModel):
    action: Literal["run_tests", "send_to_qa"]


@app.post("/api/sessions")
def create_session(payload: CreateSessionRequest) -> dict:
    session = store.create(payload.task)
    return session.to_dict()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return store.serialize(session_id)
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/sessions/{session_id}/feedback")
def send_feedback(session_id: str, payload: FeedbackRequest) -> dict:
    try:
        session = store.get(session_id)
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=404, detail="Session not found") from exc

    try:
        session.apply_feedback(payload.action, payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@app.post("/api/sessions/{session_id}/advance")
def advance(session_id: str, payload: AdvanceRequest) -> dict:
    try:
        session = store.get(session_id)
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=404, detail="Session not found") from exc

    if payload.action == "run_tests":
        if session.stage_pointer != "testing":
            raise HTTPException(status_code=409, detail="Testing stage not ready")
        session.run_tests()
    elif payload.action == "send_to_qa":
        if session.stage_pointer != "qa":
            raise HTTPException(status_code=409, detail="QA stage not ready")
        session.run_qa()
    return session.to_dict()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
