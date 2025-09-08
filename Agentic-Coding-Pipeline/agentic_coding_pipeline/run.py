"""CLI entry-point for the agentic coding pipeline."""

from __future__ import annotations

import argparse

from .agents.coding import CodingAgent
from .agents.qa import QAAgent
from .agents.testing import TestingAgent
from .pipeline import AgenticCodingPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic coding pipeline")
    parser.add_argument("task", help="High level coding task for the agents")
    args = parser.parse_args()

    pipeline = AgenticCodingPipeline(
        coder=CodingAgent(name="coder"),
        testers=[TestingAgent(name="tester")],
        reviewers=[QAAgent(name="qa")],
    )
    result = pipeline.run(args.task)
    print(result.get("status"))
    if "feedback" in result:
        print(result["feedback"])


if __name__ == "__main__":
    main()
