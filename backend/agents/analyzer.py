# backend/agents/analyzer.py
import asyncio
import os
import sys
from backend.agents.executor import ExecutorAgent


class AnalyzerAgent:
    """
    Performs reproducibility checks by re-running a compact version of the test.
    Also runs a simple cross-agent consistency check (here simulated by re-execution).
    """

    def __init__(self):
        self.executor = ExecutorAgent()
        # NOTE: Removed the asyncio fix here to prevent conflicts.

    async def analyze(self, test, initial_result):
        # Quick re-run with fewer interactions (simulate repeatability)
        # Build a reduced test: keep only goto, wait_for, and check_selector
        reduced = {
            "id": test["id"] + "_replay",
            "title": test.get("title", "") + " (replay)",
            "steps": []
        }
        for s in test["steps"]:
            # Check for structural steps
            if s["action"] in ("goto", "wait_for", "check_selector"):
                reduced["steps"].append(s)

        # save temporary artifacts into same artifacts dir
        artifacts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "artifacts")
        # Reuse executor's run_test method
        result_replay = await self.executor.run_test(reduced, artifacts_dir)

        # cross-check: compare verdict equality (pass/fail)
        reproducible = (initial_result["verdict"] == result_replay["verdict"])
        # very simple reproducibility score
        score = 1.0 if reproducible else 0.0
        return {
            "replay_verdict": result_replay["verdict"],
            "reproducible": reproducible,
            "score": score,
            "replay_artifacts": result_replay["artifacts"]
        }
