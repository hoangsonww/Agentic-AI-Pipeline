"""Shared services for the Agentic-Coding-Pipeline.

This module centralizes logic so both the CLI and the web API can:
- Accept a repository input (URL or local path)
- Optionally resolve a task from a GitHub issue or Jira ticket
- Analyze the repository to produce a concise summary
- Run the AgenticCodingPipeline while streaming progress
"""

from __future__ import annotations

import os
import re
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Dict, Iterable, Iterator, Optional, Tuple

import httpx

from .pipeline import AgenticCodingPipeline
from .agents.coding import CodingAgent
from .agents.formatting import FormattingAgent
from .agents.qa import QAAgent
from .agents.testing import TestingAgent
from agentic_ai.llm import ClaudeClient, GeminiClient, OpenAIClient


# ------------------------------ Data ------------------------------


@dataclass
class RepoContext:
    path: Optional[Path]
    summary: str
    is_cloned: bool = False


@dataclass
class TaskContext:
    source: str  # "text" | "github" | "jira"
    title: str
    description: str


# --------------------------- Repo intake --------------------------


_GIT_URL_RE = re.compile(r"^(https?://|git@).+\.git$|^https?://(www\.)?github\.com/.+/.+")


def _is_probable_git_url(value: str) -> bool:
    v = value.strip()
    return bool(_GIT_URL_RE.match(v))


def _clone_repo(url: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    dest = workdir / "repo"
    try:
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True, capture_output=True)
        return dest
    except Exception as e:  # pragma: no cover - environment dependent
        # Surface a readable error; callers can decide to proceed without repo context
        raise RuntimeError(f"Failed to clone repository: {e}")


def _detect_languages(root: Path, max_files: int = 5000) -> Dict[str, int]:
    """Very lightweight language histogram by file extension."""
    ext_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".vue": "Vue",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
        ".scala": "Scala",
        ".dart": "Dart",
        ".sh": "Shell",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".toml": "TOML",
        ".json": "JSON",
        ".md": "Markdown",
    }
    hist: Dict[str, int] = {}
    count = 0
    for p in root.rglob("*"):
        if p.is_file():
            count += 1
            if count > max_files:
                break
            lang = ext_map.get(p.suffix.lower())
            if lang:
                hist[lang] = hist.get(lang, 0) + 1
    return hist


def _read_snippet(path: Path, max_chars: int = 2000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]
    except Exception:
        return ""


def analyze_repo(repo_input: Optional[str]) -> RepoContext:
    """Accept a URL or local path and return a lightweight analysis summary.

    If input is None/empty or analysis fails, returns an empty context with summary that notes no repo was provided.
    """
    if not repo_input:
        return RepoContext(path=None, summary="No repository provided.")

    repo_input = repo_input.strip()
    tmpdir: Optional[tempfile.TemporaryDirectory[str]] = None
    repo_path: Optional[Path] = None
    cloned = False
    if _is_probable_git_url(repo_input):
        tmpdir = tempfile.TemporaryDirectory(prefix="acp_")
        try:
            repo_path = _clone_repo(repo_input, Path(tmpdir.name))
            cloned = True
        except Exception as e:  # pragma: no cover - environment dependent
            return RepoContext(path=None, summary=f"Repo clone failed: {e}", is_cloned=False)
    else:
        p = Path(repo_input)
        if p.exists() and p.is_dir():
            repo_path = p
        else:
            return RepoContext(path=None, summary=f"Local path not found: {repo_input}")

    assert repo_path is not None

    hist = _detect_languages(repo_path)
    key_files = [
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.toml",
        "go.mod",
        "Makefile",
    ]
    findings: Dict[str, str] = {}
    for name in key_files:
        p = repo_path / name
        if p.exists():
            findings[name] = _read_snippet(p, max_chars=3000)

    summary_lines = [
        f"Root: {repo_path}",
        "Languages: " + (", ".join(f"{k}({v})" for k, v in sorted(hist.items(), key=lambda kv: kv[1], reverse=True)) or "unknown"),
    ]
    if findings:
        summary_lines.append("Key files (snippets):")
        for k, v in findings.items():
            snippet = v.replace("\n", " ")
            summary_lines.append(f"- {k}: {snippet[:200]}")

    summary = "\n".join(summary_lines)
    return RepoContext(path=repo_path, summary=summary, is_cloned=cloned)


# ------------------------- Task resolution ------------------------


_GH_ISSUE_RE = re.compile(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<num>\d+)")


def _resolve_github_issue(issue_ref: str) -> Optional[TaskContext]:  # pragma: no cover - network dependent
    """Fetch GitHub issue by URL or repo#num.

    Requires no auth for public repos; uses GITHUB_TOKEN if available to raise limits.
    """
    owner = repo = num = None
    m = _GH_ISSUE_RE.match(issue_ref.strip())
    if m:
        owner, repo, num = m.group("owner"), m.group("repo"), m.group("num")
    else:
        # Accept owner/repo#123 form
        m2 = re.match(r"(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<num>\d+)", issue_ref.strip())
        if m2:
            owner, repo, num = m2.group("owner"), m2.group("repo"), m2.group("num")
    if not (owner and repo and num):
        return None

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{num}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
            title = data.get("title") or f"GitHub Issue {owner}/{repo}#{num}"
            body = data.get("body") or ""
            return TaskContext(source="github", title=title, description=body)
    except Exception:
        return None


_JIRA_URL_RE = re.compile(r"^(?P<base>https?://[^/]+)/browse/(?P<key>[A-Z][A-Z0-9]+-\d+)")


def _resolve_jira_issue(ref: str) -> Optional[TaskContext]:  # pragma: no cover - network dependent
    """Fetch Jira issue details given a URL or key and env configuration."""
    base = key = None
    m = _JIRA_URL_RE.match(ref.strip())
    if m:
        base, key = m.group("base"), m.group("key")
    else:
        # If only KEY-123 provided, require JIRA_BASE_URL env
        if re.match(r"^[A-Z][A-Z0-9]+-\d+$", ref.strip()):
            base = os.environ.get("JIRA_BASE_URL")
            key = ref.strip()
    if not (base and key):
        return None
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not (email and token):
        return None
    url = f"{base}/rest/api/3/issue/{key}"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, auth=(email, token))
            if r.status_code != 200:
                return None
            data = r.json()
            fields = data.get("fields") or {}
            title = fields.get("summary") or key
            description = ""
            desc = fields.get("description")
            # Description can be rich text; just coerce to string
            if isinstance(desc, str):
                description = desc
            elif isinstance(desc, dict):
                description = json.dumps(desc)
            return TaskContext(source="jira", title=title, description=description)
    except Exception:
        return None


def resolve_task(jira: Optional[str], github: Optional[str], text: Optional[str]) -> TaskContext:
    """Resolve a task from Jira/GitHub/text in priority order."""
    if github:
        gh = _resolve_github_issue(github)
        if gh:
            return gh
    if jira:
        ji = _resolve_jira_issue(jira)
        if ji:
            return ji
    t = (text or "").strip()
    if not t:
        return TaskContext(source="text", title="Untitled Task", description="")
    # Treat first line as title
    parts = t.splitlines()
    title = parts[0][:120] if parts else "Task"
    desc = t if len(parts) > 1 else (t if len(t) > 0 else "")
    return TaskContext(source="text", title=title, description=desc)


def compose_task_for_pipeline(task: TaskContext, repo: RepoContext) -> str:
    """Build a single prompt string embedding repo context and task details."""
    lines = [
        "You are part of an agentic coding pipeline that will propose a Python solution.",
    ]
    if repo.summary:
        lines.append("Repository context:\n" + repo.summary)
    lines.append("Task:")
    if task.title:
        lines.append(f"Title: {task.title}")
    if task.description:
        lines.append("Description:\n" + task.description)
    return "\n\n".join(lines)


# ---------------------- Pipeline streaming run --------------------


def build_pipeline() -> AgenticCodingPipeline:
    return AgenticCodingPipeline(
        coders=[
            CodingAgent(name="gpt-coder", llm=OpenAIClient()),
            CodingAgent(name="claude-coder", llm=ClaudeClient()),
        ],
        formatters=[FormattingAgent(name="formatter")],
        testers=[TestingAgent(name="tester", llm=ClaudeClient())],
        reviewers=[QAAgent(name="qa", llm=GeminiClient())],
    )


def run_pipeline_stream(
    repo_input: Optional[str] = None,
    jira: Optional[str] = None,
    github: Optional[str] = None,
    text: Optional[str] = None,
) -> Iterator[Tuple[str, str]]:
    """Yield (event, data) tuples for SSE-like streaming.

    Events:
    - "log" for incremental human-readable logs
    - "done" with a JSON object summarizing the final result
    """
    # Intake + analysis
    yield ("log", "Starting pipeline...\n")
    repo = analyze_repo(repo_input)
    if repo.path:
        yield ("log", f"Repo prepared: {repo.path}\n")
    else:
        yield ("log", f"Repo note: {repo.summary}\n")

    tsk = resolve_task(jira=jira, github=github, text=text)
    yield ("log", f"Task source: {tsk.source}\n")
    if tsk.title:
        yield ("log", f"Title: {tsk.title}\n")
    if tsk.description:
        yield ("log", f"Description: {tsk.description[:200]}{'...' if len(tsk.description) > 200 else ''}\n")

    prompt = compose_task_for_pipeline(tsk, repo)
    yield ("log", "Running agents (coding → format → tests → QA)...\n")
    pipeline = build_pipeline()
    result = pipeline.run(prompt)

    status = result.get("status", "unknown")
    yield ("log", f"Status: {status}\n")
    feedback = ""
    for key in ("test_output", "qa_output", "feedback"):
        if result.get(key):
            feedback = str(result.get(key))
            break
    if feedback:
        yield ("log", f"Feedback:\n{feedback}\n")

    payload = {
        "status": status,
        "repo": {
            "path": str(repo.path) if repo.path else None,
            "summary": repo.summary,
        },
        "task": {
            "source": tsk.source,
            "title": tsk.title,
            "description": tsk.description,
        },
    }
    yield ("done", json.dumps(payload))

