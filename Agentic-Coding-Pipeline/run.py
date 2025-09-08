"""CLI entry-point for the agentic coding pipeline."""

from __future__ import annotations

import argparse

from agents.coding import CodingAgent
from agents.qa import QAAgent
from agents.testing import TestingAgent
from pipeline import AgenticCodingPipeline

from agentic_ai.llm import ClaudeClient, GeminiClient, OpenAIClient

PROVIDERS = {
    "openai": OpenAIClient,
    "claude": ClaudeClient,
    "gemini": GeminiClient,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic coding pipeline")
    parser.add_argument("task", help="High level coding task for the agents")
    parser.add_argument(
        "--provider",
        choices=PROVIDERS.keys(),
        default="openai",
        help="LLM provider to use",
    )
    args = parser.parse_args()

    llm = PROVIDERS[args.provider]()
    pipeline = AgenticCodingPipeline(
        coder=CodingAgent(name="coder", llm=llm),
        testers=[TestingAgent(name="tester", llm=llm)],
        reviewers=[QAAgent(name="qa", llm=llm)],
    )
    result = pipeline.run(args.task)
    print(result.get("status"))
    if "feedback" in result:
        print(result["feedback"])


if __name__ == "__main__":
    main()
