"""Session orchestration helpers for the Agentic Coding Pipeline UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List
from uuid import uuid4

from agents.coding import CodingAgent
from agents.formatting import FormattingAgent
from agents.qa import QAAgent
from agents.testing import TestingAgent
from pipeline import AgenticCodingPipeline

from agentic_ai.llm import ClaudeClient, GeminiClient, OpenAIClient


class StageStatus(str, Enum):
    """Simple status tags for the front-end timeline."""

    PENDING = "pending"
    ACTIVE = "active"
    AWAITING = "awaiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TimelineStage:
    """Track progress for a pipeline stage."""

    id: str
    title: str
    description: str
    status: StageStatus = StageStatus.PENDING
    artifacts: Dict[str, object] = field(default_factory=dict)
    feedback: str | None = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "artifacts": self.artifacts,
            "feedback": self.feedback,
        }


@dataclass
class ChatMessage:
    """Representation of a chat message for the UI."""

    role: str
    content: str
    stage: str | None = None
    kind: str = "message"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    attachments: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "stage": self.stage,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "attachments": self.attachments,
        }


class CodingPipelineSession:
    """Stateful controller that advances the coding pipeline stage-by-stage."""

    def __init__(self, task: str):
        self.id = str(uuid4())
        self.task = task.strip()
        self.base_task = self.task
        self.pipeline = AgenticCodingPipeline(
            coders=[
                CodingAgent(name="gpt-coder", llm=OpenAIClient()),
                CodingAgent(name="claude-coder", llm=ClaudeClient()),
            ],
            formatters=[FormattingAgent(name="formatter")],
            testers=[TestingAgent(name="tester", llm=ClaudeClient())],
            reviewers=[QAAgent(name="qa", llm=GeminiClient())],
        )
        self.instructions: List[str] = []
        self.state: Dict[str, object] = {"task": self.task}
        self.messages: List[ChatMessage] = [
            ChatMessage(role="user", content=self.task, stage="intake", kind="task")
        ]
        self.timeline = [
            TimelineStage(
                id="coding",
                title="Multimodel Coding",
                description="Two specialist coders draft or revise the implementation in parallel.",
            ),
            TimelineStage(
                id="review",
                title="Human-in-the-loop Review",
                description="You inspect the diff, annotate issues, and decide whether to rerun the coders.",
            ),
            TimelineStage(
                id="formatting",
                title="Auto Formatting",
                description="Style and structure corrections ensure the patch is clean and readable.",
            ),
            TimelineStage(
                id="testing",
                title="Test Orchestration",
                description="Pytest suites are generated and executed when you green-light the run.",
            ),
            TimelineStage(
                id="qa",
                title="LLM QA Review",
                description="A QA agent double-checks requirements and summarizes shipping notes.",
            ),
        ]
        self.stage_pointer = "coding"
        self.timeline[0].status = StageStatus.ACTIVE
        self.run_coders()

    # ------------------------------------------------------------------
    # Internal helpers
    def _update_stage(self, stage_id: str, **changes: object) -> None:
        for stage in self.timeline:
            if stage.id == stage_id:
                for key, value in changes.items():
                    setattr(stage, key, value)
                return
        raise ValueError(f"Unknown stage id: {stage_id}")

    def _get_stage(self, stage_id: str) -> TimelineStage:
        for stage in self.timeline:
            if stage.id == stage_id:
                return stage
        raise ValueError(f"Unknown stage id: {stage_id}")

    def _append_message(
        self,
        role: str,
        content: str,
        *,
        stage: str | None = None,
        kind: str = "message",
        attachments: Dict[str, object] | None = None,
    ) -> None:
        self.messages.append(
            ChatMessage(
                role=role,
                content=content,
                stage=stage,
                kind=kind,
                attachments=attachments or {},
            )
        )

    # ------------------------------------------------------------------
    # Stage runners
    def run_coders(self) -> None:
        """Execute all coder agents and capture their proposals."""

        self.stage_pointer = "review"
        stage = self._get_stage("coding")
        stage.status = StageStatus.ACTIVE
        proposals: Dict[str, str] = {}
        for coder in self.pipeline.coders:
            result = coder.run(self.state)
            self.state.update(result)
            proposals[coder.name] = str(self.state.get("proposed_code", "")).strip()
        stage.status = StageStatus.COMPLETED
        stage.artifacts = {
            "proposed_code": self.state.get("proposed_code"),
            "coders": proposals,
        }
        summary_lines = [
            "The coding swarm produced a candidate implementation.",
        ]
        for name, snippet in proposals.items():
            preview = snippet.splitlines()[:12]
            formatted = "\n".join(preview)
            summary_lines.append(f"**{name}** preview:\n```python\n{formatted}\n```")
        self._append_message(
            "assistant",
            "\n\n".join(summary_lines),
            stage="coding",
            kind="stage-update",
            attachments=stage.artifacts,
        )
        self._update_stage("review", status=StageStatus.AWAITING)

    def apply_feedback(self, action: str, comment: str | None = None) -> None:
        """Handle human review decisions and optionally rerun the coders."""

        action = action.lower()
        comment = (comment or "").strip()
        if action not in {"approve", "revise"}:
            raise ValueError("action must be either 'approve' or 'revise'")

        if comment:
            self.instructions.append(comment)
            self._append_message("user", comment, stage="review", kind="feedback")

        review_stage = self._get_stage("review")
        if action == "revise":
            review_stage.status = StageStatus.ACTIVE
            self._update_stage("coding", status=StageStatus.ACTIVE)
            enriched_task = self.base_task
            if self.instructions:
                enriched_task += "\n\nHuman feedback:\n" + "\n".join(
                    f"- {item}" for item in self.instructions
                )
            self.state["task"] = enriched_task
            self.run_coders()
            return

        # Approve path
        review_stage.status = StageStatus.COMPLETED
        self._update_stage("formatting", status=StageStatus.ACTIVE)
        self.run_formatters()

    def run_formatters(self) -> None:
        stage = self._get_stage("formatting")
        formatted_versions: Dict[str, str] = {}
        for formatter in self.pipeline.formatters:
            result = formatter.run(self.state)
            self.state.update(result)
            formatted_versions[formatter.name] = str(self.state.get("proposed_code", ""))
        stage.status = StageStatus.COMPLETED
        stage.artifacts = {
            "formatted_code": self.state.get("proposed_code"),
            "formatters": formatted_versions,
        }
        self._append_message(
            "assistant",
            "Formatter agents polished the code and synchronized style checks.",
            stage="formatting",
            kind="stage-update",
            attachments=stage.artifacts,
        )
        self._update_stage("testing", status=StageStatus.AWAITING)
        self.stage_pointer = "testing"

    def run_tests(self) -> None:
        stage = self._get_stage("testing")
        stage.status = StageStatus.ACTIVE
        aggregated_output: List[str] = []
        tests_passed = True
        for tester in self.pipeline.testers:
            result = tester.run(self.state)
            self.state.update(result)
            aggregated_output.append(str(self.state.get("test_output", "")))
            if not self.state.get("tests_passed"):
                tests_passed = False
        combined_output = "\n".join(aggregated_output).strip()
        stage.artifacts = {
            "tests_passed": tests_passed,
            "test_output": combined_output,
        }
        if tests_passed:
            stage.status = StageStatus.COMPLETED
            self._append_message(
                "assistant",
                "✅ Automated tests passed. You're clear to send the patch to QA.",
                stage="testing",
                kind="stage-update",
                attachments=stage.artifacts,
            )
            self._update_stage("qa", status=StageStatus.AWAITING)
            self.stage_pointer = "qa"
        else:
            stage.status = StageStatus.FAILED
            self._append_message(
                "assistant",
                "❌ Tests failed. Review the logs and send feedback for another coding pass.",
                stage="testing",
                kind="stage-update",
                attachments=stage.artifacts,
            )
            self._update_stage("review", status=StageStatus.AWAITING)
            self.stage_pointer = "review"

    def run_qa(self) -> None:
        stage = self._get_stage("qa")
        stage.status = StageStatus.ACTIVE
        qa_reports: Dict[str, str] = {}
        all_passed = True
        for reviewer in self.pipeline.reviewers:
            result = reviewer.run(self.state)
            self.state.update(result)
            qa_reports[reviewer.name] = str(self.state.get("qa_output", ""))
            if not self.state.get("qa_passed"):
                all_passed = False
        stage.artifacts = {
            "qa_passed": all_passed,
            "qa_reports": qa_reports,
        }
        if all_passed:
            stage.status = StageStatus.COMPLETED
            self._append_message(
                "assistant",
                "🎉 QA approved the patch and compiled release notes.",
                stage="qa",
                kind="stage-update",
                attachments=stage.artifacts,
            )
        else:
            stage.status = StageStatus.FAILED
            self._append_message(
                "assistant",
                "⚠️ QA flagged issues. Provide guidance to re-run the coders.",
                stage="qa",
                kind="stage-update",
                attachments=stage.artifacts,
            )
            self._update_stage("review", status=StageStatus.AWAITING)
            self.stage_pointer = "review"
            return

        self.stage_pointer = "complete"
        self.state["status"] = "completed"

    # ------------------------------------------------------------------
    # Serialization helpers
    def to_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.id,
            "task": self.task,
            "stage": self.stage_pointer,
            "messages": [message.to_dict() for message in self.messages],
            "timeline": [stage.to_dict() for stage in self.timeline],
            "state": {
                key: value
                for key, value in self.state.items()
                if key in {"status", "proposed_code", "tests_passed", "qa_passed", "feedback"}
            },
            "instructions": self.instructions,
        }


class SessionStore:
    """In-memory store for active sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, CodingPipelineSession] = {}

    def create(self, task: str) -> CodingPipelineSession:
        session = CodingPipelineSession(task)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> CodingPipelineSession:
        if session_id not in self._sessions:
            raise KeyError(session_id)
        return self._sessions[session_id]

    def serialize(self, session_id: str) -> Dict[str, object]:
        return self.get(session_id).to_dict()


store = SessionStore()
"""Global session store used by the FastAPI app."""
