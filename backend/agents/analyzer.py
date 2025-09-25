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
        # Fix for Windows: Ensure the correct event loop policy is set for subprocesses.
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


    async def analyze(self, test, initial_result):
        # Quick re-run with fewer interactions (simulate repeatability)
        # Build a reduced test: keep only goto + check_selector if present
        reduced = {
            "id": test["id"] + "_replay",
            "title": test.get("title", "") + " (replay)",
            "steps": []
        }
        for s in test["steps"]:
            if s["action"] in ("goto", "check_selector", "wait_for"):
                reduced["steps"].append(s)

        # save temporary artifacts into same artifacts dir
        artifacts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "artifacts")
        result_replay = await self.executor.run_test(reduced, artifacts_dir)

        # cross-check: compare verdict equality
        reproducible = (initial_result["verdict"] == result_replay["verdict"])
        # very simple reproducibility score
        score = 1.0 if reproducible else 0.0
        return {
            "replay_verdict": result_replay["verdict"],
            "reproducible": reproducible,
            "score": score,
            "replay_artifacts": result_replay["artifacts"]
        }