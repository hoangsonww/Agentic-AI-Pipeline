"""CLI entry-point for the agentic coding pipeline.

Enhanced to accept repository input (URL or local path) and task sources
from GitHub issues, Jira tickets, or direct text input. It streams
human-friendly progress to stdout.
"""

from __future__ import annotations

import argparse

from services import run_pipeline_stream


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic coding pipeline")
    parser.add_argument("task", nargs="?", help="Task text (optional if using --github/--jira)")
    parser.add_argument("--repo", help="Git URL or local path to repository", default=None)
    parser.add_argument("--github", help="GitHub issue URL or owner/repo#number", default=None)
    parser.add_argument("--jira", help="Jira issue URL or KEY-123 (requires env: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)", default=None)
    args = parser.parse_args()

    # Resolve text precedence: explicit positional task falls back if no issue provided
    text = args.task

    final_status = None
    final_json = None
    for ev, data in run_pipeline_stream(repo_input=args.repo, jira=args.jira, github=args.github, text=text):
        if ev == "log":
            print(data, end="")
        elif ev == "done":
            try:
                final_json = json.loads(data)
                final_status = final_json.get("status")
            except Exception:
                final_status = "unknown"
    if final_status:
        print(f"\n==> {final_status}")
    if final_json and final_json.get("task", {}).get("title"):
        print(f"Task: {final_json['task']['title']}")


if __name__ == "__main__":
    main()
