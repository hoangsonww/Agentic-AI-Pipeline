"""CLI entry-point for the agentic coding pipeline."""

from __future__ import annotations

import argparse

from agents.coding import CodingAgent
from agents.formatting import FormattingAgent
from agents.qa import QAAgent
from agents.testing import TestingAgent
from pipeline import AgenticCodingPipeline

from agentic_ai.llm import ClaudeClient, GeminiClient, OpenAIClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic coding pipeline")
    parser.add_argument("task", help="High level coding task for the agents")
    args = parser.parse_args()

    pipeline = AgenticCodingPipeline(
        coders=[
            CodingAgent(name="gpt-coder", llm=OpenAIClient()),
            CodingAgent(name="claude-coder", llm=ClaudeClient()),
        ],
        formatters=[FormattingAgent(name="formatter")],
        testers=[TestingAgent(name="tester", llm=ClaudeClient())],
        reviewers=[QAAgent(name="qa", llm=GeminiClient())],
    )
    result = pipeline.run(args.task)
    print(result.get("status"))
    if "feedback" in result:
        print(result["feedback"])


if __name__ == "__main__":
    main()
